"""At-most-once intent with real files, processes and counted loopback requests."""
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import subprocess
import sys
from threading import Barrier, Lock, Thread
from urllib.error import HTTPError
from urllib.request import Request, build_opener, ProxyHandler

import pytest

import src.agents.platform.writer_attempt as attempt

ROOT=Path(__file__).resolve().parents[1]


@pytest.fixture
def endpoint():
    calls=[];lock=Lock()
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*_):pass
        def do_POST(self):
            self.rfile.read(int(self.headers.get('Content-Length', '0')))
            with lock:calls.append(self.path)
            self.send_response(int(self.path[1:]));self.end_headers()
            self.wfile.write(b'{"message":"Validation Failed"}')
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    thread=Thread(target=server.serve_forever,daemon=True);thread.start()
    try:yield 'http://127.0.0.1:'+str(server.server_port),calls
    finally:server.shutdown();server.server_close();thread.join(timeout=3)


@pytest.fixture
def directory(tmp_path):
    path=tmp_path/'attempt';path.mkdir(mode=0o700);return path


def sender(endpoint,status=201):
    def send():
        try:return build_opener(ProxyHandler({})).open(Request(endpoint+'/'+str(status),method='POST',data=b'{}'),timeout=2)
        except HTTPError as error:return error
    return send


@pytest.mark.parametrize('status',[201,403,422,503])
def test_http_observation_is_not_publication_success_and_cannot_repeat(directory,endpoint,status):
    url,calls=endpoint
    assert attempt.inspect_attempt(directory)=={'state':'NOT_STARTED'}
    result=attempt.run_once(directory,operation='create_pr',send=sender(url,status))
    assert result['state']=='OBSERVED' and result['http_status']==status
    assert 'published' not in result and 'verdict' not in result
    assert attempt.inspect_attempt(directory)==result
    assert attempt.run_once(directory,operation='create_pr',send=sender(url))['state']=='BLOCKED'
    assert attempt.run_once(directory,operation='write_target',send=sender(url))['state']=='BLOCKED'
    assert calls==['/'+str(status)]


def test_eight_racing_executors_send_one_http_request(directory,endpoint):
    url,calls=endpoint;barrier=Barrier(8,timeout=5)
    def run(_):
        barrier.wait()
        return attempt.run_once(directory,operation='create_pr',send=sender(url))
    with ThreadPoolExecutor(max_workers=8) as pool:results=list(pool.map(run,range(8)))
    assert sum(r['state']=='OBSERVED' for r in results)==1
    assert sum(r['state']=='BLOCKED' for r in results)==7
    assert calls==['/201']


@pytest.mark.parametrize('when',['before_send','after_send'])
def test_process_death_is_unknown_and_never_retransmits(directory,endpoint,when):
    url,calls=endpoint
    code='''import os,sys
from urllib.request import Request, build_opener, ProxyHandler
from src.agents.platform.writer_attempt import run_once
def send():
 if sys.argv[3]=='after_send':
  build_opener(ProxyHandler({})).open(Request(sys.argv[2]+'/201',method='POST',data=b'{}'),timeout=2).read()
 os._exit(17)
run_once(sys.argv[1],operation='create_pr',send=send)
'''
    run=subprocess.run([sys.executable,'-c',code,str(directory),url,when],cwd=ROOT,capture_output=True,text=True)
    assert run.returncode==17 and not run.stdout and not run.stderr
    assert attempt.inspect_attempt(directory)['state']=='UNKNOWN'
    assert attempt.run_once(directory,operation='create_pr',send=sender(url))['state']=='BLOCKED'
    assert calls==([] if when=='before_send' else ['/201'])


@pytest.mark.parametrize('failed_fsync',[1,2,3,4,5,6])
def test_durability_failure_never_replays_the_operation(directory,endpoint,monkeypatch,failed_fsync):
    url,calls=endpoint;fsync=os.fsync;seen=[]
    def fail(fd):
        seen.append(fd)
        if len(seen)==failed_fsync:raise OSError('SYNTHETIC_SECRET_DO_NOT_LOG')
        fsync(fd)
    monkeypatch.setattr(attempt.os,'fsync',fail)
    result=attempt.run_once(directory,operation='create_pr',send=sender(url))
    assert result['state']=='UNKNOWN' and 'SYNTHETIC_SECRET' not in json.dumps(result)
    assert calls==([] if failed_fsync<=2 else ['/201'])
    monkeypatch.setattr(attempt.os,'fsync',fsync)
    assert attempt.run_once(directory,operation='create_pr',send=sender(url))['state']=='BLOCKED'
    assert calls==([] if failed_fsync<=2 else ['/201'])


@pytest.mark.parametrize('error',[TimeoutError('secret'),OSError('secret'),RuntimeError('secret')])
def test_sender_exception_stays_unknown_without_exception_text(directory,error):
    calls=[]
    def send():calls.append(True);raise error
    result=attempt.run_once(directory,operation='create_pr',send=send)
    assert result['state']=='UNKNOWN' and 'secret' not in json.dumps(result)
    assert attempt.inspect_attempt(directory)['state']=='UNKNOWN'
    assert attempt.run_once(directory,operation='create_pr',send=send)['state']=='BLOCKED'
    assert calls==[True]
    assert all('secret' not in p.read_text() for p in directory.iterdir())


@pytest.mark.parametrize('damage',['partial_intent','partial_receipt','wrong_event','missing_event','linked_event'])
def test_corrupted_or_incomplete_records_never_reopen_execution(directory,endpoint,damage):
    url,calls=endpoint
    result=attempt.run_once(directory,operation='create_pr',send=sender(url))
    assert result['state']=='OBSERVED', result
    if damage=='partial_intent':(directory/'intent.json').write_text('{')
    elif damage=='partial_receipt':(directory/'receipt.json').write_text('{')
    elif damage=='wrong_event':
        path=directory/'receipt.json';data=json.loads(path.read_text());data['capture_event_id']='../intent';path.write_text(json.dumps(data))
    else:
        path=directory/(result['capture_event_id']+'.json');path.unlink()
        if damage=='linked_event':path.symlink_to(directory/'intent.json')
    assert attempt.inspect_attempt(directory)['state']=='UNKNOWN'
    assert attempt.run_once(directory,operation='create_pr',send=sender(url))['state']=='BLOCKED'
    assert calls==['/201']


def test_read_only_status_in_fresh_process_does_not_send(directory,endpoint):
    url,calls=endpoint;result=attempt.run_once(directory,operation='create_pr',send=sender(url))
    run=subprocess.run([sys.executable,'-c','import json,sys; from src.agents.platform.writer_attempt import inspect_attempt; print(json.dumps(inspect_attempt(sys.argv[1])))',str(directory)],cwd=ROOT,capture_output=True,text=True,check=True)
    assert json.loads(run.stdout)==result and not run.stderr
    assert calls==['/201']


@pytest.mark.parametrize('kind',['missing','shared','symlink'])
def test_invalid_storage_prevents_any_sender_call(directory,kind):
    path=directory.parent/'missing'
    if kind=='shared':directory.chmod(0o755);path=directory
    if kind=='symlink':path.symlink_to(directory,target_is_directory=True)
    calls=[]
    assert attempt.run_once(path,operation='create_pr',send=lambda:calls.append(True))['state']=='UNKNOWN'
    assert calls==[]
