"""
Tests for Detector Agent (src/agents/operations/detector/handler.py)

AWS 호출은 unittest.mock 으로 패치.
실제 AWS 연결 없이 로직만 검증.
"""

import json
import pytest
from unittest.mock import patch

from src.agents.operations.aws.detector import (
    _parse_alarm,
    _namespace_to_log_group,
    _resolve_log_groups,
    _get_companion_metrics,
    _serialise,
    _detect_provider,
    _synthetic_alarm,
)
from src.agents.models import AlarmContext, DetectorOutput, NormalizedIncident


# ─────────────────────────────────────────────────────────────
# 샘플 EventBridge 이벤트
# ─────────────────────────────────────────────────────────────

SAMPLE_EVENT = {
    "id": "test-event-001",
    "source": "aws.cloudwatch",
    "detail-type": "CloudWatch Alarm State Change",
    "resources": ["arn:aws:cloudwatch:ap-northeast-2:123456789:alarm:eks-pod-oom"],
    "detail": {
        "alarmName": "eks-pod-oom",
        "state": {
            "value": "ALARM",
            "reason": "Threshold Crossed: pod_restart_total > 5",
        },
        "configuration": {
            "metrics": [{
                "metricStat": {
                    "metric": {
                        "name": "pod_restart_total",
                        "namespace": "AWS/EKS",
                        "dimensions": [
                            {"name": "ClusterName", "value": "prod"},
                            {"name": "PodName",     "value": "api-xyz"},
                        ],
                    }
                }
            }]
        },
    },
}


# ─────────────────────────────────────────────────────────────
# _parse_alarm
# ─────────────────────────────────────────────────────────────

class TestParseAlarm:
    def test_basic_fields(self):
        alarm = _parse_alarm(SAMPLE_EVENT)
        assert alarm.alarm_name  == "eks-pod-oom"
        assert alarm.state       == "ALARM"
        assert alarm.metric_name == "pod_restart_total"
        assert alarm.namespace   == "AWS/EKS"

    def test_dimensions_parsed(self):
        alarm = _parse_alarm(SAMPLE_EVENT)
        assert alarm.dimensions == {"ClusterName": "prod", "PodName": "api-xyz"}

    def test_alarm_arn(self):
        alarm = _parse_alarm(SAMPLE_EVENT)
        assert "arn:aws:cloudwatch" in alarm.alarm_arn

    def test_empty_event_defaults(self):
        alarm = _parse_alarm({})
        assert alarm.alarm_name == "unknown"
        assert alarm.state      == "ALARM"

    def test_reason_parsed(self):
        alarm = _parse_alarm(SAMPLE_EVENT)
        assert "pod_restart_total" in alarm.reason


# ─────────────────────────────────────────────────────────────
# _namespace_to_log_group
# ─────────────────────────────────────────────────────────────

class TestNamespaceToLogGroup:
    @pytest.mark.parametrize("namespace,expected", [
        ("AWS/EKS",    "/aws/eks"),
        ("AWS/Lambda", "/aws/lambda"),
        ("AWS/RDS",    "/aws/rds"),
        ("AWS/Kafka",  "/aws/msk"),
        ("AWS/SQS",    "/aws/sqs"),
    ])
    def test_known_namespaces(self, namespace, expected):
        assert _namespace_to_log_group(namespace) == expected

    def test_unknown_namespace_returns_empty(self):
        assert _namespace_to_log_group("Unknown/Service") == ""

    def test_custom_namespace(self):
        result = _namespace_to_log_group("Custom/MyService")
        assert result.startswith("/custom/")


# ─────────────────────────────────────────────────────────────
# _resolve_log_groups
# ─────────────────────────────────────────────────────────────

