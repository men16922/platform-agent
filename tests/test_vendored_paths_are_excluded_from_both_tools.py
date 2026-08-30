"""
`pytest` and `ruff` must skip the same vendored trees. One of them didn't.

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

Three directions, because parity alone can be satisfied by two empty lists:

  * `test_the_two_tools_name_the_same_vendored_paths` — the drift guard.
  * `test_the_declaration_is_not_empty`               — the vacuity guard.
  * `test_ruff_resolves_the_exclusion_it_declares`    — asks ruff, not the file.
    A TOML key can be present and misspelled (`extend_exclude`, `excludes`) and
    ruff will accept the file and ignore the key. Reading the declaration proves
    someone typed it; reading `--show-settings` proves the tool agreed.
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


def test_the_two_tools_name_the_same_vendored_paths():
    pytest_side, ruff_side = _pytest_excludes(), _ruff_excludes()
    assert pytest_side == ruff_side, {
        "only pytest skips": sorted(pytest_side - ruff_side),
        "only ruff skips": sorted(ruff_side - pytest_side),
        "why": (
            "these two lists are the same decision written twice. When only one "
            "carried it, `ruff check` flapped between 20 and 6,527 findings on an "
            "unchanged tree. Add the path to both, or to neither."
        ),
    }


def test_the_declaration_is_not_empty():
    """Vacuity guard: two empty lists are equal, and equal is what the test above wants."""
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
