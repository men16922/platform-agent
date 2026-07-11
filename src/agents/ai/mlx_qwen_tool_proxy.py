"""OpenAI-compatible tool-call normalization proxy for MLX Qwen3-Coder.

Qwen3-Coder can emit ``<function=...>`` markup without the surrounding
``<tool_call>`` markers expected by the MLX server parser.  This localhost-only
proxy forces the upstream MLX request to stream, buffers a single response, and
re-emits a normalized OpenAI response with standard ``tool_calls``.

It is framework-neutral: the response format mirrors the *client's* request.
Streaming clients (Strands' ``OpenAIModel``) get an SSE stream; non-streaming
clients (Pydantic AI's ``run_sync``, which sends ``"stream": false``) get a
single ``chat.completion`` JSON object.

Run with::

    python -m src.agents.ai.mlx_qwen_tool_proxy \
      --upstream http://127.0.0.1:8080 --port 18081
"""

from __future__ import annotations

import argparse
import json
import re
import uuid
from http.client import HTTPConnection
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse


_FUNCTION_RE = re.compile(r"<function=(?P<name>[^>]+)>(?P<body>.*?)</function>", re.DOTALL)
_PARAM_RE = re.compile(r"<parameter=(?P<name>[^>]+)>\n?(?P<value>.*?)\n?</parameter>", re.DOTALL)


def parse_qwen_function_markup(content: str) -> tuple[str, dict[str, Any]] | None:
    """Parse the Qwen3-Coder function XML emitted by MLX into JSON arguments."""
    function = _FUNCTION_RE.search(content)
    if not function:
        return None

    arguments: dict[str, Any] = {}
    for parameter in _PARAM_RE.finditer(function.group("body")):
        value = parameter.group("value").strip()
        try:
            arguments[parameter.group("name")] = json.loads(value)
        except json.JSONDecodeError:
            arguments[parameter.group("name")] = value
    return function.group("name").strip(), arguments


def _collect_sse_content(payload: str) -> tuple[str, list[dict[str, Any]], dict[str, Any]]:
    content: list[str] = []
    tool_calls_map: dict[int, dict[str, Any]] = {}
    metadata: dict[str, Any] = {}
    for line in payload.splitlines():
        if not line.startswith("data: "):
            continue
        data = line[6:]
        if data == "[DONE]":
            continue
        try:
            event = json.loads(data)
        except json.JSONDecodeError:
            continue
        metadata = event
        for choice in event.get("choices", []):
            delta = choice.get("delta", {})
            if text := delta.get("content"):
                content.append(text)
            if upstream_tool_calls := delta.get("tool_calls"):
                for tc in upstream_tool_calls:
                    idx = tc.get("index", 0)
                    if idx not in tool_calls_map:
                        tool_calls_map[idx] = {
                            "index": idx,
                            "id": tc.get("id") or f"call_{uuid.uuid4().hex[:24]}",
                            "type": "function",
                            "function": {"name": "", "arguments": ""}
                        }
                    fn = tc.get("function", {})
                    if name := fn.get("name"):
                        tool_calls_map[idx]["function"]["name"] = name
                    if args := fn.get("arguments"):
                        tool_calls_map[idx]["function"]["arguments"] += args
    tool_calls = sorted(tool_calls_map.values(), key=lambda x: x["index"])
    return "".join(content), tool_calls, metadata


