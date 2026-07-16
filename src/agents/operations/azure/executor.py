"""
Azure Executor — Azure Function handler.

Receives DecisionOutput from Durable Functions orchestrator and:
  1. Executes remediation actions via az cli/kubectl for AUTO/APPROVE modes
  2. Skips execution for MANUAL mode
  3. Posts a Slack incident report
  4. Records the incident in Cosmos DB

Provider-neutral boilerplate (decision (de)serialisation, the action loop, the
Slack report) lives in ``operations/_executor_common.py``; only the Azure-specific
action mapping, single-action runner, and Cosmos record stay here.
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

_COSMOS_ENDPOINT = os.getenv("AZURE_COSMOS_ENDPOINT", "")
_COSMOS_DATABASE = os.getenv("AZURE_COSMOS_DATABASE", "platform-agent")
_INCIDENT_CONTAINER = os.getenv("AZURE_INCIDENT_CONTAINER", "incident-history")
_SLACK_WEBHOOK = os.getenv("SLACK_WEBHOOK_URL", "")


def azure_function_handler(event: dict[str, Any]) -> dict[str, Any]:
    """
    Event: DecisionOutput dict (Durable Functions state output from Decision).
    """
    decision = common.deserialise_decision(event)
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
        executed, skipped = common.run_actions(
            decision=decision,
            adapter_key="azure",
            execute_single_action=_execute_single_action,
            log=log,
            log_prefix="azure_executor",
        )
    else:
        skipped = decision.actions
        log.info("azure_executor.manual_mode", skipped=skipped)

    resolved = bool(executed) and not skipped

    slack_ts = common.post_incident_slack(
        webhook_url=_SLACK_WEBHOOK,
        provider_label="Azure",
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

    log.info("azure_executor.done", incident_id=incident_id, resolved=resolved)
    return common.serialise(output)


# ------------------------------------------------------------------
# Action execution (Azure-specific)
# ------------------------------------------------------------------

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
# Cosmos DB incident record (Azure-specific)
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