class TestResolveLogGroups:
    def test_lambda_function_uses_exact_log_group(self):
        alarm = AlarmContext(
            alarm_name="lambda-error",
            alarm_arn="arn:...",
            state="ALARM",
            reason="Errors > 1",
            metric_name="Errors",
            namespace="AWS/Lambda",
            dimensions={"FunctionName": "my-fn"},
        )

        assert _resolve_log_groups(alarm) == ["/aws/lambda/my-fn"]

    @patch("src.agents.operations.aws.detector._LOGS_CLIENT")
    def test_namespace_prefix_discovers_log_groups(self, logs_client):
        logs_client.describe_log_groups.return_value = {
            "logGroups": [
                {"logGroupName": "/aws/rds/instance/prod-db/error"},
                {"logGroupName": "/aws/rds/instance/prod-db/slowquery"},
            ]
        }
        alarm = AlarmContext(
            alarm_name="rds-cpu",
            alarm_arn="arn:...",
            state="ALARM",
            reason="CPU high",
            metric_name="CPUUtilization",
            namespace="AWS/RDS",
        )

        result = _resolve_log_groups(alarm)

        assert result == [
            "/aws/rds/instance/prod-db/error",
            "/aws/rds/instance/prod-db/slowquery",
        ]
        logs_client.describe_log_groups.assert_called_once()

    @patch("src.agents.operations.aws.detector._LOGS_CLIENT")
    def test_unknown_namespace_returns_empty_without_lookup(self, logs_client):
        alarm = AlarmContext(
            alarm_name="unknown",
            alarm_arn="arn:...",
            state="ALARM",
            reason="test",
            metric_name="WeirdMetric",
            namespace="Unknown/Service",
        )

        assert _resolve_log_groups(alarm) == []
        logs_client.describe_log_groups.assert_not_called()


# ─────────────────────────────────────────────────────────────
# _get_companion_metrics
# ─────────────────────────────────────────────────────────────

class TestGetCompanionMetrics:
    def test_eks_excludes_triggered_metric(self):
        metrics = _get_companion_metrics("AWS/EKS", "node_cpu_utilization")
        assert "node_cpu_utilization" not in metrics
        assert len(metrics) > 0

    def test_lambda_companions(self):
        metrics = _get_companion_metrics("AWS/Lambda", "Errors")
        assert "Errors" not in metrics
        assert "Throttles" in metrics

    def test_unknown_namespace_returns_empty(self):
        metrics = _get_companion_metrics("Unknown/NS", "SomeMetric")
        assert metrics == []


# ─────────────────────────────────────────────────────────────
# _serialise
# ─────────────────────────────────────────────────────────────

class TestSerialise:
    def test_output_is_json_compatible(self):
        alarm = AlarmContext(
            alarm_name="test", alarm_arn="arn:...", state="ALARM",
            reason="test", metric_name="m", namespace="AWS/EKS",
        )
        normalized_incident = NormalizedIncident(
            provider="aws",
            service="test-service",
            resource_type="kubernetes-workload",
            resource_id="api-xyz",
            signal_type="reliability",
            recommended_capabilities=["restart_workload"],
        )
        output = DetectorOutput(
            alarm=alarm,
            log_insights_results=[{"@message": "ERROR"}],
            xray_trace_ids=["t1"],
            related_metrics={"cpu": 90.0},
            normalized_incident=normalized_incident,
        )
        result = _serialise(output)
        # dict 여야 하고, JSON 직렬화 가능해야 함
        assert isinstance(result, dict)
        json.dumps(result)  # 예외 없으면 통과
        assert result["normalized_incident"]["provider"] == "aws"

    def test_nested_alarm_preserved(self):
        alarm = AlarmContext(
            alarm_name="my-alarm", alarm_arn="arn", state="ALARM",
            reason="r", metric_name="m", namespace="AWS/Lambda",
            dimensions={"FunctionName": "my-fn"},
        )
        output   = DetectorOutput(alarm=alarm)
        result   = _serialise(output)
        assert result["alarm"]["alarm_name"] == "my-alarm"
        assert result["alarm"]["dimensions"] == {"FunctionName": "my-fn"}


# ─────────────────────────────────────────────────────────────
# _detect_provider
# ─────────────────────────────────────────────────────────────

class TestDetectProvider:
    def test_aws_from_source_field(self):
        assert _detect_provider({"source": "aws.cloudwatch"}) == "aws"

    def test_aws_from_other_aws_source(self):
        assert _detect_provider({"source": "aws.ec2"}) == "aws"

    def test_gcp_from_incident_key(self):
        event = {"incident": {"policy_name": "my-policy", "summary": "high cpu"}}
        assert _detect_provider(event) == "gcp"

    def test_azure_from_data_essentials(self):
        event = {"data": {"essentials": {"alertRule": "high-cpu"}}}
        assert _detect_provider(event) == "azure"

    def test_onprem_from_alerts_key(self):
        event = {"alerts": [{"status": "firing"}], "groupLabels": {}}
        assert _detect_provider(event) == "onprem"

    def test_onprem_from_group_labels(self):
        event = {"groupLabels": {"alertname": "HighCPU"}}
        assert _detect_provider(event) == "onprem"

    def test_default_fallback_is_aws(self):
        assert _detect_provider({}) == "aws"
        assert _detect_provider({"foo": "bar"}) == "aws"


