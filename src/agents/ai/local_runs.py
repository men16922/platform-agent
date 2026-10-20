"""Request-bound local executions, independent of an SSE observer's lifetime.

Uses the existing append-only SQL store. Claims are durable before dispatch;
there is deliberately no lease takeover or automatic restart of an unknown run.
The router remains a trusted loopback service, not a tenant authentication edge.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import time
import uuid
from collections.abc import AsyncIterator, Callable
from contextlib import aclosing
from pathlib import Path
from typing import Any

from src.agents.ai.state_store import SQLStateStore, from_dsn

_KIND = "DEPLOY_RUN"
_TERMINAL = {"succeeded", "failed", "unknown"}


class RunConflict(ValueError):
    pass


class RunNotFound(LookupError):
    pass


class RunManager:
    def __init__(self, store: SQLStateStore):
        self.store = store
        self.instance = uuid.uuid4().hex
        self.tasks: dict[str, asyncio.Task] = {}
        self.unstored: dict[str, dict[str, Any]] = {}

    def start(self, request_id: str, actor: str, request: dict[str, Any],
              events: Callable[[], AsyncIterator[dict[str, Any]]]) -> None:
        fingerprint = hashlib.sha256(json.dumps(request, sort_keys=True).encode()).hexdigest()
        state = {"request_id": request_id, "actor": actor, "request": request,
                 "fingerprint": fingerprint, "instance": self.instance, "status": "running",
                 "updated_at": time.time(), "events": [
                     {"seq": 1, "type": "ready", "request_id": request_id, "agent": request["model"],
                      **({"read_only": request["read_only"]} if type(request.get("read_only")) is bool else {})}
                 ]}
        if not self.store.claim(_KIND, request_id, state):
            existing = self.store.latest(_KIND, request_id)
            if not existing or existing.get("actor") != actor:
                raise RunNotFound(request_id)
            if existing.get("fingerprint") != fingerprint:
                raise RunConflict("This request ID is already bound to different input.")
            return  # A replay observes the original, including unknown results.
        task = asyncio.create_task(self._execute(state, events))
        self.tasks[request_id] = task
        task.add_done_callback(lambda _: self.tasks.pop(request_id, None))

    async def _execute(self, state: dict[str, Any], events: Callable) -> None:
        request_id = state["request_id"]
        completed = False
        try:
            async with aclosing(events()) as stream:
                async for event in stream:
                    state["events"].append({**event, "seq": len(state["events"]) + 1,
                                            "request_id": request_id})
                    state["updated_at"] = time.time()
                    if event["type"] == "done":
                        state["status"] = "succeeded" if event.get("ok") else "failed"
                    elif event["type"] == "error":
                        state["status"] = "unknown"
                    self.store.append(_KIND, request_id, state)
                    if state["status"] in _TERMINAL:
                        completed = True
                        return
            if state["status"] not in _TERMINAL:
                raise RuntimeError("Execution ended without a final result.")
        except (Exception, asyncio.CancelledError):
            if completed:
                return  # Cleanup cannot erase a durably recorded final result.
            # A process shutdown, transport-independent worker error, or a failed
            # final write cannot prove that a previously started action failed.
            state["status"] = "unknown"
            state["events"] = [e for e in state["events"] if e["type"] != "done"]
            state["error"] = "Execution result is unconfirmed. Inspect the workload before starting another request."
            state["updated_at"] = time.time()
            try:
                self.store.append(_KIND, request_id, state)
            except Exception:
                self.unstored[request_id] = dict(state)

    def snapshot(self, request_id: str, actor: str) -> dict[str, Any]:
        state = self.unstored.get(request_id) or self.store.latest(_KIND, request_id)
        if not state or state.get("actor") != actor:
            raise RunNotFound(request_id)
        state = dict(state)
        if state["status"] == "running" and (
            state["instance"] != self.instance or request_id not in self.tasks
        ):
            state["status"] = "unknown"
            state["error"] = "The original worker is unavailable here. This request will not be re-executed."
        return {k: v for k, v in state.items() if k not in {"actor", "instance", "fingerprint"}}

    async def observe(self, request_id: str, actor: str, heartbeat: float = 15.0):
        sent = 0
        last_heartbeat = time.monotonic()
        while True:
            state = self.snapshot(request_id, actor)
            for event in state["events"]:
                if event["seq"] > sent:
                    sent = event["seq"]
                    yield event
            if state["status"] in _TERMINAL:
                if state["status"] == "unknown":
                    yield {"type": "error", "state": "unknown", "request_id": request_id,
                           "seq": sent + 1, "error": state.get("error", "Execution result is unconfirmed.")}
                return
            if time.monotonic() - last_heartbeat >= heartbeat:
                yield None
                last_heartbeat = time.monotonic()
            await asyncio.sleep(0.05)


_MANAGERS: dict[str, RunManager] = {}


def configured_manager() -> RunManager:
    dsn = os.getenv("PLATFORM_STATE_DSN", "").strip()
    if not dsn:
        activity_file = os.getenv("PLATFORM_ACTIVITY_FILE", "").strip()
        if not activity_file:
            raise RuntimeError("Durable local runs require PLATFORM_ACTIVITY_FILE or PLATFORM_STATE_DSN.")
        path = Path(activity_file).expanduser().resolve().with_suffix(".runs.sqlite3")
        path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT, 0o600)
        os.close(fd)
        dsn = f"sqlite://{path}"
    if dsn not in _MANAGERS:
        _MANAGERS[dsn] = RunManager(from_dsn(dsn))
    return _MANAGERS[dsn]
