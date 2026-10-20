"""Offline grant boundary exercised through the real snapshot planner."""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
from pathlib import Path

import pytest

from src.agents.platform import registry_authorization as auth
from src.agents.platform.registry_planner import PlannerError, SnapshotFile

ROOT = Path(__file__).resolve().parents[1]
REQUEST = dict(tenant='acme', env='prod', capability='logging', version='7.1.0')
NOW = datetime(2026, 9, 5, tzinfo=timezone.utc)
VALID = dict(username='operator-demo', role='operator', registry_write_tenants=['acme'])


class Users:
    def __init__(self, record):
        self.record = deepcopy(record)
        self.calls = []

    def get_current_user(self, username):
        self.calls.append(username)
        return self.record


class RegistryFiles:
    def __init__(self):
        self.calls = []

    def resolve_revision(self):
        self.calls.append('resolve')
        return 'a' * 40

    def read_file(self, path, *, revision):
        self.calls.append(path)
        content = (ROOT / path).read_bytes()
        oid = hashlib.sha1(b'blob ' + str(len(content)).encode() + b'\0' + content).hexdigest()
        return SnapshotFile(revision, path, oid, content)


def run(users, reader, *, subject='operator-demo', payload=None):
    return auth.plan_authorized_snapshot(
        REQUEST if payload is None else payload, subject=subject,
        users=users, reader=reader, request_id='request-1', now=NOW,
    )


def denied(users, *, status=403, subject='operator-demo', payload=None):
    reader = RegistryFiles()
    with pytest.raises(PlannerError) as error:
        run(users, reader, subject=subject, payload=payload)
    assert error.value.status == status
    assert reader.calls == [], 'Unauthorized requests must not read the registry'
    return error.value


@pytest.mark.parametrize('role', ['operator', 'admin'])
def test_explicit_grant_runs_real_planner_and_preserves_user_record(role):
    users = Users({**VALID, 'role': role, 'tenants': []})
    before = deepcopy(users.record)
    reader = RegistryFiles()
    envelope = run(users, reader)
    assert users.calls == ['operator-demo']
    assert reader.calls == ['resolve', 'platform/catalog.yaml', 'platform/tenants/acme.yaml',
                            'infra/onprem/addons/values/loki.yaml']
    assert envelope.path == 'platform/tenants/acme.yaml'
    assert '+      logging: loki 7.1.0\n' in envelope.diff
    assert users.record == before


@pytest.mark.parametrize('record', [None, {}, [], 'admin', {**VALID, 'username': 'another-user'},
                                   {k: v for k, v in VALID.items() if k != 'username'}])
def test_missing_malformed_or_other_user_record_refused(record):
    users = Users(record)
    assert denied(users).code == 'registry_write_forbidden'
    assert users.calls == ['operator-demo']


@pytest.mark.parametrize('role', ['viewer', 'owner', 'ADMIN', '', None, ['admin'], True])
def test_only_current_operator_and_admin_roles_qualify(role):
    denied(Users({**VALID, 'role': role}))


@pytest.mark.parametrize('role', ['operator', 'admin'])
@pytest.mark.parametrize('grants', [None, [], ['globex'], '*', ['*'], 'acme', {'acme': True},
                                   ['acme-other'], ['ACME'], ['acme', None]])
def test_admin_and_operator_both_need_exact_well_typed_write_grant(role, grants):
    denied(Users({**VALID, 'role': role, 'registry_write_tenants': grants}))


@pytest.mark.parametrize('role', ['viewer', 'operator', 'admin'])
def test_read_grants_are_never_promoted(role):
    denied(Users(dict(username='operator-demo', role=role, tenants=['acme', 'globex'])))


@pytest.mark.parametrize('subject', [None, '', ' operator-demo', 'operator-demo\n', 'a' * 257, 123])
def test_missing_or_invalid_session_subject_stops_before_lookup(subject):
    users = Users(VALID)
    assert denied(users, status=401, subject=subject).code == 'session_required'
    assert not users.calls


@pytest.mark.parametrize('key', ['subject', 'username', 'role', 'registry_write_tenants', 'path'])
def test_browser_cannot_supply_identity_or_grants(key):
    users = Users(VALID)
    denied(users, status=422, payload={**REQUEST, key: 'admin'})
    assert users.calls == []


def test_store_failure_is_sanitized_and_demo_admin_does_not_fall_back():
    class Unavailable:
        def get_current_user(self, username):
            assert username == 'men16922'  # Existing demo admin must not rescue a failed read.
            raise OSError('credential-secret /private/path')
    error = denied(Unavailable(), status=503, subject='men16922')
    assert str(error) == 'user_store_unavailable'


@pytest.mark.parametrize('change', ['delete', 'role', 'grant'])
def test_record_is_reread_and_revocations_take_effect_on_next_preview(change):
    users = Users(VALID)
    reader = RegistryFiles()
    run(users, reader)
    if change == 'delete':
        users.record = None
    elif change == 'role':
        users.record['role'] = 'viewer'
    else:
        users.record['registry_write_tenants'] = []
    denied(users)
    assert users.calls == ['operator-demo', 'operator-demo']


def test_canonical_username_is_used_for_lookup_and_digest():
    users = Users(VALID)
    assert run(users, RegistryFiles(), subject='Operator-Demo') == run(users, RegistryFiles())
    assert users.calls == ['operator-demo', 'operator-demo']


def test_lookup_cannot_change_the_request_after_authorization(monkeypatch):
    payload = dict(REQUEST)
    class MutatingLookup(Users):
        def get_current_user(self, username):
            payload['tenant'] = 'globex'
            return super().get_current_user(username)
    reader = RegistryFiles()
    envelope = run(MutatingLookup(VALID), reader, payload=payload)
    assert envelope.path == 'platform/tenants/acme.yaml'
    assert 'platform/tenants/globex.yaml' not in reader.calls


def test_authorized_request_keeps_planner_conflicts():
    with pytest.raises(PlannerError) as error:
        run(Users(VALID), RegistryFiles(), payload={**REQUEST, 'env': 'dev'})
    assert (error.value.status, error.value.code) == (409, 'already_attached')


def test_failure_on_next_lookup_never_reuses_previous_grant():
    class FailsAfterOne(Users):
        def get_current_user(self, username):
            if self.calls:
                raise TimeoutError('user store unavailable')
            return super().get_current_user(username)
    users = FailsAfterOne(VALID)
    run(users, RegistryFiles())
    denied(users, status=503)
