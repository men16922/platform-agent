"""Execute reviewed on-prem image values without an LLM rewriting them.

The API is a trusted loopback service; the dashboard authenticates its actor.
This does not add tenant credential selection or widen the executor's identity.
"""
from __future__ import annotations

import asyncio
import json
import time
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from src.agents.ai.deploy_recorder import record_deploy
from src.agents.ai.local_deployer import deploy_to_cluster
from src.agents.ai.local_runs import RunConflict, RunNotFound, configured_manager

router = APIRouter()
_DNS_LABEL = r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?$"
# Require an explicit tag or sha256 digest, never an implicit latest image.
_IMAGE = r"^[a-z0-9][a-z0-9._:/-]*(?::[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}|@sha256:[a-f0-9]{64})$"


class PreparedDeployRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    request_id: UUID
    service_name: str = Field(min_length=1, max_length=63, pattern=_DNS_LABEL)
    namespace: str = Field(min_length=1, max_length=63, pattern=_DNS_LABEL)
    image_uri: str = Field(min_length=1, max_length=512, pattern=_IMAGE)
    replicas: int = Field(strict=True, ge=1, le=100)
    environment: Literal["dev", "staging", "production"]
    # This bounded path uses the existing prepared-image adapter defaults.
    # Future changes to ports/health must be reviewed as explicit request fields.

    def tool_args(self) -> dict:
        image, separator, version = self.image_uri.rpartition("@")
        if not separator:
            image, _, version = self.image_uri.rpartition(":")
        return {"service_name": self.service_name, "namespace": self.namespace,
                "image": image, "version": version, "image_uri": self.image_uri,
                "replicas": self.replicas, "provider": "onprem",
                "ports": [8080], "health_path": "/healthz"}


async def _execute(req: PreparedDeployRequest):
    started = time.monotonic()
    args = req.tool_args()
    yield {"type": "tool_call", "tool": "deploy_to_cluster", "args": args}
    result = await asyncio.to_thread(deploy_to_cluster, **args)
    ok = (result.get("status") == "success" and result.get("applied") is True
          and result.get("rollout_verified") is True)
    summary = (f"{req.namespace}/{req.service_name}: rollout verified for {req.image_uri} "
               f"with {req.replicas} replicas." if ok else
               f"Deployment failed: {result.get('error') or 'Rollout was not verified.'}")
    yield {"type": "tool_result", "tool": "deploy_to_cluster", "ok": ok, "result": result}
    record = record_deploy(
        instruction="Deploy reviewed image: " + json.dumps(req.model_dump(mode="json"), sort_keys=True),
        model="onprem-executor", provider="onprem", environment=req.environment,
        summary=summary, steps=[{"tool": "deploy_to_cluster", "args": args, "result": result}],
        ok=ok, duration_sec=time.monotonic() - started,
    )
    yield {"type": "done", "ok": ok, "model": "onprem-executor", "provider": "onprem",
           "summary": summary, "record": record}


@router.post("/api/local-deploy/prepared", status_code=202)
async def prepared_deploy(req: PreparedDeployRequest, x_platform_actor: str = Header(default="")):
    if not x_platform_actor or len(x_platform_actor) > 128:
        raise HTTPException(status_code=401, detail="An actor from the trusted local dashboard is required.")
    try:
        manager = configured_manager()
        request = req.model_dump(mode="json", exclude={"request_id"})
        request.update(model="onprem-executor", provider="onprem")
        manager.start(str(req.request_id), x_platform_actor, request, lambda: _execute(req))
        return manager.snapshot(str(req.request_id), x_platform_actor)
    except RunNotFound as exc:
        raise HTTPException(status_code=404, detail="Run not found.") from exc
    except RunConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Run acceptance is unconfirmed; query the same request ID.") from exc
