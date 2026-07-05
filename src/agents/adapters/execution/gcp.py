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
        ("increase_function_concurrency", "serverless-service"): "GCP-ScaleCloudRunService",
        ("scale_database_read", "database-instance"): "GCP-CreateCloudSqlReadReplica",
        ("scale_out_workers", "streaming-consumer"): "GCP-ScalePubSubWorkers",
        ("open_change_request", "cloud-resource"): "GCP-NotifyOperations",
        ("open_change_request", "kubernetes-workload"): "GCP-NotifyOperations",
        ("open_change_request", "serverless-service"): "GCP-NotifyOperations",
        ("open_change_request", "database-instance"): "GCP-NotifyOperations",
        ("open_change_request", "streaming-consumer"): "GCP-NotifyOperations",
    }
    action = mapping.get((capability, resource_type))
    if action:
        return action
    raise ValueError(f"Unsupported GCP capability mapping: {capability} for {resource_type}")


def _parameters_for(action: str, incident: NormalizedIncident) -> dict[str, list[str]]:
    metadata = incident.source_metadata or {}
    labels = metadata.get("resource_labels", {}) if isinstance(metadata, dict) else {}

    if action in {"GCP-RolloutRestartGKEWorkload", "GCP-ScaleGKEWorkload"}:
        return _compact(
            {
                "ProjectId": [metadata.get("project_id", "")],
                "ClusterName": [labels.get("cluster_name", "")],
                "Namespace": [labels.get("namespace_name", "")],
                "WorkloadName": [incident.service],
            }
        )

    if action == "GCP-ScaleCloudRunService":
        return _compact(
            {
                "ProjectId": [metadata.get("project_id", "")],
                "Region": [labels.get("location", "")],
                "ServiceName": [incident.resource_id],
            }
        )

    if action == "GCP-CreateCloudSqlReadReplica":
        return _compact(
            {
                "ProjectId": [metadata.get("project_id", "")],
                "InstanceName": [incident.resource_id],
            }
        )

    if action == "GCP-ScalePubSubWorkers":
        return _compact(
            {
                "ProjectId": [metadata.get("project_id", "")],
                "SubscriptionId": [incident.resource_id],
            }
        )

    return _compact({"IncidentName": [metadata.get("policy_name", incident.resource_id)]})


def _compact(values: dict[str, list[str]]) -> dict[str, list[str]]:
    return {key: value for key, value in values.items() if value and value[0]}
