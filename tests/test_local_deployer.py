from pathlib import Path
from types import SimpleNamespace

from pydantic_ai.messages import ToolCallPart
from pydantic_ai.models.test import TestModel

import src.agents.ai.local_deployer as ld


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
                healthy=True, checks_passed=1, checks_total=1, details={"ready": "1/1"}, error=None
            ),
            rollback=lambda spec: SimpleNamespace(success=True, rolled_back_to="v0", error=None),
        ),
    )


def test_module_does_not_import_strands():
    src = Path(ld.__file__).read_text()
    assert "import strands" not in src
    assert "from strands" not in src


def test_build_image_tool_calls_adapter(monkeypatch):
    monkeypatch.setattr(ld, "get_deployment_adapters", _fake_adapters)
    out = ld.build_image("orders-api", "orders-api", "1.0.0")
    assert out == {"success": True, "image_tag": "reg/img:1", "build_id": "b1", "error": None}


def test_deploy_tool_serializes_status_enum(monkeypatch):
    monkeypatch.setattr(ld, "get_deployment_adapters", _fake_adapters)
    out = ld.deploy_to_cluster("orders-api", "orders-api", "1.0.0", "reg/img:1")
    assert out["status"] == "DEPLOYED"
    assert out["deployment_id"] == "d1"
    assert out["endpoint"] == "http://svc"


def test_all_five_tools_registered():
    names = {t.__name__ for t in ld.LOCAL_DEPLOY_TOOLS}
    assert names == {
        "build_image",
        "push_image",
        "deploy_to_cluster",
        "validate_deployment",
        "rollback_deployment",
    }


def test_local_deployer_drives_tools_with_test_model(monkeypatch):
    monkeypatch.setattr(ld, "get_deployment_adapters", _fake_adapters)
    agent = ld.create_local_deployer(model=TestModel())

    result = agent.run_sync("Deploy orders-api v1.0.0 to the local cluster with 1 replica")

    assert isinstance(result.output, str)
    called = {
        part.tool_name
        for message in result.all_messages()
        for part in getattr(message, "parts", [])
        if isinstance(part, ToolCallPart)
    }
    # TestModel exercises every registered tool once — proves the wiring end to end.
    assert "build_image" in called
    assert "deploy_to_cluster" in called
