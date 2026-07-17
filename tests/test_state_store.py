"""Opt-in SQL state store (roadmap ④) — offline via stdlib sqlite3.

Pins the seam's contract: DSN unset keeps JSONL byte-for-byte; DSN set routes
the approval/incident stores through SQL with identical append-only,
latest-row-per-key semantics (so /approve replay and dashboard reads behave
the same on either backend).
"""

from __future__ import annotations

import pytest

from src.agents.ai import onprem_approvals as approvals
from src.agents.ai import onprem_incidents as incidents
from src.agents.ai.state_store import configured_store, from_dsn


@pytest.fixture()
def sqlite_dsn(tmp_path, monkeypatch):
    dsn = f"sqlite://{tmp_path}/state.db"
    monkeypatch.setenv("PLATFORM_STATE_DSN", dsn)
    return dsn


def test_configured_store_defaults_to_none(monkeypatch):
    monkeypatch.delenv("PLATFORM_STATE_DSN", raising=False)
    assert configured_store() is None  # JSONL path stays the default


def test_append_only_latest_wins_semantics(tmp_path):
    store = from_dsn(f"sqlite://{tmp_path}/s.db")
    store.append("APPROVAL", "APR-1", {"approval_id": "APR-1", "status": "pending"})
    store.append("APPROVAL", "APR-1", {"approval_id": "APR-1", "status": "approved"})
    store.append("INCIDENT", "INC-1", {"incident_id": "INC-1"})

    rows = store.rows("APPROVAL")
    assert [r["status"] for r in rows] == ["pending", "approved"]  # append order kept
    assert store.rows("INCIDENT") == [{"incident_id": "INC-1"}]  # kinds isolated


def test_approvals_route_through_sql_store(sqlite_dsn):
    rec = approvals.create_pending({"decision": "x"}, {"service": "svc", "severity": "P2"})
    assert approvals.get(rec["approval_id"])["status"] == "pending"
    assert [p["approval_id"] for p in approvals.list_pending()] == [rec["approval_id"]]

    resolved = approvals.resolve(rec["approval_id"], "approved")
    assert resolved["status"] == "approved"
    assert approvals.list_pending() == []  # latest row wins, same as JSONL
    assert approvals.resolve(rec["approval_id"], "approved") is None  # already resolved


def test_incidents_route_through_sql_store(sqlite_dsn):
    rec = incidents.record_incident(
        severity="P2",
        alarm_name="svc",
        root_cause="rc",
        runbook_id="rb",
        remediation_mode="APPROVE",
        resolved=True,
    )
    listed = incidents.list_incidents()
    assert [i["incident_id"] for i in listed] == [rec["incident_id"]]


def test_sql_and_jsonl_do_not_cross_contaminate(tmp_path, monkeypatch):
    # With the DSN set, nothing lands in the JSONL file the env still points at.
    jsonl = tmp_path / "approvals.jsonl"
    monkeypatch.setenv("PLATFORM_APPROVALS_FILE", str(jsonl))
    monkeypatch.setenv("PLATFORM_STATE_DSN", f"sqlite://{tmp_path}/s.db")
    approvals.create_pending({"d": 1}, {"service": "svc"})
    assert not jsonl.exists()

    # And with the DSN cleared, reads come from JSONL again (empty here).
    monkeypatch.delenv("PLATFORM_STATE_DSN")
    assert approvals.list_pending() == []
