"""On-Prem PATH B webhook — the event-driven entry point for Day-2 on-prem.

PATH B (event-driven trigger) converges on the same pipeline as PATH A. AWS
receives events via EventBridge → Step Functions; GCP via Pub/Sub → Cloud
Workflows; Azure via Event Grid → Durable Functions. On-Prem's event receiver is
this **FastAPI webhook**, which ingests an alert (Prometheus Alertmanager, or any
already-normalised incident) and drives the 4-step incident pipeline in-process
(``run_incident_pipeline`` — the "직접 호출" orchestration).

The Guardian severity → mode mapping gates remediation exactly as the cloud
providers do:

    P1 → AUTO     execute immediately
    P2 → APPROVE  park a pending approval (offline store) → /approve or /reject
    P3 → MANUAL   notify only, no execution

    POST /webhook/alertmanager   ← Alertmanager webhook (status/alerts/commonLabels)
    POST /webhook/incident       ← generic pre-normalised signal payload
    GET  /pending                ← list pending approvals
    POST /approve/{approval_id}  ← approve → replay decision through the executor
    POST /reject/{approval_id}   ← reject → no execution
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

from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src.agents.ai import onprem_approvals as approvals
from src.agents.ai import onprem_incidents as incidents
from src.agents.ai.onprem_incident_pipeline import execute_incident, run_incident_pipeline

logger = logging.getLogger(__name__)


class PipelineResult(BaseModel):
    status: str  # executed | pending_approval | notified | approved | rejected
    approval_id: str | None = None
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


def _summary(result: dict[str, Any]) -> dict[str, Any]:
    # Drop the verbose per-stage payloads; keep the compact summary fields.
    return {k: v for k, v in result.items() if k != "stages"}


def _handle_incident(payload: dict[str, Any]) -> PipelineResult:
    """Run the pipeline and gate execution on the Guardian remediation mode."""
    result = run_incident_pipeline(payload, execute=False)
    summary = _summary(result)
    mode = result.get("remediation_mode")

    if mode == "AUTO":
        executor_out = execute_incident(result["stages"]["decision"])
        summary.update(
            {
                "status": "executed",
                "incident_id": executor_out.get("incident_id"),
                "executed_actions": executor_out.get("executed_actions", []),
                "skipped_actions": executor_out.get("skipped_actions", []),
                "resolved": executor_out.get("resolved", False),
            }
        )
        _record_incident(summary, resolved=executor_out.get("resolved", False), executor_out=executor_out)
    elif mode == "APPROVE":
        # Parked for approval — surfaced in /pending, recorded to the timeline
        # only once resolved (approve/reject), so it isn't double-counted.
        record = approvals.create_pending(result["stages"]["decision"], summary)
        summary.update({"status": "pending_approval", "approval_id": record["approval_id"]})
    else:  # MANUAL — notify only, unresolved incident for the timeline
        summary["status"] = "notified"
        _record_incident(summary, resolved=False)

    return PipelineResult(**summary)


def _record_incident(
    summary: dict[str, Any], *, resolved: bool, executor_out: dict[str, Any] | None = None
) -> None:
    """Persist an on-prem incident to the offline store for the dashboard timeline."""
    executor_out = executor_out or {}
    incidents.record_incident(
        severity=summary.get("severity"),
        alarm_name=summary.get("service"),
        root_cause=summary.get("root_cause"),
        runbook_id=summary.get("runbook_id"),
        remediation_mode=summary.get("remediation_mode"),
        resolved=resolved,
        executed_actions=executor_out.get("executed_actions", []),
        incident_id=executor_out.get("incident_id"),
    )


app = FastAPI(title="platform-agent On-Prem Webhook", version="1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict[str, str]:
    # Lenient liveness — 200 as long as the process is up (for restart probes).
    return {"status": "ok", "service": "onprem-webhook"}


@app.get("/health/ready")
async def health_ready(response: Response) -> dict[str, Any]:
    """Strict readiness — 503 when a required dependency (the offline stores) is
    unusable, so a load balancer stops routing to a degraded instance. The
    lenient ``/health`` above stays 200 so the process isn't killed."""
    checks: dict[str, str] = {}
    ready = True
    for name, probe in (
        ("approvals_store", approvals.list_pending),
        ("incident_store", lambda: incidents.list_incidents(limit=1)),
    ):
        try:
            probe()
            checks[name] = "ok"
        except Exception as exc:  # store dir missing / unreadable
            checks[name] = f"error: {type(exc).__name__}"
            ready = False
    if not ready:
        response.status_code = 503
    return {"status": "ready" if ready else "degraded", "checks": checks}


