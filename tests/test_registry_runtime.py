"""Lambda contract and Git object fixtures; AWS integration runs on DynamoDB Local."""
import ast
import base64
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import inspect
from pathlib import Path

import pytest

from src.agents.platform.registry_lambda import handle_event
from src.agents.platform.registry_readers import GitHubSnapshotReader

ROOT = Path(__file__).resolve().parents[1]
REQUEST = dict(tenant='acme', env='prod', capability='logging', version='7.1.0')
REV = 'a' * 40
NOW = datetime(2026, 9, 5, tzinfo=timezone.utc)
BASE = 'https://api.github.com/repos/fixture/registry'


def git_objects():
    """Actual YAML bytes, a commit, and non-recursive trees with Git object IDs."""
    files = ['platform/catalog.yaml', 'platform/tenants/acme.yaml',
             'infra/onprem/addons/values/loki.yaml']
    objects = {}; hierarchy = {}
    for path in files:
        content = (ROOT / path).read_bytes()
        sha = hashlib.sha1(b'blob ' + str(len(content)).encode() + b'\0' + content).hexdigest()
        objects['/git/blobs/' + sha] = dict(sha=sha, size=len(content), encoding='base64',
                                          content=base64.b64encode(content).decode())
        node = hierarchy
        for part in path.split('/')[:-1]:
            node = node.setdefault(part, {})
        node[path.split('/')[-1]] = dict(type='blob', mode='100644', sha=sha, size=len(content))
    def tree(node):
        entries = []
        for name, child in sorted(node.items()):
            entry = child if 'type' in child else dict(type='tree', mode='040000', sha=tree(child))
            entries.append(dict(path=name, **entry))
        raw = b''.join((entry['mode'].lstrip('0') + ' ' + entry['path']).encode() + b'\0' +
                       bytes.fromhex(entry['sha']) for entry in entries)
        sha = hashlib.sha1(b'tree ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()
        objects['/git/trees/' + sha] = dict(sha=sha, tree=entries, truncated=False)
        return sha
    root = tree(hierarchy)
    objects['/git/commits/' + REV] = dict(sha=REV, tree={'sha': root})
    objects['/git/ref/heads/main'] = dict(ref='refs/heads/main', object={'type': 'commit', 'sha': REV})
    return objects


def reader_for(objects, calls):
    def get(url):
        assert url.startswith(BASE)
        calls.append(url)
        return deepcopy(objects[url[len(BASE):]])
    return GitHubSnapshotReader('fixture/registry', 'main', json_get=get)


class User:
    def __init__(self, role='operator'):
        self.role = role
    def get_current_user(self, username):
        return dict(username=username, role=self.role, registry_write_tenants=['acme'])


class RecordedPlans:
    """Domain persistence sink for pure planner tests; no AWS API is simulated."""
    def __init__(self): self.records = []
    def put(self, record): self.records.append(record)


def invoke(event=None, users=None, objects=None):
    calls = []
    result = handle_event(
        {'subject': 'operator', 'request': REQUEST} if event is None else event,
        dependencies_factory=lambda: (users or User(), reader_for(objects or git_objects(), calls), RecordedPlans()),
        request_id='local-request', clock=lambda:NOW,
    )
    return result, calls


def test_lambda_real_planner_uses_immutable_objects_and_canonical_response():
    result, calls = invoke()
    assert result['ok'] is True and result['status'] == 200
    assert result['plan']['base_commit'] == REV
    assert result['plan']['path'] == 'platform/tenants/acme.yaml'
    assert '+      logging: loki 7.1.0' in result['plan']['diff']
    assert sum('/git/ref/' in url for url in calls) == 1
    assert len(calls) == len(set(calls))
    assert all('?recursive' not in url for url in calls)


@pytest.mark.parametrize('event,status', [({}, 422), ([], 422),
    ({'subject': None, 'request': REQUEST}, 401),
    ({'subject': 'operator', 'request': {**REQUEST, 'path': 'other'}}, 422),
    ({'subject': 'operator', 'request': REQUEST, 'repository': 'other/repo'}, 422),
])
def test_bad_invoke_inputs_stop_before_clients(event, status):
    def forbidden():
        pytest.fail('should not initialize clients')
    result = handle_event(event, dependencies_factory=forbidden, request_id='id', clock=lambda:NOW)
    assert result['ok'] is False and result['status'] == status


def test_denied_user_never_reads_github():
    result, calls = invoke(users=User('viewer'))
    assert result == dict(ok=False, status=403, error='registry_write_forbidden')
    assert calls == []


def test_business_conflict_survives_lambda_transport():
    result, _ = invoke({'subject': 'operator', 'request': {**REQUEST, 'env': 'dev'}})
    assert result == dict(ok=False, status=409, error='already_attached')


def test_dependency_errors_are_sanitized():
    def broken():
        raise RuntimeError('private-key secret /host/path')
    result = handle_event({'subject': 'operator', 'request': REQUEST},
                          dependencies_factory=broken, request_id='id', clock=lambda:NOW)
    assert result == dict(ok=False, status=503, error='planner_unavailable')


@pytest.mark.parametrize('mutation', ['symlink', 'submodule', 'directory_symlink', 'truncated',
    'commit', 'tree', 'blob_sha', 'blob_content', 'oversize', 'duplicate', 'missing'])
def test_git_membership_and_file_types_fail_closed(mutation):
    objects = git_objects()
    trees = [item for key, item in objects.items() if '/git/trees/' in key]
    target = next(tree for tree in trees if any(e['path'] == 'acme.yaml' for e in tree['tree']))
    entry = next(e for e in target['tree'] if e['path'] == 'acme.yaml')
    blob = objects['/git/blobs/' + entry['sha']]
    if mutation in ('symlink', 'submodule'):
        entry.update(mode='120000' if mutation == 'symlink' else '160000')
    elif mutation == 'directory_symlink':
        parent = next(e for tree in trees for e in tree['tree'] if e['path'] == 'platform')
        parent.update(mode='120000', type='blob')
    elif mutation == 'truncated': target['truncated'] = True
    elif mutation == 'commit': objects['/git/commits/' + REV]['sha'] = 'b' * 40
    elif mutation == 'tree': target['sha'] = 'b' * 40
    elif mutation == 'blob_sha': blob['sha'] = 'b' * 40
    elif mutation == 'blob_content':
        data = bytearray(base64.b64decode(blob['content'])); data[1] ^= 1
        blob['content'] = base64.b64encode(data).decode()
    elif mutation == 'oversize': entry['size'] = 262145
    elif mutation == 'duplicate': target['tree'].append(deepcopy(entry))
    else: target['tree'].remove(entry)
    result, _ = invoke(objects=objects)
    assert result['ok'] is False and result['status'] == 503


@pytest.mark.parametrize('path', ['../secret', 'platform/tenants/../globex.yaml', '/etc/passwd',
                                  'https://evil.example/file'])
def test_reader_refuses_paths_before_transport(path):
    calls = []
    with pytest.raises(ValueError):
        reader_for(git_objects(), calls).read_file(path, revision=REV)
    assert not calls


def test_actual_dynamodb_reader_requests_strong_consistency_without_fallback():
    # Inspect the real SDK call; do not replace/mock an AWS service. Runtime
    # behavior is separately exercised against DynamoDB Local in the evidence.
    tree = ast.parse(inspect.getsource(__import__('src.agents.platform.registry_readers', fromlist=['x'])))
    method = next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)
                  and node.name == 'get_current_user')
    call = next(node for node in ast.walk(method) if isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute) and node.func.attr == 'get_item')
    assert any(k.arg == 'ConsistentRead' and isinstance(k.value, ast.Constant) and k.value.value is True
               for k in call.keywords)
    assert not any(isinstance(node, ast.Try) for node in ast.walk(method))


