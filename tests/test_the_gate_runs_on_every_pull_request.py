"""
An unrun workflow and a passing one look the same in a checks list.

`gate.yml` used to trigger on `pull_request: branches: [main]`. That is the
natural way to write *"gate what reaches main"*, and about main it was correct:
branch protection requires the `check` context, so a PR targeting main has always
been gated. **main was never unguarded, and D43 always held.**

What the filter did was quieter. A *stacked* PR — one opened against another
feature branch rather than main — showed a full row of green:

    $ gh pr checks 58
    Amazon Q Developer        pass
    Vercel                    pass
    Vercel Preview Comments   pass

`check` is simply not in that list. Measured 2026-09-01, on this session's own
PR #58, and read as "CI green" before anyone noticed which rows were present.

That is Risk 12② one level up. The recorded shape is *"skip은 실패가 아니라서
검사 안 하는 게이트와 통과한 게이트가 같은 색이다"* — a skipped **test** looking
like a passing one. Here it is a skipped **workflow**: absence and success render
identically, and the reader supplies the difference.

⚠️ This file does not assert that the gate is a merge condition — that lives in
GitHub branch protection, not in the repo, and a test that claimed otherwise would
be asserting something it cannot see (`test_signature_gate_claims` is the standing
example of a claim that outran what was actually wired). What it asserts is the
half that *is* in the repo: every pull request runs the job, so a green row means
the same thing on every PR.
"""

from __future__ import annotations

import pathlib

import pytest
import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/gate.yml"


def _workflow() -> dict:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def _triggers() -> dict:
    wf = _workflow()
    # ⚠️ YAML 1.1 reads a bare `on:` key as the boolean True, which is why this
    # looks up both. A test that only checked `wf["on"]` would raise KeyError and
    # read as "the workflow has no triggers" — wrong for the same reason the thing
    # it guards was wrong.
    triggers = wf.get("on", wf.get(True))
    assert isinstance(triggers, dict), (
        f"gate.yml's trigger block is {triggers!r}, not a mapping. If the workflow "
        "moved to list-form triggers, move this reader with it — an unfindable "
        "claim is an unchecked one."
    )
    return triggers


def test_the_gate_triggers_on_pull_request_at_all():
    """Vacuity guard: the assertions below are about *how* it triggers."""
    assert "pull_request" in _triggers(), (
        "gate.yml no longer runs on pull requests. `main` protection requires the "
        "`check` context, so this would block every merge — but it would block them "
        "as a missing check rather than a failing one, which is the confusion this "
        "file exists to prevent."
    )


def test_the_gate_is_not_filtered_to_one_base_branch():
    """The actual fix, pinned.

    Re-adding `branches: [main]` is a one-line change that looks like a tightening
    and is a loosening: every PR whose base is not main goes back to showing green
    with this job absent.
    """
    pull_request = _triggers()["pull_request"]
    # `pull_request:` with no body parses to None — that is the state this wants.
    if pull_request is None:
        return
    assert isinstance(pull_request, dict), f"unexpected shape: {pull_request!r}"
    assert "branches" not in pull_request and "branches-ignore" not in pull_request, {
        "filter found": {
            k: v for k, v in pull_request.items()
            if k in ("branches", "branches-ignore")
        },
        "why": (
            "a base-branch filter makes stacked PRs display a full row of green "
            "checks with the gate never having run — absence and success look "
            "identical in `gh pr checks`. Measured on PR #58, 2026-09-01. If the "
            "filter is genuinely wanted back, say so in the comment above the "
            "trigger block and delete this test, so the trade is a decision."
        ),
    }


@pytest.mark.parametrize("marker", ["#58", "Risk 12"])
def test_the_reason_stays_written_next_to_the_trigger(marker):
    """The comment is what tells the next person why the obvious filter is absent.

    ⚠️ A comment is not a guard — this repo has already been caught letting one
    satisfy a rule (`"mlx-lm" in Makefile` passed on a comment while the recipe was
    broken, M41). This is the inverse and is legitimate: the *behaviour* is pinned
    by the two tests above, and this only keeps the explanation from being deleted
    as clutter once the reason is no longer fresh.
    """
    assert marker in WORKFLOW.read_text(encoding="utf-8"), (
        f"the note explaining why `pull_request` carries no branch filter lost its "
        f"reference to {marker!r}. Without it the filter reads as an oversight and "
        "gets 'fixed' back in."
    )
