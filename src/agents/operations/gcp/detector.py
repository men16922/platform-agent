"""
GCP Detector — Cloud Function handler.

Triggered by:
  Pub/Sub message from Cloud Monitoring alert policy (via notification channel)

Responsibilities:
  1. Parse the Cloud Monitoring alert payload
  2. Query Cloud Logging for recent error patterns
  3. Fetch related metrics from Cloud Monitoring API
  4. Return DetectorOutput for the Analyzer (via Cloud Workflows)
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

_PROJECT_ID = os.getenv("GCP_PROJECT_ID", "")
_LOG_LOOKBACK_SEC = int(os.getenv("LOG_LOOKBACK_SEC", "300"))


def cloud_function_handler(cloud_event: dict[str, Any]) -> dict[str, Any]:
    """
    Entry point for GCP Cloud Function (2nd gen, CloudEvent format).

    Cloud Monitoring alert → Pub/Sub → Cloud Function trigger.

    The Pub/Sub message data contains the Cloud Monitoring alert JSON:
    {
        "incident": {
            "incident_id": "...",
            "resource": {"type": "...", "labels": {...}},
            "policy_name": "...",
            "condition_name": "...",
            "summary": "...",
            "state": "open",
            "started_at": "...",
            "severity": "...",
            ...
        }
    }
    """
    log = logger.bind(event_type="gcp_cloud_monitoring")
    log.info("gcp_detector.start")

    event = _extract_alert_payload(cloud_event)
    incident_data = event.get("incident", {})
    log = log.bind(
        policy_name=incident_data.get("policy_name", "unknown"),
        incident_id=incident_data.get("incident_id", "unknown"),
    )

    # Normalise via GCP signal adapter
    normalized_incident = get_signal_adapter("gcp").normalise(event)

    # Build AlarmContext for downstream compatibility
    alarm = _build_alarm_context(incident_data, normalized_incident)

    # Collect observations from Cloud Logging
    log_results = _query_cloud_logging(normalized_incident)
    log.info("gcp_detector.logging_done", result_count=len(log_results))

    # Fetch related metrics
    related_metrics = _fetch_related_metrics(incident_data)
    log.info("gcp_detector.metrics_done", metric_count=len(related_metrics))

    output = DetectorOutput(
        alarm=alarm,
        log_insights_results=log_results,
        xray_trace_ids=[],  # GCP: no X-Ray, could use Cloud Trace
        related_metrics=related_metrics,
        normalized_incident=normalized_incident,
    )

    log.info("gcp_detector.done")
    return _serialise(output)


# ------------------------------------------------------------------
# Payload extraction
# ------------------------------------------------------------------

def _extract_alert_payload(cloud_event: dict[str, Any]) -> dict[str, Any]:
    """
    Extract the alert JSON from Pub/Sub CloudEvent envelope.

    CloudEvent format:
    {
        "data": {
            "message": {
                "data": "<base64 encoded alert JSON>"
            }
        }
    }

    Or direct invocation (testing / Workflows HTTP call):
    {
        "incident": {...}
    }
    """
    import base64

    # Direct invocation (already decoded)
    if "incident" in cloud_event:
        return cloud_event

    # Pub/Sub CloudEvent envelope
    message = cloud_event.get("data", {}).get("message", {})
    encoded_data = message.get("data", "")
    if encoded_data:
        decoded = base64.b64decode(encoded_data).decode("utf-8")
        return json.loads(decoded)

    return cloud_event


def _build_alarm_context(
    incident_data: dict[str, Any],
    normalized: NormalizedIncident,
) -> AlarmContext:
    """Build AlarmContext from Cloud Monitoring alert for downstream compatibility."""
    resource = incident_data.get("resource", {})
    metric = incident_data.get("metric", {}) if isinstance(incident_data.get("metric"), dict) else {}

    return AlarmContext(
        alarm_name=incident_data.get("policy_name", normalized.service),
        alarm_arn=incident_data.get("incident_id", ""),
        state="ALARM" if incident_data.get("state") == "open" else "OK",
        reason=incident_data.get("summary", ""),
        metric_name=metric.get("type", ""),
        namespace=f"GCP/{resource.get('type', 'unknown')}",
        dimensions=resource.get("labels", {}),
        triggered_at=incident_data.get("started_at", ""),
    )


# ------------------------------------------------------------------
# Cloud Logging query
# ------------------------------------------------------------------

def _query_cloud_logging(incident: NormalizedIncident) -> list[dict[str, Any]]:
    """
    Query Cloud Logging for recent errors related to the incident.

    Uses the google-cloud-logging client library.
    In production: google.cloud.logging.Client()
    Here: structured for Cloud Function deployment.
    """
    try:
        from google.cloud import logging as cloud_logging

        client = cloud_logging.Client(project=_PROJECT_ID or None)
        resource_filter = _build_log_filter(incident)

        end_time = time.time()
        start_time = end_time - _LOG_LOOKBACK_SEC

        from datetime import datetime, timezone
        start_dt = datetime.fromtimestamp(start_time, tz=timezone.utc).isoformat()
        end_dt = datetime.fromtimestamp(end_time, tz=timezone.utc).isoformat()

        filter_str = (
            f'{resource_filter} AND '
            f'severity>="ERROR" AND '
            f'timestamp>="{start_dt}" AND '
            f'timestamp<="{end_dt}"'
        )

        entries = []
        for entry in client.list_entries(filter_=filter_str, page_size=20, max_results=20):
            entries.append({
                "@timestamp": str(entry.timestamp),
                "@message": str(entry.payload)[:500] if entry.payload else "",
                "@severity": str(entry.severity),
                "@resource": str(entry.resource.type) if entry.resource else "",
            })

        return entries

    except ImportError:
        logger.warning("gcp_detector.cloud_logging.not_available", reason="google-cloud-logging not installed")
        return []
    except Exception as exc:
        logger.error("gcp_detector.cloud_logging.error", error=str(exc))
        return []


def _build_log_filter(incident: NormalizedIncident) -> str:
    """Build a Cloud Logging filter based on incident resource type."""
    metadata = incident.source_metadata or {}
    labels = metadata.get("resource_labels", {})

    if incident.resource_type == "kubernetes-workload":
        cluster = labels.get("cluster_name", "")
        namespace = labels.get("namespace_name", "")
        if cluster and namespace:
            return f'resource.type="k8s_container" AND resource.labels.cluster_name="{cluster}" AND resource.labels.namespace_name="{namespace}"'
        return 'resource.type="k8s_container"'

    if incident.resource_type == "serverless-service":
        service = incident.resource_id
        return f'resource.type="cloud_run_revision" AND resource.labels.service_name="{service}"'

    if incident.resource_type == "database-instance":
        instance = incident.resource_id
        return f'resource.type="cloudsql_database" AND resource.labels.database_id="{instance}"'

    return f'resource.labels.service="{incident.service}"'


# ------------------------------------------------------------------
# Related metrics
# ------------------------------------------------------------------

def _fetch_related_metrics(incident_data: dict[str, Any]) -> dict[str, float]:
    """
    Fetch related metrics from Cloud Monitoring API.
    """
    try:
        from google.cloud import monitoring_v3

        client = monitoring_v3.MetricServiceClient()
        project_name = f"projects/{_PROJECT_ID}" if _PROJECT_ID else None
        if not project_name:
            return {}

        resource = incident_data.get("resource", {})
        resource_type = resource.get("type", "")
        companion_metrics = _get_gcp_companion_metrics(resource_type)

        results: dict[str, float] = {}
        end_time = time.time()
        start_time = end_time - _LOG_LOOKBACK_SEC

        from google.protobuf.timestamp_pb2 import Timestamp
        interval = monitoring_v3.TimeInterval()
        interval.end_time = Timestamp(seconds=int(end_time))
        interval.start_time = Timestamp(seconds=int(start_time))

        for metric_type in companion_metrics[:3]:  # Limit to 3 queries
            try:
                request = monitoring_v3.ListTimeSeriesRequest(
                    name=project_name,
                    filter=f'metric.type = "{metric_type}"',
                    interval=interval,
                    view=monitoring_v3.ListTimeSeriesRequest.TimeSeriesView.FULL,
                )
                page_result = client.list_time_series(request=request)
                for ts in page_result:
                    if ts.points:
                        value = ts.points[0].value.double_value or ts.points[0].value.int64_value
                        results[metric_type.split("/")[-1]] = float(value)
                        break  # One value per metric
            except Exception:
                continue

        return results

    except ImportError:
        logger.warning("gcp_detector.monitoring.not_available")
        return {}
    except Exception as exc:
        logger.error("gcp_detector.monitoring.error", error=str(exc))
        return {}


def _get_gcp_companion_metrics(resource_type: str) -> list[str]:
    """Return companion metric types based on resource type."""
    companions = {
        "k8s_container": [
            "kubernetes.io/container/cpu/core_usage_time",
            "kubernetes.io/container/memory/used_bytes",
            "kubernetes.io/container/restart_count",
        ],
        "k8s_pod": [
            "kubernetes.io/pod/network/received_bytes_count",
            "kubernetes.io/pod/volume/utilization",
        ],
        "cloud_run_revision": [
            "run.googleapis.com/request_count",
            "run.googleapis.com/request_latencies",
            "run.googleapis.com/container/cpu/utilizations",
        ],
        "cloudsql_database": [
            "cloudsql.googleapis.com/database/cpu/utilization",
            "cloudsql.googleapis.com/database/disk/utilization",
            "cloudsql.googleapis.com/database/network/connections",
        ],
    }
    return companions.get(resource_type, [])


# ------------------------------------------------------------------
# Serialisation
# ------------------------------------------------------------------

def _serialise(output: DetectorOutput) -> dict[str, Any]:
    from dataclasses import asdict
    return json.loads(json.dumps(asdict(output), default=str))
