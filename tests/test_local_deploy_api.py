from types import SimpleNamespace

from fastapi.testclient import TestClient
from pydantic_ai.models.test import TestModel

import src.agents.ai.local_deployer as ld
from src.agents.ai.local_deploy_api import app, get_deployer_factory, get_front_door
from src.agents.ai.supervisor import AgentRole, RouteDecision


class _FakeFrontDoor:
    """A stand-in supervisor/orchestrator for the front-door DI seam."""

    def __init__(self, *, delegated, role="deploy"):
        self._delegated = delegated
        self._role = role

    def handle(self, instruction, **kwargs):
        return SimpleNamespace(
            decision=RouteDecision(AgentRole(self._role), "test"),
            delegated=self._delegated,
            trace=[{"kind": "route", "role": self._role}],
            response={"ok": True},
        )


def _fake_adapters(provider):
    return SimpleNamespace(
        build=SimpleNamespace(
            build=lambda spec, context_path=".": SimpleNamespace(
                success=True, image_tag="reg/img:1", build_id="b1", error=None
            )
        ),
        registry=SimpleNamespace(
            push=lambda image, version: SimpleNamespace(
                success=True, image_uri="reg/img:1", digest="sha256:abc", error=None
            )
        ),
        cluster=SimpleNamespace(
            deploy=lambda spec, image_uri: SimpleNamespace(
                status=SimpleNamespace(value="DEPLOYED"),
                deployment_id="d1",
                namespace="default",
                replicas_desired=1,
                endpoint="http://svc",
                error=None,
            ),
            validate=lambda spec: SimpleNamespace(
                healthy=True, checks_passed=1, checks_total=1, details={}, error=None
            ),
            rollback=lambda spec: SimpleNamespace(success=True, rolled_back_to="v0", error=None),
        ),
    )


def _test_factory(provider="onprem"):
    return ld.create_local_deployer(provider=provider, model=TestModel(call_tools=["build_image", "push_image", "deploy_to_cluster", "validate_deployment"]))


def test_health():
    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_local_deploy_endpoint_drives_tools(monkeypatch):
    monkeypatch.setattr(ld, "get_deployment_adapters", _fake_adapters)
    app.dependency_overrides[get_deployer_factory] = lambda: _test_factory
    try:
        client = TestClient(app)
        resp = client.post(
            "/api/local-deploy",
            json={"instruction": "Deploy orders-api v1.4.2 to the local cluster with 2 replicas"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["provider"] == "onprem"
        assert data["model"] == "local-qwen"
        assert data["suitability"]["verdict"] == "recommended"
        assert isinstance(data["summary"], str)
        tools = {step["tool"] for step in data["steps"]}
        assert "build_image" in tools
        assert "deploy_to_cluster" in tools
        # Step trace pairs each call with its adapter result.
        build_step = next(s for s in data["steps"] if s["tool"] == "build_image")
        assert build_step["result"]["image_tag"] == "reg/img:1"
    finally:
        app.dependency_overrides.clear()


def test_local_deploy_delegates_to_a2a_specialist():
    factory_called = {"v": False}

    def _tracking_factory(provider="onprem"):
        factory_called["v"] = True
        return _test_factory(provider)

    app.dependency_overrides[get_front_door] = lambda: _FakeFrontDoor(delegated=True, role="deploy")
    app.dependency_overrides[get_deployer_factory] = lambda: _tracking_factory
    try:
        client = TestClient(app)
        resp = client.post("/api/local-deploy", json={"instruction": "Deploy orders-api"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["delegated"] is True
        assert data["route"] == "deploy"
        assert data["steps"] == []
        # Delegation short-circuits the in-process deployer.
        assert factory_called["v"] is False
    finally:
        app.dependency_overrides.clear()


def test_local_deploy_falls_through_when_not_delegated(monkeypatch):
    monkeypatch.setattr(ld, "get_deployment_adapters", _fake_adapters)
    app.dependency_overrides[get_front_door] = lambda: _FakeFrontDoor(delegated=False, role="deploy")
    app.dependency_overrides[get_deployer_factory] = lambda: _test_factory
    try:
        client = TestClient(app)
        resp = client.post(
            "/api/local-deploy",
            json={"instruction": "Deploy orders-api v1.4.2 to the local cluster"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["delegated"] is False
        assert data["route"] == "deploy"  # classification still surfaced on the fallthrough
        assert data["ok"] is True
        assert {s["tool"] for s in data["steps"]}  # the in-process deployer actually ran
    finally:
        app.dependency_overrides.clear()


def _parse_sse(body: str):
    """Parse SSE frames into (id, data-dict) pairs; skip comment/keepalive lines."""
    import json as _json

    frames = []
    for block in body.split("\n\n"):
        lines = [ln for ln in block.splitlines() if ln and not ln.startswith(":")]
        data_line = next((ln for ln in lines if ln.startswith("data: ")), None)
        if not data_line:
            continue
        id_line = next((ln for ln in lines if ln.startswith("id: ")), None)
        frames.append((int(id_line[4:]) if id_line else None, _json.loads(data_line[6:])))
    return frames


def test_stream_emits_ready_sentinel_and_sequenced_event_ids(monkeypatch):
    monkeypatch.setattr(ld, "get_deployment_adapters", _fake_adapters)
    app.dependency_overrides[get_deployer_factory] = lambda: _test_factory
    try:
        client = TestClient(app)
        resp = client.post(
            "/api/local-deploy/stream",
            json={"instruction": "Deploy orders-api v1.4.2 to the local cluster"},
        )
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")

        frames = _parse_sse(resp.text)
        # A-2: the first frame is a READY sentinel...
        assert frames[0][1]["type"] == "ready"
        # A-3: it reserves an `agent` attribution field (the model id here).
        assert "agent" in frames[0][1]
        # A-1: every frame carries a sequential id (1..N) for dedup on reconnect.
        ids = [fid for fid, _ in frames]
        assert ids == list(range(1, len(frames) + 1))
        # ...and the stream terminates with a 'done' event carrying the same field.
        assert frames[-1][1]["type"] == "done"
        assert "agent" in frames[-1][1]
    finally:
        app.dependency_overrides.clear()


def test_models_endpoint_lists_options_for_environment():
    client = TestClient(app)
    resp = client.get("/api/models", params={"provider": "onprem"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["provider"] == "onprem"
    ids = {m["id"] for m in data["models"]}
    assert ids == {"local-qwen", "bedrock-claude", "vertex-gemini", "azure-gpt"}
    assert data["models"][0]["id"] == "local-qwen"  # recommended-first


def test_models_endpoint_rejects_unknown_environment():
    client = TestClient(app)
    resp = client.get("/api/models", params={"provider": "mars"})
    assert resp.status_code == 400


def test_local_deploy_requires_instruction():
    client = TestClient(app)
    resp = client.post("/api/local-deploy", json={"instruction": ""})
    assert resp.status_code == 422  # pydantic min_length validation
