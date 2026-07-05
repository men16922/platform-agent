"""
Azure execution capability resolution helpers.
"""

from __future__ import annotations

from typing import Any

from src.agents.adapters.base import ExecutionAdapter
from src.agents.models import NormalizedIncident


class AzureExecutionAdapter(ExecutionAdapter):
    provider = "azure"

    def resolve_action(self, capability: str, incident: NormalizedIncident) -> dict[str, Any]:
        action = _action_for(capability, incident.resource_type)
        return {
            "provider": "azure",
            "capability": capability,
            "action": action,
            "parameters": _parameters_for(action, incident),
        }

    def parameters_for_action(self, action: str, incident: NormalizedIncident) -> dict[str, list[str]]:
        return _parameters_for(action, incident)


def _action_for(capability: str, resource_type: str) -> str:
    mapping = {
        ("restart_workload", "kubernetes-workload"): "AZURE-RolloutRestartAKSWorkload",
        ("scale_out", "kubernetes-workload"): "AZURE-ScaleAKSNodePool",
        ("increase_function_concurrency", "serverless-service"): "AZURE-ScaleFunctionApp",
        ("scale_database_read", "database-instance"): "AZURE-ScaleSqlReadReplica",
        ("scale_out_workers", "streaming-consumer"): "AZURE-ScaleConsumerWorkers",
        ("open_change_request", "cloud-resource"): "AZURE-NotifyOperations",
        ("open_change_request", "kubernetes-workload"): "AZURE-NotifyOperations",
        ("open_change_request", "serverless-service"): "AZURE-NotifyOperations",
        ("open_change_request", "database-instance"): "AZURE-NotifyOperations",
        ("open_change_request", "streaming-consumer"): "AZURE-NotifyOperations",
    }
    action = mapping.get((capability, resource_type))
    if action:
        return action
    raise ValueError(f"Unsupported Azure capability mapping: {capability} for {resource_type}")


def _parameters_for(action: str, incident: NormalizedIncident) -> dict[str, list[str]]:
    metadata = incident.source_metadata or {}
    dimensions = metadata.get("dimensions", {}) if isinstance(metadata, dict) else {}
    resource_ids = metadata.get("target_resource_ids", []) if isinstance(metadata, dict) else []

    if action in {"AZURE-RolloutRestartAKSWorkload", "AZURE-ScaleAKSNodePool"}:
        return _compact(
            {
                "ClusterId": [resource_ids[0] if resource_ids else ""],
                "Namespace": [dimensions.get("Namespace", "")],
                "WorkloadName": [incident.service],
            }
        )

    if action == "AZURE-ScaleFunctionApp":
        return _compact(
            {
                "FunctionAppName": [incident.resource_id],
                "ResourceId": [resource_ids[0] if resource_ids else ""],
            }
        )

    if action == "AZURE-ScaleSqlReadReplica":
        return _compact(
            {
                "DatabaseName": [incident.resource_id],
                "ResourceId": [resource_ids[0] if resource_ids else ""],
            }
        )

    if action == "AZURE-ScaleConsumerWorkers":
        return _compact(
            {
                "ConsumerGroup": [incident.resource_id],
                "ResourceId": [resource_ids[0] if resource_ids else ""],
            }
        )

    return _compact({"AlertRule": [metadata.get("alert_rule", incident.resource_id)]})


def _compact(values: dict[str, list[str]]) -> dict[str, list[str]]:
    return {key: value for key, value in values.items() if value and value[0]}
