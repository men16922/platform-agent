"""
Tests for operations reporting helpers and Lambda dispatcher.
"""

from unittest.mock import patch, MagicMock

from src.agents.operations.slo_calculator import (
    build_daily_slo_report,
    calculate_service_slo,
    rank_services_by_burn_rate,
)
from src.agents.operations.oncall_reporter import (
    build_weekly_oncall_report,
    find_recurring_patterns,
    summarize_incidents,
)
from src.agents.operations.capacity_planner import (
    analyze_service_capacity,
    build_monthly_capacity_report,
)


class TestSloCalculator:
    def test_calculates_service_slo(self):
        summary = calculate_service_slo(
            "orders-api",
            total_requests=10_000,
            failed_requests=15,
            slo_target=0.999,
        )

        assert summary["service_name"] == "orders-api"
        assert summary["status"] == "critical"
        assert summary["burn_rate"] > 1.0

    def test_ranks_services_by_burn_rate(self):
        ranked = rank_services_by_burn_rate(
            [
                {"service_name": "a", "burn_rate": 0.2, "observed_error_rate": 0.0002},
                {"service_name": "b", "burn_rate": 1.4, "observed_error_rate": 0.0014},
            ]
        )

        assert ranked[0]["service_name"] == "b"

    def test_builds_daily_report(self):
        report = build_daily_slo_report(
            [
                {"service_name": "orders", "burn_rate": 1.1, "observed_error_rate": 0.0011, "status": "critical"},
                {"service_name": "billing", "burn_rate": 0.3, "observed_error_rate": 0.0003, "status": "healthy"},
            ]
        )

        assert report["report_type"] == "daily_slo"
        assert report["top_unstable_services"] == ["orders", "billing"]


class TestOncallReporter:
    def test_summarizes_incidents(self):
        summary = summarize_incidents(
            [
                {
                    "service_name": "orders",
                    "severity": "P1",
                    "started_at": "2026-04-01T00:00:00Z",
                    "resolved_at": "2026-04-01T00:30:00Z",
                    "runbook_id": "eks-pod-oom",
                },
                {
                    "service_name": "orders",
                    "severity": "P2",
                    "started_at": "2026-04-02T00:00:00Z",
                    "resolved_at": "2026-04-02T01:00:00Z",
                    "runbook_id": "eks-pod-oom",
                },
            ]
        )

        assert summary["total_incidents"] == 2
        assert summary["severity_counts"]["P1"] == 1
        assert summary["average_mttr_minutes"] == 45.0
        assert summary["recurring_patterns"][0]["pattern"] == "eks-pod-oom"

    def test_builds_weekly_report(self):
        report = build_weekly_oncall_report(
            current_incidents=[
                {
                    "service_name": "orders",
                    "severity": "P2",
                    "started_at": "2026-04-03T00:00:00Z",
                    "resolved_at": "2026-04-03T00:20:00Z",
                    "alarm_name": "orders-api-latency",
                }
            ],
            previous_incidents=[],
        )

        assert report["report_type"] == "weekly_oncall"
        assert report["trend"]["incident_delta"] == 1

    def test_finds_recurring_patterns(self):
        patterns = find_recurring_patterns(
            [
                {"alarm_name": "orders-api-latency"},
                {"alarm_name": "orders-api-latency"},
                {"alarm_name": "billing-timeout"},
            ]
        )

        assert patterns == [{"pattern": "orders-api-latency", "count": 2}]


class TestCapacityPlanner:
    def test_analyzes_service_capacity(self):
        analysis = analyze_service_capacity(
            "orders-api",
            [
                {"cpu_utilization": 55, "memory_utilization": 60},
                {"cpu_utilization": 78, "memory_utilization": 74},
                {"cpu_utilization": 88, "memory_utilization": 82},
                {"cpu_utilization": 91, "memory_utilization": 85},
            ],
            monthly_cost_usd=420.0,
        )

        assert analysis["service_name"] == "orders-api"
        assert analysis["recommendation"] == "scale_up"

    def test_builds_monthly_capacity_report(self):
        report = build_monthly_capacity_report(
            [
                {"service_name": "orders", "recommendation": "scale_up", "peak_cpu_utilization": 90, "peak_memory_utilization": 83},
                {"service_name": "billing", "recommendation": "observe", "peak_cpu_utilization": 62, "peak_memory_utilization": 58},
            ]
        )

        assert report["report_type"] == "monthly_capacity"
        assert report["priority_services"][0] == "orders"


