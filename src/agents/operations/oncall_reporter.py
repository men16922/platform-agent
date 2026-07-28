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

        minutes = _minutes_between(incident.get("started_at"), incident.get("resolved_at"))
        if minutes is not None:
            total_minutes += minutes
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


def _minutes_between(started_at: Any, resolved_at: Any) -> float | None:
    """Minutes from start to resolution, or None when that is not knowable.

    None rather than 0.0, and this is the whole point of the function. A
    zero-minute sample is a *claim* — "we resolved it the instant it fired" —
    and it drags the reported average toward zero, which is precisely the
    failure this and its caller were fixed for. The cases that must not become
    that claim:

      - either side missing        (unresolved incidents have no resolution time)
      - either side unparseable    (four signal adapters feed `triggered_at`
                                    straight from `startsAt`/`firedDateTime`/
                                    `started_at`; format variance is now reachable
                                    live, and it must not crash a weekly report)
      - naive/aware mismatch       (same reason — a TypeError here used to take
                                    the entire report down, not one incident)
      - resolved *before* it fired (clock skew between a spoke and the hub is
                                    normal, and skew is not a fast recovery)
    """
    if not started_at or not resolved_at:
        return None
    try:
        started = _parse_timestamp(started_at)
        resolved = _parse_timestamp(resolved_at)
        minutes = (resolved - started).total_seconds() / 60.0
    except (ValueError, TypeError, AttributeError):
        return None
    return minutes if minutes >= 0 else None


def _parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _top_counts(counts: dict[str, int], limit: int) -> list[dict[str, Any]]:
    items = [{"name": name, "count": count} for name, count in counts.items()]
    items.sort(key=lambda item: (-item["count"], item["name"]))
    return items[:limit]
