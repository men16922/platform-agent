"""
A destructive action must never run unattended — on any cloud.

Why this file exists (2026-08-15). The safety override that turns AUTO into
APPROVE lived in three copies, one per provider decision module, and they had
already drifted:

    gcp/decision.py    _DANGEROUS_PATTERNS = {Delete, Drop, Terminate, Destroy}
    azure/decision.py  _DANGEROUS_PATTERNS = {Delete, Drop, Terminate, Destroy}
    aws/decision.py    "Delete" in a or "Drop" in a or "Terminate" in a     # ← three

So an action named ``AWS-DestroyStack`` was APPROVE on two clouds and **AUTO on
the third** — executed with no human in the loop. AGENT_BRIEF states the
guardrail as "Delete/Drop/Terminate 액션은 강제 APPROVE"; two of the three
implementations had already grown past that wording and one had not.

The rule now lives once in ``runbooks.schema``. These guards ask it of every
sibling (Risk 12⑥) and pin the two judgement calls: the verb set, and the fact
that matching is case-sensitive because every execution adapter emits
``PROVIDER-PascalCase``.
"""

from __future__ import annotations

import importlib

import pytest

from src.agents.models import RemediationMode, Severity
from src.agents.runbooks.schema import (
    DESTRUCTIVE_ACTION_PATTERNS,
    is_destructive_action,
)

DECISION_MODULES = [
    "src.agents.operations.aws.decision",
    "src.agents.operations.gcp.decision",
    "src.agents.operations.azure.decision",
]

EXECUTION_ADAPTERS = [
    "src.agents.adapters.execution.aws",
    "src.agents.adapters.execution.gcp",
    "src.agents.adapters.execution.azure",
    "src.agents.adapters.execution.onprem",
]

ALL_SEVERITIES = [Severity.P1, Severity.P2, Severity.P3]


def _mode(module: str):
    return importlib.import_module(module)._determine_mode


def _tracked_sources_containing(needle: str) -> list[str]:
    """Tracked `src/**.py` files containing `needle`.

    Walks `git ls-files`, not the filesystem: `src/stacks/cdk.out/` is an
    untracked build artefact holding whole copies of this tree, so an rglob
    "who defines this?" guard reports two dozen stale hits and fails on a fact
    about a build directory. The repo already wrote this rule down after
    counting a comment as a call site — **use `git`, not the filesystem.**
    """
    import pathlib
    import subprocess

    root = pathlib.Path(__file__).resolve().parents[1]
    tracked = subprocess.run(
        ["git", "ls-files", "src/*.py", "src/**/*.py"],
        cwd=root, capture_output=True, text=True, check=True,
    ).stdout.split()
    return [
        rel for rel in tracked
        if needle in (root / rel).read_text(encoding="utf-8")
    ]


class TestEveryProviderRefusesToAutomateDestruction:
    @pytest.mark.parametrize("module", DECISION_MODULES)
    @pytest.mark.parametrize("verb", DESTRUCTIVE_ACTION_PATTERNS)
    @pytest.mark.parametrize("severity", ALL_SEVERITIES)
    def test_destructive_action_never_auto(self, module, verb, severity):
        action = f"AWS-{verb}Something"
        assert _mode(module)(severity, [action]) is not RemediationMode.AUTO

    @pytest.mark.parametrize("module", DECISION_MODULES)
    def test_destroy_is_the_one_that_had_drifted(self, module):
        """The exact case that was AUTO on AWS and APPROVE on the other two."""
        assert _mode(module)(Severity.P1, ["AWS-DestroyStack"]) is RemediationMode.APPROVE

    @pytest.mark.parametrize("module", DECISION_MODULES)
    def test_one_destructive_action_in_a_list_is_enough(self, module):
        plan = ["AWS-RestartEKSPod", "AWS-ScaleOutEKSNodeGroup", "AWS-DeleteVolume"]
        assert _mode(module)(Severity.P1, plan) is RemediationMode.APPROVE


class TestTheOverrideDoesNotSwallowEverything:
    """Reverse direction — a gate that always fires is not a gate (Risk 12③)."""

    @pytest.mark.parametrize("module", DECISION_MODULES)
    @pytest.mark.parametrize("severity,expected", [
        (Severity.P1, RemediationMode.AUTO),
        (Severity.P2, RemediationMode.APPROVE),
        (Severity.P3, RemediationMode.MANUAL),
    ])
    def test_safe_actions_keep_the_severity_mapping(self, module, severity, expected):
        assert _mode(module)(severity, ["AWS-RestartEKSPod"]) is expected

    @pytest.mark.parametrize("module", DECISION_MODULES)
    def test_empty_plan_keeps_the_severity_mapping(self, module):
        assert _mode(module)(Severity.P1, []) is RemediationMode.AUTO


class TestProvidersAgree:
    @pytest.mark.parametrize("action", [
        "AWS-DeleteVolume", "AWS-DropDatabase", "AWS-TerminateInstance",
        "AWS-DestroyStack", "AWS-RestartEKSPod", "ONPREM-RolloutRestartWorkload",
    ])
    @pytest.mark.parametrize("severity", ALL_SEVERITIES)
    def test_same_action_same_answer_everywhere(self, action, severity):
        answers = {m: _mode(m)(severity, [action]) for m in DECISION_MODULES}
        assert len(set(answers.values())) == 1, answers


class TestSingleCopy:
    """M19's rule: a shared contract lives in one module, not one copy per provider."""

    def test_no_provider_defines_its_own_verb_set(self):
        assert _tracked_sources_containing("_DANGEROUS_PATTERNS") == []

    def test_destroy_is_in_the_set(self):
        """Pins the verb the odd-one-out was missing."""
        assert "Destroy" in DESTRUCTIVE_ACTION_PATTERNS


class TestCaseSensitivityIsALoadBearingChoice:
    """The rule matches ``PROVIDER-PascalCase``. That is safe only while the
    adapters emit exactly that — so assert the premise, not just the rule."""

    @pytest.mark.parametrize("module", EXECUTION_ADAPTERS)
    def test_adapters_emit_pascal_case_action_names(self, module):
        import inspect
        import re

        source = inspect.getsource(importlib.import_module(module))
        emitted = re.findall(r'"((?:AWS|GCP|AZURE|ONPREM)-[A-Za-z0-9]+)"', source)
        assert emitted, f"{module}: no action names found — the premise is unchecked"
        lowercase = [a for a in emitted if a.split("-", 1)[1][:1].islower()]
        assert lowercase == [], (
            f"{module} emits lowercase action names {lowercase}; the destructive-action "
            "gate is case-sensitive and would miss them — widen DESTRUCTIVE_ACTION_PATTERNS"
        )

    def test_lowercase_is_knowingly_not_matched(self):
        """Documented scope, pinned so a later reader does not read it as a bug."""
        assert not is_destructive_action("terraform destroy")
        assert is_destructive_action("ONPREM-DestroyCluster")
