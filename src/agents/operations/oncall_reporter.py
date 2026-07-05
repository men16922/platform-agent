"""
Operations Agent — weekly on-call reporting helpers.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any


def summarize_incidents(incidents: list[dict[str, Any]]) -> dict[str, Any]:
    severity_counts = {"P1": 0, "P2": 0, "P3": 0}
    total_minutes = 0.0
    mttr_samples = 0
    service_counts: dict[str, int] = {}

    for incident in incidents:
        severity = incident.get("severity", "P3")
        severity_counts[severity] = severity_counts.get(severity, 0) + 1

        service = incident.get("service_name", "unknown")
        service_counts[service] = service_counts.get(service, 0) + 1

        started_at = incident.get("started_at")
        resolved_at = incident.get("resolved_at")
        if started_at and resolved_at:
            total_minutes += _minutes_between(started_at, resolved_at)
            mttr_samples += 1

    return {
        "total_incidents": len(incidents),
        "severity_counts": severity_counts,
        "average_mttr_minutes": round((total_minutes / mttr_samples) if mttr_samples else 0.0, 2),
        "top_services": _top_counts(service_counts, limit=3),
        "recurring_patterns": find_recurring_patterns(incidents),
    }


def find_recurring_patterns(
    incidents: list[dict[str, Any]],
    *,
    min_occurrences: int = 2,
) -> list[dict[str, Any]]:
    counts: dict[str, int] = {}
    for incident in incidents:
        pattern = (
            incident.get("pattern_key")
            or incident.get("runbook_id")
            or incident.get("alarm_name")
            or incident.get("root_cause")
            or "unknown"
        )
        counts[pattern] = counts.get(pattern, 0) + 1

    recurring = [
        {"pattern": pattern, "count": count}
        for pattern, count in counts.items()
        if count >= min_occurrences
    ]
    recurring.sort(key=lambda item: (-item["count"], item["pattern"]))
    return recurring


def build_weekly_oncall_report(
    current_incidents: list[dict[str, Any]],
    previous_incidents: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    current = summarize_incidents(current_incidents)
    previous = summarize_incidents(previous_incidents or [])

    return {
        "report_type": "weekly_oncall",
        "current": current,
        "previous": previous,
        "trend": {
            "incident_delta": current["total_incidents"] - previous["total_incidents"],
            "mttr_delta_minutes": round(
                current["average_mttr_minutes"] - previous["average_mttr_minutes"],
                2,
            ),
        },
    }


def _minutes_between(started_at: str, resolved_at: str) -> float:
    started = _parse_timestamp(started_at)
    resolved = _parse_timestamp(resolved_at)
    return max(0.0, (resolved - started).total_seconds() / 60.0)


def _parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _top_counts(counts: dict[str, int], limit: int) -> list[dict[str, Any]]:
    items = [{"name": name, "count": count} for name, count in counts.items()]
    items.sort(key=lambda item: (-item["count"], item["name"]))
    return items[:limit]
