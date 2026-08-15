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

They run over **every analyzer that builds a prompt**, because the first version
of this file imported only the AWS one — while its own opening paragraph named
GCP and Azure as filling the field. That is the sibling-set trap this repo keeps
hitting: the fix landed in one provider and the other two went on dropping the
operator's classification. On-prem is covered here through AWS, which is the
module `onprem_incident_pipeline` actually calls.
"""

from __future__ import annotations

import importlib

import pytest

from src.agents.models import AlarmContext, DetectorOutput, NormalizedIncident

# Every provider with its own `_build_prompt`. On-prem is absent on purpose:
# `src/agents/ai/onprem_incident_pipeline.py` imports the AWS analyzer, so the
# AWS entry covers it. A fourth builder is covered by adding its name here.
ANALYZERS = ["aws", "gcp", "azure"]


def _analyzer(provider: str):
    return importlib.import_module(f"src.agents.operations.{provider}.analyzer")


def _prompt(provider: str, **incident_kwargs) -> str:
    return _analyzer(provider)._build_prompt(_detector(**incident_kwargs))


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


@pytest.mark.parametrize("provider", ANALYZERS)
class TestOperatorSeverityReachesTheModel:
    def test_declared_severity_is_in_the_prompt(self, provider):
        prompt = _prompt(provider, severity_hint="warning")
        assert "warning" in prompt
        assert "Operator-declared severity" in prompt

    @pytest.mark.parametrize("declared", ["critical", "warning", "info", "P1", "Sev2"])
    def test_any_provider_vocabulary_survives_verbatim(self, provider, declared):
        """Each provider has its own severity words. Normalising them here would
        be inventing a mapping; the model gets the operator's own term."""
        assert declared in _prompt(provider, severity_hint=declared)

    def test_absent_hint_adds_no_line(self, provider):
        """An alert with no declared severity must not get an empty or invented
        one — "the operator said nothing" and "the operator said none" differ.

        Load-bearing in the other direction: a builder that pasted the line
        unconditionally would satisfy every test above.
        """
        assert "Operator-declared severity" not in _prompt(provider)

    def test_the_system_prompt_says_it_is_evidence_not_a_command(self, provider):
        """The mapping from a provider's severity vocabulary to P1/P2/P3 is a
        policy call. Surfacing the label is not the same as obeying it, and the
        prompt has to say which one this is.

        Without this the port would be worse than the gap it closes: a label the
        model reads as an instruction decides AUTO vs APPROVE by itself.
        """
        system_prompt = _analyzer(provider)._SYSTEM_PROMPT
        assert "Operator-declared severity" in system_prompt
        assert "not binding" in system_prompt


@pytest.mark.parametrize("provider", ANALYZERS)
class TestTheRestOfTheEvidenceStillReachesIt:
    """Regression cover for the fields that were already wired."""

    def test_alert_detail_and_signal_are_present(self, provider):
        prompt = _prompt(
            provider,
            severity_hint="critical",
            observations={"summary": "pod OOMKilled, memory limit 256Mi exceeded"},
        )
        assert "OOMKilled" in prompt
        assert "payments-api" in prompt
        assert "kubernetes-workload" in prompt
