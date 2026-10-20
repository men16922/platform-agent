"""Actual loopback transport with synthetic, independently fetched Git observations.

These tests prove local orchestration boundaries, not real GitHub permissions.
"""
from concurrent.futures import ThreadPoolExecutor
import copy
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

import src.agents.platform.writer_workflow as workflow
from src.agents.platform.writer_evidence import STAGE_KEYS, validate_stage
from tests.test_writer_evidence import diagnostic, set_value

ROOT=Path(__file__).resolve().parents[1]
FIXTURE=ROOT/'experiments/phase5-writer/fixtures/supported.synthetic.json'
CANARY='SYNTHETIC_SECRET_NOT_FOR_JOURNAL'


def prefix(data,stage):return {key:copy.deepcopy(data[key]) for key in STAGE_KEYS[stage]}


def http_adapters(url, crash=None):
    opener=build_opener(ProxyHandler({}))
    def send(spec):
        req=Request(url+spec.path,method=spec.method,
                    data=spec.body.encode() if spec.body is not None else None,
                    headers={'Content-Type':'application/json'})
        try:response=opener.open(req,timeout=3)
        except HTTPError as error:response=error
        if crash=='after_send:'+spec.operation:
            response.read();os._exit(17)
        return response
    def observe(phase,stage):
        if crash==phase+':'+stage:os._exit(17)
        with opener.open(url+'/observe/'+phase+'/'+stage,timeout=3) as response:
            return json.loads(response.read())
    return send,observe


class Lab:
    def __init__(self):
        self.evidence=json.loads(FIXTURE.read_text())
        self.statuses=dict(create_ref=201,write_target=200,write_sibling=403,create_pr=201,revoke_token=204)
        self.calls=[];self.reads=[];self.requests=[];self.lock=Lock()
        self.change=None;self.forged_status=None;self.raw=None;self.revoked_status=401

    def observation(self,phase,stage):
        if stage=='revoke_token':
            return {'expected_identity':self.evidence['expected_identity'],'identity':'installation-token',
                    'method':'GET','path':'/installation/repositories','status':self.revoked_status}
        index=workflow.STAGES.index(stage)
        prior='preflight' if index==0 else workflow.STAGES[index-1]
        data=prefix(self.evidence,stage if phase=='after' else prior)
        for operation in workflow.STAGES:
            key=workflow.CALL_KEYS[operation]
            if key in data:data[key]['status']=self.statuses[operation]
        if self.forged_status and phase=='after' and stage==self.forged_status:
            data[workflow.CALL_KEYS[stage]]['status']=201
        if phase=='before':
            result={'evidence':data,'current_snapshot':copy.deepcopy(workflow._expected_snapshot(data,prior))}
        else:result=data
        if self.change:self.change(phase,stage,result)
        return result


@pytest.fixture
def lab():
    state=Lab()
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*_):pass
        def do_GET(self):
            _,_,phase,stage=self.path.split('/')
            with state.lock:state.reads.append((phase,stage))
            data=json.dumps(state.observation(phase,stage)).encode()
            self.send_response(200);self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
        def mutate(self):
            raw=self.rfile.read(int(self.headers.get('Content-Length','0')))
            if self.path=='/installation/token':stage='revoke_token'
            elif self.path.endswith('/git/refs'):stage='create_ref'
            elif self.path.endswith('/acme.yaml'):stage='write_target'
            elif self.path.endswith('/globex.yaml'):stage='write_sibling'
            elif self.path.endswith('/pulls'):stage='create_pr'
            else:raise AssertionError('unexpected request path')
            with state.lock:
                state.calls.append(stage);state.requests.append((self.command,self.path,json.loads(raw) if raw else None))
            status=state.statuses[stage]
            body=(state.raw if state.raw is not None else b'{"message":"Validation Failed","token":"'+CANARY.encode()+b'"}') if status!=204 else b''
            self.send_response(status);self.send_header('Content-Length',str(len(body)))
            self.send_header('X-GitHub-Request-Id','C48F:10B31A:58B2FD:7EFFBB:6AA55EA5');self.end_headers();self.wfile.write(body)
        do_POST=mutate;do_PUT=mutate;do_DELETE=mutate
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    thread=Thread(target=lambda:server.serve_forever(poll_interval=.05),daemon=True);thread.start()
    state.url='http://127.0.0.1:'+str(server.server_port)
    try:yield state
    finally:server.shutdown();server.server_close();thread.join(timeout=3)


