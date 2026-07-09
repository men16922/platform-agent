"""
GCP execution capability resolution helpers.
"""

from __future__ import annotations

from typing import Any

from src.agents.adapters.base import ExecutionAdapter
from src.agents.models import NormalizedIncident


class GcpExecutionAdapter(ExecutionAdapter):
    provider = "gcp"

    def resolve_action(self, capability: str, incident: NormalizedIncident) -> dict[str, Any]:
        action = _action_for(capability, incident.resource_type)
        return {
            "provider": "gcp",
            "capability": capability,
            "action": action,
            "parameters": _parameters_for(action, incident),
        }

    def parameters_for_action(self, action: str, incident: NormalizedIncident) -> dict[str, list[str]]:
        return _parameters_for(action, incident)


def _action_for(capability: str, resource_type: str) -> str:
    mapping = {
        ("restart_workload", "kubernetes-workload"): "GCP-RolloutRestartGKEWorkload",
        ("scale_out", "kubernetes-workload"): "GCP-ScaleGKEWorkload",
        ("scale_out", "network-endpoint"): "GCP-ScaleGKEWorkload",
        ("increase_function_concurrency", "serverless-service"): "GCP-ScaleCloudRunService",
        ("increase_function_concurrency", "lambda-function"): "GCP-ScaleCloudRunService",
        ("scale_database_primary", "database-instance"): "GCP-ScaleCloudSqlInstance",
        ("scale_database_read", "database-instance"): "GCP-CreateCloudSqlReadReplica",
        ("scale_out_workers", "streaming-consumer"): "GCP-ScalePubSubWorkers",
        ("rebalance_consumer", "streaming-consumer"): "GCP-RebalancePubSubSubscription",
        ("rollback_release", "kubernetes-workload"): "GCP-RollbackGKEWorkload",
        ("rollback_release", "serverless-service"): "GCP-RollbackCloudRunRevision",
        ("cleanup_disk_space", "storage-volume"): "GCP-CleanupPersistentDisk",
        ("cleanup_disk_space", "kubernetes-workload"): "GCP-CleanupPersistentDisk",
        ("cleanup_disk_space", "database-instance"): "GCP-CleanupCloudSqlStorage",
        ("expand_storage", "storage-volume"): "GCP-ExpandPersistentDisk",
        ("expand_storage", "kubernetes-workload"): "GCP-ExpandPersistentDisk",
        ("expand_storage", "database-instance"): "GCP-ExpandCloudSqlStorage",
        ("renew_certificate", "certificate"): "GCP-RenewManagedCertificate",
        ("renew_certificate", "cloud-resource"): "GCP-RenewManagedCertificate",
        ("drain_node", "network-endpoint"): "GCP-DrainGKENode",
        ("drain_node", "kubernetes-workload"): "GCP-DrainGKENode",
        ("open_change_request", "cloud-resource"): "GCP-NotifyOperations",
        ("open_change_request", "kubernetes-workload"): "GCP-NotifyOperations",
        ("open_change_request", "serverless-service"): "GCP-NotifyOperations",
        ("open_change_request", "database-instance"): "GCP-NotifyOperations",
        ("open_change_request", "streaming-consumer"): "GCP-NotifyOperations",
        ("open_change_request", "certificate"): "GCP-NotifyOperations",
        ("open_change_request", "storage-volume"): "GCP-NotifyOperations",
        ("open_change_request", "network-endpoint"): "GCP-NotifyOperations",
    }
    action = mapping.get((capability, resource_type))
    if action:
        return action
    raise ValueError(f"Unsupported GCP capability mapping: {capability} for {resource_type}")


def _parameters_for(action: str, incident: NormalizedIncident) -> dict[str, list[str]]:
    metadata = incident.source_metadata or {}
    labels = metadata.get("resource_labels", {}) if isinstance(metadata, dict) else {}

    if action in {"GCP-RolloutRestartGKEWorkload", "GCP-ScaleGKEWorkload", "GCP-DrainGKENode", "GCP-RollbackGKEWorkload"}:
        return _compact(
            {
                "ProjectId": [metadata.get("project_id", "")],
                "ClusterName": [labels.get("cluster_name", "")],
                "Namespace": [labels.get("namespace_name", "")],
                "WorkloadName": [incident.service],
            }
        )

    if action in {"GCP-ScaleCloudRunService", "GCP-RollbackCloudRunRevision"}:
        return _compact(
            {
                "ProjectId": [metadata.get("project_id", "")],
                "Region": [labels.get("location", "")],
                "ServiceName": [incident.resource_id],
            }
        )

    if action in {"GCP-ScaleCloudSqlInstance", "GCP-CreateCloudSqlReadReplica", "GCP-ExpandCloudSqlStorage", "GCP-CleanupCloudSqlStorage"}:
        return _compact(
            {
                "ProjectId": [metadata.get("project_id", "")],
                "InstanceName": [incident.resource_id],
            }
        )

    if action in {"GCP-ScalePubSubWorkers", "GCP-RebalancePubSubSubscription"}:
        return _compact(
            {
                "ProjectId": [metadata.get("project_id", "")],
                "SubscriptionId": [incident.resource_id],
            }
        )

    if action in {"GCP-CleanupPersistentDisk", "GCP-ExpandPersistentDisk"}:
        return _compact(
            {
                "ProjectId": [metadata.get("project_id", "")],
                "DiskName": [labels.get("disk_name", incident.resource_id)],
                "Zone": [labels.get("zone", "")],
            }
        )

    if action == "GCP-RenewManagedCertificate":
        return _compact(
            {
                "ProjectId": [metadata.get("project_id", "")],
                "CertificateName": [incident.resource_id],
            }
        )

    return _compact({"IncidentName": [metadata.get("policy_name", incident.resource_id)]})


def _compact(values: dict[str, list[str]]) -> dict[str, list[str]]:
    return {key: value for key, value in values.items() if value and value[0]}
