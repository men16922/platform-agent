"""Transport boundary rejection before dependency construction; no AWS doubles."""
from datetime import datetime, timezone

import pytest

from src.agents.platform.registry_preview_service import handle_stored_event
from src.agents.platform.registry_local import local_plan_store
from src.agents.platform.registry_planner import plan_snapshot, plan_snapshot_artifact
from tests.test_registry_plan_store import Files, REQUEST, NOW


def test_internal_artifact_preserves_public_envelope_and_exact_output():
    options = dict(subject='operator', reader=Files(), request_id='artifact', now=NOW)
    artifact = plan_snapshot_artifact(REQUEST, **options)
    assert artifact.envelope == plan_snapshot(REQUEST, **options)
    assert artifact.output.endswith('      logging: loki 7.1.0\n')
    assert 'output' not in artifact.envelope.to_dict()


@pytest.mark.parametrize('operation,event,status', [
    ('preview', {}, 422), ('delete', {'subject':'operator','request':REQUEST}, 422),
    ('preview', {'subject':'operator','request':{**REQUEST,'output':'forged'}}, 422),
    ('prepare', {'subject':'operator','request':{'request_id':'id','subject':'admin'}}, 422),
    ('prepare', {'subject':'operator','request':{'request_id':'id','output':'forged'}}, 422),
    ('prepare', {'subject':'operator','request':{'request_id':'id','tenant':'globex'}}, 422),
    ('prepare', {'subject':'operator','request':{'request_id':'../id'}}, 422),
    ('prepare', {'subject':'operator','request':{'request_id':None}}, 422),
    ('prepare', {'subject':'operator','request':None}, 422),
    ('prepare', {'subject':'operator','request':{}}, 422),
    ('preview', {'subject':' operator','request':REQUEST}, 401),
    ('prepare', {'subject':None,'request':{'request_id':'id'}}, 401),
    ('status', {'subject':None,'request':{'request_id':'id'}}, 401),
    ('status', {'subject':'operator','request':{'request_id':'../id'}}, 422),
    ('status', {'subject':'operator','request':{'request_id':'id','subject':'admin'}}, 422),
    ('status', {'subject':'operator','request':{}}, 422),
])
def test_bad_input_rejected_before_dependencies(operation, event, status):
    called = []
    def dependencies():
        called.append(True)
        raise AssertionError('must not construct dependencies')
    result = handle_stored_event(event, operation=operation, dependencies_factory=dependencies,
                                request_id='server-id', clock=lambda:datetime.now(timezone.utc))
    assert result['ok'] is False and result['status'] == status
    assert not called


@pytest.mark.parametrize('endpoint', [
    'https://127.0.0.1:8000', 'http://dynamodb.ap-northeast-2.amazonaws.com',
    'http://192.168.1.1:8000', 'http://user:password@127.0.0.1:8000',
    'http://127.0.0.1:8000/path', 'http://127.0.0.1:8000?table=other',
    'http://127.0.0.1:8000#fragment', '',
])
def test_local_store_rejects_non_loopback_configuration_before_client(endpoint):
    with pytest.raises(ValueError):
        local_plan_store(endpoint, 'local-plans')
