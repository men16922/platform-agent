"""
Detector Agent — Lambda handler.

Triggered by:
  EventBridge rule (CloudWatch Alarm state change → ALARM)

Responsibilities:
  1. Parse the alarm context from the EventBridge event
  2. Query CloudWatch Logs Insights for recent error patterns
  3. Fetch related X-Ray trace IDs
  4. Return DetectorOutput for the Analyzer Agent (via Step Functions)
"""

from __future__ import annotations

import json
import os
import time
from typing import Any

import boto3
import structlog

from src.agents.adapters.registry import get_signal_adapter
from src.agents.models import AlarmContext, DetectorOutput, NormalizedIncident

logger = structlog.get_logger(__name__)

_LOGS_CLIENT   = boto3.client("logs",    region_name=os.getenv("AWS_REGION", "ap-northeast-2"))
_XRAY_CLIENT   = boto3.client("xray",   region_name=os.getenv("AWS_REGION", "ap-northeast-2"))
_CW_CLIENT     = boto3.client("cloudwatch", region_name=os.getenv("AWS_REGION", "ap-northeast-2"))

# How far back to scan logs (seconds)
_LOG_LOOKBACK_SEC = int(os.getenv("LOG_LOOKBACK_SEC", "300"))


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """
    Entry point.

    Supports multiple cloud providers via AdapterRegistry.

    AWS event shape (from EventBridge Alarm state change):
    {
        "source": "aws.cloudwatch",
        "detail-type": "CloudWatch Alarm State Change",
        "detail": { "alarmName": "...", "state": {...}, "configuration": {...} },
        "resources": ["arn:aws:cloudwatch:..."]
    }

    Non-AWS events (GCP, Azure, on-prem) are normalised directly via the
    appropriate SignalAdapter; AWS-specific data collection is skipped.
    """
    log = logger.bind(event_id=event.get("id", "unknown"))
    log.info("detector.start")

    provider = _detect_provider(event)
    log = log.bind(provider=provider)

    if provider == "aws":
        alarm = _parse_alarm(event)
        log = log.bind(alarm_name=alarm.alarm_name, alarm_state=alarm.state)
        log_results = _query_logs_insights(alarm)
        log.info("detector.logs_done", result_count=len(log_results))
        trace_ids = _fetch_xray_traces(alarm)
        log.info("detector.xray_done", trace_count=len(trace_ids))
        related_metrics = _fetch_related_metrics(alarm)
        normalized_incident = _normalise_incident(
            alarm,
            log_results=log_results,
            trace_ids=trace_ids,
            related_metrics=related_metrics,
            source_event=event,
        )
    else:
        # Non-AWS: use the provider's SignalAdapter directly; skip AWS data collection.
        normalized_incident = get_signal_adapter(provider).normalise(event)
        alarm = _synthetic_alarm(normalized_incident, provider)
        log_results, trace_ids, related_metrics = [], [], {}
        log.info(
            "detector.non_aws.normalised",
            service=normalized_incident.service,
            resource_type=normalized_incident.resource_type,
        )

    output = DetectorOutput(
        alarm=alarm,
        log_insights_results=log_results,
        xray_trace_ids=trace_ids,
        related_metrics=related_metrics,
        normalized_incident=normalized_incident,
    )

    log.info("detector.done")
    return _serialise(output)


# ------------------------------------------------------------------
# Provider detection
# ------------------------------------------------------------------

def _detect_provider(event: dict[str, Any]) -> str:
    """
    Infer the cloud provider from the inbound event shape.

    AWS:     event.source starts with "aws."
    GCP:     event has an "incident" dict (Cloud Monitoring alert payload)
    Azure:   event.data.essentials exists (Azure Monitor Common Alert Schema)
    on-prem: event has "alerts" or "groupLabels" (Alertmanager webhook)
    Default: "aws" (safe fallback for EventBridge events without source field)
    """
    source = event.get("source", "")
    if source.startswith("aws."):
        return "aws"
    if "incident" in event and isinstance(event.get("incident"), dict):
        return "gcp"
    if "data" in event and "essentials" in (event.get("data") or {}):
        return "azure"
    if "alerts" in event or "groupLabels" in event:
        return "onprem"
    return "aws"


