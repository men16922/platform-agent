import json
import threading
from http.client import HTTPConnection
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from src.agents.ai.mlx_qwen_tool_proxy import (
    QwenToolProxyHandler,
    _extract_from_json,
    _normalize_tool_calls,
    parse_qwen_function_markup,
)


def test_parses_qwen_function_markup_and_json_values():
    parsed = parse_qwen_function_markup(
        "<function=deploy_to_cluster>\n"
        "<parameter=service_name>\napi\n</parameter>\n"
        "<parameter=ports>\n[80]\n</parameter>\n"
        "</function>"
    )

    assert parsed == ("deploy_to_cluster", {"service_name": "api", "ports": [80]})


def test_ignores_regular_model_text():
    assert parse_qwen_function_markup("Deployment is healthy.") is None


def test_normalize_tool_calls_fills_index_and_id():
    normalized = _normalize_tool_calls([{"function": {"name": "build_image", "arguments": "{}"}}])
    assert normalized[0]["index"] == 0
    assert normalized[0]["type"] == "function"
    assert normalized[0]["function"]["name"] == "build_image"
    assert normalized[0]["id"].startswith("call_")


def test_extract_from_json_reads_non_streaming_body():
    raw = json.dumps({
        "model": "qwen",
        "choices": [{"message": {"content": "", "tool_calls": [
            {"id": "call_1", "function": {"name": "push_image", "arguments": "{}"}}
        ]}}],
    })
    content, tool_calls, meta = _extract_from_json(raw)
    assert content == ""
    assert tool_calls[0]["function"]["name"] == "push_image"
    assert meta["model"] == "qwen"


# --- Integration: stream flag drives the response format ------------------


def _sse(deltas: list[dict]) -> str:
    lines = [
        "data: " + json.dumps({"id": "up1", "model": "qwen", "choices": [{"delta": d, "finish_reason": None}]})
        for d in deltas
    ]
    lines.append("data: [DONE]")
    return "\n\n".join(lines) + "\n\n"


def _serve(handler_cls) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler_cls)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def _make_upstream(sse_body: str):
    class _FakeUpstream(BaseHTTPRequestHandler):
        def log_message(self, *args):  # noqa: A003
            return

        def do_POST(self):  # noqa: N802
            self.rfile.read(int(self.headers.get("Content-Length", 0)))
            payload = sse_body.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()
            self.wfile.write(payload)

    return _FakeUpstream


def _post(port: int, stream: bool):
    conn = HTTPConnection("127.0.0.1", port, timeout=10)
    conn.request(
        "POST",
        "/v1/chat/completions",
        body=json.dumps({"stream": stream, "messages": []}),
        headers={"Content-Type": "application/json"},
    )
    return conn.getresponse()


def _run_through_proxy(sse_body: str, stream: bool):
    upstream = _serve(_make_upstream(sse_body))
    try:
        QwenToolProxyHandler.upstream = f"http://127.0.0.1:{upstream.server_address[1]}"
        proxy = _serve(QwenToolProxyHandler)
        try:
            resp = _post(proxy.server_address[1], stream=stream)
            return resp.getheader("Content-Type"), resp.read().decode("utf-8")
        finally:
            proxy.shutdown()
    finally:
        upstream.shutdown()


def test_non_streaming_client_gets_json_tool_calls():
    body = _sse([{"tool_calls": [{"index": 0, "id": "call_x", "function": {"name": "build_image", "arguments": "{}"}}]}])
    content_type, raw = _run_through_proxy(body, stream=False)
    assert content_type == "application/json"
    data = json.loads(raw)
    assert data["object"] == "chat.completion"
    message = data["choices"][0]["message"]
    assert message["tool_calls"][0]["function"]["name"] == "build_image"
    assert "index" not in message["tool_calls"][0]  # stripped from final message
    assert data["choices"][0]["finish_reason"] == "tool_calls"


def test_streaming_client_still_gets_sse():
    body = _sse([{"tool_calls": [{"index": 0, "id": "call_x", "function": {"name": "build_image", "arguments": "{}"}}]}])
    content_type, raw = _run_through_proxy(body, stream=True)
    assert content_type == "text/event-stream"
    assert "chat.completion.chunk" in raw
    assert "data: [DONE]" in raw
    assert "build_image" in raw


def test_non_streaming_client_gets_xml_fallback_as_tool_call():
    markup = "<function=validate_deployment>\n<parameter=service_name>\napi\n</parameter>\n</function>"
    body = _sse([{"content": markup}])
    content_type, raw = _run_through_proxy(body, stream=False)
    assert content_type == "application/json"
    data = json.loads(raw)
    message = data["choices"][0]["message"]
    assert message["tool_calls"][0]["function"]["name"] == "validate_deployment"
    assert json.loads(message["tool_calls"][0]["function"]["arguments"]) == {"service_name": "api"}
