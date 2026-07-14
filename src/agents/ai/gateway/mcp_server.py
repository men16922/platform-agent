"""
MCP Server — Model Context Protocol server exposing kubectl and docker as tools.

Provides a standard MCP interface so that any MCP-compatible AI agent can
execute container management operations through a controlled API.

Usage:
    from src.agents.ai.gateway.mcp_server import MCPServer, KubectlTool, DockerTool

    server = MCPServer()
    result = server.call_tool("kubectl_get", {"resource": "pods", "namespace": "default"})
"""

from __future__ import annotations

import json
import os
import subprocess
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any
from urllib import request


@dataclass
class ToolResult:
    """Result of an MCP tool invocation."""

    success: bool
    output: str = ""
    error: str = ""


@dataclass
class ToolDefinition:
    """MCP tool definition with schema (the discovery view of a catalog entry)."""

    name: str
    description: str
    parameters: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ToolSpec:
    """One entry in the single tool catalog — binds discovery schema to its handler.

    The catalog (``TOOL_CATALOG``) is the single source of truth: both the
    discovery list (``MCP_TOOLS``) and the server's name→handler dispatch derive
    from it, so a tool is declared in exactly one place.
    """

    name: str
    description: str
    parameters: dict[str, Any]
    handler: Callable[..., ToolResult]

    def definition(self) -> ToolDefinition:
        return ToolDefinition(name=self.name, description=self.description, parameters=self.parameters)


