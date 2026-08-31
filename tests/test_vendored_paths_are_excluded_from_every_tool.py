"""
Every tool that walks this tree must skip the same vendored trees. One didn't —
then, after that was fixed, a third one still didn't.

`src/stacks/cdk.out` holds 4,703 vendored `.py` files (CDK asset bundles) and
`src/stacks/node_modules` another 27. Both are gitignored, and both tools claim to
handle that on their own — pytest via `testpaths`, ruff via `respect-gitignore`.
Only pytest also said so out loud:

    [tool.pytest.ini_options]
    norecursedirs = ["src/stacks/cdk.out", "src/stacks/node_modules"]

    [tool.ruff]
    (nothing)

Measured 2026-08-30: relying on the inference is **not deterministic**. Ten
consecutive `ruff check src/ tests/` runs on an unchanged working tree returned

    20, 6527, 20, 6527, 6527, 6527, 20, 6527, 6527, 20

— the 6,507 extra findings all under `cdk.out`. Same command, same tree, same
commit. Declaring `extend-exclude` made it 20 ten times out of ten.

This is the repo's own Risk 12② turned on a second tool: *게이트가 선언되지 않은 것
위에서 통과하고 있었다.* It is also the sibling-set failure (Risk 12⑥) at config
level — the same trap was blocked for one tool and left open for the other, which
is exactly how a rule ends up half-enforced.

⚠️ `make lint` is not the gate (`check: test`), so nothing here was silently wrong
in CI. What was wrong is that a developer running `make lint` got a different answer
depending on the run, and the flapping one buried 20 real findings under 6,507
vendored ones — a signal you cannot read is a signal you stop reading.

⚠️ **This file was itself the sibling-set failure it describes.** Its first version
counted *two* tools — the name said so — while `[tool.mypy]` sat in the same
`pyproject.toml` naming neither path. Measured 2026-09-01: `mypy src/` did not
produce 253 errors, it produced **one**, and stopped:

    src/stacks/cdk.out/asset.0f86cea…/src/__init__.py: error: Duplicate module
    Found 1 error in 1 file (errors prevented further checking)

So the omission was **worst on the sibling that was left out**: ruff's failure was
noisy and flapping (20 vs 6,527), mypy's was total — the declared configuration
could not be executed at all. The guard that existed to stop a rule being
half-enforced was itself enforcing on two of three.

⚠️ The counting is now counted. `TOOLS` is still a list — a dict of section names
to readers — but `test_the_tool_list_is_complete` derives the same set **from
`pyproject.toml`** and fails when they disagree. That test exists because a
mutation run said it had to: deleting mypy from `TOOLS` left the suite green,
which is this file's own subject one level up — *the rule that catches a
half-enforced rule was itself half-enforced.* Writing "both" into a filename is
how it happened the first time.

⚠️ While measuring this, `mypy src/` answered **252** once and 253 otherwise. The
252 was its **incremental cache**, not a real difference — `--no-incremental` and a
deleted `.mypy_cache/` both give 253. Same family as the `.pyc` that fooled a
mutation harness's recovery check (Risk 12⑦): *a cached answer is not a
measurement.* The number recorded in `pyproject.toml` was right.

Directions, because parity alone can be satisfied by empty lists:

  * `test_every_tool_names_the_same_vendored_paths` — the drift guard, all three.
  * `test_the_declaration_is_not_empty`             — the vacuity guard.
  * `test_ruff_resolves_the_exclusion_it_declares`  — asks ruff, not the file.
    A TOML key can be present and misspelled (`extend_exclude`, `excludes`) and
    ruff will accept the file and ignore the key. Reading the declaration proves
    someone typed it; reading `--show-settings` proves the tool agreed.
  * `test_mypy_can_collect_the_source_tree_at_all` — asks mypy the one question
    the TOML cannot answer: does it get past collection? This is the failure that
    was open for a year of this config's life, and it is not visible in the
    declaration.
"""

from __future__ import annotations

import pathlib
import re
import shutil
import subprocess
import tomllib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
PYPROJECT = ROOT / "pyproject.toml"

