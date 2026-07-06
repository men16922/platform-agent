"""
Tests for MCP Server, A2A Server, and MCP↔A2A Bridge.
"""

from __future__ import annotations

from unittest.mock import patch, MagicMock

import pytest

from src.agents.ai.gateway.mcp_server import MCPServer, KubectlTool, DockerTool, ToolResult, MCP_TOOLS
from src.agents.ai.gateway.a2a_server import A2AServer, TaskState
from src.agents.ai.gateway.bridge import McpA2aBridge


# --- MCP Server Tests ---

class TestMCPToolDefinitions:
    def test_has_9_tools(self):
        assert len(MCP_TOOLS) == 9

    def test_tool_names(self):
        names = {t.name for t in MCP_TOOLS}
        assert "kubectl_get" in names
        assert "kubectl_apply" in names
        assert "kubectl_rollout_status" in names
        assert "kubectl_logs" in names
        assert "kubectl_describe" in names
        assert "docker_build" in names
        assert "docker_push" in names
        assert "docker_images" in names
        assert "docker_ps" in names


class TestMCPServer:
    def test_tools_property(self):
        server = MCPServer()
        assert len(server.tools) == 9

    def test_call_unknown_tool_raises(self):
        server = MCPServer()
        with pytest.raises(ValueError, match="Unknown tool"):
            server.call_tool("nonexistent_tool")

    @patch("src.agents.ai.gateway.mcp_server._run_cmd")
    def test_call_kubectl_get(self, mock_run):
        mock_run.return_value = ToolResult(success=True, output='{"items": []}')
        server = MCPServer()
        result = server.call_tool("kubectl_get", {"resource": "pods", "namespace": "default"})
        assert result.success is True

    @patch("src.agents.ai.gateway.mcp_server._run_cmd")
    def test_call_docker_images(self, mock_run):
        mock_run.return_value = ToolResult(success=True, output="nginx:latest\napp:v1")
        server = MCPServer()
        result = server.call_tool("docker_images", {})
        assert result.success is True
        assert "nginx" in result.output


class TestKubectlTool:
    @patch("src.agents.ai.gateway.mcp_server._run_cmd")
    def test_get_pods(self, mock_run):
        mock_run.return_value = ToolResult(success=True, output="pod-1")
        result = KubectlTool.get("pods", namespace="kube-system")
        assert result.success is True
        mock_run.assert_called_once()

    @patch("src.agents.ai.gateway.mcp_server.subprocess.run")
    def test_apply_manifest(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="created", stderr="")
        result = KubectlTool.apply('{"kind": "Pod"}', namespace="default")
        assert result.success is True

    @patch("src.agents.ai.gateway.mcp_server._run_cmd")
    def test_rollout_status(self, mock_run):
        mock_run.return_value = ToolResult(success=True, output="successfully rolled out")
        result = KubectlTool.rollout_status("web", namespace="default")
        assert result.success is True

    @patch("src.agents.ai.gateway.mcp_server._run_cmd")
    def test_logs(self, mock_run):
        mock_run.return_value = ToolResult(success=True, output="log line 1\nlog line 2")
        result = KubectlTool.logs("pod-1")
        assert result.success is True

    @patch("src.agents.ai.gateway.mcp_server._run_cmd")
    def test_describe(self, mock_run):
        mock_run.return_value = ToolResult(success=True, output="Name: pod-1\nStatus: Running")
        result = KubectlTool.describe("pod", "pod-1")
        assert result.success is True


class TestDockerTool:
    @patch("src.agents.ai.gateway.mcp_server._run_cmd")
    def test_build(self, mock_run):
        mock_run.return_value = ToolResult(success=True, output="Built app:v1")
        result = DockerTool.build("app:v1", ".")
        assert result.success is True

    @patch("src.agents.ai.gateway.mcp_server._run_cmd")
    def test_push(self, mock_run):
        mock_run.return_value = ToolResult(success=True, output="Pushed")
        result = DockerTool.push("registry/app:v1")
        assert result.success is True

    @patch("src.agents.ai.gateway.mcp_server._run_cmd")
    def test_images(self, mock_run):
        mock_run.return_value = ToolResult(success=True, output="nginx:latest")
        result = DockerTool.images()
        assert result.success is True

    @patch("src.agents.ai.gateway.mcp_server._run_cmd")
    def test_ps(self, mock_run):
        mock_run.return_value = ToolResult(success=True, output="abc123\tnginx\tUp 2m")
        result = DockerTool.ps()
        assert result.success is True


