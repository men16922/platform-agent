"""
Deployment Agent — canary metric comparison helpers.
"""

from __future__ import annotations

from typing import Any


DEFAULT_THRESHOLDS = {
    "error_rate_delta": 0.02,
    "latency_p99_delta_pct": 0.25,
    "success_rate_drop_pct": 0.03,
}


def analyze_canary(
    baseline: dict[str, float],
    candidate: dict[str, float],
    thresholds: dict[str, float] | None = None,
) -> dict[str, Any]:
    thresholds = {**DEFAULT_THRESHOLDS, **(thresholds or {})}

    error_rate_delta = candidate["error_rate"] - baseline["error_rate"]
    latency_delta_pct = _pct_change(baseline["latency_p99_ms"], candidate["latency_p99_ms"])
    success_rate_drop_pct = max(0.0, baseline["success_rate"] - candidate["success_rate"])

    reasons: list[str] = []
    if error_rate_delta > thresholds["error_rate_delta"]:
        reasons.append("error_rate_regression")
    if latency_delta_pct > thresholds["latency_p99_delta_pct"]:
        reasons.append("latency_regression")
    if success_rate_drop_pct > thresholds["success_rate_drop_pct"]:
        reasons.append("success_rate_drop")

    # Flag borderline rollouts for human review before they cross hard rollback
    # thresholds. The 60% mark keeps the signal early enough to be useful
    # without treating minor noise as manual-review material.
    near_threshold = (
        error_rate_delta >= thresholds["error_rate_delta"] * 0.6
        or latency_delta_pct >= thresholds["latency_p99_delta_pct"] * 0.6
        or success_rate_drop_pct >= thresholds["success_rate_drop_pct"] * 0.6
    )

    return {
        "error_rate_delta": round(error_rate_delta, 4),
        "latency_p99_delta_pct": round(latency_delta_pct, 4),
        "success_rate_drop_pct": round(success_rate_drop_pct, 4),
        "rollback_recommended": bool(reasons),
        "needs_human_review": not reasons and near_threshold,
        "reasons": reasons,
    }


def _pct_change(before: float, after: float) -> float:
    if before == 0:
        return 0.0 if after == 0 else 1.0
    return max(0.0, (after - before) / before)