# The trees this file exists for. Named rather than discovered: a guard that asked
# "which directories are big and vendored?" would answer about today's checkout.
VENDORED = {"src/stacks/cdk.out", "src/stacks/node_modules"}


def _config() -> dict:
    return tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))


def _pytest_excludes() -> set[str]:
    return set(_config()["tool"]["pytest"]["ini_options"].get("norecursedirs", []))


def _ruff_excludes() -> set[str]:
    return set(_config()["tool"]["ruff"].get("extend-exclude", []))


def _mypy_excludes() -> set[str]:
    """mypy's `exclude` is a list of **regexes**, so `.` is unescaped in the others
    and escaped here. Normalise rather than compare raw, or the drift guard fires
    on a difference that is only syntax."""
    raw = _config()["tool"]["mypy"].get("exclude", [])
    if isinstance(raw, str):
        raw = [raw]
    return {pattern.replace("\\.", ".") for pattern in raw}


# Every `pyproject.toml` section whose tool walks this source tree.
TOOLS = {
    "pytest norecursedirs": _pytest_excludes,
    "ruff extend-exclude": _ruff_excludes,
    "mypy exclude": _mypy_excludes,
}

# The key names a tool uses to say "do not walk these paths". Listing the spellings
# rather than the tools is deliberate: the next tool will bring its own spelling,
# and `test_the_tool_list_is_complete` below is what makes it announce itself.
EXCLUSION_KEYS = {
    "exclude", "excludes", "extend-exclude", "extend_exclude",
    "norecursedirs", "exclude_dirs", "exclude_also", "omit",
}


def _sections_with_an_exclusion_key() -> set[str]:
    """Every `[tool.*]` section in pyproject that declares a path exclusion.

    Walked from the parsed file rather than listed, because listing is exactly how
    mypy went uncounted: the previous version of this file hard-coded two tools and
    its own filename said "both".
    """
    found: set[str] = set()

    def walk(node: dict, path: list[str]) -> None:
        for key, value in node.items():
            if key in EXCLUSION_KEYS and isinstance(value, (list, str)):
                found.add(f"{path[0]} {key}")
            elif isinstance(value, dict):
                walk(value, path + [key])

    for tool, body in _config().get("tool", {}).items():
        if isinstance(body, dict):
            walk(body, [tool])
    return found


def test_the_tool_list_is_complete():
    """The guard on the guard — this is what M5 of the mutation run needed.

    Dropping a tool from `TOOLS` above makes the drift check quietly ask one
    question fewer, and every remaining question still passes. That is precisely
    the failure this file is about, one level up: **the counting itself was never
    counted.** So the tool set is derived from the file and compared to the list.

    A new `[tool.X]` section with an exclusion key goes red here until someone
    decides whether X walks this tree. That decision may well be "it does not" —
    in which case add it to `TOOLS` with the vendored paths, or record why the
    section is exempt. What it may not be is silent.
    """
    declared, found = set(TOOLS), _sections_with_an_exclusion_key()
    assert found <= declared, {
        "declares an exclusion but is not checked here": sorted(found - declared),
        "why": (
            "this file exists because one tool was left out of a rule the others "
            "carried, and the version that fixed that left out a third. If the new "
            "tool does not walk src/, say so — but say it here."
        ),
    }
    assert declared <= found, {
        "checked here but declares no exclusion in pyproject": sorted(declared - found),
        "why": (
            "TOOLS names a section that no longer declares an exclusion key. Either "
            "the tool was removed (drop it here too) or its key was renamed and the "
            "drift guard has been asking about nothing."
        ),
    }


@pytest.mark.parametrize("name", sorted(TOOLS))
def test_every_tool_names_the_same_vendored_paths(name):
    declared = TOOLS[name]()
    assert declared == VENDORED, {
        f"{name} is missing": sorted(VENDORED - declared),
        f"{name} has extra": sorted(declared - VENDORED),
        "why": (
            "these lists are one decision written once per tool. When only pytest "
            "carried it, `ruff check` flapped between 20 and 6,527 findings on an "
            "unchanged tree; when only pytest and ruff carried it, `mypy src/` "
            "could not get past collection at all. Add the path to every tool, or "
            "to none — and update VENDORED here in the same commit if a tree "
            "genuinely stopped being vendored."
        ),
    }


