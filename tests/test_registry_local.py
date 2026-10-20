"""Explicit local adapter uses real Git objects and current fixture records."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from src.agents.platform.registry_local import GitSnapshot, LocalUsers

ROOT = Path(__file__).resolve().parents[1]


def test_local_users_reloads_grants_without_cached_success(tmp_path):
    path = tmp_path / 'users.json'
    path.write_text(json.dumps({'operator': {'registry_write_tenants': ['acme']}}))
    users = LocalUsers(path)
    assert users.get_current_user('operator')['registry_write_tenants'] == ['acme']
    path.write_text('{}')
    assert users.get_current_user('operator') is None
    path.write_text('invalid')
    with pytest.raises(ValueError):
        users.get_current_user('operator')


def test_git_snapshot_reads_pinned_commit_not_worktree(tmp_path):
    def git(*args):
        return subprocess.run(['git', '-C', str(tmp_path), *args], check=True, capture_output=True).stdout
    git('init', '-q')
    path = tmp_path / 'registry.yaml'
    path.write_bytes(b'original\n')
    git('add', 'registry.yaml')
    git('-c', 'user.name=Local Test', '-c', 'user.email=local@example.test', 'commit', '-qm', 'fixture')
    reader = GitSnapshot(str(tmp_path))
    revision = reader.resolve_revision()
    path.write_bytes(b'uncommitted\n')
    file = reader.read_file('registry.yaml', revision=revision)
    assert file.content == b'original\n'
    assert path.read_bytes() == b'uncommitted\n'
    (tmp_path / 'link.yaml').symlink_to('registry.yaml')
    git('add', 'link.yaml')
    git('-c', 'user.name=Local Test', '-c', 'user.email=local@example.test', 'commit', '-qm', 'symlink')
    with pytest.raises(ValueError, match='invalid_local_snapshot'):
        reader.read_file('link.yaml', revision=reader.resolve_revision())


@pytest.mark.parametrize('mode,vercel', [('', ''), ('aws', ''), ('local', '1')])
def test_cli_never_enables_local_fixture_on_vercel_or_by_default(mode, vercel):
    result = subprocess.run([sys.executable, '-m', 'src.agents.platform.registry_local'],
                            cwd=ROOT, input='{}', text=True, capture_output=True, check=True,
                            env={**os.environ, 'REGISTRY_PLANNER_MODE': mode, 'VERCEL': vercel})
    assert json.loads(result.stdout) == dict(ok=False, status=503, error='planner_unavailable')
    assert not result.stderr
