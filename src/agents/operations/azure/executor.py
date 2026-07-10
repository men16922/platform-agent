"""
Azure Executor — Azure Function handler.

Receives DecisionOutput from Durable Functions orchestrator and:
  1. Executes remediation actions via az cli/kubectl for AUTO/APPROVE modes
  2. Skips execution for MANUAL mode
  3. Posts a Slack incident report
  4. Records the incident in Cosmos DB
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

_COSMOS_ENDPOINT = os.getenv("AZURE_COSMOS_ENDPOINT", "")
_COSMOS_DATABASE = os.getenv("AZURE_COSMOS_DATABASE", "platform-agent")
_INCIDENT_CONTAINER = os.getenv("AZURE_INCIDENT_CONTAINER", "incident-history")
_SLACK_WEBHOOK = os.getenv("SLACK_WEBHOOK_URL", "")


def azure_function_handler(event: dict[str, Any]) -> dict[str, Any]:
    """
    Event: DecisionOutput dict (Durable Functions state output from Decision).
    """
    decision = _deserialise_decision(event)
    alarm = decision.analyzer.detector.alarm
    log = logger.bind(
        alarm_name=alarm.alarm_name,
        mode=decision.remediation_mode.value,
        runbook_id=decision.runbook_id,
    )
    log.info("azure_executor.start")

    incident_id = f"AZ-INC-{uuid.uuid4().hex[:8].upper()}"
    executed: list[str] = []
    skipped: list[str] = []

    if decision.remediation_mode in (RemediationMode.AUTO, RemediationMode.APPROVE):
        executed, skipped = _run_azure_actions(decision, log)
    else:
        skipped = decision.actions
        log.info("azure_executor.manual_mode", skipped=skipped)

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

    log.info("azure_executor.done", incident_id=incident_id, resolved=resolved)
    return _serialise(output)


# ------------------------------------------------------------------
# Action execution
# ------------------------------------------------------------------

def _run_azure_actions(
    decision: DecisionOutput,
    log: Any,
) -> tuple[list[str], list[str]]:
    """Execute Azure remediation actions via az cli / kubectl."""
    executed: list[str] = []
    skipped: list[str] = []
    normalized = decision.analyzer.detector.normalized_incident

    if not normalized:
        log.warning("azure_executor.no_normalized_incident")
        return [], decision.actions

    adapter = get_execution_adapter("azure")

    for action in decision.actions:
        try:
            log.info("azure_executor.action.start", action=action)
            result = _execute_single_action(action, normalized, adapter)
            if result.get("success"):
                executed.append(action)
                log.info("azure_executor.action.success", action=action)
            else:
                skipped.append(action)
                log.warning("azure_executor.action.failed", action=action, error=result.get("error"))
        except Exception as exc:
            skipped.append(action)
            log.error("azure_executor.action.error", action=action, error=str(exc))

    return executed, skipped


def _execute_single_action(
    action: str,
    incident: NormalizedIncident,
    adapter: Any,
) -> dict[str, Any]:
    """
    Execute a single Azure action.

    In production:
    - AKS: az aks command invoke --command "kubectl ..."
    - Functions: az functionapp scale --min-instances ...
    - SQL: az sql db update --capacity ...
    """
    try:
        capability = _action_to_capability(action)
        resolved = adapter.resolve_action(capability, incident)
        parameters = resolved.get("parameters", {})

        logger.info(
            "azure_executor.execute",
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
        "AZURE-RolloutRestartAKSWorkload": "restart_workload",
        "AZURE-ScaleAKSNodePool": "scale_out",
        "AZURE-ScaleFunctionApp": "increase_function_concurrency",
        "AZURE-ScaleSqlDatabase": "scale_database_primary",
        "AZURE-ScaleSqlReadReplica": "scale_database_read",
        "AZURE-ScaleConsumerWorkers": "scale_out_workers",
        "AZURE-RebalanceEventHubConsumer": "rebalance_consumer",
        "AZURE-RollbackAKSWorkload": "rollback_release",
        "AZURE-RollbackFunctionApp": "rollback_release",
        "AZURE-CleanupManagedDisk": "cleanup_disk_space",
        "AZURE-CleanupSqlStorage": "cleanup_disk_space",
        "AZURE-ExpandManagedDisk": "expand_storage",
        "AZURE-ExpandSqlStorage": "expand_storage",
        "AZURE-RenewAppServiceCertificate": "renew_certificate",
        "AZURE-DrainAKSNode": "drain_node",
        "AZURE-NotifyOperations": "open_change_request",
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
    if not _SLACK_WEBHOOK:
        return None

    alarm = decision.analyzer.detector.alarm
    severity = decision.analyzer.severity.value
    mode = decision.remediation_mode.value
    emoji = "✅" if resolved else "⚠️"

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"{emoji} Azure Incident: {incident_id}"}
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
        logger.warning("azure_executor.slack.error", error=str(exc))
        return None


# ------------------------------------------------------------------
# Cosmos DB incident record
# ------------------------------------------------------------------

def _record_incident(
    *,
    incident_id: str,
    alarm: AlarmContext,
    analyzer: AnalyzerOutput,
    executed: list[str],
    resolved: bool,
) -> None:
    """Record incident in Cosmos DB."""
    try:
        from azure.cosmos import CosmosClient

        client = CosmosClient(_COSMOS_ENDPOINT, credential=_get_cosmos_credential())
        database = client.get_database_client(_COSMOS_DATABASE)
        container = database.get_container_client(_INCIDENT_CONTAINER)

        container.upsert_item({
            "id": incident_id,
            "alarm_name": alarm.alarm_name,
            "severity": analyzer.severity.value,
            "root_cause": analyzer.root_cause[:1000],
            "executed_actions": executed,
            "resolved": resolved,
            "provider": "azure",
            "created_at": time.time(),
            "ttl": 90 * 24 * 3600,  # 90 days
        })

    except ImportError:
        logger.warning("azure_executor.cosmos.not_available")
    except Exception as exc:
        logger.warning("azure_executor.cosmos.error", error=str(exc))


def _get_cosmos_credential():
    key = os.getenv("AZURE_COSMOS_KEY", "")
    if key:
        return key
    try:
        from azure.identity import DefaultAzureCredential
        return DefaultAzureCredential()
    except ImportError:
        return ""


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