# ─────────────────────────────────────────────────────────────
# _synthetic_alarm
# ─────────────────────────────────────────────────────────────

class TestSyntheticAlarm:
    def test_builds_alarm_from_gcp_incident(self):
        incident = NormalizedIncident(
            provider="gcp",
            service="checkout-api",
            resource_type="kubernetes-workload",
            resource_id="checkout-api-pod-1",
            signal_type="reliability",
        )
        alarm = _synthetic_alarm(incident, "gcp")
        assert alarm.alarm_name == "checkout-api"
        assert alarm.state == "ALARM"
        assert alarm.namespace == "GCP/kubernetes-workload"

    def test_fallback_alarm_name_when_service_empty(self):
        incident = NormalizedIncident(
            provider="onprem",
            service="",
            resource_type="cloud-resource",
            resource_id="",
            signal_type="availability",
        )
        alarm = _synthetic_alarm(incident, "onprem")
        assert alarm.alarm_name == "external-incident"


# ─────────────────────────────────────────────────────────────
# lambda_handler — non-AWS path
# ─────────────────────────────────────────────────────────────

class TestLambdaHandlerNonAws:
    @patch("src.agents.operations.aws.detector.get_signal_adapter")
    def test_gcp_event_skips_aws_collection(self, mock_registry):
        from unittest.mock import MagicMock
        from src.agents.operations.aws.detector import lambda_handler

        mock_adapter = MagicMock()
        mock_adapter.normalise.return_value = NormalizedIncident(
            provider="gcp",
            service="checkout-api",
            resource_type="kubernetes-workload",
            resource_id="checkout-api-pod-1",
            signal_type="reliability",
            recommended_capabilities=["restart_workload"],
        )
        mock_registry.return_value = mock_adapter

        gcp_event = {"incident": {"policy_name": "k8s-high-restart", "summary": "pod restarting"}}
        result = lambda_handler(gcp_event, None)

        mock_registry.assert_called_once_with("gcp")
        mock_adapter.normalise.assert_called_once_with(gcp_event)
        assert result["normalized_incident"]["provider"] == "gcp"
        assert result["alarm"]["alarm_name"] == "checkout-api"
        assert result["log_insights_results"] == []
        assert result["xray_trace_ids"] == []


# ─────────────────────────────────────────────────────────────
# lambda_handler — AWS path (regression: live NameError 2026-07-18)
# ─────────────────────────────────────────────────────────────

class TestLambdaHandlerAws:
    """AWS 경로가 실 _normalise_incident + 실 signal adapter로 완주하는지.

    라이브 알람 트리거가 표면화한 NameError(_SIGNAL_ADAPTER 미정의) 회귀 가드 —
    수집 헬퍼 3종만 patch하고 normalisation은 실 코드로 실행한다.
    """

    _EVENT = {
        "id": "test-event-id",
        "source": "aws.cloudwatch",
        "detail-type": "CloudWatch Alarm State Change",
        "resources": ["arn:aws:cloudwatch:us-east-1:111122223333:alarm:checkout-5xx"],
        "detail": {
            "alarmName": "checkout-5xx",
            "state": {"value": "ALARM", "reason": "threshold crossed"},
            "configuration": {
                "metrics": [{
                    "metricStat": {"metric": {
                        "name": "HTTPCode_Target_5XX_Count",
                        "namespace": "AWS/ApplicationELB",
                        "dimensions": [{"name": "LoadBalancer", "value": "app/demo/abc"}],
                    }},
                }],
            },
        },
    }

    @patch("src.agents.operations.aws.detector._fetch_related_metrics", return_value={})
    @patch("src.agents.operations.aws.detector._fetch_xray_traces", return_value=[])
    @patch("src.agents.operations.aws.detector._query_logs_insights", return_value=[])
    def test_aws_path_runs_real_normalisation(self, *_mocks):
        from src.agents.operations.aws.detector import lambda_handler

        result = lambda_handler(self._EVENT, None)

        incident = result["normalized_incident"]
        assert incident["provider"] == "aws"
        assert result["alarm"]["alarm_name"] == "checkout-5xx"
        assert incident["source_metadata"]["alarm_name"] == "checkout-5xx"
        assert incident["severity_hint"] == "ALARM"
