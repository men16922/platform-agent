"""
A runbook step's ``condition`` is contract. Every provider that walks steps reads it.

`capability_schema.evaluate_condition` documents three forms —
``previous_step_failed``, ``severity_in``, ``provider`` — and the AWS executor has
gated every step on it since the step walk existed. Measured 2026-08-16 by
counting which providers read each shared symbol: **`evaluate_condition` was read
by AWS alone.**

GCP and Azure flatten a store runbook's steps into a flat action list in
`_resolve_actions_from_runbook`, and that walk read `capability` and nothing else.
So an operator who registered a runbook following the documented contract got
**every conditional step unconditionally**. The sharpest case is the one the
catalog itself uses six times: ``{"previous_step_failed": true}`` marks an
*escalation* step — the stronger remediation to try after something failed.
Emitting it always means applying the stronger remediation when nothing failed.

Same shape as M19 (`resource_types` 미판독): a declared contract field that the
reading side ignores in two of three providers. Latent rather than live, because
GCP/Azure reach this walk only through tier 1 and nothing seeds Firestore or
Cosmos yet — the same standing as the tier-1 validation gap (M28) found next to it.

⚠️ **The two sides evaluate at different times, and that is not a bug to paper
over.** AWS walks steps *during execution*, so it updates `previous_step_failed`
as it goes and an escalation step can genuinely fire. GCP/Azure flatten at
*decision* time, where no step has run yet — so they evaluate against the initial
context and escalation steps are excluded rather than deferred. That is the half
of the contract this side can honestly keep; the other half needs the
step-walking executor only AWS has (see
`docs/evidence/azure-executor-reports-resolved-without-executing.log`). These
tests pin the initial-context semantics deliberately, so a future step-walking
executor has to change them on purpose.

⚠️ **All three forms are asked here, because this docstring names all three.**
Until 2026-08-17 it named three and pinned two: `provider` was covered only as a
pure function over a hand-built context, and deleting the key from the real
context dict left the suite green in all three walks. Prose being true is not
the same as the guard's reach (M20).
"""

from __future__ import annotations

import ast
import importlib
import pathlib
from unittest import mock

import pytest

from src.agents.models import (
    AlarmContext,
    AnalyzerOutput,
    DetectorOutput,
    NormalizedIncident,
    Severity,
)

ROOT = pathlib.Path(__file__).resolve().parents[1]
ALARM = "step-condition-alarm"

STORE_LOOKUPS = {
    "gcp": "src.agents.operations.gcp.decision._lookup_firestore_runbook",
    "azure": "src.agents.operations.azure.decision._lookup_cosmos_runbook",
}


def _decision(provider: str):
    return importlib.import_module(f"src.agents.operations.{provider}.decision")


def _analyzer(provider: str, severity: Severity = Severity.P2) -> AnalyzerOutput:
    return AnalyzerOutput(
        detector=DetectorOutput(
            alarm=AlarmContext(
                alarm_name=ALARM,
                alarm_arn="arn:...",
                state="ALARM",
                reason="threshold crossed",
                metric_name="memory_utilization",
                namespace="kubernetes.io/container",
            ),
            normalized_incident=NormalizedIncident(
                provider=provider,
                service="checkout-api",
                resource_type="kubernetes-workload",  # 하이픈 — 어댑터 키
                resource_id="deploy/api",
                signal_type="reliability",
                recommended_capabilities=["restart_workload"],
                source_metadata={"alarm_name": ALARM},
            ),
        ),
        root_cause="container OOMKilled repeatedly",
        severity=severity,
        confidence=0.9,
    )


def _runbook(*steps: dict) -> dict:
    return {
        "runbook_id": "operator-override",
        "capabilities": ["restart_workload"],
        "actions": ["placeholder"],
        "steps": list(steps),
    }


PLAIN = {"name": "restart", "capability": "restart_workload"}
ESCALATION = {
    "name": "scale-out-after-failure",
    "capability": "scale_out",
    "condition": {"previous_step_failed": True},
}


@pytest.mark.parametrize("provider", sorted(STORE_LOOKUPS))
def test_the_unconditional_step_is_emitted(provider):
    """Control. Without this, returning `[]` would satisfy every test below."""
    module = _decision(provider)
    with mock.patch(STORE_LOOKUPS[provider], return_value=_runbook(PLAIN)):
        _id, actions, _rto = module._select_runbook(_analyzer(provider))
    assert actions, "the plain step produced no action; the walk itself is broken"