@pytest.fixture
def directory(tmp_path):
    path=tmp_path/'runs';path.mkdir(mode=0o700);return path


def run(directory,lab,review=None):
    if review is None:review=prefix(lab.evidence,'create_ref' if lab.evidence['branch_origin']=='operator' else 'preflight')
    send,observe=http_adapters(lab.url)
    return workflow.execute_workflow(directory,review,send=send,observe=observe)


@pytest.mark.parametrize('mode',['app','operator'])
def test_complete_flow_requires_all_observations_then_revokes_and_closes(directory,lab,mode):
    if mode=='operator':
        diagnostic(lab.evidence)
        lab.statuses['create_ref']=403
    result=run(directory,lab)
    assert result==dict(state='CONSISTENT',reason='four_call_evidence_consistent',cleanup='OBSERVED_INVALID',live_verified=False,diagnostic_only=mode=='operator')
    assert lab.calls==(list(workflow.STAGES) if mode=='app' else list(workflow.STAGES[1:]))+['revoke_token']
    assert run(directory,lab)['state']=='BLOCKED'
    assert lab.calls.count('revoke_token')==1
    for path in directory.rglob('*.json'):
        assert CANARY not in path.read_text()
        assert 'content' not in json.loads(path.read_text())
    request=next(r for r in lab.requests if r[1].endswith('/pulls'))
    assert request[0]=='POST' and request[2]['draft'] is True and request[2]['maintainer_can_modify'] is False
    assert request[2]['title']=='P5-E synthetic permission boundary probe'


@pytest.mark.parametrize('stage,status',[('create_ref',403),('write_target',422),('write_sibling',200),('create_pr',422)])
def test_wrong_status_stops_followup_writes_and_stays_stopped(directory,lab,stage,status):
    lab.statuses[stage]=status
    result=run(directory,lab)
    assert result['state']=='STOPPED' and result['cleanup']=='OBSERVED_INVALID'
    assert not list(directory.glob('*/'+stage+'.verified.json'))
    assert lab.calls==list(workflow.STAGES[:workflow.STAGES.index(stage)+1])+['revoke_token']
    before=lab.calls.copy();assert run(directory,lab)['state']=='BLOCKED';assert lab.calls==before


@pytest.mark.parametrize('stage,field,value',[
    ('create_ref','branch_snapshot.main','b'*40),
    ('write_target','target.after.files.platform/tenants/globex.yaml.sha','0'*40),
    ('write_target','target.after.parents',['0'*40]),
    ('write_sibling','sibling.denial_controls.token_valid',False),
    ('write_sibling','sibling.denial_controls.rate_limit_excluded',False),
    ('create_pr','pull_request.response.author_app_id',999),
    ('create_pr','pull_request.response.draft',False),
    ('create_pr','pull_request.files.complete',False),
])
def test_success_status_without_matching_independent_evidence_never_advances(directory,lab,stage,field,value):
    def change(phase,current,result):
        if phase=='after' and current==stage:
            if '.files.platform/' in field:result['target']['after']['files']['platform/tenants/globex.yaml']['sha']=value
            else:set_value(result,field,value)
    lab.change=change
    result=run(directory,lab)
    assert result['state']=='STOPPED'
    assert not list(directory.glob('*/'+stage+'.verified.json'))
    assert lab.calls==list(workflow.STAGES[:workflow.STAGES.index(stage)+1])+['revoke_token']


def test_observer_cannot_replace_captured_http_status(directory,lab):
    lab.statuses['create_pr']=422;lab.forged_status='create_pr'
    result=run(directory,lab)
    assert result['reason']=='captured_status_mismatch' and result['state']=='STOPPED'


