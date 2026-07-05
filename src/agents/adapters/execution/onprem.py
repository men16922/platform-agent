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
        ("scale_out", "kubernetes-workload"): "ONPREM-ScaleWorkload",
        ("rollback_release", "kubernetes-workload"): "ONPREM-ArgoRolloutRollback",
        ("scale_database_read", "database-instance"): "ONPREM-ScaleReadReplica",
        ("scale_out_workers", "streaming-consumer"): "ONPREM-ScaleConsumerWorkers",
        ("rebalance_consumer", "streaming-consumer"): "ONPREM-RebalanceConsumerGroup",
        ("open_change_request", "cloud-resource"): "ONPREM-CreateChangeRequest",
        ("open_change_request", "kubernetes-workload"): "ONPREM-CreateChangeRequest",
        ("open_change_request", "database-instance"): "ONPREM-CreateChangeRequest",
        ("open_change_request", "streaming-consumer"): "ONPREM-CreateChangeRequest",
    }
    action = mapping.get((capability, resource_type))
    if action:
        return action
    raise ValueError(f"Unsupported on-prem capability mapping: {capability} for {resource_type}")


def _parameters_for(action: str, incident: NormalizedIncident) -> dict[str, list[str]]:
    metadata = incident.source_metadata or {}
    labels = metadata.get("labels", {}) if isinstance(metadata, dict) else {}

    if action in {
        "ONPREM-RolloutRestartWorkload",
        "ONPREM-ScaleWorkload",
        "ONPREM-ArgoRolloutRollback",
    }:
        return _compact(
            {
                "ClusterName": [labels.get("cluster", "")],
                "Namespace": [labels.get("namespace", "")],
                "WorkloadName": [incident.service],
            }
        )

    if action == "ONPREM-ScaleReadReplica":
        return _compact({"DatabaseName": [incident.resource_id]})

    if action in {"ONPREM-ScaleConsumerWorkers", "ONPREM-RebalanceConsumerGroup"}:
        return _compact({"ConsumerGroup": [incident.resource_id]})

    return _compact({"AlertName": [metadata.get("alertname", incident.resource_id)]})


def _compact(values: dict[str, list[str]]) -> dict[str, list[str]]:
    return {key: value for key, value in values.items() if value and value[0]}
