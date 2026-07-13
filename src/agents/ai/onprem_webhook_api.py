"""On-Prem PATH B webhook — the event-driven entry point for Day-2 on-prem.

PATH B (event-driven trigger) converges on the same pipeline as PATH A. AWS
receives events via EventBridge → Step Functions; GCP via Pub/Sub → Cloud
Workflows; Azure via Event Grid → Durable Functions. On-Prem's event receiver is
this **FastAPI webhook**, which ingests an alert (Prometheus Alertmanager, or any
already-normalised incident) and drives the 4-step incident pipeline in-process
(``run_incident_pipeline`` — the "직접 호출" orchestration).

    POST /webhook/alertmanager   ← Alertmanager webhook (status/alerts/commonLabels)
    POST /webhook/incident       ← generic pre-normalised signal payload
    GET  /health

Runs LOCAL by design, next to the on-prem cluster. Fully offline: the analyzer
falls back to a heuristic without Bedrock, the on-prem executor action is a
log-only stub, and Slack/DynamoDB writes are best-effort.

Run with:
    uvicorn src.agents.ai.onprem_webhook_api:app --port 8078
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src.agents.ai.onprem_incident_pipeline import run_incident_pipeline

logger = logging.getLogger(__name__)


class PipelineResult(BaseModel):
    incident_id: str | None = None
    provider: str | None = None
    service: str | None = None
    resource_type: str | None = None
    signal_type: str | None = None
    severity: str | None = None
    confidence: float | None = None
    root_cause: str | None = None
    runbook_id: str | None = None
    remediation_mode: str | None = None
    actions: list[str] = []
    executed_actions: list[str] = []
    skipped_actions: list[str] = []
    resolved: bool = False


def _summarise(result: dict[str, Any]) -> PipelineResult:
    # Drop the verbose per-stage payloads; the webhook returns the compact summary.
    return PipelineResult(**{k: v for k, v in result.items() if k != "stages"})


app = FastAPI(title="platform-agent On-Prem Webhook", version="1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "onprem-webhook"}


@app.post("/webhook/alertmanager", response_model=PipelineResult)
async def alertmanager_webhook(payload: dict[str, Any]) -> PipelineResult:
    """Ingest a Prometheus Alertmanager webhook and run the incident pipeline."""
    if "alerts" not in payload and "groupLabels" not in payload:
        raise HTTPException(
            status_code=400,
            detail="Not an Alertmanager webhook: expected 'alerts' or 'groupLabels'.",
        )
    logger.info("onprem_webhook.alertmanager status=%s", payload.get("status"))
    return _summarise(run_incident_pipeline(payload))


@app.post("/webhook/incident", response_model=PipelineResult)
async def generic_incident_webhook(payload: dict[str, Any]) -> PipelineResult:
    """Ingest any signal payload the detector can normalise and run the pipeline."""
    if not payload:
        raise HTTPException(status_code=400, detail="Empty incident payload.")
    logger.info("onprem_webhook.incident")
    return _summarise(run_incident_pipeline(payload))
