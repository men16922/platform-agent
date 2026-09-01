"""On-Prem incident store — offline record of Day-2 remediations for the dashboard.

AWS persists incidents to a DynamoDB incident-history table that the dashboard's
Incidents timeline reads; on-prem is fully offline, so the shared executor's
DynamoDB write is a no-op there. This module gives the on-prem PATH B webhook a
file-backed incident record (append-only JSONL), exposed over HTTP so the
dashboard can merge on-prem incidents into its timeline exactly as it merges the
on-prem pending approvals — the same hybrid pattern, no file paths in the UI.

Records use the dashboard's Incident field names (incident_id, alarm_name,
provider, severity, mode, root_cause, runbook_id, resolved, executed_actions,
created_at) so the dashboard maps them without translation.
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.agents.ai import state_store

_DEFAULT_STORE = "~/.platform-agent/incidents.jsonl"


def _store_path() -> Path:
    return Path(os.getenv("PLATFORM_INCIDENT_FILE") or _DEFAULT_STORE).expanduser()


def record_incident(
    *,
    # ⚠️ `str | None`, not `str` — corrected 2026-09-01 to match what this function
    # already does. Every one of these five is read below as `x or "<default>"`,
    # so the body has always accepted `None`; the signature said otherwise and
    # `onprem_webhook_api._record_incident` has always passed `.get()` results
    # into it (ten `arg-type` errors, all from that one caller).
    #
    # The pipeline result always *has* these keys — but their values are
    # themselves `.get()` results, and `incident = detector_out.get(
    # "normalized_incident") or {}` is the pipeline's own statement that the
    # normalised incident can be absent. When it is, `service` is `None` and
    # arrives here as `alarm_name`.
    #
    # ⚠️ The defaults are policy, not tidying: a missing severity becomes **P3**
    # and a missing mode becomes **MANUAL** — the safe end of both axes. That is
    # deliberate (cf. "analyzer 폴백 severity는 정책") and is why the fix is to
    # tell the truth in the signature rather than to reject `None` at the door,
    # which would turn a degraded incident into no incident at all.
    severity: str | None,
    alarm_name: str | None,
    root_cause: str | None,
    runbook_id: str | None,
    remediation_mode: str | None,
    resolved: bool,
    executed_actions: list[str] | None = None,
    incident_id: str | None = None,
    confidence: float | None = None,
    trace_id: str | None = None,
    triggered_at: str | None = None,
) -> dict[str, Any]:
    """Append one on-prem incident (dashboard Incident shape); returns the record."""
    record = {
        "PK": "INCIDENT",
        "incident_id": incident_id or f"INC-{uuid.uuid4().hex[:8].upper()}",
        "alarm_name": alarm_name or "on-prem incident",
        "provider": "onprem",
        "severity": severity or "P3",
        "mode": remediation_mode or "MANUAL",
        "root_cause": root_cause or "On-prem Day-2 incident.",
        "runbook_id": runbook_id or "generic-recovery",
        "resolved": bool(resolved),
        "executed_actions": executed_actions or [],
        # LLM analysis confidence (Qwen on-prem / Bedrock cloud) — preserved on the
        # timeline record so the dashboard incident detail can show the analysis.
        "confidence": confidence if isinstance(confidence, (int, float)) else None,
        # OTel trace id when tracing was on — lets the incident detail deep-link
        # into the span breakdown instead of the reader eyeballing timestamps.
        # None when tracing is off, and the UI then shows no link rather than a dead one.
        "trace_id": trace_id or None,
        # When we wrote this row — NOT when the problem started.
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    # When the alert actually fired, straight from the source (`startsAt`,
    # `firedDateTime`, `started_at`). Every signal adapter has captured this
    # since they were written and nothing carried it past normalisation, so a
    # record has only ever known its own write time — which makes the gap
    # between "it broke" and "we noticed" unmeasurable, and puts the incident on
    # the timeline at the moment we happened to process it. Alertmanager
    # grouping alone can separate those by minutes; a replayed backlog, by more.
    #
    # Absent rather than empty when unknown, the same rule tenancy follows here:
    # a row from a source that never reported a fire time must not be readable
    # as "fired at the epoch", which is what a defaulted value would mean.
    if triggered_at:
        record["triggered_at"] = triggered_at
    # When the remediation finished. The webhook records the incident directly
    # after the executor returns, so the write moment is the resolution moment —
    # for the rows that were actually resolved. On-prem never wrote this field at
    # all, which is the mirror image of the cloud writer's bug: there the field
    # was always present and always equal to `created_at`, here it was always
    # missing. Either way time-to-resolve came out as zero or as nothing.
    #
    # Omitted, not defaulted, when unresolved — a P2 parked on the approval gate
    # is not an incident resolved the instant it was filed.
    if resolved:
        record["resolved_at"] = record["created_at"]
    sql = state_store.configured_store()
    if sql is not None:
        # Opt-in SQL state store (PLATFORM_STATE_DSN) — replica-shareable.
        sql.append("INCIDENT", record["incident_id"], record)
        return record
    store = _store_path()
    store.parent.mkdir(parents=True, exist_ok=True)
    with store.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, default=str) + "\n")
    return record


def list_incidents(limit: int = 100) -> list[dict[str, Any]]:
    """Recorded on-prem incidents, newest first (up to ``limit``)."""
    sql = state_store.configured_store()
    if sql is not None:
        rows = [r for r in sql.rows("INCIDENT") if r.get("PK") == "INCIDENT"]
        rows.sort(key=lambda r: str(r.get("created_at", "")), reverse=True)
        return rows[:limit]
    store = _store_path()
    if not store.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in store.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if row.get("PK") == "INCIDENT":
            rows.append(row)
    rows.sort(key=lambda r: str(r.get("created_at", "")), reverse=True)
    return rows[:limit]
