"""Measure elapsed execution against real local records, never placeholder zero."""
import asyncio
import json

import pytest

from src.agents.ai import deploy_recorder as rec
from src.agents.ai import local_deploy_api as api
from src.agents.ai.model_router import DeployOutcome


@pytest.fixture
def store(tmp_path, monkeypatch):
    path = tmp_path / "activity.jsonl"
    monkeypatch.delenv("PLATFORM_ACTIVITY_TABLE", raising=False)
    monkeypatch.setenv("PLATFORM_ACTIVITY_FILE", str(path))
    return path


@pytest.mark.parametrize("transport", ["sync", "stream", "managed"])
def test_execution_delay_is_measured_and_persisted(store, monkeypatch, transport):
    outcome = DeployOutcome(ok=True, model="local-qwen", provider="onprem", summary="Complete",
                            steps=[{"tool": "deploy_to_cluster", "args": {"service_name": "orders-api"},
                                    "result": {"success": True, "applied": True}}])

    async def run(*args, **kwargs):
        await asyncio.sleep(0.03)
        return outcome

    async def stream(*args, **kwargs):
        yield {"type": "result", "outcome": await run()}

    monkeypatch.setattr(api, "route_deploy", run)
    monkeypatch.setattr(api, "route_deploy_stream", stream)

    async def scenario():
        req = api.DeployRequest(instruction="Deploy")
        if transport == "sync":
            await api.local_deploy(req, factory=None, front_door=None)
        elif transport == "stream":
            response = await api.local_deploy_stream(req, factory=None)
            _ = [event async for event in response.body_iterator]
        else:
            _ = [event async for event in api._recorded_run_events(req, None)]

    asyncio.run(scenario())
    row = next(json.loads(line) for line in store.read_text().splitlines() if json.loads(line)["PK"] == "DEPLOY")
    assert row["duration_sec"] >= 0.03
    assert row["duration_scope"] == "agent_run"
    assert row["applied"] is True


def test_unmeasured_phases_do_not_inherit_total_run_time(store):
    rec.record_deploy(instruction="Provision then deploy", model="local-qwen", provider="onprem",
                      summary="Complete", ok=True, duration_sec=10,
                      steps=[{"tool": "provision_cluster", "args": {}, "result": {"success": True}},
                             {"tool": "deploy_to_cluster", "args": {}, "result": {"success": True}}])
    rows = [json.loads(line) for line in store.read_text().splitlines()]
    deployments = [row for row in rows if row["PK"] == "DEPLOY"]
    assert len(deployments) == 2
    assert all("duration_sec" not in row for row in deployments)
    assert all("applied" not in row for row in deployments)
