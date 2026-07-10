"""
Azure Detector — Azure Function handler.

Triggered by:
  Event Grid message from Azure Monitor alert (Common Alert Schema)

Responsibilities:
  1. Parse the Azure Monitor Common Alert Schema payload
  2. Query Log Analytics for recent error patterns
  3. Fetch related metrics from Azure Monitor
  4. Return DetectorOutput for the Analyzer (via Durable Functions)
"""

from __future__ import annotations

import json
import os
import time
from typing import Any

import structlog

from src.agents.adapters.registry import get_signal_adapter
from src.agents.models import AlarmContext, DetectorOutput, NormalizedIncident

logger = structlog.get_logger(__name__)

_SUBSCRIPTION_ID = os.getenv("AZURE_SUBSCRIPTION_ID", "")
_RESOURCE_GROUP = os.getenv("AZURE_RESOURCE_GROUP", "")
_WORKSPACE_ID = os.getenv("AZURE_LOG_ANALYTICS_WORKSPACE_ID", "")
_LOG_LOOKBACK_SEC = int(os.getenv("LOG_LOOKBACK_SEC", "300"))


def azure_function_handler(event: dict[str, Any]) -> dict[str, Any]:
    """
    Entry point for Azure Function (Event Grid trigger).

    Azure Monitor alert → Event Grid → Azure Function.

    Common Alert Schema:
    {
        "schemaId": "azureMonitorCommonAlertSchema",
        "data": {
            "essentials": {
                "alertId": "...",
                "alertRule": "...",
                "severity": "Sev1",
                "signalType": "Metric",
                "monitorCondition": "Fired",
                "targetResourceType": "...",
                ...
            },
            "alertContext": {
                "condition": {
                    "allOf": [{
                        "metricName": "...",
                        "dimensions": [...],
                        ...
                    }]
                }
            }
        }
    }
    """
    log = logger.bind(event_type="azure_monitor")
    log.info("azure_detector.start")

    essentials = event.get("data", {}).get("essentials", {})
    log = log.bind(
        alert_rule=essentials.get("alertRule", "unknown"),
        alert_id=essentials.get("alertId", "unknown"),
    )

    # Normalise via Azure signal adapter
    normalized_incident = get_signal_adapter("azure").normalise(event)

    # Build AlarmContext for downstream compatibility
    alarm = _build_alarm_context(essentials, normalized_incident, event)

    # Collect observations from Log Analytics
    log_results = _query_log_analytics(normalized_incident)
    log.info("azure_detector.log_analytics_done", result_count=len(log_results))

    # Fetch related metrics
    related_metrics = _fetch_related_metrics(event)
    log.info("azure_detector.metrics_done", metric_count=len(related_metrics))

    output = DetectorOutput(
        alarm=alarm,
        log_insights_results=log_results,
        xray_trace_ids=[],  # Azure: no X-Ray, could use App Insights traces
        related_metrics=related_metrics,
        normalized_incident=normalized_incident,
    )

    log.info("azure_detector.done")
    return _serialise(output)


# ------------------------------------------------------------------
# Alarm context building
# ------------------------------------------------------------------

def _build_alarm_context(
    essentials: dict[str, Any],
    normalized: NormalizedIncident,
    event: dict[str, Any],
) -> AlarmContext:
    """Build AlarmContext from Azure Monitor alert for downstream compatibility."""
    alert_context = event.get("data", {}).get("alertContext", {})
    condition = alert_context.get("condition", {})
    all_of = condition.get("allOf", [])
    first_condition = all_of[0] if all_of else {}

    dimensions = {
        d.get("name"): d.get("value")
        for d in first_condition.get("dimensions", [])
        if "name" in d and "value" in d
    }

    return AlarmContext(
        alarm_name=essentials.get("alertRule", normalized.service),
        alarm_arn=essentials.get("alertId", ""),
        state="ALARM" if essentials.get("monitorCondition") == "Fired" else "OK",
        reason=essentials.get("description", ""),
        metric_name=first_condition.get("metricName", ""),
        namespace=f"Azure/{essentials.get('targetResourceType', 'unknown')}",
        dimensions=dimensions,
        triggered_at=essentials.get("firedDateTime", ""),
    )


# ------------------------------------------------------------------
# Log Analytics query
# ------------------------------------------------------------------

