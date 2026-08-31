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
from src.agents.runbooks.capability_schema import resolution_verdict
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

    # Through the shared verdict, not a local copy of its rule. With no
    # verifications this is *exactly* `bool(executed) and not skipped` — which is
    # what this line used to hardcode — so behaviour is unchanged today. It is
    # routed here because that rule is a **contract**
    # (`capability_schema.resolution_verdict`, which AWS already reads) and this
    # provider had an equivalent copy of it: the shape where the next change
    # lands in one place and rots in the other. GCP/Azure have no verify path
    # yet; when they get one, resolution follows without a second edit.
    resolved = resolution_verdict(executed, skipped).resolved

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
    - AKS: ARM listClusterUserCredentials -> kubectl REST (rollout restart / scale / rollback)
    - Functions: ARM restart / slot swap
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

        # Call the real ARM/AKS action runner.
        #
        # Until 2026-08-30 this function stopped at the log line above and returned
        # ``success: True``. That success landed in ``executed``, ``resolution_verdict``
        # turned it into ``resolved=True``, and the incident was posted to Slack and
        # recorded as remediated — for an action nobody performed. GCP's executor grew
        # this call in Phase 3; Azure did not, and nothing said so
        # (`docs/evidence/azure-executor-reports-resolved-without-executing.log`).
        #
        # The 11 of 16 declared actions the runner does not implement do not become
        # silent successes: `run_azure_action` raises `ValueError("Unsupported Azure
        # action: ...")` for them, which the `except` below turns into
        # ``success: False`` — the same honest shape GCP already has.
        from src.agents.operations.runners.azure_runner import run_azure_action
        from src.agents.platform.scope import resolve_incident_scope

        incident_scope = resolve_incident_scope(incident, logger)
        run_azure_action(action, parameters, logger, incident_scope)

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
            # Relative seconds, which IS the Cosmos item-level contract (unlike
            # the absolute epoch AWS/GCP write) — but NOT ENFORCED: item `ttl`
            # only applies when the container has DefaultTimeToLive set, and
            # `durable_functions.py` creates this container with no `--ttl`.
            # Nothing expires here either. Same reasoning as the GCP writer:
            # enabling retention deletes data and is an approval.
            "ttl": 90 * 24 * 3600,
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