@pytest.mark.parametrize('kind',['snapshot','credential','history','future_step'])
def test_fresh_pre_write_checks_precede_target_call(directory,lab,kind):
    def change(phase,stage,frame):
        if phase=='before' and stage=='write_target':
            if kind=='snapshot':frame['current_snapshot']['commit']='f'*40
            elif kind=='credential':frame['evidence']['credential_control']['repository_id']=999
            elif kind=='history':frame['evidence']['branch']['status']=403
            else:frame['evidence']['pull_request']=lab.evidence['pull_request']
    lab.change=change
    result=run(directory,lab)
    assert result['state']=='STOPPED' and lab.calls==['create_ref','revoke_token']


def test_eight_concurrent_workflows_share_one_fixed_mapping(directory,lab):
    barrier=Barrier(8,timeout=5)
    def execute(_):barrier.wait();return run(directory,lab)
    with ThreadPoolExecutor(max_workers=8) as pool:results=list(pool.map(execute,range(8)))
    assert sum(r['state']=='CONSISTENT' for r in results)==1,results
    assert sum(r['state']=='BLOCKED' for r in results)==7,results
    assert lab.calls==list(workflow.STAGES)+['revoke_token']
    assert len(list(directory.iterdir()))==1


@pytest.mark.parametrize('failure',['transient_missing','persistent_missing','permission'])
def test_lock_open_failure_never_bypasses_exclusive_execution(directory,lab,monkeypatch,failure):
    original_open=os.open
    attempts=[]
    def opening(path,flags,*args,**kwargs):
        if path=='workflow.lock':
            attempts.append(flags)
            if failure=='permission':raise PermissionError(13,'denied')
            if failure=='persistent_missing' or len(attempts)==1:
                raise FileNotFoundError(2,'concurrent creation lookup')
        return original_open(path,flags,*args,**kwargs)
    monkeypatch.setattr(os,'open',opening)
    result=run(directory,lab)
    if failure=='transient_missing':
        assert result['state']=='CONSISTENT',result
        assert len(attempts)==2
        assert lab.calls==list(workflow.STAGES)+['revoke_token']
        assert run(directory,lab)['state']=='BLOCKED'
        assert lab.calls==list(workflow.STAGES)+['revoke_token']
    else:
        assert result['state']=='UNKNOWN' and result['cleanup']=='NOT_ATTEMPTED'
        assert len(attempts)==(3 if failure=='persistent_missing' else 1)
        assert lab.calls==[] and lab.reads==[]
    assert all(flags & os.O_NOFOLLOW for flags in attempts)


@pytest.mark.parametrize('crash',['before:write_target','after_send:write_target'])
def test_process_restart_never_replays_a_write_or_selects_new_attempt(directory,lab,crash):
    review=prefix(lab.evidence,'preflight')
    code='''import json,sys
from src.agents.platform.writer_workflow import execute_workflow
from tests.test_writer_workflow import http_adapters
send,observe=http_adapters(sys.argv[2],sys.argv[3])
execute_workflow(sys.argv[1],json.loads(sys.stdin.read()),send=send,observe=observe)
'''
    child=subprocess.run([sys.executable,'-c',code,str(directory),lab.url,crash],cwd=ROOT,input=json.dumps(review),text=True,capture_output=True)
    assert child.returncode==17 and not child.stdout and not child.stderr
    result=run(directory,lab,review)
    if crash=='before:write_target':
        assert result['state']=='CONSISTENT'
        assert lab.calls==list(workflow.STAGES)+['revoke_token']
    else:
        assert result['state']=='UNKNOWN' and result['reason']=='attempt_unresolved'
        assert lab.calls==['create_ref','write_target','revoke_token']
    assert len(list(directory.iterdir()))==1


@pytest.mark.parametrize('which',['revoke_status','invalidity_read','float_status'])
def test_cleanup_is_not_complete_from_204_alone(directory,lab,which):
    if which=='revoke_status':lab.statuses['revoke_token']=503
    elif which=='float_status':lab.revoked_status=401.0
    else:lab.revoked_status=200
    result=run(directory,lab)
    assert result['state']=='UNKNOWN' and result['cleanup']=='UNVERIFIED'
    assert result['reason']=='cleanup_unverified'
    assert run(directory,lab)['state']=='BLOCKED' and lab.calls.count('revoke_token')==1


