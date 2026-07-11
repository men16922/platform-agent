from types import SimpleNamespace

from fastapi.testclient import TestClient
from pydantic_ai.models.test import TestModel

import src.agents.ai.local_deployer as ld
from src.agents.ai.local_deploy_api import app, get_deployer_factory


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
    return ld.create_local_deployer(provider=provider, model=TestModel())


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
