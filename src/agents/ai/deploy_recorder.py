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


def _read_local_deploys(path: str) -> list[dict[str, Any]]:
    store = Path(path).expanduser()
    if not store.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in store.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if item.get("PK") == "DEPLOY":
            rows.append(item)
    return rows


def read_deploys(table: Any | None = None) -> list[dict[str, Any]]:
    """Latest DEPLOY row per deployment_id from the active backend. Used to find the
    rows a rollback/teardown should supersede (single-row lifecycle + cascade)."""
    if table is not None:
        rows = [i for i in getattr(table, "items", []) if i.get("PK") == "DEPLOY"]
    elif os.getenv("PLATFORM_ACTIVITY_TABLE"):
        from boto3.dynamodb.conditions import Key

        resp = _table().query(KeyConditionExpression=Key("PK").eq("DEPLOY"))
        rows = list(resp.get("Items", []))
    elif path := _local_store_path():
        rows = _read_local_deploys(path)
    else:
        return []

    # Latest per id: newest created_at wins; for equal timestamps (same-second
    # supersede) the later-written row wins, so a rollback beats the row it replaces.
    ordered = sorted(enumerate(rows), key=lambda t: (str(t[1].get("created_at", "")), t[0]), reverse=True)
    seen: set[str] = set()
    latest: list[dict[str, Any]] = []
    for _, row in ordered:
        did = str(row.get("deployment_id") or "")
        if did and did not in seen:
            seen.add(did)
            latest.append(row)
    return latest


def _agent_label(model_id: str) -> str:
    model = MODELS.get(model_id)
    if model is None:
        return "AI Model Router"
    home = {"onprem": "On-Prem", "aws": "AWS", "gcp": "GCP", "azure": "Azure"}.get(model.home, model.home)
    return f"{home} Agent ({model.label})"


# Service-rollout tools vs cluster-lifecycle tools. The service label always wins
# so a composite provision+deploy run reads as its app (orders-api/v1.0.0), not the
# cluster it landed on (platform-agent/kind).
_SERVICE_TOOLS = ("deploy_service", "build_image", "deploy_to_cluster", "rollback_deployment")
_CLUSTER_TOOLS = ("provision_cluster", "teardown_cluster")


def _infer_service_version(steps: list[dict[str, Any]]) -> tuple[str, str]:
    # Prefer the actual service rollout across ALL steps before falling back to the
    # cluster — provision_cluster often runs first in a composite deploy and would
    # otherwise shadow the real service/version.
    for step in steps:
        args = step.get("args") or {}
        if step.get("tool") in _SERVICE_TOOLS and args.get("service_name"):
            return str(args["service_name"]), str(args.get("version") or "unknown")
    for step in steps:
        args = step.get("args") or {}
        if step.get("tool") in _CLUSTER_TOOLS and args.get("cluster_name"):
            return str(args["cluster_name"]), str(args.get("mode") or "cluster")
    return "unknown", "unknown"


def _classify_type(steps: list[dict[str, Any]]) -> str:
    """A run is a 'deploy' if it rolls out a service; else 'provision' if it only
    touches cluster lifecycle. Composite provision+deploy counts as 'deploy'
    (provisioning shows as a sub-step in the trace)."""
    tools = {step.get("tool") for step in steps}
    if tools & set(_SERVICE_TOOLS):
        return "deploy"
    if tools & set(_CLUSTER_TOOLS):
        return "provision"
    return "deploy"


def _persist(deploy_item: dict[str, Any], activity_item: dict[str, Any], table: Any | None) -> None:
    """Backend is chosen at persist time: injected table > DynamoDB env > local file."""
    if table is not None:
        table.put_item(Item=deploy_item)
        table.put_item(Item=activity_item)
    elif os.getenv("PLATFORM_ACTIVITY_TABLE"):
        remote = _table()
        remote.put_item(Item=deploy_item)
        remote.put_item(Item=activity_item)
    elif path := _local_store_path():
        _append_local(path, deploy_item, activity_item)


def _infer_cluster(steps: list[dict[str, Any]]) -> str:
    """Target cluster for a run — the correlation key that links a deployment to the
    provisioning that created its cluster (deploy.cluster == provision.service)."""
    for step in steps:
        args = step.get("args") or {}
        if args.get("cluster_name"):
            return str(args["cluster_name"])
    return ""


