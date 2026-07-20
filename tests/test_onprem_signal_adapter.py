"""Guards for the on-prem Alertmanager signal adapter.

Alertmanager only promotes annotations to ``commonAnnotations`` when every
grouped alert shares the value; a single alert keeps them per-alert. The adapter
must capture the per-alert ``annotations`` so the summary/description — the
richest analysis signal (e.g. "OOMKilled") — reaches the analyzer prompt.
"""

from __future__ import annotations

from src.agents.adapters.signals.onprem import OnPremAlertmanagerSignalAdapter


def test_per_alert_annotations_are_captured():
    event = {
        "status": "firing",
        "alerts": [
            {
                "labels": {"alertname": "PodCrashLoopBackOff", "namespace": "orders", "pod": "orders-api-abc"},
                "annotations": {
                    "summary": "orders-api restarting",
                    "description": "OOMKilled, memory limit 256Mi exceeded",
                },
                "startsAt": "2026-07-21T02:40:00Z",
            }
        ],
    }

    incident = OnPremAlertmanagerSignalAdapter().normalise(event)

    assert incident.observations["summary"] == "orders-api restarting"
    assert "OOMKilled" in incident.observations["description"]


def test_common_annotations_take_precedence():
    event = {
        "status": "firing",
        "commonAnnotations": {"description": "grouped summary wins"},
        "alerts": [
            {
                "labels": {"alertname": "X", "pod": "p-1"},
                "annotations": {"summary": "per-alert summary", "description": "per-alert desc"},
            }
        ],
    }

    incident = OnPremAlertmanagerSignalAdapter().normalise(event)

    # commonAnnotations overrides the same key; per-alert fills the rest.
    assert incident.observations["description"] == "grouped summary wins"
    assert incident.observations["summary"] == "per-alert summary"
