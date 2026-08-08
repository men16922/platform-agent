"""Plan an add-on attachment as an edit to exactly one tenant file.

Phase 5's write half. The design (docs/plans/2026-07-21-multi-tenant-env-addons.md)
says the dashboard's "attach add-on" may only ever open a PR against
``platform/tenants/<tenant>.yaml``, and every tenant file's own header repeats it.
Until now that was a sentence; this module is the part that can be falsified.

TWO DECISIONS WORTH KNOWING.

1. **Edited as text, verified as data.** These files are mostly comments, and the
   comments carry the reasoning this repo keeps paying to rediscover — why `quota`
   does not cover node starvation, why `scope` exists, which flow may write here.
   A YAML round-trip would silently delete all of it, so the edit is a surgical
   line insertion. That is fragile on its own, so the result is then parsed and
   compared against the original **as data**: the only permitted difference is the
   one key being added. An edit that lands in the wrong block, or corrupts the
   file, or touches another environment, fails that comparison rather than
   producing a plausible-looking PR.

2. **The blast radius is a path, and it is checked twice.** The tenant name is
   validated as a bare slug before it is ever joined to a path (a tenant called
   ``../globex`` must not resolve), and the resulting path is required to be
   inside the tenants directory. One check is a rule; two checks are a rule and
   a guard against the way the rule gets refactored.

3. **The commit is path-limited, because the instruction was not.** Until now this
   module stopped at the edited text and told the operator to run ``git commit -am``.
   ``-a`` stages every modified tracked file, so following the printed instruction
   with anything else dirty produces a PR that touches more than the one file —
   the invariant broken by the tool that exists to enforce it. ``commit_attachment``
   commits *the path*, not the working tree, so unrelated dirt cannot ride along.

NOT IN HERE, ON PURPOSE: opening the PR. This goes as far as a **local** commit —
no network, no remote, no API. Pushing a branch and calling GitHub is outward-facing
and stays with the operator (see ``scripts/attach_addon.py``).
"""

from __future__ import annotations

import difflib
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from src.agents.platform.registry import load_registry

#: Tenant names are filenames. Anything outside this is refused before it becomes
#: a path — `..`, `/`, and absolute names never get the chance to escape.
_TENANT_NAME = re.compile(r"^[a-z0-9][a-z0-9-]*$")

_REPO_ROOT = Path(__file__).resolve().parents[3]


class RegistryWriteError(RuntimeError):
    """Raised when an attachment cannot be planned. Always fail-closed."""


@dataclass(frozen=True)
class AddonAttachment:
    """A planned edit: one capability, one environment, one file."""

    tenant: str
    env: str
    capability: str
    backend: str
    version: str
    #: The only file this attachment is allowed to change.
    path: Path
    original: str
    updated: str

    @property
    def branch(self) -> str:
        return f"attach-addon/{self.tenant}-{self.env}-{self.capability}"

    @property
    def title(self) -> str:
        return f"{self.tenant}/{self.env}: attach {self.capability} ({self.backend} {self.version})"

    def diff(self) -> str:
        rel = self.path.relative_to(_REPO_ROOT) if self.path.is_relative_to(_REPO_ROOT) else self.path
        return "".join(
            difflib.unified_diff(
                self.original.splitlines(keepends=True),
                self.updated.splitlines(keepends=True),
                fromfile=f"a/{rel}",
                tofile=f"b/{rel}",
            )
        )


def tenant_path(tenant: str, *, root: Path | None = None) -> Path:
    """Resolve a tenant's registry file, refusing anything that is not a plain name."""
    if not _TENANT_NAME.match(tenant or ""):
        raise RegistryWriteError(
            f"tenant {tenant!r} is not a plain registry name — refusing to turn it into a path"
        )
    tenants_dir = ((root or (_REPO_ROOT / "platform")) / "tenants").resolve()
    path = (tenants_dir / f"{tenant}.yaml").resolve()
    # The name was already validated; this catches the case where that validation
    # is later loosened or the directory is a symlink out of the tree.
    if path.parent != tenants_dir:
        raise RegistryWriteError(f"refusing to write outside {tenants_dir}")
    if not path.is_file():
        raise RegistryWriteError(f"no registry entry for tenant {tenant!r} at {path.name}")
    return path


