"""
The context budgets are declared in three places and enforced in none.

`DOCS_POLICY.md` sets a line budget per entry-point doc, `.claude/harness-config.json`
repeats it as machine-readable config, and each doc's own header states it again
("이 파일은 **≤60줄**로 유지한다"). Nothing checked any of them.

Written 2026-08-15 after breaking the rule **three times in one session** — every
time noticed only *after* committing, then fixed by `--amend`. A rule that is
remembered rather than enforced is the same shape this repo spent the day on:
D45 decided the gate must not reach live cloud and nothing enforced it, so it
quietly stopped being true (→ D49).

Two directions, because three copies of a number is how they drift:

  1. every doc is within its budget          — the rule itself
  2. the three declarations agree            — so fixing one place is not enough

Budgets live in `harness-config.json` here: it is the machine-readable one, and
the skills (`/checkpoint`, `/tidy-docs`) already read it.
"""

from __future__ import annotations

import json
import pathlib
import re

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
CONFIG = ROOT / ".claude/harness-config.json"
POLICY = ROOT / "docs/DOCS_POLICY.md"


def _config() -> dict:
    return json.loads(CONFIG.read_text(encoding="utf-8"))


def _budgeted_docs() -> list[tuple[str, pathlib.Path, int]]:
    """(key, path, budget) for every doc that has a budget."""
    cfg = _config()
    return [
        (key, ROOT / cfg["docs"][key], budget)
        for key, budget in cfg["budgets"].items()
        if key in cfg["docs"]
    ]


def _char_budgeted_docs() -> list[tuple[str, pathlib.Path, int]]:
    """(key, path, char budget) — the metric the line budget could not see.

    Added 2026-08-30. `AGENT_BRIEF.md` sat at exactly 60/60 lines all day, green,
    while it grew to **9,783 characters** — and one line reached **3,621**, 37% of
    the file. The doc calls itself *1분 압축 문맥*; 3,621 characters on one line is
    not that, and nothing could tell, because the budget guard counts newlines.

    Same shape as this repo keeps finding: a guard that answers about its own
    window instead of the document (Risk 12④). Lines are what the guard saw;
    characters are what the agent pays for.
    """
    cfg = _config()
    limits = cfg.get("char_budgets", {})
    return [
        (key, ROOT / cfg["docs"][key], budget)
        for key, budget in limits.items()
        if key in cfg["docs"]
    ]


def _policy_table() -> dict[str, int]:
    """Filename -> budget, as `DOCS_POLICY.md`'s table states it."""
    return {
        m.group(1): int(m.group(2))
        for m in re.finditer(r"\|\s*`([A-Z_]+\.md)`\s*\|\s*≤\s*(\d+)줄", POLICY.read_text(encoding="utf-8"))
    }


def _header_claim(path: pathlib.Path) -> int | None:
    """The budget a doc's own header states, if it states one.

    Scans the whole file rather than a fixed window: `AGENT_BRIEF.md` states its
    budget on line 23, after a long `▶ NEXT SESSION` block, and a fixed 12-line
    window silently reported "no claim" — a guard that answers about its own
    window instead of the document (Risk 12④: ask the thing the reader reads).
    """
    text = path.read_text(encoding="utf-8")
    found = re.findall(r"\*{0,2}≤\s*(\d+)\s*줄", text)
    return int(found[0]) if found else None


IDS = [key for key, _, _ in _budgeted_docs()]


class TestEveryDocIsWithinBudget:
    @pytest.mark.parametrize("key,path,budget", _budgeted_docs(), ids=IDS)
    def test_within_budget(self, key, path, budget):
        actual = len(path.read_text(encoding="utf-8").splitlines())
        assert actual <= budget, (
            f"{path.relative_to(ROOT)} is {actual} lines, budget {budget} — move the "
            "oldest increment to docs/archive/ (/tidy-docs) rather than raising the number"
        )

    def test_the_sweep_covers_the_entry_points(self):
        """Vacuity check: a config typo must not silently empty this file."""
        assert {k for k, _, _ in _budgeted_docs()} == {"brief", "status", "plan", "log", "lessons"}


class TestEveryDocIsWithinItsCharacterBudget:
    """The line budget passed while the file doubled. This is the other half."""

    @pytest.mark.parametrize(
        "key,path,budget", _char_budgeted_docs(), ids=[k for k, _, _ in _char_budgeted_docs()]
    )
    def test_within_char_budget(self, key, path, budget):
        actual = len(path.read_text(encoding="utf-8"))
        assert actual <= budget, (
            f"{path.relative_to(ROOT)} is {actual} characters, budget {budget}. "
            "The line count can be inside its budget while the file is not — that is "
            "why this exists. Compress or move detail to docs/archive/ (/tidy-docs); "
            "do not raise the number."
        )

    def test_the_sweep_covers_the_entry_points(self):
        """Vacuity check: a missing or renamed `char_budgets` key must not silently
        empty this class the way a config typo would."""
        assert {k for k, _, _ in _char_budgeted_docs()} == {"brief", "status", "plan", "log"}


class TestTheThreeDeclarationsAgree:
    """Three copies of a number is how they drift (M19)."""

    @pytest.mark.parametrize("key,path,budget", _budgeted_docs(), ids=IDS)
    def test_policy_table_matches_config(self, key, path, budget):
        table = _policy_table()
        name = path.name
        assert name in table, f"{name} has a budget in harness-config.json but no row in DOCS_POLICY.md"
        assert table[name] == budget, (
            f"DOCS_POLICY.md says {name} ≤ {table[name]}, harness-config.json says {budget}"
        )

    @pytest.mark.parametrize("key,path,budget", _budgeted_docs(), ids=IDS)
    def test_the_doc_header_matches_config(self, key, path, budget):
        claimed = _header_claim(path)
        assert claimed is not None, (
            f"{path.name} does not state its own budget in its header — a reader "
            "editing it has no way to know"
        )
        assert claimed == budget, (
            f"{path.name}'s header claims ≤{claimed}줄 but harness-config.json says {budget}"
        )

    def test_the_policy_table_has_no_extra_rows(self):
        """Reverse: a budgeted row for a doc the config does not budget."""
        configured = {p.name for _, p, _ in _budgeted_docs()}
        extra = sorted(set(_policy_table()) - configured)
        assert extra == [], f"DOCS_POLICY.md budgets docs the harness does not: {extra}"
