"""
`AGENT_BRIEF`'s Snapshot names the local model. It must be the one we serve.

Found 2026-08-16 while evaluating whether Qwen3.8-27B was worth adopting: the
Snapshot said "Local Qwen **7B**" while `Makefile` has served
`Qwen3-Coder-30B-A3B-Instruct-4bit` since 2026-07-11. `git log -L` dated it —
the Makefile default changed on 07-11 and the brief was written on **07-12**, so
the claim was **wrong when written, not stale** (the M19 ⓑ shape).

It mattered twice. The brief is the agent's entry point, so every session started
from a false premise about its own runtime; and the claim shaped the first pass of
a real evaluation ("we run 7B, so a 27B would be an upgrade") until the Makefile
was read. The real comparison is 3B-active MoE vs 27.78B-dense — the opposite
conclusion.

Deliberately loose: this asserts the brief names the **served model**, not any
particular size. Pinning the size would make every model bump a two-file edit
with no added truth.
"""

from __future__ import annotations

import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _served_model() -> str:
    """The model `make dev-up` actually starts, from the Makefile default."""
    for line in (ROOT / "Makefile").read_text(encoding="utf-8").splitlines():
        m = re.match(r"^MLX_MODEL\s*\?=\s*(\S+)", line)
        if m:
            return m.group(1)
    raise AssertionError("Makefile no longer defines MLX_MODEL — update this guard")


def test_the_makefile_still_declares_a_model():
    """Premise check: the guard is meaningless if the anchor moved."""
    assert "/" in _served_model(), _served_model()


def test_brief_names_the_served_model():
    served = _served_model()
    # "mlx-community/Qwen3-Coder-30B-A3B-Instruct-4bit" -> "Qwen3-Coder-30B-A3B"
    family = served.split("/")[-1]
    stem = re.sub(r"-(Instruct|Chat)?-?\d+bit$", "", family)
    core = "-".join(stem.split("-")[:3])  # Qwen3-Coder-30B-A3B -> Qwen3-Coder-30B

    brief = (ROOT / "docs/AGENT_BRIEF.md").read_text(encoding="utf-8")
    assert core in brief or stem in brief, (
        f"AGENT_BRIEF Snapshot does not name the served model {served!r}. "
        "The brief is the agent's entry point — a wrong model there starts every "
        "session from a false premise about its own runtime."
    )


def test_brief_does_not_name_a_retired_model():
    """The specific wrong claim, pinned: 7B was named while 30B-A3B was served."""
    brief = (ROOT / "docs/AGENT_BRIEF.md").read_text(encoding="utf-8")
    served = _served_model()
    for retired in ("Qwen 7B", "Qwen **7B**", "Qwen2.5-Coder-7B"):
        if retired in brief and retired.split("-")[-1] not in served:
            raise AssertionError(
                f"AGENT_BRIEF still names {retired!r} but the served model is {served!r}"
            )
