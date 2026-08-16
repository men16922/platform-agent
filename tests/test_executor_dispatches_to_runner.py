"""
Whether a provider's executor actually calls its runner must be written down.

Measured 2026-08-16 (`docs/evidence/azure-executor-reports-resolved-without-
executing.log`): `azure/executor.py::_execute_single_action` resolves the
capability, logs, and returns ``{"success": True}`` — it never calls
`run_azure_action`. That success lands in `executed`, `resolution_verdict` turns
it into ``resolved=True``, and the incident is **posted to Slack as resolved and
recorded as resolved**. `runners/azure_runner.py` is 311 lines of real ARM/AKS
implementation sitting one import away; GCP's executor calls its own runner, and
AWS's calls all three.

Nothing in `docs/` or `src/` says the Azure executor does not execute. M4's
"비-AWS는 scaffold" was true when written, and GCP has since grown a real path —
so the note describes a state that only Azure is still in, and says so nowhere.

**Why the existing guard missed it.** `test_scope_all_runners.py` asks all three
*runners* about scope. The runners are symmetric, so it is green. The asymmetry
is in the *executors*, which nothing asked. Risk 12④ⓐ, verbatim: 결함을 그 그림자로
세지 말 것 / 가드는 독자가 읽는 그 물건에 대고 물을 것.

This file does not fix the gap — wiring Azure would start issuing live ARM/AKS
mutations, and 작업 규칙 puts hard-to-reverse cloud changes behind approval. It
makes the gap **visible** instead, on the same rule as
`test_iam_wildcard_justified.py`: not "no asymmetry", which would be false, but
**no *unexplained* asymmetry**. Wiring Azure turns this red, so the record gets
corrected in the same commit as the behaviour.
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
    "azure": (
        frozenset(),
        "Measured 2026-08-16: `_execute_single_action` logs and returns success "
        "without calling `run_azure_action`, so Azure reports actions as executed "
        "and the incident as resolved without performing them. NOT wired here on "
        "purpose — doing so starts live ARM/AKS mutations, which 작업 규칙 puts "
        "behind approval. Evidence: "
        "docs/evidence/azure-executor-reports-resolved-without-executing.log",
    ),
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


@pytest.mark.parametrize("provider", sorted(EXPECTED), ids=sorted(EXPECTED))
def test_a_non_dispatching_executor_carries_a_reason(provider):
    """`test_iam_wildcard_justified`'s rule, one layer up: a `*` may be correct
    and an executor may legitimately not execute — but neither may be silent."""
    expected, reason = EXPECTED[provider]
    if expected:
        return
    assert reason and len(reason) > 80, (
        f"{provider} is recorded as calling no runner with no real explanation. "
        "An executor that reports success without acting is the kind of thing a "
        "reader must be told, not left to notice."
    )
