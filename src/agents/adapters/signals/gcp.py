"""
GCP alert normalization helpers.
"""

from __future__ import annotations

from typing import Any

from src.agents.adapters.base import SignalAdapter
from src.agents.models import NormalizedIncident


class GcpMonitoringSignalAdapter(SignalAdapter):
    provider = "gcp"

    def normalise(self, event: dict[str, Any]) -> NormalizedIncident:
        incident = event.get("incident", {})
        resource = incident.get("resource", {})
        labels = resource.get("labels", {}) if isinstance(resource, dict) else {}
        metric = incident.get("metric", {}) if isinstance(incident.get("metric"), dict) else {}

        resource_type = _resource_type(resource.get("type", ""), labels)
        service = _service_name(labels, incident)
        resource_id = _resource_id(labels, incident, service)
        signal_type = _signal_type(metric.get("type", ""), incident.get("summary", ""))

        return NormalizedIncident(
            provider="gcp",
            service=service,
            resource_type=resource_type,
            resource_id=resource_id,
            signal_type=signal_type,
            severity_hint=incident.get("severity"),
            observations={
                "summary": incident.get("summary", ""),
                "url": incident.get("url", ""),
            },
            recommended_capabilities=_capabilities(resource_type, signal_type),
            source_metadata={
                "policy_name": incident.get("policy_name", ""),
                "condition_name": incident.get("condition_name", ""),
                "project_id": incident.get("scoping_project_id", ""),
                "resource_labels": labels,
                "metric_type": metric.get("type", ""),
                "source_event": event,
            },
            triggered_at=incident.get("started_at", ""),
        )


def _service_name(labels: dict[str, Any], incident: dict[str, Any]) -> str:
    for key in ("service_name", "service", "pod_name", "container_name", "revision_name", "instance_id"):
        value = labels.get(key)
        if value:
            return _trim_workload(str(value))
    return incident.get("policy_name", "gcp-incident")


def _resource_type(resource_type: str, labels: dict[str, Any]) -> str:
    lowered = resource_type.lower()
    if lowered in {"k8s_container", "k8s_pod", "k8s_node"}:
        return "kubernetes-workload"
    if lowered in {"cloud_run_revision", "cloud_function"}:
        return "serverless-service"
    if lowered in {"cloudsql_database", "cloudsql_instance"}:
        return "database-instance"
    if labels.get("subscription_id") or labels.get("consumer_group"):
        return "streaming-consumer"
    return "cloud-resource"


def _resource_id(labels: dict[str, Any], incident: dict[str, Any], service: str) -> str:
    for key in ("pod_name", "revision_name", "instance_id", "database_id", "subscription_id"):
        value = labels.get(key)
        if value:
            return str(value)
    return incident.get("resource_id") or service


def _signal_type(metric_type: str, summary: str) -> str:
    text = f"{metric_type} {summary}".lower()
    if any(token in text for token in ("latency", "duration", "response_time", "p99")):
        return "latency"
    if any(token in text for token in ("cpu", "memory", "utilization", "concurrency", "instance_count")):
        return "capacity"
    if any(token in text for token in ("error", "crash", "restart", "oom", "lag")):
        return "reliability"
    return "availability"


def _capabilities(resource_type: str, signal_type: str) -> list[str]:
    if resource_type == "kubernetes-workload":
        return ["restart_workload", "scale_out", "open_change_request"]
    if resource_type == "serverless-service":
        return ["increase_function_concurrency", "open_change_request"]
    if resource_type == "database-instance":
        return ["scale_database_read", "open_change_request"]
    if resource_type == "streaming-consumer":
        return ["scale_out_workers", "rebalance_consumer", "open_change_request"]
    if signal_type == "availability":
        return ["open_change_request"]
    return ["open_change_request"]


def _trim_workload(value: str) -> str:
    parts = value.split("-")
    if len(parts) >= 3 and len(parts[-1]) <= 10:
        parts = parts[:-1]
    if len(parts) >= 2 and any(char.isdigit() for char in parts[-1]):
        parts = parts[:-1]
    return "-".join(parts) or value
