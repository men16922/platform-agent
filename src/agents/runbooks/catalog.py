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
