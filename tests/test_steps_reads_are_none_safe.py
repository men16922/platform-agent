"""
Every reader of a runbook's ``steps`` treats null and absent alike.

Found 2026-08-17 by cloud review of the commit that added `condition` validation,
and it was the same defect that commit was written to prevent, one door over.

``dict.get("steps", [])`` returns the **stored** value when the key is present, so
a document carrying an explicit ``steps: null`` yields None, not the default — and
``for step in None`` raises TypeError. The reads sat outside any try, so an
operator document that `validate_runbook` accepts with zero problems crashed
`_select_runbook` instead of falling back to heuristic matching. Firestore and
Cosmos store JSON null verbatim, and the validator's own message on the sibling
clause (*"steps must be a list or null"*) invites an operator to write it.

⚠️ **AWS was already None-safe** (`aws/decision.py` reads
``runbook.get("steps") or …``), so this was an asymmetry on the *reading* side —
the repo's standard for a real defect rather than an orphan declaration
(`NEXT_PLAN` 유지 규약). Three of four readers were the odd ones out:

    aws/decision.py            `or []`             — safe all along
    gcp/decision.py            `get("steps", [])`  — crashed
    azure/decision.py          `get("steps", [])`  — crashed
    capability_schema.py       `get("steps", [])`  — crashed (from_dict)
    aws/executor.py            `get("steps", [])`  — reachable only from our own
                                                     serialiser, fixed anyway

The structural test below is the load-bearing half: the three behavioural cases
pin the readers that exist today, and a fifth reader added next month would be
covered by neither. Counting the siblings once is not enough if the count is not
re-taken (Risk 12⑥).
"""

from __future__ import annotations

import ast
import importlib
import pathlib
import subprocess
from unittest import mock

import pytest

from src.agents.models import (
    AlarmContext,
    AnalyzerOutput,
    DetectorOutput,
    NormalizedIncident,
    Severity,
)
from src.agents.runbooks.capability_schema import CapabilityRunbook

ROOT = pathlib.Path(__file__).resolve().parents[1]
ALARM = "steps-null-alarm"

STORE_LOOKUPS = {
    "gcp": "src.agents.operations.gcp.decision._lookup_firestore_runbook",
    "azure": "src.agents.operations.azure.decision._lookup_cosmos_runbook",
}


def _analyzer(provider: str) -> AnalyzerOutput:
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
                resource_type="kubernetes-workload",
                resource_id="deploy/api",
                signal_type="reliability",
                recommended_capabilities=["restart_workload"],
                source_metadata={"alarm_name": ALARM},
            ),
        ),
        root_cause="container OOMKilled repeatedly",
        severity=Severity.P2,
        confidence=0.9,
    )


@pytest.mark.parametrize("provider", sorted(STORE_LOOKUPS))
def test_an_explicit_null_steps_document_does_not_crash_the_walk(provider):
    """`validate_runbook` accepts `steps: null`, so the walk must survive it.

    Before the fix this raised `TypeError: 'NoneType' object is not iterable` out
    of `_resolve_actions_from_runbook` — the 500 the tier-1 validation comment
    says the check exists to prevent, produced by a document the check passes.
    """
    registered = {
        "runbook_id": "operator-override",
        "capabilities": ["restart_workload"],
        "steps": None,
    }
    module = importlib.import_module(f"src.agents.operations.{provider}.decision")
    with mock.patch(STORE_LOOKUPS[provider], return_value=registered):
        runbook_id, _actions, _rto = module._select_runbook(_analyzer(provider))

    assert runbook_id == "operator-override", (
        f"{provider} did not follow a runbook whose `steps` is explicitly null; "
        "null and absent both mean 'no steps'"
    )


def test_capability_runbook_from_dict_accepts_null_steps():
    """The third reader, which is not behind a provider seam."""
    rb = CapabilityRunbook.from_dict({"runbook_id": "operator-override", "steps": None})
    assert rb.steps == [], "null steps must parse as no steps, not raise"


#: Readers of a runbook's ``steps``. Kept as a scan rather than a list of files so
#: a new reader is caught by construction — a hand-maintained list is the failure
#: this repo keeps hitting (a guard that iterates some of the siblings).
def _tracked_src_python() -> list[pathlib.Path]:
    """Tracked files only, via `git ls-files`.

    Not `ROOT.glob("src/**/*.py")`: that walks `src/stacks/node_modules/`, where
    the vendored CDK init templates are Python files containing
    `%name.PascalCased%` placeholders. Six of them fail `ast.parse`, so the glob
    version raised SyntaxError instead of reporting findings. Skipping unparseable
    files would have hidden the crash — and could hide a real reader — so the scan
    surface is what the repo owns. Same reason `test_iam_wildcard_justified.py`
    uses `git ls-files` to keep `cdk.out` out of its sweep.
    """
    out = subprocess.run(
        ["git", "ls-files", "--", "src"],
        cwd=ROOT, capture_output=True, text=True, check=True,
    ).stdout.splitlines()
    return [ROOT / p for p in out if p.endswith(".py")]


def _unsafe_steps_reads() -> list[str]:
    findings: list[str] = []
    for path in _tracked_src_python():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if not (isinstance(func, ast.Attribute) and func.attr == "get"):
                continue
            if not node.args:
                continue
            first = node.args[0]
            if not (isinstance(first, ast.Constant) and first.value == "steps"):
                continue
            # `get("steps")` with no default is fine — it yields None and the
            # caller decides. Only a *supplied* default is the trap, because it
            # reads as "absent or null → []" and only does the first half.
            if len(node.args) > 1:
                rel = path.relative_to(ROOT)
                findings.append(f"{rel}:{node.lineno}")
    return findings


def test_no_reader_uses_a_default_that_swallows_null_steps():
    """The load-bearing half: a *new* reader cannot reintroduce the trap.

    `get("steps", [])` is the shape that crashed three of four readers. A
    bare `get("steps")` is left alone — it returns None and forces the caller to
    say what that means, which is what `validate_capability_runbook` does.
    """
    unsafe = _unsafe_steps_reads()
    assert unsafe == [], (
        "these read `steps` with a default, which returns the stored None when "
        f"the key is present and raises TypeError on iteration: {unsafe}. Use "
        "`get(\"steps\") or []` — null and absent both mean 'no steps'."
    )
