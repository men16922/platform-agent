"""
The gate number printed in the entry-point docs must be the gate's real size.

`AGENT_BRIEF` already carries the rule — *게이트 숫자는 날짜와 잰 기계 없이는 주장이
아니다* (Risk 12①②) — but nothing checked the number itself, and it has now drifted
twice:

    2026-08-15  docs said 2073 while the gate was 2081, then 2085. A `str.replace`
                with no assert had silently no-op'd; the line-count budget guard
                cannot see a wrong number, only a long file.
    2026-08-16  STATUS and AGENT_BRIEF were corrected to 2102 — and `NEXT_PLAN`
                was left at **2027**, 75 behind, still warning "CI 일치는 1912까지"
                after CI had verified 2102 on `aa1c913`.

The second one is the repo's own rule turned on its author: *형제 집합은 세는 순간
전부 셀 것.* Two entry points were counted; there are three.

Two directions, because the two failures are different shapes:

  * `test_entry_docs_agree` — a static cross-read. Catches one doc drifting while
    its siblings move, which is exactly the 08-16 case and costs nothing.
  * `test_claimed_total_matches_collection` — asks pytest. Catches the 08-15 case,
    where every doc agreed and all of them were wrong.

**Why the sum and not `passed`.** Six test modules carry
`pytestmark = pytest.mark.skipif(...)` on helm / opentelemetry / a timestamp
capability. Those are *runtime* skips: the tests are still collected, so a machine
without helm moves the count between `passed` and `skipped` while their **sum**
holds. Pinning `passed` would go red on a colleague's laptop for a reason that has
nothing to do with the docs being wrong. Verified 2026-08-16: collection returns
2104 in 1.34s on macOS·py3.13, and CI reported `2102 passed, 2 skipped` on
ubuntu·py3.13 — two machines, same total.

This deliberately does NOT check the recorded date or machine. Those are claims
about an event, and a test cannot re-run yesterday.
"""

from __future__ import annotations

import pathlib
import re
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]

BRIEF = ROOT / "docs/AGENT_BRIEF.md"
STATUS = ROOT / "docs/STATUS.md"
PLAN = ROOT / "docs/NEXT_PLAN.md"

# Each doc states the number in its own shape. Anchored to the surrounding words
# on purpose: if a rewrite loses the phrasing, the claim can no longer be located
# and this file goes red rather than quietly checking nothing.
#
# `keeps_history` is measured, not assumed: STATUS's 검증 Baseline is a
# newest-first list and legitimately carries older numbers (`1862 / 1859 / 1856`,
# `1825`, `1789`). The first version of this file demanded a single number
# everywhere and went red on those — the guard was wrong, not the doc. BRIEF and
# NEXT_PLAN state exactly one each (counted 2026-08-16), so for them "more than
# one" really is a defect and stays an error.
CLAIM_PATTERNS: dict[pathlib.Path, tuple[str, bool]] = {
    BRIEF: (r"\*\*(\d{3,5}) passed, \d+ skipped\*\*", False),
    STATUS: (r"`make check` → \*\*(\d{3,5})\*\*", True),
    PLAN: (r"gate (\d{3,5})", False),
}


def _claimed(path: pathlib.Path) -> int:
    pattern, keeps_history = CLAIM_PATTERNS[path]
    found = re.findall(pattern, path.read_text(encoding="utf-8"))
    assert found, (
        f"{path.relative_to(ROOT)} no longer states a gate number in the shape "
        f"{pattern!r}. If the wording moved, move this pattern with it — an "
        "unfindable claim is an unchecked one."
    )
    if not keeps_history:
        assert len(set(found)) == 1, (
            f"{path.relative_to(ROOT)} states more than one gate number "
            f"{sorted(set(found))}, but it is not a doc that keeps history — one of "
            "them is stale."
        )
    # Newest-first: a new baseline is written at the top of the Baseline section,
    # above the dated ones. If someone appends at the bottom instead, this reads a
    # stale number — and `test_entry_docs_agree` is what catches that.
    return int(found[0])


def _collected() -> int:
    """How many tests the gate actually has, asked of pytest rather than assumed.

    `sys.executable` because the Makefile probes for an interpreter that has
    pytest, and CI's is not this machine's. `--collect-only` runs nothing, so this
    cannot recurse into itself.
    """
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/", "--collect-only", "-q"],
        cwd=ROOT, capture_output=True, text=True,
    )
    match = re.search(r"(\d+) tests? collected", result.stdout)
    assert match, f"could not read a collection count from pytest:\n{result.stdout[-2000:]}"
    return int(match.group(1))


@pytest.mark.parametrize("path", [BRIEF, STATUS, PLAN], ids=lambda p: p.name)
def test_entry_doc_states_a_gate_number(path):
    """Vacuity check — a doc that stops stating one must not pass by silence."""
    assert _claimed(path) > 0


def test_entry_docs_agree():
    """The three entry points are one claim written three times."""
    claims = {path.name: _claimed(path) for path in CLAIM_PATTERNS}
    assert len(set(claims.values())) == 1, (
        f"the entry-point docs disagree about the gate: {claims}. On 2026-08-16 two "
        "were updated and NEXT_PLAN was not — it sat 75 tests behind while claiming "
        "CI had only verified 1912. Fix every sibling in the same commit."
    )


def test_claimed_total_matches_collection():
    """`passed + skipped` in AGENT_BRIEF must be the number of tests that exist."""
    text = BRIEF.read_text(encoding="utf-8")
    match = re.search(r"\*\*(\d{3,5}) passed, (\d+) skipped\*\*", text)
    assert match, "AGENT_BRIEF no longer records passed/skipped"
    claimed = int(match.group(1)) + int(match.group(2))
    collected = _collected()
    assert claimed == collected, (
        f"AGENT_BRIEF claims {match.group(1)} passed + {match.group(2)} skipped = "
        f"{claimed}, but pytest collects {collected}. The split between passed and "
        "skipped is allowed to differ by machine (helm/otel skipif); the total is not."
    )