def _run_cmd(cmd: list[str], timeout: int = 30) -> ToolResult:
    """Execute a command and return the result."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if result.returncode == 0:
            return ToolResult(success=True, output=result.stdout.strip())
        return ToolResult(success=False, output=result.stdout.strip(), error=result.stderr.strip())
    except subprocess.TimeoutExpired:
        return ToolResult(success=False, error=f"Command timed out after {timeout}s")
    except FileNotFoundError as e:
        return ToolResult(success=False, error=str(e))


class KubectlTool:
    """kubectl operations exposed as MCP tools."""

    @staticmethod
    def get(resource: str, namespace: str = "default", name: str = "", output: str = "json") -> ToolResult:
        """Get Kubernetes resources."""
        cmd = ["kubectl", "get", resource, "--namespace", namespace, "-o", output]
        if name:
            cmd.insert(3, name)
        return _run_cmd(cmd)

    @staticmethod
    def apply(manifest: str, namespace: str = "default") -> ToolResult:
        """Apply a Kubernetes manifest from stdin."""
        try:
            result = subprocess.run(
                ["kubectl", "apply", "-f", "-", "--namespace", namespace],
                input=manifest,
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                return ToolResult(success=True, output=result.stdout.strip())
            return ToolResult(success=False, error=result.stderr.strip())
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            return ToolResult(success=False, error=str(e))

    @staticmethod
    def rollout_status(deployment: str, namespace: str = "default") -> ToolResult:
        """Check rollout status of a deployment."""
        cmd = ["kubectl", "rollout", "status", f"deployment/{deployment}", "--namespace", namespace, "--timeout=60s"]
        return _run_cmd(cmd, timeout=90)

    @staticmethod
    def logs(pod: str, namespace: str = "default", tail: int = 50) -> ToolResult:
        """Get pod logs."""
        cmd = ["kubectl", "logs", pod, "--namespace", namespace, f"--tail={tail}"]
        return _run_cmd(cmd)

    @staticmethod
    def describe(resource: str, name: str, namespace: str = "default") -> ToolResult:
        """Describe a Kubernetes resource."""
        cmd = ["kubectl", "describe", resource, name, "--namespace", namespace]
        return _run_cmd(cmd)


class DockerTool:
    """Docker operations exposed as MCP tools."""

    @staticmethod
    def build(tag: str, context: str = ".") -> ToolResult:
        """Build a Docker image."""
        cmd = ["docker", "build", "-t", tag, context]
        return _run_cmd(cmd, timeout=300)

    @staticmethod
    def push(image: str) -> ToolResult:
        """Push a Docker image to a registry."""
        cmd = ["docker", "push", image]
        return _run_cmd(cmd, timeout=180)

    @staticmethod
    def images(filter_name: str = "") -> ToolResult:
        """List Docker images."""
        cmd = ["docker", "images", "--format", "{{.Repository}}:{{.Tag}}"]
        if filter_name:
            cmd.append(filter_name)
        return _run_cmd(cmd)

    @staticmethod
    def ps(all_containers: bool = False) -> ToolResult:
        """List running containers."""
        cmd = ["docker", "ps", "--format", "{{.ID}}\t{{.Image}}\t{{.Status}}"]
        if all_containers:
            cmd.insert(2, "-a")
        return _run_cmd(cmd)


# ---------------------------------------------------------------------------
# Single tool catalog — the ONE place each gateway tool is declared. Discovery
# (MCP_TOOLS) and dispatch (MCPServer._tool_map) both derive from this, so
# kubectl/docker capabilities are governed by a single catalog rather than three
# hand-synced lists. External A2A/MCP agents and the bridge share this catalog.
# ---------------------------------------------------------------------------
TOOL_CATALOG: list[ToolSpec] = [
    ToolSpec(
        "kubectl_get",
        "Get Kubernetes resources (pods, deployments, services, etc.)",
        {"resource": "string", "namespace": "string", "name": "string", "output": "string"},
        KubectlTool.get,
    ),
    ToolSpec(
        "kubectl_apply",
        "Apply a Kubernetes manifest",
        {"manifest": "string", "namespace": "string"},
        KubectlTool.apply,
    ),
    ToolSpec(
        "kubectl_rollout_status",
        "Check rollout status of a deployment",
        {"deployment": "string", "namespace": "string"},
        KubectlTool.rollout_status,
    ),
    ToolSpec(
        "kubectl_logs",
        "Get pod logs",
        {"pod": "string", "namespace": "string", "tail": "integer"},
        KubectlTool.logs,
    ),
    ToolSpec(
        "kubectl_describe",
        "Describe a Kubernetes resource",
        {"resource": "string", "name": "string", "namespace": "string"},
        KubectlTool.describe,
    ),
    ToolSpec(
        "docker_build",
        "Build a Docker image",
        {"tag": "string", "context": "string"},
        DockerTool.build,
    ),
    ToolSpec(
        "docker_push",
        "Push a Docker image to a registry",
        {"image": "string"},
        DockerTool.push,
    ),
    ToolSpec(
        "docker_images",
        "List Docker images",
        {"filter_name": "string"},
        DockerTool.images,
    ),
    ToolSpec(
        "docker_ps",
        "List running containers",
        {"all_containers": "boolean"},
        DockerTool.ps,
    ),
]

# Discovery view, derived from the catalog (kept as the module's public schema list).
MCP_TOOLS: list[ToolDefinition] = [spec.definition() for spec in TOOL_CATALOG]


# ---------------------------------------------------------------------------
# MCP-over-HTTP connector (ref AWSome AI Gateway) — expose a *remote* MCP tool
# through this gateway's single catalog. The connector handler intercepts the
# local tool_use, forwards it to the remote MCP server over HTTP (JSON-RPC
# ``tools/call``), and reinjects the remote result as a local ToolResult. This
# lets web-search / external-API MCP servers be governed by the same catalog and
# per-tool kill-switch as the built-in kubectl/docker tools.
# ---------------------------------------------------------------------------
RemoteTransport = Callable[..., dict]


def post_mcp_call(endpoint: str, tool: str, arguments: dict[str, Any], *, timeout: float = 10.0) -> dict:
    """Invoke one remote MCP tool via a JSON-RPC ``tools/call`` over HTTP."""
    body = {
        "jsonrpc": "2.0",
        "id": "1",
        "method": "tools/call",
        "params": {"name": tool, "arguments": arguments},
    }
    payload = json.dumps(body).encode("utf-8")
    http_request = request.Request(
        endpoint, data=payload, headers={"Content-Type": "application/json"}, method="POST"
    )
    with request.urlopen(http_request, timeout=timeout) as response:  # noqa: S310 - operator-configured endpoint
        return json.loads(response.read().decode("utf-8"))


def _reinject(response: dict) -> ToolResult:
    """Translate an MCP ``tools/call`` response into a local ToolResult."""
    if not isinstance(response, dict):
        return ToolResult(success=False, error="malformed remote MCP response")
    if response.get("error"):
        err = response["error"]
        message = err.get("message", str(err)) if isinstance(err, dict) else str(err)
        return ToolResult(success=False, error=f"remote MCP error: {message}")
    result = response.get("result", {}) or {}
    text = "\n".join(
        part.get("text", "")
        for part in result.get("content", [])
        if isinstance(part, dict) and part.get("type") == "text"
    )
    if result.get("isError"):
        return ToolResult(success=False, error=text or "remote MCP tool reported an error")
    return ToolResult(success=True, output=text)


def remote_mcp_tool(
    name: str,
    description: str,
    parameters: dict[str, Any],
    *,
    endpoint: str,
    remote_tool: str | None = None,
    transport: RemoteTransport = post_mcp_call,
    timeout: float = 10.0,
) -> ToolSpec:
    """Build a catalog ToolSpec backed by a remote MCP server (intercept-reinject).

    ``remote_tool`` defaults to ``name`` when the remote server names the tool the
    same way. A transport/network failure degrades to an error ToolResult rather
    than raising, so one flaky remote connector never breaks the gateway.
    """
    remote = remote_tool or name

    def handler(**arguments: Any) -> ToolResult:
        try:
            response = transport(endpoint, remote, arguments, timeout=timeout)
        except Exception as exc:
            return ToolResult(success=False, error=f"remote MCP call to {endpoint} failed: {type(exc).__name__}: {exc}"[:400])
        return _reinject(response)

    return ToolSpec(name, description, parameters, handler)


def _env_disabled_tools() -> set[str]:
    return {name.strip() for name in os.getenv("MCP_DISABLED_TOOLS", "").split(",") if name.strip()}


def _env_kill_switch() -> bool:
    return os.getenv("MCP_KILL_SWITCH", "").lower() in ("1", "true", "yes")


class MCPServer:
    """MCP Server routing tool calls to kubectl/docker (and remote MCP) handlers.

    A per-tool + global **kill-switch** gates dispatch: a disabled tool (or, under
    the global switch, every tool) returns a blocked ToolResult without executing,
    so an operator can instantly cut off a specific capability or the whole
    gateway. Extra connectors (e.g. ``remote_mcp_tool(...)``) can be registered
    via ``extra_tools`` and are governed by the same catalog and kill-switch.
    """

    def __init__(
        self,
        *,
        extra_tools: list[ToolSpec] | None = None,
        disabled_tools: set[str] | None = None,
        kill_switch: bool | None = None,
    ):
        self._kubectl = KubectlTool()
        self._docker = DockerTool()
        # The base catalog plus any operator-registered connectors form one
        # catalog; discovery and dispatch both derive from it.
        self._catalog = list(TOOL_CATALOG) + list(extra_tools or [])
        self._tool_map = {spec.name: spec.handler for spec in self._catalog}
        self._disabled = set(disabled_tools) if disabled_tools is not None else _env_disabled_tools()
        self._kill_switch = kill_switch if kill_switch is not None else _env_kill_switch()

    @property
    def tools(self) -> list[ToolDefinition]:
        """List available tools (the catalog's discovery view, incl. connectors)."""
        return [spec.definition() for spec in self._catalog]

    @property
    def disabled_tools(self) -> frozenset[str]:
        return frozenset(self._disabled)

    @property
    def kill_switch(self) -> bool:
        return self._kill_switch

    def set_kill_switch(self, active: bool) -> None:
        """Flip the global kill-switch — blocks every tool while active."""
        self._kill_switch = bool(active)

    def disable_tool(self, name: str) -> None:
        """Per-tool kill-switch: block a single tool by name."""
        self._disabled.add(name)

    def enable_tool(self, name: str) -> None:
        self._disabled.discard(name)

    def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> ToolResult:
        """Execute a tool by name with the given arguments.

        Args:
            name: Tool name (e.g., 'kubectl_get', 'docker_build').
            arguments: Tool arguments as a dictionary.

        Returns:
            ToolResult with success status and output/error. A kill-switched tool
            returns an unsuccessful ToolResult (the tool exists but is gated).

        Raises:
            ValueError: If tool name is not found.
        """
        if name not in self._tool_map:
            raise ValueError(f"Unknown tool: {name}. Available: {list(self._tool_map.keys())}")

        # Kill-switch is checked after existence (so unknown tools still raise) but
        # before dispatch (so a blocked tool never executes).
        if self._kill_switch:
            return ToolResult(success=False, error=f"MCP kill-switch active: all tools disabled (tool '{name}' blocked)")
        if name in self._disabled:
            return ToolResult(success=False, error=f"tool '{name}' is disabled by per-tool kill-switch")

        fn = self._tool_map[name]
        args = arguments or {}
        return fn(**args)
