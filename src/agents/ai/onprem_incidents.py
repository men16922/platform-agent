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
    severity: str,
    alarm_name: str,
    root_cause: str,
    runbook_id: str,
    remediation_mode: str,
    resolved: bool,
    executed_actions: list[str] | None = None,
    incident_id: str | None = None,
    confidence: float | None = None,
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
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
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
