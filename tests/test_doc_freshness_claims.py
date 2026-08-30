"""
A doc's `최종 갱신` must not be older than the newest date the doc itself states.

`AGENT_BRIEF` carries the rule that makes this load-bearing:

    게이트 숫자는 **날짜와 잰 기계** 없이는 주장이 아니다 (Risk 12①②)

So the date is half the claim. Measured 2026-08-30: the three entry points had been
edited **nine times that day** — new gate numbers, corrected risks, closed items —
and all three headers still read `2026-08-18` / `2026-08-17`. Each document
contradicted itself: `STATUS` line 3 said 08-18 while line 11 recorded a run dated
**2026-08-30**. A reader trusting the header would have dated every one of the day's
measurements two weeks early.

`test_gate_number_claims` guards the *number* across the same three files and says,
deliberately:

    This deliberately does NOT check the recorded date or machine. Those are claims
    about an event, and a test cannot re-run yesterday.

That is right, and this file does not try to. It checks something weaker and fully
mechanical: **internal consistency**. Whether 2026-08-30 is really when the gate ran
is unknowable here; whether a document that mentions 2026-08-30 may claim it was last
updated on 2026-08-18 is not.

⚠️ Full `YYYY-MM-DD` only. These docs are dense with short forms (`08-15에 측정`,
`08-27T19:55Z`), and a year-less date cannot be ordered against a header without
guessing which year it belongs to — a guard that guesses is a guard that will be
wrong in January. Ignoring them costs nothing here: every drift of this kind so far
showed up in a full date somewhere in the same file.
"""

from __future__ import annotations

import datetime as dt
import pathlib
import re

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]

DOCS = [
    ROOT / "docs/AGENT_BRIEF.md",
    ROOT / "docs/STATUS.md",
    ROOT / "docs/NEXT_PLAN.md",
    ROOT / "docs/PROGRESS_LOG.md",
]

HEADER = re.compile(r"^최종 갱신:\s*(\d{4})-(\d{2})-(\d{2})\s*$", re.M)
ANY_DATE = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")


def _header_date(text: str) -> dt.date | None:
    m = HEADER.search(text)
    return dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3))) if m else None


def _mentioned_dates(text: str) -> list[dt.date]:
    out = []
    for y, mo, d in ANY_DATE.findall(text):
        try:
            out.append(dt.date(int(y), int(mo), int(d)))
        except ValueError:
            continue  # e.g. a version string that happens to look like a date
    return out


@pytest.mark.parametrize("path", DOCS, ids=lambda p: p.name)
def test_the_doc_records_when_it_was_last_updated(path):
    header = _header_date(path.read_text(encoding="utf-8"))
    assert header is not None, (
        f"{path.relative_to(ROOT)} has no `최종 갱신: YYYY-MM-DD` line. If the wording "
        "moved, move `HEADER` with it — an unfindable claim is an unchecked one."
    )


@pytest.mark.parametrize("path", DOCS, ids=lambda p: p.name)
def test_the_header_is_not_older_than_what_the_doc_says(path):
    text = path.read_text(encoding="utf-8")
    header = _header_date(text)
    assert header is not None  # covered by the test above
    newer = sorted({d for d in _mentioned_dates(text) if d > header})
    assert not newer, (
        f"{path.relative_to(ROOT)} says it was last updated {header}, but it mentions "
        f"{[str(d) for d in newer]}. The document disagrees with itself: whoever wrote "
        "those lines edited the file and left the header behind. Measured 2026-08-30, "
        "that is exactly what happened to all three entry points across nine edits in "
        "one day — 날짜 없는 숫자는 주장이 아니다 (Risk 12①②)."
    )


def test_the_sweep_actually_reads_dates():
    """Vacuity guard — a regex that stops matching makes every assertion above empty."""
    found = {p.name: len(_mentioned_dates(p.read_text(encoding="utf-8"))) for p in DOCS}
    assert sum(found.values()) >= 10, (
        f"only {sum(found.values())} full dates found across the entry points: {found}. "
        "These documents are dated throughout; near-zero means the pattern broke."
    )
