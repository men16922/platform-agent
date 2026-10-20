"""Explicit local preview adapter: stdin Invoke event, current users JSON, Git HEAD.

Enabled only by the server's local-mode configuration, never on Vercel. Users
are a local fixture store, not fallback data for the production DynamoDB reader.
"""
import json
import ipaddress
import os
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone
from uuid import uuid4
from urllib.parse import urlparse

from src.agents.platform.registry_preview_service import handle_stored_event
from src.agents.platform.registry_plan_store import DynamoPlanStore
from src.agents.platform.registry_planner import SnapshotFile, MAX_FILE_BYTES


class LocalUsers:
    def __init__(self, path):
        self.path = Path(path)

    def get_current_user(self, username):
        data = json.loads(self.path.read_text())
        return data.get(username)


class GitSnapshot:
    def __init__(self, root):
        self.root = root

    def git(self, *args):
        return subprocess.run(['git', '-C', self.root, *args], check=True,
                              capture_output=True, timeout=5).stdout

    def resolve_revision(self):
        return self.git('rev-parse', 'HEAD').decode().strip()

    def read_file(self, path, *, revision):
        entry = self.git('ls-tree', revision, '--', path).decode().strip()
        metadata, actual_path = entry.split('\t')
        mode, kind, sha = metadata.split()
        if (mode, kind, actual_path) != ('100644', 'blob', path):
            raise ValueError('invalid_local_snapshot')
        if int(self.git('cat-file', '-s', sha)) > MAX_FILE_BYTES:
            raise ValueError('snapshot_too_large')
        return SnapshotFile(revision, path, sha, self.git('cat-file', 'blob', sha))


def local_plan_store(endpoint, table_name):
    """Explicit loopback-only store; never discover credentials or create tables."""
    url = urlparse(endpoint)
    if (url.scheme != 'http' or not url.hostname
            or not ipaddress.ip_address(url.hostname).is_loopback
            or url.username or url.password or url.path not in ('', '/')
            or url.query or url.fragment or not table_name):
        raise ValueError('explicit_loopback_endpoint_required')
    import boto3
    from botocore.config import Config
    resource = boto3.resource('dynamodb', endpoint_url=endpoint, region_name='ap-northeast-2',
        aws_access_key_id='local', aws_secret_access_key='local',
        config=Config(connect_timeout=1, read_timeout=2, retries={'max_attempts': 0}, proxies={}))
    return DynamoPlanStore(resource.Table(table_name))


def main():
    if os.environ.get('REGISTRY_PLANNER_MODE') != 'local' or os.environ.get('VERCEL'):
        raise ValueError('local_planner_disabled')
    raw = sys.stdin.buffer.read(8193)
    if len(raw) > 8192:
        raise ValueError('request_too_large')
    operation = ('preview' if len(sys.argv) == 1 else
                 {'--prepare':'prepare','--status':'status'}.get(sys.argv[1], '') if len(sys.argv)==2 else '')
    result = handle_stored_event(json.loads(raw), operation=operation, dependencies_factory=lambda: (
        LocalUsers(os.environ['REGISTRY_PLANNER_LOCAL_USERS']),
        GitSnapshot(os.environ['REGISTRY_PLANNER_LOCAL_REPO']),
        local_plan_store(os.environ['REGISTRY_PLANNER_LOCAL_PLAN_ENDPOINT'],
                         os.environ['REGISTRY_PLANNER_LOCAL_PLAN_TABLE']),
    ), request_id=str(uuid4()), clock=lambda: datetime.now(timezone.utc))
    print(json.dumps(result))


if __name__ == '__main__':
    try:
        main()
    except Exception:
        print(json.dumps(dict(ok=False, status=503, error='planner_unavailable')))
