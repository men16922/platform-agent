"""Opt-in error diagnostics using real private files; no cloud mocks."""
import base64
import json
import stat
import subprocess
import sys
from urllib.parse import quote

import pytest

from src.agents.platform.writer_diagnostics import ErrorDetailJournal,MAX_DETAIL_BYTES,MAX_MESSAGE_BYTES
from src.agents.platform.writer_capture import MAX_RECORD

SECRETS=('ghs_operatorSensitive1234567890','ghs_installationSensitive0987654321','eyJ_appJwtSensitive1234567890.sig.signature')
MESSAGE='Synthetic diagnostic: the requested operation is unavailable for this installation.'

@pytest.fixture
def detail(tmp_path):
    root=tmp_path/'details';root.mkdir(mode=0o700)
    return ErrorDetailJournal(root,secrets=SECRETS)


def record(detail,message=MESSAGE,**changes):
    args=dict(operation='create_pr',status=422,headers={'X-GitHub-Request-Id':'A:B:C:D:E','Authorization':SECRETS[0]},
              data={'message':'Validation Failed','errors':[{'message':message,'value':SECRETS[1]}],'token':SECRETS[2]})
    args.update(changes);assert detail.record(**args) is None


def test_unknown_custom_reason_survives_a_fresh_process_with_private_storage(detail):
    record(detail);file=next(detail.directory.glob('*.json'))
    assert stat.S_IMODE(file.stat().st_mode)==0o600
    run=subprocess.run([sys.executable,'-c','import json,sys; print(json.load(open(sys.argv[1]))["messages"][0]["excerpt"])',str(file)],capture_output=True,text=True,check=True)
    assert run.stdout.strip()==MESSAGE and not run.stderr
    data=json.loads(file.read_text());assert data['github_request_id']=='A:B:C:D:E'
    assert data['scope']=='operator_diagnostic_only' and 'verdict' not in data and 'published' not in data
    assert 'Authorization' not in file.read_text() and all(s not in file.read_text() for s in SECRETS)


@pytest.mark.parametrize('encoding',['literal','url','base64','zero_width'])
def test_credentials_are_removed_before_excerpt_truncation(detail,encoding):
    transform={'literal':lambda x:x,'url':lambda x:quote(x,safe=''),
               'base64':lambda x:base64.b64encode(x.encode()).decode(),
               'zero_width':lambda x:x[:5]+'\u200b'+x[5:]}[encoding]
    value='reason '+('word '*95)+' '.join(transform(s) for s in SECRETS)
    record(detail,value);raw=next(detail.directory.glob('*.json')).read_text()
    assert all(s not in raw and transform(s) not in raw for s in SECRETS)
    excerpt=json.loads(raw)['messages'][0]['excerpt']
    assert 'ghs_' not in excerpt and 'Sensitive' not in excerpt and '[REDACTED]' in excerpt


def test_secret_shapes_urls_pem_and_control_characters_are_scrubbed(detail):
    record(detail,'Reason https://private.invalid/data Bearer abcdefghij github_pat_abc123456 \x1b[31m\x00 '
           '-----BEGIN PRIVATE KEY-----\nSYNTHETICMATERIAL\n-----END PRIVATE KEY----- end')
    raw=next(detail.directory.glob('*.json')).read_text()
    for text in ('private.invalid','abcdefghij','abc123456','SYNTHETICMATERIAL','PRIVATE KEY','\\u0000','\\u001b'):
        assert text not in raw
    assert 'Reason' in raw and 'end' in raw


def test_total_excerpt_budget_is_utf8_bounded_with_truncation(detail):
    data={'message':'상세 '*600,'errors':[{'message':'문제 '*600} for _ in range(100)]}
    record(detail,data=data);file=next(detail.directory.glob('*.json'));result=json.loads(file.read_text())
    assert sum(len(x['excerpt'].encode()) for x in result['messages'])<=MAX_DETAIL_BYTES
    assert all(len(x['excerpt'].encode())<=MAX_MESSAGE_BYTES for x in result['messages'])
    assert result['errors_truncated'] and result['omitted_messages'] and any(x['truncated'] for x in result['messages'])
    assert file.stat().st_size<=MAX_RECORD


@pytest.mark.parametrize('changes',[{'status':201},{'status':403},{'operation':'write_sibling'},
    {'data':{'message':'Validation Failed','errors':[{'message':'No commits between main and branch'}]}},
    {'data':{'token':SECRETS[0],'errors':[{'value':SECRETS[1]}]}}])
def test_other_responses_and_nonmessage_fields_are_not_saved(detail,changes):
    record(detail,**changes);assert not list(detail.directory.iterdir())


@pytest.mark.parametrize('kind',['shared','symlink','missing'])
def test_unsafe_detail_directory_is_rejected_before_capture(tmp_path,kind):
    path=tmp_path/'detail'
    if kind=='shared':path.mkdir(mode=0o755)
    if kind=='symlink':
        target=tmp_path/'target';target.mkdir(mode=0o700);path.symlink_to(target)
    with pytest.raises((ValueError,OSError)):ErrorDetailJournal(path,secrets=SECRETS)


def test_duplicate_event_never_overwrites(detail,monkeypatch):
    import src.agents.platform.writer_diagnostics as module
    from types import SimpleNamespace
    monkeypatch.setattr(module,'uuid4',lambda:SimpleNamespace(hex='d'*32))
    record(detail);file=next(detail.directory.glob('*.json'));before=file.read_bytes()
    with pytest.raises(FileExistsError):record(detail,'different reason')
    assert file.read_bytes()==before
