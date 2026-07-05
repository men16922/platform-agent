"""
Runtime Router Agent — Lambda handler.

Triggered by:
  EventBridge custom events normalized from Slack / Jira / GitHub integrations

Responsibilities:
  1. Inspect the inbound EventBridge envelope
  2. Route the request to the appropriate Step Functions pipeline
  3. Start execution with the normalized request detail as state input

Supported EventBridge shapes:
  {
      "source": "platform-agent",
      "detail-type": "Provisioning Request",
      "detail": { ... provisioning request ... }
  }

  {
      "source": "platform-agent",
      "detail-type": "Deployment Validation Request",
      "detail": { ... deployment validation request ... }
  }

The router also accepts `detail.pipeline` values such as `provisioning`,
`deployment`, or `deployment_validation` to support upstream adapters that
normalize events before publishing them onto EventBridge.
"""

from __future__ import annotations

import json
import os
import re
import uuid
from typing import Any

import boto3
import structlog

logger = structlog.get_logger(__name__)

_REGION = os.getenv("AWS_REGION", "ap-northeast-2")
_PROVISIONING_STATE_MACHINE_ARN = os.getenv("PROVISIONING_STATE_MACHINE_ARN", "")
_DEPLOYMENT_STATE_MACHINE_ARN = os.getenv("DEPLOYMENT_STATE_MACHINE_ARN", "")

_SFN = boto3.client("stepfunctions", region_name=_REGION)


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    route = _route_name(event)
    payload = _event_payload(event)
    state_machine_arn = _state_machine_arn(route)
    execution_name = _execution_name(route, event, payload)

    logger.info(
        "router.start",
        route=route,
        execution_name=execution_name,
        source=event.get("source", ""),
        detail_type=event.get("detail-type", event.get("detailType", "")),
    )

    response = _SFN.start_execution(
        stateMachineArn=state_machine_arn,
        name=execution_name,
        input=json.dumps(payload),
    )

    logger.info("router.done", route=route, execution_arn=response["executionArn"])
    return {
        "route": route,
        "state_machine_arn": state_machine_arn,
        "execution_arn": response["executionArn"],
        "execution_name": execution_name,
    }


def _route_name(event: dict[str, Any]) -> str:
    detail = event.get("detail", {})
    if isinstance(detail, dict):
        pipeline = str(detail.get("pipeline", "")).strip().lower()
        if pipeline in {"provisioning", "provision"}:
            return "provisioning"
        if pipeline in {"deployment", "deployment_validation", "validate_deployment"}:
            return "deployment"

    detail_type = str(event.get("detail-type", event.get("detailType", ""))).strip().lower()
    if "provision" in detail_type:
        return "provisioning"
    if "deployment" in detail_type or "rollout" in detail_type:
        return "deployment"

    raise ValueError("Unsupported router event: expected provisioning or deployment request")


def _event_payload(event: dict[str, Any]) -> dict[str, Any]:
    detail = event.get("detail")
    if isinstance(detail, dict):
        return detail
    if "detail" not in event and isinstance(event, dict):
        return event
    raise ValueError("Router event detail must be a JSON object")


def _state_machine_arn(route: str) -> str:
    mapping = {
        "provisioning": _PROVISIONING_STATE_MACHINE_ARN,
        "deployment": _DEPLOYMENT_STATE_MACHINE_ARN,
    }
    arn = mapping.get(route, "")
    if not arn:
        raise RuntimeError(f"State machine ARN is not configured for route: {route}")
    return arn


def _execution_name(route: str, event: dict[str, Any], payload: dict[str, Any]) -> str:
    identifier = (
        payload.get("plan_id")
        or payload.get("deployment_id")
        or event.get("id")
        or f"req-{uuid.uuid4().hex[:12]}"
    )
    raw_name = f"{route}-{identifier}"
    sanitized = re.sub(r"[^A-Za-z0-9_-]", "-", raw_name)
    sanitized = re.sub(r"-{2,}", "-", sanitized).strip("-")
    return sanitized[:80] or f"{route}-{uuid.uuid4().hex[:12]}"
