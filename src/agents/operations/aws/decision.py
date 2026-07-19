"""
Decision Agent — Lambda handler.

Receives AnalyzerOutput from Step Functions and:
  1. Selects the appropriate runbook from the runbook registry (DynamoDB / S3)
  2. Determines remediation mode:
       P1 → AUTO     (execute immediately, RTO < 5 min)
       P2 → APPROVE  (Slack approval gate, RTO < 15 min)
       P3 → MANUAL   (create ticket)
  3. Resolves the list of concrete actions (SSM doc names, kubectl commands)
  4. Returns DecisionOutput for the Executor Agent
"""

from __future__ import annotations

import json
import os
from typing import Any, Iterable

import boto3
import structlog

from src.agents.adapters.dynamodb_client import paginated_scan
from src.agents.adapters.registry import get_execution_adapter
from src.agents.ai.reconciliation import apply_gate, reconcile
from src.agents.models import (
    AlarmContext,
    AnalyzerOutput,
    DecisionOutput,
    DetectorOutput,
    NormalizedIncident,
    RemediationMode,
    Severity,
)
from src.agents.runbooks.catalog import BUILTIN_RUNBOOKS
from src.agents.runbooks.schema import validate_runbook

logger = structlog.get_logger(__name__)

_REGION          = os.getenv("AWS_REGION", "ap-northeast-2")
_RUNBOOK_TABLE   = os.getenv("RUNBOOK_TABLE", "incident-runbooks")

_DYNAMO = boto3.resource("dynamodb", region_name=_REGION)


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """
    Event: AnalyzerOutput dict (Step Functions state output from Analyzer).
    """
    log = logger.bind(
        alarm_name=event.get("detector", {}).get("alarm", {}).get("alarm_name", "?"),
        severity=event.get("severity"),
    )
    log.info("decision.start")

    analyzer = _deserialise_analyzer(event)

    runbook_id, actions, rto = _select_runbook(analyzer)
    mode = _determine_mode(analyzer.severity, actions)

    # Reconciliation gate (deterministic-tool-first): never auto-execute a
    # remediation whose analysis isn't grounded in the detector's real evidence.
    recon = reconcile(analyzer.detector, analyzer)
    gated_mode = apply_gate(mode, recon)
    if gated_mode != mode:
        log.warning(
            "decision.reconciliation.downgrade",
            from_mode=mode.value, to_mode=gated_mode.value, issues=recon.issues,
        )
    mode = gated_mode

    log.info("decision.runbook", runbook_id=runbook_id, mode=mode, actions=actions, rto=rto)

    output = DecisionOutput(
        analyzer=analyzer,
        runbook_id=runbook_id,
        remediation_mode=mode,
        actions=actions,
        estimated_rto_sec=rto,
        reconciliation=recon.to_dict(),
    )

    log.info("decision.done")
    return _serialise(output)


# ------------------------------------------------------------------
# Runbook selection
# ------------------------------------------------------------------

# Built-in fallback runbook registry shared with deploy-time DynamoDB seeding.
_BUILTIN_RUNBOOKS = BUILTIN_RUNBOOKS


def _select_runbook(analyzer: AnalyzerOutput) -> tuple[str, list[str], int | None]:
    """
    Match the analyzer output against runbook registry.

    Priority:
      1. DynamoDB lookup (exact alarm_name match)
      2. DynamoDB catalog scan heuristic
      3. Built-in registry heuristic
      4. generic-recovery fallback
    """
    alarm     = analyzer.detector.alarm
    dynamo_rb = _lookup_dynamo(alarm.alarm_name)
    if dynamo_rb:
        return (
            dynamo_rb["runbook_id"],
            _resolve_runbook_actions(dynamo_rb, analyzer),
            dynamo_rb.get("rto_sec"),
        )

    registry_rb = _match_runbook_registry(alarm, analyzer.root_cause, _scan_dynamo_candidates())
    if registry_rb:
        return (
            registry_rb["runbook_id"],
            _resolve_runbook_actions(registry_rb, analyzer),
            registry_rb.get("rto_sec"),
        )

    candidate = _match_builtin(alarm, analyzer.root_cause)
    return (
        candidate["runbook_id"],
        _resolve_runbook_actions(candidate, analyzer),
        candidate.get("rto_sec"),
    )


def _lookup_dynamo(alarm_name: str) -> dict[str, Any] | None:
    try:
        table = _DYNAMO.Table(_RUNBOOK_TABLE)
        resp  = table.get_item(Key={"alarm_name": alarm_name})
        item  = resp.get("Item")
    except Exception as exc:
        logger.warning("decision.dynamo.error", error=str(exc))
        return None

    if item is None:
        return None

    # Operator overrides are registered out-of-band; ignore malformed ones so a
    # bad hand-registered entry falls back to heuristic matching instead of
    # producing a broken decision downstream.
    problems = validate_runbook(item, require_alarm_name=True)
    if problems:
        logger.warning(
            "decision.override.invalid",
            alarm_name=alarm_name,
            problems=problems,
        )
        return None
    return item


