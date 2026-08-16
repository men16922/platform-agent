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

import importlib
from unittest import mock

import pytest

from src.agents.models import (
    AlarmContext,
    AnalyzerOutput,
    DetectorOutput,
    NormalizedIncident,
    Severity,
)

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
