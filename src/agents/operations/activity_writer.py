"""
Activity Writer — Records deployment and agent activity events to DynamoDB.

Writes to the `platform-agent-activity` table (single-table design).
Used by both the Executor Lambda and the AI Pipeline to persist events
for the dashboard read model.

Table schema:
  PK/SK + GSI1 (GSI1PK/GSI1SK) — see dashboard/src/lib/activity-model.ts
"""

from __future__ import annotations

import os
import time
import uuid
from typing import Any

import boto3
import structlog

logger = structlog.get_logger(__name__)

_REGION = os.getenv("AWS_REGION", os.getenv("PLATFORM_AWS_REGION", "us-east-1"))
_ACTIVITY_TABLE = os.getenv("ACTIVITY_TABLE", "platform-agent-activity")

TTL_30_DAYS = 30 * 24 * 60 * 60
TTL_90_DAYS = 90 * 24 * 60 * 60


def _get_table():
    """Lazy DynamoDB Table resource."""
    dynamo = boto3.resource("dynamodb", region_name=_REGION)
    return dynamo.Table(_ACTIVITY_TABLE)


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


# ─── Deployment record ───────────────────────────────────────


def record_deployment(
    *,
    deployment_id: str | None = None,
    provider: str,
    service: str,
    version: str,
    environment: str = "production",
    status: str = "success",
    agent: str = "Unknown Agent",
    duration_sec: int = 0,
    pipeline_steps: list[dict[str, Any]] | None = None,
) -> str:
    """
    Write a deployment record to the activity table.

    Returns the deployment_id.
    """
    if not deployment_id:
        deployment_id = f"DEP-{uuid.uuid4().hex[:8].upper()}"

    created_at = _now_iso()
    sk = f"{created_at}#{deployment_id}"

    item = {
        "PK": "DEPLOY",
        "SK": sk,
        "GSI1PK": f"{provider}#DEPLOY",
        "GSI1SK": sk,
        "deployment_id": deployment_id,
        "provider": provider,
        "service": service,
        "version": version,
        "environment": environment,
        "status": status,
        "agent": agent,
        "duration_sec": duration_sec,
        "pipeline_steps": pipeline_steps or [],
        "created_at": created_at,
        "updated_at": created_at,
        "ttl": int(time.time()) + TTL_30_DAYS,
    }

    try:
        _get_table().put_item(Item=item)
        logger.info(
            "activity.deployment.recorded",
            deployment_id=deployment_id,
            provider=provider,
            service=service,
        )
    except Exception as exc:
        logger.error("activity.deployment.write_failed", error=str(exc))

    return deployment_id


# ─── Agent activity record ───────────────────────────────────


def record_agent_activity(
    *,
    activity_id: str | None = None,
    agent: str,
    provider: str,
    action: str,
    tool_calls: list[str] | None = None,
    status: str = "success",
    error_message: str | None = None,
    duration_ms: int | None = None,
) -> str:
    """
    Write an agent activity record to the activity table.

    Returns the activity_id.
    """
    if not activity_id:
        activity_id = f"ACT-{uuid.uuid4().hex[:8].upper()}"

    created_at = _now_iso()
    sk = f"{created_at}#{activity_id}"

    item: dict[str, Any] = {
        "PK": "ACTIVITY",
        "SK": sk,
        "GSI1PK": f"{provider}#ACTIVITY",
        "GSI1SK": sk,
        "activity_id": activity_id,
        "agent": agent,
        "provider": provider,
        "action": action,
        "tool_calls": tool_calls or [],
        "status": status,
        "created_at": created_at,
        "ttl": int(time.time()) + TTL_30_DAYS,
    }

    if error_message:
        item["error_message"] = error_message
    if duration_ms is not None:
        item["duration_ms"] = duration_ms

    try:
        _get_table().put_item(Item=item)
        logger.info(
            "activity.agent.recorded",
            activity_id=activity_id,
            agent=agent,
            action=action,
        )
    except Exception as exc:
        logger.error("activity.agent.write_failed", error=str(exc))

    return activity_id


# ─── Provider health update ──────────────────────────────────


def update_provider_health(
    *,
    provider: str,
    status: str = "healthy",
    active_incidents: int = 0,
    last_deployment_id: str | None = None,
    last_deployment_at: str | None = None,
) -> None:
    """
    Upsert the provider health snapshot.
    """
    now = _now_iso()

    item: dict[str, Any] = {
        "PK": "HEALTH",
        "SK": provider,
        "provider": provider,
        "status": status,
        "active_incidents": active_incidents,
        "last_check": now,
        "updated_at": now,
    }

    if last_deployment_id:
        item["last_deployment_id"] = last_deployment_id
    if last_deployment_at:
        item["last_deployment_at"] = last_deployment_at

    try:
        _get_table().put_item(Item=item)
        logger.info("activity.health.updated", provider=provider, status=status)
    except Exception as exc:
        logger.error("activity.health.write_failed", error=str(exc))

    # Also write history entry
    history_item = {
        "PK": f"HEALTH_HISTORY#{provider}",
        "SK": now,
        "provider": provider,
        "status": status,
        "active_incidents": active_incidents,
        "checked_at": now,
        "ttl": int(time.time()) + TTL_90_DAYS,
    }

    try:
        _get_table().put_item(Item=history_item)
    except Exception as exc:
        logger.error("activity.health_history.write_failed", error=str(exc))