def _scan_dynamo_candidates() -> list[dict[str, Any]]:
    try:
        items = paginated_scan(_DYNAMO.Table(_RUNBOOK_TABLE))
    except Exception as exc:
        logger.warning("decision.dynamo.scan_error", error=str(exc))
        return []

    valid: list[dict[str, Any]] = []
    for item in items:
        if validate_runbook(item, require_alarm_name=True):
            logger.warning(
                "decision.candidate.invalid",
                runbook_id=item.get("runbook_id") if isinstance(item, dict) else None,
            )
            continue
        valid.append(item)
    return valid


def _match_builtin(alarm: AlarmContext, root_cause: str) -> dict[str, Any]:
    candidate = _match_runbook_registry(alarm, root_cause, _BUILTIN_RUNBOOKS.values())
    if candidate:
        return candidate
    return _BUILTIN_RUNBOOKS["generic-recovery"]


def _match_runbook_registry(
    alarm: AlarmContext,
    root_cause: str,
    registry: Iterable[dict[str, Any]],
) -> dict[str, Any] | None:
    text = f"{alarm.metric_name} {alarm.reason} {root_cause}".lower()

    best_score = 0
    best_rb: dict[str, Any] | None = None
    generic_rb: dict[str, Any] | None = None

    for rb in registry:
        if rb.get("runbook_id") == "generic-recovery":
            generic_rb = rb
            continue
        score = 0
        if any(alarm.namespace.startswith(ns) for ns in rb.get("namespaces", [])):
            score += 2
        score += sum(1 for kw in rb.get("keywords", []) if kw.lower() in text)
        if score > best_score:
            best_score = score
            best_rb = rb

    return best_rb or generic_rb


def _resolve_runbook_actions(runbook: dict[str, Any], analyzer: AnalyzerOutput) -> list[str]:
    capabilities = runbook.get("capabilities", [])
    if capabilities and analyzer.detector.normalized_incident:
        incident = analyzer.detector.normalized_incident
        provider = incident.provider or "aws"
        try:
            execution_adapter = get_execution_adapter(provider)
            return [
                execution_adapter.resolve_action(capability, incident)["action"]
                for capability in capabilities
            ]
        except Exception as exc:
            logger.warning(
                "decision.capability_resolution.error",
                runbook_id=runbook.get("runbook_id"),
                provider=provider,
                error=str(exc),
            )

    return list(runbook.get("actions", []))


# ------------------------------------------------------------------
# Remediation mode
# ------------------------------------------------------------------

def _determine_mode(severity: Severity, actions: list[str]) -> RemediationMode:
    """
    P1 → AUTO    (critical, immediate action needed)
    P2 → APPROVE (significant but not immediately catastrophic)
    P3 → MANUAL  (early warning, human review)

    Override: if any action name contains "Delete" or "Drop", require APPROVE regardless.
    """
    if any("Delete" in a or "Drop" in a or "Terminate" in a for a in actions):
        return RemediationMode.APPROVE

    return {
        Severity.P1: RemediationMode.AUTO,
        Severity.P2: RemediationMode.APPROVE,
        Severity.P3: RemediationMode.MANUAL,
    }[severity]

# ------------------------------------------------------------------
# Serialisation
# ------------------------------------------------------------------

def _deserialise_analyzer(event: dict[str, Any]) -> AnalyzerOutput:
    from dataclasses import fields as dc_fields
    from src.agents.models import Severity

    det_data   = event["detector"]
    alarm_data = det_data["alarm"]

    alarm = AlarmContext(**{
        k: alarm_data[k]
        for k in (f.name for f in dc_fields(AlarmContext))
        if k in alarm_data
    })
    detector = DetectorOutput(
        alarm=alarm,
        log_insights_results=det_data.get("log_insights_results", []),
        xray_trace_ids=det_data.get("xray_trace_ids", []),
        related_metrics=det_data.get("related_metrics", {}),
        normalized_incident=_deserialise_normalized_incident(det_data.get("normalized_incident")),
    )
    return AnalyzerOutput(
        detector=detector,
        root_cause=event["root_cause"],
        severity=Severity(event["severity"]),
        confidence=float(event["confidence"]),
        similar_incidents=event.get("similar_incidents", []),
    )


def _deserialise_normalized_incident(event: dict[str, Any] | None) -> NormalizedIncident | None:
    if not event:
        return None
    return NormalizedIncident(**event)


def _serialise(output: DecisionOutput) -> dict[str, Any]:
    from dataclasses import asdict
    return json.loads(json.dumps(asdict(output), default=str))
