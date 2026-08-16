"""
Guards for the executor actually walking a runbook's declared `steps`.

The gap these close: `capability_schema` has always been able to express
ordering, `condition`, `on_failure` and a per-step `verify` — and nothing
consumed it. `DecisionOutput` carried a flat `actions` list, so a runbook could
declare the full plan and still be executed as an unordered bag of actions with
no conditions and no proof that any of it helped.

Same family as the defects the live runs surfaced this week (a chart value
declared but never wired to the workload; a capability schema declared but
never wired to the executor): the tests were green because they tested the
declaration, not the consumption.
"""

from __future__ import annotations

from unittest import mock

from src.agents.models import (
    AlarmContext,
    AnalyzerOutput,
    DecisionOutput,
    DetectorOutput,
    RemediationMode,
    Severity,
)
from src.agents.operations.aws import executor as handler


def _decision(steps: list[dict], *, severity: Severity = Severity.P1) -> DecisionOutput:
    alarm = AlarmContext(
        alarm_name="checkout-5xx",
        alarm_arn="arn:aws:cloudwatch:us-east-1:111122223333:alarm:checkout-5xx",
        state="ALARM",
        reason="threshold crossed",
        metric_name="HTTPCode_Target_5XX_Count",
        namespace="AWS/ApplicationELB",
    )
    analyzer = AnalyzerOutput(
        detector=DetectorOutput(alarm=alarm),
        root_cause="elevated 5xx",
        severity=severity,
        confidence=0.9,
    )
    return DecisionOutput(
        analyzer=analyzer,
        runbook_id="eks-pod-oom",
        remediation_mode=RemediationMode.AUTO,
        actions=[s["action"] for s in steps],
        steps=steps,
    )


def _step(name: str, action: str, **overrides) -> dict:
    base = {
        "name": name,
        "capability": f"cap-{name}",
        "action": action,
        "parameters": {},
        "condition": None,
        "on_failure": "abort",
        "verify": None,
    }
    base.update(overrides)
    return base


def _run(decision):
    ssm = mock.MagicMock()
    ssm.start_automation_execution.return_value = {"AutomationExecutionId": "exec-1"}
    with mock.patch.object(handler, "_SSM", ssm), \
         mock.patch.object(handler, "_wait_for_ssm", mock.MagicMock()):
        executed, skipped, verifications, na = handler._run_ssm_actions(decision, mock.MagicMock())
    return executed, skipped, verifications, ssm, na


class TestStepsAreWalked:
    def test_steps_run_in_declared_order(self):
        decision = _decision([_step("a", "Doc-A"), _step("b", "Doc-B"), _step("c", "Doc-C")])
        executed, skipped, _v, _ssm, _na = _run(decision)
        assert executed == ["Doc-A", "Doc-B", "Doc-C"], "order is the point of a step list"
        assert skipped == []

    def test_flat_actions_path_is_untouched_when_no_steps_declared(self):
        """Every runbook predating the step schema must behave exactly as before."""
        decision = _decision([])
        decision.actions = ["Doc-Legacy"]
        decision.steps = []
        executed, skipped, _v, ssm, _na = _run(decision)
        assert executed == ["Doc-Legacy"]
        assert skipped == []
        ssm.start_automation_execution.assert_called_once()


