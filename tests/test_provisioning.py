"""
Tests for provisioning helper modules and Lambda handler.
"""

from unittest.mock import patch, MagicMock

from src.agents.provisioning.cdk_generator import build_service_blueprint
from src.agents.provisioning.iam_designer import build_iam_plan
from src.agents.provisioning.cost_estimator import estimate_monthly_cost


class TestBuildServiceBlueprint:
    def test_eks_service_defaults(self):
        blueprint = build_service_blueprint({"service_name": "orders-api"})

        assert blueprint["platform"] == "eks"
        assert blueprint["stack_name"] == "OrdersApiServiceStack"
        assert blueprint["capacity"]["desired_count"] == 2
        assert blueprint["resources"]["compute"] == "fargate_profile"

    def test_lambda_service_defaults(self):
        blueprint = build_service_blueprint(
            {"service_name": "image-resizer", "platform": "lambda", "exposure": "public"}
        )

        assert blueprint["platform"] == "lambda"
        assert blueprint["resources"]["function_url"] is True
        assert blueprint["deployment_strategy"]["type"] == "linear"


class TestBuildIamPlan:
    def test_includes_observability_and_dependency_templates(self):
        plan = build_iam_plan("orders-api", ["s3_read", "dynamodb_rw"])

        assert plan["role_name"] == "orders-api-service-role"
        assert any(statement["sid"] == "CloudwatchAccess" for statement in plan["inline_statements"])
        assert any(statement["sid"] == "S3ReadAccess" for statement in plan["inline_statements"])
        assert any(statement["sid"] == "DynamodbRwAccess" for statement in plan["inline_statements"])


class TestEstimateMonthlyCost:
    def test_estimates_eks_cost(self):
        estimate = estimate_monthly_cost({"platform": "eks", "desired_count": 2, "cpu": 512, "memory": 1024})

        assert estimate["currency"] == "USD"
        assert estimate["monthly_total_usd"] > 0
        assert "heuristic" in estimate["assumptions"][0].lower()

    def test_estimates_lambda_cost(self):
        estimate = estimate_monthly_cost({"platform": "lambda", "monthly_invocations": 2_000_000})

        assert estimate["breakdown"]["compute"] > 0


# ─────────────────────────────────────────────────────────────
# Provisioning Lambda handler
# ─────────────────────────────────────────────────────────────

class TestProvisioningHandler:
    @patch("src.agents.provisioning.handler._DYNAMO")
    @patch("src.agents.provisioning.handler._SLACK_WEBHOOK", "")
    def test_eks_plan_output_shape(self, mock_dynamo):
        from src.agents.provisioning.handler import lambda_handler

        mock_table = MagicMock()
        mock_dynamo.Table.return_value = mock_table

        event = {
            "service_name": "orders-api",
            "platform": "eks",
            "exposure": "internal",
            "requester": "eng-alice",
            "integrations": ["dynamodb_rw"],
        }
        result = lambda_handler(event, None)

        assert result["blueprint"]["service_name"] == "orders-api"
        assert result["blueprint"]["platform"] == "eks"
        assert result["cdk_artifact"]["stack_name"] == "OrdersApiServiceStack"
        assert any(file["path"] == "bin/app.ts" for file in result["cdk_artifact"]["files"])
        assert result["cost_estimate"]["currency"] == "USD"
        assert "plan_id" in result
        assert result["plan_id"].startswith("PLAN-")
        mock_table.put_item.assert_called_once()

    @patch("src.agents.provisioning.handler._DYNAMO")
    @patch("src.agents.provisioning.handler._SLACK_WEBHOOK", "")
    def test_public_service_needs_approval(self, mock_dynamo):
        from src.agents.provisioning.handler import lambda_handler

        mock_dynamo.Table.return_value = MagicMock()

        event = {
            "service_name": "checkout-api",
            "platform": "eks",
            "exposure": "public",
            "requester": "eng-bob",
        }
        result = lambda_handler(event, None)

        assert result["needs_approval"] is True
        assert result["status"] == "pending_approval"

    @patch("src.agents.provisioning.handler._DYNAMO")
    @patch("src.agents.provisioning.handler._SLACK_WEBHOOK", "")
    @patch("src.agents.provisioning.handler._COST_AUTO_LIMIT", 1000.0)
    def test_low_cost_internal_service_auto_approved(self, mock_dynamo):
        from src.agents.provisioning.handler import lambda_handler

        mock_dynamo.Table.return_value = MagicMock()

        event = {
            "service_name": "cron-worker",
            "platform": "lambda",
            "exposure": "internal",
            "requester": "eng-carol",
        }
        result = lambda_handler(event, None)

        assert result["needs_approval"] is False
        assert result["status"] == "approved"

    @patch("src.agents.provisioning.handler._DYNAMO")
    @patch("src.agents.adapters.slack_client.requests")
    def test_slack_notification_sent(self, mock_requests, mock_dynamo):
        from src.agents.provisioning.handler import lambda_handler
        import src.agents.provisioning.handler as prov_handler

        prov_handler._SLACK_WEBHOOK = "https://hooks.slack.com/test"
        mock_dynamo.Table.return_value = MagicMock()
        mock_requests.post.return_value = MagicMock(status_code=200)
        mock_requests.post.return_value.raise_for_status = MagicMock()

        try:
            event = {"service_name": "notify-test", "platform": "eks", "requester": "eng-test"}
            lambda_handler(event, None)
            mock_requests.post.assert_called_once()
            call_args = mock_requests.post.call_args
            assert call_args[0][0] == "https://hooks.slack.com/test"
        finally:
            prov_handler._SLACK_WEBHOOK = ""
