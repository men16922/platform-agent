"""
Operations Agent — daily SLO reporting helpers.
"""

from __future__ import annotations

from typing import Any


def calculate_service_slo(
    service_name: str,
    *,
    total_requests: int,
    failed_requests: int,
    slo_target: float = 0.999,
    window_hours: int = 24,
) -> dict[str, Any]:
    """
    Calculate a daily SLO summary for a single service.
    """
    if total_requests < 0 or failed_requests < 0:
        raise ValueError("Request counts must be non-negative")
    if failed_requests > total_requests:
        raise ValueError("failed_requests cannot exceed total_requests")
    if not 0 < slo_target < 1:
        raise ValueError("slo_target must be between 0 and 1")

    error_budget = 1.0 - slo_target
    observed_error_rate = (failed_requests / total_requests) if total_requests else 0.0
    success_rate = 1.0 - observed_error_rate
    burn_rate = (observed_error_rate / error_budget) if error_budget else 0.0
    consumed_error_budget_pct = min(1.0, burn_rate)
    remaining_error_budget_pct = max(0.0, 1.0 - consumed_error_budget_pct)

    return {
        "service_name": service_name,
        "window_hours": window_hours,
        "slo_target": round(slo_target, 6),
        "total_requests": total_requests,
        "failed_requests": failed_requests,
        "success_rate": round(success_rate, 6),
        "observed_error_rate": round(observed_error_rate, 6),
        "burn_rate": round(burn_rate, 4),
        "consumed_error_budget_pct": round(consumed_error_budget_pct, 4),
        "remaining_error_budget_pct": round(remaining_error_budget_pct, 4),
        "status": _classify_burn_rate(burn_rate),
    }


def rank_services_by_burn_rate(service_summaries: list[dict[str, Any]], limit: int = 3) -> list[dict[str, Any]]:
    ranked = sorted(
        service_summaries,
        key=lambda summary: (
            summary.get("burn_rate", 0.0),
            summary.get("observed_error_rate", 0.0),
        ),
        reverse=True,
    )
    return ranked[:limit]


def build_daily_slo_report(service_summaries: list[dict[str, Any]]) -> dict[str, Any]:
    top_unstable = rank_services_by_burn_rate(service_summaries, limit=3)
    status_counts = {"healthy": 0, "warning": 0, "critical": 0}
    for summary in service_summaries:
        status_counts[summary["status"]] += 1

    return {
        "report_type": "daily_slo",
        "service_count": len(service_summaries),
        "status_counts": status_counts,
        "top_unstable_services": [summary["service_name"] for summary in top_unstable],
        "services": service_summaries,
    }


def _classify_burn_rate(burn_rate: float) -> str:
    if burn_rate >= 1.0:
        return "critical"
    if burn_rate >= 0.5:
        return "warning"
    return "healthy"
