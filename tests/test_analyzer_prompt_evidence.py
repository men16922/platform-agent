"""
Does the evidence we normalise actually reach the model?

Found by sweeping for the defect class this repo has now hit six times in two
days: a field that is declared, populated, stored — and read by nobody. Of 437
declared fields, `NormalizedIncident.severity_hint` was the one with teeth.

Every signal adapter fills it (Alertmanager's `severity` label, GCP and Azure
severity, the AWS alarm state), and nothing anywhere consumed it. So the single
classification a human made *in advance* was dropped, and severity — which
decides AUTO vs APPROVE, i.e. whether a remediation runs with no human in the
loop — was inferred from prose alone. Observed live on 2026-07-29: an
Alertmanager rule labelled `severity: warning` was graded P1 and remediated
immediately.

These tests assert the prompt, because the prompt is the only consumer. A test
that checked `severity_hint` were merely *set* would have passed for as long as
the field has existed.
"""

from __future__ import annotations

import pytest

from src.agents.models import AlarmContext, DetectorOutput, NormalizedIncident
from src.agents.operations.aws.analyzer import _SYSTEM_PROMPT, _build_prompt


def _detector(**incident_kwargs) -> DetectorOutput:
    return DetectorOutput(
        alarm=AlarmContext(
            alarm_name="payments-api",
            alarm_arn="",
            state="ALARM",
            reason="KubePodNotReady pod stuck in a non-ready state",
            metric_name="availability",
            namespace="ONPREM/kubernetes-workload",
        ),
        normalized_incident=NormalizedIncident(
            provider="onprem",
            service="payments-api",
            resource_type="kubernetes-workload",
            resource_id="payments-api-7d9f",
            signal_type="availability",
            **incident_kwargs,
        ),
    )


class TestOperatorSeverityReachesTheModel:
    def test_declared_severity_is_in_the_prompt(self):
        prompt = _build_prompt(_detector(severity_hint="warning"))
        assert "warning" in prompt
        assert "Operator-declared severity" in prompt

    @pytest.mark.parametrize("declared", ["critical", "warning", "info", "P1", "Sev2"])
    def test_any_provider_vocabulary_survives_verbatim(self, declared):
        """Each provider has its own severity words. Normalising them here would
        be inventing a mapping; the model gets the operator's own term."""
        assert declared in _build_prompt(_detector(severity_hint=declared))

    def test_absent_hint_adds_no_line(self):
        """An alert with no declared severity must not get an empty or invented
        one — "the operator said nothing" and "the operator said none" differ."""
        prompt = _build_prompt(_detector())
        assert "Operator-declared severity" not in prompt

    def test_the_system_prompt_says_it_is_evidence_not_a_command(self):
        """The mapping from a provider's severity vocabulary to P1/P2/P3 is a
        policy call. Surfacing the label is not the same as obeying it, and the
        prompt has to say which one this is."""
        assert "Operator-declared severity" in _SYSTEM_PROMPT
        assert "not binding" in _SYSTEM_PROMPT


class TestTheRestOfTheEvidenceStillReachesIt:
    """Regression cover for the fields that were already wired."""

    def test_alert_detail_and_signal_are_present(self):
        detector = _detector(
            severity_hint="critical",
            observations={"summary": "pod OOMKilled, memory limit 256Mi exceeded"},
        )
        prompt = _build_prompt(detector)
        assert "OOMKilled" in prompt
        assert "payments-api" in prompt
        assert "kubernetes-workload" in prompt
