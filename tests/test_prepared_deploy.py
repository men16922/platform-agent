"""Reviewed inputs, durable replay and truthful results at the local HTTP edge.

The executor seam writes a real local file. No AWS service is mocked, and these
checks are not a substitute for the real Kubernetes/browser experiment.
"""
import asyncio
import json
from uuid import uuid4

import httpx
import pytest

from src.agents.ai import local_deploy_api as api
from src.agents.ai import prepared_deploy as prepared
from src.agents.ai.local_runs import configured_manager


def request():
    return {"request_id": str(uuid4()), "service_name": "orders-api-dogfood",
            "namespace": "acme-dev-observability", "image_uri": "localhost:5001/orders-api-dogfood:r1",
            "replicas": 2, "environment": "dev"}


@pytest.mark.parametrize("result, expected", [
    ({"status": "success", "applied": True, "rollout_verified": True}, "succeeded"),
    ({"status": "failed", "applied": True, "rollout_verified": False, "error": "rollout failed"}, "failed"),
    ({"status": "success"}, "failed"),
])
def test_exact_reviewed_values_survive_replay_and_record_actual_outcome(tmp_path, monkeypatch, result, expected):
    monkeypatch.setenv("PLATFORM_STATE_DSN", f"sqlite://{tmp_path}/runs.db")
    monkeypatch.setenv("PLATFORM_ACTIVITY_FILE", str(tmp_path / "activity.jsonl"))
    effects = tmp_path / "effects.jsonl"

    def execute(**args):
        with effects.open("a") as stream:
            stream.write(json.dumps(args) + "\n")
        return result

    monkeypatch.setattr(prepared, "deploy_to_cluster", execute)

    async def scenario():
        payload = request()
        headers = {"X-Platform-Actor": "alice"}
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=api.app), base_url="http://in-process") as client:
            accepted = await client.post("/api/local-deploy/prepared", json=payload, headers=headers)
            assert accepted.status_code == 202
            manager = configured_manager()
            task = manager.tasks[payload["request_id"]]
            # No observer is needed for completion, just as after a lost response.
            await task
            saved = await client.get(f"/api/local-deploy/runs/{payload['request_id']}", headers=headers)
            assert saved.json()["status"] == expected
            assert saved.json()["request"]["image_uri"] == payload["image_uri"]
            assert (await client.post("/api/local-deploy/prepared", json=payload, headers=headers)).status_code == 202
            changed = {**payload, "replicas": 1}
            assert (await client.post("/api/local-deploy/prepared", json=changed, headers=headers)).status_code == 409
            assert (await client.post("/api/local-deploy/prepared", json=payload, headers={"X-Platform-Actor": "bob"})).status_code == 404
        args = [json.loads(line) for line in effects.read_text().splitlines()]
        assert args == [{"service_name": payload["service_name"], "namespace": payload["namespace"],
                         "image": "localhost:5001/orders-api-dogfood", "version": "r1", "image_uri": payload["image_uri"],
                         "replicas": 2, "provider": "onprem", "ports": [8080], "health_path": "/healthz"}]
        rows = [json.loads(line) for line in (tmp_path / "activity.jsonl").read_text().splitlines()]
        deployment = next(row for row in rows if row["PK"] == "DEPLOY")
        assert deployment["agent"] == "On-Prem Executor"
        assert deployment["duration_scope"] == "executor_run"
        assert deployment["status"] == ("success" if expected == "succeeded" else "failed")

    asyncio.run(scenario())


def test_invalid_input_or_missing_actor_never_dispatches(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(prepared, "deploy_to_cluster", lambda **args: calls.append(args))
    monkeypatch.setenv("PLATFORM_STATE_DSN", f"sqlite://{tmp_path}/runs.db")

    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=api.app), base_url="http://in-process") as client:
            for changes in [{"replicas": None}, {"replicas": "2"}, {"replicas": True}, {"namespace": ""},
                            {"image_uri": "localhost:5001/app"}, {"provider": "aws"}, {"actor": "bob"}]:
                response = await client.post("/api/local-deploy/prepared", json={**request(), **changes}, headers={"X-Platform-Actor": "alice"})
                assert response.status_code == 422, response.text
            assert (await client.post("/api/local-deploy/prepared", json=request())).status_code == 401
        assert calls == []
        assert not configured_manager().tasks

    asyncio.run(scenario())
