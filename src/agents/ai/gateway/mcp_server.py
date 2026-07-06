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
    """MCP tool definition with schema."""

    name: str
    description: str
    parameters: dict[str, Any] = field(default_factory=dict)


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


# MCP Tool definitions (schema for discovery)
MCP_TOOLS: list[ToolDefinition] = [
    ToolDefinition(
        name="kubectl_get",
        description="Get Kubernetes resources (pods, deployments, services, etc.)",
        parameters={"resource": "string", "namespace": "string", "name": "string", "output": "string"},
    ),
    ToolDefinition(
        name="kubectl_apply",
        description="Apply a Kubernetes manifest",
        parameters={"manifest": "string", "namespace": "string"},
    ),
    ToolDefinition(
        name="kubectl_rollout_status",
        description="Check rollout status of a deployment",
        parameters={"deployment": "string", "namespace": "string"},
    ),
    ToolDefinition(
        name="kubectl_logs",
        description="Get pod logs",
        parameters={"pod": "string", "namespace": "string", "tail": "integer"},
    ),
    ToolDefinition(
        name="kubectl_describe",
        description="Describe a Kubernetes resource",
        parameters={"resource": "string", "name": "string", "namespace": "string"},
    ),
    ToolDefinition(
        name="docker_build",
        description="Build a Docker image",
        parameters={"tag": "string", "context": "string"},
    ),
    ToolDefinition(
        name="docker_push",
        description="Push a Docker image to a registry",
        parameters={"image": "string"},
    ),
    ToolDefinition(
        name="docker_images",
        description="List Docker images",
        parameters={"filter_name": "string"},
    ),
    ToolDefinition(
        name="docker_ps",
        description="List running containers",
        parameters={"all_containers": "boolean"},
    ),
]


class MCPServer:
    """MCP Server that routes tool calls to kubectl/docker implementations."""

    def __init__(self):
        self._kubectl = KubectlTool()
        self._docker = DockerTool()
        self._tool_map = {
            "kubectl_get": self._kubectl.get,
            "kubectl_apply": self._kubectl.apply,
            "kubectl_rollout_status": self._kubectl.rollout_status,
            "kubectl_logs": self._kubectl.logs,
            "kubectl_describe": self._kubectl.describe,
            "docker_build": self._docker.build,
            "docker_push": self._docker.push,
            "docker_images": self._docker.images,
            "docker_ps": self._docker.ps,
        }

    @property
    def tools(self) -> list[ToolDefinition]:
        """List available tools."""
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
