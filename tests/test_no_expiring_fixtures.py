"""
A test must not pin an absolute time and then compare it against a live clock.

Risk 12① is the only entry in that list with a recorded live failure: a fixture
written on 2026-07-29 hardcoded an absolute instant while the producer opened its
window against the running clock, and the suite went red on 2026-08-05 — not
because anything changed, but because the calendar moved. **A green gate whose
truth expires is not a green gate; it is a countdown.**

Swept 2026-08-16: the suite pins **90** absolute date literals across 16 files,
and the dangerous shape — one of those *and* a live-clock call in the same
function — occurs **zero** times. That conjunction is the whole claim here. It is
deliberately narrower than "no hardcoded dates", which would be false and useless:
paired timestamps whose *difference* is the subject (`2026-07-29T06:40:00Z` with
`…06:40:30Z`), API version strings (`bedrock-2023-05-31`), and reference points
with `now` injected rather than read (`test_orphan_sweeper`'s `NOW`; its script
says why — *"a run days later still reaches the right verdict"*) are all correct
and must stay legal.

⚠️ **Two instrument bugs found while writing this, both by the self-test below.**
The date regex first ended in `\\b`, so it could not see `"2026-07-29T00:00:00Z"`
— `T` is a word character, so there is no boundary after the day. That is the
*most common* way to pin an instant: the broken sweep reported 4 literals where
there are 90, i.e. it was looking at 4% of the evidence and would have called the
suite clean no matter what. A first draft of this docstring then enumerated "every
absolute literal is one of these five kinds" — a classification written from that
4-item sample, and exactly the kind of confident summary this repo keeps having to
retract. What is asserted now is only what is mechanically checked.

So this guard pins a property the codebase already has, at the moment it is
cheapest to pin. It exists because the failure it prevents is invisible on the
day it is introduced — the test passes, and passes, until it doesn't.
"""

from __future__ import annotations

import ast
import pathlib
import re
import subprocess


ROOT = pathlib.Path(__file__).resolve().parents[1]

# `(?![0-9])` rather than a trailing `\b`: the first version used `\b` and
# therefore could not see `"2026-07-29T00:00:00Z"` — the `T` is a word
# character, so there is no boundary after the day. That is the **most
# common** way to pin an instant, and the self-test below is what caught it.
ABSOLUTE_DATE = re.compile(r"\b20[0-9]{2}-[01][0-9]-[0-3][0-9](?![0-9])")
LIVE_CLOCK = frozenset({"now", "utcnow", "today", "time", "monotonic"})


def _pins_absolute_time(node: ast.AST) -> bool:
    for inner in ast.walk(node):
        if isinstance(inner, ast.Constant) and isinstance(inner.value, str):
            if ABSOLUTE_DATE.search(inner.value):
                return True
        if isinstance(inner, ast.Call) and isinstance(inner.func, ast.Name):
            if inner.func.id in ("datetime", "date") and len(inner.args) >= 3:
                return True
    return False


def _reads_live_clock(node: ast.AST) -> bool:
    for inner in ast.walk(node):
        if not isinstance(inner, ast.Call):
            continue
        name = (
            inner.func.id if isinstance(inner.func, ast.Name)
            else getattr(inner.func, "attr", None)
        )
        if name in LIVE_CLOCK:
            return True
    return False


def _test_functions() -> list[tuple[str, int, str, ast.AST]]:
    paths = subprocess.run(
        ["git", "ls-files", "tests/*.py"],
        cwd=ROOT, capture_output=True, text=True, check=True,
    ).stdout.split()
    found = []
    for rel in paths:
        try:
            tree = ast.parse((ROOT / rel).read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                found.append((rel, node.lineno, node.name, node))
    return found


FUNCTIONS = _test_functions()

_SYNTHETIC = ast.parse(
    "def t():\n"
    "    import time\n"
    "    fired = '2026-07-29T00:00:00Z'\n"
    "    return time.time() - parse(fired)\n"
).body[0]


class TestTheDetectorWorks:
    """Risk 12⑤ — 가드 자신도 틀린다. A sweep that detects nothing reports a clean
    codebase, which is indistinguishable from a clean codebase."""

    def test_it_sees_the_shape_that_actually_broke(self):
        assert _pins_absolute_time(_SYNTHETIC)
        assert _reads_live_clock(_SYNTHETIC)

    def test_it_finds_each_half_separately_in_the_real_suite(self):
        """Both halves must be present somewhere, or the conjunction is vacuous."""
        pinned = [n for _, _, _, n in FUNCTIONS if _pins_absolute_time(n)]
        clocked = [n for _, _, _, n in FUNCTIONS if _reads_live_clock(n)]
        assert pinned, "no test pins an absolute time — the date detector is broken"
        assert clocked, "no test reads a live clock — the clock detector is broken"

    def test_the_sweep_reaches_the_suite(self):
        assert len(FUNCTIONS) > 500, len(FUNCTIONS)


def test_no_test_pins_an_instant_and_then_asks_the_clock():
    offenders = [
        f"{rel}:{line} {name}"
        for rel, line, name, node in FUNCTIONS
        if _pins_absolute_time(node) and _reads_live_clock(node)
    ]
    assert not offenders, (
        "these pin an absolute instant and also read the running clock:\n  "
        + "\n  ".join(offenders)
        + "\n\nThat combination passes until the calendar moves past it — it took "
        "this repo from 2026-07-29 to 2026-08-05. Inject `now` as a parameter, or "
        "derive the fixture from the clock (`time.time() - age * DAY`) so the "
        "relationship under test is the thing that is pinned, not the date."
    )
