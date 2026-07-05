"""
Tests for non-AWS portability adapter scaffolding.
"""

from __future__ import annotations

import pytest

from src.agents.adapters import get_execution_adapter, get_signal_adapter, supported_providers
from src.agents.adapters.execution.azure import AzureExecutionAdapter
from src.agents.adapters.execution.gcp import GcpExecutionAdapter
from src.agents.adapters.execution.onprem import OnPremExecutionAdapter
from src.agents.adapters.signals.azure import AzureMonitorSignalAdapter
from src.agents.adapters.signals.gcp import GcpMonitoringSignalAdapter
from src.agents.adapters.signals.onprem import OnPremAlertmanagerSignalAdapter


class TestSignalRegistry:
    def test_supported_providers(self):
        assert supported_providers() == ["aws", "azure", "gcp", "onprem"]

    def test_get_signal_adapter(self):
        assert isinstance(get_signal_adapter("gcp"), GcpMonitoringSignalAdapter)
        assert isinstance(get_signal_adapter("azure"), AzureMonitorSignalAdapter)
        assert isinstance(get_signal_adapter("onprem"), OnPremAlertmanagerSignalAdapter)

    def test_get_execution_adapter(self):
        assert isinstance(get_execution_adapter("gcp"), GcpExecutionAdapter)
        assert isinstance(get_execution_adapter("azure"), AzureExecutionAdapter)
        assert isinstance(get_execution_adapter("onprem"), OnPremExecutionAdapter)

    def test_unknown_provider_raises(self):
        with pytest.raises(ValueError):
            get_signal_adapter("unknown")


class TestGcpAdapter:
    def test_normalise_gke_incident(self):
        adapter = GcpMonitoringSignalAdapter()
        event = {
            "incident": {
                "policy_name": "gke-checkout-latency",
                "condition_name": "request-latency",
                "summary": "checkout latency is elevated",
                "severity": "high",
                "started_at": "2026-04-12T01:00:00Z",
                "scoping_project_id": "platform-prod",
                "resource": {
                    "type": "k8s_container",
                    "labels": {
                        "cluster_name": "prod-gke",
                        "namespace_name": "checkout",
                        "pod_name": "checkout-api-77f6d9f8b7-12345",
                    },
                },
                "metric": {"type": "kubernetes.io/container/cpu/core_usage_time"},
            }
        }

        incident = adapter.normalise(event)

        assert incident.provider == "gcp"
        assert incident.resource_type == "kubernetes-workload"
        assert incident.service == "checkout-api"
        assert incident.recommended_capabilities == ["restart_workload", "scale_out", "open_change_request"]

    def test_resolve_gcp_serverless_action(self):
        incident = get_signal_adapter("gcp").normalise(
            {
                "incident": {
                    "policy_name": "cloud-run-throttle",
                    "summary": "concurrency saturation on checkout-run",
                    "resource": {
                        "type": "cloud_run_revision",
                        "labels": {"revision_name": "checkout-run-00012-abc", "location": "asia-northeast3"},
                    },
                    "metric": {"type": "run.googleapis.com/container/instance_count"},
                    "scoping_project_id": "platform-prod",
                }
            }
        )
        action = get_execution_adapter("gcp").resolve_action("increase_function_concurrency", incident)

        assert action["action"] == "GCP-ScaleCloudRunService"
        assert action["parameters"]["ProjectId"] == ["platform-prod"]
        assert action["parameters"]["ServiceName"] == ["checkout-run-00012-abc"]


class TestAzureAdapter:
    def test_normalise_aks_alert(self):
        adapter = AzureMonitorSignalAdapter()
        event = {
            "data": {
                "essentials": {
                    "alertRule": "aks-checkout-high-cpu",
                    "severity": "Sev2",
                    "monitorCondition": "Fired",
                    "description": "CPU high in checkout pod",
                    "firedDateTime": "2026-04-12T01:10:00Z",
                    "targetResourceType": "Microsoft.ContainerService/managedClusters",
                    "alertTargetIDs": ["/subscriptions/test/resourceGroups/rg/providers/Microsoft.ContainerService/managedClusters/prod-aks"],
                },
                "alertContext": {
                    "condition": {
                        "allOf": [
                            {
                                "metricName": "CpuUsage",
                                "dimensions": [
                                    {"name": "Pod", "value": "checkout-api-7d9f6b88d8-abcde"},
                                    {"name": "Namespace", "value": "checkout"},
                                ],
                            }
                        ]
                    }
                },
            }
        }

        incident = adapter.normalise(event)

        assert incident.provider == "azure"
        assert incident.resource_type == "kubernetes-workload"
        assert incident.service == "checkout-api"
        assert incident.signal_type == "capacity"

    def test_resolve_azure_restart(self):
        incident = get_signal_adapter("azure").normalise(
            {
                "data": {
                    "essentials": {
                        "alertRule": "aks-checkout-restart",
                        "targetResourceType": "Microsoft.ContainerService/managedClusters",
                        "alertTargetIDs": ["/subscriptions/test/managedClusters/prod-aks"],
                        "firedDateTime": "2026-04-12T01:10:00Z",
                    },
                    "alertContext": {
                        "condition": {
                            "allOf": [
                                {
                                    "metricName": "RestartCount",
                                    "dimensions": [
                                        {"name": "Pod", "value": "checkout-api-7d9f6b88d8-abcde"},
                                        {"name": "Namespace", "value": "checkout"},
                                    ],
                                }
                            ]
                        }
                    },
                }
            }
        )
        action = get_execution_adapter("azure").resolve_action("restart_workload", incident)

        assert action["action"] == "AZURE-RolloutRestartAKSWorkload"
        assert action["parameters"]["Namespace"] == ["checkout"]


class TestOnPremAdapter:
    def test_normalise_alertmanager_event(self):
        adapter = OnPremAlertmanagerSignalAdapter()
        event = {
            "status": "firing",
            "commonLabels": {
                "alertname": "KubePodCrashLooping",
                "service": "checkout-api",
                "namespace": "checkout",
                "cluster": "prod-k8s",
                "severity": "critical",
            },
            "commonAnnotations": {
                "summary": "checkout pod is restarting frequently",
                "description": "CrashLoopBackOff observed for checkout-api",
            },
            "alerts": [
                {
                    "startsAt": "2026-04-12T01:20:00Z",
                    "labels": {"pod": "checkout-api-7d9f6b88d8-abcde"},
                    "generatorURL": "http://prometheus.example.local/graph",
                }
            ],
        }

        incident = adapter.normalise(event)

        assert incident.provider == "onprem"
        assert incident.resource_type == "kubernetes-workload"
        assert incident.recommended_capabilities == [
            "restart_workload",
            "scale_out",
            "rollback_release",
            "open_change_request",
        ]

    def test_resolve_onprem_rollback(self):
        incident = get_signal_adapter("onprem").normalise(
            {
                "status": "firing",
                "commonLabels": {
                    "alertname": "KubeDeploymentReplicasMismatch",
                    "service": "checkout-api",
                    "namespace": "checkout",
                    "cluster": "prod-k8s",
                },
                "alerts": [
                    {
                        "startsAt": "2026-04-12T01:20:00Z",
                        "labels": {"pod": "checkout-api-7d9f6b88d8-abcde"},
                    }
                ],
            }
        )
        action = get_execution_adapter("onprem").resolve_action("rollback_release", incident)

        assert action["action"] == "ONPREM-ArgoRolloutRollback"
        assert action["parameters"]["ClusterName"] == ["prod-k8s"]
