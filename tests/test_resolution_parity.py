"""
"Resolved" must mean the same thing on every cloud.

`resolved` is what decides whether `resolved_at` is written, and `resolved_at` is
half of the pair the weekly on-call report subtracts for MTTR. So a provider that
computes it differently reports a different kind of number under the same name.

Found 2026-08-15 by walking the lens one layer down (AlarmContext ->
AnalyzerOutput -> DecisionOutput -> ExecutorOutput). The `ExecutorOutput` fields
are constructed identically by all three, but the value behind one of them was
not:

    aws/executor.py     resolved = resolution_verdict(...).resolved   ← contract
    gcp/executor.py     resolved = bool(executed) and not skipped     ← copy
    azure/executor.py   resolved = bool(executed) and not skipped     ← copy

**Not a live defect**: `resolution_verdict` with no verifications *is* exactly
`bool(executed) and not skipped`, and GCP/Azure have no verify path, so the two
agreed. It is the shape the repo's own maintenance rule forbids — a shared
*contract* copied per provider, where "the next fix lands in one and rots in the
other". AWS's own comment says the point is that "both axes have one definition";
two providers were not using it.

These guards keep the three answering the same question, and pin that the
routing did not change today's behaviour.
"""

from __future__ import annotations

import importlib
import inspect

import pytest

from src.agents.runbooks.capability_schema import resolution_verdict

EXECUTORS = [
    "src.agents.operations.aws.executor",
    "src.agents.operations.gcp.executor",
    "src.agents.operations.azure.executor",
]

# (executed, skipped) -> the historical rule's answer. Behaviour must not move.
HISTORICAL_CASES = [
    ([], [], False),
    (["A"], [], True),
    (["A"], ["B"], False),
    ([], ["B"], False),
    (["A", "B"], [], True),
]


class TestTheContractStillMeansWhatItMeant:
    @pytest.mark.parametrize("executed,skipped,expected", HISTORICAL_CASES)
    def test_no_verifications_is_the_historical_rule(self, executed, skipped, expected):
        """Routing GCP/Azure through the verdict must be a no-op today."""
        assert resolution_verdict(executed, skipped).resolved is expected
        assert (bool(executed) and not skipped) is expected

    def test_verified_is_unknown_not_passed(self):
        """With nothing checked, the verdict must not claim proof."""
        assert resolution_verdict(["A"], []).verified is None


class TestEveryExecutorAsksTheContract:
    @pytest.mark.parametrize("module", EXECUTORS)
    def test_imports_the_shared_verdict(self, module):
        assert hasattr(importlib.import_module(module), "resolution_verdict"), (
            f"{module} does not read `resolution_verdict` — if it computes "
            "`resolved` itself, the three drift the moment one of them learns "
            "about verification"
        )

    @pytest.mark.parametrize("module", EXECUTORS)
    def test_no_local_copy_of_the_rule(self, module):
        """The exact expression that used to be duplicated."""
        source = inspect.getsource(importlib.import_module(module))
        offending = "resolved = bool(executed) and not skipped"
        assert offending not in source, (
            f"{module} re-hardcodes the resolution rule; call "
            "`resolution_verdict(executed, skipped)` instead"
        )

    def test_all_three_agree_on_every_historical_case(self):
        """Same inputs, same answer — asked of the contract they all now read."""
        for executed, skipped, expected in HISTORICAL_CASES:
            answers = {
                m: importlib.import_module(m).resolution_verdict(executed, skipped).resolved
                for m in EXECUTORS
            }
            assert set(answers.values()) == {expected}, (executed, skipped, answers)