def test_actual_handler_uses_lambda_context_request_id(monkeypatch):
    from types import SimpleNamespace
    from src.agents.platform import registry_lambda
    monkeypatch.setattr(registry_lambda, 'production_dependencies',
                        lambda: (User(), reader_for(git_objects(), []), RecordedPlans()))
    result = registry_lambda.handler({'subject': 'operator', 'request': REQUEST},
                                     SimpleNamespace(aws_request_id='invoke-context-id'))
    assert result['ok'] is True
    assert result['plan']['request_id'] == 'invoke-context-id'


@pytest.mark.parametrize('mode', ['ok', 'redirect', 'oversize', 'rate_limit'])
def test_real_http_transport_bounds_and_redirect_policy(mode):
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from threading import Thread
    from src.agents.platform.registry_readers import _github_json
    requests = []
    class HTTP(BaseHTTPRequestHandler):
        def do_GET(self):
            requests.append(self.path)
            if mode == 'redirect':
                self.send_response(302); self.send_header('Location', '/elsewhere'); self.end_headers()
            elif mode == 'rate_limit':
                self.send_response(429); self.end_headers()
            else:
                self.send_response(200); self.end_headers()
                self.wfile.write(b' ' * (1024 * 1024 + 1) if mode == 'oversize' else b'{"ok":true}')
        def log_message(self, *args): pass
    server = ThreadingHTTPServer(('127.0.0.1', 0), HTTP)
    thread = Thread(target=server.serve_forever, daemon=True); thread.start()
    try:
        url = f'http://127.0.0.1:{server.server_port}/read'
        if mode == 'ok': assert _github_json(url) == {'ok': True}
        else:
            with pytest.raises(Exception): _github_json(url)
        assert requests == ['/read']
    finally:
        server.shutdown(); server.server_close(); thread.join()


