"""
When an entry-point doc says "the history is in M10~M28", those entries must exist.

`AGENT_BRIEF` does not merely link `COMPLETED_SUMMARY` — it *delegates* to it:

    이력·근거는 `STATUS` 검증 Baseline과 `COMPLETED_SUMMARY` **M10~M28**에 있다
    — 여기에 다시 적지 말 것.

That instruction is what makes the pointer load-bearing. A reader who follows it
writes nothing down, trusting the target. Measured 2026-08-16: the target held
**M0–M20**, and `AGENT_BRIEF` claimed M10~M26 while `STATUS` claimed M0~M24.
Six milestones — the entire 08-15 run, M21 through M26 — existed only as prose
labels in the two docs that pointed away from themselves. `/checkpoint`'s
"milestone done → compress into `<completed>`" step had been skipped six times,
and nothing could notice, because a dangling pointer reads exactly like a good one.

Same family as `test_gate_number_claims.py`: a number, or a range, that no test
ever compares against the thing it describes. The line-count budget guard sees a
long file; it cannot see a promise pointing at nothing.

Deliberately narrow. This checks that the *entries exist*, not that they are
accurate or well written — a test cannot read a milestone and judge whether it
tells the truth. Existence is the part that can be mechanised, and it is the part
that failed.
"""

from __future__ import annotations

import pathlib
import re

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]

BRIEF = ROOT / "docs/AGENT_BRIEF.md"
STATUS = ROOT / "docs/STATUS.md"
COMPLETED = ROOT / "docs/COMPLETED_SUMMARY.md"

# Matches the two shapes in use: "`COMPLETED_SUMMARY` **M10~M28**에" and
# "`COMPLETED_SUMMARY` **M0~M28**이 권위다". Both name a start and an end.
#
# `[\s>]{0,6}` because STATUS writes its pointer inside a blockquote and the range
# wraps to the next line, so a literal "\n> " sits between the two halves. The
# first version used `\s*`, found nothing in STATUS, and reported it as "the doc
# no longer names a range" — the doc was fine and the instrument was not.
RANGE = re.compile(r"COMPLETED_SUMMARY`?[\s>]{0,6}\*\*M(\d+)~M(\d+)\*\*")


def _claimed_ranges(path: pathlib.Path) -> list[tuple[int, int]]:
    return [
        (int(a), int(b))
        for a, b in RANGE.findall(path.read_text(encoding="utf-8"))
    ]


def _recorded_milestones() -> set[int]:
    headings = re.findall(
        r"^## M(\d+) ", COMPLETED.read_text(encoding="utf-8"), re.MULTILINE
    )
    return {int(n) for n in headings}


def test_some_milestones_are_recorded():
    """Vacuity check — an empty target would satisfy an empty claim."""
    assert len(_recorded_milestones()) >= 20


@pytest.mark.parametrize("path", [BRIEF, STATUS], ids=lambda p: p.name)
def test_the_doc_still_points_at_the_summary(path):
    """A pointer that gets rephrased out of existence stops being checked."""
    assert _claimed_ranges(path), (
        f"{path.relative_to(ROOT)} no longer names a `COMPLETED_SUMMARY` M-range. "
        "If the wording moved, move `RANGE` with it — an unfindable claim is an "
        "unchecked one."
    )


@pytest.mark.parametrize("path", [BRIEF, STATUS], ids=lambda p: p.name)
def test_every_claimed_milestone_exists(path):
    recorded = _recorded_milestones()
    for start, end in _claimed_ranges(path):
        missing = sorted(n for n in range(start, end + 1) if n not in recorded)
        assert not missing, (
            f"{path.relative_to(ROOT)} sends the reader to COMPLETED_SUMMARY "
            f"M{start}~M{end}, but M{missing} are not there. On 2026-08-16 that was "
            "M21–M26 — a whole day's work that the entry docs described in one line "
            "each and told the next session not to repeat. Run /checkpoint's "
            "milestone step, or narrow the range."
        )
