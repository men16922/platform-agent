"""
GCP Decision — Cloud Function handler.

Receives AnalyzerOutput from Cloud Workflows and:
  1. Selects the appropriate runbook from Firestore runbook registry
  2. Determines remediation mode (AUTO / APPROVE / MANUAL)
  3. Resolves concrete actions via GCP execution adapter
  4. Returns DecisionOutput for the Executor
"""

from __future__ import annotations

import json
import os
from typing import Any

import structlog

from src.agents.adapters.registry import get_execution_adapter
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

_PROJECT_ID = os.getenv("GCP_PROJECT_ID", "")
_RUNBOOK_COLLECTION = os.getenv("RUNBOOK_COLLECTION", "incident-runbooks")


def cloud_function_handler(event: dict[str, Any]) -> dict[str, Any]:
    """
    Event: AnalyzerOutput dict (Cloud Workflows state output from Analyzer).
    """
    log = logger.bind(
        alarm_name=event.get("detector", {}).get("alarm", {}).get("alarm_name", "?"),
        severity=event.get("severity"),
    )
    log.info("gcp_decision.start")

    analyzer = _deserialise_analyzer(event)

    runbook_id, actions, rto = _select_runbook(analyzer)
    mode = _determine_mode(analyzer.severity, actions)
    log.info("gcp_decision.runbook", runbook_id=runbook_id, mode=mode, actions=actions, rto=rto)

    output = DecisionOutput(
        analyzer=analyzer,
        runbook_id=runbook_id,
        remediation_mode=mode,
        actions=actions,
        estimated_rto_sec=rto,
    )

    log.info("gcp_decision.done")
    return _serialise(output)


# ------------------------------------------------------------------
# Runbook selection
# ------------------------------------------------------------------

def _select_runbook(analyzer: AnalyzerOutput) -> tuple[str, list[str], int | None]:
    """
    1. Exact match by alarm_name in Firestore
    2. Capability-based catalog scan (heuristic)
    3. Generic fallback
    """
    alarm_name = analyzer.detector.alarm.alarm_name
    normalized = analyzer.detector.normalized_incident

    # 1. Try Firestore exact match
    firestore_runbook = _lookup_firestore_runbook(alarm_name)
    if firestore_runbook:
        runbook_id = firestore_runbook.get("runbook_id", alarm_name)
        actions = _resolve_actions_from_runbook(firestore_runbook, normalized)
        rto = firestore_runbook.get("estimated_rto_sec")
        return runbook_id, actions, rto

    # 2. Capability-based catalog scan
    if normalized and normalized.recommended_capabilities:
        for rb_id, rb in BUILTIN_RUNBOOKS.items():
            if not validate_runbook(rb):
                continue
            rb_capabilities = {
                step.get("capability") for step in rb.get("steps", [])
            }
            if rb_capabilities & set(normalized.recommended_capabilities):
                actions = _resolve_actions_from_capabilities(
                    normalized.recommended_capabilities, normalized
                )
                rto = rb.get("estimated_rto_sec", 300)
                return rb_id, actions, rto

    # 3. Generic fallback
    actions = _resolve_actions_from_capabilities(
        normalized.recommended_capabilities if normalized else ["open_change_request"],
        normalized,
    )
    return "generic-recovery", actions, None


def _lookup_firestore_runbook(alarm_name: str) -> dict[str, Any] | None:
    """Look up a runbook by alarm_name in Firestore."""
    try:
        from google.cloud import firestore

        db = firestore.Client(project=_PROJECT_ID or None)
        doc = db.collection(_RUNBOOK_COLLECTION).document(alarm_name).get()
        if doc.exists:
            return doc.to_dict()
        return None

    except ImportError:
        logger.warning("gcp_decision.firestore.not_available")
        return None
    except Exception as exc:
        logger.warning("gcp_decision.firestore.error", error=str(exc))
        return None


def _resolve_actions_from_runbook(
    runbook: dict[str, Any],
    normalized: NormalizedIncident | None,
) -> list[str]:
    """Resolve concrete GCP actions from a runbook's steps."""
    if not normalized:
        return []

    adapter = get_execution_adapter("gcp")
    actions = []
    for step in runbook.get("steps", []):
        capability = step.get("capability")
        if not capability:
            continue
        try:
            resolved = adapter.resolve_action(capability, normalized)
            actions.append(resolved["action"])
        except (ValueError, KeyError):
            continue
    return actions


def _resolve_actions_from_capabilities(
    capabilities: list[str],
    normalized: NormalizedIncident | None,
) -> list[str]:
    """Resolve GCP actions from a list of capabilities."""
    if not normalized:
        return []

    adapter = get_execution_adapter("gcp")
    actions = []
    for capability in capabilities:
        try:
            resolved = adapter.resolve_action(capability, normalized)
            actions.append(resolved["action"])
        except (ValueError, KeyError):
            continue
    return actions


# ------------------------------------------------------------------
# Mode determination
# ------------------------------------------------------------------

_DANGEROUS_PATTERNS = {"Delete", "Drop", "Terminate", "Destroy"}


def _determine_mode(severity: Severity, actions: list[str]) -> RemediationMode:
    """
    P1 → AUTO, P2 → APPROVE, P3 → MANUAL.
    Safety: dangerous actions force APPROVE regardless of severity.
    """
    # Safety override
    for action in actions:
        if any(pattern in action for pattern in _DANGEROUS_PATTERNS):
            return RemediationMode.APPROVE

    if severity == Severity.P1:
        return RemediationMode.AUTO
    elif severity == Severity.P2:
        return RemediationMode.APPROVE
    else:
        return RemediationMode.MANUAL


# ------------------------------------------------------------------
# Serialisation
# ------------------------------------------------------------------

def _deserialise_analyzer(event: dict[str, Any]) -> AnalyzerOutput:
    from dataclasses import fields

    detector_data = event["detector"]
    alarm_data = detector_data["alarm"]
    alarm = AlarmContext(**{
        k: alarm_data[k] for k in (f.name for f in fields(AlarmContext))
        if k in alarm_data
    })
    normalized_data = detector_data.get("normalized_incident")
    normalized = NormalizedIncident(**normalized_data) if normalized_data else None

    detector = DetectorOutput(
        alarm=alarm,
        log_insights_results=detector_data.get("log_insights_results", []),
        xray_trace_ids=detector_data.get("xray_trace_ids", []),
        related_metrics=detector_data.get("related_metrics", {}),
        normalized_incident=normalized,
    )

    return AnalyzerOutput(
        detector=detector,
        root_cause=event["root_cause"],
        severity=Severity(event["severity"]),
        confidence=float(event.get("confidence", 0.0)),
        similar_incidents=event.get("similar_incidents", []),
    )


def _serialise(output: DecisionOutput) -> dict[str, Any]:
    from dataclasses import asdict
    return json.loads(json.dumps(asdict(output), default=str))
