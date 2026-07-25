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

Exit codes: 0 = clean, 1 = orphans found (usable as a CI/cron signal), 2 = usage error.
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


def _run_json(cmd: list[str]) -> object | None:
    """Run a read-only CLI command and parse JSON, or return None on any failure.

    A provider that is not configured must not abort the whole sweep — the other
    providers still need reporting.
    """
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.TimeoutExpired) as exc:
        print(f"WARN: {cmd[0]} failed: {exc}", file=sys.stderr)
        return None
    if proc.returncode != 0:
        print(f"WARN: {' '.join(cmd[:3])} exited {proc.returncode}", file=sys.stderr)
        return None
    try:
        return json.loads(proc.stdout or "null")
    except json.JSONDecodeError:
        print(f"WARN: {' '.join(cmd[:3])} returned non-JSON", file=sys.stderr)
        return None


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
        described = _run_json(
            ["aws", "eks", "describe-cluster", "--name", name, "--region", region]
        ) or {}
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
    for provider in providers:
        clusters.extend(_COLLECTORS[provider]())

    now = datetime.now(timezone.utc)
    findings = find_orphans(
        clusters, now=now, max_age_min=args.max_age_min, protected=args.protect
    )

    if args.json:
        print(json.dumps(
            {
                "swept_at": now.isoformat(),
                "providers": providers,
                "cluster_count": len(clusters),
                "findings": [f.to_dict() for f in findings],
                "delete_commands": delete_commands(findings),
            },
            indent=2,
        ))
    else:
        print(format_report(findings, now=now))
        if findings:
            print("\nSuggested (NOT executed) delete commands:")
            for command in delete_commands(findings):
                print(f"  {command}")

    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
