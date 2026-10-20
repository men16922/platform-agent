"""Character-limit numbers belong in harness-config.json, not copied into Markdown.

Unlike line limits (intentionally declared three times), character limits have a
single source. Read the configured values, then find numeric copies in character
budget paragraphs, including archives. This is a lexical guard, not a ban on ports,
currency amounts, or every occurrence of a coincidentally equal number.
"""

from __future__ import annotations

import json
import pathlib
import re
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[1]
CONFIG = ROOT / ".claude/harness-config.json"
CONTEXT = re.compile(
    r"(?:문자|글자)\s*예산|char(?:acter)?[_ -]budgets?"
    r"|TestEveryDocIsWithinItsCharacterBudget|(?:문자|글자)[^\n]*≤",
    re.IGNORECASE,
)
INTEGER = re.compile(
    r"(?<![\d,A-Za-z_.₩$])(?:\d{1,3}(?:,\d{3})+|\d+)(?![\dA-Za-z_]|[,.]\d)"
)
PORT_PREFIX = re.compile(r"\b(?:port|포트)\s*[:=]?\s*$|\blocalhost:$", re.IGNORECASE)
DECLARATION = re.compile(
    r"(?:(?:문자|글자)\s*예산|character\s+budget)"
    r"\s*[*`]*(?:[(:=≤]\s*)?[*`]*$", re.IGNORECASE,
)


def _copies(text: str, limits: set[int]) -> list[tuple[int, str]]:
    """Line number and literal; paragraphs keep Markdown's wrapped declarations together."""
    found = []
    for paragraph in re.finditer(r"\S[^\n]*(?:\n(?!\s*\n)[^\n]+)*", text):
        if not CONTEXT.search(paragraph.group()):
            continue
        for number in INTEGER.finditer(paragraph.group()):
            before = paragraph.group()[:number.start()]
            after = paragraph.group()[number.end():]
            if PORT_PREFIX.search(before):
                continue
            # Explicit declarations also catch a stale limit that no longer equals
            # today's config. A percentage is a ratio, not another absolute limit.
            declared = DECLARATION.search(before) and not re.match(r"\s*[%/]", after)
            if int(number.group().replace(",", "")) in limits or declared:
                line = text.count("\n", 0, paragraph.start() + number.start()) + 1
                found.append((line, number.group()))
    return found


def _markdown_files() -> list[pathlib.Path]:
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=ROOT, capture_output=True, text=True, check=True,
    )
    return sorted({ROOT / p for p in result.stdout.split("\0") if p.endswith(".md")})


def test_character_budget_numbers_have_one_source():
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    limits = set(config["char_budgets"].values())
    assert limits and all(isinstance(n, int) and n > 0 for n in limits)
    paths = _markdown_files()
    assert ROOT / "docs/DOCS_POLICY.md" in paths
    assert ROOT / "docs/NEXT_PLAN.md" in paths
    assert any(p.is_relative_to(ROOT / "docs/archive") for p in paths)
    copies = [
        f"{p.relative_to(ROOT)}:{line}: {literal}"
        for p in paths
        for line, literal in _copies(p.read_text(encoding="utf-8"), limits)
    ]
    assert not copies, (
        "Character-budget numbers copied outside harness-config.json:\n"
        + "\n".join(copies)
        + "\nKeep measured sizes, percentages and warnings; replace the limit with a config pointer."
    )


def test_wrapped_budget_declarations_and_measured_comparisons_are_found():
    limits = {1234, 5678}
    assert _copies(
        "상한은 char_budgets에만 선언한다(brief 1,234 ·\nstatus/plan 5678).\n\n"
        "문자 999 ≤ 1,234 · 줄 12 ≤ 40\n\n문자 예산(5678)의 90%", limits
    ) == [(1, "1,234"), (2, "5678"), (4, "1,234"), (6, "5678")]
    assert _copies("문자 예산 1,234", {999}) == [(1, "1,234")]
    assert _copies("문자 예산 90% 이하", limits) == []
    assert _copies("문자 예산 1,000/1,234", limits) == [(1, "1,234")]
    assert _copies('char_budgets: {"brief":1234,"log":5678}', limits) == [
        (1, "1234"), (1, "5678"),
    ]
    assert _copies("문자 예산:1234", limits) == [(1, "1234")]


def test_ports_costs_line_limits_and_numeric_substrings_are_not_copies():
    limits = {8000, 11000, 12000}
    assert _copies(
        "port 8000\n\n비용 11,000원\n\n줄 예산 12000\n\n"
        "문자 예산은 config에서 읽는다. 포트 :8000 · ₩11,000 · $12000 · "
        "28,000 · 111000 · 120000 · 8.000 · 8000ms\n"
        "- Status: 09-02 완료\n여유: brief 1,317자 · status 1,941자 · log 7,781자\n"
        "현재 파일: NEXT_PLAN 10,797 · AGENT_BRIEF 7,606", limits
    ) == []
