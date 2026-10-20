#!/usr/bin/env python3
"""Exercise the packaged Lambda contract against real DynamoDB Local only."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import hashlib
import ipaddress
from pathlib import Path
import sys
from threading import Barrier
from types import SimpleNamespace
from urllib.parse import urlparse
from uuid import uuid4


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--asset', type=Path, required=True)
    parser.add_argument('--endpoint', required=True)
    args = parser.parse_args()
    endpoint = urlparse(args.endpoint)
    if (endpoint.scheme != 'http' or not endpoint.hostname
            or not ipaddress.ip_address(endpoint.hostname).is_loopback
            or endpoint.username or endpoint.password or endpoint.path not in ('','/')
            or endpoint.query or endpoint.fragment):
        raise ValueError('DynamoDB Local must use an explicit loopback address')
    asset = args.asset.resolve()
    sys.path.insert(0, str(asset))
    import boto3
    from botocore.config import Config
    from src.agents.platform import registry_lambda as runtime
    from src.agents.platform.registry_plan_store import DynamoPlanStore
    from src.agents.platform.registry_readers import DynamoCurrentUsers
    from src.agents.platform.registry_planner import SnapshotFile
    assert Path(runtime.__file__).resolve().is_relative_to(asset), 'handler must come from packaged asset'
    root = Path(__file__).resolve().parents[1]
    reads = []
    class LocalSnapshot:
        """Three repository YAML fixtures, not a simulated AWS service."""
        def resolve_revision(self):
            reads.append('revision')
            return 'a' * 40
        def read_file(self, path, *, revision):
            reads.append(path)
            data = (root / path).read_bytes()
            sha = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
            return SnapshotFile(revision, path, sha, data)
    def database():
        return boto3.resource('dynamodb', endpoint_url=args.endpoint, region_name='ap-northeast-2',
            aws_access_key_id='local', aws_secret_access_key='local',
            config=Config(connect_timeout=1, read_timeout=2, retries={'total_max_attempts':1}, proxies={}))
    db = database()
    created = []
    def table(key):
        value = db.create_table(TableName='planner-local-' + uuid4().hex,
            KeySchema=[{'AttributeName':key,'KeyType':'HASH'}],
            AttributeDefinitions=[{'AttributeName':key,'AttributeType':'S'}],
            BillingMode='PAY_PER_REQUEST')
        created.append(value)
        return value
    try:
        users_table, plans = table('username'), table('request_id')
        def dependencies():
            # A fresh SDK resource per invocation, including concurrent callers.
            resource=database()
            return (DynamoCurrentUsers(resource.Table(users_table.name)), LocalSnapshot(),
                    DynamoPlanStore(resource.Table(plans.name)))
        event = dict(subject='operator',request=dict(tenant='acme',env='prod',capability='logging',version='7.1.0'))
        grant = dict(username='operator',role='operator',registry_write_tenants=['acme'])
        users_table.put_item(Item=grant)
        users_table.put_item(Item={**grant,'username':'other'})
        # Exercise the actual entry point using explicit local dependencies. Neither
        # an AWS API nor the production factory is mocked; both tables are real.
        runtime.production_dependencies = dependencies
        allowed = runtime.handler(event,SimpleNamespace(aws_request_id='packaged-context'))
        assert allowed['status']==200,allowed
        row=plans.get_item(Key={'request_id':'packaged-context'},ConsistentRead=True)['Item']
        assert row['state']=='PREVIEW' and 'ttl' in row
        assert allowed['plan']['request_id']=='packaged-context'
        print('PASS packaged handler uses context request ID and persists preview before success',flush=True)
        now=datetime.now(timezone.utc)
        def invoke(operation,request_id='packaged-context',subject='operator',at=None):
            return runtime.handle_event(dict(operation=operation,subject=subject,request={'request_id':request_id}),
                dependencies_factory=dependencies,request_id='invoke-unused',clock=lambda:at or datetime.now(timezone.utc))
        before=len(reads)
        result=invoke('status')
        assert result['observation']['state']=='PREVIEW' and result['observation']['published'] is False
        assert len(reads)==before and plans.get_item(Key={'request_id':'packaged-context'})['Item']==row
        assert runtime.handler(event,SimpleNamespace(aws_request_id='packaged-context'))['status']==409
        print('PASS status is minimal/nonmutating and duplicate preview cannot overwrite the saved ID',flush=True)
        barrier=Barrier(8)
        def prepare_once(_):
            barrier.wait(timeout=10)
            return invoke('prepare')
        with ThreadPoolExecutor(max_workers=8) as pool: outcomes=list(pool.map(prepare_once,range(8)))
        assert sorted(r['status'] for r in outcomes)==[200]+[409]*7,outcomes
        success=next(r for r in outcomes if r['status']==200)
        assert success['preparation']==dict(request_id='packaged-context',state='CLAIMED',published=False)
        claimed=plans.get_item(Key={'request_id':'packaged-context'},ConsistentRead=True)['Item']
        assert claimed['state']=='CLAIMED' and 'ttl' not in claimed and claimed['payload']==row['payload']
        before=len(reads)
        observed=invoke('status',at=now+timedelta(minutes=6))
        assert observed['observation']['state']=='CLAIMED' and observed['observation']['expired'] is True
        assert observed['observation']['published'] is False and len(reads)==before
        print('PASS eight real DB preparations: one claim/seven conflicts; expired claim retained without TTL or publication',flush=True)
        assert invoke('status',subject='other')['status']==404
        assert invoke('status',request_id='missing')['status']==404
        users_table.put_item(Item=dict(username='operator',role='admin',tenants=['acme']))
        assert invoke('status')['status']==403
        assert runtime.handler(event,SimpleNamespace(aws_request_id='denied'))['status']==403
        assert 'Item' not in plans.get_item(Key={'request_id':'denied'})
        users_table.delete_item(Key={'username':'operator'})
        assert invoke('status')['status']==403
        users_table.put_item(Item=grant)
        assert invoke('status')['status']==200
        print('PASS current grant revocation/deleted user403 and foreign/missing request404',flush=True)
        plans.delete();created.remove(plans)
        assert invoke('status')==dict(ok=False,status=503,error='plan_store_unavailable')
        assert runtime.handler(event,SimpleNamespace(aws_request_id='lost-store'))==dict(ok=False,status=503,error='plan_store_unavailable')
        users_table.delete();created.remove(users_table)
        assert runtime.handler(event,SimpleNamespace(aws_request_id='lost-users'))==dict(ok=False,status=503,error='user_store_unavailable')
        print('PASS real missing plan/user tables return sanitized503; no unsaved preview success',flush=True)
    finally:
        for item in created:item.delete()
    print('PASS owned local tables deleted; no cloud endpoint or GitHub API used',flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(f'FAILED: {error}')
        raise SystemExit(1)
