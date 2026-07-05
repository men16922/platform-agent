"""
Provisioning Agent — Lambda handler.

Triggered by:
  EventBridge rule (Slack/Jira/GitHub service provisioning request)

Responsibilities:
  1. Normalise the provisioning request into a CDK service blueprint
  2. Build a least-privilege IAM role plan
  3. Estimate monthly AWS cost
  4. Store the plan in DynamoDB (provisioning-plans table)
  5. Post a Slack summary with Approve / Reject buttons
  6. Return ProvisioningOutput for the Step Functions Approval gate

Step Functions flow:
  GeneratePlan → CheckCostThreshold → [RequestApproval →] PublishArtifact → NotifyComplete
"""

from __future__ import annotations

import json
import os
import time
import uuid
from typing import Any

import boto3
import structlog

from src.agents.adapters.slack_client import post_webhook

from src.agents.provisioning.cdk_generator import build_service_blueprint
from src.agents.provisioning.cdk_emitter import build_cdk_artifact
from src.agents.provisioning.cost_estimator import estimate_monthly_cost
from src.agents.provisioning.iam_designer import build_iam_plan

logger = structlog.get_logger(__name__)

_REGION            = os.getenv("AWS_REGION", "ap-northeast-2")
_SLACK_WEBHOOK     = os.getenv("SLACK_WEBHOOK_URL", "")
_PLAN_TABLE        = os.getenv("PROVISIONING_TABLE", "provisioning-plans")
_COST_AUTO_LIMIT   = float(os.getenv("PROVISIONING_COST_AUTO_LIMIT_USD", "200"))

_DYNAMO = boto3.resource("dynamodb", region_name=_REGION)


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """
    Entry point.

    Input event shape:
    {
        "service_name": "orders-api",
        "platform": "eks|lambda",
        "exposure": "internal|public",
        "requester": "eng-alice",
        "integrations": ["dynamodb_rw", "sqs_producer"],
        "desired_count": 2,          # optional
        "cpu": 512,                  # optional
        "memory": 1024,              # optional
        "monthly_invocations": ...,  # optional, Lambda only
    }
    """
    log = logger.bind(service_name=event.get("service_name", "unknown"))
    log.info("provisioning.start")

    plan_id = f"PLAN-{uuid.uuid4().hex[:8].upper()}"

    blueprint = build_service_blueprint(event)
    iam_plan  = build_iam_plan(
        blueprint["service_name"],
        dependencies=blueprint.get("integrations", []),
    )
    cdk_artifact = build_cdk_artifact(blueprint, iam_plan)
    cost_estimate = estimate_monthly_cost({**event, "platform": blueprint["platform"]})

    log.info(
        "provisioning.plan_generated",
        plan_id=plan_id,
        platform=blueprint["platform"],
        monthly_cost_usd=cost_estimate["monthly_total_usd"],
    )

    _store_plan(plan_id, blueprint, iam_plan, cdk_artifact, cost_estimate, event)
    _post_slack_summary(plan_id, blueprint, iam_plan, cost_estimate, event)

    needs_approval = (
        cost_estimate["monthly_total_usd"] > _COST_AUTO_LIMIT
        or blueprint.get("network", {}).get("exposure") == "public"
        or event.get("force_approval", False)
    )

    output = {
        "plan_id": plan_id,
        "blueprint": blueprint,
        "iam_plan": iam_plan,
        "cdk_artifact": cdk_artifact,
        "cost_estimate": cost_estimate,
        "needs_approval": needs_approval,
        "status": "pending_approval" if needs_approval else "approved",
        "requester": event.get("requester", "unknown"),
    }

    log.info("provisioning.done", plan_id=plan_id, needs_approval=needs_approval)
    return output


# ------------------------------------------------------------------
# DynamoDB persistence
# ------------------------------------------------------------------

def _store_plan(
    plan_id: str,
    blueprint: dict[str, Any],
    iam_plan: dict[str, Any],
    cdk_artifact: dict[str, Any],
    cost_estimate: dict[str, Any],
    request: dict[str, Any],
) -> None:
    try:
        table = _DYNAMO.Table(_PLAN_TABLE)
        table.put_item(Item={
            "plan_id":      plan_id,
            "service_name": blueprint["service_name"],
            "platform":     blueprint["platform"],
            "status":       "pending",
            "blueprint":    json.dumps(blueprint),
            "iam_plan":     json.dumps(iam_plan),
            "cdk_artifact": json.dumps(cdk_artifact),
            "cost_estimate": json.dumps(cost_estimate),
            "requester":    request.get("requester", "unknown"),
            "created_at":   time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "ttl":          int(time.time()) + 30 * 86400,  # 30-day retention
        })
        logger.info("provisioning.plan_stored", plan_id=plan_id)
    except Exception as exc:
        logger.error("provisioning.dynamo.error", plan_id=plan_id, error=str(exc))


# ------------------------------------------------------------------
# Slack notification
# ------------------------------------------------------------------

def _post_slack_summary(
    plan_id: str,
    blueprint: dict[str, Any],
    iam_plan: dict[str, Any],
    cost_estimate: dict[str, Any],
    request: dict[str, Any],
) -> None:
    if not _SLACK_WEBHOOK:
        logger.warning("provisioning.slack.skip", reason="SLACK_WEBHOOK_URL not set")
        return

    service    = blueprint["service_name"]
    platform   = blueprint["platform"].upper()
    exposure   = blueprint["network"]["exposure"]
    monthly    = cost_estimate["monthly_total_usd"]
    requester  = request.get("requester", "unknown")
    compute    = cost_estimate["breakdown"]["compute"]
    networking = cost_estimate["breakdown"]["networking"]
    observability = cost_estimate["breakdown"]["observability"]
    roles      = len(iam_plan["inline_statements"])

    payload = {
        "attachments": [{
            "color": "#3498DB",
            "blocks": [
                {
                    "type": "header",
                    "text": {"type": "plain_text", "text": f":hammer_and_wrench: New Service Request: {service}"},
                },
                {
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": f"*Plan ID:*\n`{plan_id}`"},
                        {"type": "mrkdwn", "text": f"*Requester:*\n{requester}"},
                        {"type": "mrkdwn", "text": f"*Platform:*\n{platform}"},
                        {"type": "mrkdwn", "text": f"*Exposure:*\n{exposure}"},
                    ],
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": (
                            f"*Estimated Monthly Cost:* ${monthly:.2f}/mo\n"
                            f"  Compute: ${compute:.2f}  |  Networking: ${networking:.2f}  "
                            f"|  Observability: ${observability:.2f}"
                        ),
                    },
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": (
                            f"*IAM Plan:* {roles} least-privilege statement(s)\n"
                            f"*Guardrails:* {', '.join(blueprint.get('guardrails', []))}"
                        ),
                    },
                },
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": (
                                "_This plan is pending Approval Gate in Step Functions. "
                                "Cost estimates are heuristic — review before deployment._"
                            ),
                        }
                    ],
                },
            ],
        }]
    }

    try:
        post_webhook(_SLACK_WEBHOOK, payload)
        logger.info("provisioning.slack.sent", plan_id=plan_id)
    except Exception as exc:
        logger.error("provisioning.slack.error", plan_id=plan_id, error=str(exc))