def _cost_metrics(steps: list[dict[str, Any]], trace: list[dict[str, Any]] | None) -> dict[str, Any]:
    """Per-run cost/usage sub-metrics for the trace (ref AWSome AI Gateway sub-metrics).

    Deterministically aggregates from the trace: tool-call counts (total + by name),
    reasoning-step count, and token usage summed from any per-entry ``usage`` block
    (input/output, tolerating openai- or anthropic-style key names). Zeros when the
    trace carries no usage — the numbers only ever come from recorded execution."""
    entries = trace if trace is not None else [{"kind": "tool", **s} for s in steps]
    by_tool: dict[str, int] = {}
    tool_total = 0
    reasoning_steps = 0
    input_tokens = 0
    output_tokens = 0
    for entry in entries:
        if entry.get("kind") == "tool" or entry.get("tool"):
            name = str(entry.get("tool") or "unknown")
            by_tool[name] = by_tool.get(name, 0) + 1
            tool_total += 1
        elif entry.get("kind") in ("reasoning", "text", "thinking"):
            reasoning_steps += 1
        usage = entry.get("usage") or {}
        input_tokens += int(usage.get("input_tokens") or usage.get("prompt_tokens") or 0)
        output_tokens += int(usage.get("output_tokens") or usage.get("completion_tokens") or 0)
    return {
        "tool_calls_total": tool_total,
        "tool_calls_by_name": by_tool,
        "reasoning_steps": reasoning_steps,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
    }


def _steps_ok(steps: list[dict[str, Any]]) -> bool:
    """A phase succeeded if none of its tool results carry an error / success=False."""
    for step in steps:
        result = step.get("result")
        if isinstance(result, dict):
            if result.get("error"):
                return False
            if "success" in result and not result.get("success"):
                return False
    return True


def _write_row(
    *,
    kind: str,
    cluster: str,
    instruction: str,
    model: str,
    provider: str,
    environment: str,
    summary: str,
    steps: list[dict[str, Any]],
    ok: bool,
    trace: list[dict[str, Any]] | None,
    table: Any | None,
) -> dict[str, str]:
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
        "type": kind,
        "cluster": cluster,  # links a deploy to its provisioning (provision.service)
        "service": service,
        "version": version,
        "provider": provider,
        "environment": environment,
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
        "type": kind,
        "agent": agent,
        "model": model,
        "provider": provider,
        "action": instruction[:140],
        "instruction": instruction[:2000],
        "summary": (summary or "")[:4000],
        "tool_calls": tool_calls,
        # Full ordered trace: reasoning text + tool (args/result), for observability.
        "trace": json.dumps(trace if trace is not None else [{"kind": "tool", **s} for s in steps])[:350000],
        # Per-run cost/usage sub-metrics derived from the trace (observability).
        "cost_metrics": _cost_metrics(steps, trace),
        "status": status,
        "created_at": now,
    }

    _persist(deploy_item, activity_item, table)
    return {"deployment_id": deployment_id, "activity_id": activity_id}


def record_deploy(
    *,
    instruction: str,
    model: str,
    provider: str,
    summary: str,
    steps: list[dict[str, Any]],
    ok: bool,
    environment: str = "dev",
    trace: list[dict[str, Any]] | None = None,
    table: Any | None = None,
) -> dict[str, str] | None:
    """Persist DEPLOY + ACTIVITY rows for a completed run.

    ``provider`` is where it ran (aws/gcp/azure/onprem); ``environment`` is the tier
    (production/staging/dev) — the two are orthogonal and no longer conflated. A
    composite run that BOTH provisions a cluster and deploys an app is split into two
    rows — one ``provision`` (Provisioning page) and one ``deploy`` (Deployments page) —
    each independently roll-back-able. Returns the primary (deploy) ids, or None when
    recording is disabled.
    """
    if table is None and not recording_enabled():
        return None

    tools = {s.get("tool") for s in steps}
    default_cluster = "platform-agent" if provider == "onprem" else ""

    # Natural-language teardown / rollback: route to the single-row lifecycle so an
    # Agent command reads the same as the UI buttons (supersede + cascade), instead of
    # spawning a fresh row.
    if tools and tools <= {"teardown_cluster"}:
        return record_cluster_teardown(
            cluster=_infer_cluster(steps) or default_cluster, provider=provider,
            environment=environment, model=model, summary=summary, steps=steps, ok=ok, table=table,
        )
    if tools and tools <= {"rollback_deployment"}:
        service = _infer_service_version(steps)[0]
        rows = read_deploys(table)
        target = next(
            (r for r in rows if r.get("type") == "deploy" and r.get("service") == service and r.get("status") == "success"),
            None,
        )
        return record_rollback(
            deployment_id=target.get("deployment_id") if target else None,
            kind="deploy", cluster=(target.get("cluster") if target else "") or default_cluster,
            service=service, version="previous", provider=provider, environment=environment,
            model=model, action=f"Rollback {service} to previous revision", summary=summary,
            steps=steps, ok=ok, table=table,
        )

    provision_steps = [s for s in steps if s.get("tool") in _CLUSTER_TOOLS]
    service_steps = [s for s in steps if s.get("tool") not in _CLUSTER_TOOLS]

    if provision_steps and service_steps:
        cluster = _infer_cluster(provision_steps) or default_cluster
        # Per-phase status: a succeeded provision still shows green even if the deploy fails.
        _write_row(
            kind="provision", cluster=cluster, instruction=instruction, model=model, provider=provider,
            environment=environment, summary=summary, steps=provision_steps,
            ok=_steps_ok(provision_steps), trace=None, table=table,
        )
        return _write_row(
            kind="deploy", cluster=cluster, instruction=instruction, model=model, provider=provider,
            environment=environment, summary=summary, steps=service_steps,
            ok=_steps_ok(service_steps), trace=trace, table=table,
        )

    return _write_row(
        kind=_classify_type(steps), cluster=_infer_cluster(steps) or default_cluster,
        instruction=instruction, model=model, provider=provider,
        environment=environment, summary=summary, steps=steps, ok=ok, trace=trace, table=table,
    )


