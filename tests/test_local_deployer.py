import re
from pathlib import Path
from types import SimpleNamespace

from pydantic_ai.messages import ToolCallPart
from pydantic_ai.models.test import TestModel

import src.agents.ai.local_deployer as ld


def _prompt_advertised_tools() -> set[str]:
    """Tool names the system prompt tells the LLM it has (the discovery view)."""
    block = ld.DEPLOYER_SYSTEM_PROMPT.split("## Tools", 1)[1].split("## How to work", 1)[0]
    return set(re.findall(r"^- `(\w+)`", block, flags=re.MULTILINE))


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


def test_deploy_tools_registered():
    names = {t.__name__ for t in ld.LOCAL_DEPLOY_TOOLS}
    assert names == {
        "deploy_service",
        "build_image",
        "push_image",
        "deploy_to_cluster",
        "validate_deployment",
        "rollback_deployment",
    }


def test_deploy_service_runs_full_pipeline(monkeypatch):
    # deploy_to_cluster reports success via DeployStatus.SUCCESS.value == "success",
    # so the composite's success gate keys on that (the shared _fake_adapters uses an
    # unrealistic "DEPLOYED" sentinel; build a realistic cluster stub here).
    adapters = _fake_adapters("onprem")
    adapters.cluster.deploy = lambda spec, image_uri: SimpleNamespace(
        status=SimpleNamespace(value="success"), deployment_id="d1", namespace="default",
        replicas_desired=1, endpoint="http://svc", error=None,
    )
    monkeypatch.setattr(ld, "get_deployment_adapters", lambda provider: adapters)
    out = ld.deploy_service("orders-api", "1.0.0", context_path="examples/orders-api")
    assert out["ok"] is True
    assert out["failed_step"] is None
    assert out["steps"] == {"build": True, "push": True, "deploy": True, "validate": True}


def test_ops_agent_includes_readonly_tools():
    names = {t.__name__ for t in ld.ALL_OPS_TOOLS}
    # deploy/recover (mutating) + read-only diagnostics
    assert {"build_image", "rollback_deployment"} <= names
    assert {"list_pods", "get_logs", "describe_deployment", "rollout_status", "list_namespaces"} <= names


def test_local_deployer_drives_tools_with_test_model(monkeypatch):
    monkeypatch.setattr(ld, "get_deployment_adapters", _fake_adapters)
    # Limit to deploy tools — the agent also has read-only ops + MUTATING provision
    # tools (real terraform/kubectl) that must not run in a unit test.
    agent = ld.create_local_deployer(
        model=TestModel(call_tools=["build_image", "push_image", "deploy_to_cluster", "validate_deployment"])
    )

    result = agent.run_sync("Deploy orders-api v1.0.0 to the local cluster with 1 replica")

    assert isinstance(result.output, str)
    called = {
        part.tool_name
        for message in result.all_messages()
        for part in getattr(message, "parts", [])
        if isinstance(part, ToolCallPart)
    }
    assert "build_image" in called
    assert "deploy_to_cluster" in called


def test_platform_agent_includes_provision_tools():
    names = {t.__name__ for t in ld.ALL_OPS_TOOLS}
    assert {"provision_cluster", "teardown_cluster"} <= names


def test_single_catalog_is_source_of_truth():
    """Dispatch (ALL_OPS_TOOLS) and discovery (prompt inventory) derive from one catalog — no drift."""
    catalog_names = [t.name for t in ld.AGENT_TOOL_CATALOG]
    assert len(catalog_names) == len(set(catalog_names))  # unique
    # Dispatch view: registered tools mirror the catalog exactly, in order.
    assert [t.__name__ for t in ld.ALL_OPS_TOOLS] == catalog_names
    # Discovery view: the prompt advertises exactly the registered tools — no tool
    # is hidden from the LLM, and none is advertised that isn't wired.
    assert _prompt_advertised_tools() == set(catalog_names)
    # The catalog covers exactly the union of the three source tool lists (nothing dropped/added).
    from src.agents.ai.ops_tools import OPS_TOOLS
    from src.agents.ai.provision_tools import PROVISION_TOOLS

    union = {t.__name__ for t in OPS_TOOLS + PROVISION_TOOLS + ld.LOCAL_DEPLOY_TOOLS}
    assert set(catalog_names) == union


def test_catalog_categories_are_known():
    """Every catalog entry uses a declared category (so the prompt renderer places it)."""
    assert all(t.category in ld._CATEGORY_BLURBS for t in ld.AGENT_TOOL_CATALOG)
