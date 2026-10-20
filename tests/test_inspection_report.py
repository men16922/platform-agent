"""Acquired facts must survive wrong or incomplete model explanations and replay."""
import asyncio
from copy import deepcopy
from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient
from pydantic_ai.messages import ModelRequest, ModelResponse, TextPart, ToolCallPart, ToolReturnPart
import pytest

from src.agents.ai import local_deploy_api as api, model_router as mr
from src.agents.ai.inspection_report import inspection_report, model_completion
from tests.test_deployment_evidence import assess, snapshot


def recorded_result(*, positive=False, finish="length"):
    d, objects = snapshot()
    if not positive:
        objects[1]["spec"]["template"]["spec"]["containers"][0].pop("readinessProbe")
        objects[3]["spec"]["containers"][0].pop("readinessProbe")
    evidence = assess(d, objects)
    args = {"deployment": "orders", "namespace": "acme"}
    result = {"ok": True, "output": "Description", "evidence": evidence}
    raw = "The application is healthy. Roll back now. " * 4
    messages = [ModelResponse([ToolCallPart("describe_deployment", args, tool_call_id="call-1")]),
                ModelRequest([ToolReturnPart("describe_deployment", result, tool_call_id="call-1")]),
                ModelResponse([TextPart(raw)], finish_reason=finish)]
    return SimpleNamespace(output=raw, all_messages=lambda: messages)


def outcome(**kwargs):
    return mr._local_outcome(recorded_result(**kwargs), "local-qwen", "onprem", {})


def test_wrong_incomplete_model_text_never_replaces_durable_observations():
    class Agent:
        async def run(self, instruction):
            return recorded_result()
    result = asyncio.run(mr.route_deploy("inspect", "local-qwen", "onprem", agent_factory=lambda **_: Agent()))
    assert "Application health not established" in result.summary
    assert "Recovery candidate not established" in result.summary
    assert "Roll back now" not in result.summary
    assert result.inspection[0]["previous_health"] == "not_established"
    assert result.model_completion["status"] == "incomplete"
    assert result.model_completion["finish_reason"] == "length"
    assert "Roll back now" in result.model_completion["text"]
    assert "unverified" in result.trace[-1]["text"]
    assert result.ok is True  # Read completed; semantic success is explicitly separate.


def test_supported_previous_revision_remains_a_specific_review_candidate():
    result = outcome(positive=True, finish="stop")
    assert result.inspection[0]["candidate_revision"] == 1
    assert result.inspection[0]["execution_authorized"] is False
    assert "Revision 1 is a recovery review candidate; execution not authorized" in result.summary
    assert result.model_completion["status"] == "complete"
    assert result.model_completion["semantic_verified"] is False


@pytest.mark.parametrize("finish,expected", [(None, "unknown"), ("content_filter", "incomplete"), ("error", "incomplete")])
def test_unknown_or_filtered_completion_is_not_complete(finish, expected):
    assert model_completion([ModelResponse([TextPart("partial")], finish_reason=finish)], "partial")["status"] == expected


def test_model_response_usage_retains_provider_counts_without_inventing_zero():
    from pydantic_ai.usage import RequestUsage
    one = ModelResponse([TextPart("one")], usage=RequestUsage(input_tokens=100, output_tokens=20))
    two = ModelResponse([TextPart("two")], usage=RequestUsage(input_tokens=140, output_tokens=30), finish_reason="stop")
    completion = model_completion([one, two], "two")
    assert completion["model_responses"] == 2
    assert completion["tool_call_attempts"] == 0
    attempt = ModelResponse([ToolCallPart("describe_deployment", {"deployment":"orders"}, "one")])
    assert model_completion([attempt, two], "two")["tool_call_attempts"] == 1
    assert completion["token_usage"] == {"status":"reported", "input_tokens":240, "output_tokens":50}
    for messages in ([], [ModelResponse([TextPart("unreported")])],
                     [one, ModelResponse([TextPart("missing second usage")])],
                     [ModelResponse([], usage=RequestUsage(input_tokens=100, output_tokens=0))]):
        usage = model_completion(messages, "unknown")["token_usage"]
        assert usage == {"status":"not_established", "input_tokens":None, "output_tokens":None}


def test_target_mismatch_missing_evidence_and_mutating_runs_are_not_promoted():
    result = outcome()
    steps = deepcopy(result.steps)
    steps[0]["args"]["namespace"] = "globex"
    assert inspection_report(steps)[0]["available"] is False
    steps[0]["result"].pop("evidence")
    assert inspection_report(steps) is None
    steps = deepcopy(result.steps) + [{"tool": "rollback_deployment", "args": {}, "result": {"success": True}}]
    assert inspection_report(steps) is None  # Do not turn an actual action into an inspection.


@pytest.mark.parametrize("durable", [False, True])
def test_sse_and_durable_replay_retain_facts_completion_and_original_interpretation(tmp_path, monkeypatch, durable):
    monkeypatch.setenv("PLATFORM_ACTIVITY_FILE", str(tmp_path / "activity.jsonl"))
    monkeypatch.setenv("PLATFORM_STATE_DSN", f"sqlite://{tmp_path}/runs.db")
    result = outcome()
    async def events(*args, **kwargs):
        yield {"type": "tool_call", "tool": "describe_deployment", "args": {"deployment": "orders", "namespace": "acme"}}
        yield {"type": "tool_result", "tool": "describe_deployment", "ok": True, "result": result.steps[0]["result"]}
        yield {"type": "result", "outcome": result}
    monkeypatch.setattr(api, "route_deploy_stream", events)
    rid = str(uuid4())
    body = {"instruction": "inspect orders", "model": "local-qwen", "provider": "onprem"}
    if durable:
        body["request_id"] = rid
    with TestClient(api.app) as client:
        response = client.post("/api/local-deploy/stream", json=body, headers={"X-Platform-Actor": "alice"})
        assert response.status_code == 200
        import json
        frames = [json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: ")]
        done = frames[-1]
        assert done["inspection"] == result.inspection
        assert done["model_completion"] == result.model_completion
        assert "healthy" not in done["summary"]
        if durable:
            stored = client.get(f"/api/local-deploy/runs/{rid}", headers={"X-Platform-Actor": "alice"}).json()
            assert stored["events"][-1] == done
            assert stored["status"] == "succeeded"
        assert "deployment_id" not in done["record"]
        rows = [json.loads(line) for line in (tmp_path / "activity.jsonl").read_text().splitlines()]
        assert all(row["PK"] == "ACTIVITY" for row in rows)
        assert rows[-1]["summary"] == result.summary
        assert "unverified" in rows[-1]["trace"]
