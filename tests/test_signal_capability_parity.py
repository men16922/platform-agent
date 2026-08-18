"""
A provider may decline to *recommend* a capability only if it cannot execute it.

`recommended_capabilities` is not decoration. For GCP and Azure, tier 2 of
`_select_runbook` resolves its actions from **these recommendations** — not from
the matched runbook's `steps` or `capabilities`, which only gate the match. So a
capability a provider implements but never recommends is a remediation that
provider can never apply.

Measured 2026-08-17 by sweeping all four signal adapters × every resource type
they classify, and asking the *execution* adapter whether the missing capability
resolves. Four asymmetries, of two different kinds:

    streaming-consumer   azure          rebalance_consumer   3-vs-1, implemented → fixed
    kubernetes-workload  aws/gcp/azure  rollback_release     1-vs-3, disruptive  → open policy

The first was an oversight: the four adapters were written in one commit
(`a22a283`) and Azure was born without it, while its execution adapter gained
`AZURE-RebalanceEventHubConsumer` in the commit that claims "9 runbooks × 4
providers". Wrong from the start, not gone stale — the shape M19 ⓑ and M33 both
had.

The second is **not** a defect this test may decide. Only on-prem recommends
`rollback_release`, so the majority is the side without it, and rolling a release
back is materially more disruptive than restarting a workload. Whether the other
three should recommend it is the kind of policy call `NEXT_PLAN` keeps as an open
item; what this file adds is that the call is now visible in code with its reason
attached, instead of living only in a doc nobody diffs.

⚠️ Related open item, deliberately not resolved here: Azure's executor reports
`resolved` without executing (`docs/evidence/azure-executor-reports-resolved-
without-executing.log`). Adding a recommendation gives Azure one more action it
will claim to have taken. That is an argument for fixing the executor, not for
leaving a provider unable to reach its own implementation.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

from src.agents.adapters.registry import get_execution_adapter
from src.agents.models import NormalizedIncident

ROOT = pathlib.Path(__file__).resolve().parents[1]
PROVIDERS = ("aws", "gcp", "azure", "onprem")

#: (resource_type, provider, capability) triples where the provider implements the
#: capability and still does not recommend it. Every entry needs a reason, because
#: an unexplained entry is how a real gap gets parked here forever.
JUSTIFIED_GAPS = {
    # Only on-prem recommends this, so the majority is the side without it, and a
    # release rollback is materially more disruptive than a restart. Open policy
    # question (`NEXT_PLAN` capability 스캔 ⓐ·ⓒ family): either the other three
    # should recommend it, or on-prem should not. Measured 2026-08-17; not decided
    # by this test.
    ("kubernetes-workload", "aws", "rollback_release"),
    ("kubernetes-workload", "gcp", "rollback_release"),
    ("kubernetes-workload", "azure", "rollback_release"),
}


def _recommendation_table(provider: str) -> dict[str, list[str]]:
    """`{resource_type: [capability, ...]}` read off the adapter's own source.

    AST rather than calling the functions, because the four signatures differ
    (`_recommended_capabilities(alarm)` on AWS, `_capabilities(resource_type,
    signal_type)` on GCP, `_capabilities(resource_type)` on the other two). What
    they share is the shape `if resource_type == "<literal>": return [<literals>]`,
    and that is what the platform's recommendation policy actually is.
    """
    path = ROOT / f"src/agents/adapters/signals/{provider}.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    table: dict[str, list[str]] = {}
    for node in ast.walk(tree):
        if not (
            isinstance(node, ast.FunctionDef)
            and node.name in ("_capabilities", "_recommended_capabilities")
        ):
            continue
        for stmt in node.body:
            if not isinstance(stmt, ast.If):
                continue
            test = stmt.test
            if not (
                isinstance(test, ast.Compare)
                and isinstance(test.left, ast.Name)
                and test.left.id == "resource_type"
                and len(test.comparators) == 1
                and isinstance(test.comparators[0], ast.Constant)
            ):
                continue
            for body_stmt in stmt.body:
                if isinstance(body_stmt, ast.Return) and isinstance(body_stmt.value, ast.List):
                    table[test.comparators[0].value] = [
                        e.value for e in body_stmt.value.elts if isinstance(e, ast.Constant)
                    ]
    return table


TABLES = {p: _recommendation_table(p) for p in PROVIDERS}


def _resolves(provider: str, capability: str, resource_type: str) -> bool:
    incident = NormalizedIncident(
        provider=provider,
        service="checkout",
        resource_id="checkout-consumer",
        resource_type=resource_type,
        signal_type="saturation",
        recommended_capabilities=[capability],
        source_metadata={},
    )
    try:
        get_execution_adapter(provider).resolve_action(capability, incident)
    except ValueError:
        return False
    return True


def test_the_sweep_reads_all_four_adapters():
    """Anti-vacuous. An AST walk that matched nothing would pass every test below.

    `resolve_action` is keyed on (capability, resource_type) — the first version of
    this sweep asked with `kafka-topic` instead of `streaming-consumer` and got
    "unsupported on all four providers" for a capability all four implement.
    A parity test whose lookups all fail agrees with itself about nothing.
    """
    for provider in PROVIDERS:
        table = TABLES[provider]
        assert table, f"{provider}: no `resource_type == ...` recommendations parsed"
        assert "streaming-consumer" in table, f"{provider}: shape changed"
    assert _resolves("azure", "rebalance_consumer", "streaming-consumer"), (
        "the resolvability probe itself is broken: Azure implements "
        "`rebalance_consumer` for streaming-consumer"
    )


@pytest.mark.parametrize("provider", PROVIDERS)
def test_every_unrecommended_capability_is_one_the_provider_cannot_execute(provider):
    gaps = []
    for resource_type, recommended in sorted(TABLES[provider].items()):
        peers = set().union(
            *(set(TABLES[p].get(resource_type, ())) for p in PROVIDERS)
        )
        for capability in sorted(peers - set(recommended)):
            if (resource_type, provider, capability) in JUSTIFIED_GAPS:
                continue
            if _resolves(provider, capability, resource_type):
                gaps.append(f"{resource_type}/{capability}")

    assert gaps == [], (
        f"{provider} implements these capabilities and never recommends them, so "
        f"tier 2 can never apply them on {provider}: {gaps}. Either recommend "
        "them, or add the triple to JUSTIFIED_GAPS with the reason."
    )


def test_every_justified_gap_still_describes_reality():
    """An allowlist nobody re-measures becomes a place gaps go to die.

    Two ways an entry rots: the provider started recommending it (entry is
    stale), or it stopped being able to execute it (the gap is no longer the kind
    this allowlist is about). Both should force a re-read of the reason.
    """
    stale = []
    for resource_type, provider, capability in sorted(JUSTIFIED_GAPS):
        if capability in TABLES[provider].get(resource_type, ()):
            stale.append(f"{provider}/{resource_type}/{capability}: now recommended")
        elif not _resolves(provider, capability, resource_type):
            stale.append(f"{provider}/{resource_type}/{capability}: no longer resolvable")
    assert stale == [], f"JUSTIFIED_GAPS no longer matches the code: {stale}"