@pytest.mark.parametrize('script,args', [
    ('build_registry_planner.py', ['--output', '.']),
    ('verify_registry_planner_local.py', ['--asset', '.', '--endpoint', 'https://example.com']),
])
def test_operator_scripts_report_failures_on_stdout(script, args):
    import subprocess
    import sys
    result = subprocess.run([sys.executable, str(ROOT / 'scripts' / script), *args], cwd=ROOT,
                            capture_output=True, text=True)
    assert result.returncode == 1
    assert 'FAILED:' in result.stdout
    assert result.stderr == ''


@pytest.mark.parametrize('operation', [None, '', 'publish', 'SUCCEEDED', 1, [], {}])
def test_lambda_refuses_invalid_trusted_operation_before_dependencies(operation):
    def forbidden(): pytest.fail('invalid operation initialized dependencies')
    result = handle_event(dict(subject='operator', request=REQUEST, operation=operation),
        dependencies_factory=forbidden, request_id='id', clock=lambda:NOW)
    assert result == dict(ok=False, status=422, error='invalid_invoke_request')


@pytest.mark.parametrize('operation', ['prepare','status'])
@pytest.mark.parametrize('payload', [REQUEST, {'request_id':'saved','subject':'admin'}, {'request_id':'../id'}])
def test_lambda_saved_operations_reject_client_authority_and_bad_ids(operation,payload):
    def forbidden(): pytest.fail('bad saved request initialized dependencies')
    result=handle_event(dict(subject='operator',request=payload,operation=operation),
        dependencies_factory=forbidden,request_id='id',clock=lambda:NOW)
    assert result == dict(ok=False,status=422,error='invalid_request')


def test_lambda_preview_acknowledges_only_persisted_exact_artifact():
    plans=RecordedPlans()
    event=dict(subject='operator',request=REQUEST,operation='preview')
    result=handle_event(event,dependencies_factory=lambda:(User(),reader_for(git_objects(),[]),plans),
        request_id='stored-by-lambda',clock=lambda:NOW)
    assert result['ok'] is True and len(plans.records)==1
    stored=plans.records[0].data()
    assert stored['plan']==result['plan']
    assert stored['subject']=='operator' and stored['request']==REQUEST
    assert hashlib.sha256(stored['output'].encode()).hexdigest()==result['plan']['output_sha256']


def test_lambda_does_not_acknowledge_preview_on_persistence_failure():
    from src.agents.platform.registry_planner import PlannerError
    class Unavailable:
        def put(self, record): raise PlannerError('plan_store_unavailable',503)
    result=handle_event(dict(subject='operator',request=REQUEST),
        dependencies_factory=lambda:(User(),reader_for(git_objects(),[]),Unavailable()),
        request_id='not-stored',clock=lambda:NOW)
    assert result==dict(ok=False,status=503,error='plan_store_unavailable')


def test_production_sdk_configuration_ignores_endpoint_overrides_and_never_retries_writes(monkeypatch):
    from src.agents.platform.registry_lambda import production_dependencies
    for key,value in {'AWS_ACCESS_KEY_ID':'local-constructor-only','AWS_SECRET_ACCESS_KEY':'local',
        'AWS_DEFAULT_REGION':'ap-northeast-2','AWS_EC2_METADATA_DISABLED':'true',
        'AWS_ENDPOINT_URL':'http://127.0.0.1:1','AWS_ENDPOINT_URL_DYNAMODB':'http://127.0.0.1:2',
        'REGISTRY_USERS_TABLE':'users','REGISTRY_PLANS_TABLE':'plans',
        'REGISTRY_REPOSITORY':'fixture/registry','REGISTRY_BRANCH':'main'}.items():
        monkeypatch.setenv(key,value)
    monkeypatch.delenv('AWS_PROFILE',raising=False)
    users,reader,store=production_dependencies() # Constructs real SDK only; no API calls.
    client=store.table.meta.client
    assert client.meta.endpoint_url=='https://dynamodb.ap-northeast-2.amazonaws.com'
    assert client.meta.config.retries['total_max_attempts']==1
    assert store.table.name=='plans' and users.table.name=='users'
    client.close()


@pytest.mark.parametrize('users_name,plans_name',[('users','users'),('users',''),('','plans')])
def test_production_rejects_shared_or_empty_plan_table(monkeypatch,users_name,plans_name):
    from src.agents.platform.registry_lambda import production_dependencies
    monkeypatch.setenv('REGISTRY_USERS_TABLE',users_name)
    monkeypatch.setenv('REGISTRY_PLANS_TABLE',plans_name)
    with pytest.raises(ValueError,match='separate_plan_table_required'):
        production_dependencies()
