"""Sweep for over-budget (orphan) clusters across GCP / AWS / Azure.

Report-only by design. The local watchdog in ``provision_gke_live.py`` protects
the window *after* a cluster is created, but every layer of it dies with the
machine; this sweeper re-derives orphan status from the cloud's own inventory, so
a run days later still reaches the right verdict.

Reads only. It shells out to list/describe verbs (the ones the permission
allowlist keeps un-gated) and prints the delete commands rather than running
them — destructive actions are force-APPROVE by D5.

Usage:
  python scripts/sweep_orphan_clusters.py [--max-age-min 1440] [--provider gcp|aws|azure]
                                          [--protect NAME ...] [--json]

Exit codes:
  0 = every requested provider was inventoried and nothing is over budget
  1 = orphans found (usable as a CI/cron signal)
  2 = coverage incomplete — at least one provider could not be inventoried, so
      "nothing found" cannot be read as "nothing there". Scope the run
      (--provider gcp) when only some clouds are configured.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.agents.operations.orphan_sweeper import (  # noqa: E402
    DEFAULT_MAX_AGE_MIN,
    ClusterRecord,
    delete_commands,
    find_orphans,
    format_report,
)


class ProviderUnavailable(Exception):
    """A provider could not be inventoried at all (CLI missing, unauthenticated, timeout).

    This is NOT the same as "the provider has no clusters", and conflating the
    two is how a sweeper becomes dangerous: a container without `gcloud` would
    inventory nothing, find nothing, and report a green all-clear forever while
    the clusters it was supposed to catch keep billing. Unreachable must be
    louder than empty, not quieter.
    """


def _run_json(cmd: list[str]) -> object | None:
    """Run a read-only CLI command and parse JSON.

    Raises ProviderUnavailable on any failure so the caller can tell "looked and
    saw nothing" apart from "never got to look".
    """
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ProviderUnavailable(f"{cmd[0]} failed: {exc}") from exc
    if proc.returncode != 0:
        detail = (proc.stderr or "").strip().splitlines()
        hint = detail[-1] if detail else f"exited {proc.returncode}"
        raise ProviderUnavailable(f"{' '.join(cmd[:3])}: {hint}")
    try:
        return json.loads(proc.stdout or "null")
    except json.JSONDecodeError as exc:
        raise ProviderUnavailable(f"{' '.join(cmd[:3])} returned non-JSON") from exc


def _parse_ts(raw: object) -> datetime | None:
    if not isinstance(raw, str) or not raw:
        return None
    text = raw.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _gcp_clusters() -> list[ClusterRecord]:
    project = os.getenv("GCP_PROJECT", "")
    cmd = ["gcloud", "container", "clusters", "list", "--format=json"]
    if project:
        cmd.append(f"--project={project}")
    data = _run_json(cmd) or []
    records = []
    for item in data if isinstance(data, list) else []:
        records.append(
            ClusterRecord(
                provider="gcp",
                name=item.get("name", "?"),
                location=item.get("location", "?"),
                created_at=_parse_ts(item.get("createTime")),
                labels=item.get("resourceLabels") or {},
                project=project or None,
            )
        )
    return records


def _aws_clusters() -> list[ClusterRecord]:
    region = os.getenv("AWS_REGION", "ap-northeast-2")
    listing = _run_json(["aws", "eks", "list-clusters", "--region", region]) or {}
    names = listing.get("clusters", []) if isinstance(listing, dict) else []
    records = []
    for name in names:
        # A describe that fails after a successful list (racing deletion, or a
        # per-cluster permission hole) must not discard the cluster — keep it
        # with an unknown creation time, which find_orphans reports rather than
        # skips. Losing the row would be the silent-skip bug one level down.
        try:
            described = _run_json(
                ["aws", "eks", "describe-cluster", "--name", name, "--region", region]
            ) or {}
        except ProviderUnavailable as exc:
            print(f"WARN: eks describe-cluster {name}: {exc}", file=sys.stderr)
            described = {}
        cluster = described.get("cluster", {}) if isinstance(described, dict) else {}
        records.append(
            ClusterRecord(
                provider="aws",
                name=name,
                location=region,
                created_at=_parse_ts(cluster.get("createdAt")),
                labels=cluster.get("tags") or {},
            )
        )
    return records


def _azure_clusters() -> list[ClusterRecord]:
    data = _run_json(["az", "aks", "list", "-o", "json"]) or []
    records = []
    for item in data if isinstance(data, list) else []:
        records.append(
            ClusterRecord(
                provider="azure",
                name=item.get("name", "?"),
                # Delete needs the resource group, so that is the useful "location".
                location=item.get("resourceGroup", "?"),
                created_at=_parse_ts(item.get("systemData", {}).get("createdAt")),
                labels=item.get("tags") or {},
            )
        )
    return records


_COLLECTORS = {"gcp": _gcp_clusters, "aws": _aws_clusters, "azure": _azure_clusters}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-age-min", type=int, default=DEFAULT_MAX_AGE_MIN,
                        help="age budget in minutes (per-cluster `ttl-min` label overrides)")
    parser.add_argument("--provider", action="append", choices=sorted(_COLLECTORS),
                        help="limit the sweep (default: all three)")
    parser.add_argument("--protect", action="append", default=[],
                        help="cluster name to never report (exact match, repeatable)")
    parser.add_argument("--json", action="store_true", help="emit findings as JSON")
    args = parser.parse_args()

    providers = args.provider or sorted(_COLLECTORS)
    clusters: list[ClusterRecord] = []
    swept: list[str] = []
    unswept: dict[str, str] = {}
    for provider in providers:
        try:
            clusters.extend(_COLLECTORS[provider]())
        except ProviderUnavailable as exc:
            unswept[provider] = str(exc)
            print(f"WARN: {provider} not swept — {exc}", file=sys.stderr)
        else:
            swept.append(provider)

    now = datetime.now(timezone.utc)
    findings = find_orphans(
        clusters, now=now, max_age_min=args.max_age_min, protected=args.protect
    )

    if args.json:
        print(json.dumps(
            {
                "swept_at": now.isoformat(),
                "providers": providers,
                "swept": swept,
                "unswept": unswept,
                "cluster_count": len(clusters),
                "findings": [f.to_dict() for f in findings],
                "delete_commands": delete_commands(findings),
            },
            indent=2,
        ))
    else:
        print(format_report(findings, now=now))
        if unswept:
            print(
                f"\nCOVERAGE INCOMPLETE — {len(unswept)} of {len(providers)} provider(s) "
                "were not inventoried. This report cannot mean 'clean':"
            )
            for provider, reason in unswept.items():
                print(f"  - {provider}: {reason}")
        if findings:
            print("\nSuggested (NOT executed) delete commands:")
            for command in delete_commands(findings):
                print(f"  {command}")

    if findings:
        return 1
    # No findings, but we did not look everywhere we were asked to. Saying 0
    # here is the whole failure mode this guards against. Scope the run
    # (--provider gcp) to get a green that actually means something.
    return 2 if unswept else 0


if __name__ == "__main__":
    raise SystemExit(main())