class TestConditions:
    def test_false_condition_skips_without_running(self):
        decision = _decision([
            _step("a", "Doc-A"),
            _step("b", "Doc-B", condition={"previous_step_failed": True}),
        ])
        executed, skipped, _v, ssm, _na = _run(decision)
        assert executed == ["Doc-A"]
        assert skipped == ["Doc-B"]
        assert ssm.start_automation_execution.call_count == 1

    def test_condition_sees_the_previous_step_failing(self):
        """The schema's headline example: scale out only if the restart did not help."""
        ssm = mock.MagicMock()
        ssm.start_automation_execution.side_effect = [
            RuntimeError("restart failed"),
            {"AutomationExecutionId": "exec-2"},
        ]
        decision = _decision([
            _step("restart", "Doc-Restart", on_failure="continue"),
            _step("scale", "Doc-Scale", condition={"previous_step_failed": True}),
        ])
        with mock.patch.object(handler, "_SSM", ssm), \
             mock.patch.object(handler, "_wait_for_ssm", mock.MagicMock()):
            executed, skipped, _v, _na = handler._run_ssm_actions(decision, mock.MagicMock())
        assert executed == ["Doc-Scale"]
        assert skipped == ["Doc-Restart"]

    def test_severity_condition_is_honoured(self):
        decision = _decision(
            [_step("a", "Doc-A", condition={"severity_in": ["P1"]})],
            severity=Severity.P3,
        )
        executed, skipped, _v, _ssm, _na = _run(decision)
        assert executed == []
        assert skipped == ["Doc-A"]

    def test_the_severity_in_the_context_is_the_incident_s_own(self):
        """The direction the test above cannot see.

        `test_severity_condition_is_honoured` gates on `["P1"]` with an incident
        at P3 and asserts the step is skipped — but a context whose severity were
        **hardcoded** to any non-P1 value would skip it too. The only case it
        exercises is one where the correct and the broken implementation agree,
        which is Risk 12⑤ (기본값과 같은 값을 고른 픽스처는 가드가 아니다).

        `NEXT_PLAN` carried the matching worry from 08-12 — *"`severity`는 `"P2"`
        고정이라 `severity_in` 스텝이 생기면 재발한다"*. Measured 2026-08-16: false.
        `git log -L 175,175:…/aws/executor.py` dates
        `"severity": decision.analyzer.severity.value` to gate **1191**, long
        before that note. The premise was wrong when written — but the *guard*
        gap it pointed at was real, and this is it.

        So: same condition, an incident that matches it, and the step must run.
        Verified by mutation — pinning the context to `"P2"` leaves the test above
        green and turns this one red.
        """
        decision = _decision(
            [_step("a", "Doc-A", condition={"severity_in": ["P1"]})],
            severity=Severity.P1,
        )
        executed, skipped, _v, _ssm, _na = _run(decision)
        assert executed == ["Doc-A"], (
            "a P1 incident did not satisfy `severity_in: [P1]` — the condition "
            "context is not reading the incident's own severity"
        )
        assert skipped == []


class TestOnFailure:
    def test_abort_stops_the_remaining_steps(self):
        ssm = mock.MagicMock()
        ssm.start_automation_execution.side_effect = RuntimeError("boom")
        decision = _decision([_step("a", "Doc-A"), _step("b", "Doc-B")])
        with mock.patch.object(handler, "_SSM", ssm):
            executed, skipped, _v, _na = handler._run_ssm_actions(decision, mock.MagicMock())
        assert executed == []
        assert skipped == ["Doc-A", "Doc-B"], "a plan that stopped halfway did not finish"
        assert ssm.start_automation_execution.call_count == 1, "aborted steps must not be dispatched"

    def test_continue_runs_the_rest(self):
        ssm = mock.MagicMock()
        ssm.start_automation_execution.side_effect = [
            RuntimeError("boom"),
            {"AutomationExecutionId": "exec-2"},
        ]
        decision = _decision([_step("a", "Doc-A", on_failure="continue"), _step("b", "Doc-B")])
        with mock.patch.object(handler, "_SSM", ssm), \
             mock.patch.object(handler, "_wait_for_ssm", mock.MagicMock()):
            executed, skipped, _v, _na = handler._run_ssm_actions(decision, mock.MagicMock())
        assert executed == ["Doc-B"]
        assert skipped == ["Doc-A"]