def test_the_declaration_is_not_empty():
    """Vacuity guard: empty lists are all equal, and equal is what the test above wants."""
    ruff_side = _ruff_excludes()
    assert VENDORED <= ruff_side, {
        "missing from ruff extend-exclude": sorted(VENDORED - ruff_side),
        "why": (
            "dropping these re-opens the flapping measured on 2026-08-30. If a tree "
            "genuinely stopped being vendored, update VENDORED in this file in the "
            "same commit so the removal is a decision rather than an erosion."
        ),
    }


@pytest.mark.skipif(shutil.which("ruff") is None, reason="ruff not installed")
def test_ruff_resolves_the_exclusion_it_declares():
    """Ask the tool, not the TOML. A misspelled key parses fine and does nothing."""
    result = subprocess.run(
        ["ruff", "check", "--show-settings", "src/"],
        cwd=ROOT, capture_output=True, text=True, timeout=120,
    )
    block = re.search(
        r"file_resolver\.extend_exclude = \[(.*?)\n\]", result.stdout, re.DOTALL
    )
    assert block, (
        "`ruff check --show-settings` printed no `file_resolver.extend_exclude` "
        "block. Either ruff's output format moved (update this regex — an "
        "unfindable claim is an unchecked one) or the key is not being read at all."
    )
    resolved = set(re.findall(r'"([^"]+)"', block.group(1)))
    assert VENDORED <= resolved, {
        "declared in pyproject": sorted(_ruff_excludes()),
        "actually resolved by ruff": sorted(resolved),
        "why": "ruff accepted the file but did not take these paths.",
    }


@pytest.mark.skipif(shutil.which("mypy") is None, reason="mypy not installed")
def test_mypy_can_collect_the_vendored_tree_without_choking():
    """Ask mypy the one question the TOML cannot answer, at the place it fails.

    Without the exclusion, `mypy` walking `src/stacks/` dies on a duplicate module
    inside `cdk.out` and reports:

        Found 1 error in 1 file (errors prevented further checking)

    That sentence is the failure mode — a tool that stopped before looking at any
    of our code. With the exclusion the same command answers *"There are no .py[i]
    files in directory 'src/stacks'"*, which is correct: nothing under `src/stacks`
    is tracked Python (the CDK there is TypeScript). So this is not a vacuous
    check — it has exactly two possible answers and only one of them is right.

    ⚠️ Deliberately narrow. The full `mypy src/` run is the real number (253 errors
    across 88 of 166 files, measured by hand and recorded in `pyproject.toml`), but
    it costs **~45s** against a gate that currently takes ~36s. Doubling the gate to
    re-derive a number the repo has already decided not to enforce is a bad trade;
    D49 exists because this gate's speed was worth 288s→39s. The regression this
    file guards against is a *config* regression, and it shows up here in 0.13s.

    ⚠️ Deliberately **not** "mypy passes". `strict = true` is 253 errors away from
    that, on purpose, as an intention rather than a standard — see the note above
    `exclude` in `pyproject.toml` and `test_pyproject_claims`.
    """
    result = subprocess.run(
        ["mypy", "src/stacks/", "--no-incremental"],
        cwd=ROOT, capture_output=True, text=True, timeout=180,
    )
    output = result.stdout + result.stderr
    assert "errors prevented further checking" not in output, (
        "mypy stopped before checking anything — this is what an unexcluded "
        "vendored tree does to it:\n" + "\n".join(output.strip().splitlines()[-4:])
    )
    assert "no .py[i] files" in output, (
        "expected mypy to find no tracked Python under src/stacks (the CDK there is "
        f"TypeScript). It said instead:\n{output.strip()[-800:]}\n\nIf real Python "
        "moved under src/stacks, this assertion is the thing to update — but check "
        "first that a vendored tree is not being collected again."
    )
