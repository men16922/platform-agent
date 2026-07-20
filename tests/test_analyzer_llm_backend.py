"""Guards for the analyzer's pluggable LLM backend.

On-prem prioritises a local OpenAI-compatible model (Qwen via the MLX proxy):
when ``ANALYZER_LLM_ENDPOINT`` is set the analyzer must POST to that endpoint's
``/chat/completions`` instead of Bedrock, while the cloud path (no env) stays on
Bedrock. Both return the same ``{root_cause, severity, confidence}`` JSON.
"""

from __future__ import annotations

import json

import pytest

from src.agents.operations.aws import analyzer


class _FakeResp:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def test_openai_backend_used_when_endpoint_configured(monkeypatch):
    captured = {}

    def fake_post(url, json=None, timeout=None):  # noqa: A002 - mirror requests API
        captured["url"] = url
        captured["body"] = json
        return _FakeResp(
            {"choices": [{"message": {"content": '{"ok": true}'}}]}
        )

    monkeypatch.setenv("ANALYZER_LLM_ENDPOINT", "http://127.0.0.1:18091/v1")
    monkeypatch.setenv("ANALYZER_LLM_MODEL", "qwen-test")
    monkeypatch.setattr("requests.post", fake_post)
    # Bedrock must NOT be touched on the on-prem path.
    monkeypatch.setattr(
        analyzer._BEDROCK, "invoke_model",
        lambda **_: pytest.fail("Bedrock called while ANALYZER_LLM_ENDPOINT set"),
    )

    out = analyzer._invoke_llm("SYS", "USER")

    assert out == '{"ok": true}'
    assert captured["url"] == "http://127.0.0.1:18091/v1/chat/completions"
    assert captured["body"]["model"] == "qwen-test"
    roles = [m["role"] for m in captured["body"]["messages"]]
    assert roles == ["system", "user"]


def test_bedrock_backend_used_when_no_endpoint(monkeypatch):
    monkeypatch.delenv("ANALYZER_LLM_ENDPOINT", raising=False)
    calls = {}

    class _Body:
        def read(self):
            return json.dumps({"content": [{"text": '{"from": "bedrock"}'}]})

    def fake_invoke(**kwargs):
        calls["modelId"] = kwargs.get("modelId")
        return {"body": _Body()}

    monkeypatch.setattr(analyzer._BEDROCK, "invoke_model", fake_invoke)

    out = analyzer._invoke_llm("SYS", "USER")

    assert out == '{"from": "bedrock"}'
    assert calls["modelId"] == analyzer._MODEL_ID


def test_analyse_end_to_end_over_qwen(monkeypatch):
    """_analyse must parse a Qwen JSON response into (root_cause, severity, conf)."""
    monkeypatch.setenv("ANALYZER_LLM_ENDPOINT", "http://127.0.0.1:18091/v1")
    payload = {
        "choices": [
            {"message": {"content": json.dumps({
                "root_cause": "CrashLoop from bad config",
                "severity": "P2",
                "confidence": 0.82,
            })}}
        ]
    }
    monkeypatch.setattr("requests.post", lambda *a, **k: _FakeResp(payload))

    raw = analyzer._invoke_llm("S", "U")
    parsed = analyzer._parse_llm_response(raw)
    assert parsed["root_cause"].startswith("CrashLoop")
    assert parsed["severity"] == "P2"
    assert parsed["confidence"] == 0.82


def test_parser_tolerates_prose_around_json():
    """Local coder models (Qwen) wrap JSON in commentary — parser must cope."""
    messy = (
        'Here is my analysis:\n'
        '{"root_cause": "OOMKilled under load", "severity": "P2", "confidence": 0.7}\n'
        'Let me know if you need more detail.'
    )
    parsed = analyzer._parse_llm_response(messy)
    assert parsed["severity"] == "P2"
    assert parsed["confidence"] == 0.7

    fenced = '```json\n{"root_cause": "x", "severity": "P1", "confidence": 0.9}\n```'
    assert analyzer._parse_llm_response(fenced)["severity"] == "P1"
