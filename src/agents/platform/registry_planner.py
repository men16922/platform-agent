"""Offline preview boundary for Phase 5; no authorization or remote writes.

The trusted reader owns repository/default-branch configuration and must verify
commit membership when fetching blobs. SHA-1 here is the Git object identifier,
not an authentication mechanism. The envelope digest is also a content binding,
not a signature: later submission must use a server-held plan and reauthorize.
"""
from __future__ import annotations

import difflib
import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Mapping, Protocol

import yaml

from src.agents.platform.registry import load_registry
from src.agents.platform.registry_write import RegistryWriteError, plan_addon_attachment

MAX_FILE_BYTES = 256 * 1024
CONTRACT_VERSION = "registry-attachment/v1"
_FIELDS = {"tenant", "env", "capability", "version"}
_SLUG = re.compile(r"[a-z0-9][a-z0-9-]{0,62}")
_VERSION = re.compile(r"[A-Za-z0-9][A-Za-z0-9.+_-]{0,127}")
_OID = re.compile(r"[0-9a-f]{40}")


class PlannerError(ValueError):
    """Stable errors for a future transport adapter; messages contain no inputs."""

    def __init__(self, code: str, status: int = 422):
        self.code = code
        self.status = status
        super().__init__(code)


@dataclass(frozen=True)
class SnapshotFile:
    commit: str
    path: str
    blob: str
    content: bytes


class SnapshotReader(Protocol):
    """Read-only adapter, configured by the server, never by the request."""

    def resolve_revision(self) -> str: ...

    def read_file(self, path: str, *, revision: str) -> SnapshotFile: ...


@dataclass(frozen=True)
class PlanEnvelope:
    contract_version: str
    request_id: str
    base_commit: str
    catalog_blob: str
    tenant_blob: str
    values_path: str
    values_blob: str
    path: str
    diff: str
    output_sha256: str
    digest: str
    expires_at: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


def _git_blob(content: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(content)).encode("ascii") + b"\0" + content).hexdigest()


class _UniqueLoader(yaml.SafeLoader):
    def construct_mapping(self, node, deep=False):
        result = {}
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            if not isinstance(key, str) or key in result:
                raise PlannerError("invalid_yaml")
            result[key] = self.construct_object(value_node, deep=deep)
        return result


def _document(content: bytes) -> tuple[str, dict]:
    if not isinstance(content, bytes) or len(content) > MAX_FILE_BYTES:
        raise PlannerError("invalid_file_size")
    try:
        text = content.decode("utf-8")
        # Bound nesting and event count before constructing data. Alias/merge
        # semantics are unnecessary for these two declarative input files.
        depth = 0
        for count, event in enumerate(yaml.parse(text), start=1):
            if isinstance(event, yaml.AliasEvent) or count > 10000:
                raise PlannerError("invalid_yaml")
            if isinstance(event, (yaml.MappingStartEvent, yaml.SequenceStartEvent)):
                depth += 1
                if depth > 64:
                    raise PlannerError("invalid_yaml")
            elif isinstance(event, (yaml.MappingEndEvent, yaml.SequenceEndEvent)):
                depth -= 1
        data = yaml.load(text, Loader=_UniqueLoader)
        if not isinstance(data, dict):
            raise PlannerError("invalid_yaml")
        return text, data
    except PlannerError:
        raise
    except (UnicodeError, yaml.YAMLError, RecursionError, ValueError):
        raise PlannerError("invalid_yaml") from None


def validate_attachment_request(request: Mapping[str, object]) -> dict[str, str]:
    """Validate and copy the four user fields before any lookup or planning."""
    if not isinstance(request, Mapping) or set(request) != _FIELDS:
        raise PlannerError("invalid_request")
    result = dict(request)
    for key, value in result.items():
        pattern = _VERSION if key == "version" else _SLUG
        if not isinstance(value, str) or not pattern.fullmatch(value):
            raise PlannerError("invalid_request")
    return result


def _read(reader: SnapshotReader, path: str, revision: str) -> SnapshotFile:
    try:
        blob = reader.read_file(path, revision=revision)
    except Exception:
        raise PlannerError("snapshot_unavailable", 503) from None
    if not isinstance(blob, SnapshotFile) or blob.path != path:
        raise PlannerError("snapshot_path_mismatch")
    if blob.commit != revision:
        raise PlannerError("snapshot_revision_mismatch", 409)
    if not isinstance(blob.content, bytes) or len(blob.content) > MAX_FILE_BYTES:
        raise PlannerError("invalid_file_size")
    if blob.blob != _git_blob(blob.content):
        raise PlannerError("snapshot_blob_mismatch")
    return blob


@dataclass(frozen=True)
class PlanArtifact:
    """Internal planner result; only envelope is part of the preview response."""
    envelope: PlanEnvelope
    output: str


def plan_snapshot(
    request: Mapping[str, object], *, subject: str, reader: SnapshotReader,
    request_id: str, now: datetime,
) -> PlanEnvelope:
    return plan_snapshot_artifact(request, subject=subject, reader=reader,
                                  request_id=request_id, now=now).envelope


