"""On-Prem Day-2 incident pipeline — in-process 4-step orchestration (PATH B).

AWS chains Detector → Analyzer → Decision → Executor via Step Functions, GCP via
Cloud Workflows, Azure via Durable Functions. On-Prem has **no managed
orchestrator** — the architecture's On-Prem row is "Event Bus = Webhook (FastAPI),
Orchestration = 직접 호출". This module is that direct call: it chains the same
four operations handlers in-process, feeding each handler the previous handler's
JSON-serialisable dict output exactly as the cloud orchestrators pass state
between steps.

The detector auto-detects the provider from the event shape, so an Alertmanager
webhook body (carrying ``alerts`` / ``groupLabels``) routes through the on-prem
SignalAdapter and on-prem ExecutionAdapter. The whole chain runs fully offline:
the analyzer falls back to a heuristic when Bedrock is unreachable, the on-prem
executor action is a log-only stub (real kubectl via the MCP Gateway is roadmap),
and Slack/DynamoDB writes are best-effort and skipped when unconfigured.

Execution is separable from decision: ``run_incident_pipeline(event, execute=False)``
runs detect → analyze → decide only, so a P2 (APPROVE) incident can be parked for
human approval and later replayed through the executor via ``execute_incident``.
"""

from __future__ import annotations

from typing import Any

from src.agents.operations.analyzer.handler import lambda_handler as _analyze
from src.agents.operations.decision.handler import lambda_handler as _decide
from src.agents.operations.detector.handler import lambda_handler as _detect
from src.agents.operations.executor.handler import lambda_handler as _execute


def run_incident_pipeline(event: dict[str, Any], *, execute: bool = True) -> dict[str, Any]:
    """Run detect → analyze → decide (→ execute) in-process for one signal.

    ``event`` is a raw signal payload — e.g. an Alertmanager webhook body. When
    ``execute`` is False the executor stage is skipped (used to park an
    approval-gated incident); the returned ``stages.decision`` can be replayed
    through :func:`execute_incident` once approved.
    """
    detector_out = _detect(event, None)
    analyzer_out = _analyze(detector_out, None)
    decision_out = _decide(analyzer_out, None)
    executor_out = _execute(decision_out, None) if execute else None

    incident = detector_out.get("normalized_incident") or {}
    result = {
        "provider": incident.get("provider"),
        "service": incident.get("service"),
        "resource_type": incident.get("resource_type"),
        "signal_type": incident.get("signal_type"),
        "severity": analyzer_out.get("severity"),
        "confidence": analyzer_out.get("confidence"),
        "root_cause": analyzer_out.get("root_cause"),
        "runbook_id": decision_out.get("runbook_id"),
        "remediation_mode": decision_out.get("remediation_mode"),
        "actions": decision_out.get("actions", []),
        "stages": {
            "detector": detector_out,
            "analyzer": analyzer_out,
            "decision": decision_out,
            "executor": executor_out,
        },
    }
    result.update(_executor_fields(executor_out))
    return result


def execute_incident(decision_out: dict[str, Any]) -> dict[str, Any]:
    """Replay a parked decision through the executor (used on approval)."""
    return _execute(decision_out, None)


def _executor_fields(executor_out: dict[str, Any] | None) -> dict[str, Any]:
    """Flatten the executor's summary onto the top-level result."""
    executor_out = executor_out or {}
    return {
        "incident_id": executor_out.get("incident_id"),
        "executed_actions": executor_out.get("executed_actions", []),
        "skipped_actions": executor_out.get("skipped_actions", []),
        "resolved": executor_out.get("resolved", False),
    }
