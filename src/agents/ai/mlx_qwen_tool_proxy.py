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
from http.client import HTTPConnection, HTTPException
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


def _iter_json_objects(text: str):
    """Yield top-level JSON objects embedded anywhere in text (prose, ``` fences,
    <tool_call> tags), using brace-balanced decoding so nested args survive."""
    decoder = json.JSONDecoder()
    i = 0
    n = len(text)
    while i < n:
        if text[i] == "{":
            try:
                obj, end = decoder.raw_decode(text, i)
                yield obj
                i = end
                continue
            except json.JSONDecodeError:
                pass
        i += 1


def parse_json_tool_call(content: str) -> tuple[str, dict[str, Any]] | None:
    """Parse a tool call emitted as a JSON object ``{"name": ..., "arguments": {...}}``.

    Covers models (e.g. Qwen2.5-Coder-Instruct) that write the call as a bare or
    ```json-fenced object, or inside Hermes ``<tool_call>...</tool_call>`` tags,
    instead of the Qwen3-Coder ``<function=...>`` markup. Returns the FIRST such
    object so the agent runs one tool per turn (trailing prose/plans are ignored).
    """
    for obj in _iter_json_objects(content):
        if not isinstance(obj, dict) or "name" not in obj:
            continue
        raw_args = obj.get("arguments", obj.get("parameters", {}))
        if isinstance(raw_args, str):
            try:
                raw_args = json.loads(raw_args)
            except json.JSONDecodeError:
                raw_args = {}
        if not isinstance(raw_args, dict):
            continue
        return str(obj["name"]).strip(), raw_args
    return None


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
        except json.JSONDecodeError as exc:
            raise ValueError("Malformed upstream SSE event") from exc
        if not isinstance(event, dict):
            raise ValueError("Upstream event must be an object")
        # A final usage-only frame has choices=[]; do not let it erase the
        # completion reason from the preceding frame (notably `length`).
        for key in ("id", "model", "usage", "error"):
            if event.get(key) is not None:
                metadata[key] = event[key]
        for choice in event.get("choices", []):
            if choice.get("finish_reason") is not None:
                metadata["finish_reason"] = choice["finish_reason"]
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
    event = json.loads(raw)
    if not isinstance(event, dict):
        raise ValueError("Upstream response must be an object")
    choice = (event.get("choices") or [{}])[0]
    event["finish_reason"] = choice.get("finish_reason")
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
            self.send_error(400, "Expected a JSON object")
            return
        if not isinstance(request, dict):
            self.send_error(400, "Expected a JSON object")
            return
        client_wants_stream = bool(request.get("stream", False))
        stream_options = request.get("stream_options") or {}
        if not isinstance(stream_options, dict):
            self.send_error(400, "Expected stream_options object")
            return
        client_wants_usage = bool(stream_options.get("include_usage", False))

        # Always stream from upstream so we can buffer + normalize uniformly,
        # regardless of what the client asked for.
        request["stream"] = True
        request["stream_options"] = {**stream_options, "include_usage": True}
        upstream_body = json.dumps(request).encode("utf-8")

        upstream = urlparse(self.upstream)
        conn = HTTPConnection(upstream.hostname, upstream.port or 80, timeout=600)
        try:
            conn.request("POST", self.path, body=upstream_body, headers={"Content-Type": "application/json"})
            response = conn.getresponse()
            raw_bytes = response.read()
        except (HTTPException, OSError):
            self._upstream_error("upstream_transport_error")
            return
        finally:
            conn.close()

        if not 200 <= response.status < 300:
            # The proxy must not turn a model/template/service error into an
            # empty successful generation. Do not retry the upstream request.
            self.send_response(response.status)
            self.send_header("Content-Type", response.getheader("Content-Type") or "application/octet-stream")
            self.send_header("Content-Length", str(len(raw_bytes)))
            if retry_after := response.getheader("Retry-After"):
                self.send_header("Retry-After", retry_after)
            self.end_headers()
            self.wfile.write(raw_bytes)
            return

        try:
            raw = raw_bytes.decode("utf-8")
            is_sse = (response.getheader("Content-Type") or "").startswith("text/event-stream") or raw.lstrip().startswith("data:")
            content, tool_calls, metadata = _collect_sse_content(raw) if is_sse else _extract_from_json(raw)
            if metadata.get("error") is not None:
                self._upstream_error("upstream_generation_error", error=metadata["error"])
                return
            finish_reason = metadata.get("finish_reason")
            if not isinstance(finish_reason, str) or not finish_reason:
                raise ValueError("Upstream did not report a terminal completion reason")
        except (ValueError, TypeError, KeyError, AttributeError):
            self._upstream_error("invalid_upstream_response")
            return

        if finish_reason not in ("stop", "tool_calls"):
            # Even syntactically complete arguments in a truncated/filtered
            # generation are not a completed tool request. Preserve the reason
            # for the SDK, but never promote partial output to executable calls.
            tool_calls = []
        elif not tool_calls:
            parsed = parse_qwen_function_markup(content) or parse_json_tool_call(content)
            if parsed:
                name, arguments = parsed
                tool_calls = [{
                    "index": 0,
                    "id": f"call_{uuid.uuid4().hex[:24]}",
                    "type": "function",
                    "function": {"name": name, "arguments": json.dumps(arguments)},
                }]

        if tool_calls and finish_reason == "stop":
            finish_reason = "tool_calls"  # completed textual tool-call fallback

        model = metadata.get("model", "qwen-mlx")
        chunk_id = metadata.get("id", f"chatcmpl-{uuid.uuid4()}")
        usage = metadata.get("usage")
        if not isinstance(usage, dict):
            usage = None  # absent accounting is unknown, never zero tokens

        if client_wants_stream:
            self._respond_stream(chunk_id, model, content, tool_calls, finish_reason, usage if client_wants_usage else None)
        else:
            self._respond_json(chunk_id, model, content, tool_calls, finish_reason, usage)

    def _upstream_error(self, code: str, *, error: Any = None) -> None:
        data = json.dumps({"error": error if error is not None else {
            "code": code, "message": "The upstream model did not return a valid completed response.",
        }}).encode("utf-8")
        self.send_response(502)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _respond_stream(self, chunk_id: str, model: str, content: str, tool_calls: list[dict[str, Any]], finish_reason: str, usage: dict[str, Any] | None) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        if tool_calls:
            self._event(chunk_id, model, {"role": "assistant", "tool_calls": tool_calls}, None)
            self._event(chunk_id, model, {}, finish_reason)
        else:
            self._event(chunk_id, model, {"role": "assistant", "content": content}, finish_reason)
        if usage is not None:
            self._event(chunk_id, model, {}, None, usage=usage)
        self.wfile.write(b"data: [DONE]\n\n")

    def _respond_json(self, chunk_id: str, model: str, content: str, tool_calls: list[dict[str, Any]], finish_reason: str, usage: dict[str, Any] | None) -> None:
        if tool_calls:
            # "index" is a streaming-delta concept; drop it from the final message.
            message = {
                "role": "assistant",
                "content": None,
                "tool_calls": [{k: v for k, v in tc.items() if k != "index"} for tc in tool_calls],
            }
        else:
            message = {"role": "assistant", "content": content}
        payload = {
            "id": chunk_id,
            "object": "chat.completion",
            "created": 0,
            "model": model,
            "choices": [{"index": 0, "message": message, "finish_reason": finish_reason}],
        }
        if usage is not None:
            payload["usage"] = usage
        data = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _event(self, chunk_id: str, model: str, delta: dict[str, Any], finish_reason: str | None, *, usage: dict[str, Any] | None = None) -> None:
        event = {"id": chunk_id, "object": "chat.completion.chunk", "created": 0, "model": model, "choices": [{"index": 0, "delta": delta, "finish_reason": finish_reason}]}
        if usage is not None:
            event.update(choices=[], usage=usage)
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