# --- A2A Server Tests ---

class TestA2AServer:
    @pytest.fixture
    def server(self):
        return A2AServer()

    def test_agent_card(self, server):
        card = server.agent_card
        assert "name" in card
        assert "version" in card

    def test_send_message_creates_task(self, server):
        message = {"role": "ROLE_USER", "parts": [{"text": "Deploy api v1"}]}
        result = server.send_message(message)

        assert "task" in result
        task = result["task"]
        assert "id" in task
        assert "contextId" in task
        assert task["status"]["state"] == TaskState.COMPLETED.value
        assert len(task["artifacts"]) > 0

    def test_get_task(self, server):
        message = {"role": "ROLE_USER", "parts": [{"text": "Deploy web"}]}
        result = server.send_message(message)
        task_id = result["task"]["id"]

        fetched = server.get_task(task_id)
        assert fetched is not None
        assert fetched["id"] == task_id

    def test_get_task_not_found(self, server):
        assert server.get_task("nonexistent") is None

    def test_list_tasks_empty(self, server):
        result = server.list_tasks()
        assert result["tasks"] == []
        assert result["totalSize"] == 0

    def test_list_tasks_after_send(self, server):
        server.send_message({"role": "ROLE_USER", "parts": [{"text": "test"}]})
        server.send_message({"role": "ROLE_USER", "parts": [{"text": "test2"}]})

        result = server.list_tasks()
        assert result["totalSize"] == 2

    def test_cancel_task_not_found(self, server):
        assert server.cancel_task("nonexistent") is None

    def test_cancel_completed_task_fails(self, server):
        message = {"role": "ROLE_USER", "parts": [{"text": "test"}]}
        result = server.send_message(message)
        task_id = result["task"]["id"]

        # Task is already completed, cannot cancel
        assert server.cancel_task(task_id) is None

    def test_deploy_message_response(self, server):
        message = {"role": "ROLE_USER", "parts": [{"text": "Deploy orders-api v2"}]}
        result = server.send_message(message)
        artifact_text = result["task"]["artifacts"][0]["parts"][0]["text"]
        assert "Deployment" in artifact_text or "deploy" in artifact_text.lower()


# --- Bridge Tests ---

class TestMcpA2aBridge:
    @pytest.fixture
    def bridge(self):
        return McpA2aBridge()

    @patch("src.agents.ai.gateway.mcp_server._run_cmd")
    def test_mcp_to_a2a(self, mock_run, bridge):
        mock_run.return_value = ToolResult(success=True, output="pod-1 Running")

        result = bridge.mcp_to_a2a("kubectl_get", {"resource": "pods", "namespace": "default"})

        assert "task" in result
        assert result["task"]["status"]["state"] == TaskState.COMPLETED.value

    @patch("src.agents.ai.gateway.mcp_server._run_cmd")
    def test_mcp_to_a2a_error(self, mock_run, bridge):
        mock_run.return_value = ToolResult(success=False, error="connection refused")

        result = bridge.mcp_to_a2a("kubectl_get", {"resource": "pods"})

        assert "task" in result
        # The task completes (A2A server always creates a task), but the content
        # contains the MCP error forwarded through the message
        assert result["task"]["status"]["state"] == TaskState.COMPLETED.value

    @patch("src.agents.ai.gateway.mcp_server._run_cmd")
    def test_a2a_to_mcp_pods(self, mock_run, bridge):
        mock_run.return_value = ToolResult(success=True, output="pod-1 Running")

        message = {"parts": [{"text": "get pods in default namespace"}]}
        result = bridge.a2a_to_mcp(message)

        assert result.success is True

    @patch("src.agents.ai.gateway.mcp_server._run_cmd")
    def test_a2a_to_mcp_docker_images(self, mock_run, bridge):
        mock_run.return_value = ToolResult(success=True, output="nginx:latest")

        message = {"parts": [{"text": "list docker images"}]}
        result = bridge.a2a_to_mcp(message)

        assert result.success is True

    def test_a2a_to_mcp_unknown_message(self, bridge):
        message = {"parts": [{"text": "hello world"}]}
        result = bridge.a2a_to_mcp(message)

        assert result.success is False
        assert "Could not route" in result.error

    def test_bridge_has_servers(self, bridge):
        assert bridge.mcp_server is not None
        assert bridge.a2a_server is not None