def test_malformed_http_body_remains_unknown_despite_good_observer(directory,lab):
    lab.raw=b'not json'
    result=run(directory,lab)
    assert result['state']=='UNKNOWN' and result['reason']=='response_body_unusable'
    assert lab.calls==['create_ref','revoke_token']


def test_observer_exception_cannot_leak_its_message(directory,lab):
    send,observe=http_adapters(lab.url)
    def broken(phase,stage):
        if stage=='write_target':raise workflow.WorkflowError(CANARY)
        return observe(phase,stage)
    result=workflow.execute_workflow(directory,prefix(lab.evidence,'preflight'),send=send,observe=broken)
    assert result['reason']=='observer_unavailable' and CANARY not in json.dumps(result)
    assert lab.calls==['create_ref','revoke_token']


def test_proof_persistence_failure_closes_without_next_write(directory,lab,monkeypatch):
    original=workflow._write_new
    def fail(fd,name,record):
        if name=='create_ref.verified.json':raise OSError(CANARY)
        return original(fd,name,record)
    monkeypatch.setattr(workflow,'_write_new',fail)
    result=run(directory,lab)
    assert result['state']=='UNKNOWN' and CANARY not in json.dumps(result)
    assert lab.calls==['create_ref','revoke_token']
    assert run(directory,lab)['state']=='BLOCKED'


def test_same_identity_branch_base_cannot_silently_change_review_binding(directory,lab):
    assert run(directory,lab)['state']=='CONSISTENT'
    review=prefix(lab.evidence,'preflight');review['seed']['parents']=['c'*40]
    result=run(directory,lab,review)
    assert result['state']=='BLOCKED' and result['reason']=='review_binding_changed'
    assert len(lab.calls)==5


@pytest.mark.parametrize('stage',workflow.STAGES)
def test_stage_validator_rejects_premature_future_or_extra_fields(lab,stage):
    data=prefix(lab.evidence,stage);data['untrusted']={'status':'approved'}
    assert validate_stage(data,stage)['verdict']=='inconclusive'


@pytest.mark.parametrize('phase',['before','after'])
def test_policy_assets_changing_during_observation_stop_further_writes(directory,lab,tmp_path,phase):
    import shutil
    policy=tmp_path/'policy';shutil.copytree(workflow.LAB,policy)
    send,observe=http_adapters(lab.url)
    def changing(current,stage):
        data=observe(current,stage)
        if current==phase and stage=='write_target':
            with (policy/'expected/acme.yaml').open('a') as stream:stream.write('# changed\n')
        return data
    result=workflow.execute_workflow(directory,prefix(lab.evidence,'preflight'),
                    send=send,observe=changing,policy_root=policy)
    assert result['state']=='STOPPED' and result['reason']=='review_policy_changed'
    assert lab.calls==(['create_ref'] if phase=='before' else ['create_ref','write_target'])+['revoke_token']


@pytest.mark.parametrize('field,value',[('http_status',422),('evidence_digest','0'*64)])
def test_resume_rejects_a_proof_not_bound_to_the_captured_attempt(directory,lab,field,value):
    review=prefix(lab.evidence,'preflight')
    code='''import json,sys
from src.agents.platform.writer_workflow import execute_workflow
from tests.test_writer_workflow import http_adapters
send,observe=http_adapters(sys.argv[2],'before:write_target')
execute_workflow(sys.argv[1],json.loads(sys.stdin.read()),send=send,observe=observe)
'''
    child=subprocess.run([sys.executable,'-c',code,str(directory),lab.url],cwd=ROOT,input=json.dumps(review),text=True,capture_output=True)
    assert child.returncode==17
    path=next(directory.glob('*/create_ref.verified.json'));proof=json.loads(path.read_text())
    proof[field]=value;path.write_text(json.dumps(proof))
    result=run(directory,lab,review)
    assert result['state']=='STOPPED' and result['reason']=='previous_observation_changed'
    assert lab.calls==['create_ref','revoke_token']