class TestResolutionSemantics:
    """A condition-skip is "we correctly chose not to act", not a failure.

    Found by running the real pipeline: with conditions honoured but every skip
    counted against resolution, the runbook's SUCCESS path (restart worked, so
    do not scale) reported `resolved=False`. That is the same inversion log-only
    mode already taught us, and it would make every properly-conditioned runbook
    look broken exactly when it worked.
    """

    def test_condition_skip_does_not_withhold_resolution(self):
        from src.agents.runbooks.capability_schema import resolution_verdict

        verdict = resolution_verdict(["Doc-A"], ["Doc-B"], [], ["Doc-B"])
        assert verdict.resolved is True

    def test_a_failure_skip_still_withholds_resolution(self):
        """Only the condition-skips are exempt — a step that tried and failed is not."""
        from src.agents.runbooks.capability_schema import resolution_verdict

        assert resolution_verdict(["Doc-A"], ["Doc-B"], [], []).resolved is False
        assert resolution_verdict(["Doc-A"], ["Doc-B", "Doc-C"], [], ["Doc-C"]).resolved is False

    def test_executor_reports_condition_skips_separately(self):
        decision = _decision([
            _step("a", "Doc-A"),
            _step("b", "Doc-B", condition={"previous_step_failed": True}),
        ])
        _executed, skipped, _v, _ssm, not_applicable = _run(decision)
        assert skipped == ["Doc-B"], "still reported, for transparency"
        assert not_applicable == ["Doc-B"], "but not counted as a failure to act"


class TestSerialisationBoundary:
    """`steps` must survive DecisionOutput → dict → DecisionOutput.

    This is where the wiring actually died the first time: every unit test above
    passed because it built DecisionOutput in memory, while the real pipeline
    serialises the decision between stages. `_deserialise_decision` dropped
    `steps`, so the executor silently fell back to the flat path — conditions,
    on_failure and verify all gone, and nothing in the logs to say so.
    """

    def test_steps_survive_the_round_trip(self):
        from src.agents.operations.aws.executor import _deserialise_decision
        from src.agents.operations.aws.decision import _serialise

        decision = _decision([_step("a", "Doc-A", condition={"severity_in": ["P1"]})])
        restored = _deserialise_decision(_serialise(decision))
        assert restored.steps, "dropping steps here silently reinstates the flat path"
        assert restored.steps[0]["condition"] == {"severity_in": ["P1"]}


class TestDeclaredVerifyWins:
    """A step's own `verify` beats the global action→capability table.

    The table is a guess about what an action implies; the step's `verify` is
    the runbook author stating what would count as proof for THIS use of it.
    """

    def _onprem_decision(self, verify):
        decision = _decision([_step("a", "ONPREM-RestartWorkload", verify=verify)])
        incident = mock.MagicMock()
        incident.provider = "onprem"
        decision.analyzer.detector.normalized_incident = incident
        return decision

    def _run_onprem(self, decision):
        seen = {}

        def fake_verify(action, params, log, scope, capability=None, step_name=None, **kw):
            seen["capability"] = capability
            seen["step_name"] = step_name
            return None

        with mock.patch.object(handler, "_run_external_action", mock.MagicMock()), \
             mock.patch.object(handler, "_resolve_incident_scope", mock.MagicMock(return_value=None)), \
             mock.patch.dict(
                 "sys.modules",
                 {"src.agents.operations.runners.onprem_verify": mock.MagicMock(
                     verify_onprem_action=fake_verify)},
             ):
            handler._run_ssm_actions(decision, mock.MagicMock())
        return seen

    def test_declared_capability_is_passed_through(self):
        seen = self._run_onprem(self._onprem_decision({"capability": "assert_replica_count"}))
        assert seen["capability"] == "assert_replica_count"
        assert seen["step_name"] == "a", "the step name is what a human reads in the verdict"

    def test_no_declared_verify_falls_back_to_the_table(self):
        seen = self._run_onprem(self._onprem_decision(None))
        assert seen["capability"] is None, "None lets verify_onprem_action use VERIFY_FOR_ACTION"
