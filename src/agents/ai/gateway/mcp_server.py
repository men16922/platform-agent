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

import subprocess
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


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


class MCPServer:
    """MCP Server that routes tool calls to kubectl/docker implementations."""

    def __init__(self):
        self._kubectl = KubectlTool()
        self._docker = DockerTool()
        # Dispatch derives from the single catalog — no hand-synced name→handler map.
        self._tool_map = {spec.name: spec.handler for spec in TOOL_CATALOG}

    @property
    def tools(self) -> list[ToolDefinition]:
        """List available tools (the catalog's discovery view)."""
        return MCP_TOOLS

    def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> ToolResult:
        """Execute a tool by name with the given arguments.

        Args:
            name: Tool name (e.g., 'kubectl_get', 'docker_build').
            arguments: Tool arguments as a dictionary.

        Returns:
            ToolResult with success status and output/error.

        Raises:
            ValueError: If tool name is not found.
        """
        if name not in self._tool_map:
            raise ValueError(f"Unknown tool: {name}. Available: {list(self._tool_map.keys())}")

        fn = self._tool_map[name]
        args = arguments or {}
        return fn(**args)
