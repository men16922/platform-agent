import json
import threading
from http.client import HTTPConnection
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

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
    lines.append('data: ' + json.dumps({"id": "up1", "model": "qwen", "choices": [{"delta": {}, "finish_reason": "stop"}]}))
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


def _exchange(body, *, stream, status=200, content_type="text/event-stream", headers=None):
    """Real loopback HTTP peers; no cloud service or model call."""
    received = []

    class Upstream(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            received.append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
            data = body.encode()
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            for name, value in (headers or {}).items():
                self.send_header(name, value)
            self.end_headers()
            self.wfile.write(data)

    upstream = _serve(Upstream)
    proxy_type = type("TestProxy", (QwenToolProxyHandler,), {
        "upstream": f"http://127.0.0.1:{upstream.server_address[1]}",
    })
    proxy = _serve(proxy_type)
    conn = HTTPConnection("127.0.0.1", proxy.server_address[1], timeout=10)
    try:
        request = {"stream": stream, "messages": []}
        if stream:
            request["stream_options"] = {"include_usage": True}
        conn.request("POST", "/v1/chat/completions", json.dumps(request), {"Content-Type": "application/json"})
        response = conn.getresponse()
        return response.status, dict(response.getheaders()), response.read().decode(), received
    finally:
        conn.close()
        proxy.shutdown()
        proxy.server_close()
        upstream.shutdown()
        upstream.server_close()


def _events(body):
    return [json.loads(line[6:]) for line in body.splitlines()
            if line.startswith("data: ") and line != "data: [DONE]"]


@pytest.mark.parametrize("stream", [False, True])
@pytest.mark.parametrize("status", [404, 503])
def test_upstream_error_status_body_and_retry_after_survive(stream, status):
    body = json.dumps({"error": {"message": "System message must be at the beginning.", "type": "upstream_error"}})
    code, headers, raw, received = _exchange(body, stream=stream, status=status,
        content_type="application/json", headers={"Retry-After": "7"})
    assert code == status
    assert raw == body and headers["Content-Type"] == "application/json"
    assert headers["Retry-After"] == "7"
    assert len(received) == 1  # proxy does not retry generation


@pytest.mark.parametrize("stream", [False, True])
@pytest.mark.parametrize("upstream_format", ["sse", "json"])
def test_length_and_actual_usage_survive_separate_usage_frame(stream, upstream_format):
    usage = {"prompt_tokens": 17, "completion_tokens": 3, "total_tokens": 20,
             "prompt_tokens_details": {"cached_tokens": 11}}
    if upstream_format == "sse":
        body = _sse([{"content": "partial answer"}]).replace('"finish_reason": "stop"', '"finish_reason": "length"')
        # MLX's usage-only chunk has no choice/finish_reason; it must not erase it.
        body = body.replace("data: [DONE]", 'data: ' + json.dumps({"id": "up1", "model": "qwen", "choices": [], "usage": usage}) + '\n\ndata: [DONE]')
    else:
        body = json.dumps({"id": "up1", "model": "qwen", "choices": [{
            "message": {"content": "partial answer"}, "finish_reason": "length"}], "usage": usage})
    code, _, raw, received = _exchange(body, stream=stream,
        content_type="application/json" if upstream_format == "json" else "text/event-stream")
    assert code == 200
    assert received[0]["stream"] is True
    assert received[0]["stream_options"]["include_usage"] is True
    events = _events(raw) if stream else [json.loads(raw)]
    choices = [choice for event in events for choice in event["choices"]]
    assert choices[-1]["finish_reason"] == "length"
    assert [e["usage"] for e in events if "usage" in e] == [usage]
    assert "partial answer" in raw


@pytest.mark.parametrize("stream", [False, True])
def test_missing_usage_is_not_reported_as_zero_tokens(stream):
    code, _, raw, _ = _exchange(_sse([{"content": "OK"}]), stream=stream)
    assert code == 200
    events = _events(raw) if stream else [json.loads(raw)]
    assert all("usage" not in event or event["usage"] is None for event in events)


@pytest.mark.parametrize("stream", [False, True])
@pytest.mark.parametrize("kind", ["markup", "native"])
def test_truncated_generation_cannot_be_promoted_to_executable_tool_call(stream, kind):
    delta = ({"content": '<function=restart><parameter=service>api</parameter></function>'}
             if kind == "markup" else {"tool_calls": [{"index": 0, "id": "call_x", "function": {"name": "restart", "arguments": "{}"}}]})
    body = _sse([delta]).replace('"finish_reason": "stop"', '"finish_reason": "length"')
    code, _, raw, _ = _exchange(body, stream=stream)
    assert code == 200
    events = _events(raw) if stream else [json.loads(raw)]
    choices = [choice for event in events for choice in event["choices"]]
    assert choices[-1]["finish_reason"] == "length"
    assert not any(c.get("delta", c.get("message", {})).get("tool_calls") for c in choices)


@pytest.mark.parametrize("stream", [False, True])
def test_empty_answer_keeps_token_limit_instead_of_becoming_success(stream):
    body = _sse([]).replace('"finish_reason": "stop"', '"finish_reason": "length"')
    code, _, raw, _ = _exchange(body, stream=stream)
    assert code == 200
    events = _events(raw) if stream else [json.loads(raw)]
    assert [c for e in events for c in e["choices"]][-1]["finish_reason"] == "length"


@pytest.mark.parametrize("stream", [False, True])
def test_stream_without_terminal_reason_is_not_reported_as_completed(stream):
    body = 'data: ' + json.dumps({"choices": [{"delta": {"content": "unfinished"}}]}) + '\n\n'
    code, _, raw, received = _exchange(body, stream=stream)
    assert code == 502
    assert json.loads(raw)["error"]["code"] == "invalid_upstream_response"
    assert len(received) == 1
