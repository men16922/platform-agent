"""
Guards for on-prem post-execution verification.

The contract: an action that was *dispatched* is not the same fact as a
remediation that *worked*. These checks fill the `verified` axis of
`resolution_verdict`, and the failure modes they must avoid are asymmetric —
claiming success without evidence is far worse than reporting "unknown".
"""

from __future__ import annotations

import json
import subprocess

import pytest

from src.agents.operations.runners import onprem_verify
from src.agents.platform.scope import IncidentScope

SCOPE = IncidentScope(
    tenant="acme", env="dev", kubeconfig_path="/creds/acme.kubeconfig", approval_id="APR-1"
)
PARAMS = {"Namespace": ["acme-dev"], "WorkloadName": ["api"]}


class _Log:
    def __init__(self):
        self.events = []

    def _record(self, event, **kw):
        self.events.append(event)

    info = warning = error = _record


@pytest.fixture(autouse=True)
def _live(monkeypatch):
    """Default these tests to live mode; log-only is covered explicitly below."""
    monkeypatch.setenv("ONPREM_EXECUTOR_LIVE", "true")
    monkeypatch.delenv("TESTING", raising=False)


def _fake_kubectl(monkeypatch, code=0, out="", err=""):
    seen: dict = {}

    def fake(args, scope, timeout):
        seen["args"] = args
        seen["scope"] = scope
        return code, out, err

    monkeypatch.setattr(onprem_verify, "_kubectl", fake)
    return seen


class TestDispatchPolicy:
    def test_action_with_nothing_to_verify_returns_none(self):
        assert onprem_verify.verify_onprem_action("ONPREM-CreateChangeRequest", {}, _Log()) is None

    def test_log_only_mode_verifies_nothing(self, monkeypatch):
        """
        Nothing was executed, so there is nothing to verify. Returning a *failed*
        check here would turn "we chose not to act" into "we acted and it failed"
        and flip resolved to False on the default safe configuration.
        """
        monkeypatch.setenv("ONPREM_EXECUTOR_LIVE", "false")
        log = _Log()
        assert onprem_verify.verify_onprem_action(
            "ONPREM-RolloutRestartWorkload", PARAMS, log, SCOPE
        ) is None
        assert "onprem_verify.skipped_log_only" in log.events

    def test_live_without_scope_is_a_failed_check_not_a_skip(self):
        """We ran a live action and then could not confirm it — that is not success."""
        result = onprem_verify.verify_onprem_action(
            "ONPREM-RolloutRestartWorkload", PARAMS, _Log(), None
        )
        assert result is not None and result.passed is False
        assert "scoped credential" in result.detail

    def test_verification_uses_the_same_scoped_credential(self, monkeypatch):
        seen = _fake_kubectl(monkeypatch, code=0, out="deployment successfully rolled out")
        onprem_verify.verify_onprem_action("ONPREM-RolloutRestartWorkload", PARAMS, _Log(), SCOPE)
        assert seen["scope"] is SCOPE, "a check must not reach further than the action it proves"


class TestWorkloadReady:
    def test_converged_rollout_passes(self, monkeypatch):
        _fake_kubectl(monkeypatch, code=0, out="deployment \"api\" successfully rolled out")
        result = onprem_verify.verify_onprem_action(
            "ONPREM-RolloutRestartWorkload", PARAMS, _Log(), SCOPE
        )
        assert result.passed is True

    def test_failed_rollout_fails_the_check(self, monkeypatch):
        _fake_kubectl(monkeypatch, code=1, err="error: deployment exceeded its progress deadline")
        result = onprem_verify.verify_onprem_action(
            "ONPREM-RolloutRestartWorkload", PARAMS, _Log(), SCOPE
        )
        assert result.passed is False
        assert "progress deadline" in result.detail

    def test_timeout_is_a_failure_not_an_exception(self, monkeypatch):
        """A verification that cannot answer in time has failed to answer."""
        def boom(args, scope, timeout):
            raise subprocess.TimeoutExpired(cmd="kubectl", timeout=timeout)

        monkeypatch.setattr(onprem_verify, "_kubectl", boom)
        result = onprem_verify.verify_onprem_action(
            "ONPREM-RolloutRestartWorkload", PARAMS, _Log(), SCOPE
        )
        assert result.passed is False
        assert "converge" in result.detail

    def test_missing_workload_name_fails(self, monkeypatch):
        _fake_kubectl(monkeypatch)
        result = onprem_verify.verify_onprem_action(
            "ONPREM-RolloutRestartWorkload", {"Namespace": ["acme-dev"]}, _Log(), SCOPE
        )
        assert result.passed is False

    def test_rollback_is_verified_the_same_way(self, monkeypatch):
        seen = _fake_kubectl(monkeypatch, code=0, out="rolled out")
        result = onprem_verify.verify_onprem_action(
            "ONPREM-ArgoRolloutRollback", PARAMS, _Log(), SCOPE
        )
        assert result.passed is True
        assert "rollout" in seen["args"] and "status" in seen["args"]


