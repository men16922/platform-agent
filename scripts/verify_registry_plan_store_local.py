#!/usr/bin/env python3
"""Real DynamoDB Local checks for preview persistence and conditional consumption."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import hashlib
import ipaddress
import json
import multiprocessing
import os
import subprocess
from tempfile import TemporaryDirectory
from pathlib import Path
import sys
from threading import Barrier
from urllib.parse import urlparse
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.agents.platform.registry_plan_store import DynamoPlanStore, StoredPreview
from src.agents.platform.registry_planner import SnapshotFile, PlannerError
from src.agents.platform.registry_preview_service import handle_stored_event
from src.agents.platform.registry_readers import DynamoCurrentUsers

NOW = datetime(2026, 9, 12, tzinfo=timezone.utc)
REQUEST = dict(tenant='acme', env='prod', capability='logging', version='7.1.0')


def db(endpoint):
    import boto3
    from botocore.config import Config
    url = urlparse(endpoint)
    if (url.scheme != 'http' or not url.hostname or not ipaddress.ip_address(url.hostname).is_loopback
            or url.username or url.password or url.path not in ('', '/') or url.query or url.fragment):
        raise ValueError('explicit_loopback_endpoint_required')
    return boto3.resource('dynamodb', endpoint_url=endpoint, region_name='ap-northeast-2',
        aws_access_key_id='local', aws_secret_access_key='local',
        config=Config(connect_timeout=1, read_timeout=2, retries={'max_attempts': 0}))


class Files:
    revision = 'a' * 40
    def resolve_revision(self): return self.revision
    def read_file(self, path, *, revision):
        data = (ROOT / path).read_bytes()
        sha = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
        return SnapshotFile(revision, path, sha, data)


def child_read(endpoint, table, request_id, queue):
    row = DynamoPlanStore(db(endpoint).Table(table)).get(request_id)
    queue.put({'state': row['state'], 'payload': row['payload']})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--endpoint', required=True)
    args = parser.parse_args(); resource = db(args.endpoint)
    created = []
    def table(key):
        t = resource.create_table(TableName='plan-store-local-'+uuid4().hex,
            KeySchema=[{'AttributeName':key,'KeyType':'HASH'}],
            AttributeDefinitions=[{'AttributeName':key,'AttributeType':'S'}],
            BillingMode='PAY_PER_REQUEST')
        created.append(t); return t
    try:
        plans = table('request_id'); users_table = table('username')
        store = DynamoPlanStore(plans); users = DynamoCurrentUsers(users_table)
        grant = {'username':'operator','role':'operator','registry_write_tenants':['acme']}
        users_table.put_item(Item=grant)
        users_table.put_item(Item={**grant,'username':'someone-else'})
        output = (ROOT/'platform/tenants/acme.yaml').read_text()+'      logging: loki 7.1.0\n'
        def preview(name, **overrides):
            opts = dict(operation='preview', dependencies_factory=lambda:(users, Files(), store),
                        request_id=name, clock=lambda:NOW)
            opts.update(overrides)
            return handle_stored_event({'subject':'Operator','request':REQUEST}, **opts)
        def seed(name):
            result = preview(name)
            assert result['ok'] is True, result
            row = store.get(name)
            assert row is not None, 'preview acknowledged without persisted record'
            record = StoredPreview(name, row['subject'], row['payload'], int(row['expires_us']))
            assert record.data()['output'] == output
            assert result == dict(ok=True,status=200,plan=record.data()['plan'])
            return record
        def consume(name, **overrides):
            opts=dict(subject='operator', store=store, users=users, reader=Files(), clock=lambda:NOW)
            opts.update(overrides)
            result = handle_stored_event({'subject':opts['subject'],'request':{'request_id':name}},
                operation='prepare', dependencies_factory=lambda:(opts['users'],opts['reader'],opts['store']),
                request_id='unused', clock=opts['clock'])
            if result['ok']:
                assert result == dict(ok=True,status=200,preparation={
                    'request_id':name,'state':'CLAIMED','published':False}), result
                return result['preparation']
            return result
        def status_of(name, **overrides):
            opts=dict(subject='operator',store=store,users=users,clock=lambda:NOW)
            opts.update(overrides)
            return handle_stored_event({'subject':opts['subject'],'request':{'request_id':name}},
                operation='status',dependencies_factory=lambda:(opts['users'],None,opts['store']),
                request_id='unused',clock=opts['clock'])
        record=seed('persist')
        before=store.get('persist')
        observed=status_of('persist')
        assert observed['observation']==dict(request_id='persist',state='PREVIEW',published=False,
            expires_at=record.data()['plan']['expires_at'],expired=False),observed
        assert store.get('persist')==before
        print('PASS own status returns minimal observation without changing storage or reading GitHub',flush=True)
        ctx=multiprocessing.get_context('spawn'); q=ctx.Queue(); proc=ctx.Process(target=child_read,args=(args.endpoint,plans.name,'persist',q))
        proc.start(); answer=q.get(timeout=15); proc.join(timeout=15)
        assert proc.exitcode==0 and answer=={'state':'PREVIEW','payload':record.payload}
        print('PASS new process reads complete server payload',flush=True)
        try: store.put(record)
        except PlannerError as e: assert e.code=='plan_conflict'
        else: raise AssertionError('duplicate overwrite accepted')
        print('PASS duplicate request_id cannot overwrite',flush=True)
        seed('race')
        barrier = Barrier(8, timeout=15)
        class RacingStore(DynamoPlanStore):
            def claim(self, row, *, now):
                barrier.wait()
                return super().claim(row, now=now)
        def attempt(_):
            # Each worker uses its own boto3 resource; boto3 resource objects are not thread-safe.
            client=db(args.endpoint)
            return consume('race',store=RacingStore(client.Table(plans.name)),users=DynamoCurrentUsers(client.Table(users_table.name)))
        with ThreadPoolExecutor(max_workers=8) as pool: results=list(pool.map(attempt,range(8)))
        counts={'claimed':sum(x.get('state')=='CLAIMED' for x in results), 'conflicts':sum(x.get('error')=='plan_conflict' for x in results)}
        assert counts=={'claimed':1,'conflicts':7}, counts
        assert consume('race')['error']=='plan_conflict'
        assert 'ttl' not in store.get('race'), 'claimed records must survive preview TTL'
        observed=status_of('race',clock=lambda:NOW+timedelta(days=1))
        assert observed['observation']['state']=='CLAIMED' and observed['observation']['expired'] is True
        assert observed['observation']['published'] is False and 'claim_id' not in observed['observation']
        print('PASS 8 concurrent consumers -> 1 claim, 7 conflicts; retry remains closed',flush=True)
        seed('status-race')
        class ClaimDuringStatus(DynamoPlanStore):
            reads=0
            def get(self,request_id):
                row=super().get(request_id);self.reads+=1
                if self.reads==1:self.claim(row,now=NOW)
                return row
        observed=status_of('status-race',store=ClaimDuringStatus(plans))
        assert observed['observation']['state']=='CLAIMED',observed
        print('PASS status sees concurrent claim after authorization; expired claim remains retained',flush=True)
        seed('status-reopened');consume('status-reopened')
        class ReopenDuringStatus(DynamoPlanStore):
            reads=0
            def get(self,request_id):
                row=super().get(request_id);self.reads+=1
                if self.reads==1:
                    plans.update_item(Key={'request_id':request_id},
                        UpdateExpression='SET #s=:preview, #ttl=:ttl REMOVE claim_id',
                        ExpressionAttributeNames={'#s':'state','#ttl':'ttl'},
                        ExpressionAttributeValues={':preview':'PREVIEW',':ttl':row['expires_us']//1_000_000})
                return row
        assert status_of('status-reopened',store=ReopenDuringStatus(plans))==dict(
            ok=False,status=409,error='plan_changed_during_read')
        print('PASS status refuses a claim reopened during its read window',flush=True)
        seed('foreign'); assert consume('foreign',subject='someone-else')['status']==404
        assert status_of('foreign',subject='someone-else')['status']==404
        assert store.get('foreign')['state']=='PREVIEW'
        print('PASS subject swap cannot consume another preview',flush=True)
        seed('revoked'); users_table.put_item(Item={**grant,'registry_write_tenants':[]})
        assert consume('revoked')==dict(ok=False,status=403,error='registry_write_forbidden')
        assert status_of('revoked')==dict(ok=False,status=403,error='registry_write_forbidden')
        assert store.get('revoked')['state']=='PREVIEW'
        users_table.put_item(Item=grant)
        print('PASS current grant revocation precedes claim',flush=True)
        seed('changed'); changed=Files(); changed.revision='b'*40
        assert consume('changed',reader=changed)['status']==409 and store.get('changed')['state']=='PREVIEW'
        print('PASS changed base revision requires replan',flush=True)
        seed('expired'); assert consume('expired',clock=lambda:NOW+timedelta(minutes=5))['error']=='plan_expired'
        assert status_of('expired',clock=lambda:NOW+timedelta(minutes=5))['observation']['expired'] is True
        assert store.get('expired')['state']=='PREVIEW'
        seed('late'); ticks=iter([NOW,NOW+timedelta(minutes=5)])
        assert consume('late',clock=lambda:next(ticks)).get('error')=='plan_conflict'
        assert store.get('late')['state']=='PREVIEW'
        print('PASS TTL deletion not required; expiry during authorization/read also rejects',flush=True)
        seed('corrupt'); row=store.get('corrupt'); data=json.loads(row['payload']); data['output']='forged'
        plans.update_item(Key={'request_id':'corrupt'},UpdateExpression='SET payload=:p',ExpressionAttributeValues={':p':json.dumps(data,sort_keys=True,ensure_ascii=False)})
        assert consume('corrupt')['error']=='invalid_stored_plan' and store.get('corrupt')['state']=='PREVIEW'
        assert status_of('corrupt')==dict(ok=False,status=503,error='invalid_stored_plan')
        print('PASS stored output corruption rejected',flush=True)
        for phase, ticks in [('planning',[NOW,NOW+timedelta(minutes=5)]),
                             ('persisting',[NOW,NOW,NOW+timedelta(minutes=5)])]:
            moments=iter(ticks)
            result=preview('slow-'+phase,clock=lambda:next(moments))
            assert result == dict(ok=False,status=409,error='plan_expired'), result
            assert (store.get('slow-'+phase) is not None) == (phase=='persisting')
        print('PASS service never returns expired success after planning or persistence',flush=True)
        # Real CLI invocations use a committed fixture and the same durable local table.
        with TemporaryDirectory(prefix='registry-service-fixture-') as directory:
            fixture=Path(directory)
            for name in ['platform/catalog.yaml','platform/tenants/acme.yaml',
                         'infra/onprem/addons/values/loki.yaml']:
                target=fixture/name; target.parent.mkdir(parents=True,exist_ok=True)
                target.write_bytes((ROOT/name).read_bytes())
            def git(*args):
                subprocess.run(['git','-C',directory,*args],check=True,capture_output=True)
            git('init','-q'); git('add','platform','infra')
            git('-c','user.name=Local Test','-c','user.email=local@example.test','commit','-qm','fixture')
            userfile=fixture/'users.json'; userfile.write_text(json.dumps({'operator':grant}))
            env={**os.environ,'VERCEL':'','REGISTRY_PLANNER_MODE':'local',
                 'REGISTRY_PLANNER_LOCAL_REPO':directory,'REGISTRY_PLANNER_LOCAL_USERS':str(userfile),
                 'REGISTRY_PLANNER_LOCAL_PLAN_ENDPOINT':args.endpoint,
                 'REGISTRY_PLANNER_LOCAL_PLAN_TABLE':plans.name,'PYTHONPATH':str(ROOT)}
            def cli(request, prepare=False, environment=None, status=False):
                result=subprocess.run([sys.executable,'-m','src.agents.platform.registry_local']+
                    (['--status'] if status else ['--prepare'] if prepare else []),cwd=directory,env=env if environment is None else environment,
                    input=json.dumps({'subject':'operator','request':request}),text=True,capture_output=True,check=True)
                assert not result.stderr
                return json.loads(result.stdout)
            result=cli(REQUEST); assert result['ok'] is True, result
            planid=result['plan']['request_id']
            assert store.get(planid)['state']=='PREVIEW'
            assert cli({'request_id':planid},status=True)['observation']['state']=='PREVIEW'
            prepared=cli({'request_id':planid},True)
            assert prepared==dict(ok=True,status=200,preparation={
                'request_id':planid,'state':'CLAIMED','published':False}), prepared
            assert cli({'request_id':planid},True)['error']=='plan_conflict'
            observed=cli({'request_id':planid},status=True)['observation']
            assert observed['state']=='CLAIMED' and observed['published'] is False
            assert cli(REQUEST,environment={**env,'REGISTRY_PLANNER_LOCAL_PLAN_TABLE':'missing-'+uuid4().hex})['error']=='plan_store_unavailable'
            assert cli(REQUEST,environment={k:v for k,v in env.items() if k!='REGISTRY_PLANNER_LOCAL_PLAN_ENDPOINT'})['ok'] is False
        print('PASS real Git + separate CLI preview/prepare processes; missing storage never succeeds',flush=True)
        seed('lost-users'); users_table.delete(); created.remove(users_table)
        assert consume('lost-users')['error']=='user_store_unavailable'
        assert status_of('lost-users')['error']=='user_store_unavailable'
        assert preview('no-user-store')['error']=='user_store_unavailable'
        assert store.get('lost-users')['state']=='PREVIEW'
        print('PASS real missing users table fails closed before claim',flush=True)
        users_table = table('username'); users_table.put_item(Item=grant)
        users = DynamoCurrentUsers(users_table)
        plans.delete(); created.remove(plans)
        assert consume('persist')['error']=='plan_store_unavailable'
        assert status_of('persist')['error']=='plan_store_unavailable'
        assert preview('no-plan-store')==dict(ok=False,status=503,error='plan_store_unavailable')
        try: store.put(record)
        except PlannerError as e: assert e.code=='plan_store_unavailable'
        else: raise AssertionError('missing plan store accepted write')
        print('PASS real missing plan table rejects reads/writes; no publication adapter invoked',flush=True)
    finally:
        for item in created: item.delete()
    print('PASS temporary local tables removed; no AWS endpoint or GitHub write used',flush=True)


if __name__=='__main__':
    try:
        main()
    except Exception as error:
        print('FAILED: '+type(error).__name__, flush=True)
        raise SystemExit(1)
