"""
Provisioning Agent — heuristic monthly cost estimation.

This is intentionally a rough planning aid. It does not attempt to mirror live
AWS pricing, which should be sourced separately during real rollout reviews.
"""

from __future__ import annotations

from typing import Any


def estimate_monthly_cost(request: dict[str, Any]) -> dict[str, Any]:
    platform = request.get("platform", "eks").strip().lower()

    if platform == "eks":
        cpu = float(request.get("cpu", 512)) / 1024.0
        memory = float(request.get("memory", 1024)) / 1024.0
        desired_count = int(request.get("desired_count", 2))
        compute = round(desired_count * ((cpu * 18) + (memory * 7)), 2)
        networking = 25.0 if request.get("exposure", "internal") == "public" else 12.0
    elif platform == "lambda":
        monthly_invocations = int(request.get("monthly_invocations", 1_000_000))
        avg_duration_ms = int(request.get("avg_duration_ms", 250))
        memory_mb = int(request.get("memory", 512))
        compute = round((monthly_invocations / 1_000_000) * (memory_mb / 512) * (avg_duration_ms / 250) * 4.5, 2)
        networking = 5.0 if request.get("exposure", "internal") == "public" else 0.0
    else:
        raise ValueError(f"Unsupported platform: {platform}")

    observability = 18.0
    total = round(compute + networking + observability, 2)
    return {
        "currency": "USD",
        "monthly_total_usd": total,
        "breakdown": {
            "compute": compute,
            "networking": networking,
            "observability": observability,
        },
        "assumptions": [
            "Estimate is heuristic and meant for early planning, not approval-grade pricing.",
            "Observability includes CloudWatch logs, metrics, and alarm overhead.",
        ],
    }
