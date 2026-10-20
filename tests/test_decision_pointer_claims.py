"""D-number citations in brief/status/plan must name recorded decision headings.

The milestone guard's sibling: prose mentioning a decision is not its definition.
Ranges promise every member, including the middle; Korean particles after an ID
must not make it disappear (an ASCII identifier boundary, not Python's Unicode \b).
"""

from __future__ import annotations

import json
import pathlib
import re

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / ".claude/harness-config.json").read_text(encoding="utf-8"))
DOCS = [ROOT / CONFIG["docs"][key] for key in ("brief", "status", "plan")]
DECISIONS = ROOT / CONFIG["docs"]["decisions"]
CITATION = re.compile(
    r"(?<![A-Za-z0-9_])D(\d+)(?:\s*[~–—-]\s*D?(\d+))?(?![A-Za-z0-9_])"
)


def _cited(text: str) -> set[int]:
    cited: set[int] = set()
    for first, last in CITATION.findall(text):
        start, end = int(first), int(last or first)
        assert start <= end, f"reversed decision range D{start}~D{end}"
        cited.update(range(start, end + 1))
    return cited


def _recorded(text: str) -> set[int]:
    return {int(n) for n in re.findall(r"^## D(\d+)(?=\s|$)", text, re.MULTILINE)}


def _missing(text: str, decisions: str) -> set[int]:
    return _cited(text) - _recorded(decisions)


@pytest.mark.parametrize("path", DOCS, ids=lambda p: p.name)
def test_every_cited_decision_is_recorded(path):
    text = path.read_text(encoding="utf-8")
    assert _cited(text), f"{path.name}: decision sweep found nothing"
    decisions = DECISIONS.read_text(encoding="utf-8")
    assert _recorded(decisions), "DECISIONS contains no decision headings"
    assert not (missing := _missing(text, decisions)), (
        f"{path.relative_to(ROOT)} cites unrecorded decisions: "
        f"{['D%d' % n for n in sorted(missing)]}. Add the decision or correct the citation."
    )


def test_individual_ids_korean_particles_and_range_interiors():
    assert _cited("D36·D38~D43, D48로 D49는 **D50** (D51) D15→D22") == {
        15, 22, 36, 38, 39, 40, 41, 42, 43, 48, 49, 50, 51,
    }
    assert _cited("D38–40 D41-D43") == set(range(38, 44))
    assert _cited("ADK 3D40 SDK_D48 D49suffix D50_foo") == set()


def test_only_headings_resolve_decisions_and_every_range_member_is_required():
    definitions = "## D38 — first\n## D40 — last\nprose D39\n### D39 detail\n"
    assert _missing("D38~D40", definitions) == {39}
    assert _missing("D38~D40", definitions + "## D39 — middle\n") == set()
    with pytest.raises(AssertionError, match="reversed decision range"):
        _cited("D40~D38")
