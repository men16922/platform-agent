"""Transport heartbeats must not cancel the action they are observing."""
import asyncio
import json

from fastapi.testclient import TestClient

from src.agents.ai import local_deploy_api as api
from src.agents.ai.model_router import DeployOutcome


def test_slow_event_survives_heartbeats_and_is_recorded(tmp_path, monkeypatch):
    store = tmp_path / "activity.jsonl"
    monkeypatch.delenv("PLATFORM_ACTIVITY_TABLE", raising=False)
    monkeypatch.setenv("PLATFORM_ACTIVITY_FILE", str(store))
    monkeypatch.setattr(api, "_SSE_HEARTBEAT_S", 0.01)
    state = {"started": 0, "completed": 0, "cancelled": 0}

    async def slow_stream(*args, **kwargs):
        state["started"] += 1
        yield {"type": "tool_call", "tool": "list_pods", "args": {"namespace": "acme-dev-observability"}}
        try:
            await asyncio.sleep(0.055)
        except asyncio.CancelledError:
            state["cancelled"] += 1
            raise
        state["completed"] += 1
        yield {"type": "result", "outcome": DeployOutcome(
            ok=True, model="local-qwen", provider="onprem", summary="Read complete",
            steps=[{"tool": "list_pods", "args": {"namespace": "acme-dev-observability"},
                    "result": {"ok": True, "output": "No resources found"}}],
        )}

    monkeypatch.setattr(api, "route_deploy_stream", slow_stream)
    with TestClient(api.app) as client:
        response = client.post("/api/local-deploy/stream", json={"instruction": "Read pods"})
    assert state == {"started": 1, "completed": 1, "cancelled": 0}
    assert response.text.count(": keepalive") >= 2
    frames = [json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: ")]
    assert frames[-1]["type"] == "done"
    assert frames[-1]["ok"] is True
    rows = [json.loads(line) for line in store.read_text().splitlines()]
    assert len(rows) == 1 and rows[0]["PK"] == "ACTIVITY"
    assert frames[-1]["record"]["activity_id"] == rows[0]["activity_id"]


def test_closing_heartbeat_stream_cleans_up_the_pending_event(monkeypatch):
    monkeypatch.setattr(api, "_SSE_HEARTBEAT_S", 0.01)

    async def scenario():
        closed = asyncio.Event()

        async def waiting():
            try:
                await asyncio.sleep(3600)
                yield {"type": "unreachable"}
            finally:
                closed.set()

        stream = api._events_with_heartbeats(waiting())
        assert await anext(stream) is None
        await stream.aclose()
        assert closed.is_set()

    asyncio.run(scenario())