class TestReplicaCount:
    @staticmethod
    def _params(desired="3"):
        return {**PARAMS, "DesiredReplicas": [desired]}

    def test_ready_replicas_meeting_target_passes(self, monkeypatch):
        _fake_kubectl(monkeypatch, code=0, out=json.dumps({"status": {"readyReplicas": 3}}))
        result = onprem_verify.verify_onprem_action(
            "ONPREM-ScaleWorkload", self._params(), _Log(), SCOPE
        )
        assert result.passed is True
        assert "readyReplicas=3" in result.detail

    def test_accepted_but_not_ready_fails(self, monkeypatch):
        """A scale the API accepted but that never became ready is not a fix."""
        _fake_kubectl(monkeypatch, code=0, out=json.dumps({"status": {"readyReplicas": 1}}))
        result = onprem_verify.verify_onprem_action(
            "ONPREM-ScaleWorkload", self._params(), _Log(), SCOPE
        )
        assert result.passed is False

    def test_absent_ready_replicas_reads_as_zero(self, monkeypatch):
        _fake_kubectl(monkeypatch, code=0, out=json.dumps({"status": {}}))
        result = onprem_verify.verify_onprem_action(
            "ONPREM-ScaleWorkload", self._params(), _Log(), SCOPE
        )
        assert result.passed is False

    def test_unparseable_target_fails(self, monkeypatch):
        _fake_kubectl(monkeypatch)
        result = onprem_verify.verify_onprem_action(
            "ONPREM-ScaleWorkload", self._params("many"), _Log(), SCOPE
        )
        assert result.passed is False

    def test_malformed_json_fails_rather_than_raising(self, monkeypatch):
        _fake_kubectl(monkeypatch, code=0, out="not json")
        result = onprem_verify.verify_onprem_action(
            "ONPREM-ScaleWorkload", self._params(), _Log(), SCOPE
        )
        assert result.passed is False


class TestNodeDrain:
    def test_cordoned_node_passes(self, monkeypatch):
        _fake_kubectl(monkeypatch, code=0, out="true")
        result = onprem_verify.verify_onprem_action(
            "ONPREM-DrainNode", {"NodeName": ["worker-1"]}, _Log(), SCOPE
        )
        assert result.passed is True

    def test_still_schedulable_node_fails(self, monkeypatch):
        """A drain that left the node schedulable did not do what the runbook claimed."""
        _fake_kubectl(monkeypatch, code=0, out="")
        result = onprem_verify.verify_onprem_action(
            "ONPREM-DrainNode", {"NodeName": ["worker-1"]}, _Log(), SCOPE
        )
        assert result.passed is False


class TestVerdictIntegration:
    def test_failed_required_check_withholds_resolution(self):
        from src.agents.runbooks.capability_schema import VerificationResult, resolution_verdict

        verdict = resolution_verdict(
            ["ONPREM-RolloutRestartWorkload"], [],
            [VerificationResult("ONPREM-RolloutRestartWorkload", "assert_workload_ready", False)],
        )
        assert verdict.dispatched is True   # the action DID run
        assert verdict.resolved is False    # but it did not help
        assert verdict.verified is False

    def test_no_verifications_keeps_the_historical_semantics(self):
        from src.agents.runbooks.capability_schema import resolution_verdict

        verdict = resolution_verdict(["A"], [], [])
        assert verdict.resolved is True
        assert verdict.verified is None, "absent evidence must read as unknown, not proven"
