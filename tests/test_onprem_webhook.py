"""On-Prem PATH B webhook + in-process incident pipeline + approval-gate tests.

Exercises the real on-prem chain — detector (Alertmanager normalisation) →
decision (runbook + severity→mode) → executor (log-only on-prem action) — plus
the offline approval gate, while stubbing the analyzer's Bedrock call so the test
is hermetic and controls severity, and redirecting the activity + approval
stores to temp files.
"""

import pytest
from fastapi.testclient import TestClient

from src.agents.ai import onprem_incident_pipeline as pipeline_mod
from src.agents.ai.onprem_webhook_api import app

ALERTMANAGER_PAYLOAD = {
    "status": "firing",
    "groupLabels": {"alertname": "KubePodCrashLooping"},
    "commonLabels": {
        "alertname": "KubePodCrashLooping",
        "severity": "critical",
        "namespace": "payments",
        "service": "payments-api",
    },
    "commonAnnotations": {
        "summary": "Pod payments-api crash looping",
        "description": "Container restarting repeatedly (OOM)",
    },
    "alerts": [
        {
            "status": "firing",
            "labels": {
                "alertname": "KubePodCrashLooping",
                "pod": "payments-api-7d9f-abc",
                "namespace": "payments",
                "severity": "critical",
            },
            "annotations": {"summary": "Pod payments-api crash looping"},
            "startsAt": "2026-07-14T06:40:00Z",
            "generatorURL": "http://prometheus/graph",
        }
    ],
}


def _stub_analyze(severity: str):
    def _fn(detector_out, _ctx):
        return {
            "detector": detector_out,
            "root_cause": "heuristic: pod crash loop (OOM)",
            "severity": severity,
            "confidence": 0.5,
            "similar_incidents": [],
        }

    return _fn


@pytest.fixture(autouse=True)
def _isolate(monkeypatch, tmp_path):
    # Keep executor + approval + incident writes out of the real ~/.platform-agent files.
    monkeypatch.setenv("PLATFORM_ACTIVITY_FILE", str(tmp_path / "activity.jsonl"))
    monkeypatch.setenv("PLATFORM_APPROVALS_FILE", str(tmp_path / "approvals.jsonl"))
    monkeypatch.setenv("PLATFORM_INCIDENT_FILE", str(tmp_path / "incidents.jsonl"))
    # Default: P1 → AUTO. Individual tests re-patch for P2/P3.
    monkeypatch.setattr(pipeline_mod, "_analyze", _stub_analyze("P1"))


@pytest.fixture
def client():
    return TestClient(app)


# ------------------------------------------------------------------
# Pipeline core
# ------------------------------------------------------------------

def test_run_incident_pipeline_normalises_onprem_alertmanager():
    result = pipeline_mod.run_incident_pipeline(ALERTMANAGER_PAYLOAD)

    assert result["provider"] == "onprem"
    assert result["service"]
    assert result["resource_type"] == "kubernetes-workload"
    assert result["severity"] == "P1"
    assert result["runbook_id"]
    assert result["remediation_mode"] == "AUTO"
    assert result["incident_id"]
    assert set(result["stages"]) == {"detector", "analyzer", "decision", "executor"}


def test_execute_false_skips_executor():
    result = pipeline_mod.run_incident_pipeline(ALERTMANAGER_PAYLOAD, execute=False)

    assert result["incident_id"] is None
    assert result["executed_actions"] == []
    assert result["stages"]["executor"] is None
    # Decision is still available for later replay on approval.
    assert result["stages"]["decision"]["remediation_mode"] == "AUTO"


# ------------------------------------------------------------------
# Guardian severity → mode gating at the webhook
# ------------------------------------------------------------------

def test_p1_auto_executes_immediately(client):
    resp = client.post("/webhook/alertmanager", json=ALERTMANAGER_PAYLOAD)

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "executed"
    assert body["provider"] == "onprem"
    assert body["incident_id"]
    assert "stages" not in body
    assert client.get("/pending").json()["count"] == 0


