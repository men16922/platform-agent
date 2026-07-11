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

import json
import logging
from typing import Any, Callable

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from src.agents.ai.deploy_recorder import (
    record_cluster_teardown,
    record_deploy,
    record_rollback,
)
from src.agents.ai.local_deployer import rollback_deployment
from src.agents.ai.model_router import (
    ENVIRONMENTS,
    models_for_environment,
    route_deploy,
    route_deploy_stream,
)
from src.agents.ai.provision_tools import teardown_cluster

logger = logging.getLogger(__name__)


class DeployRequest(BaseModel):
    instruction: str = Field(..., min_length=1, description="Natural-language deploy instruction.")
    model: str = Field("local-qwen", description="AI model id (see /api/models).")
    provider: str = Field("onprem", description="Target infrastructure (aws/gcp/azure/onprem).")
    environment: str = Field("dev", description="Deployment tier (production/staging/dev).")


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


class RollbackRequest(BaseModel):
    service_name: str = Field(..., min_length=1, description="Deployment to roll back.")
    namespace: str = Field("default", description="Kubernetes namespace.")
    scope: str = Field("app", description="'app' (kubectl rollout undo) or 'cluster' (teardown).")
    cluster_name: str = Field("platform-agent", description="Cluster name (scope=cluster).")
    mode: str = Field("kind", description="Provisioning mode for cluster scope (kind/k3s).")
    model: str = Field("local-qwen", description="Model id recorded for the activity trail.")
    provider: str = Field("onprem", description="Target infrastructure (aws/gcp/azure/onprem).")
    environment: str = Field("dev", description="Deployment tier (production/staging/dev).")
    # Supersede-in-place: the original deployment being rolled back. When set, the
    # rollback flips that row to 'rolled-back' instead of spawning a duplicate.
    deployment_id: str | None = Field(None, description="Original deployment id to supersede.")
    service: str | None = Field(None, description="Original service label for the row.")
    version: str | None = Field(None, description="Original version label for the row.")


def get_deployer_factory() -> Callable[..., Any] | None:
    """Dependency seam — overridden in tests to inject a TestModel deployer.

    Returns None in production so the router uses its default pydantic-ai factory.
    """
    return None


app = FastAPI(title="platform-agent AI Model Router API", version="1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "model-router-api"}


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
) -> DeployResponse:
    try:
        outcome = await route_deploy(req.instruction, req.model, req.provider, agent_factory=factory)
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
            )
        except Exception:  # noqa: BLE001
            logger.warning("deploy recording failed", exc_info=True)

    return DeployResponse(
        ok=outcome.ok,
        model=outcome.model,
        provider=outcome.provider,
        instruction=req.instruction,
        summary=outcome.summary,
        steps=[DeployStep(**step) for step in outcome.steps],
        suitability=outcome.suitability,
        record=record,
    )


def _sse(obj: dict[str, Any]) -> str:
    return f"data: {json.dumps(obj)}\n\n"


@app.post("/api/local-deploy/stream")
async def local_deploy_stream(
    req: DeployRequest,
    factory: Callable[..., Any] | None = Depends(get_deployer_factory),
) -> StreamingResponse:
    """SSE stream of tool-calling progress, ending with a 'done' event.

    Events: tool_call -> tool_result (repeated) -> done (or error).
    """

    async def generate():
        try:
            async for event in route_deploy_stream(
                req.instruction, req.model, req.provider, agent_factory=factory
            ):
                if event["type"] != "result":
                    yield _sse(event)
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
                        )
                    except Exception:  # noqa: BLE001
                        logger.warning("deploy recording failed", exc_info=True)
                yield _sse(
                    {
                        "type": "done",
                        "ok": outcome.ok,
                        "model": outcome.model,
                        "provider": outcome.provider,
                        "summary": outcome.summary,
                        "suitability": outcome.suitability,
                        "record": record,
                    }
                )
        except ValueError as exc:
            yield _sse({"type": "error", "error": str(exc)})
        except Exception as exc:  # noqa: BLE001
            logger.exception("stream deploy failed")
            yield _sse({"type": "error", "error": str(exc)})

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
        result = rollback_deployment(req.service_name, provider=req.provider, namespace=req.namespace)
        ok = bool(result.get("success"))
        tool = "rollback_deployment"
        args = {"service_name": req.service_name, "version": "previous", "namespace": req.namespace}
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
                model=req.model,
                action=action,
                summary=summary,
                steps=steps,
                ok=ok,
            )
    except Exception:  # noqa: BLE001
        logger.warning("rollback recording failed", exc_info=True)

    return {"ok": ok, "scope": req.scope, "result": result, "summary": summary, "record": record}
