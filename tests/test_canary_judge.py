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
    fetch_canary_alerts,
    judge_canary,
    judge_from_analysis,
    judge_observed_canary,
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


class TestTerraformWiring:
    """Enabling the gate must be an IaC change, not a hand-edit of chart values.

    Stage 1 is exposed through the addons module; stage 2 shipped without that
    wiring, which left `helm upgrade --set` as the only way to turn it on — and
    that drifts the release out from under the Terraform state that owns it.
    """

    @staticmethod
    def _module() -> Path:
        return CHART.parents[1]

    def test_enabling_is_a_module_variable(self):
        variables = (self._module() / "variables.tf").read_text(encoding="utf-8")
        assert 'variable "rollouts_demo_agent_analysis_enabled"' in variables
        assert 'variable "rollouts_demo_agent_analysis_url"' in variables

    def test_release_passes_both_values_through(self):
        rollouts = (self._module() / "rollouts.tf").read_text(encoding="utf-8")
        assert "agentAnalysis.enabled" in rollouts
        assert "agentAnalysis.url" in rollouts, (
            "the judge address is deployment-specific — hardcoding it strands non-default installs"
        )

    def test_terraform_default_matches_the_chart_default(self):
        """A module default of `true` would enable the gate on the next apply."""
        variables = (self._module() / "variables.tf").read_text(encoding="utf-8")
        block = variables.split('variable "rollouts_demo_agent_analysis_enabled"')[1].split("}")[0]
        assert "default = false" in block

    def test_the_two_judges_stay_independently_switchable(self):
        """Either judge alone is a valid configuration — one flag for both would erase that."""
        rollouts = (self._module() / "rollouts.tf").read_text(encoding="utf-8")
        assert "var.rollouts_demo_analysis_enabled" in rollouts
        assert "var.rollouts_demo_agent_analysis_enabled" in rollouts


class TestObservedCanary:
    """The gate must observe the canary, not take the caller's word for it.

    Live defect this encodes: the AnalysisTemplate posted a synthetic
    "CanaryUnderJudgement" FIRING alert and asked the analyzer for an opinion.
    That payload asserts a problem, so the analyzer reported one — a healthy
    canary came back `fail` at confidence 0.80. "No signal → pass" could never
    fire, because the gate manufactured the signal it judged.
    """

    @staticmethod
    def _pipeline(_signal, execute=False):
        return {"severity": "P1", "confidence": 0.9, "root_cause": "real outage"}

    def test_quiet_canary_passes(self):
        verdict = judge_observed_canary(
            "argo-rollouts", "rollouts-demo-abc",
            run_pipeline=self._pipeline,
            alert_source="http://am",
            http_get=lambda url, timeout: [],
        )
        assert verdict.verdict == VERDICT_PASS

    def test_no_alert_source_is_unknown_not_pass(self, monkeypatch):
        """An unobserved canary is not a quiet one."""
        monkeypatch.delenv("CANARY_ALERT_SOURCE", raising=False)
        verdict = judge_observed_canary(
            "argo-rollouts", "rollouts-demo-abc", run_pipeline=self._pipeline
        )
        assert verdict.verdict == VERDICT_UNKNOWN

    def test_unreachable_alert_source_is_unknown(self):
        def boom(url, timeout):
            raise OSError("connection refused")

        verdict = judge_observed_canary(
            "argo-rollouts", "rollouts-demo-abc",
            run_pipeline=self._pipeline,
            alert_source="http://am",
            http_get=boom,
        )
        assert verdict.verdict == VERDICT_UNKNOWN

    def test_real_alert_reaches_the_analyzer_and_fails(self):
        alerts = [{"labels": {"namespace": "argo-rollouts", "pod": "rollouts-demo-abc-1"}}]
        verdict = judge_observed_canary(
            "argo-rollouts", "rollouts-demo-abc",
            run_pipeline=self._pipeline,
            alert_source="http://am",
            http_get=lambda url, timeout: alerts,
        )
        assert verdict.verdict == VERDICT_FAIL

    def test_stable_pod_alerts_do_not_abort_the_canary(self):
        """Prefix match on the canary pod-template-hash is what separates the two."""
        alerts = [
            {"labels": {"namespace": "argo-rollouts", "pod": "rollouts-demo-STABLE-9"}},
            {"labels": {"namespace": "other-ns", "pod": "rollouts-demo-abc-1"}},
        ]
        verdict = judge_observed_canary(
            "argo-rollouts", "rollouts-demo-abc",
            run_pipeline=self._pipeline,
            alert_source="http://am",
            http_get=lambda url, timeout: alerts,
        )
        assert verdict.verdict == VERDICT_PASS

    def test_looked_and_empty_differs_from_could_not_look(self):
        assert fetch_canary_alerts("ns", "p", alert_source="", http_get=None) is None
        assert fetch_canary_alerts(
            "ns", "p", alert_source="http://am", http_get=lambda url, timeout: []
        ) == []


class TestTemplateSendsIdentityNotAClaim:
    def test_body_carries_identity(self):
        template = (CHART / "templates" / "analysis.yaml").read_text(encoding="utf-8")
        # Only the request body matters here; the comments above it explain why.
        body = [
            line for line in template.splitlines()
            if line.strip().startswith("{") and "canary" in line
        ]
        assert body, "the web provider must post a JSON body"
        joined = "\n".join(body)
        assert '"canary"' in joined and "podPrefix" in joined
        assert "alertname" not in joined, (
            "a synthetic firing alert asserts the problem it asks about"
        )


class TestCanaryTimescaleRule:
    """A gate is only as fast as the alerts it reads.

    kube-prometheus-stack's pod rules are written for steady-state ops —
    `KubePodCrashLooping` uses `for: 15m`. A canary lives two or three minutes,
    so with only the stock rules a canary that crashloops its entire life fires
    nothing, the gate honestly reports "no alerts firing", and the bad release
    is promoted. The chart therefore ships a canary-timescale rule.
    """

    @staticmethod
    def _rule() -> str:
        return (CHART / "templates" / "prometheusrule.yaml").read_text(encoding="utf-8")

    @staticmethod
    def _values() -> dict:
        return yaml.safe_load((CHART / "values.yaml").read_text(encoding="utf-8"))

    def test_rule_ships_with_the_gate(self):
        rule = self._rule()
        assert "kind: PrometheusRule" in rule
        assert ".Values.agentAnalysis.enabled" in rule, "the rule is an input to the gate"

    def test_window_is_shorter_than_a_canary(self):
        for_seconds = self._values()["agentAnalysis"]["ruleFor"]
        assert for_seconds.endswith("s"), "a minutes-long `for` outlives the canary it guards"
        assert int(for_seconds.rstrip("s")) <= 60

    def test_rule_carries_the_kps_selector_label(self):
        """Without it the rule is created, looks installed, and is never loaded."""
        assert "release: {{ .Values.agentAnalysis.ruleReleaseLabel }}" in self._rule()

    def test_rule_exposes_the_labels_the_gate_matches_on(self):
        rule = self._rule()
        assert "kube_pod_container_status_restarts_total" in rule
        assert 'namespace="{{ .Release.Namespace }}"' in rule, "must not alert on other namespaces"

    def test_rule_is_not_a_paging_rule(self):
        assert "severity: warning" in self._rule(), "a gate input must stay off the on-call path"

    def test_name_does_not_collide_with_the_stage_one_template(self):
        rule = self._rule()
        stage_one = self._values()["analysis"]["templateName"]
        assert stage_one not in rule, "two objects answering to one name invites the wrong deletion"
