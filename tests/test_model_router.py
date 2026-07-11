import asyncio
from types import SimpleNamespace

import pytest
from pydantic_ai.models.test import TestModel

import src.agents.ai.local_deployer as ld
from src.agents.ai import model_router as mr


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


# --- Suitability matrix ---------------------------------------------------


def test_native_pairings_are_recommended():
    assert mr.suitability("bedrock-claude", "aws")["verdict"] == "recommended"
    assert mr.suitability("vertex-gemini", "gcp")["verdict"] == "recommended"
    assert mr.suitability("azure-gpt", "azure")["verdict"] == "recommended"
    assert mr.suitability("local-qwen", "onprem")["verdict"] == "recommended"


def test_onprem_offers_every_model_local_recommended_first():
    rows = mr.models_for_environment("onprem")
    ids = [r["id"] for r in rows]
    assert set(ids) == {"local-qwen", "bedrock-claude", "vertex-gemini", "azure-gpt"}
    # recommended-first ordering
    assert rows[0]["id"] == "local-qwen"
    assert rows[0]["verdict"] == "recommended"
    # cloud brains are offered but only "allowed" on-prem
    assert all(r["verdict"] == "allowed" for r in rows if r["id"] != "local-qwen")


def test_cloud_native_selector_recommends_home_model():
    rows = mr.models_for_environment("aws")
    assert rows[0]["id"] == "bedrock-claude"
    assert rows[0]["verdict"] == "recommended"


def test_unknown_model_or_env_raises():
    with pytest.raises(ValueError):
        mr.suitability("no-such-model", "aws")
    with pytest.raises(ValueError):
        mr.suitability("local-qwen", "no-such-env")


# --- Routing / execution --------------------------------------------------


def test_route_deploy_local_qwen_executes(monkeypatch):
    monkeypatch.setattr(ld, "get_deployment_adapters", _fake_adapters)

    def factory(provider="onprem"):
        return ld.create_local_deployer(provider=provider, model=TestModel())

    outcome = asyncio.run(
        mr.route_deploy("Deploy orders-api v1 to the local cluster", "local-qwen", "onprem", agent_factory=factory)
    )
    assert outcome.ok is True
    assert outcome.model == "local-qwen"
    assert outcome.provider == "onprem"
    assert outcome.suitability["verdict"] == "recommended"
    tools = {step["tool"] for step in outcome.steps}
    assert "build_image" in tools and "deploy_to_cluster" in tools


def test_route_deploy_cloud_model_validates_without_creds():
    outcome = asyncio.run(mr.route_deploy("Deploy orders-api v1 to AWS", "bedrock-claude", "aws"))
    assert outcome.ok is False
    assert outcome.model == "bedrock-claude"
    assert outcome.suitability["verdict"] == "recommended"
    assert "credentials" in outcome.summary.lower()
    assert outcome.steps == []


def test_route_deploy_rejects_unknown_model():
    with pytest.raises(ValueError):
        asyncio.run(mr.route_deploy("x", "no-such-model", "aws"))
