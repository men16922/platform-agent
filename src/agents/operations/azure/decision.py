"""
Azure Decision — Azure Function handler.

Receives AnalyzerOutput from Durable Functions orchestrator and:
  1. Selects the appropriate runbook from Cosmos DB
  2. Determines remediation mode (AUTO / APPROVE / MANUAL)
  3. Resolves concrete actions via Azure execution adapter
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

_COSMOS_ENDPOINT = os.getenv("AZURE_COSMOS_ENDPOINT", "")
_COSMOS_DATABASE = os.getenv("AZURE_COSMOS_DATABASE", "platform-agent")
_RUNBOOK_CONTAINER = os.getenv("AZURE_RUNBOOK_CONTAINER", "incident-runbooks")


def azure_function_handler(event: dict[str, Any]) -> dict[str, Any]:
    """
    Event: AnalyzerOutput dict (Durable Functions state output from Analyzer).
    """
    log = logger.bind(
        alarm_name=event.get("detector", {}).get("alarm", {}).get("alarm_name", "?"),
        severity=event.get("severity"),
    )
    log.info("azure_decision.start")

    analyzer = _deserialise_analyzer(event)

    runbook_id, actions, rto = _select_runbook(analyzer)
    mode = _determine_mode(analyzer.severity, actions)
    log.info("azure_decision.runbook", runbook_id=runbook_id, mode=mode, actions=actions, rto=rto)

    output = DecisionOutput(
        analyzer=analyzer,
        runbook_id=runbook_id,
        remediation_mode=mode,
        actions=actions,
        estimated_rto_sec=rto,
    )

    log.info("azure_decision.done")
    return _serialise(output)


# ------------------------------------------------------------------
# Runbook selection
# ------------------------------------------------------------------

def _select_runbook(analyzer: AnalyzerOutput) -> tuple[str, list[str], int | None]:
    """
    1. Exact match by alarm_name in Cosmos DB
    2. Capability-based catalog scan (heuristic)
    3. Generic fallback
    """
    alarm_name = analyzer.detector.alarm.alarm_name
    normalized = analyzer.detector.normalized_incident

    # 1. Try Cosmos DB exact match
    cosmos_runbook = _lookup_cosmos_runbook(alarm_name)
    if cosmos_runbook:
        # Same contract as GCP tier 1, and the same reason AWS validates its
        # DynamoDB reads: an override is hand-registered out-of-band, so a
        # malformed one must fall back to the catalog rather than drive a
        # decision. Tier 2 below validated `BUILTIN_RUNBOOKS` — the one source
        # that cannot be malformed — while this tier validated nothing.
        #
        # `require_alarm_name` stays False: the Cosmos item id is the alarm name,
        # so the document need not carry it as a field (AWS's DynamoDB key is the
        # attribute, which is why it passes True).
        # Id default applied before validating, so the check runs on the runbook
        # as it would be used; non-dicts pass through for `validate_runbook` to
        # report rather than raising here.
        candidate = (
            {**cosmos_runbook, "runbook_id": cosmos_runbook.get("runbook_id", alarm_name)}
            if isinstance(cosmos_runbook, dict)
            else cosmos_runbook
        )
        problems = validate_runbook(candidate)
        if problems:
            logger.warning(
                "azure_decision.override.invalid",
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


def _lookup_cosmos_runbook(alarm_name: str) -> dict[str, Any] | None:
    """Look up a runbook by alarm_name in Cosmos DB."""
    try:
        from azure.cosmos import CosmosClient

        client = CosmosClient(_COSMOS_ENDPOINT, credential=_get_cosmos_credential())
        database = client.get_database_client(_COSMOS_DATABASE)
        container = database.get_container_client(_RUNBOOK_CONTAINER)

        try:
            item = container.read_item(item=alarm_name, partition_key=alarm_name)
            return item
        except Exception:
            return None

    except ImportError:
        logger.warning("azure_decision.cosmos.not_available")
        return None
    except Exception as exc:
        logger.warning("azure_decision.cosmos.error", error=str(exc))
        return None


def _get_cosmos_credential():
    key = os.getenv("AZURE_COSMOS_KEY", "")
    if key:
        return key
    try:
        from azure.identity import DefaultAzureCredential
        return DefaultAzureCredential()
    except ImportError:
        return ""


def _resolve_actions_from_runbook(
    runbook: dict[str, Any],
    normalized: NormalizedIncident | None,
    severity: Severity | None = None,
) -> list[str]:
    """Resolve concrete Azure actions from a runbook's steps.

    Same contract, and same gap, as the GCP walk — see the docstring there.
    Step ``condition`` was not read at all, so `{"previous_step_failed": true}`
    (an escalation step) was emitted unconditionally. Evaluated here with the
    initial context: this side flattens steps at decision time, so escalation
    steps are excluded rather than deferred.
    """
    if not normalized:
        return []

    context = {
        "severity": severity.value if severity is not None else None,
        "provider": normalized.provider,
        "previous_step_failed": False,
    }

    adapter = get_execution_adapter("azure")
    actions = []
    for step in runbook.get("steps", []):
        if not evaluate_condition(step.get("condition"), context):
            logger.info(
                "azure_decision.step.condition_false",
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
    if not normalized:
        return []

    adapter = get_execution_adapter("azure")
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
