"""Real local files, subprocesses and loopback HTTP; no AWS service substitutes."""
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
from threading import Thread
from types import SimpleNamespace
from urllib.error import HTTPError
from urllib.request import build_opener, ProxyHandler

import pytest

import src.agents.platform.writer_capture as capture

ROOT = Path(__file__).resolve().parents[1]
RID = 'C48F:10B31A:58B2FD:7EFFBB:6AA55EA5'
CANARY = 'SYNTHETIC_SECRET_abcde12345'
BODY = {'message':'Validation Failed','errors':[{'resource':'PullRequest','field':'head',
        'code':'custom','message':'No commits between owner:main and owner:branch',
        'value':CANARY}], 'token':CANARY, 'documentation_url':'https://example.test/'+CANARY}


def sanitized(**changes):
    options = dict(operation='create_pr', status=422,
                   headers=[('x-github-request-id',RID),('Authorization','Bearer '+CANARY)],
                   body=json.dumps(BODY).encode())
    options.update(changes)
    return capture.sanitize_response(**options)


def test_validation_diagnostics_keep_semantics_without_free_text():
    result = sanitized()
    assert result['http_status'] == 422 and result['github_request_id'] == RID
    assert result['message_class'] == 'validation_failed'
    assert result['errors'] == [{'resource':'PullRequest','field':'head','code':'custom',
                                 'message_class':'no_commits_between'}]
    raw = json.dumps(result)
    for value in [CANARY,'owner:main','owner:branch','Bearer','documentation_url','Authorization']:
        assert value not in raw
    assert 'verdict' not in result and 'published' not in result


@pytest.mark.parametrize('raw,state', [
    (b'', 'empty'), (b'[]', 'non_object'), (b'null', 'non_object'), (b'\xff','invalid_json'),
    (b'{','invalid_json'), (b'{"message":"Validation Failed","message":"secret"}','invalid_json'),
    (b'{"x":NaN}','invalid_json'), (b'['*2000+b']'*2000,'invalid_json'),
    (b' '*65537,'oversize'), (None,'unavailable'),
])
def test_malformed_or_oversize_body_is_recorded_without_inference(raw,state):
    result = sanitized(body=raw)
    assert result['body_state'] == state and result['message_class']=='unclassified'
    assert result['errors']==[]


@pytest.mark.parametrize('status', [True,422.0,'422',0,600,None])
def test_invalid_http_context_cannot_create_an_observation(status):
    with pytest.raises(capture.CaptureError,match='invalid_capture_context'):
        sanitized(status=status)


@pytest.mark.parametrize('headers', [
    [('X-GitHub-Request-Id',CANARY)], [('x-github-request-id',RID+'\n')],
    [('X-GitHub-Request-Id',RID),('x-github-request-id',RID)],
    [('authorization',CANARY)], [('x-github-request-id',[RID])],
    [('x-github-request-id',RID)]+[('ignored','x')]*128,
])
def test_untrusted_or_ambiguous_request_id_is_not_persisted(headers):
    assert sanitized(headers=headers)['github_request_id'] is None


def test_error_fields_and_messages_are_independently_allowlisted_and_bounded():
    body = {'message':CANARY,'errors':[{'resource':CANARY,'field':CANARY,'code':CANARY,
                                     'message':CANARY}]*100}
    result=sanitized(body=json.dumps(body).encode())
    assert CANARY not in json.dumps(result)
    assert len(result['errors'])==16 and result['errors_truncated'] is True
    assert result['errors'][0]==dict(resource=None,field=None,code=None,message_class='unclassified')


@pytest.mark.parametrize('errors', [CANARY, None, {}, [CANARY, None, []]])
def test_nonstandard_error_entries_never_escape(errors):
    result=sanitized(body=json.dumps({'errors':errors}).encode())
    assert CANARY not in json.dumps(result)


def test_transport_failure_discards_even_a_success_shaped_body():
    result=sanitized(status=None,transport='timeout',body=b'{"published":true}')
    assert result['http_status'] is None and result['transport']=='timeout'
    assert result['body_state']=='unavailable' and result['errors']==[]


@pytest.fixture
def journal(tmp_path):
    path=tmp_path/'journal';path.mkdir(mode=0o700)
    return capture.ResponseJournal(path)


def record(journal):
    return journal.record(operation='create_pr',status=422,headers=[('x-github-request-id',RID)],
                          body=json.dumps(BODY).encode())


def test_atomic_private_file_survives_a_fresh_process(journal):
    result=record(journal);files=list(journal.directory.iterdir())
    assert len(files)==1 and files[0].name==result['event_id']+'.json'
    assert stat.S_IMODE(files[0].stat().st_mode)==0o600
    run=subprocess.run([sys.executable,'-c','import json,sys; print(json.dumps(json.load(open(sys.argv[1]))))',
                        str(files[0])],capture_output=True,text=True,check=True)
    assert json.loads(run.stdout)==result
    assert CANARY not in run.stdout and not run.stderr
    assert files[0].stat().st_size<=capture.MAX_RECORD


@pytest.mark.parametrize('kind',['missing','shared','symlink'])
def test_unsafe_or_missing_journal_never_acknowledges_capture(tmp_path,kind):
    target=tmp_path/'target';target.mkdir(mode=0o700)
    path=tmp_path/'missing'
    if kind=='shared':target.chmod(0o755);path=target
    elif kind=='symlink':path.symlink_to(target,target_is_directory=True)
    with pytest.raises(capture.CaptureError):record(capture.ResponseJournal(path))
    assert not list(target.iterdir())


