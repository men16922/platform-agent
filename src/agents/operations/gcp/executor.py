"""
GCP Executor — Cloud Function handler.

Receives DecisionOutput from Cloud Workflows and:
  1. Executes remediation actions via gcloud/kubectl for AUTO/APPROVE modes
  2. Skips execution for MANUAL mode
  3. Posts a Slack incident report
  4. Records the incident in Firestore
"""

from __future__ import annotations

import json
import os
import time
import uuid
from typing import Any

import structlog

from src.agents.adapters.registry import get_execution_adapter
from src.agents.adapters.slack_client import post_webhook
from src.agents.models import (
    AlarmContext, AnalyzerOutput, DecisionOutput, DetectorOutput,
    ExecutorOutput, NormalizedIncident, RemediationMode, Severity,
)

logger = structlog.get_logger(__name__)

_PROJECT_ID = os.getenv("GCP_PROJECT_ID", "")
_SLACK_WEBHOOK = os.getenv("SLACK_WEBHOOK_URL", "")
_INCIDENT_COLLECTION = os.getenv("INCIDENT_COLLECTION", "incident-history")


def cloud_function_handler(event: dict[str, Any]) -> dict[str, Any]:
    """
    Event: DecisionOutput dict (Cloud Workflows state output from Decision).
    """
    decision = _deserialise_decision(event)
    alarm = decision.analyzer.detector.alarm
    log = logger.bind(
        alarm_name=alarm.alarm_name,
        mode=decision.remediation_mode.value,
        runbook_id=decision.runbook_id,
    )
    log.info("gcp_executor.start")

    incident_id = f"GCP-INC-{uuid.uuid4().hex[:8].upper()}"
    executed: list[str] = []
    skipped: list[str] = []

    if decision.remediation_mode in (RemediationMode.AUTO, RemediationMode.APPROVE):
        executed, skipped = _run_gcp_actions(decision, log)
    else:
        skipped = decision.actions
        log.info("gcp_executor.manual_mode", skipped=skipped)

    resolved = bool(executed) and not skipped

    slack_ts = _post_slack_report(
        incident_id=incident_id,
        decision=decision,
        executed=executed,
        skipped=skipped,
        resolved=resolved,
    )

    _record_incident(
        incident_id=incident_id,
        alarm=alarm,
        analyzer=decision.analyzer,
        executed=executed,
        resolved=resolved,
    )

    output = ExecutorOutput(
        decision=decision,
        executed_actions=executed,
        skipped_actions=skipped,
        slack_ts=slack_ts,
        incident_id=incident_id,
        resolved=resolved,
    )

    log.info("gcp_executor.done", incident_id=incident_id, resolved=resolved)
    return _serialise(output)


# ------------------------------------------------------------------
# Action execution
# ------------------------------------------------------------------

def _run_gcp_actions(
    decision: DecisionOutput,
    log: Any,
) -> tuple[list[str], list[str]]:
    """
    Execute GCP remediation actions.

    In production, this calls gcloud CLI or GCP client libraries.
    Actions are resolved by the GCP execution adapter.
    """
    executed: list[str] = []
    skipped: list[str] = []
    normalized = decision.analyzer.detector.normalized_incident

    if not normalized:
        log.warning("gcp_executor.no_normalized_incident")
        return [], decision.actions

    adapter = get_execution_adapter("gcp")

    for action in decision.actions:
        try:
            log.info("gcp_executor.action.start", action=action)
            result = _execute_single_action(action, normalized, adapter)
            if result.get("success"):
                executed.append(action)
                log.info("gcp_executor.action.success", action=action)
            else:
                skipped.append(action)
                log.warning("gcp_executor.action.failed", action=action, error=result.get("error"))
        except Exception as exc:
            skipped.append(action)
            log.error("gcp_executor.action.error", action=action, error=str(exc))

    return executed, skipped


def _execute_single_action(
    action: str,
    incident: NormalizedIncident,
    adapter: Any,
) -> dict[str, Any]:
    """
    Execute a single GCP action.

    In production, this would:
    - GKE actions: kubectl rollout restart, kubectl scale, etc.
    - Cloud Run: gcloud run services update
    - Cloud SQL: gcloud sql instances patch
    - Pub/Sub: gcloud pubsub subscriptions update

    For now, resolve parameters and simulate execution.
    """
    try:
        # Find the capability for this action
        capability = _action_to_capability(action)
        resolved = adapter.resolve_action(capability, incident)
        parameters = resolved.get("parameters", {})

        # In production: subprocess.run(["gcloud", ...]) or API client call
        # Here: log the intended action and return success
        logger.info(
            "gcp_executor.execute",
            action=action,
            capability=capability,
            parameters=parameters,
        )

        return {"success": True, "action": action, "parameters": parameters}

    except Exception as exc:
        return {"success": False, "action": action, "error": str(exc)}


