"""
Tests for provider adapter scaffolding.
"""

from __future__ import annotations

from src.agents.adapters.execution.aws import AwsSsmExecutionAdapter
from src.agents.adapters.signals.aws import AwsCloudWatchSignalAdapter
from src.agents.models import AlarmContext, NormalizedIncident


class TestAwsCloudWatchSignalAdapter:
    def test_normalise_eks_alarm_context(self):
        adapter = AwsCloudWatchSignalAdapter()
        alarm = AlarmContext(
            alarm_name="eks-pod-oom",
            alarm_arn="arn:aws:cloudwatch:ap-northeast-2:123456789:alarm:eks-pod-oom",
            state="ALARM",
            reason="OOMKilled in checkout-api pod",
            metric_name="pod_restart_total",
            namespace="AWS/EKS",
            dimensions={
                "ClusterName": "prod-eks",
                "Namespace": "checkout",
                "PodName": "checkout-api-7d9f6b88d8-xk2lm",
            },
        )

        incident = adapter.from_alarm_context(alarm, observations={"logs": ["OOMKilled"]})

        assert incident.provider == "aws"
        assert incident.service == "checkout-api"
        assert incident.resource_type == "kubernetes-workload"
        assert incident.resource_id == "checkout-api-7d9f6b88d8-xk2lm"
        assert incident.signal_type == "reliability"
        assert incident.recommended_capabilities == ["restart_workload", "scale_out", "open_change_request"]

    def test_normalise_lambda_event(self):
        adapter = AwsCloudWatchSignalAdapter()
        event = {
            "resources": ["arn:aws:cloudwatch:ap-northeast-2:123456789:alarm:lambda-throttle"],
            "detail": {
                "alarmName": "lambda-throttle",
                "state": {"value": "ALARM", "reason": "Throttle detected"},
                "configuration": {
                    "metrics": [
                        {
                            "metricStat": {
                                "metric": {
                                    "name": "Throttles",
                                    "namespace": "AWS/Lambda",
                                    "dimensions": [{"name": "FunctionName", "value": "checkout-handler"}],
                                }
                            }
                        }
                    ]
                },
            },
        }

        incident = adapter.normalise(event)

        assert incident.service == "checkout-handler"
        assert incident.resource_type == "lambda-function"
        assert incident.recommended_capabilities == ["increase_function_concurrency", "open_change_request"]


class TestAwsSsmExecutionAdapter:
    def test_resolve_restart_workload(self):
        adapter = AwsSsmExecutionAdapter()
        incident = NormalizedIncident(
            provider="aws",
            service="checkout-api",
            resource_type="kubernetes-workload",
            resource_id="checkout-api-7d9f6b88d8-xk2lm",
            signal_type="reliability",
            source_metadata={
                "alarm_name": "eks-pod-oom",
                "dimensions": {
                    "ClusterName": "prod-eks",
                    "Namespace": "checkout",
                    "PodName": "checkout-api-7d9f6b88d8-xk2lm",
                },
            },
        )

        action = adapter.resolve_action("restart_workload", incident)

        assert action["action"] == "AWS-RestartEKSPod"
        assert action["parameters"]["ClusterName"] == ["prod-eks"]
        assert action["parameters"]["Namespace"] == ["checkout"]

    def test_resolve_lambda_concurrency(self):
        adapter = AwsSsmExecutionAdapter()
        incident = NormalizedIncident(
            provider="aws",
            service="checkout-handler",
            resource_type="lambda-function",
            resource_id="checkout-handler",
            signal_type="capacity",
            source_metadata={"alarm_name": "lambda-throttle", "dimensions": {"FunctionName": "checkout-handler"}},
        )

        action = adapter.resolve_action("increase_function_concurrency", incident)

        assert action["action"] == "AWS-IncreaseLambdaConcurrency"
        assert action["parameters"]["FunctionName"] == ["checkout-handler"]

    def test_resolve_rds_primary_scale(self):
        adapter = AwsSsmExecutionAdapter()
        incident = NormalizedIncident(
            provider="aws",
            service="prod-db",
            resource_type="database-instance",
            resource_id="prod-db",
            signal_type="capacity",
            source_metadata={
                "alarm_name": "rds-cpu-high",
                "dimensions": {"DBInstanceIdentifier": "prod-db"},
            },
        )

        action = adapter.resolve_action("scale_database_primary", incident)

        assert action["action"] == "AWS-ScaleRDSInstance"
        assert action["parameters"]["DBInstanceIdentifier"] == ["prod-db"]
