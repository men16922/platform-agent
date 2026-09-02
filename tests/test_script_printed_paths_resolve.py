"""
Every repo-relative path a `scripts/*.py` hands to its reader must exist in the repo.

These scripts are instruments: they print what to look at next.

    print("      docs/GCP_BILLING_EXPORT_SETUP.md §3   (판정 시점과 좁히는 순서)")

09-01 measured what that class of line is worth when nobody checks it: the GCP probe
had been printing a `bq` command with three defects in one line, and the branch that
printed it needed a live export to reach, so it had **never once been executed** (M46).
A printed instruction is a claim. A printed *path* is the cheapest claim to check and
the one that rots first — a doc gets renamed, an evidence log gets archived, and the
line keeps printing, pointing at nothing, indistinguishable from a good pointer until
a reader follows it mid-incident.

`test_evidence_pointers_resolve` holds the same invariant for `docs/evidence/*.log`
cited under `tests/`, `docs/`, `src/`. It does **not** read `scripts/` and it only knows
one path shape. This file is the other half: any repo-relative path, anywhere in a
script's string literals.

Measured 2026-09-02 before writing this: **39 distinct paths across 23 scripts, 4 of them
reaching stdout, 0 dangling.** So this guard starts green and holds an invariant that is
currently true — it is not a cleanup task disguised as a test.

Four boundaries, each measured rather than assumed:

⚠️ **Existence is asked of git, not of this laptop.** `pathlib.exists()` would pass here
and fail in CI the first time a script named a build artefact — `src/stacks/node_modules`
is on this machine and in `.gitignore`. "The repo contains it" is the invariant; "my
filesystem has it" is a different sentence that happens to agree today (Risk 12②).

⚠️ **String literals only, not `#` comments.** Measured: the one path that lives only in a
comment is `src/stacks/node_modules` (`find_unwritten_keys.py`), which is deliberately
untracked. Sweeping comments would make this guard demand that a vendored dependency be
committed — an obligation nobody wants, defended by an exemption list nobody maintains.
Docstrings stay in scope: they are string literals and readers read them.

⚠️ **A literal compared as a fragment is not a path.** `probe_scope_reachability.py`
filters its own grep output with `.endswith("platform/scope.py")`. That string is a
suffix of a real file and a path from nowhere, and the first version of this guard
called it dangling. The exclusion is by *use* — an argument to `startswith`/`endswith`/
`in` is never shown to anyone — not by a list of paths to keep exempt.

⚠️ **A prefix of a real path is not a real path.** `docs/evidence/*.jsonl` sits next to
nothing named `.json`, and an extension alternation written `json|jsonl` truncates the
first to the second — the extractor would report a file that does not exist, and a
membership test written with `startswith` would swallow one that does not. Both
directions are pinned below.

증거 `docs/evidence/the-printed-path-was-a-claim-nobody-checked.log` — 쓰기 전 측정,
false red 하나와 그 경계, 변이 8종(그중 하나는 첫 판에서 살아남았다).
"""

from __future__ import annotations

import ast
import pathlib
import re
import subprocess


ROOT = pathlib.Path(__file__).resolve().parents[1]

# Measured floors (2026-09-02). They exist so that a sweep which quietly stops reading
# fails loudly instead of reporting success — the `no tests ran` shape from 08-15.
SCRIPTS_FLOOR = 15  # 23 scripts today
PATHS_FLOOR = 30  # 39 distinct paths today
PRINTED_FLOOR = 3  # 4 distinct paths reach stdout today

# Calls whose string arguments are what the reader actually sees.
OUTPUT_CALLS = {"print", "write", "writelines"}

# Calls whose string argument is a *fragment* matched against some other string, never a
# path shown to anyone. Measured: `probe_scope_reachability.py` filters its own grep hits
# with `.endswith("platform/scope.py")` — a suffix of `src/agents/platform/scope.py` that
# is not a path from the repo root and was never meant to be read as one.
FRAGMENT_CALLS = {"endswith", "startswith"}


def _tracked() -> list[str]:
    out = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=ROOT, capture_output=True, text=True, check=True,
    ).stdout.split("\0")
    return [rel for rel in out if rel]


def _repo_paths() -> set[str]:
    """Every path git knows: tracked files plus the directories holding them.

    Directories are included because scripts legitimately point at one
    (`docs/evidence/`, `infra/onprem/addons/`).
    """
    universe: set[str] = set()
    for rel in _tracked():
        posix = pathlib.PurePosixPath(rel)
        universe.add(str(posix))
        universe.update(str(parent) for parent in posix.parents if str(parent) != ".")
    return universe


def _in_repo(path: str, universe: set[str]) -> bool:
    """Exact membership, and the single place that decides it.

    Both the dangling sweep and the prefix trap below ask *this*, not the set. When they
    asked the set separately, loosening this line to `startswith` left every test green —
    the trap was guarding its own window instead of the thing the reader relies on
    (Risk 12④).
    """
    return path in universe


def _path_pattern() -> re.Pattern[str]:
    """Anchored on the repo's own top-level directories, read from git.

    Derived rather than listed so a new top-level directory is swept the day it lands.
    Dot-prefixed ones (`.github/`, `.claude/`) are left out: the lookbehind that stops
    `foo.docs/bar` from matching also stops `.github/` from starting, and a different
    anchor for them would buy nothing — measured 2026-09-02, the scripts reference such
    a path zero times.
    """
    tops = sorted({rel.split("/")[0] for rel in _tracked() if "/" in rel and not rel.startswith(".")})
    alternation = "|".join(re.escape(top) for top in tops)
    # The tail is one greedy character class, never an extension alternation: greedy is
    # what keeps `…points.jsonl` whole instead of stopping at a `json` branch.
    return re.compile(rf"(?<![A-Za-z0-9_./-])(?:{alternation})/[A-Za-z0-9_][A-Za-z0-9_./-]*")


