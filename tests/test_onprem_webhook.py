"""On-Prem PATH B webhook + in-process incident pipeline tests.

Exercises the real on-prem chain — detector (Alertmanager normalisation) →
decision (runbook selection) → executor (log-only on-prem action + activity) —
while stubbing the analyzer's Bedrock call so the test is hermetic and fast, and
redirecting the executor's activity write to a temp file.
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


@pytest.fixture(autouse=True)
def _isolate(monkeypatch, tmp_path):
    # Keep the executor's activity write out of the real ~/.platform-agent file.
    monkeypatch.setenv("PLATFORM_ACTIVITY_FILE", str(tmp_path / "activity.jsonl"))

    # Force the analyzer's heuristic path without a real Bedrock network call.
    def _stub_analyze(detector_out, _ctx):
        return {
            "detector": detector_out,
            "root_cause": "heuristic: pod crash loop (OOM)",
            "severity": "P1",
            "confidence": 0.5,
            "similar_incidents": [],
        }

    monkeypatch.setattr(pipeline_mod, "_analyze", _stub_analyze)


def test_run_incident_pipeline_normalises_onprem_alertmanager():
    result = pipeline_mod.run_incident_pipeline(ALERTMANAGER_PAYLOAD)

    assert result["provider"] == "onprem"
    assert result["service"]  # normalised from labels
    assert result["resource_type"] == "kubernetes-workload"
    assert result["severity"] == "P1"
    assert result["runbook_id"]
    assert result["remediation_mode"] in {"AUTO", "APPROVE", "MANUAL"}
    assert result["incident_id"]
    # Full per-stage trace is available for observability.
    assert set(result["stages"]) == {"detector", "analyzer", "decision", "executor"}


def test_alertmanager_webhook_endpoint_returns_compact_summary():
    client = TestClient(app)
    resp = client.post("/webhook/alertmanager", json=ALERTMANAGER_PAYLOAD)

    assert resp.status_code == 200
    body = resp.json()
    assert body["provider"] == "onprem"
    assert body["severity"] == "P1"
    assert body["incident_id"]
    # Webhook returns the compact summary, not the verbose per-stage payloads.
    assert "stages" not in body


def test_generic_incident_webhook_endpoint():
    client = TestClient(app)
    resp = client.post("/webhook/incident", json=ALERTMANAGER_PAYLOAD)

    assert resp.status_code == 200
    assert resp.json()["provider"] == "onprem"


def test_alertmanager_webhook_rejects_non_alertmanager_payload():
    client = TestClient(app)
    resp = client.post("/webhook/alertmanager", json={"unrelated": "payload"})

    assert resp.status_code == 400


def test_generic_incident_webhook_rejects_empty_payload():
    client = TestClient(app)
    resp = client.post("/webhook/incident", json={})

    assert resp.status_code == 400


def test_health():
    client = TestClient(app)
    resp = client.get("/health")

    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "service": "onprem-webhook"}
