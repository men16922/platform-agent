"""
AWS signal normalization helpers.
"""

from __future__ import annotations

from typing import Any

from src.agents.adapters.base import SignalAdapter
from src.agents.models import AlarmContext, NormalizedIncident


class AwsCloudWatchSignalAdapter(SignalAdapter):
    provider = "aws"

    def normalise(self, event: dict[str, Any]) -> NormalizedIncident:
        detail = event.get("detail", {})
        metric = (
            (((detail.get("configuration", {}) or {}).get("metrics") or [{}])[0].get("metricStat") or {})
            .get("metric", {})
        )
        alarm = AlarmContext(
            alarm_name=detail.get("alarmName", "unknown-alarm"),
            alarm_arn=(event.get("resources") or [""])[0],
            state=(detail.get("state") or {}).get("value", "ALARM"),
            reason=(detail.get("state") or {}).get("reason", ""),
            metric_name=metric.get("name", "unknown-metric"),
            namespace=metric.get("namespace", "AWS/Unknown"),
            dimensions={dim["name"]: dim["value"] for dim in metric.get("dimensions", []) if "name" in dim and "value" in dim},
        )
        return self.from_alarm_context(alarm, source_event=event)

    def from_alarm_context(
        self,
        alarm: AlarmContext,
        *,
        observations: dict[str, Any] | None = None,
        severity_hint: str | None = None,
        source_event: dict[str, Any] | None = None,
    ) -> NormalizedIncident:
        return NormalizedIncident(
            provider="aws",
            service=_infer_service(alarm),
            resource_type=_infer_resource_type(alarm),
            resource_id=_infer_resource_id(alarm),
            signal_type=_infer_signal_type(alarm),
            severity_hint=severity_hint,
            observations=observations or {},
            recommended_capabilities=_recommended_capabilities(alarm),
            source_metadata={
                "alarm_name": alarm.alarm_name,
                "alarm_arn": alarm.alarm_arn,
                "namespace": alarm.namespace,
                "metric_name": alarm.metric_name,
                "dimensions": alarm.dimensions,
                "source_event": source_event or {},
            },
            triggered_at=alarm.triggered_at,
        )


def _infer_service(alarm: AlarmContext) -> str:
    dimensions = alarm.dimensions

    pod_name = dimensions.get("PodName", "")
    if pod_name:
        return _trim_k8s_workload_name(pod_name)

    function_name = dimensions.get("FunctionName", "")
    if function_name:
        return function_name

    db_name = dimensions.get("DBInstanceIdentifier", "")
    if db_name:
        return db_name

    cluster_name = dimensions.get("ClusterName", "")
    if cluster_name:
        return cluster_name

    return alarm.alarm_name


def _infer_resource_type(alarm: AlarmContext) -> str:
    dimensions = alarm.dimensions
    namespace = alarm.namespace.upper()

    if "PODNAME" in {key.upper() for key in dimensions} or "AWS/EKS" in namespace:
        return "kubernetes-workload"
    if "FUNCTIONNAME" in {key.upper() for key in dimensions} or "AWS/LAMBDA" in namespace:
        return "lambda-function"
    if "DBINSTANCEIDENTIFIER" in {key.upper() for key in dimensions} or "AWS/RDS" in namespace:
        return "database-instance"
    if "CONSUMERGROUP" in {key.upper() for key in dimensions} or "AWS/KAFKA" in namespace or "AWS/MSK" in namespace:
        return "streaming-consumer"
    return "cloud-resource"


def _infer_resource_id(alarm: AlarmContext) -> str:
    dimensions = alarm.dimensions
    for key in [
        "PodName",
        "FunctionName",
        "DBInstanceIdentifier",
        "ConsumerGroup",
        "ClusterName",
    ]:
        value = dimensions.get(key)
        if value:
            return value
    return alarm.alarm_name


def _infer_signal_type(alarm: AlarmContext) -> str:
    metric = alarm.metric_name.lower()
    reason = alarm.reason.lower()

    if any(token in metric for token in ["latency", "duration", "p99"]):
        return "latency"
    if any(token in metric for token in ["cpu", "memory", "utilization", "throttle", "concurrency"]):
        return "capacity"
    if any(token in metric for token in ["error", "restart", "oom", "lag"]) or "error" in reason:
        return "reliability"
    return "availability"


def _recommended_capabilities(alarm: AlarmContext) -> list[str]:
    resource_type = _infer_resource_type(alarm)
    metric = alarm.metric_name.lower()
    reason = alarm.reason.lower()

    if resource_type == "kubernetes-workload":
        return ["restart_workload", "scale_out", "open_change_request"]
    if resource_type == "lambda-function":
        if "throttle" in metric or "throttle" in reason:
            return ["increase_function_concurrency", "open_change_request"]
        return ["open_change_request"]
    if resource_type == "database-instance":
        return ["scale_database_read", "open_change_request"]
    if resource_type == "streaming-consumer":
        return ["scale_out_workers", "rebalance_consumer", "open_change_request"]
    return ["open_change_request"]


def _trim_k8s_workload_name(value: str) -> str:
    parts = value.split("-")
    if len(parts) >= 3 and len(parts[-1]) <= 10:
        parts = parts[:-1]
    if len(parts) >= 2 and any(char.isdigit() for char in parts[-1]):
        parts = parts[:-1]
    return "-".join(parts) or value
