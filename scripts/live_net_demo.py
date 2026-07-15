"""Live demonstration of Tier 2 #3 (MCP-over-HTTP connector) and #4 (cross-account
STS graceful fallback) — over REAL HTTP and REAL STS, not stub transports.

Exercises the shipped code paths:
  - src.agents.ai.gateway.mcp_server.remote_mcp_tool + post_mcp_call  (real urllib HTTP)
  - src.agents.adapters.aws_session.assume_role_session              (real boto3 STS)

#3 stands up a local mock MCP server (stdlib http.server) and calls it through the
real connector. #4 attempts a real AssumeRole against a role that does not exist in
this account and shows the graceful fallback to in-account credentials.

Run: python scripts/live_net_demo.py
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from src.agents.adapters.aws_session import assume_role_session
from src.agents.ai.circuit_breaker import CircuitBreaker
from src.agents.ai.gateway.mcp_server import MCPServer, post_mcp_call, remote_mcp_tool


# --- Part C: #3 MCP-over-HTTP connector over a real local mock MCP server ------

class _MockMCP(BaseHTTPRequestHandler):
    hits: list[dict] = []

    def log_message(self, *_a):  # silence access logs
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        _MockMCP.hits.append(body)
        tool = body.get("params", {}).get("name")
        if tool == "search":
            result = {"content": [{"type": "text", "text": "kubernetes docs: kubectl rollout restart"}], "isError": False}
            payload = {"jsonrpc": "2.0", "id": body.get("id"), "result": result}
        elif tool == "boom":
            result = {"content": [{"type": "text", "text": "upstream 503"}], "isError": True}
            payload = {"jsonrpc": "2.0", "id": body.get("id"), "result": result}
        else:
            payload = {"jsonrpc": "2.0", "id": body.get("id"), "error": {"code": -32601, "message": "method not found"}}
        data = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def demo_mcp_over_http() -> None:
    print("\n" + "=" * 78)
    print("PART C — Tier 2 #3: MCP-over-HTTP connector over a REAL local mock MCP server")
    print("=" * 78)
    server = HTTPServer(("127.0.0.1", 0), _MockMCP)
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    endpoint = f"http://127.0.0.1:{port}/rpc"
    print(f"  mock MCP server listening on {endpoint}")

    try:
        # REAL transport (post_mcp_call, stdlib urllib) — genuine HTTP round-trip.
        search = remote_mcp_tool("web_search", "Search", {"query": "string"},
                                 endpoint=endpoint, remote_tool="search", transport=post_mcp_call)
        errtool = remote_mcp_tool("flaky", "Flaky", {}, endpoint=endpoint, remote_tool="boom", transport=post_mcp_call)
        dead = remote_mcp_tool("offline", "Offline", {}, endpoint="http://127.0.0.1:1/rpc", transport=post_mcp_call)
        gw = MCPServer(extra_tools=[search, errtool, dead])

        _MockMCP.hits.clear()
        r1 = gw.call_tool("web_search", {"query": "how to restart a deployment"})
        print(f"\n[C1 real HTTP round-trip] success={r1.success}  output={r1.output!r}")
        print(f"  server received JSON-RPC: method={_MockMCP.hits[-1]['method']!r} "
              f"name={_MockMCP.hits[-1]['params']['name']!r} args={_MockMCP.hits[-1]['params']['arguments']}")

        r2 = gw.call_tool("flaky")
        print(f"\n[C2 remote isError → mapped] success={r2.success}  error={r2.error!r}")

        hits_before = len(_MockMCP.hits)
        gw.disable_tool("web_search")
        r3 = gw.call_tool("web_search", {"query": "blocked"})
        print(f"\n[C3 kill-switch] success={r3.success}  error={r3.error!r}")
        print(f"  server hit count unchanged: {len(_MockMCP.hits) == hits_before}  "
              "(no HTTP call made — kill-switch fired before dispatch)")

        r4 = gw.call_tool("offline")
        print(f"\n[C4 transport failure → graceful degrade] success={r4.success}  error={r4.error!r}")
    finally:
        server.shutdown()


# --- Part D: #4 cross-account STS graceful fallback over real STS --------------

def _identity(session) -> str:
    return session.client("sts").get_caller_identity()["Arn"]


def demo_sts_fallback() -> None:
    print("\n" + "=" * 78)
    print("PART D — Tier 2 #4: cross-account STS AssumeRole graceful fallback (REAL STS)")
    print("=" * 78)
    account = boto3_account()
    bogus_role = f"arn:aws:iam::{account}:role/nonexistent-cross-account-role"
    print(f"  current account={account}")
    print(f"  attempting AssumeRole into a role that does NOT exist: {bogus_role}")

    # REAL boto3 STS assume_role → fails → graceful fallback to in-account creds.
    result = assume_role_session(bogus_role, region="us-east-1", breaker=CircuitBreaker())
    print(f"\n[D1 graceful fallback] assumed={result.assumed}  fell_back={result.fell_back}")
    print(f"  returned session identity (proves in-account fallback works): {_identity(result.session)}")

    # fallback=False must re-raise the real STS error.
    try:
        assume_role_session(bogus_role, region="us-east-1", fallback=False, breaker=CircuitBreaker())
        print("\n[D2 fallback=False] UNEXPECTED: no error raised")
    except Exception as exc:
        print(f"\n[D2 fallback=False → re-raises real STS error] {type(exc).__name__}: {str(exc)[:120]}")


def boto3_account() -> str:
    import boto3

    return boto3.client("sts", region_name="us-east-1").get_caller_identity()["Account"]


if __name__ == "__main__":
    demo_mcp_over_http()
    demo_sts_fallback()
    print("\n" + "=" * 78)
    print("DONE — real HTTP (connector) and real STS (fallback) exercised the shipped code.")
    print("=" * 78)
