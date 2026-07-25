"""Preflight a Terraform → GitOps ownership handoff. Read-only; changes nothing.

Phase 1b hands add-on ownership from `helm_release` to a GitOps engine via
`terraform state rm` + adoption of the already-installed release. Adoption must
be a no-op — if the controller treats the objects as new it deletes and recreates
them, taking any PVC with them.

This answers "is it safe yet?" BEFORE anything leaves Terraform state, and exits
non-zero on anything it cannot prove.

Usage:
  python scripts/preflight_gitops_handoff.py <release> -n <namespace>
                                             [--terraform-address helm_release.x]
                                             [--snapshot-taken] [--json]

Exit codes: 0 = safe to proceed, 1 = blocking findings, 2 = could not evaluate.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.agents.platform.handoff import preflight, rollback_commands  # noqa: E402


def _run(cmd: list[str], timeout: int = 120) -> tuple[int, str, str]:
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 1, "", str(exc)
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()


def _helm_revision(release: str, namespace: str) -> int | None:
    code, out, _ = _run(["helm", "status", release, "-n", namespace, "-o", "json"])
    if code != 0:
        return None
    try:
        return int(json.loads(out)["version"])
    except (ValueError, KeyError, TypeError):
        return None


def _release_resources(release: str, namespace: str) -> list[dict]:
    """
    Every live object Helm applied for this release, with its real metadata.

    Enumerated from ``helm get manifest`` rather than by label selector: charts are
    not obliged to stamp ``app.kubernetes.io/instance``, and a selector that misses
    them reports "no resources found", which reads as a blocker when the release is
    actually fine. The manifest is the authoritative list of what Helm owns; the
    live objects are then fetched because only they carry the ownership metadata
    Helm applies at install time.
    """
    code, manifest, _ = _run(["helm", "get", "manifest", release, "-n", namespace])
    if code != 0:
        return []

    targets: list[tuple[str, str]] = []
    for doc in manifest.split("\n---"):
        kind = name = ""
        for line in doc.splitlines():
            stripped = line.strip()
            if not kind and stripped.startswith("kind:"):
                kind = stripped.split(":", 1)[1].strip()
            # Only the FIRST `name:` at metadata depth is the object's own name;
            # deeper ones belong to containers, volumes, ports…
            elif not name and line.startswith("  name:"):
                name = stripped.split(":", 1)[1].strip()
            if kind and name:
                break
        if kind and name:
            targets.append((kind, name))

    resources: list[dict] = []
    for kind, name in targets:
        code, out, _ = _run(["kubectl", "get", kind, name, "-n", namespace, "-o", "json"])
        if code != 0:
            continue
        try:
            resources.append(json.loads(out))
        except ValueError:
            continue
    return resources


def _commits_ahead() -> tuple[int, bool]:
    code, out, _ = _run(["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"])
    if code != 0:
        return 0, False
    code, out, _ = _run(["git", "rev-list", "--count", "@{upstream}..HEAD"])
    if code != 0:
        return 0, True
    try:
        return int(out.strip()), True
    except ValueError:
        return 0, True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("release")
    parser.add_argument("-n", "--namespace", required=True)
    parser.add_argument("--terraform-address", default="helm_release.<name>",
                        help="address to import back on rollback")
    parser.add_argument("--snapshot-taken", action="store_true",
                        help="assert a volume snapshot exists (required when the release is stateful)")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    revision = _helm_revision(args.release, args.namespace)
    if revision is None:
        print(f"ERROR: no helm release {args.release!r} in namespace {args.namespace!r}",
              file=sys.stderr)
        return 2

    resources = _release_resources(args.release, args.namespace)
    commits_ahead, remote_configured = _commits_ahead()

    result = preflight(
        release=args.release,
        namespace=args.namespace,
        revision=revision,
        resources=resources,
        commits_ahead=commits_ahead,
        remote_configured=remote_configured,
        snapshot_taken=args.snapshot_taken,
    )
    commands = rollback_commands(args.terraform_address, args.release, args.namespace)

    if args.json:
        print(json.dumps({**result.to_dict(), "rollback": commands}, indent=2))
    else:
        verdict = "SAFE TO PROCEED" if result.safe else "BLOCKED"
        print(f"[handoff-preflight] {args.release} (ns={args.namespace}) — {verdict}")
        for finding in result.findings:
            mark = "ok  " if finding.passed else ("FAIL" if finding.blocking else "warn")
            print(f"  [{mark}] {finding.check}: {finding.detail}")
        if not result.safe:
            print("\n  Do NOT run `terraform state rm` until the FAIL rows are cleared.")
        print("\n  Rollback to single Terraform ownership:")
        for command in commands:
            print(f"    {command}")

    return 0 if result.safe else 1


if __name__ == "__main__":
    raise SystemExit(main())
