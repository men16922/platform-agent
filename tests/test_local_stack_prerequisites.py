"""
`make dev-up` promised a one-command stack that a fresh clone could not run.

`AGENT_BRIEF` says: *"`make dev-up`으로 로컬 스택(MLX+proxy+router+dashboard) 한 방
기동"*. Measured 2026-08-30: the recipe launches `.venv-mlx/bin/mlx_lm.server`, and
**nothing in this repo created `.venv-mlx`**. It was a hand-made venv on one
machine — 36 packages holding `mlx-lm` and `mlx`, with neither `platform-agent`
nor `pydantic-ai-slim` in it, so it was not `pip install .[onprem]` either.

The failure was **silent**, which is why nobody noticed. Two of the three call
sites launch under `nohup ... &` with stdout redirected to a log file, so a missing
binary produced no error on the terminal: `dev-up` printed *"model load takes
~30-60s"* and moved on, and the proxy then talked to nothing. This repo's
recurring shape — *values 파일은 에러가 아니라 안 읽히는 방식으로 실패한다* (Risk 8),
*TS 타입은 초록인데 라이브 페이지가 죽는다* (Risk 7).

`make mlx-setup` now creates it and the three call sites check before launching, so
the absence is loud. This file keeps that true.

⚠️ Deliberately does NOT assert `.venv-mlx` exists. It is gitignored, machine-local,
and macOS-only (`mlx` resolves only on Apple Silicon) — a test demanding it would go
red on CI for a reason that has nothing to do with the promise being kept. What is
checkable is the *shape*: something creates it, and every launch site looks first.
"""

from __future__ import annotations

import pathlib
import re

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
MAKEFILE = ROOT / "Makefile"

# The binary the local stack launches, spelled as the Makefile spells it via $(MLX_BIN)
# or literally. Both forms are searched: the literal path is what a copy-paste
# reintroduces, and it is exactly how the three sites read before this was fixed.
LAUNCH = re.compile(r"\.venv-mlx/bin/mlx_lm\.server")
GUARD = re.compile(r"-x \$\(MLX_BIN\)")


def _lines() -> list[str]:
    return MAKEFILE.read_text(encoding="utf-8").splitlines()


def _recipe_blocks() -> dict[str, list[str]]:
    """target -> its recipe lines. Comments and variables are not recipes."""
    blocks: dict[str, list[str]] = {}
    current: str | None = None
    for line in _lines():
        if line.startswith("\t"):
            if current:
                blocks.setdefault(current, []).append(line)
            continue
        m = re.match(r"^([A-Za-z0-9_.-]+):(?!=)", line)
        current = m.group(1) if m else None
    return blocks


def test_something_creates_the_venv_the_stack_runs_from():
    """The gap this file exists for: three targets used it, none made it."""
    blocks = _recipe_blocks()
    assert "mlx-setup" in blocks, (
        "no `mlx-setup` target. Three recipes launch .venv-mlx/bin/mlx_lm.server and "
        "before 2026-08-30 nothing in the repo created that venv, so `make dev-up` on "
        "a fresh clone launched a binary that does not exist — under `nohup`, silently."
    )
    recipe = "\n".join(blocks["mlx-setup"])
    assert "venv .venv-mlx" in recipe and "mlx-lm" in recipe, (
        "`mlx-setup` no longer creates the venv and installs mlx-lm into it:\n" + recipe
    )


def _launch_targets() -> dict[str, list[str]]:
    return {
        target: recipe
        for target, recipe in _recipe_blocks().items()
        if any(LAUNCH.search(line) for line in recipe)
    }


def test_the_sweep_finds_the_launch_sites():
    """Vacuity check — if the pattern stops matching, every assertion below is empty."""
    found = _launch_targets()
    assert len(found) >= 3, (
        f"expected at least 3 targets launching the MLX server, found {sorted(found)}. "
        "Measured 2026-08-30: mlx-serve, local-llm-up, dev-up."
    )


@pytest.mark.parametrize("target", sorted(_launch_targets()), ids=sorted(_launch_targets()))
def test_every_launch_site_checks_before_launching(target):
    recipe = _launch_targets()[target]
    guard_at = next((i for i, line in enumerate(recipe) if GUARD.search(line)), None)
    launch_at = next(i for i, line in enumerate(recipe) if LAUNCH.search(line))
    assert guard_at is not None, (
        f"`{target}` launches .venv-mlx/bin/mlx_lm.server without checking it exists.\n"
        "Two of these sites use `nohup ... &` with stdout to a log, so a missing binary "
        "is not an error the operator sees — it is a stack that starts and answers "
        "nothing. Add: @test -x $(MLX_BIN) || { $(MLX_MISSING); }"
    )
    assert guard_at < launch_at, (
        f"`{target}` checks for the binary *after* launching it (guard at recipe line "
        f"{guard_at}, launch at {launch_at}) — the check cannot stop what already ran."
    )
