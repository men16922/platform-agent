"""
Orphan cluster sweeper — the cost guard the local watchdog cannot be.

`scripts/provision_gke_live.py` arms three teardown layers, but every one of them
runs *on this machine*: try/finally, signal handlers, and a detached watchdog
process. They all die with the machine. The 2026-06/07 incidents were caught by
none of them for that reason — a laptop that sleeps, loses power, or is closed
mid-run leaves a billing cluster with nothing left to delete it.

This module closes that hole from the other side: instead of trusting a process to
survive, it **re-derives orphan status from the cloud's own inventory** every time
it runs. Age comes from the provider's creation timestamp, so a sweep run days
later still reaches the correct verdict.

Deliberately **report-only by default**. Deleting a cluster is irreversible and
`Delete/Drop/Terminate` is force-APPROVE by D5, so the sweeper's job is to make
orphans impossible to *miss*, not to unilaterally remove them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

# Anything a live test creates is expected to be short-lived; a day is generous
# relative to the 30-minute watchdog TTL and still catches "left up overnight".
DEFAULT_MAX_AGE_MIN = 1440

# Clusters that are meant to persist. Matched exactly, never by prefix, so a
# typo'd name is reported rather than silently treated as protected.
DEFAULT_PROTECTED: frozenset[str] = frozenset()


@dataclass(frozen=True)
class ClusterRecord:
    """One cluster as the provider reports it."""

    provider: str
    name: str
    location: str
    created_at: datetime | None
    # Provider labels/tags — used to spot live-test clusters and TTL intent.
    labels: dict[str, str] = field(default_factory=dict)
    project: str | None = None

    def age(self, *, now: datetime) -> timedelta | None:
        if self.created_at is None:
            return None
        created = self.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        return now - created


@dataclass(frozen=True)
class OrphanFinding:
    cluster: ClusterRecord
    age_min: int | None
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.cluster.provider,
            "name": self.cluster.name,
            "location": self.cluster.location,
            "project": self.cluster.project,
            "age_min": self.age_min,
            "reason": self.reason,
        }


def _ttl_from_labels(labels: dict[str, str]) -> int | None:
    """
    Per-cluster TTL override from a label (e.g. ``ttl-min=120``).

    Lets a deliberately longer-lived test cluster declare its own budget instead
    of forcing the global default up for everything.
    """
    for key in ("ttl-min", "ttl_min", "ttlminutes"):
        raw = labels.get(key)
        if raw is None:
            continue
        try:
            value = int(raw)
        except (TypeError, ValueError):
            return None
        return value if value > 0 else None
    return None


def find_orphans(
    clusters: Iterable[ClusterRecord],
    *,
    now: datetime,
    max_age_min: int = DEFAULT_MAX_AGE_MIN,
    protected: Iterable[str] = DEFAULT_PROTECTED,
) -> list[OrphanFinding]:
    """
    Report clusters that have outlived their budget, worst (oldest) first.

    Two non-obvious rules, both chosen to fail toward *reporting*:

    * **Unknown age is reported, not skipped.** A cluster whose creation time we
      cannot read is exactly the case where a silent skip costs money.
    * **Protected names must match exactly.** Prefix matching would let
      ``pa-gke-live-2`` inherit protection from ``pa-gke-live``.
    """
    protected_set = set(protected)
    findings: list[OrphanFinding] = []

    for cluster in clusters:
        if cluster.name in protected_set:
            continue

        budget = _ttl_from_labels(cluster.labels) or max_age_min
        age = cluster.age(now=now)

        if age is None:
            findings.append(
                OrphanFinding(
                    cluster=cluster,
                    age_min=None,
                    reason="creation time unknown — cannot prove it is within budget",
                )
            )
            continue

        age_min = int(age.total_seconds() // 60)
        if age_min > budget:
            findings.append(
                OrphanFinding(
                    cluster=cluster,
                    age_min=age_min,
                    reason=f"age {age_min}min exceeds {budget}min budget",
                )
            )

    # Unknown age sorts first: it is the least provable and the most urgent.
    return sorted(findings, key=lambda f: (f.age_min is not None, -(f.age_min or 0)))


def format_report(findings: list[OrphanFinding], *, now: datetime) -> str:
    """Human-readable sweep report (stdout / Slack / CI log)."""
    stamp = now.replace(microsecond=0).isoformat()
    if not findings:
        return f"[orphan-sweep {stamp}] no clusters over budget."

    lines = [f"[orphan-sweep {stamp}] {len(findings)} cluster(s) over budget:"]
    for finding in findings:
        cluster = finding.cluster
        where = f"{cluster.provider}/{cluster.location}"
        if cluster.project:
            where += f" ({cluster.project})"
        lines.append(f"  - {cluster.name} [{where}] — {finding.reason}")
    lines.append(
        "  Deletion is NOT automatic: destructive actions are approval-gated (D5). "
        "Re-run with --delete to be prompted per cluster."
    )
    return "\n".join(lines)


def delete_commands(findings: list[OrphanFinding]) -> list[str]:
    """
    The exact per-provider delete command for each finding.

    Emitted as text rather than executed so a human reviews the blast radius
    first — and so the sweeper needs no delete permissions of its own.
    """
    commands: list[str] = []
    for finding in findings:
        cluster = finding.cluster
        if cluster.provider == "gcp":
            project = f" --project {cluster.project}" if cluster.project else ""
            commands.append(
                f"gcloud container clusters delete {cluster.name}"
                f"{project} --region {cluster.location} --quiet"
            )
        elif cluster.provider == "aws":
            commands.append(
                f"aws eks delete-cluster --name {cluster.name} --region {cluster.location}"
            )
        elif cluster.provider == "azure":
            commands.append(
                f"az aks delete --name {cluster.name} --resource-group {cluster.location} --yes"
            )
        else:
            commands.append(f"# no delete command known for provider {cluster.provider!r}")
    return commands