def _normalize_tool_calls(raw_tool_calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Coerce arbitrary upstream tool_calls into indexed OpenAI shape."""
    normalized: list[dict[str, Any]] = []
    for idx, tc in enumerate(raw_tool_calls):
        fn = tc.get("function", {})
        normalized.append({
            "index": tc.get("index", idx),
            "id": tc.get("id") or f"call_{uuid.uuid4().hex[:24]}",
            "type": "function",
            "function": {"name": fn.get("name", ""), "arguments": fn.get("arguments", "")},
        })
    return normalized


def _extract_from_json(raw: str) -> tuple[str, list[dict[str, Any]], dict[str, Any]]:
    """Fallback for an upstream that answered with a non-streaming JSON body."""
    try:
        event = json.loads(raw)
    except json.JSONDecodeError:
        return "", [], {}
    choice = (event.get("choices") or [{}])[0]
    message = choice.get("message", {})
    content = message.get("content") or ""
    tool_calls = _normalize_tool_calls(message.get("tool_calls") or [])
    return content, tool_calls, event


class QwenToolProxyHandler(BaseHTTPRequestHandler):
    upstream: str = "http://127.0.0.1:8080"

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
        return

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/v1/chat/completions":
            self.send_error(404)
            return
        body = self.rfile.read(int(self.headers["Content-Length"]))
        try:
            request = json.loads(body)
        except json.JSONDecodeError:
            request = {}
        client_wants_stream = bool(request.get("stream", False))

        # Always stream from upstream so we can buffer + normalize uniformly,
        # regardless of what the client asked for.
        request["stream"] = True
        upstream_body = json.dumps(request).encode("utf-8")

        upstream = urlparse(self.upstream)
        conn = HTTPConnection(upstream.hostname, upstream.port or 80, timeout=600)
        conn.request("POST", self.path, body=upstream_body, headers={"Content-Type": "application/json"})
        response = conn.getresponse()
        raw = response.read().decode("utf-8")

        content, tool_calls, metadata = _collect_sse_content(raw)
        if not content and not tool_calls:
            # Upstream ignored stream=true and answered with a JSON body.
            content, tool_calls, metadata = _extract_from_json(raw)

        if not tool_calls:
            parsed = parse_qwen_function_markup(content)
            if parsed:
                name, arguments = parsed
                tool_calls = [{
                    "index": 0,
                    "id": f"call_{uuid.uuid4().hex[:24]}",
                    "type": "function",
                    "function": {"name": name, "arguments": json.dumps(arguments)},
                }]

        model = metadata.get("model", "qwen-mlx")
        chunk_id = metadata.get("id", f"chatcmpl-{uuid.uuid4()}")

        if client_wants_stream:
            self._respond_stream(chunk_id, model, content, tool_calls)
        else:
            self._respond_json(chunk_id, model, content, tool_calls)

    def _respond_stream(self, chunk_id: str, model: str, content: str, tool_calls: list[dict[str, Any]]) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        if tool_calls:
            self._event(chunk_id, model, {"role": "assistant", "tool_calls": tool_calls}, None)
            self._event(chunk_id, model, {}, "tool_calls")
        else:
            self._event(chunk_id, model, {"role": "assistant", "content": content}, "stop")
        self.wfile.write(b"data: [DONE]\n\n")

    def _respond_json(self, chunk_id: str, model: str, content: str, tool_calls: list[dict[str, Any]]) -> None:
        if tool_calls:
            # "index" is a streaming-delta concept; drop it from the final message.
            message = {
                "role": "assistant",
                "content": None,
                "tool_calls": [{k: v for k, v in tc.items() if k != "index"} for tc in tool_calls],
            }
            finish_reason = "tool_calls"
        else:
            message = {"role": "assistant", "content": content}
            finish_reason = "stop"
        payload = {
            "id": chunk_id,
            "object": "chat.completion",
            "created": 0,
            "model": model,
            "choices": [{"index": 0, "message": message, "finish_reason": finish_reason}],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        }
        data = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _event(self, chunk_id: str, model: str, delta: dict[str, Any], finish_reason: str | None) -> None:
        event = {"id": chunk_id, "object": "chat.completion.chunk", "created": 0, "model": model, "choices": [{"index": 0, "delta": delta, "finish_reason": finish_reason}]}
        self.wfile.write(f"data: {json.dumps(event)}\n\n".encode("utf-8"))
        self.wfile.flush()


def main() -> None:
    parser = argparse.ArgumentParser(description="MLX Qwen3-Coder OpenAI tool-call compatibility proxy")
    parser.add_argument("--upstream", default="http://127.0.0.1:8080")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=18081)
    args = parser.parse_args()
    QwenToolProxyHandler.upstream = args.upstream
    ThreadingHTTPServer((args.host, args.port), QwenToolProxyHandler).serve_forever()


if __name__ == "__main__":
    main()
