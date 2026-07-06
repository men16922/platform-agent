"""
MCP ↔ A2A Bridge — Translates between MCP tool calls and A2A protocol messages.

Enables MCP-based agents (like Strands tools) to communicate with A2A-based
agents, and vice versa. The bridge acts as a protocol translator.

Usage:
    from src.agents.ai.gateway.bridge import McpA2aBridge

    bridge = McpA2aBridge()

    # MCP tool call → A2A message
    a2a_response = bridge.mcp_to_a2a(tool_name="kubectl_get", arguments={"resource": "pods"})

    # A2A message → MCP tool call
    mcp_result = bridge.a2a_to_mcp(message={"parts": [{"text": "get pods in default namespace"}]})
"""

from __future__ import annotations

from typing import Any

from src.agents.ai.gateway.a2a_server import A2AServer
from src.agents.ai.gateway.mcp_server import MCPServer, ToolResult


class McpA2aBridge:
    """Bidirectional bridge between MCP tool calls and A2A messages."""

    def __init__(
        self,
        mcp_server: MCPServer | None = None,
        a2a_server: A2AServer | None = None,
    ):
        self._mcp = mcp_server or MCPServer()
        self._a2a = a2a_server or A2AServer()

    @property
    def mcp_server(self) -> MCPServer:
        return self._mcp

    @property
    def a2a_server(self) -> A2AServer:
        return self._a2a

    def mcp_to_a2a(self, tool_name: str, arguments: dict[str, Any] | None = None) -> dict:
        """Execute an MCP tool call and wrap the result as an A2A message.

        Args:
            tool_name: MCP tool name (e.g., 'kubectl_get').
            arguments: Tool arguments.

        Returns:
            A2A-formatted response with the tool result as a task artifact.
        """
        # Execute MCP tool
        result = self._mcp.call_tool(tool_name, arguments)

        # Wrap as A2A message
        text = result.output if result.success else f"Error: {result.error}"
        message = {
            "role": "ROLE_USER",
            "parts": [{"text": f"[MCP:{tool_name}] {text}"}],
        }

        # Send through A2A server
        return self._a2a.send_message(message)

    def a2a_to_mcp(self, message: dict[str, Any]) -> ToolResult:
        """Parse an A2A message and route to the appropriate MCP tool.

        Extracts intent from the message text and maps to an MCP tool call.

        Args:
            message: A2A message object with role and parts.

        Returns:
            MCP ToolResult from executing the derived tool call.
        """
        # Extract text from message parts
        text_parts = [p.get("text", "") for p in message.get("parts", []) if "text" in p]
        text = " ".join(text_parts).lower()

        # Route to appropriate MCP tool based on intent
        tool_name, arguments = self._route_message(text)

        if tool_name:
            return self._mcp.call_tool(tool_name, arguments)

        return ToolResult(success=False, error=f"Could not route message to MCP tool: {text[:100]}")

    def _route_message(self, text: str) -> tuple[str | None, dict[str, Any]]:
        """Route a message text to an MCP tool + arguments.

        Simple keyword-based routing. In production, an LLM would do this.
        """
        if "pods" in text or "get pod" in text:
            ns = self._extract_namespace(text)
            return "kubectl_get", {"resource": "pods", "namespace": ns}
        elif "deployment" in text and "status" in text:
            name = self._extract_name(text)
            ns = self._extract_namespace(text)
            return "kubectl_rollout_status", {"deployment": name, "namespace": ns}
        elif "deploy" in text or "get deploy" in text:
            ns = self._extract_namespace(text)
            return "kubectl_get", {"resource": "deployments", "namespace": ns}
        elif "service" in text or "get svc" in text:
            ns = self._extract_namespace(text)
            return "kubectl_get", {"resource": "services", "namespace": ns}
        elif "logs" in text:
            name = self._extract_name(text)
            ns = self._extract_namespace(text)
            return "kubectl_logs", {"pod": name, "namespace": ns}
        elif "build" in text and "docker" in text:
            tag = self._extract_tag(text)
            return "docker_build", {"tag": tag}
        elif "push" in text and "docker" in text:
            tag = self._extract_tag(text)
            return "docker_push", {"image": tag}
        elif "images" in text or "docker image" in text:
            return "docker_images", {}
        elif "containers" in text or "docker ps" in text:
            return "docker_ps", {"all_containers": "all" in text}

        return None, {}

    def _extract_namespace(self, text: str) -> str:
        """Extract namespace from text, default to 'default'."""
        words = text.split()
        for i, w in enumerate(words):
            if w in ("namespace", "ns", "-n") and i + 1 < len(words):
                return words[i + 1]
            if w.startswith("namespace="):
                return w.split("=", 1)[1]
        return "default"

    def _extract_name(self, text: str) -> str:
        """Extract a resource name from text."""
        words = text.split()
        for i, w in enumerate(words):
            if w in ("name", "pod", "deployment") and i + 1 < len(words):
                return words[i + 1]
        # Return last meaningful word as fallback
        return words[-1] if words else "unknown"

    def _extract_tag(self, text: str) -> str:
        """Extract a Docker image tag from text."""
        words = text.split()
        for w in words:
            if ":" in w and "/" in w:
                return w
            if ":" in w and not w.startswith("http"):
                return w
        return "app:latest"