def plan_snapshot_artifact(
    request: Mapping[str, object], *, subject: str, reader: SnapshotReader,
    request_id: str, now: datetime,
) -> PlanArtifact:
    """Produce a five-minute preview from inputs at one immutable revision.

    ``subject``, ``request_id`` and ``now`` are trusted server inputs, separate
    from the four-field user request. The caller must authenticate/authorize;
    this offline function does neither. Fixed inputs produce identical output.
    """
    values = validate_attachment_request(request)
    if (not isinstance(subject, str) or not subject.strip() or len(subject) > 256
            or not isinstance(request_id, str)
            or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", request_id)
            or not isinstance(now, datetime) or now.utcoffset() is None):
        raise PlannerError("invalid_server_context")
    try:
        revision = reader.resolve_revision()
    except Exception:
        raise PlannerError("snapshot_unavailable", 503) from None
    if not isinstance(revision, str) or not _OID.fullmatch(revision):
        raise PlannerError("invalid_revision")
    path = f"platform/tenants/{values['tenant']}.yaml"
    catalog = _read(reader, "platform/catalog.yaml", revision)
    tenant = _read(reader, path, revision)
    _, catalog_data = _document(catalog.content)
    original, before = _document(tenant.content)
    try:
        entry = catalog_data['capabilities'][values['capability']]
        values_path = entry['self_hosted_values']
        if not isinstance(values_path, str) or not re.fullmatch(
            r"infra/onprem/addons/values/[A-Za-z0-9][A-Za-z0-9_-]*\.yaml", values_path
        ):
            raise PlannerError("invalid_values_path")
        baseline = _read(reader, values_path, revision)
        _, baseline_data = _document(baseline.content)
        if not baseline_data:
            raise PlannerError("invalid_registry")
        with TemporaryDirectory(prefix="registry-preview-") as directory:
            snapshot_root = Path(directory).resolve()
            root = snapshot_root / "platform"
            (root / "tenants").mkdir(parents=True)
            catalog_path = root / "catalog.yaml"
            target = root / "tenants" / f"{values['tenant']}.yaml"
            baseline_path = snapshot_root / values_path
            baseline_path.parent.mkdir(parents=True)
            catalog_path.write_bytes(catalog.content)
            target.write_bytes(tenant.content)
            baseline_path.write_bytes(baseline.content)
            registry = load_registry(root)
            environment = registry.environment(values['tenant'], values['env'])
            if environment.addon_version(values['capability']) is not None:
                raise PlannerError("already_attached", 409)
            backend = registry.backend_for(values['capability'], environment.substrate)
            plan = plan_addon_attachment(**values, root=root, values_repo_root=snapshot_root)
            if (plan.path != target or plan.original != original
                    or any(getattr(plan, key) != value for key, value in values.items())
                    or plan.backend != backend
                    or catalog_path.read_bytes() != catalog.content
                    or target.read_bytes() != tenant.content
                    or baseline_path.read_bytes() != baseline.content):
                raise PlannerError("invalid_planner_output")
            if {p for p in snapshot_root.rglob('*') if p.is_file()} != {
                catalog_path, target, baseline_path,
            }:
                raise PlannerError("invalid_planner_output")
            updated = plan.updated
            _, after = _document(updated.encode("utf-8"))
            # Independently check the target key and the rest of the document,
            # even if the existing planner's own change guard is regressed.
            expected_value = f"{backend} {values['version']}"
            addons = after['environments'][values['env']]['addons']
            if addons.pop(values['capability']) != expected_value or after != before:
                raise PlannerError("invalid_planner_output")
            old_lines, new_lines = original.splitlines(keepends=True), updated.splitlines(keepends=True)
            if len(new_lines) != len(old_lines) + 1 or not any(
                line.strip() == f"{values['capability']}: {expected_value}"
                and new_lines[:i] + new_lines[i + 1:] == old_lines
                for i, line in enumerate(new_lines)
            ):
                raise PlannerError("invalid_planner_output")
    except PlannerError:
        raise
    except OSError:
        raise PlannerError("snapshot_unavailable", 503) from None
    except (RegistryWriteError, ValueError, TypeError, KeyError, AttributeError, yaml.YAMLError):
        raise PlannerError("invalid_registry") from None
    diff = "".join(difflib.unified_diff(
        original.splitlines(keepends=True), updated.splitlines(keepends=True),
        fromfile=f"a/{path}", tofile=f"b/{path}",
    ))
    expires_at = (now.astimezone(timezone.utc) + timedelta(minutes=5)).isoformat()
    public = dict(
        contract_version=CONTRACT_VERSION, request_id=request_id,
        base_commit=revision, catalog_blob=catalog.blob, tenant_blob=tenant.blob,
        values_path=values_path, values_blob=baseline.blob,
        path=path, diff=diff,
        output_sha256=hashlib.sha256(updated.encode("utf-8")).hexdigest(),
        expires_at=expires_at,
    )
    digest_input = {**public, "subject": subject, "request": values}
    digest = hashlib.sha256(json.dumps(
        digest_input, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
    ).encode("utf-8")).hexdigest()
    return PlanArtifact(PlanEnvelope(**public, digest=digest), updated)
