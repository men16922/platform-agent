"""
GCP Executor — Cloud Function handler.

Receives DecisionOutput from Cloud Workflows and:
  1. Executes remediation actions via gcloud/kubectl for AUTO/APPROVE modes
  2. Skips execution for MANUAL mode
  3. Posts a Slack incident report
  4. Records the incident in Firestore

Provider-neutral boilerplate (decision (de)serialisation, the action loop, the
Slack report) lives in ``operations/_executor_common.py``; only the GCP-specific
action mapping, single-action runner, and Firestore record stay here.
"""

from __future__ import annotations

import os
import time
import uuid
from typing import Any

import structlog

from src.agents.operations import _executor_common as common
from src.agents.operations._executor_common import RemediationMode
from src.agents.models import (
    AlarmContext, AnalyzerOutput, ExecutorOutput, NormalizedIncident,
)

logger = structlog.get_logger(__name__)

_PROJECT_ID = os.getenv("GCP_PROJECT_ID", "")
_SLACK_WEBHOOK = os.getenv("SLACK_WEBHOOK_URL", "")
_INCIDENT_COLLECTION = os.getenv("INCIDENT_COLLECTION", "incident-history")


def cloud_function_handler(event: dict[str, Any]) -> dict[str, Any]:
    """
    Event: DecisionOutput dict (Cloud Workflows state output from Decision).
    """
    decision = common.deserialise_decision(event)
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
        executed, skipped = common.run_actions(
            decision=decision,
            adapter_key="gcp",
            execute_single_action=_execute_single_action,
            log=log,
            log_prefix="gcp_executor",
        )
    else:
        skipped = decision.actions
        log.info("gcp_executor.manual_mode", skipped=skipped)

    resolved = bool(executed) and not skipped

    slack_ts = common.post_incident_slack(
        webhook_url=_SLACK_WEBHOOK,
        provider_label="GCP",
        incident_id=incident_id,
        decision=decision,
        executed=executed,
        skipped=skipped,
        resolved=resolved,
        log=log,
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
    return common.serialise(output)


# ------------------------------------------------------------------
# Action execution (GCP-specific)
# ------------------------------------------------------------------

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

        # Call real GKE and Cloud Run action runner
        from src.agents.operations.runners.gcp_runner import run_gcp_action
        run_gcp_action(action, parameters, logger)

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
# Firestore incident record (GCP-specific)
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
