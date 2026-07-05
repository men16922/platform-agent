"""
AWS execution capability resolution helpers.
"""

from __future__ import annotations

from typing import Any

from src.agents.adapters.base import ExecutionAdapter
from src.agents.models import NormalizedIncident


class AwsSsmExecutionAdapter(ExecutionAdapter):
    provider = "aws"

    def resolve_action(self, capability: str, incident: NormalizedIncident) -> dict[str, Any]:
        action = _action_for(capability, incident)
        return {
            "provider": "aws",
            "capability": capability,
            "action": action,
            "parameters": _parameters_for(action, incident),
        }

    def parameters_for_action(self, action: str, incident: NormalizedIncident) -> dict[str, list[str]]:
        return _parameters_for(action, incident)


def _action_for(capability: str, incident: NormalizedIncident) -> str:
    resource_type = incident.resource_type
    mapping = {
        ("restart_workload", "kubernetes-workload"): "AWS-RestartEKSPod",
        ("scale_out", "kubernetes-workload"): "AWS-ScaleOutEKSNodeGroup",
        ("increase_function_concurrency", "lambda-function"): "AWS-IncreaseLambdaConcurrency",
        ("scale_database_primary", "database-instance"): "AWS-ScaleRDSInstance",
        ("scale_database_read", "database-instance"): "AWS-CreateRDSReadReplica",
        ("scale_out_workers", "streaming-consumer"): "AWS-ScaleOutKafkaConsumerGroup",
        ("open_change_request", "cloud-resource"): "AWS-SendSlackAlert",
        ("open_change_request", "kubernetes-workload"): "AWS-SendSlackAlert",
        ("open_change_request", "lambda-function"): "AWS-SendSlackAlert",
        ("open_change_request", "database-instance"): "AWS-SendSlackAlert",
        ("open_change_request", "streaming-consumer"): "AWS-SendSlackAlert",
    }
    action = mapping.get((capability, resource_type))
    if action:
        return action
    raise ValueError(f"Unsupported AWS capability mapping: {capability} for {resource_type}")


def _parameters_for(action: str, incident: NormalizedIncident) -> dict[str, list[str]]:
    metadata = incident.source_metadata or {}
    dimensions = metadata.get("dimensions", {}) if isinstance(metadata, dict) else {}

    if action == "AWS-RestartEKSPod":
        return _compact(
            {
                "ClusterName": [dimensions.get("ClusterName", "")],
                "Namespace": [dimensions.get("Namespace", "default")],
                "PodName": [dimensions.get("PodName", incident.resource_id)],
            }
        )

    if action == "AWS-ScaleOutEKSNodeGroup":
        return _compact(
            {
                "ClusterName": [dimensions.get("ClusterName", incident.service)],
                "NodeGroupName": [dimensions.get("NodeGroupName", "")],
            }
        )

    if action == "AWS-IncreaseLambdaConcurrency":
        return _compact({"FunctionName": [dimensions.get("FunctionName", incident.resource_id)]})

    if action == "AWS-ScaleRDSInstance":
        return _compact({"DBInstanceIdentifier": [dimensions.get("DBInstanceIdentifier", incident.resource_id)]})

    if action == "AWS-CreateRDSReadReplica":
        return _compact({"DBInstanceIdentifier": [dimensions.get("DBInstanceIdentifier", incident.resource_id)]})

    if action == "AWS-ScaleOutKafkaConsumerGroup":
        return _compact(
            {
                "ClusterName": [dimensions.get("ClusterName", incident.service)],
                "ConsumerGroup": [dimensions.get("ConsumerGroup", incident.resource_id)],
            }
        )

    return _compact({"AlarmName": [metadata.get("alarm_name", incident.resource_id)]})


def _compact(values: dict[str, list[str]]) -> dict[str, list[str]]:
    return {key: value for key, value in values.items() if value and value[0]}