@app.post("/webhook/alertmanager", response_model=PipelineResult)
async def alertmanager_webhook(payload: dict[str, Any]) -> PipelineResult:
    """Ingest a Prometheus Alertmanager webhook and run the incident pipeline."""
    if "alerts" not in payload and "groupLabels" not in payload:
        raise HTTPException(
            status_code=400,
            detail="Not an Alertmanager webhook: expected 'alerts' or 'groupLabels'.",
        )
    logger.info("onprem_webhook.alertmanager status=%s", payload.get("status"))
    return _handle_incident(payload)


@app.post("/webhook/incident", response_model=PipelineResult)
async def generic_incident_webhook(payload: dict[str, Any]) -> PipelineResult:
    """Ingest any signal payload the detector can normalise and run the pipeline."""
    if not payload:
        raise HTTPException(status_code=400, detail="Empty incident payload.")
    logger.info("onprem_webhook.incident")
    return _handle_incident(payload)


@app.get("/pending")
async def pending() -> dict[str, Any]:
    """List Day-2 remediations awaiting human approval."""
    items = approvals.list_pending()
    return {"count": len(items), "pending": items}


@app.post("/approve/{approval_id}", response_model=PipelineResult)
async def approve(approval_id: str) -> PipelineResult:
    """Approve a parked P2 remediation and replay its decision through the executor."""
    record = approvals.get(approval_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Unknown approval: {approval_id}")
    if record.get("status") != "pending":
        raise HTTPException(status_code=409, detail=f"Already {record.get('status')}: {approval_id}")

    executor_out = execute_incident(record["decision"])
    approvals.resolve(approval_id, "approved", executor_out=executor_out)
    _record_incident_from_approval(record, resolved=executor_out.get("resolved", False), executor_out=executor_out)
    logger.info("onprem_webhook.approved id=%s", approval_id)
    return PipelineResult(
        status="approved",
        approval_id=approval_id,
        severity=record.get("severity"),
        runbook_id=record.get("runbook_id"),
        remediation_mode=record.get("remediation_mode"),
        actions=record.get("actions", []),
        incident_id=executor_out.get("incident_id"),
        executed_actions=executor_out.get("executed_actions", []),
        skipped_actions=executor_out.get("skipped_actions", []),
        resolved=executor_out.get("resolved", False),
    )


@app.post("/reject/{approval_id}", response_model=PipelineResult)
async def reject(approval_id: str) -> PipelineResult:
    """Reject a parked P2 remediation; no execution occurs."""
    record = approvals.get(approval_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Unknown approval: {approval_id}")
    if record.get("status") != "pending":
        raise HTTPException(status_code=409, detail=f"Already {record.get('status')}: {approval_id}")

    approvals.resolve(approval_id, "rejected")
    _record_incident_from_approval(record, resolved=False)
    logger.info("onprem_webhook.rejected id=%s", approval_id)
    return PipelineResult(
        status="rejected",
        approval_id=approval_id,
        severity=record.get("severity"),
        runbook_id=record.get("runbook_id"),
        remediation_mode=record.get("remediation_mode"),
        actions=record.get("actions", []),
    )


def _record_incident_from_approval(
    record: dict[str, Any], *, resolved: bool, executor_out: dict[str, Any] | None = None
) -> None:
    """Record a resolved (approved/rejected) P2 approval as a timeline incident."""
    executor_out = executor_out or {}
    analyzer = (record.get("decision") or {}).get("analyzer") or {}
    incidents.record_incident(
        severity=record.get("severity"),
        alarm_name=record.get("service"),
        root_cause=analyzer.get("root_cause"),
        runbook_id=record.get("runbook_id"),
        remediation_mode=record.get("remediation_mode"),
        resolved=resolved,
        executed_actions=executor_out.get("executed_actions", []),
        incident_id=executor_out.get("incident_id"),
    )


@app.get("/incidents")
async def list_onprem_incidents(limit: int = 100) -> dict[str, Any]:
    """List recorded on-prem incidents for the dashboard timeline (hybrid merge)."""
    items = incidents.list_incidents(limit=limit)
    return {"count": len(items), "incidents": items}
