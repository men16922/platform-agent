"""Local natural-language deploy API — the AI Model Router's HTTP surface.

Wraps the model router (``model_router``) behind a small FastAPI service so any
UI — the dashboard Agents chat running in local mode, a curl call, an internal
ops console — can pick an LLM, target an environment, and POST a *natural-language*
instruction to drive an autonomous deploy.

    { "instruction": "Deploy orders-api v1.4.2 to the local cluster with 2 replicas",
      "model": "local-qwen", "provider": "onprem" }
        -> router validates (model x environment) suitability
        -> runs the model's deployer (local-qwen executes fully offline via MLX)
        -> build -> push -> deploy -> validate  (structured step trace + summary)

This service is LOCAL by design: it runs next to the MLX-LM server and the target
Kubernetes cluster (kind / on-prem), which a cloud-hosted (Vercel) dashboard
cannot reach directly. The executor writes; the dashboard reads.

Run with:
    uvicorn src.agents.ai.local_deploy_api:app --port 8077
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from contextlib import aclosing, suppress
from typing import Any, Callable
from uuid import UUID

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, StrictBool

from src.agents.adapters.deployment import ServiceSpec
from src.agents.ai.deploy_recorder import (
    record_cluster_teardown,
    record_deploy,
    record_rollback,
)
from src.agents.ai.local_deployer import rollback_deployment
from src.agents.ai.model_router import (
    ENVIRONMENTS,
    MODELS,
    models_for_environment,
    route_deploy,
    route_deploy_stream,
    validate_execution_mode,
)
from src.agents.ai.provision_tools import teardown_cluster
from src.agents.ai.prepared_deploy import router as prepared_deploy_router
from src.agents.platform.collector import (
    StatusStore,
    UnauthenticatedReport,
    load_push_keys,
    verify,
)
from src.agents.platform.registry import load_registry

logger = logging.getLogger(__name__)


from src.agents.ai.snapshot_diagnosis import SnapshotQuestion, validate_snapshot_mode


class DeployRequest(BaseModel):
    instruction: str = Field(..., min_length=1, description="Natural-language deploy instruction.")
    model: str = Field("local-qwen", description="AI model id (see /api/models).")
    provider: str = Field("onprem", description="Target infrastructure (aws/gcp/azure/onprem).")
    # No default. The dashboard's natural-language deploy sends no environment at
    # all, so a default here is not a convenience — it is this API asserting a tier
    # the operator never chose, on every row that path writes.
    environment: str | None = Field(None, description="Deployment tier, when the caller declares one.")
    request_id: UUID | None = Field(None, description="Stable ID for a durable local run; repeats observe the original.")
    read_only: StrictBool = Field(False, description="Only register read-only tools; local-qwen/onprem only.")
    snapshot: SnapshotQuestion | None = None


class DeployStep(BaseModel):
    tool: str
    args: dict[str, Any]
    result: Any


class DeployResponse(BaseModel):
    ok: bool
    model: str
    provider: str
    instruction: str
    summary: str
    steps: list[DeployStep]
    suitability: dict[str, str]
    record: dict[str, str] | None = None
    # Front-door supervisor: whether the request was delegated to an A2A specialist
    # and the classified route (present even when it falls through in-process).
    delegated: bool = False
    route: str | None = None
    route_trace: list[dict[str, Any]] | None = None
    inspection: list[dict[str, Any]] | None = None
    model_completion: dict[str, Any] | None = None
    snapshot_analysis: dict[str, Any] | None = None
    read_only: bool = False


class RollbackRequest(BaseModel):
    service_name: str = Field(..., min_length=1, description="Deployment to roll back.")
    # No default. The namespace a deployment lives in is now recorded on its row,
    # so the caller that knows the answer is the row — and a "default" here was one
    # of four layers substituting the same literal, which rolled a tenant-namespaced
    # service back in `default` (undo finds nothing, or reverts a same-named
    # workload). Absent means "fall through to the executor's documented default".
    namespace: str | None = Field(None, description="Kubernetes namespace, when the caller knows it.")
    scope: str = Field("app", description="'app' (kubectl rollout undo) or 'cluster' (teardown).")
    cluster_name: str = Field("platform-agent", description="Cluster name (scope=cluster).")
    mode: str = Field("kind", description="Provisioning mode for cluster scope (kind/k3s).")
    model: str = Field("local-qwen", description="Model id recorded for the activity trail.")
    provider: str = Field("onprem", description="Target infrastructure (aws/gcp/azure/onprem).")
    environment: str | None = Field(None, description="Deployment tier, when the caller declares one.")
    # Supersede-in-place: the original deployment being rolled back. When set, the
    # rollback flips that row to 'rolled-back' instead of spawning a duplicate.
    deployment_id: str | None = Field(None, description="Original deployment id to supersede.")
    service: str | None = Field(None, description="Original service label for the row.")
    version: str | None = Field(None, description="Original version label for the row.")


def _default_namespace() -> str:
    """The executor's own namespace default, read from the spec instead of restated.

    Derived on purpose: this value appears in a recorded row, and a copy of the
    literal here would be a fifth layer answering the same question — the exact
    shape of the defect this path just had. If ``ServiceSpec`` ever changes where
    an unplaced workload goes, the row follows it.
    """
    return ServiceSpec(name="", image="", version="").namespace


def get_deployer_factory() -> Callable[..., Any] | None:
    """Dependency seam — overridden in tests to inject a TestModel deployer.

    Returns None in production so the router uses its default pydantic-ai factory.
    """
    return None


def get_front_door() -> Any | None:
    """The supervisor/orchestrator front door — classifies each request and
    delegates to a registered A2A specialist when one is configured, else the
    request falls through to the in-process on-prem deployer.

    Dependency seam (overridden in tests). Non-breaking: with no
    ``PLATFORM_{PROVISION,DEPLOY,KAGENT}_A2A_URL`` set, the supervisor only
    classifies and never delegates, so behavior is identical to before.
    """
    from src.agents.ai.supervisor import Supervisor

    if os.getenv("SUPERVISOR_ORCHESTRATION", "").lower() in ("1", "true", "yes"):
        from src.agents.ai.orchestration import Orchestrator

        return Orchestrator.from_environment()
    return Supervisor.from_environment()


app = FastAPI(title="platform-agent AI Model Router API", version="1.0")
app.include_router(prepared_deploy_router)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "model-router-api"}


# --- platform status: the hub half of the push collector --------------------
#
# The hub ACCEPTS status; it never fetches it. That is the point — a hub that
# polled N clusters would have to hold credentials for N clusters, which is the
# cross-tenant concentration Phase 1a removed. Everything here is therefore
# write-in / read-out, with no outbound path to any spoke.

_status_store = StatusStore()


@app.post("/api/platform/status")
async def ingest_platform_status(
    payload: dict[str, Any],
    x_platform_signature: str = Header(default=""),
) -> dict[str, Any]:
    """Accept one spoke's report, authenticated by a per-identity HMAC key.

    With no keys configured the endpoint accepts nothing. An unconfigured hub that
    accepted unsigned reports would let anyone who can reach the port write any
    tenant's status — and status is what humans act on.
    """
    keys = load_push_keys()
    if not keys:
        raise HTTPException(status_code=503, detail="no push keys configured")
    try:
        report = verify(payload, x_platform_signature, keys)
    except UnauthenticatedReport as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    _status_store.ingest(report, received_at=time.time())
    return {"accepted": report.identity, "rows": len(report.statuses)}


@app.get("/api/platform/status")
async def read_platform_status() -> dict[str, Any]:
    """Everything the hub has been told, plus what it has stopped being told.

    `freshness` and `missing` are not decoration: a drift view that only lists what
    it received is silent exactly when a cluster goes dark, which is the case it
    exists for.
    """
    now = time.time()
    try:
        missing = _status_store.missing_identities(load_registry())
    except (OSError, ValueError):
        # The registry is a git artifact and may not ship with the hub; the
        # received data is still worth serving.
        missing = []
    return {
        "statuses": [s.to_dict() for s in _status_store.statuses(now=now)],
        "tenancy": _status_store.tenancy(),
        "freshness": _status_store.freshness(now=now),
        "missing": missing,
        "stale_after_sec": _status_store.stale_after_sec,
    }


@app.get("/api/platform/tenants")
async def read_declared_tenants() -> dict[str, Any]:
    """The declared tenant roster, straight from the registry (the SSOT).

    This exists so the dashboard can *check* a tenant grant instead of storing
    whatever string an admin typed. A grant for a tenant that does not exist is
    not a harmless no-op: it reads on screen as "this person has access to
    something", and matches nothing — the failure is silent in the direction
    that looks fine.

    Deliberately the registry and not the push store: a roster derived from what
    has reported would make a tenant ungrantable until its agent happened to
    push, which is backwards — grants are how you get someone ready to look.

    503 rather than an empty list when the registry cannot be read. "There are
    no tenants" and "I could not ask" must not collapse, because the caller
    fails closed on one and would happily reject every grant on the other.
    """
    try:
        registry = load_registry()
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=503, detail=f"registry unavailable: {exc}") from exc
    return {
        "tenants": sorted(registry.tenants),
        "identities": sorted(
            f"{name}/{env}"
            for name, tenant in registry.tenants.items()
            for env in tenant.environments
        ),
    }


@app.get("/api/models")
async def list_models(provider: str = "onprem") -> dict[str, Any]:
    """Models offered for an environment, recommended-first — drives the UI selector."""
    if provider not in ENVIRONMENTS:
        raise HTTPException(status_code=400, detail=f"Unknown environment: {provider}")
    return {"provider": provider, "models": models_for_environment(provider)}


@app.post("/api/local-deploy", response_model=DeployResponse)
async def local_deploy(
    req: DeployRequest,
    factory: Callable[..., Any] | None = Depends(get_deployer_factory),
    front_door: Any | None = Depends(get_front_door),
) -> DeployResponse:
    _validate_request_mode(req)
    started = time.monotonic()
    # Front-door: classify the request and delegate to a registered A2A specialist
    # when one is configured; otherwise fall through to the in-process deployer.
    route: str | None = None
    route_trace: list[dict[str, Any]] | None = None
    if front_door is not None and not req.read_only:
        try:
            # handle() may do network I/O when delegating — keep the event loop free.
            s_outcome = await asyncio.to_thread(front_door.handle, req.instruction)
            route = s_outcome.decision.role.value
            route_trace = s_outcome.trace
            if s_outcome.delegated:
                return DeployResponse(
                    ok=True,
                    model=req.model,
                    provider=req.provider,
                    instruction=req.instruction,
                    summary=f"Supervisor delegated this request to the {route} A2A specialist.",
                    steps=[],
                    suitability={},
                    record=None,
                    delegated=True,
                    route=route,
                    route_trace=route_trace,
                )
        except Exception:  # noqa: BLE001 - front door is best-effort; fall through
            logger.warning("front-door supervisor failed; using in-process deployer", exc_info=True)

    try:
        outcome = await route_deploy(req.instruction, req.model, req.provider, agent_factory=factory,
                                     **({"read_only": True} if req.read_only else {}),
                                     **({"snapshot": req.snapshot} if req.snapshot is not None else {}))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # Executor-writes: persist to the activity table so the dashboard tracks it.
    # Best-effort — recording failures must not fail the deploy response.
    record = None
    if outcome.steps:
        try:
            record = record_deploy(
                instruction=req.instruction,
                model=outcome.model,
                provider=outcome.provider,
                environment=req.environment,
                summary=outcome.summary,
                steps=outcome.steps,
                ok=outcome.ok,
                trace=outcome.trace,
                duration_sec=time.monotonic() - started,
                read_only=req.read_only,
            )
        except Exception:  # noqa: BLE001
            logger.warning("deploy recording failed", exc_info=True)

    return DeployResponse(
        ok=outcome.ok,
        model=outcome.model,
        provider=outcome.provider,
        instruction=req.instruction,
        summary=outcome.summary,
        inspection=getattr(outcome, "inspection", None),
        model_completion=getattr(outcome, "model_completion", None),
        snapshot_analysis=getattr(outcome, "snapshot_analysis", None),
        read_only=req.read_only,
        steps=[DeployStep(**step) for step in outcome.steps],
        suitability=outcome.suitability,
        record=record,
        delegated=False,
        route=route,
        route_trace=route_trace,
    )


def _sse(obj: dict[str, Any], *, event_id: int | None = None) -> str:
    """One SSE frame. An ``event_id`` emits an ``id:`` line so a client can dedup
    on reconnect via ``Last-Event-ID`` (older clients simply ignore it)."""
    prefix = f"id: {event_id}\n" if event_id is not None else ""
    return f"{prefix}data: {json.dumps(obj)}\n\n"


# An SSE comment line — ignored by clients, but keeps idle proxies/load balancers
# from closing a stream that is quiet during a long tool call.
_SSE_KEEPALIVE = ": keepalive\n\n"
# Emit a keepalive if no real event arrives within this many seconds.
_SSE_HEARTBEAT_S = 15.0


async def _events_with_heartbeats(events):
    """Keep agent iteration in one task; idle transport heartbeats cannot cancel it."""
    queue = asyncio.Queue(maxsize=16)

    async def produce():
        # Pydantic AI/AnyIO scopes must be entered and exited by the same task.
        # Scheduling each __anext__ separately violates that contract.
        try:
            async with aclosing(events.__aiter__()) as iterator:
                async for event in iterator:
                    await queue.put(("event", event))
        except Exception as exc:
            await queue.put(("error", exc))
        else:
            await queue.put(("end", None))

    producer = asyncio.create_task(produce())
    try:
        while True:
            try:
                kind, payload = await asyncio.wait_for(queue.get(), timeout=_SSE_HEARTBEAT_S)
            except asyncio.TimeoutError:
                yield None
                continue
            if kind == "end":
                break
            if kind == "error":
                raise payload
            yield payload
    finally:
        producer.cancel()
        with suppress(asyncio.CancelledError):
            await producer


async def _recorded_run_events(req: DeployRequest, factory):
    """Complete and record the agent run even when its SSE observer disconnects."""
    started = time.monotonic()
    async with aclosing(route_deploy_stream(
        req.instruction, req.model, req.provider, agent_factory=factory,
        **({"read_only": True} if req.read_only else {}),
        **({"snapshot": req.snapshot} if req.snapshot is not None else {})
    )) as events:
        async for event in events:
            if event["type"] != "result":
                yield event
                continue
            outcome = event["outcome"]
            record = None
            if outcome.steps:
                record = record_deploy(
                    instruction=req.instruction, model=outcome.model, provider=outcome.provider,
                    environment=req.environment, summary=outcome.summary,
                    steps=outcome.steps, ok=outcome.ok, trace=outcome.trace,
                    duration_sec=time.monotonic() - started,
                    read_only=req.read_only,
                )
            yield {"type": "done", "ok": outcome.ok, "agent": outcome.model,
                   "model": outcome.model, "provider": outcome.provider,
                   "summary": outcome.summary, "suitability": outcome.suitability, "record": record,
                   "inspection": getattr(outcome, "inspection", None),
                   "model_completion": getattr(outcome, "model_completion", None),
                   "snapshot_analysis": getattr(outcome, "snapshot_analysis", None),
                   "read_only": req.read_only}


def _validate_request_mode(req: DeployRequest) -> None:
    try:
        validate_execution_mode(req.model, req.provider, req.read_only)
        validate_snapshot_mode(req.instruction, req.model, req.provider, req.read_only, req.snapshot)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _run_manager():
    from src.agents.ai.local_runs import configured_manager
    try:
        return configured_manager()
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Durable local run storage is unavailable.") from exc


@app.get("/api/local-deploy/runs/{request_id}")
async def local_deploy_run(request_id: UUID, x_platform_actor: str = Header(default="")):
    from src.agents.ai.local_runs import RunNotFound
    if not x_platform_actor or len(x_platform_actor) > 128:
        raise HTTPException(status_code=401, detail="An actor from the trusted local dashboard is required.")
    try:
        return _run_manager().snapshot(str(request_id), x_platform_actor)
    except RunNotFound as exc:
        raise HTTPException(status_code=404, detail="Run not found.") from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Run state could not be read.") from exc


@app.post("/api/local-deploy/stream")
async def local_deploy_stream(
    req: DeployRequest,
    factory: Callable[..., Any] | None = Depends(get_deployer_factory),
    x_platform_actor: str = Header(default=""),
) -> StreamingResponse:
    """SSE stream of tool-calling progress, ending with a 'done' event.

    Events: tool_call -> tool_result (repeated) -> done (or error).
    """
    _validate_request_mode(req)
    if req.request_id is not None:
        from src.agents.ai.local_runs import RunConflict, RunNotFound
        if not x_platform_actor or len(x_platform_actor) > 128:
            raise HTTPException(status_code=401, detail="An actor from the trusted local dashboard is required.")
        if req.model not in MODELS or req.provider not in ENVIRONMENTS:
            raise HTTPException(status_code=400, detail="Unknown model or provider.")
        manager = _run_manager()
        request_id = str(req.request_id)
        try:
            manager.start(request_id, x_platform_actor,
                          req.model_dump(mode="json", exclude={"request_id"} | ({"snapshot"} if req.snapshot is None else set())),
                          lambda: _recorded_run_events(req, factory))
        except RunNotFound as exc:
            raise HTTPException(status_code=404, detail="Run not found.") from exc
        except RunConflict as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=503, detail="Run could not be durably accepted.") from exc

        async def observe():
            async for event in manager.observe(request_id, x_platform_actor, _SSE_HEARTBEAT_S):
                yield _SSE_KEEPALIVE if event is None else _sse(event, event_id=event["seq"])

        return StreamingResponse(observe(), media_type="text/event-stream", headers={
            "Cache-Control": "no-cache", "X-Accel-Buffering": "no", "X-Request-ID": request_id,
        })

    async def generate():
        started = time.monotonic()
        seq = 0

        def frame(obj: dict[str, Any]) -> str:
            nonlocal seq
            seq += 1
            return _sse(obj, event_id=seq)

        # READY sentinel first: the client confirms the connection and attaches a
        # live tail before any backfill, closing the initial-render gap. The
        # `agent` field is reserved for per-agent attribution (A-3) — today the
        # deploy stream is single-agent, so it carries the model id.
        yield frame({"type": "ready", "agent": req.model, "read_only": req.read_only})
        try:
            events = route_deploy_stream(
                req.instruction, req.model, req.provider, agent_factory=factory,
                **({"read_only": True} if req.read_only else {}),
                **({"snapshot": req.snapshot} if req.snapshot is not None else {})
            )
            async with aclosing(_events_with_heartbeats(events)) as event_stream:
                async for event in event_stream:
                    if event is None:
                        yield _SSE_KEEPALIVE
                        continue

                    if event["type"] != "result":
                        yield frame(event)
                        continue

                    outcome = event["outcome"]
                    record = None
                    if outcome.steps:
                        try:
                            record = record_deploy(
                                instruction=req.instruction,
                                model=outcome.model,
                                provider=outcome.provider,
                                environment=req.environment,
                                summary=outcome.summary,
                                steps=outcome.steps,
                                ok=outcome.ok,
                                trace=outcome.trace,
                                duration_sec=time.monotonic() - started,
                                read_only=req.read_only,
                            )
                        except Exception:  # noqa: BLE001
                            logger.warning("deploy recording failed", exc_info=True)
                    yield frame(
                        {
                            "type": "done",
                            "ok": outcome.ok,
                            "agent": outcome.model,  # A-3: per-agent attribution field
                            "model": outcome.model,
                            "provider": outcome.provider,
                            "summary": outcome.summary,
                            "inspection": getattr(outcome, "inspection", None),
                            "model_completion": getattr(outcome, "model_completion", None),
                            "snapshot_analysis": getattr(outcome, "snapshot_analysis", None),
                            "read_only": req.read_only,
                            "suitability": outcome.suitability,
                            "record": record,
                        }
                    )
        except ValueError as exc:
            yield frame({"type": "error", "error": str(exc)})
        except Exception as exc:  # noqa: BLE001
            logger.exception("stream deploy failed")
            yield frame({"type": "error", "error": str(exc)})

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/api/local-rollback")
async def local_rollback(req: RollbackRequest) -> dict[str, Any]:
    """Roll back an on-prem deployment (real ``kubectl rollout undo``) or, for
    scope='cluster', tear the cluster down. Records a DEPLOY/ACTIVITY row so the
    dashboard timeline reflects the action.

    This is the on-prem counterpart to the cloud (AWS Step Functions) rollback:
    the dashboard's Rollback button routes here when the deployment is on-prem.
    """
    if req.provider not in ENVIRONMENTS:
        raise HTTPException(status_code=400, detail=f"Unknown environment: {req.provider}")

    if req.scope == "cluster":
        result = teardown_cluster(cluster_name=req.cluster_name, mode=req.mode, provider=req.provider)
        ok = bool(result.get("success"))
        tool = "teardown_cluster"
        args: dict[str, Any] = {"cluster_name": req.cluster_name, "mode": req.mode}
        action = f"Rollback (cluster teardown): {req.cluster_name}"
        summary = f"Cluster '{req.cluster_name}' torn down." if ok else f"Cluster teardown failed: {result.get('error')}"
    else:
        # Only override when the caller actually knew the namespace, so the single
        # kubectl default stays in the executor rather than being restated here.
        ns_kwargs = {"namespace": req.namespace} if req.namespace else {}
        result = rollback_deployment(req.service_name, provider=req.provider, **ns_kwargs)
        ok = bool(result.get("success"))
        tool = "rollback_deployment"
        # Record the namespace that was actually acted on, not the request's blank.
        args = {"service_name": req.service_name, "version": "previous",
                "namespace": req.namespace or _default_namespace()}
        action = f"Rollback {req.service_name} to previous revision"
        summary = (
            f"{req.service_name} rolled back to previous revision."
            if ok else f"Rollback failed: {result.get('error')}"
        )

    steps = [{"tool": tool, "args": args, "result": result}]
    record = None
    try:
        if req.scope == "cluster":
            # Tearing down the cluster removes every app on it — supersede the
            # provisioning row and cascade its deployments to 'rolled-back'.
            record = record_cluster_teardown(
                cluster=req.cluster_name,
                provider=req.provider,
                environment=req.environment,
                model=req.model,
                summary=summary,
                steps=steps,
                ok=ok,
                provision_deployment_id=req.deployment_id,
            )
        else:
            # App rollback: supersede the original deployment (row flips to
            # 'rolled-back') rather than appending a duplicate feed row.
            record = record_rollback(
                deployment_id=req.deployment_id,
                kind="deploy",
                cluster=req.cluster_name,
                service=req.service or req.service_name or req.cluster_name,
                version=req.version or "previous",
                provider=req.provider,
                environment=req.environment,
                # Keep the placement on the row we are superseding — dropping it
                # would leave the *next* rollback with nothing to target.
                namespace=req.namespace,
                model=req.model,
                action=action,
                summary=summary,
                steps=steps,
                ok=ok,
            )
    except Exception:  # noqa: BLE001
        logger.warning("rollback recording failed", exc_info=True)

    return {"ok": ok, "scope": req.scope, "result": result, "summary": summary, "record": record}
