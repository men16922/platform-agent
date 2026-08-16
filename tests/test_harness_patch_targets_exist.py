"""
A harness that patches a module global must patch one that exists.

`scripts/slack_live_approval.py` swaps six module globals to run the real
approval-bridge handler offline. When the package moved under `aws/` and was
split into submodules, five of the six moved with it — and the script kept
assigning them to `handler`. Python does not object: `handler._SLACK_WEBHOOK = x`
happily creates an attribute nobody reads. **The harness ran, printed its
progress, and did nothing.**

That is the failure this file guards. It is a static check on purpose: it reads
the assignments out of the script and asks the target module whether the name is
real, so it holds without a Slack webhook, AWS credentials, or a demo.

Found 2026-08-16 by testing a recorded blocker rather than believing it.
`NEXT_PLAN` said the correct names *"could only be settled by putting the demo
through Slack"*. They could not have been more settled: each of the five lives in
exactly one submodule, and the script's own `simulate` mode — documented as
"fully offline" — proves the whole path end to end. The record had been carried
since 08-11.
"""

from __future__ import annotations

import ast
import importlib
import pathlib
import re

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/slack_live_approval.py"


def _imported_modules() -> dict[str, str]:
    """Local alias -> dotted module path, for `from X import a, b` lines."""
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    out: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and "approval_bridge" in node.module:
            for alias in node.names:
                out[alias.asname or alias.name] = f"{node.module}.{alias.name}"
    return out


def _patch_targets() -> list[tuple[str, str]]:
    """(alias, attribute) for every `alias._ATTR = ...` in the script."""
    aliases = _imported_modules()
    source = SCRIPT.read_text(encoding="utf-8")
    hits = re.findall(r"^\s*(\w+)\.(_\w+)(?:\.\w+)?\s*=", source, re.MULTILINE)
    return sorted({(a, attr) for a, attr in hits if a in aliases})


TARGETS = _patch_targets()
IDS = [f"{a}.{n}" for a, n in TARGETS]


def test_the_script_still_patches_something():
    """Vacuity check — a refactor that stops patching must not silently pass."""
    assert len(TARGETS) >= 5, TARGETS


@pytest.mark.parametrize("alias,attribute", TARGETS, ids=IDS)
def test_patch_target_exists(alias, attribute):
    module = importlib.import_module(_imported_modules()[alias])
    assert hasattr(module, attribute), (
        f"{SCRIPT.name} assigns {alias}.{attribute}, but {module.__name__} has no such "
        "name — Python will create the attribute and nothing will read it, so the "
        "harness runs and does nothing. Find where the name moved."
    )


def test_the_called_entry_points_exist():
    """The other half: patching the right globals is useless if the calls moved."""
    handler = importlib.import_module("src.agents.operations.aws.approval_bridge.handler")
    for name in ("_post_slack_request", "lambda_handler", "_approval_id"):
        assert hasattr(handler, name), name


def test_the_pre_move_import_path_is_gone():
    """`src.agents.operations.approval_bridge` now exists only in untracked
    `cdk.out/`, which is why the stale import resolved on one machine."""
    source = SCRIPT.read_text(encoding="utf-8")
    assert "from src.agents.operations.approval_bridge import" not in source