def _query_log_analytics(incident: NormalizedIncident) -> list[dict[str, Any]]:
    """
    Query Azure Log Analytics for recent errors.

    Uses azure-monitor-query client library.
    """
    try:
        from azure.monitor.query import LogsQueryClient
        from azure.identity import DefaultAzureCredential

        credential = DefaultAzureCredential()
        client = LogsQueryClient(credential)

        query = _build_kql_query(incident)
        from datetime import timedelta
        timespan = timedelta(seconds=_LOG_LOOKBACK_SEC)

        response = client.query_workspace(
            workspace_id=_WORKSPACE_ID,
            query=query,
            timespan=timespan,
        )

        entries = []
        if response.tables:
            for row in response.tables[0].rows[:20]:
                columns = response.tables[0].columns
                entry = {col.name: str(val) for col, val in zip(columns, row)}
                entries.append(entry)

        return entries

    except ImportError:
        logger.warning("azure_detector.log_analytics.not_available", reason="azure-monitor-query not installed")
        return []
    except Exception as exc:
        logger.error("azure_detector.log_analytics.error", error=str(exc))
        return []


def _build_kql_query(incident: NormalizedIncident) -> str:
    """Build a KQL query based on incident resource type."""
    if incident.resource_type == "kubernetes-workload":
        return (
            "ContainerLog\n"
            f"| where LogEntry contains 'error' or LogEntry contains 'exception'\n"
            "| project TimeGenerated, LogEntry, ContainerID\n"
            "| order by TimeGenerated desc\n"
            "| take 20"
        )

    if incident.resource_type == "serverless-service":
        return (
            "FunctionAppLogs\n"
            "| where Level == 'Error' or Level == 'Critical'\n"
            "| project TimeGenerated, Message, FunctionName\n"
            "| order by TimeGenerated desc\n"
            "| take 20"
        )

    if incident.resource_type == "database-instance":
        return (
            "AzureDiagnostics\n"
            "| where Category == 'SQLSecurityAuditEvents' or Category == 'Errors'\n"
            "| project TimeGenerated, Message, Resource\n"
            "| order by TimeGenerated desc\n"
            "| take 20"
        )

    return (
        "AppTraces\n"
        "| where SeverityLevel >= 3\n"
        "| project TimeGenerated, Message, OperationName\n"
        "| order by TimeGenerated desc\n"
        "| take 20"
    )


# ------------------------------------------------------------------
# Related metrics
# ------------------------------------------------------------------

def _fetch_related_metrics(event: dict[str, Any]) -> dict[str, float]:
    """Fetch related metrics from Azure Monitor."""
    try:
        from azure.monitor.query import MetricsQueryClient
        from azure.identity import DefaultAzureCredential

        essentials = event.get("data", {}).get("essentials", {})
        resource_ids = essentials.get("alertTargetIDs", [])
        if not resource_ids:
            return {}

        credential = DefaultAzureCredential()
        client = MetricsQueryClient(credential)

        resource_type = essentials.get("targetResourceType", "")
        companion_metrics = _get_azure_companion_metrics(resource_type)

        results: dict[str, float] = {}
        from datetime import timedelta
        timespan = timedelta(seconds=_LOG_LOOKBACK_SEC)

        for metric_name in companion_metrics[:3]:
            try:
                response = client.query_resource(
                    resource_uri=resource_ids[0],
                    metric_names=[metric_name],
                    timespan=timespan,
                )
                for metric in response.metrics:
                    for ts in metric.timeseries:
                        if ts.data:
                            latest = ts.data[-1]
                            value = latest.average or latest.total or 0.0
                            results[metric_name] = float(value)
                            break
            except Exception:
                continue

        return results

    except ImportError:
        logger.warning("azure_detector.metrics.not_available")
        return {}
    except Exception as exc:
        logger.error("azure_detector.metrics.error", error=str(exc))
        return {}


def _get_azure_companion_metrics(resource_type: str) -> list[str]:
    """Return companion metric names based on resource type."""
    lowered = resource_type.lower()
    if "managedclusters" in lowered:
        return ["node_cpu_usage_percentage", "node_memory_rss_percentage", "kube_pod_status_ready"]
    if "web/sites" in lowered or "function" in lowered:
        return ["Http5xx", "AverageResponseTime", "FunctionExecutionCount"]
    if "sql" in lowered:
        return ["cpu_percent", "storage_percent", "connection_failed"]
    return []


# ------------------------------------------------------------------
# Serialisation
# ------------------------------------------------------------------

def _serialise(output: DetectorOutput) -> dict[str, Any]:
    from dataclasses import asdict
    return json.loads(json.dumps(asdict(output), default=str))
