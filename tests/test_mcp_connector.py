"""MCP-over-HTTP connector + per-tool/global kill-switch tests."""

import pytest

from src.agents.ai.gateway.mcp_server import (
    MCP_TOOLS,
    TOOL_CATALOG,
    MCPServer,
    ToolResult,
    ToolSpec,
    remote_mcp_tool,
)


# --- kill-switch --------------------------------------------------------------


def _echo_tool(name="echo"):
    return ToolSpec(name, "echo", {}, lambda **kw: ToolResult(success=True, output="ran"))


def test_global_kill_switch_blocks_every_tool_without_executing():
    ran: list[str] = []
    tool = ToolSpec("echo", "echo", {}, lambda **kw: ran.append("x") or ToolResult(True, output="ran"))
    server = MCPServer(extra_tools=[tool], kill_switch=True)

    result = server.call_tool("echo")

    assert result.success is False
    assert "kill-switch active" in result.error
    assert ran == []  # handler never invoked


def test_per_tool_kill_switch_blocks_only_that_tool():
    server = MCPServer(extra_tools=[_echo_tool("echo"), _echo_tool("echo2")])
    server.disable_tool("echo")

    blocked = server.call_tool("echo")
    assert blocked.success is False
    assert "disabled by per-tool kill-switch" in blocked.error
    assert server.disabled_tools == frozenset({"echo"})

    # A sibling tool is unaffected.
    assert server.call_tool("echo2").success is True


def test_enable_tool_reverses_per_tool_kill_switch():
    server = MCPServer(extra_tools=[_echo_tool("echo")])
    server.disable_tool("echo")
    assert server.call_tool("echo").success is False
    server.enable_tool("echo")
    assert server.call_tool("echo").success is True


def test_set_kill_switch_toggles_global_gate():
    server = MCPServer(extra_tools=[_echo_tool("echo")])
    assert server.call_tool("echo").success is True
    server.set_kill_switch(True)
    assert server.call_tool("echo").success is False
    server.set_kill_switch(False)
    assert server.call_tool("echo").success is True


def test_kill_switch_from_environment(monkeypatch):
    monkeypatch.setenv("MCP_KILL_SWITCH", "true")
    monkeypatch.setenv("MCP_DISABLED_TOOLS", "kubectl_get, docker_push")
    server = MCPServer()
    assert server.kill_switch is True
    assert server.disabled_tools == frozenset({"kubectl_get", "docker_push"})


def test_unknown_tool_still_raises_even_with_kill_switch():
    # Existence is checked before the kill-switch, so a bad name still surfaces.
    server = MCPServer(kill_switch=True)
    with pytest.raises(ValueError, match="Unknown tool"):
        server.call_tool("nope")


# --- base catalog stays intact (non-breaking) --------------------------------


def test_base_catalog_unchanged():
    assert len(TOOL_CATALOG) == 9
    assert len(MCP_TOOLS) == 9
    # A default server exposes exactly the base catalog for dispatch.
    assert set(MCPServer()._tool_map) == {spec.name for spec in TOOL_CATALOG}


def test_extra_tools_appear_in_discovery_and_dispatch():
    server = MCPServer(extra_tools=[_echo_tool("web_search")])
    names = {t.name for t in server.tools}
    assert "web_search" in names and "kubectl_get" in names
    assert len(server.tools) == 10
    assert server.call_tool("web_search").success is True


# --- remote MCP connector (intercept -> tools/call -> reinject) ---------------


def _mcp_result(text, is_error=False):
    return {"jsonrpc": "2.0", "id": "1", "result": {"content": [{"type": "text", "text": text}], "isError": is_error}}


def test_remote_connector_forwards_and_reinjects_text():
    sent: dict = {}

    def transport(endpoint, tool, arguments, *, timeout=10.0):
        sent.update(endpoint=endpoint, tool=tool, arguments=arguments)
        return _mcp_result("search results here")

    spec = remote_mcp_tool(
        "web_search",
        "Search the web",
        {"query": "string"},
        endpoint="http://remote-mcp/rpc",
        remote_tool="search",
        transport=transport,
    )
    server = MCPServer(extra_tools=[spec])

    result = server.call_tool("web_search", {"query": "k8s"})

    assert result.success is True
    assert result.output == "search results here"
    assert sent["endpoint"] == "http://remote-mcp/rpc"
    assert sent["tool"] == "search"  # remote_tool override honored
    assert sent["arguments"] == {"query": "k8s"}


def test_remote_connector_maps_is_error_result():
    spec = remote_mcp_tool(
        "web_search", "Search", {}, endpoint="http://x", transport=lambda *a, **k: _mcp_result("boom", is_error=True)
    )
    result = spec.handler()
    assert result.success is False
    assert "boom" in result.error


def test_remote_connector_maps_jsonrpc_error():
    err = {"jsonrpc": "2.0", "id": "1", "error": {"code": -32601, "message": "method not found"}}
    spec = remote_mcp_tool("web_search", "Search", {}, endpoint="http://x", transport=lambda *a, **k: err)
    result = spec.handler()
    assert result.success is False
    assert "method not found" in result.error


def test_remote_connector_degrades_on_transport_failure():
    def transport(*_a, **_k):
        raise ConnectionError("connection refused")

    spec = remote_mcp_tool("web_search", "Search", {}, endpoint="http://down", transport=transport)
    result = spec.handler()
    assert result.success is False
    assert "remote MCP call to http://down failed" in result.error
    assert "ConnectionError" in result.error


def test_remote_connector_is_governed_by_kill_switch():
    calls: list[int] = []
    spec = remote_mcp_tool(
        "web_search", "Search", {}, endpoint="http://x", transport=lambda *a, **k: calls.append(1) or _mcp_result("ok")
    )
    server = MCPServer(extra_tools=[spec])
    server.disable_tool("web_search")

    result = server.call_tool("web_search", {"query": "q"})

    assert result.success is False
    assert "disabled by per-tool kill-switch" in result.error
    assert calls == []  # kill-switch prevents the remote call entirely