def _synthetic_alarm(incident: NormalizedIncident, provider: str) -> AlarmContext:
    """
    Build a minimal AlarmContext from a NormalizedIncident for non-AWS events.
    Keeps the downstream pipeline (Analyzer, Decision) working unchanged.
    """
    return AlarmContext(
        alarm_name=incident.service or "external-incident",
        alarm_arn="",
        state="ALARM",
        reason=incident.signal_type or "",
        metric_name=incident.signal_type or "",
        namespace=f"{provider.upper()}/{incident.resource_type}",
    )


# ------------------------------------------------------------------
# Alarm parsing
# ------------------------------------------------------------------

def _parse_alarm(event: dict[str, Any]) -> AlarmContext:
    detail    = event.get("detail", {})
    state     = detail.get("state", {})
    config    = detail.get("configuration", {})
    resources = event.get("resources", [""])

    # Extract first metric from configuration
    metrics    = config.get("metrics", [{}])
    first_m    = metrics[0].get("metricStat", {}).get("metric", {}) if metrics else {}
    dimensions = {d["name"]: d["value"] for d in first_m.get("dimensions", [])}

    return AlarmContext(
        alarm_name  = detail.get("alarmName", "unknown"),
        alarm_arn   = resources[0] if resources else "",
        state       = state.get("value", "ALARM"),
        reason      = state.get("reason", ""),
        metric_name = first_m.get("name", ""),
        namespace   = first_m.get("namespace", ""),
        dimensions  = dimensions,
    )


# ------------------------------------------------------------------
# CloudWatch Logs Insights
# ------------------------------------------------------------------

def _query_logs_insights(alarm: AlarmContext) -> list[dict[str, Any]]:
    """
    Run a Logs Insights query against log groups derived from the alarm namespace.

    Namespace → log group heuristic:
      AWS/EKS          → /aws/eks/*
      AWS/Lambda       → /aws/lambda/*
      AWS/RDS          → /aws/rds/*
      Custom/*         → /custom/*
    """
    log_groups = _resolve_log_groups(alarm)
    if not log_groups:
        logger.warning("detector.logs_insights.skip", reason="no_log_group_mapping",
                       namespace=alarm.namespace)
        return []

    end_time   = int(time.time())
    start_time = end_time - _LOG_LOOKBACK_SEC

    query = (
        "fields @timestamp, @message, @logStream "
        "| filter @message like /ERROR|Exception|WARN|timeout|OOM/ "
        "| sort @timestamp desc "
        "| limit 20"
    )

    try:
        resp = _LOGS_CLIENT.start_query(
            logGroupNames=log_groups,
            startTime=start_time,
            endTime=end_time,
            queryString=query,
        )
        query_id = resp["queryId"]
        return _poll_query(query_id)
    except Exception as exc:
        logger.error("detector.logs_insights.error", error=str(exc))
        return []


def _poll_query(query_id: str, max_wait_sec: int = 30) -> list[dict[str, Any]]:
    deadline = time.time() + max_wait_sec
    while time.time() < deadline:
        resp   = _LOGS_CLIENT.get_query_results(queryId=query_id)
        status = resp["status"]
        if status == "Complete":
            return [
                {f["field"]: f["value"] for f in row}
                for row in resp.get("results", [])
            ]
        if status in {"Failed", "Cancelled"}:
            logger.warning("detector.logs_query.failed", status=status)
            return []
        time.sleep(2)
    logger.warning("detector.logs_query.timeout", query_id=query_id)
    return []


def _namespace_to_log_group(namespace: str) -> str:
    mapping = {
        "AWS/EKS":    "/aws/eks",
        "AWS/Lambda": "/aws/lambda",
        "AWS/RDS":    "/aws/rds",
        "AWS/Kafka":  "/aws/msk",
        "AWS/SQS":    "/aws/sqs",
    }
    for prefix, group in mapping.items():
        if namespace.startswith(prefix):
            return group
    # Custom namespace — try a best-effort path
    slug = namespace.lower().replace("/", "-").replace(" ", "-")
    return f"/custom/{slug}" if namespace.startswith("Custom") else ""


