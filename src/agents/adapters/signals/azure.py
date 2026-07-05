"""
Azure alert normalization helpers.
"""

from __future__ import annotations

from typing import Any

from src.agents.adapters.base import SignalAdapter
from src.agents.models import NormalizedIncident


class AzureMonitorSignalAdapter(SignalAdapter):
    provider = "azure"

    def normalise(self, event: dict[str, Any]) -> NormalizedIncident:
        data = event.get("data", {})
        essentials = data.get("essentials", {}) if isinstance(data, dict) else {}
        alert_context = data.get("alertContext", {}) if isinstance(data, dict) else {}
        condition = alert_context.get("condition", {}) if isinstance(alert_context, dict) else {}
        all_of = condition.get("allOf", []) if isinstance(condition, dict) else []
        first_condition = all_of[0] if all_of else {}
        dimensions = {
            dimension.get("name"): dimension.get("value")
            for dimension in first_condition.get("dimensions", [])
            if "name" in dimension and "value" in dimension
        }

        resource_type = _resource_type(
            essentials.get("targetResourceType", ""),
            first_condition.get("metricName", ""),
            dimensions,
        )
        service = _service_name(dimensions, essentials)
        resource_id = _resource_id(dimensions, essentials, service)
        signal_type = _signal_type(first_condition.get("metricName", ""), essentials.get("description", ""))

        return NormalizedIncident(
            provider="azure",
            service=service,
            resource_type=resource_type,
            resource_id=resource_id,
            signal_type=signal_type,
            severity_hint=essentials.get("severity"),
            observations={
                "description": essentials.get("description", ""),
                "monitor_condition": essentials.get("monitorCondition", ""),
                "fired_datetime": essentials.get("firedDateTime", ""),
            },
            recommended_capabilities=_capabilities(resource_type),
            source_metadata={
                "alert_rule": essentials.get("alertRule", ""),
                "target_resource_ids": essentials.get("alertTargetIDs", []),
                "signal_type": essentials.get("signalType", ""),
                "dimensions": dimensions,
                "source_event": event,
            },
            triggered_at=essentials.get("firedDateTime", ""),
        )


def _resource_type(target_resource_type: str, metric_name: str, dimensions: dict[str, Any]) -> str:
    lowered = target_resource_type.lower()
    metric_text = metric_name.lower()
    if "containerservice/managedclusters" in lowered or dimensions.get("Pod"):
        return "kubernetes-workload"
    if "web/sites" in lowered or "function" in metric_text:
        return "serverless-service"
    if "sql" in lowered or "database" in lowered:
        return "database-instance"
    if dimensions.get("ConsumerGroup"):
        return "streaming-consumer"
    return "cloud-resource"


def _service_name(dimensions: dict[str, Any], essentials: dict[str, Any]) -> str:
    for key in ("Pod", "Deployment", "App", "FunctionApp", "DatabaseName"):
        value = dimensions.get(key)
        if value:
            return _trim_workload(str(value))
    return essentials.get("alertRule", "azure-incident")


def _resource_id(dimensions: dict[str, Any], essentials: dict[str, Any], service: str) -> str:
    for key in ("Pod", "FunctionApp", "DatabaseName", "ConsumerGroup"):
        value = dimensions.get(key)
        if value:
            return str(value)
    target_ids = essentials.get("alertTargetIDs", [])
    if target_ids:
        return str(target_ids[0])
    return service


def _signal_type(metric_name: str, description: str) -> str:
    text = f"{metric_name} {description}".lower()
    if any(token in text for token in ("latency", "duration", "response", "p99")):
        return "latency"
    if any(token in text for token in ("cpu", "memory", "utilization", "concurrency", "throttle")):
        return "capacity"
    if any(token in text for token in ("error", "restart", "crash", "lag")):
        return "reliability"
    return "availability"


def _capabilities(resource_type: str) -> list[str]:
    if resource_type == "kubernetes-workload":
        return ["restart_workload", "scale_out", "open_change_request"]
    if resource_type == "serverless-service":
        return ["increase_function_concurrency", "open_change_request"]
    if resource_type == "database-instance":
        return ["scale_database_read", "open_change_request"]
    if resource_type == "streaming-consumer":
        return ["scale_out_workers", "open_change_request"]
    return ["open_change_request"]


def _trim_workload(value: str) -> str:
    parts = value.split("-")
    if len(parts) >= 3 and len(parts[-1]) <= 10:
        parts = parts[:-1]
    if len(parts) >= 2 and any(char.isdigit() for char in parts[-1]):
        parts = parts[:-1]
    return "-".join(parts) or value
