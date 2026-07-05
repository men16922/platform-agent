"""
Deployment Validation Agent — Lambda handler.

Triggered by:
  Step Functions after a CDK deploy completes (post-deploy hook).

Responsibilities:
  1. Run smoke tests against the new deployment (health + core endpoints)
  2. Compare canary metrics vs baseline (error rate, latency p99, success rate)
  3. Decide rollout action: KEEP_ROLLOUT | REQUEST_APPROVAL | ROLLBACK
  4. Post a Slack report with deployment health summary
  5. Preserve rollback execution hints for the executor stage
  6. Return DeploymentOutput for Step Functions routing

Step Functions flow:
  SmokeTest → CanaryAnalysis → RolloutDecision → [ApprovalGate |] Notify
"""

from __future__ import annotations

import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

import boto3
import requests
import structlog

from src.agents.adapters.slack_client import post_webhook
from src.agents.deployment.canary_analyzer import analyze_canary
from src.agents.deployment.rollback_decider import (
    KEEP_ROLLOUT,
    REQUEST_APPROVAL,
    ROLLBACK,
    decide_rollout_action,
)
from src.agents.deployment.smoke_tester import build_smoke_test_plan, summarise_smoke_results

logger = structlog.get_logger(__name__)

_REGION        = os.getenv("AWS_REGION", "ap-northeast-2")
_SLACK_WEBHOOK = os.getenv("SLACK_WEBHOOK_URL", "")
_CW_CLIENT     = boto3.client("cloudwatch", region_name=_REGION)
_SMOKE_TIMEOUT = int(os.getenv("SMOKE_TEST_TIMEOUT_SEC", "10"))


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """
    Entry point.

    Input event shape:
    {
        "deployment_id":  "deploy-abc123",
        "service_name":   "orders-api",
        "version":        "v1.4.2",
        "base_url":       "https://orders-api.internal",
        "health_path":    "/healthz",       # optional, default /healthz
        "core_endpoints": [                 # optional
            {"name": "list_orders", "path": "/orders", "method": "GET"}
        ],
        "baseline_metrics": {               # optional, from previous deploy
            "error_rate": 0.005,
            "latency_p99_ms": 120.0,
            "success_rate": 0.995
        },
        "canary_metrics": {                 # required for canary analysis
            "error_rate": 0.008,
            "latency_p99_ms": 130.0,
            "success_rate": 0.992
        },
        "canary_thresholds": {...}          # optional override
    }
    """
    deployment_id = event.get("deployment_id", f"deploy-{int(time.time())}")
    service_name  = event.get("service_name", "unknown")
    version       = event.get("version", "unknown")

    log = logger.bind(deployment_id=deployment_id, service=service_name, version=version)
    log.info("deployment.validation.start")

    smoke_plan    = build_smoke_test_plan(event)
    smoke_results = _run_smoke_tests(smoke_plan["checks"])
    smoke_summary = summarise_smoke_results(smoke_results)
    log.info("deployment.smoke_done", passed=smoke_summary["passed"], failed=smoke_summary["failed"])

    baseline = event.get("baseline_metrics")
    canary   = event.get("canary_metrics")
    canary_analysis: dict[str, Any] = {}
    if baseline and canary:
        canary_analysis = analyze_canary(
            baseline,
            canary,
            thresholds=event.get("canary_thresholds"),
        )
        log.info(
            "deployment.canary_done",
            rollback=canary_analysis.get("rollback_recommended"),
            review=canary_analysis.get("needs_human_review"),
        )

    # Smoke failure overrides canary: always rollback if health checks fail.
    if not smoke_summary["should_continue"]:
        rollout_decision = {
            "action": ROLLBACK,
            "reason": f"smoke_test_failed: {smoke_summary['failed_checks']}",
        }
    elif canary_analysis:
        rollout_decision = decide_rollout_action(canary_analysis)
    else:
        rollout_decision = {"action": KEEP_ROLLOUT, "reason": "no_canary_data_available"}

    needs_approval = rollout_decision["action"] == REQUEST_APPROVAL
    log.info("deployment.decision", action=rollout_decision["action"])

    _post_slack_report(
        deployment_id=deployment_id,
        service_name=service_name,
        version=version,
        smoke_summary=smoke_summary,
        canary_analysis=canary_analysis,
        rollout_decision=rollout_decision,
    )

    output = {
        "deployment_id":    deployment_id,
        "service_name":     service_name,
        "version":          version,
        "smoke_summary":    smoke_summary,
        "canary_analysis":  canary_analysis,
        "rollout_action":   rollout_decision["action"],
        "rollout_reason":   rollout_decision["reason"],
        "needs_approval":   needs_approval,
        "execution_context": _execution_context(event),
    }

    log.info("deployment.validation.done", action=rollout_decision["action"])
    return output


