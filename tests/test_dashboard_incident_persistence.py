from unittest.mock import MagicMock, patch

from src.agents.models import (
    AlarmContext,
    AnalyzerOutput,
    DecisionOutput,
    DetectorOutput,
    NormalizedIncident,
    RemediationMode,
    Severity,
)
from src.agents.operations.executor.handler import _record_incident


def _decision(provider: str = "aws") -> DecisionOutput:
    alarm = AlarmContext(
        alarm_name="orders-api-oom",
        alarm_arn="arn:aws:cloudwatch:us-east-1:123456789012:alarm:orders-api-oom",
        namespace="AWS/EKS",
        metric_name="pod_memory_utilization",
        dimensions={"ClusterName": "orders"},
        reason="memory above threshold",
        state="ALARM",
        triggered_at="2026-07-11T00:00:00Z",
    )
    normalized = NormalizedIncident(
        provider=provider,
        service="orders-api",
        resource_type="kubernetes-workload",
        resource_id="orders-api",
        signal_type="memory-high",
        severity_hint="P1",
        source_metadata={"region": "us-east-1"},
    )
    detector = DetectorOutput(alarm=alarm, normalized_incident=normalized)
    analyzer = AnalyzerOutput(
        detector=detector,
        root_cause="memory leak",
        severity=Severity.P1,
        confidence=0.98,
    )
    return DecisionOutput(
        analyzer=analyzer,
        runbook_id="eks-pod-oom",
        remediation_mode=RemediationMode.AUTO,
        actions=["AWS-RestartEKSPod"],
    )


def test_incident_record_contains_dashboard_read_model_fields():
    table = MagicMock()

    with patch("src.agents.operations.executor.handler._DYNAMO") as dynamo:
        dynamo.Table.return_value = table
        _record_incident(
            incident_id="INC-12345678",
            decision=_decision(),
            executed=["AWS-RestartEKSPod"],
            resolved=True,
        )

    item = table.put_item.call_args.kwargs["Item"]
    assert item["provider"] == "aws"
    assert item["mode"] == "AUTO"
    assert item["runbook_id"] == "eks-pod-oom"
    assert item["executed_actions"] == ["AWS-RestartEKSPod"]
    assert item["created_at"] == item["resolved_at"]
    assert item["executed"] == item["executed_actions"]
