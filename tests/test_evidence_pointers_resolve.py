"""
Every `docs/evidence/*.log` a test or doc cites must exist.

This repo's guards do something unusual: they carry their reasoning in docstrings
and hand the reader a path to the measurement behind it —

    증거 `docs/evidence/azure-executor-reports-resolved-without-executing.log`

That citation is load-bearing in the same way `test_milestone_pointer_claims`
describes: a reader who follows the pointer writes nothing down, trusting the
target. And a dangling pointer reads exactly like a good one — nothing collects
these paths, so a renamed or never-committed log is invisible until someone tries
to open it, which is usually months later and usually mid-incident.

Measured 2026-08-30 before writing this: **68 distinct evidence paths cited across
`tests/`, `docs/`, `src/`; 0 dangling.** So this guard starts green and holds an
invariant that is currently true — it is not a cleanup task disguised as a test.

⚠️ Existence only, deliberately. Whether a log actually supports the claim citing it
is not mechanisable, and pretending otherwise would make this file the kind of guard
that answers about its own window instead of the document (Risk 12④). Existence is
the part that can be checked, and it is the part that silently rots.
"""

from __future__ import annotations

import pathlib
import re


ROOT = pathlib.Path(__file__).resolve().parents[1]

# The citation shape in use everywhere: a path under docs/evidence/ ending in .log.
CITATION = re.compile(r"docs/evidence/[A-Za-z0-9._\-]+\.log")

# Where citations live. `docs/archive/` is included on purpose: an archived progress
# log still points at evidence, and archiving is exactly when a rename goes unnoticed.
SEARCH_ROOTS = ("tests", "docs", "src")
SEARCH_SUFFIXES = {".py", ".md", ".log", ".yaml", ".yml"}


def _citing_files() -> list[pathlib.Path]:
    out: list[pathlib.Path] = []
    for root in SEARCH_ROOTS:
        for path in (ROOT / root).rglob("*"):
            if path.is_file() and path.suffix in SEARCH_SUFFIXES:
                out.append(path)
    return out


def _citations() -> dict[str, set[str]]:
    """evidence path -> the files that cite it."""
    found: dict[str, set[str]] = {}
    for path in _citing_files():
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for cited in CITATION.findall(text):
            found.setdefault(cited, set()).add(str(path.relative_to(ROOT)))
    return found


def test_the_sweep_finds_citations_at_all():
    """Vacuity guard. A regex that stops matching turns this file into a no-op that
    reports success — the failure mode the mutation harness itself hit on 08-15
    (`no tests ran` counted as red)."""
    found = _citations()
    assert len(found) >= 40, (
        f"only {len(found)} evidence citations found; 68 were measured on 2026-08-30. "
        "Either the citation shape changed or this sweep stopped reading the files "
        "it claims to read."
    )


def test_every_cited_evidence_log_exists():
    dangling = {
        cited: sorted(citers)
        for cited, citers in sorted(_citations().items())
        if not (ROOT / cited).is_file()
    }
    assert not dangling, (
        "these evidence logs are cited but do not exist:\n"
        + "\n".join(f"  {path}\n      cited by: {', '.join(citers)}" for path, citers in dangling.items())
        + "\n\nA guard's docstring is where its reasoning lives, and the log is the "
        "measurement behind the reasoning. Restore the file or fix the citation — do "
        "not delete the pointer, which is the one edit that makes the loss permanent."
    )
