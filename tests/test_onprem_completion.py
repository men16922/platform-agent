"""Apply/undo acknowledgement cannot stand in for a completed rollout."""
from types import SimpleNamespace

import pytest

from src.agents.adapters.deployment.base import DeployStatus, ServiceSpec
from src.agents.adapters.deployment import onprem


@pytest.mark.parametrize("action", ["deploy", "rollback"])
def test_accepted_change_with_failed_rollout_is_not_success(monkeypatch, action):
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        failed = "status" in command
        return SimpleNamespace(returncode=1 if failed else 0, stdout="accepted" if not failed else "",
                               stderr="rollout timed out" if failed else "")

    monkeypatch.setattr(onprem.subprocess, "run", run)
    monkeypatch.setenv("PLATFORM_DEPLOY_KUBECONFIG", "/local/test-deployer")
    adapter = onprem.OnPremClusterAdapter()
    spec = ServiceSpec(name="orders-api-dogfood", image="orders-api-dogfood", version="missing", namespace="acme-dev-observability")
    result = adapter.deploy(spec, "localhost:5001/orders-api-dogfood:missing") if action == "deploy" else adapter.rollback(spec)
    assert (result.status == DeployStatus.FAILED if action == "deploy" else result.success is False)
    assert "rollout timed out" in result.error
    if action == "deploy":
        assert result.metadata == {"applied": True, "rollout_verified": False}
    assert len(calls) == 2
    assert all("/local/test-deployer" in cmd and "acme-dev-observability" in cmd for cmd in calls)
