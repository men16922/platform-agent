"""Pure stored-artifact validation; DynamoDB behavior is checked by local script."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import hashlib
from pathlib import Path

import pytest
from src.agents.platform.registry_plan_store import stored_preview
from src.agents.platform.registry_planner import plan_snapshot, SnapshotFile, PlannerError

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 9, 12, tzinfo=timezone.utc)
REQUEST = dict(tenant='acme', env='prod', capability='logging', version='7.1.0')

class Files:
    def resolve_revision(self): return 'a' * 40
    def read_file(self, path, *, revision):
        data = (ROOT / path).read_bytes()
        blob = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
        return SnapshotFile(revision, path, blob, data)

@pytest.fixture
def artifact():
    plan = plan_snapshot(REQUEST, subject='operator', reader=Files(), request_id='stored-1', now=NOW)
    output = (ROOT / 'platform/tenants/acme.yaml').read_text() + '      logging: loki 7.1.0\n'
    return plan, output


def make(artifact, **changes):
    plan, output = artifact
    values = dict(plan=plan, output=output, subject='operator', request=REQUEST, now=NOW)
    values.update(changes)
    return stored_preview(**values)


def test_real_plan_output_roundtrip_has_no_shared_mutable_payload(artifact):
    record = make(artifact)
    decoded = record.data(); decoded['request']['tenant'] = 'globex'
    assert record.data()['request']['tenant'] == 'acme'
    assert record.data()['output'] == artifact[1]
    assert record.expires_us == int((NOW + timedelta(minutes=5)).timestamp()) * 1000000


@pytest.mark.parametrize('field,value', [
    ('subject', 'other'), ('subject', 'Operator'), ('output', 'forged'),
    ('request', {**REQUEST, 'tenant': 'globex'}),
    ('request', {**REQUEST, 'path': 'forged'}),
    ('now', NOW + timedelta(minutes=5)), ('now', NOW - timedelta(microseconds=1)),
    ('now', NOW.replace(tzinfo=None)),
])
def test_rejects_misbound_or_expired_artifact(artifact, field, value):
    with pytest.raises(PlannerError): make(artifact, **{field:value})


@pytest.mark.parametrize('field,value', [('request_id','../bad'),('digest','0'*64),
    ('diff','forged'),('path','platform/tenants/globex.yaml'),('base_commit','b'*40)])
def test_envelope_tampering_does_not_become_a_saved_plan(artifact, field, value):
    with pytest.raises(PlannerError): make((replace(artifact[0], **{field:value}), artifact[1]))


@pytest.mark.parametrize('state,expired',[('PREVIEW',False),('PREVIEW',True),('CLAIMED',False),('CLAIMED',True)])
def test_status_record_retains_expired_state_without_exposing_claim_or_payload(artifact,state,expired):
    from src.agents.platform.registry_plan_store import _status_record
    record=make(artifact)
    row={'request_id':record.request_id,'subject':record.subject,'payload':record.payload,
         'expires_us':record.expires_us,'state':state}
    if state=='PREVIEW':row['ttl']=record.expires_us//1_000_000
    else:row['claim_id']='a'*32
    observation,_=_status_record(row,request_id=record.request_id,subject='Operator',
        now=NOW+timedelta(minutes=5) if expired else NOW)
    assert observation=={'request_id':record.request_id,'state':state,'published':False,
                        'expires_at':artifact[0].expires_at,'expired':expired}
    assert row['state']==state


@pytest.mark.parametrize('field,value',[
    ('state','SUCCEEDED'),('state','UNKNOWN'),('claim_id','a'*32),('ttl',0),
    ('payload','{}'),('payload','not-json'),('request_id','different'),('expires_us',1),
])
def test_invalid_status_record_is_not_a_publication_receipt(artifact,field,value):
    from src.agents.platform.registry_plan_store import _status_record
    record=make(artifact)
    row={'request_id':record.request_id,'subject':record.subject,'payload':record.payload,
         'expires_us':record.expires_us,'state':'PREVIEW','ttl':record.expires_us//1_000_000}
    row[field]=value
    with pytest.raises(PlannerError) as error:
        _status_record(row,request_id=record.request_id,subject='operator',now=NOW)
    assert error.value.code=='invalid_stored_plan'


@pytest.mark.parametrize('claim_id,ttl',[('',False),('a'*31,False),('a'*32,True),(None,False)])
def test_claimed_status_requires_retained_claim_and_no_ttl(artifact,claim_id,ttl):
    from src.agents.platform.registry_plan_store import _status_record
    record=make(artifact)
    row={'request_id':record.request_id,'subject':record.subject,'payload':record.payload,
         'expires_us':record.expires_us,'state':'CLAIMED','claim_id':claim_id}
    if ttl:row['ttl']=record.expires_us//1_000_000
    with pytest.raises(PlannerError):_status_record(row,request_id=record.request_id,subject='operator',now=NOW)
