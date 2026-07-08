"""
Built-in runbook catalog used by decision logic and deployment seeding.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

BUILTIN_RUNBOOKS: dict[str, dict[str, Any]] = {
    "eks-pod-oom": {
        "runbook_id": "eks-pod-oom",
        "namespaces": ["AWS/EKS"],
        "keywords": ["OOM", "MemoryPressure", "pod_restart"],
        "capabilities": ["restart_workload", "scale_out"],
        "actions": ["AWS-RestartEKSPod", "AWS-ScaleOutEKSNodeGroup"],
        "rto_sec": 180,
        "provider": "aws",
        "resource_types": ["kubernetes-workload"],
    },
    "lambda-throttle": {
        "runbook_id": "lambda-throttle",
        "namespaces": ["AWS/Lambda"],
        "keywords": ["Throttles", "throttl"],
        "capabilities": ["increase_function_concurrency"],
        "actions": ["AWS-IncreaseLambdaConcurrency"],
        "rto_sec": 60,
        "provider": "aws",
        "resource_types": ["lambda-function"],
    },
    "rds-cpu-high": {
        "runbook_id": "rds-cpu-high",
        "namespaces": ["AWS/RDS"],
        "keywords": ["CPUUtilization", "cpu"],
        "capabilities": ["scale_database_primary", "scale_database_read"],
        "actions": ["AWS-ScaleRDSInstance", "AWS-CreateRDSReadReplica"],
        "rto_sec": 600,
        "provider": "aws",
        "resource_types": ["database-instance"],
    },
    "kafka-lag-spike": {
        "runbook_id": "kafka-lag-spike",
        "namespaces": ["AWS/Kafka", "Custom/Kafka"],
        "keywords": ["lag", "ConsumerLag", "offset"],
        "capabilities": ["scale_out_workers"],
        "actions": ["AWS-ScaleOutKafkaConsumerGroup"],
        "rto_sec": 300,
        "provider": "aws",
        "resource_types": ["streaming-consumer"],
    },
    "generic-recovery": {
        "runbook_id": "generic-recovery",
        "namespaces": [],
        "keywords": [],
        "capabilities": ["open_change_request"],
        "actions": ["AWS-SendSlackAlert"],
        "rto_sec": None,
        "provider": "aws",
        "resource_types": ["cloud-resource"],
    },
}


def builtin_runbook_items() -> list[dict[str, Any]]:
    """
    Return DynamoDB-ready items for the built-in runbook catalog.
    """
    items: list[dict[str, Any]] = []
    for alarm_name, runbook in BUILTIN_RUNBOOKS.items():
        item = deepcopy(runbook)
        item["alarm_name"] = alarm_name
        items.append(item)
    return items


# --- Capability-based runbook catalog (cloud-neutral steps) ---

CAPABILITY_RUNBOOKS: dict[str, dict[str, Any]] = {
    "eks-pod-oom": {
        "runbook_id": "eks-pod-oom",
        "description": "Recover from pod OOMKilled by restarting then scaling",
        "resource_types": ["kubernetes-workload"],
        "rto_sec": 180,
        "steps": [
            {
                "name": "restart_pod",
                "capability": "restart_workload",
                "description": "Restart the OOMKilled pod with grace period",
                "parameters": {"grace_period_sec": 30},
                "on_failure": "continue",
            },
            {
                "name": "scale_nodes",
                "capability": "scale_out",
                "description": "Scale out node group if restart didn't recover",
                "condition": {"previous_step_failed": True},
                "parameters": {"increment": 1, "max_nodes": 10},
                "on_failure": "abort",
            },
        ],
    },
    "lambda-throttle": {
        "runbook_id": "lambda-throttle",
        "description": "Increase reserved concurrency for throttled function",
        "resource_types": ["lambda-function"],
        "rto_sec": 60,
        "steps": [
            {
                "name": "increase_concurrency",
                "capability": "increase_function_concurrency",
                "description": "Bump reserved concurrency by increment",
                "parameters": {"increment": 50, "max_concurrency": 1000},
                "on_failure": "abort",
            },
        ],
    },
    "rds-cpu-high": {
        "runbook_id": "rds-cpu-high",
        "description": "Scale RDS instance or add read replica for CPU pressure",
        "resource_types": ["database-instance"],
        "rto_sec": 600,
        "steps": [
            {
                "name": "scale_primary",
                "capability": "scale_database_primary",
                "description": "Vertically scale the primary instance",
                "parameters": {"target_class_increment": 1},
                "on_failure": "continue",
            },
            {
                "name": "add_read_replica",
                "capability": "scale_database_read",
                "description": "Add a read replica to offload read traffic",
                "condition": {"previous_step_failed": True},
                "parameters": {},
                "on_failure": "abort",
            },
        ],
    },
    "kafka-lag-spike": {
        "runbook_id": "kafka-lag-spike",
        "description": "Scale consumer group to reduce lag",
        "resource_types": ["streaming-consumer"],
        "rto_sec": 300,
        "steps": [
            {
                "name": "scale_consumers",
                "capability": "scale_out_workers",
                "description": "Add consumer instances to the group",
                "parameters": {"increment": 2, "max_consumers": 20},
                "on_failure": "abort",
            },
        ],
    },
    "generic-recovery": {
        "runbook_id": "generic-recovery",
        "description": "Open a change request for manual review",
        "resource_types": ["cloud-resource"],
        "rto_sec": None,
        "steps": [
            {
                "name": "notify",
                "capability": "open_change_request",
                "description": "Send Slack alert for human review",
                "parameters": {},
                "on_failure": "abort",
            },
        ],
    },
}
