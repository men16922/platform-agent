"""Lost observers and duplicate requests against actual local SQLite/files.

These are offline transport/storage checks, not Kubernetes recovery evidence.
"""
import asyncio
import json
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient

from src.agents.ai import local_deploy_api as api
from src.agents.ai import local_runs
from src.agents.ai.state_store import from_dsn


@pytest.fixture
def configured(tmp_path, monkeypatch):
    monkeypatch.setenv("PLATFORM_STATE_DSN", f"sqlite://{tmp_path}/runs.db")
    monkeypatch.setenv("PLATFORM_ACTIVITY_FILE", str(tmp_path / "activity.jsonl"))
    return tmp_path


def test_sql_claim_is_atomic_across_connections_and_survives_reopen(tmp_path):
    dsn = f"sqlite://{tmp_path}/runs.db"
    # Independent connections/managers race for the same effect, not a mocked DB.
    with ThreadPoolExecutor(max_workers=8) as pool:
        claimed = list(pool.map(lambda _: from_dsn(dsn).claim("RUN", "one", {"status": "running"}), range(16)))
    assert claimed.count(True) == 1
    store = from_dsn(dsn)
    assert store.rows("RUN") == [{"status": "running"}]
    assert not store.claim("RUN", "one", {"status": "running"})
    store.append("RUN", "one", {"status": "done"})
    assert store.latest("RUN", "one") == {"status": "done"}
    assert store.claim("OTHER", "one", {"status": "running"})


def test_failed_initial_state_write_does_not_leave_an_orphan_claim(tmp_path):
    store = from_dsn(f"sqlite://{tmp_path}/runs.db")
    circular = {}
    circular["self"] = circular
    with pytest.raises(ValueError, match="Circular"):
        store.claim("RUN", "one", circular)
    assert store.latest("RUN", "one") is None
    assert store.claim("RUN", "one", {"status": "running"})


def test_disconnected_observer_finishes_once_records_and_replays(configured, monkeypatch):
    async def scenario():
        started, release = asyncio.Event(), asyncio.Event()
        effects = configured / "effects.txt"

        async def events(*args, **kwargs):
            started.set()
            yield {"type": "tool_call", "tool": "list_pods", "args": {}}
            await release.wait()
            # A local file is the actual effect counted across duplicate submits.
            with effects.open("a") as out:
                out.write("executed\n")
            yield {"type": "result", "outcome": SimpleNamespace(
                ok=True, model="local-qwen", provider="onprem", summary="Read complete",
                suitability={}, trace=[], steps=[{"tool": "list_pods", "args": {},
                                                  "result": {"ok": True, "output": "empty"}}],
            )}

        monkeypatch.setattr(api, "route_deploy_stream", events)
        request_id = str(uuid4())
        req = api.DeployRequest(instruction="Read pods", request_id=request_id)
        response = await api.local_deploy_stream(req, factory=None, x_platform_actor="alice")
        assert '"ready"' in await anext(response.body_iterator)
        await started.wait()
        await response.body_iterator.aclose()  # The observer disappears before completion.
        manager = local_runs.configured_manager()
        task = manager.tasks[request_id]
        assert not task.cancelled() and not task.done()

        # Retry before completion attaches to the same worker, as does retry after.
        replay = await api.local_deploy_stream(req, factory=None, x_platform_actor="alice")
        assert manager.tasks[request_id] is task
        await replay.body_iterator.aclose()
        release.set()
        await task
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=api.app), base_url="http://in-process") as client:
            snapshot = await client.get(f"/api/local-deploy/runs/{request_id}", headers={"X-Platform-Actor": "alice"})
            assert snapshot.status_code == 200
            state = snapshot.json()
            assert state["status"] == "succeeded"
            assert state["events"][-1]["type"] == "done"
            assert not {"actor", "instance", "fingerprint"}.intersection(state)
            assert (await client.get(f"/api/local-deploy/runs/{request_id}", headers={"X-Platform-Actor": "bob"})).status_code == 404
            assert (await client.get(f"/api/local-deploy/runs/{request_id}")).status_code == 401
            duplicate = await client.post("/api/local-deploy/stream", json=req.model_dump(mode="json"), headers={"X-Platform-Actor": "alice"})
            assert duplicate.status_code == 200 and '"done"' in duplicate.text
            changed = req.model_dump(mode="json") | {"instruction": "Different work"}
            assert (await client.post("/api/local-deploy/stream", json=changed, headers={"X-Platform-Actor": "alice"})).status_code == 409
            assert (await client.post("/api/local-deploy/stream", json=changed, headers={"X-Platform-Actor": "bob"})).status_code == 404

        assert effects.read_text().splitlines() == ["executed"]
        rows = [json.loads(line) for line in (configured / "activity.jsonl").read_text().splitlines()]
        assert len(rows) == 1 and rows[0]["PK"] == "ACTIVITY"
        assert state["events"][-1]["record"]["activity_id"] == rows[0]["activity_id"]
        reopened = local_runs.RunManager(from_dsn(f"sqlite://{configured}/runs.db"))
        assert reopened.snapshot(request_id, "alice")["status"] == "succeeded"

    asyncio.run(scenario())


