"""
Deployment Agent — rollout decision helper.
"""

from __future__ import annotations

from typing import Any

ROLLBACK         = "ROLLBACK"
REQUEST_APPROVAL = "REQUEST_APPROVAL"
KEEP_ROLLOUT     = "KEEP_ROLLOUT"


def decide_rollout_action(canary_analysis: dict[str, Any]) -> dict[str, str]:
    if canary_analysis.get("rollback_recommended"):
        return {
            "action": ROLLBACK,
            "reason": ",".join(canary_analysis.get("reasons", [])) or "canary_regression",
        }
    if canary_analysis.get("needs_human_review"):
        return {
            "action": REQUEST_APPROVAL,
            "reason": "near_threshold_regression",
        }
    return {
        "action": KEEP_ROLLOUT,
        "reason": "canary_healthy",
    }
