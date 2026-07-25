"""
Guards for the agent-as-release-gate (AnalysisTemplate stage 2).

The asymmetry that drives every rule here: wrongly aborting a good release costs
a retry, wrongly promoting a bad one ships it. So "cannot judge" must never read
as approval — an analyzer that is offline (confidence 0.0 heuristic fallback)
would otherwise silently rubber-stamp every deploy.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

from src.agents.ai.canary_judge import (
    VERDICT_FAIL,
    VERDICT_PASS,
    VERDICT_UNKNOWN,
    judge_canary,
    judge_from_analysis,
)

CHART = Path(__file__).resolve().parents[1] / "infra" / "onprem" / "addons" / "charts" / "rollouts-demo"


def _analysis(**overrides):
    base = {
        "severity": "P3",
        "confidence": 0.9,
        "root_cause": "nothing serious",
        "runbook_id": "generic-recovery",
        "actions": [],
        "remediation_mode": "MANUAL",
    }
    base.update(overrides)
    return base


class TestVerdictRules:
    def test_no_signal_passes(self):
        """A quiet workload must not block its own canary."""
        verdict = judge_from_analysis({"severity": "", "confidence": 0.0})
        assert verdict.verdict == VERDICT_PASS
        assert "no incident signal" in verdict.reason

    def test_severe_finding_fails(self):
        verdict = judge_from_analysis(_analysis(severity="P1", root_cause="OOMKilled loop"))
        assert verdict.verdict == VERDICT_FAIL
        assert "OOMKilled" in verdict.reason

    def test_p2_also_fails(self):
        assert judge_from_analysis(_analysis(severity="P2")).verdict == VERDICT_FAIL

    def test_low_severity_passes(self):
        verdict = judge_from_analysis(_analysis(severity="P3"))
        assert verdict.verdict == VERDICT_PASS
        assert "below the abort threshold" in verdict.reason

    def test_low_confidence_is_unknown_not_pass(self):
        """
        Confidence 0.0 is the heuristic fallback that runs when no model is
        reachable. Promoting on it would let an offline analyzer approve
        everything — the exact failure this gate exists to prevent.
        """
        verdict = judge_from_analysis(_analysis(severity="P3", confidence=0.0))
        assert verdict.verdict == VERDICT_UNKNOWN
        assert "refusing to promote" in verdict.reason

    def test_low_confidence_beats_even_a_severe_finding(self):
        """Order matters: an untrustworthy P1 is still untrustworthy."""
        verdict = judge_from_analysis(_analysis(severity="P1", confidence=0.1))
        assert verdict.verdict == VERDICT_UNKNOWN

    def test_confidence_threshold_is_configurable(self):
        assert judge_from_analysis(_analysis(confidence=0.5), min_confidence=0.9).verdict == VERDICT_UNKNOWN
        assert judge_from_analysis(_analysis(confidence=0.5), min_confidence=0.4).verdict == VERDICT_PASS

    def test_unparseable_confidence_is_treated_as_zero(self):
        verdict = judge_from_analysis(_analysis(confidence="high"))
        assert verdict.verdict == VERDICT_UNKNOWN

    def test_trace_id_is_carried_for_the_human_reader(self):
        verdict = judge_from_analysis(_analysis(trace_id="abc123"))
        assert verdict.details["trace_id"] == "abc123"

    def test_serialisation_exposes_verdict_as_a_scalar(self):
        """Argo asserts on jsonPath {$.verdict}; it must be a top-level scalar."""
        payload = judge_from_analysis(_analysis()).to_dict()
        assert payload["verdict"] in {VERDICT_PASS, VERDICT_FAIL, VERDICT_UNKNOWN}
        assert isinstance(payload["confidence"], float)


class TestPipelineIntegration:
    def test_analysis_only_never_executes(self):
        """A release gate that could remediate is an unreviewed remediation."""
        seen = {}

        def fake(signal, execute=True):
            seen["execute"] = execute
            return _analysis(severity="P1")

        judge_canary({"alerts": []}, run_pipeline=fake)
        assert seen["execute"] is False

    def test_pipeline_failure_is_unknown_not_pass(self):
        def boom(signal, execute=True):
            raise RuntimeError("analyzer unreachable")

        verdict = judge_canary({"alerts": []}, run_pipeline=boom)
        assert verdict.verdict == VERDICT_UNKNOWN
        assert "analyzer unreachable" in verdict.reason


class TestEndpoint:
    @pytest.fixture
    def client(self, monkeypatch, tmp_path):
        monkeypatch.setenv("PLATFORM_INCIDENT_FILE", str(tmp_path / "i.jsonl"))
        monkeypatch.setenv("PLATFORM_APPROVALS_FILE", str(tmp_path / "a.jsonl"))
        from src.agents.ai import onprem_webhook_api

        return TestClient(onprem_webhook_api.app), onprem_webhook_api

    def test_empty_payload_rejected(self, client):
        api_client, _ = client
        assert api_client.post("/canary/judge", json={}).status_code == 400

    def test_verdict_shape(self, client, monkeypatch):
        api_client, module = client
        monkeypatch.setattr(
            module, "run_incident_pipeline", lambda signal, execute=True: _analysis(severity="P1")
        )
        response = api_client.post("/canary/judge", json={"alerts": [{"labels": {}}]})
        assert response.status_code == 200
        body = response.json()
        assert body["verdict"] == VERDICT_FAIL
        assert "confidence" in body and "reason" in body


class TestChartWiring:
    @staticmethod
    def _values() -> dict:
        return yaml.safe_load((CHART / "values.yaml").read_text(encoding="utf-8"))

    @staticmethod
    def _template() -> str:
        return (CHART / "templates" / "analysis.yaml").read_text(encoding="utf-8")

    def test_agent_analysis_defaults_off(self):
        """Needs the webhook reachable FROM the cluster — not a safe default."""
        assert self._values()["agentAnalysis"]["enabled"] is False

    def test_only_pass_promotes(self):
        """`unknown` must not satisfy the success condition."""
        assert 'successCondition: result == "pass"' in self._template()

    def test_web_provider_posts_json_and_reads_the_verdict(self):
        template = self._template()
        assert "web:" in template and "method: POST" in template
        assert 'jsonPath: "{$.verdict}"' in template

    def test_timeout_accommodates_an_llm_call(self):
        """The judgement includes inference (~4-5s live); a tight timeout reads as a failed gate."""
        assert self._values()["agentAnalysis"]["timeoutSeconds"] >= 20

    def test_both_judges_can_run_together(self):
        rollout = (CHART / "templates" / "rollout.yaml").read_text(encoding="utf-8")
        assert "or .Values.analysis.enabled .Values.agentAnalysis.enabled" in rollout
        assert rollout.count("templateName:") == 2, "each judge is listed independently"