def _action_to_capability(action: str) -> str:
    """Reverse-map action name to capability."""
    mapping = {
        "GCP-RolloutRestartGKEWorkload": "restart_workload",
        "GCP-ScaleGKEWorkload": "scale_out",
        "GCP-ScaleCloudRunService": "increase_function_concurrency",
        "GCP-ScaleCloudSqlInstance": "scale_database_primary",
        "GCP-CreateCloudSqlReadReplica": "scale_database_read",
        "GCP-ScalePubSubWorkers": "scale_out_workers",
        "GCP-RebalancePubSubSubscription": "rebalance_consumer",
        "GCP-RollbackGKEWorkload": "rollback_release",
        "GCP-RollbackCloudRunRevision": "rollback_release",
        "GCP-CleanupPersistentDisk": "cleanup_disk_space",
        "GCP-CleanupCloudSqlStorage": "cleanup_disk_space",
        "GCP-ExpandPersistentDisk": "expand_storage",
        "GCP-ExpandCloudSqlStorage": "expand_storage",
        "GCP-RenewManagedCertificate": "renew_certificate",
        "GCP-DrainGKENode": "drain_node",
        "GCP-NotifyOperations": "open_change_request",
    }
    return mapping.get(action, "open_change_request")


# ------------------------------------------------------------------
# Slack report
# ------------------------------------------------------------------

def _post_slack_report(
    *,
    incident_id: str,
    decision: DecisionOutput,
    executed: list[str],
    skipped: list[str],
    resolved: bool,
) -> str | None:
    """Post incident report to Slack."""
    if not _SLACK_WEBHOOK:
        return None

    alarm = decision.analyzer.detector.alarm
    severity = decision.analyzer.severity.value
    mode = decision.remediation_mode.value
    emoji = "✅" if resolved else "⚠️"

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"{emoji} GCP Incident: {incident_id}"}
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Alert:* {alarm.alarm_name}"},
                {"type": "mrkdwn", "text": f"*Severity:* {severity}"},
                {"type": "mrkdwn", "text": f"*Mode:* {mode}"},
                {"type": "mrkdwn", "text": f"*Runbook:* {decision.runbook_id}"},
            ]
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Root Cause:*\n{decision.analyzer.root_cause[:500]}"}
        },
    ]

    if executed:
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Executed:*\n{'  '.join(f'• {a}' for a in executed)}"}
        })

    if skipped:
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Skipped:*\n{'  '.join(f'• {a}' for a in skipped)}"}
        })

    try:
        result = post_webhook({"blocks": blocks})
        return result.get("ts")
    except Exception as exc:
        logger.warning("gcp_executor.slack.error", error=str(exc))
        return None


# ------------------------------------------------------------------
# Firestore incident record
# ------------------------------------------------------------------

def _record_incident(
    *,
    incident_id: str,
    alarm: AlarmContext,
    analyzer: AnalyzerOutput,
    executed: list[str],
    resolved: bool,
) -> None:
    """Record the incident in Firestore for future lookups."""
    try:
        from google.cloud import firestore

        db = firestore.Client(project=_PROJECT_ID or None)
        doc_ref = db.collection(_INCIDENT_COLLECTION).document(incident_id)
        doc_ref.set({
            "incident_id": incident_id,
            "alarm_name": alarm.alarm_name,
            "severity": analyzer.severity.value,
            "root_cause": analyzer.root_cause[:1000],
            "executed_actions": executed,
            "resolved": resolved,
            "provider": "gcp",
            "created_at": time.time(),
            "ttl": int(time.time()) + (90 * 24 * 3600),  # 90 days
        })

    except ImportError:
        logger.warning("gcp_executor.firestore.not_available")
    except Exception as exc:
        logger.warning("gcp_executor.firestore.error", error=str(exc))


# ------------------------------------------------------------------
# Serialisation
# ------------------------------------------------------------------

def _deserialise_decision(event: dict[str, Any]) -> DecisionOutput:
    from dataclasses import fields

    analyzer_data = event["analyzer"]
    detector_data = analyzer_data["detector"]
    alarm_data = detector_data["alarm"]

    alarm = AlarmContext(**{
        k: alarm_data[k] for k in (f.name for f in fields(AlarmContext))
        if k in alarm_data
    })
    normalized_data = detector_data.get("normalized_incident")
    normalized = NormalizedIncident(**normalized_data) if normalized_data else None

    detector = DetectorOutput(
        alarm=alarm,
        log_insights_results=detector_data.get("log_insights_results", []),
        xray_trace_ids=detector_data.get("xray_trace_ids", []),
        related_metrics=detector_data.get("related_metrics", {}),
        normalized_incident=normalized,
    )

    analyzer = AnalyzerOutput(
        detector=detector,
        root_cause=analyzer_data["root_cause"],
        severity=Severity(analyzer_data["severity"]),
        confidence=float(analyzer_data.get("confidence", 0.0)),
        similar_incidents=analyzer_data.get("similar_incidents", []),
    )

    return DecisionOutput(
        analyzer=analyzer,
        runbook_id=event["runbook_id"],
        remediation_mode=RemediationMode(event["remediation_mode"]),
        actions=event.get("actions", []),
        estimated_rto_sec=event.get("estimated_rto_sec"),
    )


def _serialise(output: ExecutorOutput) -> dict[str, Any]:
    from dataclasses import asdict
    return json.loads(json.dumps(asdict(output), default=str))