def _resolve_log_groups(alarm: AlarmContext, max_groups: int = 20) -> list[str]:
    """
    Resolve candidate log groups from an alarm.

    Logs Insights requires explicit log group names or identifiers. We first try a
    targeted exact log group for services that expose a strong dimension mapping,
    then fall back to discovering log groups by prefix.
    """
    exact_log_group = _exact_log_group(alarm)
    if exact_log_group:
        return [exact_log_group]

    log_group_prefix = _namespace_to_log_group(alarm.namespace)
    if not log_group_prefix:
        return []

    try:
        resp = _LOGS_CLIENT.describe_log_groups(logGroupNamePrefix=log_group_prefix, limit=max_groups)
        return [
            group["logGroupName"]
            for group in resp.get("logGroups", [])
            if "logGroupName" in group
        ]
    except Exception as exc:
        logger.warning(
            "detector.log_group_discovery.error",
            namespace=alarm.namespace,
            prefix=log_group_prefix,
            error=str(exc),
        )
        return []


def _exact_log_group(alarm: AlarmContext) -> str | None:
    if alarm.namespace.startswith("AWS/Lambda"):
        function_name = alarm.dimensions.get("FunctionName")
        if function_name:
            return f"/aws/lambda/{function_name}"

    if alarm.namespace.startswith("Custom"):
        prefix = _namespace_to_log_group(alarm.namespace)
        return prefix or None

    return None


# ------------------------------------------------------------------
# X-Ray
# ------------------------------------------------------------------

def _fetch_xray_traces(alarm: AlarmContext) -> list[str]:
    """Fetch recent trace IDs from X-Ray for the service implied by alarm dimensions."""
    service = alarm.dimensions.get("ServiceName") or alarm.dimensions.get("FunctionName")
    if not service:
        return []

    end_time   = time.time()
    start_time = end_time - _LOG_LOOKBACK_SEC

    try:
        resp = _XRAY_CLIENT.get_trace_summaries(
            StartTime=start_time,
            EndTime=end_time,
            FilterExpression=f'service("{service}") AND responsetime > 1',
        )
        return [t["Id"] for t in resp.get("TraceSummaries", [])]
    except Exception as exc:
        logger.warning("detector.xray.error", error=str(exc))
        return []


# ------------------------------------------------------------------
# Related metrics
# ------------------------------------------------------------------

def _fetch_related_metrics(alarm: AlarmContext) -> dict[str, float]:
    """Pull a few adjacent metrics to give the Analyzer more signal."""
    related: dict[str, float] = {}

    companion_metrics = _get_companion_metrics(alarm.namespace, alarm.metric_name)
    end_time   = time.time()
    start_time = end_time - _LOG_LOOKBACK_SEC

    for metric_name in companion_metrics:
        try:
            resp = _CW_CLIENT.get_metric_statistics(
                Namespace  = alarm.namespace,
                MetricName = metric_name,
                Dimensions = [{"Name": k, "Value": v} for k, v in alarm.dimensions.items()],
                StartTime  = start_time,
                EndTime    = end_time,
                Period     = 60,
                Statistics = ["Average"],
            )
            pts = resp.get("Datapoints", [])
            if pts:
                related[metric_name] = pts[-1]["Average"]
        except Exception:
            pass

    return related


def _get_companion_metrics(namespace: str, triggered_metric: str) -> list[str]:
    companions = {
        "AWS/EKS":    ["node_cpu_utilization", "node_memory_utilization", "pod_restart_total"],
        "AWS/Lambda": ["Errors", "Throttles", "Duration", "ConcurrentExecutions"],
        "AWS/RDS":    ["CPUUtilization", "FreeStorageSpace", "DatabaseConnections"],
        "AWS/SQS":    ["ApproximateNumberOfMessagesNotVisible", "NumberOfMessagesSent"],
    }
    for prefix, metrics in companions.items():
        if namespace.startswith(prefix):
            return [m for m in metrics if m != triggered_metric]
    return []


def _normalise_incident(
    alarm: AlarmContext,
    *,
    log_results: list[dict[str, Any]],
    trace_ids: list[str],
    related_metrics: dict[str, float],
    source_event: dict[str, Any],
):
    return _SIGNAL_ADAPTER.from_alarm_context(
        alarm,
        observations={
            "logs": log_results[:10],
            "traces": trace_ids[:10],
            "metrics": related_metrics,
        },
        severity_hint=alarm.state,
        source_event=source_event,
    )


# ------------------------------------------------------------------
# Serialisation
# ------------------------------------------------------------------

def _serialise(output: DetectorOutput) -> dict[str, Any]:
    """Convert DetectorOutput to a Step Functions–compatible dict."""
    from dataclasses import asdict
    return json.loads(json.dumps(asdict(output), default=str))
