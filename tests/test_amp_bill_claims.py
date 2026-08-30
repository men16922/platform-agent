"""
The 4a bill is now a measurement. The entry-point docs must not re-state the estimate.

For thirteen days three entry points carried the same pending claim — *"$1.42/월은
아직 산수다"* — and pointed at the measurement that would settle it. On 2026-08-30 it
was settled: **$0.00**, because AMP's free tier is `Always Free` 40 M samples/month
and the plan's §3 had reasoned its way out of that tier on a premise (a 12-month
window) that turned out false. Metered usage: 798,331 samples, $0.00 charged.

Why this needs a guard rather than a careful edit. This repository's most expensive
documented failure is exactly this shape: three entry-point documents copied "≈$5/월"
from a plan whose series count was never measured, and the copy survived to an
approval before anyone counted the cluster — 100× wrong
(`docs/evidence/4a-cost-assumed-a-hundredth-of-the-cluster.log`). `$1.42` is now a
number of the same kind: it was honest arithmetic, it is no longer the bill, and it
is sitting in git history where the next session can copy it forward.

Two directions, because the two ways to be wrong here are opposites:

  * `test_a_restated_estimate_must_carry_its_correction` — drift guard. If an entry
    point names $1.42 again, the same document must also say what superseded it.
    Deleting the number is fine; restating it bare is not.
  * `test_the_measured_result_is_actually_stated` — vacuity guard. The first test
    passes trivially on a document that says nothing about the bill at all, which is
    how a measured fact quietly stops being carried. At least one entry point must
    hold the result and its reason.

⚠️ Deliberately not asserting that "$1.42" never appears. It appears legitimately in
the plan's §3 correction box, in `DECISIONS`, and in the evidence log, where the whole
point is to show the superseded number next to what replaced it. A guard that banned
the string would force those records to launder their own history — and this repo has
already found that **만족 불가능한 규칙은 우회를 습관으로 만든다**.

⚠️ Also not asserting the bill stays $0.00. That is a fact about AWS on one date, not
an invariant of this repository; `test_amp_cost_handles.py` guards the two handles that
decide the volume, and 40 M is the limit they now have to stay under.
"""

from __future__ import annotations

import pathlib
import re

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]

BRIEF = ROOT / "docs/AGENT_BRIEF.md"
STATUS = ROOT / "docs/STATUS.md"
PLAN = ROOT / "docs/NEXT_PLAN.md"
ENTRY_POINTS = [BRIEF, STATUS, PLAN]

DESIGN_PLAN = ROOT / "docs/plans/2026-08-15-4a-remote-write-allowlist.md"
EVIDENCE = ROOT / "docs/evidence/amp-actual-bill-is-zero-and-the-free-tier-reason-was-inverted.log"

# The superseded estimate, in the shapes the docs actually wrote it: "$1.42/월",
# "$1.42는", "**$1.42**". Bare "1.42" would also match the gate timing "1.42s" in
# an evidence log, which is why the dollar sign is part of the pattern.
SUPERSEDED_ESTIMATE = re.compile(r"\$1\.42")

# What a correction has to say for the number to be safe to repeat. Any one of
# these turns a bare restatement into a record: the measured bill, the reason, or
# an explicit correction marker.
CORRECTION_MARKERS = ("$0.00", "Always Free", "정정", "전건이 거짓")


def _text(path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8")


# The correction has to sit *next to* the number, not merely somewhere in the same
# file. The first version of this test asked the whole document, and that version
# could never go red again: once an entry point carries the correction anywhere, a
# bare "$1.42" pasted into an unrelated paragraph passes. That is the shape Risk 12③
# names — a guard that only ever runs its happy path. A ±3-line window is one dense
# paragraph in these documents, which is the unit a reader actually takes in.
CORRECTION_WINDOW = 3


def _uncorrected_mentions(path: pathlib.Path) -> list[tuple[int, str]]:
    lines = _text(path).splitlines()
    out = []
    for n, line in enumerate(lines):
        if not SUPERSEDED_ESTIMATE.search(line):
            continue
        lo, hi = max(0, n - CORRECTION_WINDOW), min(len(lines), n + CORRECTION_WINDOW + 1)
        window = "\n".join(lines[lo:hi])
        if not any(marker in window for marker in CORRECTION_MARKERS):
            out.append((n + 1, line.strip()))
    return out


@pytest.mark.parametrize("path", ENTRY_POINTS, ids=lambda p: p.name)
def test_a_restated_estimate_must_carry_its_correction(path):
    bare = _uncorrected_mentions(path)
    assert not bare, (
        f"{path.relative_to(ROOT)} names $1.42 with no correction within "
        f"±{CORRECTION_WINDOW} lines:\n"
        + "\n".join(f"  line {n}: {text[:110]}" for n, text in bare)
        + "\n\nThat number was the 4a estimate; the measured bill is $0.00 because "
        "AMP's free tier is `Always Free` 40M/mo (plan §10). A bare estimate in an "
        "entry point is how '≈$5/월' reached an approval 100× wrong — put the "
        f"correction beside it or drop the number. Expected one of: {CORRECTION_MARKERS}"
    )


def test_the_measured_result_is_actually_stated():
    """Vacuity guard: the test above is satisfied by silence, and silence loses this."""
    carriers = [p for p in ENTRY_POINTS if "$0.00" in _text(p) and "Always Free" in _text(p)]
    assert carriers, (
        "no entry-point doc states the measured 4a bill ($0.00) together with its "
        "reason (AMP's `Always Free` 40M/mo tier). One of AGENT_BRIEF / STATUS / "
        "NEXT_PLAN has to carry it, or the drift guard above passes on a repo that "
        "has forgotten the measurement entirely."
    )


def test_the_authority_the_entry_points_delegate_to_exists():
    """`§10` and the evidence log are where the entry points send the reader."""
    assert EVIDENCE.is_file(), f"missing evidence log: {EVIDENCE.relative_to(ROOT)}"
    assert re.search(r"^## 10\. ", _text(DESIGN_PLAN), re.MULTILINE), (
        "the plan has no §10. Every entry point says '권위 §10' for the bill "
        "measurement; a pointer at a section that does not exist reads exactly like "
        "a good one (same family as test_milestone_pointer_claims)."
    )


def test_the_free_tier_limit_is_recorded_where_the_cliff_now_is():
    """The cliff moved from the $0.90/10M rate to the 40M limit.

    `test_amp_cost_handles.py` pins the allowlist and the interval; this pins that
    the *reason* they are pinned is written down somewhere a reader will find it.
    Without the limit, "the bill is $0.00" reads as "AMP is free" — which is the one
    summary the measurement does not support (no filter overruns 40M by 128×).
    """
    handles = _text(ROOT / "tests/test_amp_cost_handles.py")
    assert "40 M" in handles or "40M" in handles, (
        "the AMP handles guard no longer names the 40M free-tier limit. That limit "
        "is what makes the allowlist load-bearing now that the rate never applies."
    )
