"""Shared CI-vs-local policy for tests that need a compiled TS toolchain.

A missing `tsc` binary must not present as a passing skip in CI: `gate.yml` is
responsible for installing `dashboard/` and `src/stacks/` node_modules before
`make check` runs. If that install step is ever removed or breaks, the TS
contract and CDK synthesis tests must go red, not quietly disappear into the
skip count — a skip and a real pass look identical in `gh pr checks` (Risk 12:
스킵은 실패가 아니다). On a developer machine without the toolchain installed,
skipping is still the right call; the distinction is whether pytest is running
under CI.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest


def require_ts_toolchain(compiler: Path, node_available: bool, hint: str) -> None:
    if compiler.exists() and node_available:
        return
    reason = f"{hint} ({compiler} exists={compiler.exists()}, node on PATH={node_available})"
    if os.environ.get("CI") or os.environ.get("GITHUB_ACTIONS"):
        pytest.fail(
            f"{reason} — running under CI (CI/GITHUB_ACTIONS set), where gate.yml "
            "must install this toolchain before pytest runs. Skipping here would "
            "hide a broken or missing npm-install step behind a green gate."
        )
    pytest.skip(reason)
