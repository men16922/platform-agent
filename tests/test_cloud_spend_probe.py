"""The two defaults that reported "$0" while $8.81 was accruing.

On 2026-08-09 an AWS budget alert ($8.50 threshold, $8.81 actual) arrived right
after the same account had been checked by hand twice and reported as spending
nothing. Neither check was careless in an obvious way; both used a default that
answers a *different, reassuring* question:

  1. **Cost Explorer includes credits.** `get-cost-and-usage` with no filter is
     net of credits, so a credited account reads as $0 regardless of consumption.
     Budgets exclude `Credit`/`Refund`, which is why the alert fired and the hand
     query did not. "What will be charged" and "what am I consuming" are different
     questions and only the second finds a forgotten resource.
  2. **`describe-instances` is one region.** The instance was in `us-east-1`; the
     configured default region was `us-west-2`.

`scripts/probe_cloud_spend.py` hard-codes the fix for both. These are the guards
that make removing either one go red, because a probe that quietly loses its filter
is worse than no probe: it carries the authority of a measurement.

Static assertions on purpose — the probe talks to a live account, so exercising it
for real would need credentials and would make the gate non-deterministic. What is
falsifiable here is that the *right question* is baked in, which is exactly what was
wrong when it was asked by hand.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
PROBE = REPO / "scripts" / "probe_cloud_spend.py"


@pytest.fixture(scope="module")
def source() -> str:
    assert PROBE.is_file(), "the probe this file guards does not exist"
    return PROBE.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def module(source):
    """The probe's constants, without importing it (import must not shell out)."""
    tree = ast.parse(source)
    consts = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
            try:
                consts[node.targets[0].id] = ast.literal_eval(node.value)
            except ValueError:
                pass
    return consts


class TestCreditsAreExcluded:
    """Failure 1: the query answered "net of credits" and read as $0."""

    def test_the_filter_constant_excludes_credits_and_refunds(self, module):
        f = module.get("CREDIT_EXCLUDING_FILTER")
        assert f, "the probe no longer declares a credit-excluding filter"
        dims = f["Not"]["Dimensions"]
        assert dims["Key"] == "RECORD_TYPE"
        assert set(dims["Values"]) == {"Credit", "Refund"}, (
            "Budgets exclude exactly these two; dropping either re-opens the gap"
        )

    def test_the_cost_call_actually_passes_it(self, source):
        """Declaring the constant is not using it — that gap is how this returns."""
        assert "--filter" in source
        assert "json.dumps(CREDIT_EXCLUDING_FILTER)" in source, (
            "the filter must reach the CLI call, not just sit in a constant"
        )

    def test_the_filter_is_valid_json_for_the_cli(self, module):
        json.loads(json.dumps(module["CREDIT_EXCLUDING_FILTER"]))


class TestEveryRegionIsSwept:
    """Failure 2: one region was checked and the instance was in another."""

    def test_regions_are_enumerated_rather_than_assumed(self, source):
        assert "describe-regions" in source, (
            "a hard-coded region list goes stale; ask the account which regions exist"
        )

    def test_the_instance_query_is_run_per_region(self, source):
        assert '"--region", region' in source, (
            "describe-instances without --region uses one configured region — the bug"
        )

    def test_only_running_instances_are_reported(self, source):
        assert "Name=instance-state-name,Values=running" in source


class TestTheProbeCannotChangeAnything:
    """A cost probe that can also stop things turns a report into an action."""

    FORBIDDEN = (
        "stop-instances", "terminate-instances", "delete-", "modify-",
        "create-", "put-", "stop_instances", "terminate_instances",
    )

    def test_no_mutating_verb_appears(self, source):
        body = "\n".join(
            line for line in source.splitlines() if not line.strip().startswith("#")
        )
        # The module docstring names what it must NOT do; strip it before scanning.
        body = body.split('"""', 2)[-1]
        hits = [v for v in self.FORBIDDEN if v in body]
        assert not hits, f"the probe gained a mutating call: {hits}"

    def test_it_says_so_to_whoever_runs_it(self, source):
        assert "중지·종료하지 않는다" in source, (
            "the output must state that acting is a human decision"
        )


class TestUnmeasuredIsNotZero:
    """The failure being guarded is a false zero, so silence must not read as zero."""

    def test_a_failed_lookup_returns_none_not_zero(self, source):
        assert "return None" in source
        assert "이것은 '$0'이 아니다" in source
        assert "이것은 '0대'가 아니다" in source

    def test_it_exits_nonzero_when_it_could_not_look(self, source):
        assert "return 2" in source, (
            "exit 0 on an unmeasured account is the same false reassurance"
        )

    def test_zero_spend_is_still_exit_zero(self, source):
        """Measured-and-zero is a result; conflating it with 'could not look' would
        make the probe cry wolf on a genuinely idle account."""
        assert "spend may be zero — that is a result, not a failure" in source


class TestTheWindowIsRight:
    def test_end_is_exclusive_and_covers_today(self, source):
        """Cost Explorer's End is exclusive; end=today silently drops today."""
        assert "timedelta(days=1)" in source
        assert "end exclusive" in source or "exclusive" in source