def _insert_addon(text: str, env: str, capability: str, value: str) -> str:
    """Insert ``capability: value`` into ``environments.<env>.addons``.

    Walks the file by indentation rather than parsing it, so every comment,
    blank line and quoting choice around the edit survives untouched. The result
    is checked by :func:`_assert_only_change` — this function is allowed to be
    naive because it is not allowed to be trusted.
    """
    lines = text.splitlines(keepends=True)
    in_environments = in_env = in_addons = False
    insert_at: int | None = None

    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(line) - len(line.lstrip())

        if indent == 0:
            in_environments = stripped.startswith("environments:")
            in_env = in_addons = False
            continue
        if not in_environments:
            continue

        if indent == 2 and stripped.endswith(":"):
            in_env = stripped[:-1].strip() == env
            in_addons = False
            continue
        if not in_env:
            continue

        if indent == 4:
            in_addons = stripped == "addons:"
            if not in_addons and insert_at is not None:
                break          # left the addons block; the insertion point is fixed
            continue

        if in_addons and indent > 4:
            insert_at = i + 1  # keep moving to the end of the block

    if insert_at is None:
        raise RegistryWriteError(
            f"could not find environments.{env}.addons — refusing to guess where the edit goes"
        )

    indent = " " * (len(lines[insert_at - 1]) - len(lines[insert_at - 1].lstrip()))
    lines.insert(insert_at, f"{indent}{capability}: {value}\n")
    return "".join(lines)


def _assert_only_change(original: str, updated: str, env: str, capability: str, value: str) -> None:
    """The parsed documents may differ in exactly one key, and no other way."""
    before: dict[str, Any] = yaml.safe_load(original) or {}
    after: dict[str, Any] = yaml.safe_load(updated) or {}

    envs_after = (after.get("environments") or {}).get(env) or {}
    if (envs_after.get("addons") or {}).get(capability) != value:
        raise RegistryWriteError(
            f"the edit did not land in environments.{env}.addons.{capability} — refusing"
        )

    # Remove the intended change and require byte-for-byte structural equality.
    # Anything else the insertion disturbed — a sibling environment, a quota, the
    # isolation tier — shows up here rather than in a reviewer's blind spot.
    del after["environments"][env]["addons"][capability]
    if after != before:
        raise RegistryWriteError(
            "the edit changed more than the one add-on key — refusing to open a PR for it"
        )


def plan_addon_attachment(
    tenant: str,
    env: str,
    capability: str,
    version: str,
    *,
    root: Path | None = None,
) -> AddonAttachment:
    """Plan attaching ``capability`` to ``tenant``/``env``. Never writes to disk."""
    path = tenant_path(tenant, root=root)
    registry = load_registry(root) if root else load_registry()

    environment = registry.environment(tenant, env)   # raises if either is unknown

    reason = registry.uninstallable_reason(capability)
    if reason:
        raise RegistryWriteError(f"capability {capability!r} cannot be installed: {reason}")

    if environment.addon_version(capability) is not None:
        # Changing a version is a different review with different risk, and
        # silently turning "attach" into "upgrade" is how a PR gets approved for
        # something it does not say.
        raise RegistryWriteError(
            f"{tenant}/{env} already declares {capability!r} — attaching is not upgrading"
        )

    backend = registry.backend_for(capability, environment.substrate)
    if not backend:
        raise RegistryWriteError(
            f"no backend satisfies {capability!r} on substrate {environment.substrate!r}"
        )

    original = path.read_text(encoding="utf-8")
    value = f"{backend} {version}"
    updated = _insert_addon(original, env, capability, value)
    _assert_only_change(original, updated, env, capability, value)

    return AddonAttachment(
        tenant=tenant, env=env, capability=capability, backend=backend,
        version=version, path=path, original=original, updated=updated,
    )


def _git(repo_root: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo_root), *args],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        raise RegistryWriteError(
            f"git {' '.join(args)} failed: {(proc.stderr or proc.stdout).strip()}"
        )
    return proc.stdout


def commit_attachment(plan: AddonAttachment, *, repo_root: Path | None = None) -> str:
    """Apply the plan and commit it on its own branch. Local only — never pushes.

    The commit is **path-limited** (``git commit -- <path>``), not
    ``git commit -a``. That difference is the whole point: ``-a`` sweeps in every
    modified tracked file, so the printed instruction this replaces could produce
    a PR touching files the plan never named — from the tool whose one job is that
    the PR touches exactly one file. A path-limited commit ignores the index and
    the rest of the working tree, so unrelated dirt physically cannot ride along.

    Returns the new commit's sha. Raises ``RegistryWriteError`` if the branch
    already exists, so a second run cannot quietly append to the first one's PR.
    """
    root = (repo_root or _REPO_ROOT).resolve()
    if not plan.path.is_relative_to(root):
        raise RegistryWriteError(f"refusing to commit {plan.path} — it is outside {root}")

    existing = _git(root, "branch", "--list", plan.branch).strip()
    if existing:
        raise RegistryWriteError(
            f"branch {plan.branch!r} already exists — refusing to add to an open attachment"
        )

    plan.path.write_text(plan.updated, encoding="utf-8")
    _git(root, "switch", "-c", plan.branch)
    # `-- <path>`: commit this file's working-tree content and nothing else.
    _git(root, "commit", "-m", plan.title, "--", str(plan.path.relative_to(root)))
    return _git(root, "rev-parse", "HEAD").strip()