def test_p2_approve_parks_then_approves(client, monkeypatch):
    monkeypatch.setattr(pipeline_mod, "_analyze", _stub_analyze("P2"))

    resp = client.post("/webhook/alertmanager", json=ALERTMANAGER_PAYLOAD)
    body = resp.json()
    assert body["status"] == "pending_approval"
    assert body["remediation_mode"] == "APPROVE"
    approval_id = body["approval_id"]
    assert approval_id
    assert body["incident_id"] is None  # not executed yet

    listing = client.get("/pending").json()
    assert listing["count"] == 1
    assert listing["pending"][0]["approval_id"] == approval_id

    approved = client.post(f"/approve/{approval_id}").json()
    assert approved["status"] == "approved"
    assert approved["incident_id"]
    assert approved["executed_actions"]

    assert client.get("/pending").json()["count"] == 0


def test_p2_reject_does_not_execute(client, monkeypatch):
    monkeypatch.setattr(pipeline_mod, "_analyze", _stub_analyze("P2"))

    approval_id = client.post("/webhook/alertmanager", json=ALERTMANAGER_PAYLOAD).json()["approval_id"]

    rejected = client.post(f"/reject/{approval_id}").json()
    assert rejected["status"] == "rejected"
    assert rejected["incident_id"] is None
    assert client.get("/pending").json()["count"] == 0

    # A resolved approval cannot be approved again.
    assert client.post(f"/approve/{approval_id}").status_code == 409


def test_p3_manual_notifies_without_execution(client, monkeypatch):
    monkeypatch.setattr(pipeline_mod, "_analyze", _stub_analyze("P3"))

    body = client.post("/webhook/alertmanager", json=ALERTMANAGER_PAYLOAD).json()
    assert body["status"] == "notified"
    assert body["remediation_mode"] == "MANUAL"
    assert body["incident_id"] is None
    assert client.get("/pending").json()["count"] == 0


def test_approve_unknown_returns_404(client):
    assert client.post("/approve/APR-DEADBEEF").status_code == 404


# ------------------------------------------------------------------
# On-prem incident timeline store (dashboard hybrid)
# ------------------------------------------------------------------

def test_p1_auto_records_resolved_incident(client):
    assert client.get("/incidents").json()["count"] == 0
    client.post("/webhook/alertmanager", json=ALERTMANAGER_PAYLOAD)

    listing = client.get("/incidents").json()
    assert listing["count"] == 1
    inc = listing["incidents"][0]
    assert inc["provider"] == "onprem"
    assert inc["severity"] == "P1"
    assert inc["resolved"] is True
    assert inc["incident_id"]
    assert inc["alarm_name"]  # service


def test_p3_manual_records_unresolved_incident(client, monkeypatch):
    monkeypatch.setattr(pipeline_mod, "_analyze", _stub_analyze("P3"))
    client.post("/webhook/alertmanager", json=ALERTMANAGER_PAYLOAD)

    inc = client.get("/incidents").json()["incidents"][0]
    assert inc["severity"] == "P3"
    assert inc["resolved"] is False


def test_p2_incident_recorded_only_after_approval(client, monkeypatch):
    monkeypatch.setattr(pipeline_mod, "_analyze", _stub_analyze("P2"))
    approval_id = client.post("/webhook/alertmanager", json=ALERTMANAGER_PAYLOAD).json()["approval_id"]
    # Parked, not yet on the timeline.
    assert client.get("/incidents").json()["count"] == 0

    client.post(f"/approve/{approval_id}")
    listing = client.get("/incidents").json()
    assert listing["count"] == 1
    assert listing["incidents"][0]["resolved"] is True


# ------------------------------------------------------------------
# Input validation + health
# ------------------------------------------------------------------

def test_generic_incident_webhook(client):
    assert client.post("/webhook/incident", json=ALERTMANAGER_PAYLOAD).json()["provider"] == "onprem"


def test_alertmanager_webhook_rejects_non_alertmanager_payload(client):
    assert client.post("/webhook/alertmanager", json={"unrelated": "payload"}).status_code == 400


def test_generic_incident_webhook_rejects_empty_payload(client):
    assert client.post("/webhook/incident", json={}).status_code == 400


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "service": "onprem-webhook"}
