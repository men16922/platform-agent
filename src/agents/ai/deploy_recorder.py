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
from pathlib import Path
from typing import Any

from src.agents.ai.model_router import MODELS


def _local_store_path() -> str | None:
    """Path to the local JSONL activity store (offline, no-AWS recording).

    When set, on-prem runs are persisted to a local file the dashboard reads in
    ``DASHBOARD_DATA_SOURCE=local`` mode — keeping the on-prem path fully offline.
    """
    return os.getenv("PLATFORM_ACTIVITY_FILE") or None


def recording_enabled() -> bool:
    return bool(os.getenv("PLATFORM_ACTIVITY_TABLE")) or bool(_local_store_path())


def _table() -> Any:
    import boto3

    region = os.getenv("AWS_REGION", "ap-northeast-2")
    return boto3.resource("dynamodb", region_name=region).Table(os.environ["PLATFORM_ACTIVITY_TABLE"])


def _append_local(path: str, *items: dict[str, Any]) -> None:
    store = Path(path).expanduser()
    store.parent.mkdir(parents=True, exist_ok=True)
    with store.open("a", encoding="utf-8") as handle:
        for item in items:
            handle.write(json.dumps(item, default=str) + "\n")


def _agent_label(model_id: str) -> str:
    model = MODELS.get(model_id)
    if model is None:
        return "AI Model Router"
    home = {"onprem": "On-Prem", "aws": "AWS", "gcp": "GCP", "azure": "Azure"}.get(model.home, model.home)
    return f"{home} Agent ({model.label})"


def _infer_service_version(steps: list[dict[str, Any]]) -> tuple[str, str]:
    _SERVICE_TOOLS = ("deploy_service", "build_image", "deploy_to_cluster", "rollback_deployment")
    for step in steps:
        args = step.get("args") or {}
        if step.get("tool") in _SERVICE_TOOLS and args.get("service_name"):
            return str(args["service_name"]), str(args.get("version") or "unknown")
        if step.get("tool") in ("provision_cluster", "teardown_cluster") and args.get("cluster_name"):
            return str(args["cluster_name"]), str(args.get("mode") or "cluster")
    return "unknown", "unknown"


def record_deploy(
    *,
    instruction: str,
    model: str,
    provider: str,
    summary: str,
    steps: list[dict[str, Any]],
    ok: bool,
    trace: list[dict[str, Any]] | None = None,
    table: Any | None = None,
) -> dict[str, str] | None:
    """Persist a DEPLOY + ACTIVITY row for a completed deploy.

    Returns the generated ids, or None when recording is disabled.
    """
    # Backend is chosen at persist time: injected table > DynamoDB env > local file.
    if table is None and not recording_enabled():
        return None

    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    deployment_id = "DEP-" + uuid.uuid4().hex[:8].upper()
    activity_id = "ACT-" + uuid.uuid4().hex[:8].upper()
    service, version = _infer_service_version(steps)
    status = "success" if ok else "failed"
    agent = _agent_label(model)
    tool_calls = [str(step.get("tool")) for step in steps if step.get("tool")]

    deploy_item = {
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
    activity_item = {
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
        # Full ordered trace: reasoning text + tool (args/result), for observability.
        "trace": json.dumps(trace if trace is not None else [{"kind": "tool", **s} for s in steps])[:350000],
        "status": status,
        "created_at": now,
    }

    if table is not None:
        table.put_item(Item=deploy_item)
        table.put_item(Item=activity_item)
    elif os.getenv("PLATFORM_ACTIVITY_TABLE"):
        remote = _table()
        remote.put_item(Item=deploy_item)
        remote.put_item(Item=activity_item)
    elif path := _local_store_path():
        _append_local(path, deploy_item, activity_item)

    return {"deployment_id": deployment_id, "activity_id": activity_id}
