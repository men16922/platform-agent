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
from src.agents.runbooks.capability_schema import evaluate_condition
from src.agents.runbooks.catalog import BUILTIN_RUNBOOKS
from src.agents.runbooks.schema import fits_resource, is_destructive_action, validate_runbook

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
        # Operator overrides are registered out-of-band, so a malformed one falls
        # back to the catalog instead of producing a broken decision downstream —
        # the reason AWS has validated its DynamoDB reads all along. Tier 2 below
        # was validating `BUILTIN_RUNBOOKS`, i.e. the *one* source that cannot be
        # hand-edited, while this tier used whatever the store returned.
        #
        # `require_alarm_name` stays at its default False: the lookup key here is
        # the **document id**, so a valid document need not repeat `alarm_name` as
        # a field. AWS passes True because its DynamoDB key *is* that attribute.
        # Passing True here would reject every correctly-registered runbook and
        # make this tier unreachable — the same shape as the inverted check that
        # once disabled tier 2.
        # The id default is applied *before* validating, so the check runs on the
        # runbook as it would actually be used. Non-dicts pass through untouched —
        # `validate_runbook` reports those itself and never raises, which is what
        # keeps a junk document a logged fallback rather than a 500.
        candidate = (
            {**firestore_runbook, "runbook_id": firestore_runbook.get("runbook_id", alarm_name)}
            if isinstance(firestore_runbook, dict)
            else firestore_runbook
        )
        problems = validate_runbook(candidate)
        if problems:
            logger.warning(
                "gcp_decision.override.invalid",
                alarm_name=alarm_name,
                problems=problems,
            )
        else:
            actions = _resolve_actions_from_runbook(candidate, normalized, analyzer.severity)
            return candidate["runbook_id"], actions, candidate.get("rto_sec")

    # 2. Capability-based catalog scan
    if normalized and normalized.recommended_capabilities:
        recommended = set(normalized.recommended_capabilities)
        for rb_id, rb in BUILTIN_RUNBOOKS.items():
            # `validate_runbook` returns the list of problems — empty means valid.
            # Skip on problems; the inverted form skipped every valid runbook and
            # made this whole tier unreachable.
            if validate_runbook(rb):
                continue
            # The match surface is the runbook's own `capabilities` list, which is
            # what the schema contract declares and what the AWS action resolver
            # reads. `steps` belongs to CAPABILITY_RUNBOOKS, not here — reading it
            # off a built-in entry always produced the empty set.
            # Capability overlap alone chose runbooks for resources they do not
            # apply to — and it failed quietly, because the unresolvable
            # capability is dropped rather than raised: `certificate-expiry` on
            # a Kubernetes workload came back selected, with its RTO, carrying
            # only the notify action. AWS has read this field since it added
            # `_fits_resource`; the rule is shared from `runbooks/schema.py`.
            if not fits_resource(rb, normalized.resource_type):
                continue
            if set(rb.get("capabilities", ())) & recommended:
                actions = _resolve_actions_from_capabilities(
                    normalized.recommended_capabilities, normalized
                )
                # First entry wins on overlap, as in the AWS catalog: `catalog.py`
                # documents that later entries are appended so they cannot steal a
                # selection an earlier one already made.
                return rb_id, actions, rb.get("rto_sec")

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
    severity: Severity | None = None,
) -> list[str]:
    """Resolve concrete GCP actions from a runbook's steps.

    Step ``condition`` is part of the runbook contract — `evaluate_condition`
    documents three forms (`previous_step_failed`, `severity_in`, `provider`) and
    the AWS executor has gated on it all along. This walk **ignored the field**,
    so an operator following the documented contract got every conditional step
    unconditionally: `{"previous_step_failed": true}` marks an *escalation* step,
    and running it always is the stronger remediation applied when nothing failed.

    ⚠️ Evaluated with the **initial** context, because this provider flattens
    steps into a flat action list at decision time and has no step-walking
    executor to update it. So `previous_step_failed` is False here and always
    will be: escalation steps are excluded rather than deferred. That is the
    honest half of the contract this side can keep — including them
    unconditionally was the other, worse, half.
    """
    if not normalized:
        return []

    context = {
        "severity": severity.value if severity is not None else None,
        "provider": normalized.provider,
        "previous_step_failed": False,
    }

    adapter = get_execution_adapter("gcp")
    actions = []
    for step in runbook.get("steps", []):
        if not evaluate_condition(step.get("condition"), context):
            logger.info(
                "gcp_decision.step.condition_false",
                step=step.get("name") or step.get("action"),
                condition=step.get("condition"),
            )
            continue
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

def _determine_mode(severity: Severity, actions: list[str]) -> RemediationMode:
    """
    P1 → AUTO, P2 → APPROVE, P3 → MANUAL.
    Safety: dangerous actions force APPROVE regardless of severity.
    """
    # Safety override
    if any(is_destructive_action(a) for a in actions):
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