@pytest.mark.parametrize("provider", sorted(STORE_LOOKUPS))
def test_an_escalation_step_is_not_emitted_up_front(provider):
    module = _decision(provider)
    with mock.patch(STORE_LOOKUPS[provider], return_value=_runbook(PLAIN)):
        _id, plain_only, _rto = module._select_runbook(_analyzer(provider))
    with mock.patch(STORE_LOOKUPS[provider], return_value=_runbook(PLAIN, ESCALATION)):
        _id, with_escalation, _rto = module._select_runbook(_analyzer(provider))

    assert with_escalation == plain_only, (
        f"{provider} emitted the `previous_step_failed: true` step at decision time "
        f"({with_escalation} vs {plain_only}). Nothing has run yet, so nothing has "
        "failed — emitting it means the escalation remediation fires when the "
        "incident never escalated."
    )


@pytest.mark.parametrize("provider", sorted(STORE_LOOKUPS))
@pytest.mark.parametrize(
    "severity,should_run",
    [(Severity.P1, True), (Severity.P2, False)],
    ids=["P1-matches", "P2-does-not"],
)
def test_severity_in_is_honoured(provider, severity, should_run):
    """The second documented form, and the one the repo flagged as untested:
    `NEXT_PLAN`'s "런북 walk ②" noted no catalog runbook declares `severity_in`,
    so no guard was written. An operator can still declare one."""
    step = {
        "name": "p1-only",
        "capability": "restart_workload",
        "condition": {"severity_in": ["P1"]},
    }
    module = _decision(provider)
    with mock.patch(STORE_LOOKUPS[provider], return_value=_runbook(step)):
        _id, actions, _rto = module._select_runbook(_analyzer(provider, severity))

    assert bool(actions) is should_run, (
        f"{provider} with severity {severity.value} and a step gated on "
        f"['P1'] produced {actions}"
    )


@pytest.mark.parametrize("provider", sorted(STORE_LOOKUPS))
@pytest.mark.parametrize(
    "gate_on_own,should_run",
    [(True, True), (False, False)],
    ids=["own-provider-runs", "other-provider-skipped"],
)
def test_the_provider_form_is_honoured(provider, gate_on_own, should_run):
    """The third documented form — the one this file named and did not ask.

    Measured 2026-08-17 by mutation: deleting ``"provider": normalized.provider``
    from the context dict in **all three** walks left the suite fully green
    (2218 passed), while deleting ``"severity"`` from the same two dicts turned
    it red. So the contract had three forms, the walks were asked about two, and
    the third was pinned only as a pure function over a hand-built context
    (`test_capability_runbook.py::test_provider_match`) — Risk 12④ⓒ, a guard
    that asks half of what it covers, under a docstring that enumerates all of it.

    ``own-provider-runs`` is the direction that carries the load. Dropping the
    key makes ``context.get("provider")`` None, which matches no declared
    provider, so every provider-gated step is skipped **forever and silently**;
    the ``other-provider-skipped`` case agrees with that broken implementation
    and would stay green on its own (Risk 12⑤).
    """
    gated_on = provider if gate_on_own else "aws"
    step = {
        "name": "provider-gated",
        "capability": "restart_workload",
        "condition": {"provider": gated_on},
    }
    module = _decision(provider)
    with mock.patch(STORE_LOOKUPS[provider], return_value=_runbook(step)):
        _id, actions, _rto = module._select_runbook(_analyzer(provider))

    assert bool(actions) is should_run, (
        f"a {provider} incident met a step gated on `provider: {gated_on}` "
        f"and produced {actions} — the condition context is not reading the "
        "incident's own provider"
    )


def _reads_evaluate_condition(path: pathlib.Path) -> bool:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return any(
        isinstance(n, ast.ImportFrom)
        and any(a.name == "evaluate_condition" for a in n.names)
        for n in ast.walk(tree)
    )


@pytest.mark.parametrize(
    "path",
    [
        "src/agents/operations/aws/executor.py",
        "src/agents/operations/gcp/decision.py",
        "src/agents/operations/azure/decision.py",
    ],
)
def test_every_step_walk_reads_the_contract(path):
    """Parity, asked structurally — the three walks live in different modules
    (AWS at execution time, the other two at decision time), so a behavioural
    test cannot cover them with one shape. What can be asked of all three is
    whether they read the contract at all, which is what was false."""
    assert _reads_evaluate_condition(ROOT / path), (
        f"{path} walks runbook steps without importing `evaluate_condition` — the "
        "`condition` field is then silently ignored, which is how GCP and Azure "
        "emitted escalation steps unconditionally until 2026-08-16."
    )