def _normalize(raw: str) -> str:
    """Trim what prose leaves stuck to the end of a path (`docs/X.md.`, `docs/evidence/`)."""
    return raw.rstrip("./")


def _paths_in(text: str) -> set[str]:
    return {_normalize(m) for m in _path_pattern().findall(text)}


def _scripts() -> list[pathlib.Path]:
    return sorted((ROOT / "scripts").glob("*.py"))


def _fragment_literals(tree: ast.AST) -> set[int]:
    """Node ids of literals used as match fragments — excluded by how they are *used*,
    not by a list of paths someone has to keep up to date."""
    excluded: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and _call_name(node) in FRAGMENT_CALLS:
            for arg in node.args:
                excluded.update(id(sub) for sub in ast.walk(arg))
        elif isinstance(node, ast.Compare) and any(
            isinstance(op, (ast.In, ast.NotIn)) for op in node.ops
        ):
            excluded.update(id(sub) for sub in ast.walk(node.left))
    return excluded


def _named_paths(printed_only: bool = False) -> dict[str, set[str]]:
    """repo-relative path -> the `script:line` sites naming it."""
    pattern = _path_pattern()
    found: dict[str, set[str]] = {}
    for script in _scripts():
        tree = ast.parse(script.read_text(encoding="utf-8"))
        fragments = _fragment_literals(tree)
        nodes: list[ast.AST] = []
        if printed_only:
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and _call_name(node) in OUTPUT_CALLS:
                    nodes.append(node)
        else:
            nodes.append(tree)
        for root in nodes:
            for node in ast.walk(root):
                if not (isinstance(node, ast.Constant) and isinstance(node.value, str)):
                    continue
                if id(node) in fragments:
                    continue
                for raw in pattern.findall(node.value):
                    site = f"{script.relative_to(ROOT)}:{node.lineno}"
                    found.setdefault(_normalize(raw), set()).add(site)
    return found


def _call_name(node: ast.Call) -> str | None:
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def test_the_sweep_reads_the_scripts_at_all():
    """Vacuity guard: an extractor that stops matching is a no-op that reports success."""
    scripts = _scripts()
    assert len(scripts) >= SCRIPTS_FLOOR, (
        f"only {len(scripts)} scripts found under scripts/; {SCRIPTS_FLOOR}+ expected. "
        "This sweep is reading the wrong directory."
    )
    named = _named_paths()
    assert len(named) >= PATHS_FLOOR, (
        f"only {len(named)} distinct repo-relative paths found in scripts/*.py; 39 were "
        f"measured on 2026-09-02. Either the path shape changed or the extractor stopped "
        "reading the literals it claims to read."
    )


def test_the_printed_paths_are_still_reached():
    """The class this guard was written for: paths that go to stdout, not just docstrings.

    Held separately because it is the smaller set and the one that can silently drop to
    zero — a refactor that routes output through a helper this sweep does not recognise
    would leave the wider assertion green while covering none of what a reader sees.
    """
    printed = _named_paths(printed_only=True)
    assert len(printed) >= PRINTED_FLOOR, (
        f"only {len(printed)} printed repo-relative paths found ({sorted(printed)}); 4 were "
        f"measured on 2026-09-02. Output may have moved to a call this sweep does not know "
        f"about — the recognised ones are {sorted(OUTPUT_CALLS)}."
    )
    assert set(printed) <= set(_named_paths()), (
        "the printed sweep found paths the full sweep did not — they disagree about what "
        "counts as a path, and the wider assertion is no longer a superset."
    )


def test_every_repo_relative_path_a_script_names_exists():
    universe = _repo_paths()
    dangling = {
        path: sorted(sites)
        for path, sites in sorted(_named_paths().items())
        if not _in_repo(path, universe)
    }
    assert not dangling, (
        "these paths are named by a script but are not in the repo:\n"
        + "\n".join(f"  {path}\n      named at: {', '.join(sites)}" for path, sites in dangling.items())
        + "\n\nA script's printed path is an instruction, and an instruction that points at "
        "nothing reads exactly like one that works. Fix the path or drop the line — and if "
        "the target is deliberately untracked, say so where the reader can see it, because "
        "this guard asks git, not your filesystem."
    )


def test_an_extension_prefix_does_not_truncate_the_extracted_path():
    """`json|jsonl` written in that order stops at the shorter branch. Ours cannot."""
    extracted = _paths_in("wrote docs/evidence/points.jsonl and docs/evidence/points.json")
    assert extracted == {"docs/evidence/points.jsonl", "docs/evidence/points.json"}, extracted


def test_a_path_that_is_only_a_prefix_of_a_real_one_is_not_treated_as_real():
    """Membership is exact. A `startswith` check would call `…points.json` present
    because `…points.jsonl` is tracked — the same trap on the checking side."""
    universe = _repo_paths()
    reals = sorted(path for path in universe if path.endswith(".jsonl"))
    assert reals, "no .jsonl tracked; this trap test needs a suffix pair that exists"
    for real in reals:
        assert _in_repo(real, universe), f"{real!r} is tracked and must count as present"
        assert not _in_repo(real[:-1], universe), (
            f"{real[:-1]!r} is a strict prefix of the tracked {real!r} and must not count "
            "as a path in the repo."
        )
