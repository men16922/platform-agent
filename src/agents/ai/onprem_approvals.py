"""On-Prem approval store — offline pending-approval gate for Day-2 P2 incidents.

AWS pauses a P2 (APPROVE) remediation on a Step Functions ``WaitForTaskToken``
and resumes it when a human clicks the Slack button; GCP/Azure use Cloud Tasks /
Service Bus callbacks. On-Prem's equivalent (ARCHITECTURE "On-Prem Approval Flow")
is this file-backed pending store + the webhook's ``/approve`` / ``/reject``
endpoints — fully offline, no Slack required for the core gate (a Slack button is
an optional front-end, deferred).

Records are append-only JSONL with a single-row lifecycle: resolving an approval
appends a new row with the same ``approval_id``; the latest row per id wins —
mirroring the deploy recorder's offline pattern. The stored ``decision`` payload
is the executor's input, so an approved incident is simply replayed through the
executor.
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.agents.ai import state_store

_DEFAULT_STORE = "~/.platform-agent/pending-approvals.jsonl"


def _store_path() -> Path:
    return Path(os.getenv("PLATFORM_APPROVALS_FILE") or _DEFAULT_STORE).expanduser()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _append(record: dict[str, Any]) -> None:
    # Opt-in SQL state store (PLATFORM_STATE_DSN) — same append-only lifecycle,
    # shared across replicas. Unset (the default) keeps the JSONL file.
    sql = state_store.configured_store()
    if sql is not None:
        sql.append("APPROVAL", record["approval_id"], record)
        return
    store = _store_path()
    store.parent.mkdir(parents=True, exist_ok=True)
    with store.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, default=str) + "\n")


def _all_rows() -> list[dict[str, Any]]:
    sql = state_store.configured_store()
    if sql is not None:
        return sql.rows("APPROVAL")
    store = _store_path()
    if not store.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in store.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def _latest_by_id() -> dict[str, dict[str, Any]]:
    """Latest row per approval_id (later-written wins for equal timestamps)."""
    latest: dict[str, dict[str, Any]] = {}
    for row in _all_rows():
        latest[row["approval_id"]] = row
    return latest


def create_pending(decision: dict[str, Any], summary: dict[str, Any]) -> dict[str, Any]:
    """Park a decision awaiting human approval; returns the pending record."""
    now = _now()
    record = {
        "PK": "APPROVAL",
        "approval_id": f"APR-{uuid.uuid4().hex[:8].upper()}",
        "status": "pending",
        "created_at": now,
        "updated_at": now,
        "service": summary.get("service"),
        "severity": summary.get("severity"),
        "runbook_id": summary.get("runbook_id"),
        "remediation_mode": summary.get("remediation_mode"),
        "actions": summary.get("actions", []),
        "decision": decision,
    }
    _append(record)
    return record


def list_pending() -> list[dict[str, Any]]:
    """All currently-pending approvals, newest first."""
    pending = [r for r in _latest_by_id().values() if r.get("status") == "pending"]
    return sorted(pending, key=lambda r: str(r.get("created_at", "")), reverse=True)


def get(approval_id: str) -> dict[str, Any] | None:
    return _latest_by_id().get(approval_id)


def resolve(
    approval_id: str, status: str, *, executor_out: dict[str, Any] | None = None
) -> dict[str, Any] | None:
    """Append a resolved (approved/rejected) row for ``approval_id``.

    Returns the updated record, or None if the id is unknown / already resolved.
    """
    current = get(approval_id)
    if current is None or current.get("status") != "pending":
        return None
    updated = {**current, "status": status, "updated_at": _now()}
    if executor_out is not None:
        updated["incident_id"] = executor_out.get("incident_id")
        updated["executed_actions"] = executor_out.get("executed_actions", [])
    _append(updated)
    return updated
