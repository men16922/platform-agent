"""Real repository fixtures through a plain read adapter; no cloud services."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import hashlib
from pathlib import Path

import pytest

from src.agents.platform import registry_planner as planner
from src.agents.platform import registry_write

REPO = Path(__file__).resolve().parents[1]
REVISION = 'a' * 40
REQUEST = dict(tenant='acme', env='prod', capability='logging', version='7.1.0')
NOW = datetime(2026, 9, 5, tzinfo=timezone.utc)
CATALOG = 'platform/catalog.yaml'
TENANT = 'platform/tenants/acme.yaml'
VALUES = 'infra/onprem/addons/values/loki.yaml'


def blob_id(content):
    return hashlib.sha1(b'blob ' + str(len(content)).encode() + b'\0' + content).hexdigest()


class Files:
    def __init__(self):
        self.contents = {path: (REPO / path).read_bytes() for path in (CATALOG, TENANT, VALUES)}
        self.calls = []
        self.revision = REVISION
        self.transform = lambda item: item

    def resolve_revision(self):
        self.calls.append(('resolve',))
        return self.revision

    def read_file(self, path, *, revision):
        self.calls.append((path, revision))
        content = self.contents[path]
        return self.transform(planner.SnapshotFile(revision, path, blob_id(content), content))


def run(files, request=None, **context):
    return planner.plan_snapshot(
        REQUEST if request is None else request, reader=files,
        **dict(subject='operator', request_id='request-1', now=NOW, **context),
    )


def test_real_snapshot_is_pinned_deterministic_and_immutable(monkeypatch, tmp_path):
    files = Files()
    original = dict(files.contents)
    roots = []
    real = registry_write.plan_addon_attachment

    def inspect(*args, **kwargs):
        root = kwargs['values_repo_root']
        roots.append(root)
        assert sorted(str(p.relative_to(root)) for p in root.rglob('*') if p.is_file()) == sorted(original)
        assert not (root / '.git').exists()
        return real(*args, **kwargs)

    # A checkout fallback would now fail: only the pinned snapshot has values.
    monkeypatch.setattr('src.agents.platform.registry.DEFAULT_REGISTRY_ROOT', tmp_path / 'missing')
    monkeypatch.setattr(planner, 'plan_addon_attachment', inspect)
    monkeypatch.setattr('subprocess.Popen', lambda *a, **k: pytest.fail('subprocess forbidden'))
    monkeypatch.setattr('socket.socket.connect', lambda *a, **k: pytest.fail('network forbidden'))
    result = run(files)
    assert result == run(files)
    assert files.calls == [('resolve',), (CATALOG, REVISION), (TENANT, REVISION), (VALUES, REVISION)] * 2
    assert files.contents == original
    assert all((REPO / path).read_bytes() == content for path, content in original.items())
    assert all(not root.exists() for root in roots)
    assert roots[0] != roots[1]
    assert result.path == TENANT
    assert result.diff.startswith(f'--- a/{TENANT}\n+++ b/{TENANT}\n')
    assert [line for line in result.diff.splitlines() if line.startswith('+')][1:] == ['+      logging: loki 7.1.0']
    assert '/tmp/' not in str(result.to_dict()) and 'registry-preview-' not in str(result.to_dict())
    assert 'subject' not in result.to_dict()
    assert result.expires_at == '2026-09-05T00:05:00+00:00'
    assert result.output_sha256 == hashlib.sha256(original[TENANT] + b'      logging: loki 7.1.0\n').hexdigest()


@pytest.mark.parametrize('field,value', [
    ('tenant', '../globex'), ('tenant', 'acme\n'), ('tenant', 'a' * 64),
    ('env', 'prod\n'), ('capability', 'logging: hacked'),
    ('version', ''), ('version', '7.1.0\n  prod: {}'), ('version', ' 7.1.0'),
    ('version', 7), ('version', 'v' * 129),
])
def test_bad_fields_rejected_before_io(field, value):
    files = Files()
    with pytest.raises(planner.PlannerError, match='invalid_request'):
        run(files, {**REQUEST, field: value})
    assert files.calls == []


@pytest.mark.parametrize('extra', ['path', 'repository', 'subject', 'role', 'grants', 'backend', 'branch', 'url', 'yaml'])
def test_extra_user_control_is_rejected(extra):
    files = Files()
    with pytest.raises(planner.PlannerError, match='invalid_request'):
        run(files, {**REQUEST, extra: 'attacker'})
    assert not files.calls


@pytest.mark.parametrize('payload', [{}, {'tenant': 'acme'}, [], None])
def test_incomplete_or_non_mapping_request(payload):
    with pytest.raises(planner.PlannerError, match='invalid_request'):
        planner.plan_snapshot(payload, subject='operator', reader=Files(), request_id='id', now=NOW)


@pytest.mark.parametrize('content', [
    b'\xff', b'[invalid:', b'[]', b'', b'a: 1\na: 2\n', b'a: &x [1]\nb: *x',
    b'a: !!python/object:os.system {}', b'a: 2026-99-99', b'a: ' + b'[' * 65 + b']' * 65,
    b'a: [' + b'0,' * 10001 + b']', b'\n' * (planner.MAX_FILE_BYTES + 1),
])
@pytest.mark.parametrize('path', [CATALOG, TENANT, VALUES])
def test_invalid_snapshot_files_refused(path, content):
    files = Files()
    files.contents[path] = content
    with pytest.raises(planner.PlannerError) as error:
        run(files)
    assert error.value.status == 422


@pytest.mark.parametrize('field,value,code,status', [
    ('path', 'platform/tenants/globex.yaml', 'snapshot_path_mismatch', 422),
    ('commit', 'b' * 40, 'snapshot_revision_mismatch', 409),
    ('blob', '0' * 40, 'snapshot_blob_mismatch', 422),
    ('content', b'tampered', 'snapshot_blob_mismatch', 422),
])
@pytest.mark.parametrize('path', [CATALOG, TENANT, VALUES])
def test_snapshot_metadata_and_content_tampering(path, field, value, code, status):
    files = Files()
    files.transform = lambda item: replace(item, **{field: value}) if item.path == path else item
    with pytest.raises(planner.PlannerError, match=code) as error:
        run(files)
    assert error.value.status == status


@pytest.mark.parametrize('value', ['main', 'A' * 40, 'a' * 40 + '\n', None])
def test_revision_must_be_immutable_sha(value):
    files = Files()
    files.revision = value
    with pytest.raises(planner.PlannerError, match='invalid_revision'):
        run(files)
    assert files.calls == [('resolve',)]


@pytest.mark.parametrize('field,value,status', [('env', 'missing', 422), ('capability', 'missing', 422), ('env', 'dev', 409)])
def test_unknown_target_and_existing_addon(field, value, status):
    with pytest.raises(planner.PlannerError) as error:
        run(Files(), {**REQUEST, field: value})
    assert error.value.status == status


@pytest.mark.parametrize('value', ['../../etc/passwd', '/etc/passwd', 'infra/onprem/addons/values/../secret.yaml'])
def test_catalog_cannot_escape_values_directory(value):
    files = Files()
    files.contents[CATALOG] = files.contents[CATALOG].replace(VALUES.encode(), value.encode())
    with pytest.raises(planner.PlannerError, match='invalid_values_path'):
        run(files)
    assert len(files.calls) == 3


@pytest.mark.parametrize('method', ['resolve_revision', 'read_file'])
def test_read_failures_are_sanitized(method):
    files = Files()
    def fail(*args, **kwargs):
        raise OSError('/private/token=secret')
    setattr(files, method, fail)
    with pytest.raises(planner.PlannerError, match='snapshot_unavailable') as error:
        run(files)
    assert error.value.status == 503 and 'secret' not in str(error.value)


@pytest.mark.parametrize('mutation', ['path', 'sibling_env', 'comment', 'original', 'version', 'write_input', 'write_catalog', 'write_values', 'write_sibling'])
def test_regressed_planner_cannot_change_scope(monkeypatch, mutation):
    real = registry_write.plan_addon_attachment
    def corrupt(*args, **kwargs):
        result = real(*args, **kwargs)
        if mutation == 'path':
            return replace(result, path=result.path.with_name('globex.yaml'))
        if mutation == 'sibling_env':
            return replace(result, updated=result.updated.replace('logging: loki 7.1.0', 'logging: loki 9.0.0', 1))
        if mutation == 'comment':
            return replace(result, updated=result.updated.replace('# Tenant registry', '# Different comment'))
        if mutation == 'original':
            return replace(result, original='forged')
        if mutation == 'version':
            return replace(result, version='9.0.0')
        if mutation in ('write_catalog', 'write_values', 'write_sibling'):
            paths = {'write_catalog': CATALOG, 'write_values': VALUES, 'write_sibling': 'platform/tenants/globex.yaml'}
            (kwargs['values_repo_root'] / paths[mutation]).write_text('tampered')
            return result
        result.path.write_text(result.updated)
        return result
    monkeypatch.setattr(planner, 'plan_addon_attachment', corrupt)
    with pytest.raises(planner.PlannerError, match='invalid_planner_output'):
        run(Files())


@pytest.mark.parametrize('change', ['subject', 'request_id', 'time', 'revision', 'catalog', 'tenant', 'values', 'version'])
def test_digest_binds_identity_request_and_all_snapshot_inputs(change):
    files = Files()
    baseline = run(files)
    request = dict(REQUEST)
    context = dict(subject='operator', request_id='request-1', now=NOW)
    if change in ('subject', 'request_id'):
        context[change] += '-other'
    elif change == 'time':
        context['now'] += timedelta(seconds=1)
    elif change == 'revision':
        files.revision = 'b' * 40
    elif change in ('catalog', 'tenant', 'values'):
        files.contents[{'catalog': CATALOG, 'tenant': TENANT, 'values': VALUES}[change]] += b'# comment\n'
    else:
        request['version'] = '7.1.1'
    changed = planner.plan_snapshot(request, reader=files, **context)
    assert changed.digest != baseline.digest


def test_missing_snapshot_values_never_falls_back_to_checkout():
    files = Files()
    del files.contents[VALUES]
    with pytest.raises(planner.PlannerError, match='snapshot_unavailable'):
        run(files)


@pytest.mark.parametrize('field,value', [
    ('subject', ''), ('subject', None), ('request_id', '../id'),
    ('now', NOW.replace(tzinfo=None)), ('now', '2026-09-05'),
])
def test_trusted_context_is_required(field, value):
    context = dict(subject='operator', request_id='id', now=NOW)
    context[field] = value
    files = Files()
    with pytest.raises(planner.PlannerError, match='invalid_server_context'):
        planner.plan_snapshot(REQUEST, reader=files, **context)
    assert not files.calls


def test_single_line_insertion_in_wrong_environment_is_rejected(monkeypatch):
    files = Files()
    line = b'      logging: loki 7.1.0\n'
    files.contents[TENANT] = files.contents[TENANT].replace(line, b'')
    real = registry_write.plan_addon_attachment
    def wrong_environment(*args, **kwargs):
        result = real(*args, **kwargs)
        lines = result.original.splitlines(keepends=True)
        at = next(i for i, text in enumerate(lines) if 'observability:' in text) + 1
        lines.insert(at, line.decode())
        return replace(result, updated=''.join(lines))
    monkeypatch.setattr(planner, 'plan_addon_attachment', wrong_environment)
    with pytest.raises(planner.PlannerError):
        run(files)
