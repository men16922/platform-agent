"""Record a completed router deploy into the platform-agent activity table.

Executor-writes / dashboard-reads: the deploy runs locally (next to MLX + the
cluster), and this recorder persists a DEPLOY row (Deployments page) and an
ACTIVITY row (Agent activity timeline) into ``platform-agent-activity`` so the
dashboard can track it. The dashboard's own AWS role is read-only, so the write
belongs here on the executor side.

Gated by ``PLATFORM_ACTIVITY_TABLE`` — unset (tests, no-AWS local runs) means the
recorder is a no-op. The table can be injected for tests.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from typing import Any

from src.agents.ai.model_router import MODELS


def recording_enabled() -> bool:
    return bool(os.getenv("PLATFORM_ACTIVITY_TABLE"))


def _table() -> Any:
    import boto3

    region = os.getenv("AWS_REGION", "ap-northeast-2")
    return boto3.resource("dynamodb", region_name=region).Table(os.environ["PLATFORM_ACTIVITY_TABLE"])


def _agent_label(model_id: str) -> str:
    model = MODELS.get(model_id)
    if model is None:
        return "AI Model Router"
    home = {"onprem": "On-Prem", "aws": "AWS", "gcp": "GCP", "azure": "Azure"}.get(model.home, model.home)
    return f"{home} Agent ({model.label})"


def _infer_service_version(steps: list[dict[str, Any]]) -> tuple[str, str]:
    for step in steps:
        if step.get("tool") in ("build_image", "deploy_to_cluster"):
            args = step.get("args") or {}
            service = args.get("service_name")
            if service:
                return str(service), str(args.get("version") or "unknown")
    return "unknown", "unknown"


def record_deploy(
    *,
    instruction: str,
    model: str,
    provider: str,
    summary: str,
    steps: list[dict[str, Any]],
    ok: bool,
    table: Any | None = None,
) -> dict[str, str] | None:
    """Persist a DEPLOY + ACTIVITY row for a completed deploy.

    Returns the generated ids, or None when recording is disabled.
    """
    if table is None:
        if not recording_enabled():
            return None
        table = _table()

    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    deployment_id = "DEP-" + uuid.uuid4().hex[:8].upper()
    activity_id = "ACT-" + uuid.uuid4().hex[:8].upper()
    service, version = _infer_service_version(steps)
    status = "success" if ok else "failed"
    agent = _agent_label(model)
    tool_calls = [str(step.get("tool")) for step in steps if step.get("tool")]

    table.put_item(
        Item={
            "PK": "DEPLOY",
            "SK": f"{now}#{deployment_id}",
            "deployment_id": deployment_id,
            "service": service,
            "version": version,
            "provider": provider,
            "environment": provider,
            "status": status,
            "agent": agent,
            "duration_sec": 0,
            "created_at": now,
        }
    )
    table.put_item(
        Item={
            "PK": "ACTIVITY",
            "SK": f"{now}#{activity_id}",
            "activity_id": activity_id,
            "deployment_id": deployment_id,  # links the activity to its Deployments detail
            "agent": agent,
            "model": model,
            "provider": provider,
            "action": instruction[:140],
            "instruction": instruction[:2000],
            "summary": (summary or "")[:4000],
            "tool_calls": tool_calls,
            # Full execution trace (tool + args + result) for observability.
            "trace": json.dumps(steps)[:350000],
            "status": status,
            "created_at": now,
        }
    )
    return {"deployment_id": deployment_id, "activity_id": activity_id}
