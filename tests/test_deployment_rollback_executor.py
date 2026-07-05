"""
Tests for deployment rollback execution.
"""

from unittest.mock import patch


@patch("src.agents.deployment.rollback_executor._SSM")
def test_starts_ssm_automation_when_document_is_configured(mock_ssm):
    from src.agents.deployment.rollback_executor import lambda_handler

    mock_ssm.start_automation_execution.return_value = {
        "AutomationExecutionId": "exec-123",
    }
    event = {
        "deployment_id": "deploy-100",
        "service_name": "orders-api",
        "version": "v2.0.0",
        "rollout_reason": "error_rate_regression",
        "execution_context": {
            "platform": "eks",
            "cluster_name": "prod-cluster",
            "namespace": "payments",
            "workload_name": "orders-api",
            "rollback_document_name": "PlatformAgent-EksRollback",
            "rollback_target_version": "v1.9.9",
            "rollback_parameters": {"ChangeWindow": "approved"},
        },
    }

    result = lambda_handler(event, None)

    kwargs = mock_ssm.start_automation_execution.call_args.kwargs
    assert kwargs["DocumentName"] == "PlatformAgent-EksRollback"
    assert kwargs["Parameters"]["ChangeWindow"] == ["approved"]
    assert kwargs["Parameters"]["TargetVersion"] == ["v1.9.9"]
    assert kwargs["Parameters"]["ClusterName"] == ["prod-cluster"]
    assert result["rollback_status"] == "started"
    assert result["rollback_mode"] == "ssm_automation"
    assert result["rollback_execution_id"] == "exec-123"


def test_returns_manual_plan_when_no_automation_document_exists():
    from src.agents.deployment.rollback_executor import lambda_handler

    event = {
        "deployment_id": "deploy-101",
        "service_name": "orders-api",
        "version": "v2.0.1",
        "rollout_reason": "smoke_test_failed",
        "execution_context": {
            "platform": "eks",
            "namespace": "payments",
            "workload_name": "orders-api",
            "previous_version": "v2.0.0",
        },
    }

    result = lambda_handler(event, None)

    assert result["rollback_status"] == "manual_intervention_required"
    assert result["rollback_mode"] == "manual"
    assert result["rollback_target_version"] == "v2.0.0"
    assert result["rollback_plan"]["suggested_command"] == (
        "kubectl rollout undo deployment/orders-api --namespace payments"
    )
