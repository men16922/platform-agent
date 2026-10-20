"""Production read adapters: current DynamoDB users and public GitHub snapshots.

No GitHub credential is accepted: this initial runtime reads a public repository.
Private repository/token provisioning remains a separate operational decision.
"""
from __future__ import annotations

import base64
import hashlib
import json
import re
import urllib.parse
import urllib.request

from src.agents.platform.registry_planner import MAX_FILE_BYTES, SnapshotFile


class DynamoCurrentUsers:
    def __init__(self, table):
        self.table = table

    def get_current_user(self, username: str):
        return self.table.get_item(
            Key={"username": username}, ConsistentRead=True,
        ).get("Item")


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("registry_redirect_refused")


def _github_json(url: str) -> dict:
    request = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "platform-agent-registry-planner",
    }, method="GET")
    with urllib.request.build_opener(_NoRedirect()).open(request, timeout=5) as response:
        raw = response.read(1024 * 1024 + 1)
    if len(raw) > 1024 * 1024:
        raise ValueError("registry_response_too_large")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("invalid_registry_response")
    return data


def _oid(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{40}", value):
        raise ValueError("invalid_git_object")
    return value


class GitHubSnapshotReader:
    """Walk immutable commit/tree/blob objects; reject symlinks and submodules.

    json_get is a transport seam for offline Git object fixtures, not caller
    configuration. All production URLs are constructed at api.github.com.
    Caches live only in this request's reader instance.
    """
    def __init__(self, repository: str, branch: str, *, json_get=_github_json):
        if not re.fullmatch(r"[A-Za-z0-9_-]+/[A-Za-z0-9_.-]+", repository):
            raise ValueError("invalid_repository")
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_./-]{0,199}", branch) or '..' in branch:
            raise ValueError("invalid_branch")
        self.base = f"https://api.github.com/repos/{repository}"
        self.branch = branch
        self.json_get = json_get
        self.objects = {}

    def _get(self, suffix):
        if suffix not in self.objects:
            self.objects[suffix] = self.json_get(self.base + suffix)
        return self.objects[suffix]

    def resolve_revision(self):
        data = self._get('/git/ref/heads/' + urllib.parse.quote(self.branch, safe=''))
        if data.get('ref') != 'refs/heads/' + self.branch or data['object']['type'] != 'commit':
            raise ValueError('invalid_branch_ref')
        return _oid(data['object']['sha'])

    def read_file(self, path: str, *, revision: str) -> SnapshotFile:
        if not re.fullmatch(
            r"platform/catalog\.yaml|platform/tenants/[a-z0-9][a-z0-9-]{0,62}\.yaml|"
            r"infra/onprem/addons/values/[A-Za-z0-9][A-Za-z0-9_-]*\.yaml", path
        ):
            raise ValueError('invalid_snapshot_path')
        commit = self._get('/git/commits/' + _oid(revision))
        if commit['sha'] != revision:
            raise ValueError('commit_mismatch')
        tree_id = _oid(commit['tree']['sha'])
        parts = path.split('/')
        for index, part in enumerate(parts):
            tree = self._get('/git/trees/' + tree_id)
            if tree['sha'] != tree_id or tree.get('truncated') is not False:
                raise ValueError('invalid_tree')
            entries = [entry for entry in tree['tree'] if entry.get('path') == part]
            if len(entries) != 1:
                raise ValueError('missing_or_ambiguous_path')
            entry = entries[0]
            last = index == len(parts) - 1
            if (entry.get('type'), entry.get('mode')) != (('blob', '100644') if last else ('tree', '040000')):
                raise ValueError('non_regular_snapshot_path')
            tree_id = _oid(entry['sha'])
        if type(entry.get('size')) is not int or not 0 <= entry['size'] <= MAX_FILE_BYTES:
            raise ValueError('invalid_blob_size')
        blob = self._get('/git/blobs/' + tree_id)
        if blob['sha'] != tree_id or blob.get('encoding') != 'base64' or blob.get('size') != entry['size']:
            raise ValueError('invalid_blob')
        content = base64.b64decode(''.join(blob['content'].split()), validate=True)
        actual = hashlib.sha1(b'blob ' + str(len(content)).encode() + b'\0' + content).hexdigest()
        if len(content) != entry['size'] or actual != tree_id:
            raise ValueError('blob_content_mismatch')
        return SnapshotFile(revision, path, tree_id, content)
