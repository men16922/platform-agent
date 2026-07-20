"""
On-prem alert normalization helpers.
"""

from __future__ import annotations

from typing import Any

from src.agents.adapters.base import SignalAdapter
from src.agents.models import NormalizedIncident


class OnPremAlertmanagerSignalAdapter(SignalAdapter):
    provider = "onprem"

    def normalise(self, event: dict[str, Any]) -> NormalizedIncident:
        common_labels = event.get("commonLabels", {}) if isinstance(event, dict) else {}
        common_annotations = event.get("commonAnnotations", {}) if isinstance(event, dict) else {}
        alerts = event.get("alerts", []) if isinstance(event, dict) else []
        first_alert = alerts[0] if alerts else {}
        labels = first_alert.get("labels", {}) if isinstance(first_alert, dict) else {}
        merged_labels = {**common_labels, **labels}
        # Alertmanager only lifts annotations into commonAnnotations when every
        # grouped alert shares the same value; a single alert (or varying ones)
        # keeps them per-alert. Fall back to the first alert so the summary and
        # description — the richest analysis signal — are never dropped.
        first_annotations = first_alert.get("annotations", {}) if isinstance(first_alert, dict) else {}
        annotations = {**first_annotations, **common_annotations}

        resource_type = _resource_type(merged_labels)
        service = merged_labels.get("service") or merged_labels.get("job") or merged_labels.get("pod") or "onprem-incident"
        resource_id = merged_labels.get("pod") or merged_labels.get("instance") or merged_labels.get("service") or service
        signal_type = _signal_type(merged_labels.get("alertname", ""), annotations.get("summary", ""))

        return NormalizedIncident(
            provider="onprem",
            service=_trim_workload(str(service)),
            resource_type=resource_type,
            resource_id=str(resource_id),
            signal_type=signal_type,
            severity_hint=merged_labels.get("severity"),
            observations={
                "summary": annotations.get("summary", ""),
                "description": annotations.get("description", ""),
                "status": event.get("status", ""),
            },
            recommended_capabilities=_capabilities(resource_type),
            source_metadata={
                "alertname": merged_labels.get("alertname", ""),
                "labels": merged_labels,
                "generator_url": first_alert.get("generatorURL", ""),
                "source_event": event,
            },
            triggered_at=first_alert.get("startsAt", ""),
        )


def _resource_type(labels: dict[str, Any]) -> str:
    if labels.get("pod") or labels.get("namespace"):
        return "kubernetes-workload"
    if labels.get("service_type") == "database" or labels.get("db_instance"):
        return "database-instance"
    if labels.get("consumer_group") or labels.get("topic"):
        return "streaming-consumer"
    return "cloud-resource"


def _signal_type(alertname: str, summary: str) -> str:
    text = f"{alertname} {summary}".lower()
    if any(token in text for token in ("latency", "duration", "response", "slow")):
        return "latency"
    if any(token in text for token in ("cpu", "memory", "saturation", "capacity")):
        return "capacity"
    if any(token in text for token in ("down", "error", "restart", "crash", "lag")):
        return "reliability"
    return "availability"


def _capabilities(resource_type: str) -> list[str]:
    if resource_type == "kubernetes-workload":
        return ["restart_workload", "scale_out", "rollback_release", "open_change_request"]
    if resource_type == "database-instance":
        return ["scale_database_read", "open_change_request"]
    if resource_type == "streaming-consumer":
        return ["scale_out_workers", "rebalance_consumer", "open_change_request"]
    return ["open_change_request"]


def _trim_workload(value: str) -> str:
    parts = value.split("-")
    if len(parts) >= 3 and len(parts[-1]) <= 10:
        parts = parts[:-1]
    if len(parts) >= 2 and any(char.isdigit() for char in parts[-1]):
        parts = parts[:-1]
    return "-".join(parts) or value