def _execution_context(event: dict[str, Any]) -> dict[str, Any]:
    """Pass through only the fields the rollback executor may need later."""

    keys = [
        "platform",
        "deployment_environment",
        "cluster_name",
        "namespace",
        "workload_name",
        "function_name",
        "alias_name",
        "rollback_document_name",
        "rollback_target_version",
        "rollback_parameters",
        "rollback_context",
        "stable_version",
        "previous_version",
    ]
    return {key: event[key] for key in keys if key in event}


def _run_smoke_tests(checks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Execute HTTP checks concurrently. Returns results with status=passed|failed."""

    def _run_one(check: dict[str, Any]) -> dict[str, Any]:
        try:
            resp = requests.request(
                method  = check.get("method", "GET"),
                url     = check["url"],
                timeout = _SMOKE_TIMEOUT,
            )
            return {
                "name":        check["name"],
                "url":         check["url"],
                "status":      "passed" if resp.status_code < 400 else "failed",
                "status_code": resp.status_code,
            }
        except Exception as exc:
            return {"name": check["name"], "url": check["url"], "status": "failed", "error": str(exc)}

    if not checks:
        return []
    with ThreadPoolExecutor(max_workers=min(len(checks), 10)) as pool:
        futures = {pool.submit(_run_one, c): c for c in checks}
        return [f.result() for f in as_completed(futures)]


_ACTION_COLOR = {
    KEEP_ROLLOUT:     "#2ECC71",
    REQUEST_APPROVAL: "#F39C12",
    ROLLBACK:         "#E74C3C",
}
_ACTION_EMOJI = {
    KEEP_ROLLOUT:     ":white_check_mark:",
    REQUEST_APPROVAL: ":warning:",
    ROLLBACK:         ":rotating_light:",
}


def _post_slack_report(
    deployment_id: str,
    service_name: str,
    version: str,
    smoke_summary: dict[str, Any],
    canary_analysis: dict[str, Any],
    rollout_decision: dict[str, str],
) -> None:
    if not _SLACK_WEBHOOK:
        logger.warning("deployment.slack.skip", reason="SLACK_WEBHOOK_URL not set")
        return

    action = rollout_decision["action"]
    color  = _ACTION_COLOR.get(action, "#95A5A6")
    emoji  = _ACTION_EMOJI.get(action, ":grey_question:")

    smoke_text = (
        f"✅ {smoke_summary['passed']} passed"
        if smoke_summary["should_continue"]
        else f"❌ {smoke_summary['failed']} failed: {smoke_summary['failed_checks']}"
    )

    canary_text = "No canary data"
    if canary_analysis:
        canary_text = (
            f"Error rate Δ: {canary_analysis['error_rate_delta']:.2%}  |  "
            f"Latency p99 Δ: {canary_analysis['latency_p99_delta_pct']:.1%}  |  "
            f"Success rate drop: {canary_analysis['success_rate_drop_pct']:.2%}"
        )

    payload = {
        "attachments": [{
            "color": color,
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": f"{emoji} Deploy Validation: {service_name} {version}",
                    },
                },
                {
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": f"*Deploy ID:*\n`{deployment_id}`"},
                        {"type": "mrkdwn", "text": f"*Decision:*\n`{action}`"},
                        {"type": "mrkdwn", "text": f"*Reason:*\n{rollout_decision['reason']}"},
                    ],
                },
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": f"*Smoke Tests:*\n{smoke_text}"},
                },
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": f"*Canary Metrics:*\n{canary_text}"},
                },
            ],
        }]
    }

    try:
        post_webhook(_SLACK_WEBHOOK, payload)
        logger.info("deployment.slack.sent", deployment_id=deployment_id)
    except Exception as exc:
        logger.error("deployment.slack.error", error=str(exc))
