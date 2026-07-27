"""
Guards for the MCP gateway's cluster boundary.

Phase 1a removed the ambient-kubeconfig path from the executor because blast
radius was "whatever the current context can reach". The MCP gateway kept it:
every kubectl tool shelled out to a bare `kubectl`, and `kubectl_apply` took an
arbitrary manifest and an arbitrary namespace. The front door was bolted and the
side door was not.

What these pin down:

  1. A mutating cluster tool with no scoped credential is **refused**.
  2. With a scope, kubectl is **pinned** to that credential — not merely asked
     nicely to stay in its namespace.
  3. A namespace outside the scope is refused **before** the process runs.
  4. Non-cluster tools and unscoped reads are untouched, because the verified
     anonymous kagent round trip goes through them.
"""

from __future__ import annotations

import pytest

from src.agents.ai.gateway.mcp_server import (
    CLUSTER_TOOLS,
    MUTATING_CLUSTER_TOOLS,
    MCPServer,
    ToolResult,
)
from src.agents.platform.scope import IncidentScope

SCOPE = IncidentScope(
    tenant="acme",
    env="dev",
    kubeconfig_path="/tmp/acme.kubeconfig",
    approval_id="APR-MCP",
    allowed_namespaces=("acme-dev-logging", "acme-dev-observability"),
)


@pytest.fixture
def captured(monkeypatch):
    """Record argv instead of running kubectl."""
    seen: list[list[str]] = []

    def fake_run(cmd, capture_output=True, text=True, timeout=30, input=None):
        seen.append(list(cmd))

        class _P:
            returncode = 0
            stdout = "{}"
            stderr = ""

        return _P()

    monkeypatch.setattr("src.agents.ai.gateway.mcp_server.subprocess.run", fake_run)
    return seen


class TestMutationFailsClosed:
    def test_apply_without_scope_is_refused(self, captured):
        result = MCPServer().call_tool(
            "kubectl_apply", {"manifest": "kind: Pod", "namespace": "kube-system"}
        )
        assert isinstance(result, ToolResult) and result.success is False
        assert "without a scoped credential" in (result.error or "")
        assert not captured, "kubectl must not run for a refused mutation"

    def test_every_mutating_tool_is_a_cluster_tool(self):
        """A mutating tool outside CLUSTER_TOOLS would skip the gate entirely."""
        assert MUTATING_CLUSTER_TOOLS <= CLUSTER_TOOLS

    def test_apply_with_scope_runs_pinned(self, captured):
        result = MCPServer(scope=SCOPE).call_tool(
            "kubectl_apply", {"manifest": "kind: Pod", "namespace": "acme-dev-logging"}
        )
        assert result.success is True
        assert captured[0][:3] == ["kubectl", "--kubeconfig", "/tmp/acme.kubeconfig"]


class TestNamespaceBoundary:
    def test_cross_tenant_namespace_is_refused_before_the_process_runs(self, captured):
        result = MCPServer(scope=SCOPE).call_tool(
            "kubectl_get", {"resource": "pods", "namespace": "globex-dev-observability"}
        )
        assert result.success is False
        assert "outside the scope" in (result.error or "")
        assert not captured, "the refusal must land before kubectl, not after"

    @pytest.mark.parametrize("tool,args", [
        ("kubectl_get", {"resource": "pods", "namespace": "acme-dev-logging"}),
        ("kubectl_logs", {"pod": "api-1", "namespace": "acme-dev-logging"}),
        ("kubectl_describe", {"resource": "pod", "name": "api-1", "namespace": "acme-dev-logging"}),
        ("kubectl_rollout_status", {"deployment": "api", "namespace": "acme-dev-logging"}),
    ])
    def test_every_cluster_tool_is_pinned_to_the_credential(self, tool, args, captured):
        """
        Parametrised over the tools rather than spot-checked: a tool that builds
        its own bare `kubectl` argv would pass a single-tool test and quietly
        keep the ambient path alive.
        """
        MCPServer(scope=SCOPE).call_tool(tool, args)
        assert captured, f"{tool} ran no command"
        assert captured[0][:3] == ["kubectl", "--kubeconfig", "/tmp/acme.kubeconfig"], (
            f"{tool} built an unpinned kubectl argv"
        )

    def test_no_cluster_tool_escapes_the_gate(self):
        """
        Every kubectl-shaped tool in the catalog must be declared a cluster tool.
        Adding a sixth one and forgetting this set is how the side door reopens.
        """
        server = MCPServer()
        kubectl_tools = {t.name for t in server.tools if t.name.startswith("kubectl_")}
        assert kubectl_tools == CLUSTER_TOOLS, (
            f"undeclared cluster tools: {sorted(kubectl_tools - CLUSTER_TOOLS)}"
        )


class TestVerifiedPathsUnchanged:
    def test_unscoped_read_still_works(self, captured):
        """The live kagent round trip reads anonymously; it must keep working."""
        result = MCPServer().call_tool("kubectl_get", {"resource": "pods", "namespace": "default"})
        assert result.success is True
        assert captured[0][:2] == ["kubectl", "get"], "unscoped read stays ambient"

    def test_non_cluster_tools_are_not_gated(self, captured):
        result = MCPServer(scope=SCOPE).call_tool("docker_images", {})
        assert result.success is True

    def test_kill_switch_still_precedes_the_scope_gate(self, captured):
        """A killed tool must not be reported as a scope problem."""
        result = MCPServer(kill_switch=True).call_tool(
            "kubectl_apply", {"manifest": "kind: Pod", "namespace": "acme-dev-logging"}
        )
        assert result.success is False
        assert "kill-switch" in (result.error or "")