# ─────────────────────────────────────────────────────────────
# Reporting Lambda dispatcher
# ─────────────────────────────────────────────────────────────

class TestReportingHandler:
    @patch("src.agents.operations.aws.reporting._DYNAMO")
    @patch("src.agents.operations.aws.reporting._SLACK_WEBHOOK", "")
    def test_daily_slo_dispatch(self, mock_dynamo):
        from src.agents.operations.aws.reporting import lambda_handler

        event = {
            "report_type": "daily_slo",
            "services": [
                {"service_name": "orders-api", "total_requests": 10000, "failed_requests": 5},
                {"service_name": "billing",    "total_requests": 5000,  "failed_requests": 0},
            ],
        }
        report = lambda_handler(event, None)

        assert report["report_type"] == "daily_slo"
        assert report["service_count"] == 2
        assert "status_counts" in report

    @patch("src.agents.operations.aws.reporting._DYNAMO")
    @patch("src.agents.operations.aws.reporting._SLACK_WEBHOOK", "")
    def test_weekly_oncall_dispatch(self, mock_dynamo):
        from src.agents.operations.aws.reporting import lambda_handler

        event = {
            "report_type": "weekly_oncall",
            "current_incidents": [
                {
                    "service_name": "orders-api",
                    "severity": "P2",
                    "alarm_name": "orders-high-latency",
                    "started_at": "2026-04-07T10:00:00Z",
                    "resolved_at": "2026-04-07T10:20:00Z",
                }
            ],
            "previous_incidents": [],
        }
        report = lambda_handler(event, None)

        assert report["report_type"] == "weekly_oncall"
        assert report["current"]["total_incidents"] == 1
        assert report["trend"]["incident_delta"] == 1

    @patch("src.agents.operations.aws.reporting._DYNAMO")
    @patch("src.agents.operations.aws.reporting._CW")
    @patch("src.agents.operations.aws.reporting._SLACK_WEBHOOK", "")
    def test_monthly_capacity_dispatch(self, mock_cw, mock_dynamo):
        from src.agents.operations.aws.reporting import lambda_handler

        event = {
            "report_type": "monthly_capacity",
            "services": [
                {
                    "service_name": "orders-api",
                    "samples": [
                        {"cpu_utilization": 88, "memory_utilization": 82},
                        {"cpu_utilization": 91, "memory_utilization": 85},
                    ],
                    "monthly_cost_usd": 350.0,
                }
            ],
        }
        report = lambda_handler(event, None)

        assert report["report_type"] == "monthly_capacity"
        assert report["service_count"] == 1
        assert report["priority_services"] == ["orders-api"]

    def test_unknown_report_type_raises(self):
        import pytest
        from src.agents.operations.aws.reporting import lambda_handler

        with pytest.raises(ValueError, match="Unknown report_type"):
            lambda_handler({"report_type": "quarterly_magic"}, None)

    @patch("src.agents.operations.aws.reporting._DYNAMO")
    @patch("src.agents.adapters.slack_client.requests")
    def test_slack_notification_sent_for_slo(self, mock_requests, mock_dynamo):
        from src.agents.operations.aws.reporting import lambda_handler
        import src.agents.operations.aws.reporting as rh

        rh._SLACK_WEBHOOK = "https://hooks.slack.com/test"
        mock_requests.post.return_value = MagicMock(status_code=200)
        mock_requests.post.return_value.raise_for_status = MagicMock()

        try:
            event = {
                "report_type": "daily_slo",
                "services": [{"service_name": "orders-api", "total_requests": 1000, "failed_requests": 1}],
            }
            lambda_handler(event, None)
            mock_requests.post.assert_called_once()
        finally:
            rh._SLACK_WEBHOOK = ""
