"""Tests for the activity writer module — DynamoDB write path for dashboard read model."""

from unittest.mock import patch, MagicMock
import time

from src.agents.operations.activity_writer import (
    record_deployment,
    record_agent_activity,
    update_provider_health,
    TTL_30_DAYS,
    TTL_90_DAYS,
)


class TestRecordDeployment:
    """record_deployment writes a DEPLOY item with correct schema."""

    @patch("src.agents.operations.activity_writer._get_table")
    def test_writes_deployment_with_correct_pk(self, mock_table):
        table = MagicMock()
        mock_table.return_value = table

        dep_id = record_deployment(
            provider="aws",
            service="orders-api",
            version="v1.4.2",
            environment="production",
            status="success",
            agent="Strands Agent (Bedrock Claude)",
            duration_sec=45,
        )

        table.put_item.assert_called_once()
        item = table.put_item.call_args[1]["Item"]
        assert item["PK"] == "DEPLOY"
        assert dep_id in item["SK"]
        assert item["GSI1PK"] == "aws#DEPLOY"
        assert item["provider"] == "aws"
        assert item["service"] == "orders-api"
        assert item["version"] == "v1.4.2"
        assert item["status"] == "success"
        assert item["agent"] == "Strands Agent (Bedrock Claude)"
        assert item["duration_sec"] == 45

    @patch("src.agents.operations.activity_writer._get_table")
    def test_generates_deployment_id_if_not_provided(self, mock_table):
        mock_table.return_value = MagicMock()

        dep_id = record_deployment(provider="gcp", service="api", version="v1")
        assert dep_id.startswith("DEP-")
        assert len(dep_id) == 12  # DEP- + 8 hex chars

    @patch("src.agents.operations.activity_writer._get_table")
    def test_uses_provided_deployment_id(self, mock_table):
        table = MagicMock()
        mock_table.return_value = table

        dep_id = record_deployment(
            deployment_id="DEP-CUSTOM01",
            provider="azure",
            service="svc",
            version="v2",
        )
        assert dep_id == "DEP-CUSTOM01"
        item = table.put_item.call_args[1]["Item"]
        assert item["deployment_id"] == "DEP-CUSTOM01"

    @patch("src.agents.operations.activity_writer._get_table")
    def test_sets_ttl_30_days(self, mock_table):
        table = MagicMock()
        mock_table.return_value = table

        record_deployment(provider="onprem", service="svc", version="v1")
        item = table.put_item.call_args[1]["Item"]
        expected_ttl = int(time.time()) + TTL_30_DAYS
        assert abs(item["ttl"] - expected_ttl) < 5

    @patch("src.agents.operations.activity_writer._get_table")
    def test_handles_write_failure_gracefully(self, mock_table):
        table = MagicMock()
        table.put_item.side_effect = Exception("DynamoDB error")
        mock_table.return_value = table

        # Should not raise
        dep_id = record_deployment(provider="aws", service="svc", version="v1")
        assert dep_id.startswith("DEP-")


class TestRecordAgentActivity:
    """record_agent_activity writes an ACTIVITY item with correct schema."""

    @patch("src.agents.operations.activity_writer._get_table")
    def test_writes_activity_with_correct_pk(self, mock_table):
        table = MagicMock()
        mock_table.return_value = table

        act_id = record_agent_activity(
            agent="Executor (AWS)",
            provider="aws",
            action="Incident remediation: eks-pod-oom (INC-ABC123)",
            tool_calls=["AWS-RestartEKSPod", "AWS-ScaleNodeGroup"],
            status="success",
        )

        table.put_item.assert_called_once()
        item = table.put_item.call_args[1]["Item"]
        assert item["PK"] == "ACTIVITY"
        assert act_id in item["SK"]
        assert item["GSI1PK"] == "aws#ACTIVITY"
        assert item["agent"] == "Executor (AWS)"
        assert item["tool_calls"] == ["AWS-RestartEKSPod", "AWS-ScaleNodeGroup"]
        assert item["status"] == "success"

    @patch("src.agents.operations.activity_writer._get_table")
    def test_includes_error_message_when_provided(self, mock_table):
        table = MagicMock()
        mock_table.return_value = table

        record_agent_activity(
            agent="Executor (GCP)",
            provider="gcp",
            action="Failed remediation",
            status="failed",
            error_message="Permission denied",
        )

        item = table.put_item.call_args[1]["Item"]
        assert item["error_message"] == "Permission denied"
        assert item["status"] == "failed"

    @patch("src.agents.operations.activity_writer._get_table")
    def test_includes_duration_ms_when_provided(self, mock_table):
        table = MagicMock()
        mock_table.return_value = table

        record_agent_activity(
            agent="ADK Agent",
            provider="gcp",
            action="Deploy",
            duration_ms=1500,
        )

        item = table.put_item.call_args[1]["Item"]
        assert item["duration_ms"] == 1500


