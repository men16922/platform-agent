"""
The operator-registered runbook must be validated before it drives a decision.

`_select_runbook` has three tiers in every provider. Tier 1 is an exact-match
lookup in the incident store — DynamoDB on AWS, Firestore on GCP, Cosmos DB on
Azure — and those documents are **hand-registered out-of-band**. Tier 2 scans
`BUILTIN_RUNBOOKS`, which are constants in this repository.

Measured 2026-08-16, by counting which providers read each symbol of the shared
contract module: `fits_resource`, `validate_runbook` and `is_destructive_action`
are read by all three, and `normalise_runbook` by AWS alone. Following that odd
one out is what surfaced this — GCP and Azure called `validate_runbook` inside
the **tier 2** loop and not at all in tier 1. They were validating the one source
that cannot be malformed and trusting the one that can.

AWS gets it right, and says why, at its DynamoDB read:

    # Operator overrides are registered out-of-band; ignore malformed ones so a
    # bad hand-registered entry falls back to heuristic matching instead of
    # producing a broken decision downstream.

Nothing seeds Firestore or Cosmos today, so this was latent rather than live —
the same standing as the `rto_sec` defect found in the tier below it. The failure
it would have produced: a typo'd document is returned by the lookup, `if
firestore_runbook:` is true for any non-empty dict, and its `runbook_id` and
`rto_sec` are reported as the followed runbook. On AWS the identical mistake is
logged and dropped.

⚠️ **Measured 2026-08-17: this contract stopped at the top level.**
`validate_runbook` checked `runbook_id`, the list-of-str fields, `rto_sec` and
`provider` — and **nothing inside `steps`**, which is where `condition` lives. So
the tier this file exists to guard handed unvalidated steps to the walk that reads
them. Two consequences, both silent:

  - a misspelled condition key (`previous_step_fail`) matches no branch in
    `evaluate_condition`, which returns True — so a step gated as an *escalation*,
    the stronger remediation, runs on **every** incident. That is the same failure
    GCP and Azure produced on 2026-08-16 by not reading `condition` at all,
    reached through the opposite door: reading one that means nothing.
  - a non-dict `condition` raises TypeError from inside the walk, outside its try
    block — the 500 the comment below says validation exists to prevent.

A strict per-step validator already existed (`capability_schema.
validate_capability_runbook`) and **only tests ever called it**. The fix put the
condition clause in the shared contract module instead, because that is the one
all three providers read.

⚠️ **`require_alarm_name` is deliberately left at its default `False` here, and
that asymmetry with AWS is correct.** AWS reads
`table.get_item(Key={"alarm_name": alarm_name})`, so the attribute is on the item
by construction. GCP and Azure key by *document id*
(`.document(alarm_name)` / `read_item(item=alarm_name, …)`), so a correctly
registered document need not repeat the name as a field. Passing `True` here
would reject every valid override and make tier 1 unreachable — which is exactly
how tier 2 was broken before (`test_capability_catalog_scan.py`). The last test
below pins that.
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
from src.agents.runbooks.capability_schema import CONDITION_KEYS

ROOT = pathlib.Path(__file__).resolve().parents[1]
ALARM = "store-override-alarm"

# provider -> the tier-1 lookup to patch. AWS is checked separately: it validates
# inside the lookup itself, so there is no seam of this shape to patch.
STORE_LOOKUPS = {
    "gcp": "src.agents.operations.gcp.decision._lookup_firestore_runbook",
    "azure": "src.agents.operations.azure.decision._lookup_cosmos_runbook",
}

# Each is rejected by `validate_runbook` for a different clause, so a partial
# implementation cannot pass them all.
MALFORMED = {
    "no actions and no capabilities": {"runbook_id": "bad-override"},
    "rto_sec is prose": {
        "runbook_id": "bad-override",
        "actions": ["Custom-RestartWorkload"],
        "rto_sec": "as soon as possible",
    },
    "capabilities is a string": {
        "runbook_id": "bad-override",
        "capabilities": "restart_workload",
    },
    "not a dict at all": ["runbook_id", "bad-override"],
    # Added 2026-08-17. `validate_runbook` checked every top-level field and
    # nothing inside `steps`, so these four reached the walk that reads them.
    # Each carries valid top-level fields, so only the new clause can reject it.
    "step condition key is misspelled": {
        "runbook_id": "bad-override",
        "capabilities": ["restart_workload"],
        "steps": [{
            "name": "escalate",
            "capability": "rollback_release",
            # One letter short of the real key. No branch matches, so
            # `evaluate_condition` returns True and the escalation step —
            # the *stronger* remediation — runs on every incident.
            "condition": {"previous_step_fail": True},
        }],
    },
    "step condition is not a dict": {
        "runbook_id": "bad-override",
        "capabilities": ["restart_workload"],
        # `"previous_step_failed" in condition` on a str is a substring test, so
        # this does not merely mis-evaluate: `severity_in`'s branch raises
        # TypeError from inside the walk, outside its try block.
        "steps": [{"name": "restart", "capability": "restart_workload",
                   "condition": "previous_step_failed"}],
    },
    "step condition severity_in is a bare string": {
        "runbook_id": "bad-override",
        "capabilities": ["restart_workload"],
        # `context["severity"] not in "P12"` is a substring test — a P1 incident
        # satisfies a gate the operator wrote for P12.
        "steps": [{"name": "restart", "capability": "restart_workload",
                   "condition": {"severity_in": "P12"}}],
    },
    # ⚠️ Not a string. `steps: "restart"` was the first fixture and it is rejected
    # *without* the list check too — a str is iterable, so each character fails the
    # per-step dict check. Correct and broken implementations agreed, so the clause
    # took no load (measured: the mutation survived; Risk 12⑤). A number is not
    # iterable, and without the check `enumerate` raises TypeError out of a
    # validator documented to never raise — the tier-1 call site has no try.
    "steps is a number": {
        "runbook_id": "bad-override",
        "capabilities": ["restart_workload"],
        "steps": 5,
    },
}

#: Every form the evaluator understands, each of which must still be accepted —
#: the direction that keeps the new check from closing the tier it guards (M28's
#: `require_alarm_name` trap, one layer down).
VALID_CONDITIONS = {
    "previous_step_failed": {"previous_step_failed": True},
    "severity_in": {"severity_in": ["P1", "P2"]},
    "provider": {"provider": "gcp"},
    "all three at once": {
        "previous_step_failed": False,
        "severity_in": ["P2"],
        "provider": "gcp",
    },
    "absent": None,
}


def _decision(provider: str):
    return importlib.import_module(f"src.agents.operations.{provider}.decision")


def _analyzer(provider: str) -> AnalyzerOutput:
    alarm = AlarmContext(
        alarm_name=ALARM,
        alarm_arn="arn:...",
        state="ALARM",
        reason="threshold crossed",
        metric_name="memory_utilization",
        namespace="kubernetes.io/container",
    )
    return AnalyzerOutput(
        detector=DetectorOutput(
            alarm=alarm,
            normalized_incident=NormalizedIncident(
                provider=provider,
                service="checkout-api",
                resource_type="kubernetes_workload",
                resource_id="deploy/api",
                signal_type="reliability",
                recommended_capabilities=["restart_workload", "scale_out"],
                source_metadata={"alarm_name": ALARM},
            ),
        ),
        root_cause="container OOMKilled repeatedly",
        severity=Severity.P2,
        confidence=0.9,
    )


@pytest.mark.parametrize("provider", sorted(STORE_LOOKUPS))
@pytest.mark.parametrize("reason", sorted(MALFORMED), ids=sorted(MALFORMED))
def test_malformed_store_runbook_is_not_followed(provider, reason):
    module = _decision(provider)
    with mock.patch(STORE_LOOKUPS[provider], return_value=MALFORMED[reason]):
        runbook_id, _actions, _rto = module._select_runbook(_analyzer(provider))

    assert runbook_id != "bad-override", (
        f"{provider} tier 1 followed a runbook that `validate_runbook` rejects "
        f"({reason}). An override is hand-registered, so a malformed one must fall "
        "through to the catalog — AWS has dropped these since it added the check."
    )


@pytest.mark.parametrize("provider", sorted(STORE_LOOKUPS))
def test_a_valid_store_runbook_is_still_followed(provider):
    """The other direction — validation must not close the tier it guards.

    Without this, `return None` in the lookup would pass every test above.
    """
    registered = {
        "runbook_id": "operator-override",
        "capabilities": ["restart_workload"],
        "actions": ["Custom-RestartWorkload"],
        "rto_sec": 42,
        "steps": [{"name": "restart", "capability": "restart_workload"}],
    }
    module = _decision(provider)
    with mock.patch(STORE_LOOKUPS[provider], return_value=registered):
        runbook_id, _actions, rto = module._select_runbook(_analyzer(provider))

    assert runbook_id == "operator-override"
    assert rto == 42


@pytest.mark.parametrize("provider", sorted(STORE_LOOKUPS))
def test_a_document_without_runbook_id_is_still_followed(provider):
    """The document id *is* the name — a valid override need not repeat it.

    This is the test that would go red if someone "fixed" the asymmetry with AWS
    by passing `require_alarm_name=True`, or by validating before the id default
    is applied. Both would reject a correctly registered document and silently
    disable tier 1.
    """
    registered = {
        "capabilities": ["restart_workload"],
        "actions": ["Custom-RestartWorkload"],
        "rto_sec": 42,
    }
    module = _decision(provider)
    with mock.patch(STORE_LOOKUPS[provider], return_value=registered):
        runbook_id, _actions, rto = module._select_runbook(_analyzer(provider))

    assert runbook_id == ALARM, "the alarm name is the fallback id, as before"
    assert rto == 42


@pytest.mark.parametrize("provider", sorted(STORE_LOOKUPS))
@pytest.mark.parametrize("form", sorted(VALID_CONDITIONS), ids=sorted(VALID_CONDITIONS))
def test_a_step_condition_the_evaluator_understands_is_still_followed(provider, form):
    """The other direction for the condition clause, and the one that carries it.

    Rejecting malformed conditions is only safe if every *well-formed* one still
    passes. Without this, tightening the check to "conditions are not supported"
    would satisfy every rejection test above while silently disabling tier 1 —
    the same shape as `require_alarm_name=True`, one layer down.
    """
    registered = {
        "runbook_id": "operator-override",
        "capabilities": ["restart_workload"],
        "steps": [{
            "name": "restart",
            "capability": "restart_workload",
            "condition": VALID_CONDITIONS[form],
        }],
    }
    module = _decision(provider)
    with mock.patch(STORE_LOOKUPS[provider], return_value=registered):
        runbook_id, _actions, _rto = module._select_runbook(_analyzer(provider))

    assert runbook_id == "operator-override", (
        f"{provider} rejected a runbook whose step condition uses the documented "
        f"`{form}` form — validation must not close the tier it guards"
    )


def test_the_validator_and_the_evaluator_agree_on_the_key_set():
    """`CONDITION_KEYS` is the writer's copy of what the reader branches on.

    Re-derived from `evaluate_condition`'s own AST rather than trusted, because a
    fourth form added to the evaluator and not to this tuple would be rejected at
    registration as "unknown" — the validator would forbid what the reader
    supports. Two copies of a contract is how the last fix landed on one side
    only (M18 유지 규약).
    """
    src = (ROOT / "src/agents/runbooks/capability_schema.py").read_text(encoding="utf-8")
    fn = next(
        n for n in ast.walk(ast.parse(src))
        if isinstance(n, ast.FunctionDef) and n.name == "evaluate_condition"
    )
    branched_on = tuple(
        node.left.value
        for node in ast.walk(fn)
        if isinstance(node, ast.Compare)
        and len(node.ops) == 1
        and isinstance(node.ops[0], ast.In)
        and isinstance(node.left, ast.Constant)
        and isinstance(node.left.value, str)
        and isinstance(node.comparators[0], ast.Name)
        and node.comparators[0].id == "condition"
    )
    assert branched_on, "no `\"key\" in condition` branch found — the shape changed"
    assert set(branched_on) == set(CONDITION_KEYS), (
        f"`evaluate_condition` branches on {sorted(branched_on)} but "
        f"CONDITION_KEYS declares {sorted(CONDITION_KEYS)}. The validator rejects "
        "anything outside CONDITION_KEYS, so a form the reader supports and this "
        "tuple omits is unregistrable."
    )


@pytest.mark.parametrize("reason", sorted(MALFORMED), ids=sorted(MALFORMED))
def test_aws_drops_the_same_documents(reason):
    """Parity, asked of AWS through its own seam.

    AWS validates inside `_lookup_dynamo` rather than at the call site, so the
    equivalent question is whether the lookup yields the item at all. Included so
    the three providers are held to one contract by one file — if AWS ever loses
    the check, this goes red next to its siblings rather than nowhere.
    """
    aws = _decision("aws")
    item = MALFORMED[reason]
    if isinstance(item, dict):
        item = {**item, "alarm_name": ALARM}

    table = mock.MagicMock()
    table.get_item.return_value = {"Item": item}
    with mock.patch("src.agents.operations.aws.decision._DYNAMO") as dynamo:
        dynamo.Table.return_value = table
        assert aws._lookup_dynamo(ALARM) is None, (
            f"AWS accepted a malformed override ({reason})"
        )
