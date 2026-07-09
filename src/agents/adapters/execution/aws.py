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
        ("scale_out", "network-endpoint"): "AWS-ScaleOutEKSNodeGroup",
        ("increase_function_concurrency", "lambda-function"): "AWS-IncreaseLambdaConcurrency",
        ("increase_function_concurrency", "serverless-service"): "AWS-IncreaseLambdaConcurrency",
        ("scale_database_primary", "database-instance"): "AWS-ScaleRDSInstance",
        ("scale_database_read", "database-instance"): "AWS-CreateRDSReadReplica",
        ("scale_out_workers", "streaming-consumer"): "AWS-ScaleOutKafkaConsumerGroup",
        ("rebalance_consumer", "streaming-consumer"): "AWS-RebalanceKafkaConsumerGroup",
        ("rollback_release", "kubernetes-workload"): "AWS-RollbackEKSDeployment",
        ("rollback_release", "serverless-service"): "AWS-RollbackLambdaAlias",
        ("cleanup_disk_space", "storage-volume"): "AWS-CleanupEBSVolume",
        ("cleanup_disk_space", "kubernetes-workload"): "AWS-CleanupEBSVolume",
        ("cleanup_disk_space", "database-instance"): "AWS-CleanupRDSStorage",
        ("expand_storage", "storage-volume"): "AWS-ExpandEBSVolume",
        ("expand_storage", "kubernetes-workload"): "AWS-ExpandEBSVolume",
        ("expand_storage", "database-instance"): "AWS-ExpandRDSStorage",
        ("renew_certificate", "certificate"): "AWS-RenewACMCertificate",
        ("renew_certificate", "cloud-resource"): "AWS-RenewACMCertificate",
        ("drain_node", "network-endpoint"): "AWS-DrainEKSNode",
        ("drain_node", "kubernetes-workload"): "AWS-DrainEKSNode",
        ("open_change_request", "cloud-resource"): "AWS-SendSlackAlert",
        ("open_change_request", "kubernetes-workload"): "AWS-SendSlackAlert",
        ("open_change_request", "lambda-function"): "AWS-SendSlackAlert",
        ("open_change_request", "serverless-service"): "AWS-SendSlackAlert",
        ("open_change_request", "database-instance"): "AWS-SendSlackAlert",
        ("open_change_request", "streaming-consumer"): "AWS-SendSlackAlert",
        ("open_change_request", "certificate"): "AWS-SendSlackAlert",
        ("open_change_request", "storage-volume"): "AWS-SendSlackAlert",
        ("open_change_request", "network-endpoint"): "AWS-SendSlackAlert",
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

    if action in {"AWS-ScaleOutEKSNodeGroup", "AWS-DrainEKSNode"}:
        return _compact(
            {
                "ClusterName": [dimensions.get("ClusterName", incident.service)],
                "NodeGroupName": [dimensions.get("NodeGroupName", "")],
            }
        )

    if action == "AWS-RollbackEKSDeployment":
        return _compact(
            {
                "ClusterName": [dimensions.get("ClusterName", incident.service)],
                "Namespace": [dimensions.get("Namespace", "default")],
                "DeploymentName": [dimensions.get("DeploymentName", incident.resource_id)],
            }
        )

    if action in {"AWS-IncreaseLambdaConcurrency", "AWS-RollbackLambdaAlias"}:
        return _compact({"FunctionName": [dimensions.get("FunctionName", incident.resource_id)]})

    if action in {"AWS-ScaleRDSInstance", "AWS-CreateRDSReadReplica", "AWS-ExpandRDSStorage", "AWS-CleanupRDSStorage"}:
        return _compact({"DBInstanceIdentifier": [dimensions.get("DBInstanceIdentifier", incident.resource_id)]})

    if action in {"AWS-ScaleOutKafkaConsumerGroup", "AWS-RebalanceKafkaConsumerGroup"}:
        return _compact(
            {
                "ClusterName": [dimensions.get("ClusterName", incident.service)],
                "ConsumerGroup": [dimensions.get("ConsumerGroup", incident.resource_id)],
            }
        )

    if action in {"AWS-CleanupEBSVolume", "AWS-ExpandEBSVolume"}:
        return _compact(
            {
                "VolumeId": [dimensions.get("VolumeId", incident.resource_id)],
            }
        )

    if action == "AWS-RenewACMCertificate":
        return _compact(
            {
                "CertificateArn": [dimensions.get("CertificateArn", incident.resource_id)],
            }
        )

    return _compact({"AlarmName": [metadata.get("alarm_name", incident.resource_id)]})


def _compact(values: dict[str, list[str]]) -> dict[str, list[str]]:
    return {key: value for key, value in values.items() if value and value[0]}
