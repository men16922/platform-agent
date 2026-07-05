"""
Tests for src/agents/models.py

데이터 모델의 직렬화/역직렬화, Severity/RemediationMode Enum 동작 검증.
AWS 서비스 호출 없음 — 순수 단위 테스트.
"""

import json
import pytest
from dataclasses import asdict

from src.agents.models import (
    AlarmContext, DetectorOutput, AnalyzerOutput,
    DecisionOutput, ExecutorOutput, NormalizedIncident,
    Severity, RemediationMode, to_json,
)


# ─────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────

@pytest.fixture
def alarm():
    return AlarmContext(
        alarm_name="eks-pod-oom",
        alarm_arn="arn:aws:cloudwatch:ap-northeast-2:123456789:alarm:eks-pod-oom",
        state="ALARM",
        reason="Threshold Crossed: pod restart > 5",
        metric_name="pod_restart_total",
        namespace="AWS/EKS",
        dimensions={"ClusterName": "prod", "PodName": "api-abc"},
    )


@pytest.fixture
def detector(alarm, normalized_incident):
    return DetectorOutput(
        alarm=alarm,
        log_insights_results=[{"@timestamp": "2026-04-11T10:00:00", "@message": "OOMKilled"}],
        xray_trace_ids=["trace-001", "trace-002"],
        related_metrics={"node_cpu_utilization": 85.5},
        normalized_incident=normalized_incident,
    )


@pytest.fixture
def normalized_incident():
    return NormalizedIncident(
        provider="aws",
        service="checkout-api",
        resource_type="kubernetes-workload",
        resource_id="checkout-api-7d9f6b88d8-xk2lm",
        signal_type="reliability",
        severity_hint="high",
        observations={"logs": ["OOMKilled"], "metrics": {"Errors": 42.0}},
        recommended_capabilities=["restart_workload", "scale_out"],
        source_metadata={"alarm_name": "eks-pod-oom"},
    )


@pytest.fixture
def analyzer(detector):
    return AnalyzerOutput(
        detector=detector,
        root_cause="Pod exceeded memory limit due to heap leak in api service.",
        severity=Severity.P2,
        confidence=0.87,
        similar_incidents=["INC-AABBCC"],
    )


@pytest.fixture
def decision(analyzer):
    return DecisionOutput(
        analyzer=analyzer,
        runbook_id="eks-pod-oom",
        remediation_mode=RemediationMode.APPROVE,
        actions=["AWS-RestartEKSPod", "AWS-ScaleOutEKSNodeGroup"],
        estimated_rto_sec=180,
    )


@pytest.fixture
def executor(decision):
    return ExecutorOutput(
        decision=decision,
        executed_actions=["AWS-RestartEKSPod"],
        skipped_actions=["AWS-ScaleOutEKSNodeGroup"],
        slack_ts="1712834400.123456",
        incident_id="INC-12345678",
        resolved=False,
    )


# ─────────────────────────────────────────────────────────────
# AlarmContext
# ─────────────────────────────────────────────────────────────

class TestAlarmContext:
    def test_fields(self, alarm):
        assert alarm.alarm_name == "eks-pod-oom"
        assert alarm.namespace  == "AWS/EKS"
        assert alarm.dimensions == {"ClusterName": "prod", "PodName": "api-abc"}

    def test_triggered_at_set(self, alarm):
        # triggered_at 는 기본값으로 자동 설정
        assert alarm.triggered_at != ""

    def test_serialise_roundtrip(self, alarm):
        d = asdict(alarm)
        restored = AlarmContext(**d)
        assert restored.alarm_name == alarm.alarm_name
        assert restored.dimensions == alarm.dimensions


class TestNormalizedIncident:
    def test_fields(self, normalized_incident):
        assert normalized_incident.provider == "aws"
        assert normalized_incident.service == "checkout-api"
        assert normalized_incident.recommended_capabilities == ["restart_workload", "scale_out"]

    def test_serialise_roundtrip(self, normalized_incident):
        raw = to_json(normalized_incident)
        parsed = json.loads(raw)

        assert parsed["provider"] == "aws"
        assert parsed["resource_type"] == "kubernetes-workload"
        assert parsed["source_metadata"]["alarm_name"] == "eks-pod-oom"


# ─────────────────────────────────────────────────────────────
# Severity
# ─────────────────────────────────────────────────────────────

class TestSeverity:
    def test_values(self):
        assert Severity.P1.value == "P1"
        assert Severity.P2.value == "P2"
        assert Severity.P3.value == "P3"

    def test_from_string(self):
        assert Severity("P1") == Severity.P1

    def test_invalid_raises(self):
        with pytest.raises(ValueError):
            Severity("P4")


# ─────────────────────────────────────────────────────────────
# RemediationMode
# ─────────────────────────────────────────────────────────────

class TestRemediationMode:
    def test_values(self):
        assert RemediationMode.AUTO.value    == "AUTO"
        assert RemediationMode.APPROVE.value == "APPROVE"
        assert RemediationMode.MANUAL.value  == "MANUAL"

    def test_from_string(self):
        assert RemediationMode("APPROVE") == RemediationMode.APPROVE


# ─────────────────────────────────────────────────────────────
# to_json / _to_dict
# ─────────────────────────────────────────────────────────────

class TestSerialisation:
    def test_to_json_alarm(self, alarm):
        raw = to_json(alarm)
        parsed = json.loads(raw)
        assert parsed["alarm_name"] == "eks-pod-oom"
        assert parsed["namespace"]  == "AWS/EKS"

    def test_to_json_enum_becomes_string(self, analyzer):
        raw    = to_json(analyzer)
        parsed = json.loads(raw)
        # Enum 값이 문자열로 직렬화되어야 함
        assert parsed["severity"]   == "P2"

    def test_to_json_nested(self, executor):
        raw    = to_json(executor)
        parsed = json.loads(raw)
        # 중첩 구조 확인
        assert parsed["decision"]["analyzer"]["severity"] == "P2"
        assert parsed["decision"]["remediation_mode"]     == "APPROVE"
        assert parsed["incident_id"]                      == "INC-12345678"

    def test_full_pipeline_json_roundtrip(self, executor):
        """ExecutorOutput → JSON → dict 가 손실 없이 변환되는지 확인."""
        raw    = to_json(executor)
        parsed = json.loads(raw)

        # 최상위 필드
        assert parsed["resolved"]          == False
        assert parsed["executed_actions"]  == ["AWS-RestartEKSPod"]
        assert parsed["skipped_actions"]   == ["AWS-ScaleOutEKSNodeGroup"]

        # 중첩 에이전트 데이터
        alarm_data = parsed["decision"]["analyzer"]["detector"]["alarm"]
        assert alarm_data["alarm_name"] == "eks-pod-oom"
        assert alarm_data["dimensions"] == {"ClusterName": "prod", "PodName": "api-abc"}
        normalized_data = parsed["decision"]["analyzer"]["detector"]["normalized_incident"]
        assert normalized_data["provider"] == "aws"
        assert normalized_data["recommended_capabilities"] == ["restart_workload", "scale_out"]
