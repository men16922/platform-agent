from decimal import Decimal
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
from src.agents.operations.aws.executor import _record_incident


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

    with patch("src.agents.operations.aws.executor._DYNAMO") as dynamo:
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
    # This incident resolved, and `_record_incident` runs directly after the
    # actions do, so the two coincide *here*. It is no longer an invariant:
    # `resolved_at` used to be written unconditionally, which gave open incidents
    # a resolution time and made the weekly report's MTTR a structural zero.
    # See tests/test_incident_time_to_resolve.py.
    assert item["created_at"] == item["resolved_at"]
    assert item["executed"] == item["executed_actions"]


def _tenant_decision(tenant: str = "acme", env: str = "dev") -> DecisionOutput:
    """Same incident, but owned — `NormalizedIncident` has carried these since Phase 1a."""
    decision = _decision()
    normalized = decision.analyzer.detector.normalized_incident
    object.__setattr__(normalized, "tenant", tenant)
    object.__setattr__(normalized, "env", env)
    return decision


def _record(decision) -> dict:
    table = MagicMock()
    with patch("src.agents.operations.aws.executor._DYNAMO") as dynamo:
        dynamo.Table.return_value = table
        _record_incident(
            incident_id="INC-12345678",
            decision=decision,
            executed=["AWS-RestartEKSPod"],
            resolved=True,
        )
    return table.put_item.call_args.kwargs["Item"]


class TestIncidentCarriesItsOwner:
    """
    The dashboard could not partition incidents by tenant because this writer
    dropped the tenant — `NormalizedIncident.tenant` existed and nothing read
    it. The read gap and the write gap were the same gap, and the read side is
    where it was noticed.
    """

    def test_owned_incident_records_tenant_and_env(self):
        item = _record(_tenant_decision())
        assert item["tenant"] == "acme"
        assert item["env"] == "dev"

    def test_unowned_incident_omits_the_keys_entirely(self):
        """
        Absent, not empty-string. "No tenant recorded" and "belongs to tenant ''"
        are different facts, and the reader treats the first as admin-only —
        writing "" would make every legacy row look like a real tenant named
        nothing.
        """
        item = _record(_decision())
        assert "tenant" not in item
        assert "env" not in item

    def test_aws_path_without_tenancy_still_records(self):
        """The AWS path has no tenant and never had this problem; it must not break."""
        item = _record(_decision())
        assert item["provider"] == "aws" and item["runbook_id"] == "eks-pod-oom"


class TestTheCloudRowKnowsWhenItFired:
    """The on-prem writer was corrected first; this is the cloud half.

    `created_at`/`resolved_at` are both the write moment, so without the fire
    time a cloud incident lands on the timeline whenever it happened to be
    processed and the gap between breaking and noticing is not derivable at all.
    The dashboard already reads `triggered_at` — the reader existed before the
    writer, which is the same asymmetry the tenant fix directly above closed.
    """

    def test_fire_time_is_recorded_from_the_normalized_incident(self):
        item = _record(_decision())
        assert item["triggered_at"], "the timeline cannot place an incident without it"

    def test_absent_when_the_source_reported_none(self):
        import dataclasses

        decision = _decision()
        decision.analyzer.detector.normalized_incident = dataclasses.replace(
            decision.analyzer.detector.normalized_incident, triggered_at=""
        )
        assert "triggered_at" not in _record(decision), (
            "a defaulted fire time asserts a moment that never happened"
        )


class TestConfidenceReachesTheDashboard:
    """It has always been rendered and never been written.

    The detail view shows "confidence n/a" when it is missing, so every cloud
    incident has displayed that since the view existed — the analyser produced a
    number and this writer dropped it.
    """

    def test_confidence_is_recorded(self):
        assert _record(_decision())["confidence"] == Decimal("0.98")

    def test_it_is_a_decimal_because_a_float_would_delete_the_row(self):
        """boto3's resource layer rejects Python floats outright, and the raise
        would be caught by this writer's own `except Exception` — so the wrong
        type here does not degrade one field, it loses the whole incident."""
        assert isinstance(_record(_decision())["confidence"], Decimal)

    def test_no_float_survives_anywhere_in_the_item(self):
        """One float anywhere is enough to fail the write, so this guards the
        whole item rather than the field that happened to introduce the risk."""
        floats = [k for k, v in _record(_decision()).items() if isinstance(v, float)]
        assert floats == [], f"floats reach DynamoDB as an exception, not a value: {floats}"
