"""Inspect synthesized CDK resources, not TypeScript permission strings."""
import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest

from tests._ts_toolchain import require_ts_toolchain

ROOT = Path(__file__).resolve().parents[1]
STACKS = ROOT / 'src/stacks'


@pytest.fixture(scope='module')
def synth(tmp_path_factory):
    compiler = STACKS / 'node_modules/.bin/tsc'
    require_ts_toolchain(compiler, shutil.which('node') is not None,
                         'Run npm ci in src/stacks to validate planner CDK')
    out = tmp_path_factory.mktemp('planner-cdk')
    subprocess.run([str(compiler), 'registry_planner_stack.ts', '--target', 'es2020',
                    '--module', 'commonjs', '--skipLibCheck', '--esModuleInterop',
                    '--outDir', str(out)], cwd=STACKS, check=True, capture_output=True, text=True)
    asset = out / 'asset'; asset.mkdir(); (asset / 'handler.py').write_text('# synthetic test asset\n')
    script = out / 'synth.js'
    script.write_text('''const cdk=require('aws-cdk-lib');
const {Template}=require('aws-cdk-lib/assertions');
const {RegistryPlannerStack}=require('./registry_planner_stack');
const config=JSON.parse(process.argv[2]);
const stack=new RegistryPlannerStack(new cdk.App(), 'PlannerTest', config);
process.stdout.write(JSON.stringify(Template.fromStack(stack).toJSON()));
''')
    config = dict(env=dict(account='111111111111', region='ap-northeast-2'), assetPath=str(asset),
                  usersTableArn='arn:aws:dynamodb:ap-northeast-2:111111111111:table/users',
                  repository='fixture/registry', branch='main', vercelTeam='team', vercelProject='project',
                  oidcProviderArn='arn:aws:iam::111111111111:oidc-provider/oidc.vercel.com/team')
    def run(**overrides):
        result = subprocess.run(['node', str(script), json.dumps({**config, **overrides})],
            env={**os.environ, 'NODE_PATH': str(STACKS / 'node_modules')}, text=True,
            capture_output=True)
        return result
    return run


def test_only_required_resources_and_exact_permission_targets(synth):
    result = synth(); assert result.returncode == 0, result.stderr
    resources = json.loads(result.stdout)['Resources']
    kinds = [r['Type'] for r in resources.values()]
    assert sorted(kinds) == sorted(['AWS::Logs::LogGroup', 'AWS::IAM::Role', 'AWS::IAM::Role',
                                   'AWS::IAM::Policy', 'AWS::IAM::Policy', 'AWS::Lambda::Function', 'AWS::DynamoDB::Table'])
    fn_id, fn = next((key, r['Properties']) for key, r in resources.items() if r['Type'] == 'AWS::Lambda::Function')
    log_id = next(key for key, r in resources.items() if r['Type'] == 'AWS::Logs::LogGroup')
    assert fn['Runtime'] == 'python3.13' and fn['Architectures'] == ['arm64']
    assert set(fn['Environment']['Variables']) == {'REGISTRY_USERS_TABLE', 'REGISTRY_PLANS_TABLE', 'REGISTRY_REPOSITORY', 'REGISTRY_BRANCH'}
    permissions = {}
    for resource in resources.values():
        assert 'ManagedPolicyArns' not in resource.get('Properties', {})
        if resource['Type'] != 'AWS::IAM::Policy': continue
        for statement in resource['Properties']['PolicyDocument']['Statement']:
            actions = statement['Action']
            for action in [actions] if isinstance(actions, str) else actions:
                permissions.setdefault(action, []).append(statement['Resource'])
    plan_id = next(key for key,r in resources.items() if r['Type']=='AWS::DynamoDB::Table')
    assert fn['Environment']['Variables']['REGISTRY_PLANS_TABLE']=={'Ref':plan_id}
    assert permissions == {
        'dynamodb:GetItem': ['arn:aws:dynamodb:ap-northeast-2:111111111111:table/users',
                             {'Fn::GetAtt':[plan_id,'Arn']}],
        'dynamodb:PutItem': [{'Fn::GetAtt':[plan_id,'Arn']}],
        'dynamodb:UpdateItem': [{'Fn::GetAtt':[plan_id,'Arn']}],
        'logs:CreateLogStream': [{'Fn::GetAtt': [log_id, 'Arn']}],
        'logs:PutLogEvents': [{'Fn::GetAtt': [log_id, 'Arn']}],
        'lambda:InvokeFunction': [{'Fn::GetAtt': [fn_id, 'Arn']}],
    }
    # Execution role must own only database/log policy; invocation permission
    # belongs to the separate web identity role.
    execution_id = fn['Role']['Fn::GetAtt'][0]
    for resource in resources.values():
        if resource['Type'] == 'AWS::IAM::Policy':
            props = resource['Properties']
            contains_invoke = any(s['Action'] == 'lambda:InvokeFunction' for s in props['PolicyDocument']['Statement'])
            assert (props['Roles'] == [{'Ref': execution_id}]) is not contains_invoke


def test_only_production_subject_can_assume_invocation_role(synth):
    resources = json.loads(synth().stdout)['Resources']
    statements = [s for r in resources.values() if r['Type'] == 'AWS::IAM::Role'
                  for s in r['Properties']['AssumeRolePolicyDocument']['Statement']]
    trust = next(s for s in statements if s['Action'] == 'sts:AssumeRoleWithWebIdentity')
    assert trust['Principal'] == {'Federated': 'arn:aws:iam::111111111111:oidc-provider/oidc.vercel.com/team'}
    assert trust['Condition'] == {'StringEquals': {
        'oidc.vercel.com/team:aud': 'https://vercel.com/team',
        'oidc.vercel.com/team:sub': 'owner:team:project:project:environment:production',
    }}


@pytest.mark.parametrize('override', [
    {'usersTableArn': '*'}, {'usersTableArn': 'arn:aws:dynamodb:us-east-1:111111111111:table/users'},
    {'oidcProviderArn': 'arn:aws:iam::111111111111:oidc-provider/oidc.vercel.com/other'},
    {'repository': 'https://evil.example/repo'},
])
def test_broad_or_mismatched_configuration_is_refused(synth, override):
    assert synth(**override).returncode != 0


def test_plan_table_retains_claims_and_supports_exact_store_schema(synth):
    resources=json.loads(synth().stdout)['Resources']
    table=next(r for r in resources.values() if r['Type']=='AWS::DynamoDB::Table')
    props=table['Properties']
    assert props['KeySchema']==[{'AttributeName':'request_id','KeyType':'HASH'}]
    assert props['AttributeDefinitions']==[{'AttributeName':'request_id','AttributeType':'S'}]
    assert props['BillingMode']=='PAY_PER_REQUEST'
    assert props['TimeToLiveSpecification']=={'AttributeName':'ttl','Enabled':True}
    assert props['DeletionProtectionEnabled'] is True
    assert props['PointInTimeRecoverySpecification']=={'PointInTimeRecoveryEnabled':True}
    assert table['DeletionPolicy']==table['UpdateReplacePolicy']=='Retain'
    assert 'StreamSpecification' not in props
    assert not any(r['Type'] in ('AWS::Lambda::Url','AWS::Lambda::EventSourceMapping') for r in resources.values())
