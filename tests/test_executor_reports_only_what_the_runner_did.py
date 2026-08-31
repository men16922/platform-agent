"""
An executor may not report an action as executed unless its runner performed it.

`test_executor_dispatches_to_runner.py` asks the *source* whether the call is
there (AST). That is the right question for a table of stubs vs. live paths, and
it is the guard that made the Azure gap visible — but it cannot see the property
the gap actually violated. Measured 2026-08-16
(`docs/evidence/azure-executor-reports-resolved-without-executing.log`):

    _execute_single_action -> {"success": True}      (nothing ran)
      -> run_actions puts the action in `executed`
      -> resolution_verdict(executed, skipped).resolved is True
      -> Slack says "resolved" and `_record_incident` writes resolved=True

Every link in that chain was already tested. None of them was wrong. The chain
was fed a `success: True` that meant nothing had happened, so the guards for the
downstream links were all green about a lie told upstream — Risk 12④ⓐ, 결함을 그
그림자로 세지 말 것.

So this file asks the behaviour, on the two providers whose executors dispatch:

  1. the runner is really invoked, with the parameters the adapter resolved
  2. a runner that raises becomes `success: False` — which is what keeps the 11
     of 16 declared-but-unimplemented actions per provider (`ValueError:
     Unsupported ... action`) from being reported as done
  3. end to end, an incident whose only action failed is **not** resolved

Both providers, not just the one that was broken: the sibling-set failure this
repo keeps re-finding (M18~M20, Risk 12⑥) is a guard that walks one of a set. If
a third executor is ever wired, add it to `WIRED` — `test_the_wired_set_matches_
the_dispatch_table` fails until then, so the set cannot silently fall behind.
"""

from __future__ import annotations

import importlib
from unittest import mock

import pytest

from src.agents.models import (
    AlarmContext,
    AnalyzerOutput,
    DecisionOutput,
    DetectorOutput,
    NormalizedIncident,
    RemediationMode,
    Severity,
)
from src.agents.operations import _executor_common as common
from src.agents.runbooks.capability_schema import resolution_verdict

#: provider -> (executor module, runner module, runner function, a restart action)
#: Restart is chosen because all three of AWS/GCP/Azure implement it in their
#: runner, so a failure here is about dispatch and not about a missing branch.
WIRED = {
    "gcp": (
        "src.agents.operations.gcp.executor",
        "src.agents.operations.runners.gcp_runner",
        "run_gcp_action",
        "GCP-RolloutRestartGKEWorkload",
    ),
    "azure": (
        "src.agents.operations.azure.executor",
        "src.agents.operations.runners.azure_runner",
        "run_azure_action",
        "AZURE-RolloutRestartAKSWorkload",
    ),
}


def _incident(provider: str) -> NormalizedIncident:
    return NormalizedIncident(
        provider=provider,
        service="checkout-api",
        resource_type="kubernetes-workload",
        resource_id="deploy/api",
        signal_type="reliability",
        recommended_capabilities=["restart_workload"],
        source_metadata={"alarm_name": "checkout-5xx"},
    )


def _decision(provider: str, action: str) -> DecisionOutput:
    alarm = AlarmContext(
        alarm_name="checkout-5xx",
        alarm_arn="arn:aws:cloudwatch:us-east-1:111122223333:alarm:checkout-5xx",
        state="ALARM",
        reason="threshold crossed",
        metric_name="HTTPCode_Target_5XX_Count",
        namespace="AWS/ApplicationELB",
    )
    analyzer = AnalyzerOutput(
        detector=DetectorOutput(alarm=alarm, normalized_incident=_incident(provider)),
        severity=Severity.P1,
        root_cause="pods thrashing",
        confidence=0.9,
    )
    return DecisionOutput(
        analyzer=analyzer,
        runbook_id="rb-restart",
        remediation_mode=RemediationMode.AUTO,
        actions=[action],
    )


