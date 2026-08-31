"""
Whether a provider's executor actually calls its runner must be written down.

Measured 2026-08-16 (`docs/evidence/azure-executor-reports-resolved-without-
executing.log`): `azure/executor.py::_execute_single_action` resolved the
capability, logged, and returned ``{"success": True}`` — it never called
`run_azure_action`. That success landed in `executed`, `resolution_verdict`
turned it into ``resolved=True``, and the incident was **posted to Slack as
resolved and recorded as resolved**. `runners/azure_runner.py` was 311 lines of
real ARM/AKS implementation sitting one import away.

**Wired 2026-08-30 under approval**, so the exemption below is gone and every
executor here now dispatches. What the file is for did not change: the next
reader must be able to tell a stub from a live path without diffing two
executors, and an executor that reports success without acting must be declared,
not left to be noticed.

**Why the earlier guard missed it.** `test_scope_all_runners.py` asks all three
*runners* about scope. The runners are symmetric, so it is green. The asymmetry
was in the *executors*, which nothing asked. Risk 12④ⓐ, verbatim: 결함을 그
그림자로 세지 말 것 / 가드는 독자가 읽는 그 물건에 대고 물을 것.

The exemption rule (`test_a_non_dispatching_executor_carries_a_reason`) is the
same shape as `test_iam_wildcard_justified.py`: not "no asymmetry", which would
be false, but **no *unexplained* asymmetry**. With the table now fully wired that
rule has no real row to bite, so it is exercised against a synthetic table too —
a rule that cannot fail is not a rule (Risk 12③).
"""

from __future__ import annotations

import ast
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]

# provider -> (runner functions its executor is expected to call, reason if none)
#
# AWS is the multi-cloud dispatcher: `_run_external_action` fans out to all three
# runners, which is why it names more than its own.
EXPECTED: dict[str, tuple[frozenset[str], str | None]] = {
    "aws": (
        frozenset({"run_gcp_action", "run_azure_action", "run_onprem_action"}),
        None,
    ),
    "gcp": (frozenset({"run_gcp_action"}), None),
    # Wired 2026-08-30 under approval. This entry was the exemption the file was
    # written to hold, and moving it is the point: the table and the behaviour
    # changed in one commit. `onprem` has no `operations/onprem/executor.py` —
    # its runner is reached from the AWS dispatcher — so it is not a row here.
    "azure": (frozenset({"run_azure_action"}), None),
}

RUNNER_FUNCTIONS = frozenset(
    {"run_aws_action", "run_gcp_action", "run_azure_action", "run_onprem_action"}
)


def _called_runners(provider: str) -> frozenset[str]:
    """Runner functions this executor actually calls.

    Reads calls, not imports: an import that nothing invokes is exactly the state
    this file exists to tell apart from a wired one.
    """
    source = (ROOT / f"src/agents/operations/{provider}/executor.py").read_text(
        encoding="utf-8"
    )
    called = {
        node.func.id
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in RUNNER_FUNCTIONS
    }
    return frozenset(called)


def test_the_sweep_finds_a_wired_executor():
    """Vacuity check — if the AST walk breaks, every set is empty and every
    'not wired' entry passes. GCP is the control: it is wired."""
    assert _called_runners("gcp"), "the call sweep found nothing even for GCP"


@pytest.mark.parametrize("provider", sorted(EXPECTED), ids=sorted(EXPECTED))
def test_executor_dispatch_matches_the_record(provider):
    expected, reason = EXPECTED[provider]
    actual = _called_runners(provider)

    assert actual == expected, (
        f"{provider}/executor.py calls {sorted(actual) or 'no runner'}, but the "
        f"record here says {sorted(expected) or 'none'}. If you wired (or unwired) "
        "a provider, update this table and the evidence log in the same commit — "
        "the whole point is that the next reader can tell a stub from a live path "
        "without diffing two executors."
    )


def _unexplained(table: dict[str, tuple[frozenset[str], str | None]]) -> list[str]:
    """Providers recorded as dispatching to nothing, with no real explanation."""
    return [
        name
        for name, (expected, reason) in sorted(table.items())
        if not expected and not (reason and len(reason) > 80)
    ]


@pytest.mark.parametrize("provider", sorted(EXPECTED), ids=sorted(EXPECTED))
def test_a_non_dispatching_executor_carries_a_reason(provider):
    """`test_iam_wildcard_justified`'s rule, one layer up: a `*` may be correct
    and an executor may legitimately not execute — but neither may be silent."""
    assert not _unexplained({provider: EXPECTED[provider]}), (
        f"{provider} is recorded as calling no runner with no real explanation. "
        "An executor that reports success without acting is the kind of thing a "
        "reader must be told, not left to notice."
    )


def test_the_exemption_rule_still_bites():
    """Every row is wired as of 2026-08-30, so the check above passes without
    evaluating anything — the shape Risk 12③ names (a guard carrying no load).
    Ask the rule directly instead, so that re-stubbing a provider without a
    reason is still caught by a rule that was demonstrably alive."""
    assert _unexplained({"ghost": (frozenset(), None)}) == ["ghost"]
    assert _unexplained({"ghost": (frozenset(), "too short")}) == ["ghost"]
    assert _unexplained({"ghost": (frozenset(), "x" * 81)}) == []
