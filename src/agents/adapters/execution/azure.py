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
        ("scale_out", "network-endpoint"): "AZURE-ScaleAKSNodePool",
        ("increase_function_concurrency", "serverless-service"): "AZURE-ScaleFunctionApp",
        ("increase_function_concurrency", "lambda-function"): "AZURE-ScaleFunctionApp",
        ("scale_database_primary", "database-instance"): "AZURE-ScaleSqlDatabase",
        ("scale_database_read", "database-instance"): "AZURE-ScaleSqlReadReplica",
        ("scale_out_workers", "streaming-consumer"): "AZURE-ScaleConsumerWorkers",
        ("rebalance_consumer", "streaming-consumer"): "AZURE-RebalanceEventHubConsumer",
        ("rollback_release", "kubernetes-workload"): "AZURE-RollbackAKSWorkload",
        ("rollback_release", "serverless-service"): "AZURE-RollbackFunctionApp",
        ("cleanup_disk_space", "storage-volume"): "AZURE-CleanupManagedDisk",
        ("cleanup_disk_space", "kubernetes-workload"): "AZURE-CleanupManagedDisk",
        ("cleanup_disk_space", "database-instance"): "AZURE-CleanupSqlStorage",
        ("expand_storage", "storage-volume"): "AZURE-ExpandManagedDisk",
        ("expand_storage", "kubernetes-workload"): "AZURE-ExpandManagedDisk",
        ("expand_storage", "database-instance"): "AZURE-ExpandSqlStorage",
        ("renew_certificate", "certificate"): "AZURE-RenewAppServiceCertificate",
        ("renew_certificate", "cloud-resource"): "AZURE-RenewAppServiceCertificate",
        ("drain_node", "network-endpoint"): "AZURE-DrainAKSNode",
        ("drain_node", "kubernetes-workload"): "AZURE-DrainAKSNode",
        ("open_change_request", "cloud-resource"): "AZURE-NotifyOperations",
        ("open_change_request", "kubernetes-workload"): "AZURE-NotifyOperations",
        ("open_change_request", "serverless-service"): "AZURE-NotifyOperations",
        ("open_change_request", "database-instance"): "AZURE-NotifyOperations",
        ("open_change_request", "streaming-consumer"): "AZURE-NotifyOperations",
        ("open_change_request", "certificate"): "AZURE-NotifyOperations",
        ("open_change_request", "storage-volume"): "AZURE-NotifyOperations",
        ("open_change_request", "network-endpoint"): "AZURE-NotifyOperations",
    }
    action = mapping.get((capability, resource_type))
    if action:
        return action
    raise ValueError(f"Unsupported Azure capability mapping: {capability} for {resource_type}")


def _parameters_for(action: str, incident: NormalizedIncident) -> dict[str, list[str]]:
    metadata = incident.source_metadata or {}
    dimensions = metadata.get("dimensions", {}) if isinstance(metadata, dict) else {}
    resource_ids = metadata.get("target_resource_ids", []) if isinstance(metadata, dict) else []

    if action in {"AZURE-RolloutRestartAKSWorkload", "AZURE-ScaleAKSNodePool", "AZURE-DrainAKSNode", "AZURE-RollbackAKSWorkload"}:
        return _compact(
            {
                "ClusterId": [resource_ids[0] if resource_ids else ""],
                "Namespace": [dimensions.get("Namespace", "")],
                "WorkloadName": [incident.service],
            }
        )

    if action in {"AZURE-ScaleFunctionApp", "AZURE-RollbackFunctionApp"}:
        return _compact(
            {
                "FunctionAppName": [incident.resource_id],
                "ResourceId": [resource_ids[0] if resource_ids else ""],
            }
        )

    if action in {"AZURE-ScaleSqlDatabase", "AZURE-ScaleSqlReadReplica", "AZURE-ExpandSqlStorage", "AZURE-CleanupSqlStorage"}:
        return _compact(
            {
                "DatabaseName": [incident.resource_id],
                "ResourceId": [resource_ids[0] if resource_ids else ""],
            }
        )

    if action in {"AZURE-ScaleConsumerWorkers", "AZURE-RebalanceEventHubConsumer"}:
        return _compact(
            {
                "ConsumerGroup": [incident.resource_id],
                "ResourceId": [resource_ids[0] if resource_ids else ""],
            }
        )

    if action in {"AZURE-CleanupManagedDisk", "AZURE-ExpandManagedDisk"}:
        return _compact(
            {
                "DiskName": [dimensions.get("DiskName", incident.resource_id)],
                "ResourceId": [resource_ids[0] if resource_ids else ""],
            }
        )

    if action == "AZURE-RenewAppServiceCertificate":
        return _compact(
            {
                "CertificateName": [incident.resource_id],
                "ResourceId": [resource_ids[0] if resource_ids else ""],
            }
        )

    return _compact({"AlertRule": [metadata.get("alert_rule", incident.resource_id)]})


def _compact(values: dict[str, list[str]]) -> dict[str, list[str]]:
    return {key: value for key, value in values.items() if value and value[0]}