def _call(provider: str, *, runner):
    """Run `_execute_single_action` once with the runner replaced."""
    exec_mod_name, runner_mod_name, runner_fn, action = WIRED[provider]
    exec_mod = importlib.import_module(exec_mod_name)
    runner_mod = importlib.import_module(runner_mod_name)
    adapter = common.get_execution_adapter(provider)
    with mock.patch.object(runner_mod, runner_fn, runner):
        return exec_mod._execute_single_action(action, _incident(provider), adapter)


# ---------------------------------------------------------------------------
# 1. The runner is really invoked
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("provider", sorted(WIRED), ids=sorted(WIRED))
def test_the_runner_is_invoked_with_the_resolved_parameters(provider):
    spy = mock.MagicMock(return_value=None)
    result = _call(provider, runner=spy)

    assert spy.call_count == 1, (
        f"{provider}/executor.py returned {result} without calling its runner. "
        "That is the 2026-08-16 Azure defect exactly: a success nobody earned."
    )
    passed_action, passed_params = spy.call_args.args[0], spy.call_args.args[1]
    assert passed_action == WIRED[provider][3]
    assert passed_params == result["parameters"], (
        "the runner was called, but not with the parameters the adapter resolved — "
        "the report would then describe a different action than the one performed"
    )
    assert result["success"] is True


# ---------------------------------------------------------------------------
# 2. A runner that refuses or fails must not be reported as done
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("provider", sorted(WIRED), ids=sorted(WIRED))
def test_a_raising_runner_becomes_a_failure_not_a_success(provider):
    """Covers the unimplemented-action case without pretending to enumerate it:
    each runner raises `ValueError("Unsupported ... action: ...")` for the 11 of
    16 declared actions it has no branch for. What matters is that *any* raise
    from the runner lands as `success: False`."""
    boom = mock.MagicMock(side_effect=ValueError("Unsupported action: nope"))
    result = _call(provider, runner=boom)

    assert result["success"] is False, (
        f"{provider} swallowed a runner failure and still reported success"
    )
    assert "Unsupported action" in result["error"]


# ---------------------------------------------------------------------------
# 3. End to end: the incident must not come out resolved
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("provider", sorted(WIRED), ids=sorted(WIRED))
def test_a_failed_action_leaves_the_incident_unresolved(provider):
    exec_mod_name, runner_mod_name, runner_fn, action = WIRED[provider]
    exec_mod = importlib.import_module(exec_mod_name)
    runner_mod = importlib.import_module(runner_mod_name)
    boom = mock.MagicMock(side_effect=RuntimeError("ARM said no"))

    with mock.patch.object(runner_mod, runner_fn, boom):
        executed, skipped = common.run_actions(
            decision=_decision(provider, action),
            adapter_key=provider,
            execute_single_action=exec_mod._execute_single_action,
            log=mock.MagicMock(),
            log_prefix=f"{provider}_executor",
        )

    assert executed == [], f"{provider} recorded {executed} as executed after the runner raised"
    assert skipped == [action]
    assert resolution_verdict(executed, skipped).resolved is False, (
        "the incident would be posted to Slack and recorded as remediated for an "
        "action that failed — the exact shape measured on Azure on 2026-08-16"
    )


# ---------------------------------------------------------------------------
# Anti-vacuity: this set must not fall behind the dispatch table
# ---------------------------------------------------------------------------

def test_the_wired_set_matches_the_dispatch_table():
    """If someone wires a third executor, these behavioural checks must grow with
    it rather than keep passing about two providers. AWS is excluded by shape,
    not by oversight: its executor is the multi-cloud dispatcher and reaches the
    runners through `_run_external_action`, so it is not a single-runner row."""
    from tests.test_executor_dispatches_to_runner import EXPECTED

    dispatching = {
        name
        for name, (expected, _) in EXPECTED.items()
        if expected and name != "aws"
    }
    assert dispatching == set(WIRED), (
        f"dispatch table says {sorted(dispatching)} dispatch to their own runner, "
        f"but this file only asks {sorted(WIRED)} whether they tell the truth "
        "about it"
    )
