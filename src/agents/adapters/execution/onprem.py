"""
On-prem execution capability resolution helpers.
"""

from __future__ import annotations

from typing import Any

from src.agents.adapters.base import ExecutionAdapter
from src.agents.models import NormalizedIncident


class OnPremExecutionAdapter(ExecutionAdapter):
    provider = "onprem"

    def resolve_action(self, capability: str, incident: NormalizedIncident) -> dict[str, Any]:
        action = _action_for(capability, incident.resource_type)
        return {
            "provider": "onprem",
            "capability": capability,
            "action": action,
            "parameters": _parameters_for(action, incident),
        }

    def parameters_for_action(self, action: str, incident: NormalizedIncident) -> dict[str, list[str]]:
        return _parameters_for(action, incident)


def _action_for(capability: str, resource_type: str) -> str:
    mapping = {
        ("restart_workload", "kubernetes-workload"): "ONPREM-RolloutRestartWorkload",
        ("restart_workload", "serverless-service"): "ONPREM-RolloutRestartWorkload",
        ("scale_out", "kubernetes-workload"): "ONPREM-ScaleWorkload",
        ("scale_out", "network-endpoint"): "ONPREM-ScaleWorkload",
        ("rollback_release", "kubernetes-workload"): "ONPREM-ArgoRolloutRollback",
        ("rollback_release", "serverless-service"): "ONPREM-ArgoRolloutRollback",
        ("scale_database_primary", "database-instance"): "ONPREM-ScaleDatabasePrimary",
        ("scale_database_read", "database-instance"): "ONPREM-ScaleReadReplica",
        ("scale_out_workers", "streaming-consumer"): "ONPREM-ScaleConsumerWorkers",
        ("rebalance_consumer", "streaming-consumer"): "ONPREM-RebalanceConsumerGroup",
        ("cleanup_disk_space", "storage-volume"): "ONPREM-CleanupDiskSpace",
        ("cleanup_disk_space", "kubernetes-workload"): "ONPREM-CleanupDiskSpace",
        ("cleanup_disk_space", "database-instance"): "ONPREM-CleanupDiskSpace",
        ("expand_storage", "storage-volume"): "ONPREM-ExpandVolume",
        ("expand_storage", "kubernetes-workload"): "ONPREM-ExpandVolume",
        ("expand_storage", "database-instance"): "ONPREM-ExpandVolume",
        ("renew_certificate", "certificate"): "ONPREM-RenewCertificate",
        ("renew_certificate", "cloud-resource"): "ONPREM-RenewCertificate",
        ("drain_node", "network-endpoint"): "ONPREM-DrainNode",
        ("drain_node", "kubernetes-workload"): "ONPREM-DrainNode",
        ("open_change_request", "cloud-resource"): "ONPREM-CreateChangeRequest",
        ("open_change_request", "kubernetes-workload"): "ONPREM-CreateChangeRequest",
        ("open_change_request", "database-instance"): "ONPREM-CreateChangeRequest",
        ("open_change_request", "streaming-consumer"): "ONPREM-CreateChangeRequest",
        ("open_change_request", "serverless-service"): "ONPREM-CreateChangeRequest",
        ("open_change_request", "certificate"): "ONPREM-CreateChangeRequest",
        ("open_change_request", "storage-volume"): "ONPREM-CreateChangeRequest",
        ("open_change_request", "network-endpoint"): "ONPREM-CreateChangeRequest",
    }
    action = mapping.get((capability, resource_type))
    if action:
        return action
    raise ValueError(f"Unsupported on-prem capability mapping: {capability} for {resource_type}")


def _parameters_for(action: str, incident: NormalizedIncident) -> dict[str, list[str]]:
    metadata = incident.source_metadata or {}
    labels = metadata.get("labels", {}) if isinstance(metadata, dict) else {}

    if action == "ONPREM-ScaleWorkload":
        # Scale is a desired-state action: carry the target replica count from the
        # alert labels so the runner can `kubectl scale --replicas=N`. Absent the
        # count, the param is dropped and the runner stays log-only.
        return _compact(
            {
                "ClusterName": [labels.get("cluster", "")],
                "Namespace": [labels.get("namespace", "")],
                "WorkloadName": [incident.service],
                "DesiredReplicas": [str(labels.get("desired_replicas", labels.get("replicas", "")))],
            }
        )

    if action == "ONPREM-DrainNode":
        # Node-level action: carry the node name (not a workload) from the alert
        # labels so the runner can `kubectl drain <node>`. Absent a node, the param
        # is dropped and the runner stays log-only.
        return _compact(
            {
                "ClusterName": [labels.get("cluster", "")],
                "NodeName": [labels.get("node", labels.get("instance", ""))],
            }
        )

    if action in {
        "ONPREM-RolloutRestartWorkload",
        "ONPREM-ArgoRolloutRollback",
    }:
        return _compact(
            {
                "ClusterName": [labels.get("cluster", "")],
                "Namespace": [labels.get("namespace", "")],
                "WorkloadName": [incident.service],
            }
        )

    if action in {"ONPREM-ScaleReadReplica", "ONPREM-ScaleDatabasePrimary"}:
        return _compact({"DatabaseName": [incident.resource_id]})

    if action in {"ONPREM-ScaleConsumerWorkers", "ONPREM-RebalanceConsumerGroup"}:
        return _compact({"ConsumerGroup": [incident.resource_id]})

    if action in {"ONPREM-CleanupDiskSpace", "ONPREM-ExpandVolume"}:
        return _compact(
            {
                "NodeName": [labels.get("node", "")],
                "VolumeName": [labels.get("volume", incident.resource_id)],
            }
        )

    if action == "ONPREM-RenewCertificate":
        return _compact({"CertificateName": [incident.resource_id]})

    return _compact({"AlertName": [metadata.get("alertname", incident.resource_id)]})


def _compact(values: dict[str, list[str]]) -> dict[str, list[str]]:
    return {key: value for key, value in values.items() if value and value[0]}
