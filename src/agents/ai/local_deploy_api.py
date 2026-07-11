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

from src.agents.ai.deploy_recorder import record_deploy
from src.agents.ai.model_router import (
    ENVIRONMENTS,
    models_for_environment,
    route_deploy,
    route_deploy_stream,
)

logger = logging.getLogger(__name__)


class DeployRequest(BaseModel):
    instruction: str = Field(..., min_length=1, description="Natural-language deploy instruction.")
    model: str = Field("local-qwen", description="AI model id (see /api/models).")
    provider: str = Field("onprem", description="Target environment (aws/gcp/azure/onprem).")


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
                            summary=outcome.summary,
                            steps=outcome.steps,
                            ok=outcome.ok,
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