class TestUpdateProviderHealth:
    """update_provider_health upserts HEALTH + HEALTH_HISTORY items."""

    @patch("src.agents.operations.activity_writer._get_table")
    def test_writes_health_snapshot(self, mock_table):
        table = MagicMock()
        mock_table.return_value = table

        update_provider_health(
            provider="aws",
            status="healthy",
            active_incidents=0,
            last_deployment_id="DEP-001",
        )

        # Should write 2 items: HEALTH + HEALTH_HISTORY
        assert table.put_item.call_count == 2

        calls = table.put_item.call_args_list
        health_item = calls[0][1]["Item"]
        history_item = calls[1][1]["Item"]

        assert health_item["PK"] == "HEALTH"
        assert health_item["SK"] == "aws"
        assert health_item["status"] == "healthy"
        assert health_item["last_deployment_id"] == "DEP-001"

        assert history_item["PK"] == "HEALTH_HISTORY#aws"
        assert history_item["status"] == "healthy"

    @patch("src.agents.operations.activity_writer._get_table")
    def test_health_history_has_90_day_ttl(self, mock_table):
        table = MagicMock()
        mock_table.return_value = table

        update_provider_health(provider="gcp", status="degraded", active_incidents=1)

        history_item = table.put_item.call_args_list[1][1]["Item"]
        expected_ttl = int(time.time()) + TTL_90_DAYS
        assert abs(history_item["ttl"] - expected_ttl) < 5


class TestExecutorIntegration:
    """Verify executor handler calls record_agent_activity."""

    @patch("src.agents.operations.activity_writer._get_table")
    @patch("src.agents.operations.executor.handler._DYNAMO")
    @patch("src.agents.operations.executor.handler._SSM")
    def test_executor_records_activity_on_auto(self, mock_ssm, mock_dynamo, mock_activity_table):
        """Executor in AUTO mode records agent activity after execution."""
        from src.agents.operations.executor.handler import lambda_handler

        # Mock SSM
        mock_ssm.start_automation_execution.return_value = {
            "AutomationExecutionId": "exec-123"
        }
        mock_ssm.get_automation_execution.return_value = {
            "AutomationExecution": {"AutomationExecutionStatus": "Success"}
        }
        mock_ssm.exceptions = type("Exc", (), {
            "AutomationDefinitionNotFoundException": type("E", (Exception,), {})
        })()

        # Mock DynamoDB incident table
        mock_table = MagicMock()
        mock_dynamo.Table.return_value = mock_table

        # Mock activity table
        activity_table = MagicMock()
        mock_activity_table.return_value = activity_table

        event = {
            "analyzer": {
                "detector": {
                    "alarm": {
                        "alarm_name": "eks-pod-oom-alert",
                        "alarm_arn": "arn:aws:cloudwatch:us-east-1:123:alarm/test",
                        "state": "ALARM",
                        "reason": "test threshold breach",
                        "metric_name": "pod_memory_utilization",
                        "namespace": "ContainerInsights",
                        "dimensions": {"ClusterName": "prod"},
                    },
                    "log_insights_results": [],
                    "xray_trace_ids": [],
                    "related_metrics": {},
                    "normalized_incident": {
                        "provider": "aws",
                        "service": "eks",
                        "resource_type": "pod",
                        "resource_id": "pod/orders-api",
                        "signal_type": "oom_kill",
                        "severity_hint": "P1",
                        "observations": {"memory_pct": 98},
                        "recommended_capabilities": ["restart_workload"],
                    },
                },
                "root_cause": "Memory leak in orders-api",
                "severity": "P1",
                "confidence": 0.95,
                "similar_incidents": [],
            },
            "runbook_id": "eks-pod-oom",
            "remediation_mode": "AUTO",
            "actions": ["AWS-RestartEKSPod"],
        }

        result = lambda_handler(event, None)

        # Activity writer should have been called
        activity_table.put_item.assert_called()
        activity_item = activity_table.put_item.call_args[1]["Item"]
        assert activity_item["PK"] == "ACTIVITY"
        assert "Executor (AWS)" in activity_item["agent"]
        assert "AWS-RestartEKSPod" in activity_item["tool_calls"]
