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
from unittest import mock

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


class TestDeclaredCapability:
    """A runbook step can name its own check; an unrunnable one is never a pass."""

    def test_declared_capability_overrides_the_action_table(self, monkeypatch):
        from src.agents.operations.runners import onprem_verify as mod

        seen = {}

        def fake_check(action, params, scope, timeout_sec):
            seen["called"] = True
            return mod.VerificationResult(
                step_name=action, capability="assert_replica_count", passed=True, detail="ok",
            )

        monkeypatch.setattr(mod, "_CHECKS", {"assert_replica_count": fake_check})
        monkeypatch.setattr(
            "src.agents.operations.runners.onprem_runner._is_live", lambda: True
        )
        result = mod.verify_onprem_action(
            "ONPREM-RestartWorkload", {}, mock.MagicMock(), scope=object(),
            capability="assert_replica_count",
        )
        assert seen.get("called") is True
        assert result is not None and result.passed is True

    def test_unknown_declared_capability_fails_rather_than_silently_passing(self):
        from src.agents.operations.runners import onprem_verify as mod

        result = mod.verify_onprem_action(
            "ONPREM-RestartWorkload", {}, mock.MagicMock(), scope=object(),
            capability="assert_something_nobody_implemented", step_name="scale",
        )
        assert result is not None
        assert result.passed is False, "a check we cannot run must not count as verified"
        assert result.step_name == "scale"


class TestEveryDeclaredCheckIsImplemented:
    """The audit `test_unknown_declared_capability_fails…` implies but never runs.

    That test proves an unimplemented check cannot pass. It does not ask whether
    the catalog currently declares one — which is the question that decides
    whether any runbook is quietly shipping a verification it can never perform.

    Measured 2026-08-13, and the measuring got it wrong first: a verify capability
    has **two** declaration sources, and the first pass read only the catalog.
    `verify_onprem_action` resolves `capability or VERIFY_FOR_ACTION.get(action)`,
    so the action→check table declares them too — `assert_node_unschedulable` lives
    only there and looked orphaned until the second source was counted. Same shape
    as the two defects found earlier the same day: a set-based check that walks one
    member of a family. Hence `_declared()` below reads both, by construction.
    """

    def _declared(self) -> dict[str, list[str]]:
        from src.agents.runbooks.catalog import CAPABILITY_RUNBOOKS

        sources: dict[str, list[str]] = {}
        for rb_id, runbook in CAPABILITY_RUNBOOKS.items():
            for step in runbook.get("steps", []):
                capability = (step.get("verify") or {}).get("capability")
                if capability:
                    sources.setdefault(capability, []).append(f"catalog:{rb_id}.{step['name']}")
        for action, capability in onprem_verify.VERIFY_FOR_ACTION.items():
            sources.setdefault(capability, []).append(f"action-table:{action}")
        return sources

    def test_the_audit_reads_both_declaration_sources(self):
        """Ground truth. Reading only the catalog reported a false orphan."""
        declared = self._declared()
        assert "assert_node_unschedulable" in declared, (
            "the action→check table is no longer being read, so this audit is "
            "back to walking one member of the family"
        )
        assert any(s.startswith("catalog:") for v in declared.values() for s in v), (
            "the catalog is no longer being read"
        )

    #: Declared with no implementation, deliberately. Listed rather than tolerated
    #: so that shrinking or growing it is an edit somebody makes on purpose.
    KNOWN_UNIMPLEMENTED = {
        # lambda-throttle's verify. On-prem is the only provider that runs checks
        # at all, and it can resolve no step of a lambda runbook — the reason the
        # gate carries a justified skip. Implementing it would be an unreachable
        # check; `verify_onprem_action` already refuses to call it a pass.
        "assert_concurrency_applied",
    }

    def test_every_declared_verify_capability_has_a_check(self):
        declared = self._declared()
        missing = sorted(set(declared) - set(onprem_verify._CHECKS) - self.KNOWN_UNIMPLEMENTED)

        assert missing == [], (
            f"{missing} are declared as verification but no check implements them, "
            "so a runbook that reaches one reports `passed=False` — a remediation "
            "that may well have worked, recorded as unverified. Implement the "
            "check, or add it to KNOWN_UNIMPLEMENTED with the reason."
        )

    def test_the_known_gap_is_still_a_gap(self):
        """Keeps the exception list from outliving its reason."""
        stale = sorted(self.KNOWN_UNIMPLEMENTED & set(onprem_verify._CHECKS))
        assert stale == [], f"{stale} are implemented now — drop them from KNOWN_UNIMPLEMENTED"

        undeclared = sorted(self.KNOWN_UNIMPLEMENTED - set(self._declared()))
        assert undeclared == [], f"{undeclared} are no longer declared — drop them"