def test_existing_event_cannot_be_overwritten_or_removed(journal,monkeypatch):
    monkeypatch.setattr(capture,'uuid4',lambda:SimpleNamespace(hex='a'*32))
    first=record(journal);path=journal.directory/(first['event_id']+'.json');original=path.read_bytes()
    with pytest.raises(capture.CaptureError,match='capture_store_unavailable'):record(journal)
    assert path.read_bytes()==original and len(list(journal.directory.iterdir()))==1


@pytest.mark.parametrize('failure_call',[1,2])
def test_fsync_failure_is_never_acknowledged(journal,monkeypatch,failure_call):
    fsync=os.fsync;calls=[]
    def fail(fd):
        calls.append(fd)
        if len(calls)==failure_call:raise OSError(CANARY)
        return fsync(fd)
    monkeypatch.setattr(capture.os,'fsync',fail)
    with pytest.raises(capture.CaptureError,match='^capture_store_unavailable$'):record(journal)
    files=list(journal.directory.iterdir())
    assert len(files)==(0 if failure_call==1 else 1)
    if files:assert CANARY not in files[0].read_text() and json.loads(files[0].read_text())['http_status']==422


def cli(directory,raw):
    return subprocess.run([sys.executable,str(ROOT/'scripts/capture_registry_writer_response.py'),
        '--directory',str(directory),'--operation','create_pr'],input=raw,text=True,capture_output=True)


def test_eight_cli_processes_preserve_separate_complete_records(journal):
    raw=json.dumps(dict(status=422,headers=[['X-GitHub-Request-ID',RID]],body=json.dumps(BODY),transport='response'))
    with ThreadPoolExecutor(max_workers=8) as pool:runs=list(pool.map(lambda _:cli(journal.directory,raw),range(8)))
    ids=set()
    for run in runs:
        assert run.returncode==0 and not run.stderr and CANARY not in run.stdout
        result=json.loads(run.stdout);ids.add(result['event_id'])
        assert json.loads((journal.directory/(result['event_id']+'.json')).read_text())==result
    assert len(ids)==8 and len(list(journal.directory.iterdir()))==8


# Explicit ids: pytest exports the node id in PYTEST_CURRENT_TEST, and a 131 KB id
# exceeds Linux's per-string exec limit (E2BIG) when the CLI subprocess is spawned.
@pytest.mark.parametrize('raw',[CANARY, '{"status":422,"status":200,"body":"'+CANARY+'"}',
                                 ' '*131073],ids=['canary','duplicate-status','oversize-131073'])
def test_cli_invalid_input_has_only_fixed_diagnostic(journal,raw):
    run=cli(journal.directory,raw)
    assert run.returncode==2 and not run.stdout
    assert run.stderr=='Cannot capture a valid bounded observation in a private journal.\n'
    assert not list(journal.directory.iterdir())


@pytest.mark.parametrize('status,raw,state',[(422,json.dumps(BODY).encode(),'object'),
    (503,b'<html>'+CANARY.encode(),'invalid_json'),(200,b'x'*65537,'oversize'),(204,b'','empty')])
def test_actual_http_error_and_success_streams_are_captured(journal,status,raw,state):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*_):pass
        def do_GET(self):
            self.send_response(status);self.send_header('X-GitHub-Request-Id',RID)
            self.send_header('Authorization',CANARY);self.end_headers()
            try:self.wfile.write(raw)
            except (BrokenPipeError,ConnectionResetError):pass
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    thread=Thread(target=server.serve_forever,daemon=True);thread.start()
    try:
        opener=build_opener(ProxyHandler({}))
        try:response=opener.open('http://127.0.0.1:'+str(server.server_port),timeout=2)
        except HTTPError as error:response=error
        result=capture.capture_http_response(journal,response,operation='create_pr')
        assert result['http_status']==status and result['body_state']==state
        assert result['github_request_id']==RID
        assert CANARY not in json.dumps(result)
        assert len(list(journal.directory.iterdir()))==1
        if status==422:assert result['errors'][0]['message_class']=='no_commits_between'
    finally:server.shutdown();server.server_close();thread.join(timeout=3)


def test_http_body_timeout_is_retained_without_response_text(journal):
    from threading import Event
    release=Event()
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*_):pass
        def do_GET(self):
            self.send_response(422);self.send_header('Content-Length','1000')
            self.send_header('X-GitHub-Request-Id',RID);self.end_headers()
            self.wfile.write(CANARY.encode());self.wfile.flush()
            release.wait(2)
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    thread=Thread(target=server.serve_forever,daemon=True);thread.start()
    try:
        try:response=build_opener(ProxyHandler({})).open('http://127.0.0.1:'+str(server.server_port),timeout=.1)
        except HTTPError as error:response=error
        result=capture.capture_http_response(journal,response,operation='create_pr')
        assert result['transport']=='body_unavailable' and result['http_status']==422
        assert result['body_state']=='unavailable' and result['github_request_id']==RID
        assert CANARY not in json.dumps(result)
    finally:release.set();server.shutdown();server.server_close();thread.join(timeout=3)


def test_local_http_observation_is_not_returned_when_persistence_fails(tmp_path):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*_):pass
        def do_GET(self):
            self.send_response(201);self.end_headers();self.wfile.write(b'{}')
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    thread=Thread(target=server.serve_forever,daemon=True);thread.start()
    try:
        response=build_opener(ProxyHandler({})).open('http://127.0.0.1:'+str(server.server_port),timeout=2)
        with pytest.raises(capture.CaptureError,match='capture_store_unavailable'):
            capture.capture_http_response(capture.ResponseJournal(tmp_path/'missing'),response,operation='create_pr')
        assert response.closed
    finally:server.shutdown();server.server_close();thread.join(timeout=3)