def test_worker_loss_is_unknown_and_never_dispatches_same_id_again(configured):
    async def scenario():
        manager = local_runs.configured_manager()
        started = asyncio.Event()
        dispatches = 0

        async def events():
            nonlocal dispatches
            dispatches += 1
            started.set()
            await asyncio.sleep(3600)
            yield {"type": "done", "ok": True}

        req = {"model": "local-qwen", "instruction": "work"}
        manager.start("one", "alice", req, events)
        await started.wait()
        # Another process cannot distinguish a hard crash from an unreachable worker.
        reopened = local_runs.RunManager(from_dsn(f"sqlite://{configured}/runs.db"))
        assert reopened.snapshot("one", "alice")["status"] == "unknown"
        reopened.start("one", "alice", req, events)
        assert not reopened.tasks
        task = manager.tasks["one"]
        task.cancel()
        await task
        assert manager.snapshot("one", "alice")["status"] == "unknown"
        manager.start("one", "alice", req, events)
        assert dispatches == 1
        observed = [event async for event in manager.observe("one", "alice")]
        assert observed[-1]["state"] == "unknown"
        assert all(event["type"] != "done" for event in observed)

    asyncio.run(scenario())


def test_unavailable_acceptance_store_prevents_dispatch(configured, monkeypatch):
    called = []
    manager = local_runs.configured_manager()

    def fail(*args):
        raise OSError("disk unavailable")

    monkeypatch.setattr(manager.store, "claim", fail)
    monkeypatch.setattr(api, "route_deploy_stream", lambda *a, **kw: called.append(True))
    with TestClient(api.app) as client:
        response = client.post("/api/local-deploy/stream", json={"instruction": "work", "request_id": str(uuid4())},
                               headers={"X-Platform-Actor": "alice"})
    assert response.status_code == 503 and not called and not manager.tasks


@pytest.mark.parametrize("persist_unknown", [True, False])
def test_failed_final_write_cannot_leak_a_success(configured, monkeypatch, persist_unknown):
    async def scenario():
        manager = local_runs.configured_manager()
        real_append = manager.store.append

        def append(kind, key, state):
            if state["status"] == "succeeded" or not persist_unknown:
                raise OSError("disk unavailable")
            real_append(kind, key, state)

        async def events():
            yield {"type": "done", "ok": True, "summary": "Effect finished"}

        monkeypatch.setattr(manager.store, "append", append)
        manager.start("one", "alice", {"model": "local-qwen"}, events)
        await manager.tasks["one"]
        assert manager.snapshot("one", "alice")["status"] == "unknown"
        observed = [event async for event in manager.observe("one", "alice")]
        assert observed[-1]["state"] == "unknown"
        assert all(event["type"] != "done" for event in observed)

    asyncio.run(scenario())


def test_managed_stream_keeps_real_pydantic_ai_scopes_in_one_task(configured):
    from pydantic_ai import Agent
    from pydantic_ai.models.test import TestModel

    def factory(provider="onprem"):
        return Agent(TestModel(call_tools=[]))

    api.app.dependency_overrides[api.get_deployer_factory] = lambda: factory
    try:
        with TestClient(api.app) as client:
            request_id = str(uuid4())
            response = client.post("/api/local-deploy/stream", json={"instruction": "Explain", "request_id": request_id},
                                   headers={"X-Platform-Actor": "alice"})
            frames = [json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: ")]
            assert response.status_code == 200
            assert frames[-1]["type"] == "done", frames
            # No tools were called, so there is no successful deployment evidence.
            assert frames[-1]["ok"] is False
            snapshot = client.get(f"/api/local-deploy/runs/{request_id}", headers={"X-Platform-Actor": "alice"})
            assert snapshot.json()["status"] == "failed"
            assert [e["seq"] for e in frames] == list(range(1, len(frames) + 1))
    finally:
        api.app.dependency_overrides.pop(api.get_deployer_factory, None)
