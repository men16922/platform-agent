"""
`pyproject.toml` makes claims. Two of them were not true.

**The version claim.** `requires-python = ">=3.11"` had been in this file since it
was written, and `AGENT_BRIEF` and `STATUS` Risk 12② both flagged it — twice — as
*"아무도 확인한 적 없는 주장"*. Measured 2026-08-30: it was **false**. A fresh 3.11
venv, installed with CI's exact line, runs the gate at **2 failed, 2300 passed**
(an anyio cancel-scope error surfacing as an SSE stream that ends `error` instead
of `done`, and a `StopIteration` that escapes a CLI loop).

The confounder was eliminated before concluding. The 3.11 env resolved *newer*
packages than this machine's long-lived 3.13 env (starlette 1.6.0 vs 1.3.1, pytest
9.1.1 vs 8.3.4), so the failures could have been dependency drift rather than the
interpreter. A **fresh 3.13 venv resolving the same versions** is green at 2302 —
so it is the interpreter. `>=3.13` is now what the file says, because that is what
has been run.

**The tooling claim.** `[tool.mypy] strict = true` is declared and **nothing runs
mypy** — not the Makefile, not CI, not scripts/, and there is no pre-commit config.
It is 253 errors across 88 of 165 files from that setting. A newcomer reads
`strict = true` as a standard this repo holds; it is an intention. The comment in
`pyproject.toml` now says so, and the second test below keeps it saying so.

Both are the same family as this session's other findings: **a declaration nobody
reads.** Same as `ruff` never being told to skip the vendored trees that `pytest`
was told to skip, and as `provider` being declared on nine runbooks that no reader
consulted (M19).

⚠️ Deliberately does NOT assert the gate passes on the declared floor. That would
mean running the whole suite under another interpreter from inside the suite. What
it asserts is cheaper and catches the actual drift: the three copies of the version
agree, and the floor is not above the interpreter running the gate.
"""

from __future__ import annotations

import pathlib
import re
import sys
import tomllib

ROOT = pathlib.Path(__file__).resolve().parents[1]
PYPROJECT = ROOT / "pyproject.toml"

# Where a tool would be invoked from. A tool named in none of these is declared
# and unrun — which is allowed, but only out loud.
INVOCATION_SITES = ("Makefile", ".github/workflows", "scripts")

# Tools whose config may sit in pyproject without being invoked, each with the
# marker its comment must carry so the gap is visible rather than implied.
UNINVOKED_BUT_EXPLAINED = {"mypy": "Declared and never run"}


def _config() -> dict:
    return tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))


def _text() -> str:
    return PYPROJECT.read_text(encoding="utf-8")


class TestTheThreePythonVersionsAgree:
    """Three copies of a number is how they drift (M19, and test_gate_number_claims)."""

    @staticmethod
    def _declared() -> dict[str, tuple[int, int]]:
        cfg, text = _config(), _text()
        requires = re.search(r'^requires-python = ">=(\d+)\.(\d+)"', text, re.M)
        assert requires, "requires-python is no longer declared in the shape this test reads"
        target = cfg["tool"]["ruff"]["target-version"]
        mypy_v = cfg["tool"]["mypy"]["python_version"]
        return {
            "requires-python": (int(requires.group(1)), int(requires.group(2))),
            "ruff target-version": (int(target[2]), int(target[3:])),
            "mypy python_version": tuple(int(p) for p in mypy_v.split(".")),  # type: ignore[return-value]
        }

    def test_they_are_the_same_version(self):
        declared = self._declared()
        assert len(set(declared.values())) == 1, {
            **{k: ".".join(map(str, v)) for k, v in declared.items()},
            "why": (
                "these are three spellings of one decision. They read >=3.11 / py311 / "
                "3.11 while the gate had only ever been run on 3.13, and 3.11 was "
                "measured red on 2026-08-30. Move them together."
            ),
        }

    def test_the_floor_is_not_above_the_interpreter_running_the_gate(self):
        """A floor above the running interpreter means the gate is proving something
        about a version the package says it does not support."""
        floor = self._declared()["requires-python"]
        running = sys.version_info[:2]
        assert floor <= running, (
            f"requires-python declares >={floor[0]}.{floor[1]} but this gate is running "
            f"on {running[0]}.{running[1]}. Either the floor is wrong or this run does "
            "not support the package it is testing."
        )


class TestEveryDeclaredToolIsInvokedOrExplained:
    """`[tool.X]` in pyproject says the repo uses X. For mypy that was not true."""

    @staticmethod
    def _declared_tools() -> set[str]:
        # `pytest.ini_options` -> `pytest`; `setuptools.*` sections likewise.
        return {section.split(".")[0] for section in _config().get("tool", {})}

    @staticmethod
    def _invoked(tool: str) -> bool:
        for site in INVOCATION_SITES:
            path = ROOT / site
            files = [path] if path.is_file() else list(path.rglob("*")) if path.is_dir() else []
            for f in files:
                if not f.is_file():
                    continue
                try:
                    text = f.read_text(encoding="utf-8")
                except (UnicodeDecodeError, OSError):
                    continue
                if re.search(rf"\b{re.escape(tool)}\b", text):
                    return True
        return False

    def test_the_sweep_finds_an_invoked_tool(self):
        """Vacuity check — if the search breaks, every tool looks uninvoked and the
        test below turns into a demand for comments nobody can satisfy."""
        assert self._invoked("pytest"), "the invocation sweep cannot even find pytest"

    def test_each_tool_is_invoked_or_says_why_not(self):
        text = _text()
        silent = []
        for tool in sorted(self._declared_tools()):
            if self._invoked(tool):
                continue
            marker = UNINVOKED_BUT_EXPLAINED.get(tool)
            if marker is None or marker not in text:
                silent.append(tool)
        assert not silent, (
            f"these tools are configured in pyproject.toml but invoked nowhere in "
            f"{list(INVOCATION_SITES)}, and say nothing about it: {silent}.\n"
            "A `[tool.X]` block reads as a standard the repo holds. If X is not run, "
            "the config is an intention — say so in a comment beside it and add the "
            "marker to UNINVOKED_BUT_EXPLAINED, or wire it up. `strict = true` that "
            "nothing enforces is the shape this file exists to keep visible."
        )
