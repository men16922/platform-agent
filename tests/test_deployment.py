"""
Tests for deployment helper modules and Lambda handler.
"""

from unittest.mock import patch, MagicMock

from src.agents.deployment.smoke_tester import build_smoke_test_plan, summarise_smoke_results
from src.agents.deployment.canary_analyzer import analyze_canary
from src.agents.deployment.rollback_decider import decide_rollout_action


class TestSmokeTester:
    def test_builds_checks(self):
        plan = build_smoke_test_plan(
            {
                "service_name": "orders-api",
                "base_url": "https://orders.example.com",
                "core_endpoints": [{"name": "create-order", "path": "/orders", "method": "POST"}],
            }
        )

        assert plan["checks"][0]["name"] == "health"
        assert plan["checks"][1]["method"] == "POST"

    def test_summarises_failures(self):
        summary = summarise_smoke_results(
            [
                {"name": "health", "status": "passed"},
                {"name": "create-order", "status": "failed"},
            ]
        )

        assert summary["should_continue"] is False
        assert summary["failed_checks"] == ["create-order"]


class TestCanaryAnalyzer:
    def test_recommends_rollback_for_large_regression(self):
        analysis = analyze_canary(
            baseline={"error_rate": 0.01, "latency_p99_ms": 300, "success_rate": 0.99},
            candidate={"error_rate": 0.05, "latency_p99_ms": 420, "success_rate": 0.94},
        )

        assert analysis["rollback_recommended"] is True
        assert "error_rate_regression" in analysis["reasons"]

    def test_requests_human_review_when_near_threshold(self):
        analysis = analyze_canary(
            baseline={"error_rate": 0.01, "latency_p99_ms": 300, "success_rate": 0.99},
            candidate={"error_rate": 0.022, "latency_p99_ms": 360, "success_rate": 0.975},
            thresholds={"error_rate_delta": 0.02, "latency_p99_delta_pct": 0.3, "success_rate_drop_pct": 0.03},
        )

        assert analysis["rollback_recommended"] is False
        assert analysis["needs_human_review"] is True


class TestRollbackDecider:
    def test_rolls_back_when_regression_detected(self):
        decision = decide_rollout_action({"rollback_recommended": True, "reasons": ["latency_regression"]})
        assert decision["action"] == "ROLLBACK"

    def test_keeps_rollout_when_healthy(self):
        decision = decide_rollout_action({"rollback_recommended": False, "needs_human_review": False, "reasons": []})
        assert decision["action"] == "KEEP_ROLLOUT"


# ─────────────────────────────────────────────────────────────
# Deployment Lambda handler
# ─────────────────────────────────────────────────────────────

class TestDeploymentHandler:
    @patch("src.agents.deployment.handler.requests")
    @patch("src.agents.deployment.handler._SLACK_WEBHOOK", "")
    def test_healthy_canary_keeps_rollout(self, mock_requests):
        from src.agents.deployment.handler import lambda_handler

        mock_requests.request.return_value = MagicMock(status_code=200)

        event = {
            "deployment_id": "deploy-001",
            "service_name":  "orders-api",
            "version":       "v1.5.0",
            "base_url":      "https://orders.internal",
            "baseline_metrics": {"error_rate": 0.005, "latency_p99_ms": 120.0, "success_rate": 0.995},
            "canary_metrics":   {"error_rate": 0.006, "latency_p99_ms": 125.0, "success_rate": 0.994},
        }
        result = lambda_handler(event, None)

        assert result["rollout_action"] == "KEEP_ROLLOUT"
        assert result["smoke_summary"]["should_continue"] is True
        assert result["needs_approval"] is False

    @patch("src.agents.deployment.handler.requests")
    @patch("src.agents.deployment.handler._SLACK_WEBHOOK", "")
    def test_canary_regression_triggers_rollback(self, mock_requests):
        from src.agents.deployment.handler import lambda_handler

        mock_requests.request.return_value = MagicMock(status_code=200)

        event = {
            "deployment_id": "deploy-002",
            "service_name":  "orders-api",
            "version":       "v1.5.1",
            "base_url":      "https://orders.internal",
            "baseline_metrics": {"error_rate": 0.005, "latency_p99_ms": 100.0, "success_rate": 0.995},
            "canary_metrics":   {"error_rate": 0.08,  "latency_p99_ms": 500.0, "success_rate": 0.92},
        }
        result = lambda_handler(event, None)

        assert result["rollout_action"] == "ROLLBACK"
        assert result["needs_approval"] is False

    @patch("src.agents.deployment.handler.requests")
    @patch("src.agents.deployment.handler._SLACK_WEBHOOK", "")
    def test_smoke_failure_overrides_healthy_canary(self, mock_requests):
        from src.agents.deployment.handler import lambda_handler

        mock_requests.request.return_value = MagicMock(status_code=503)

        event = {
            "deployment_id": "deploy-003",
            "service_name":  "orders-api",
            "version":       "v1.5.2",
            "base_url":      "https://orders.internal",
            "baseline_metrics": {"error_rate": 0.005, "latency_p99_ms": 100.0, "success_rate": 0.995},
            "canary_metrics":   {"error_rate": 0.005, "latency_p99_ms": 101.0, "success_rate": 0.995},
        }
        result = lambda_handler(event, None)

        assert result["rollout_action"] == "ROLLBACK"
        assert "smoke_test_failed" in result["rollout_reason"]

    @patch("src.agents.deployment.handler.requests")
    @patch("src.agents.deployment.handler._SLACK_WEBHOOK", "")
    def test_no_canary_data_keeps_rollout(self, mock_requests):
        from src.agents.deployment.handler import lambda_handler

        mock_requests.request.return_value = MagicMock(status_code=200)

        event = {
            "deployment_id": "deploy-004",
            "service_name":  "cron-worker",
            "version":       "v2.0.0",
            "base_url":      "https://cron.internal",
        }
        result = lambda_handler(event, None)

        assert result["rollout_action"] == "KEEP_ROLLOUT"
        assert result["rollout_reason"] == "no_canary_data_available"

    @patch("src.agents.deployment.handler.requests")
    @patch("src.agents.deployment.handler._SLACK_WEBHOOK", "")
    def test_preserves_rollback_execution_context(self, mock_requests):
        from src.agents.deployment.handler import lambda_handler

        mock_requests.request.return_value = MagicMock(status_code=200)

        event = {
            "deployment_id": "deploy-005",
            "service_name": "orders-api",
            "version": "v1.5.3",
            "base_url": "https://orders.internal",
            "platform": "eks",
            "namespace": "payments",
            "workload_name": "orders-api",
            "rollback_document_name": "PlatformAgent-EksRollback",
            "rollback_target_version": "v1.5.2",
            "rollback_parameters": {"ChangeWindow": "approved"},
        }
        result = lambda_handler(event, None)

        assert result["execution_context"]["platform"] == "eks"
        assert result["execution_context"]["rollback_document_name"] == "PlatformAgent-EksRollback"
        assert result["execution_context"]["rollback_target_version"] == "v1.5.2"
