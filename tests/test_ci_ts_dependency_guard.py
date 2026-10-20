"""Missing TS dependencies must fail CI through the actual contract fixtures."""
from __future__ import annotations

import importlib

import pytest

from tests._ts_toolchain import require_ts_toolchain


@pytest.fixture(autouse=True)
def isolated_ci_environment(monkeypatch):
    # Each selector must work independently, including when pytest itself is in CI.
    monkeypatch.delenv('CI', raising=False)
    monkeypatch.delenv('GITHUB_ACTIONS', raising=False)


def test_present_toolchain_does_not_skip_or_fail(tmp_path):
    compiler = tmp_path / 'tsc'
    compiler.write_text('#!/bin/sh\n')
    require_ts_toolchain(compiler, True, 'present')  # must not raise


def test_missing_toolchain_skips_outside_ci(tmp_path, monkeypatch):
    monkeypatch.delenv('CI', raising=False)
    monkeypatch.delenv('GITHUB_ACTIONS', raising=False)
    with pytest.raises(pytest.skip.Exception):
        require_ts_toolchain(tmp_path / 'missing-tsc', True, 'local dev')


@pytest.mark.parametrize('env_var', ['CI', 'GITHUB_ACTIONS'])
def test_missing_toolchain_fails_hard_under_ci(tmp_path, monkeypatch, env_var):
    monkeypatch.setenv(env_var, 'true')
    with pytest.raises(pytest.fail.Exception):
        require_ts_toolchain(tmp_path / 'missing-tsc', True, 'ci run')


def test_missing_node_fails_hard_under_ci_even_if_compiler_present(tmp_path, monkeypatch):
    monkeypatch.setenv('CI', 'true')
    compiler = tmp_path / 'tsc'
    compiler.write_text('#!/bin/sh\n')
    with pytest.raises(pytest.fail.Exception):
        require_ts_toolchain(compiler, False, 'ci run')


@pytest.mark.parametrize('module_name,fixture_name,root_name', [
    ('tests.test_registry_preview_ui', 'run_ts', 'DASH'),
    ('tests.test_registry_planner_stack', 'synth', 'STACKS'),
])
@pytest.mark.parametrize('ci_variable', [None, 'CI', 'GITHUB_ACTIONS'])
@pytest.mark.parametrize('missing', ['compiler', 'node'])
def test_contract_fixture_enforces_dependency_policy(
    module_name, fixture_name, root_name, ci_variable, missing,
    tmp_path, tmp_path_factory, monkeypatch,
):
    module = importlib.import_module(module_name)
    monkeypatch.setattr(module, root_name, tmp_path)
    compiler = tmp_path / 'node_modules/.bin/tsc'
    if missing == 'node':
        compiler.parent.mkdir(parents=True)
        compiler.touch()
    monkeypatch.setattr(module.shutil, 'which', lambda _: None if missing == 'node' else '/node')
    if ci_variable:
        monkeypatch.setenv(ci_variable, 'true')
    expected = pytest.fail.Exception if ci_variable else pytest.skip.Exception
    # Catch both: an accidental CI skip must become a failed assertion, not a
    # skipped regression test. Execute the real fixture before any compilation.
    with pytest.raises((pytest.fail.Exception, pytest.skip.Exception)) as result:
        getattr(module, fixture_name).__wrapped__(tmp_path_factory)
    assert type(result.value) is expected
