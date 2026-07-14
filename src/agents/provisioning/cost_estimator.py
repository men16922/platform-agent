"""
Provisioning Agent — heuristic monthly cost estimation.

This is intentionally a rough planning aid. It does not attempt to mirror live
AWS pricing, which should be sourced separately during real rollout reviews.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

# Budget-gate levels (ref: AWSome AI Gateway HARD_BLOCK / SOFT_WARNING / THROTTLE).
BUDGET_OK = "OK"
BUDGET_SOFT_WARNING = "SOFT_WARNING"
BUDGET_THROTTLE = "THROTTLE"
BUDGET_HARD_BLOCK = "HARD_BLOCK"


@dataclass
class BudgetGate:
    """Cost-governance verdict for a provision/deploy request.

    Maps a monthly-cost estimate against a budget into an escalating gate:
      OK            (< warn)          → auto-allowed
      SOFT_WARNING  (warn..throttle)  → allowed, surface a warning
      THROTTLE      (throttle..block) → allowed only with human approval
      HARD_BLOCK    (>= block)        → blocked
    """

    level: str
    allowed: bool
    require_approval: bool
    reason: str
    estimate_usd: float
    budget_usd: float
    ratio: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "level": self.level,
            "allowed": self.allowed,
            "require_approval": self.require_approval,
            "reason": self.reason,
            "estimate_usd": self.estimate_usd,
            "budget_usd": self.budget_usd,
            "ratio": round(self.ratio, 3),
        }


def evaluate_budget(
    estimate_usd: float,
    budget_usd: float | None = None,
    *,
    warn_ratio: float = 0.8,
    throttle_ratio: float = 1.0,
    block_ratio: float = 1.5,
) -> BudgetGate:
    """Gate a cost estimate against a monthly budget (3-level, ref AWSome AI Gateway).

    ``budget_usd`` falls back to the ``PLATFORM_MONTHLY_BUDGET_USD`` env var; when
    no budget is configured the gate is OK (governance disabled, never blocks).
    """
    if budget_usd is None:
        env = os.getenv("PLATFORM_MONTHLY_BUDGET_USD", "")
        budget_usd = float(env) if env else 0.0

    if not budget_usd or budget_usd <= 0:
        return BudgetGate(BUDGET_OK, True, False, "no budget configured", estimate_usd, budget_usd or 0.0, 0.0)

    ratio = estimate_usd / budget_usd
    if ratio >= block_ratio:
        return BudgetGate(
            BUDGET_HARD_BLOCK, False, False,
            f"estimate ${estimate_usd:.2f} is {ratio:.0%} of ${budget_usd:.2f} budget (>= {block_ratio:.0%} hard cap)",
            estimate_usd, budget_usd, ratio,
        )
    if ratio >= throttle_ratio:
        return BudgetGate(
            BUDGET_THROTTLE, True, True,
            f"estimate ${estimate_usd:.2f} exceeds ${budget_usd:.2f} budget ({ratio:.0%}) — requires approval",
            estimate_usd, budget_usd, ratio,
        )
    if ratio >= warn_ratio:
        return BudgetGate(
            BUDGET_SOFT_WARNING, True, False,
            f"estimate ${estimate_usd:.2f} is {ratio:.0%} of ${budget_usd:.2f} budget (nearing cap)",
            estimate_usd, budget_usd, ratio,
        )
    return BudgetGate(
        BUDGET_OK, True, False,
        f"estimate ${estimate_usd:.2f} is {ratio:.0%} of ${budget_usd:.2f} budget",
        estimate_usd, budget_usd, ratio,
    )


def gate_provision_cost(request: dict[str, Any], budget_usd: float | None = None, **kwargs: Any) -> dict[str, Any]:
    """Estimate a request's monthly cost and gate it against the budget in one call."""
    estimate = estimate_monthly_cost(request)
    gate = evaluate_budget(estimate["monthly_total_usd"], budget_usd, **kwargs)
    return {"estimate": estimate, "budget_gate": gate.to_dict()}


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