def record_rollback(
    *,
    deployment_id: str | None,
    kind: str,
    cluster: str,
    service: str,
    version: str,
    provider: str,
    environment: str,
    model: str,
    action: str,
    summary: str,
    steps: list[dict[str, Any]],
    ok: bool,
    table: Any | None = None,
) -> dict[str, str] | None:
    """Record a rollback as a single-row lifecycle event.

    When ``deployment_id`` is given, the DEPLOY row reuses that id so the read layer
    (latest-per-id) *supersedes* the original row — it flips to ``rolled-back`` in place
    rather than spawning a duplicate. ``kind`` keeps the row on its home page (an app
    rollback stays ``deploy``/Deployments, a cluster teardown stays ``provision``/
    Provisioning). The rollback trace is linked as a fresh ACTIVITY under the same id.
    """
    if table is None and not recording_enabled():
        return None

    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    deployment_id = deployment_id or ("DEP-" + uuid.uuid4().hex[:8].upper())
    activity_id = "ACT-" + uuid.uuid4().hex[:8].upper()
    status = "rolled-back" if ok else "failed"
    agent = _agent_label(model)
    tool_calls = [str(step.get("tool")) for step in steps if step.get("tool")]

    deploy_item = {
        "PK": "DEPLOY",
        "SK": f"{now}#{deployment_id}",
        "deployment_id": deployment_id,
        "type": kind,
        "cluster": cluster,
        "service": service,
        "version": version,
        "provider": provider,
        "environment": environment,
        "status": status,
        "agent": agent,
        "duration_sec": 0,
        "created_at": now,
    }
    activity_item = {
        "PK": "ACTIVITY",
        "SK": f"{now}#{activity_id}",
        "activity_id": activity_id,
        "deployment_id": deployment_id,
        "type": kind,
        "agent": agent,
        "model": model,
        "provider": provider,
        "action": action[:140],
        "instruction": action[:2000],
        "summary": (summary or "")[:4000],
        "tool_calls": tool_calls,
        "trace": json.dumps([{"kind": "tool", **s} for s in steps])[:350000],
        "status": "success" if ok else "failed",
        "created_at": now,
    }

    _persist(deploy_item, activity_item, table)
    return {"deployment_id": deployment_id, "activity_id": activity_id}


def record_cluster_teardown(
    *,
    cluster: str,
    provider: str,
    environment: str,
    model: str,
    summary: str,
    steps: list[dict[str, Any]],
    ok: bool,
    provision_deployment_id: str | None = None,
    table: Any | None = None,
) -> dict[str, str] | None:
    """Tear down a cluster: supersede its provisioning row to ``rolled-back`` AND cascade
    the apps that ran on it — every workload goes when the cluster does, so their deploy
    rows flip to ``rolled-back`` too (keeps the feed truthful after a teardown)."""
    if table is None and not recording_enabled():
        return None

    rows = read_deploys(table)
    prov_id = provision_deployment_id
    if prov_id is None:
        prov_id = next(
            (r.get("deployment_id") for r in rows if r.get("type") == "provision" and r.get("service") == cluster),
            None,
        )

    ids = record_rollback(
        deployment_id=prov_id, kind="provision", cluster=cluster, service=cluster, version="cluster",
        provider=provider, environment=environment, model=model,
        action=f"Rollback (cluster teardown): {cluster}", summary=summary, steps=steps, ok=ok, table=table,
    )

    # Cascade: every still-active app on this cluster is gone with it.
    for row in rows:
        if row.get("type") == "deploy" and (row.get("cluster") or "") == cluster and row.get("status") == "success":
            svc = str(row.get("service", "unknown"))
            record_rollback(
                deployment_id=row.get("deployment_id"), kind="deploy", cluster=cluster,
                service=svc, version=str(row.get("version", "unknown")), provider=provider,
                environment=environment, model=model, action=f"Removed with cluster {cluster}",
                summary=f"{svc} removed — cluster '{cluster}' was torn down.", steps=[], ok=ok, table=table,
            )
    return ids
