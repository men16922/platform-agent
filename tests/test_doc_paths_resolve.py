"""Concrete Markdown paths in the six entry documents must survive a fresh checkout.

Archive contents are historical, so they are not citation sources here. An archive
*target* named by an entry document still has to exist. Glob/ellipsis shorthand is
not a concrete filename. In particular, never extract docs/... from bin/docs/...
(the false positives measured while preparing the 2026-09-03 backlog).
"""

from __future__ import annotations

import json
import pathlib
import re
import subprocess

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / ".claude/harness-config.json").read_text(encoding="utf-8"))
DOC_KEYS = ("brief", "status", "plan", "log", "completed", "decisions")
DOCS = [ROOT / CONFIG["docs"][key] for key in DOC_KEYS]
PATH = re.compile(
    r"(?<![\w/.:~-])docs/(?:[\w.-]+/)*[\w.-]+\.md(?![A-Za-z0-9_/-]|\.[A-Za-z0-9_])"
)


def _paths(text: str) -> set[str]:
    return set(PATH.findall(text))


def _tracked() -> set[str]:
    result = subprocess.run(
        ["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, text=True, check=True
    )
    return set(result.stdout.split("\0")) - {""}


def _missing(text: str, tracked: set[str], root: pathlib.Path = ROOT) -> list[str]:
    return sorted(p for p in _paths(text) if p not in tracked or not (root / p).is_file())


@pytest.mark.parametrize("path", DOCS, ids=lambda p: p.name)
def test_every_entry_document_path_exists_in_git_and_on_disk(path):
    text = path.read_text(encoding="utf-8")
    assert _paths(text), f"{path.name}: citation sweep found nothing"
    assert not (missing := _missing(text, _tracked())), (
        f"{path.relative_to(ROOT)} points at missing/untracked Markdown: {missing}. "
        "Restore the target or correct the reference; local ignored files do not ship in CI."
    )


def test_path_boundaries_and_markdown_reference_shapes():
    text = """
    `docs/STATUS.md` [plan](docs/NEXT_PLAN.md#next) docs/AGENT_BRIEF.md:5
    docs/LESSONS.md. `docs/archive/progress-2026-09.md` `docs/설명.md`
    bin/docs/missing.md /tmp/docs/missing.md https://example.org/docs/missing.md
    `docs/**/*.md` `docs/….md` `docs/archive/month-2026-0{7,8}.md`
    `docs/STATUS.md.bak` `docs/STATUS.mdx`
    """
    assert _paths(text) == {
        "docs/STATUS.md", "docs/NEXT_PLAN.md", "docs/AGENT_BRIEF.md", "docs/LESSONS.md",
        "docs/archive/progress-2026-09.md", "docs/설명.md",
    }


def test_local_only_deleted_and_prefix_targets_are_missing(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    for name in ("local.md", "real.md", "prefix.md.bak"):
        (docs / name).write_text("present", encoding="utf-8")
    tracked = {"docs/real.md", "docs/deleted.md", "docs/prefix.md.bak"}
    assert _missing(
        "`docs/local.md` `docs/real.md` `docs/deleted.md` `docs/prefix.md`", tracked, tmp_path
    ) == ["docs/deleted.md", "docs/local.md", "docs/prefix.md"]
