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
from src.agents.runbooks.catalog import BUILTIN_RUNBOOKS, CAPABILITY_RUNBOOKS
from src.agents.runbooks.schema import fits_resource, is_destructive_action, normalise_runbook, validate_runbook

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

    runbook_id, actions, rto, steps = _select_runbook(analyzer)
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

    log.info(
        "decision.runbook",
        runbook_id=runbook_id, mode=mode, actions=actions, rto=rto,
        # Which plan shape the executor will walk — the flat list, or ordered
        # steps with conditions and per-step verification.
        step_count=len(steps),
    )

    output = DecisionOutput(
        analyzer=analyzer,
        runbook_id=runbook_id,
        remediation_mode=mode,
        actions=actions,
        steps=steps,
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


def _select_runbook(
    analyzer: AnalyzerOutput,
) -> tuple[str, list[str], int | None, list[dict[str, Any]]]:
    """
    Match the analyzer output against runbook registry.

    Priority:
      1. DynamoDB lookup (exact alarm_name match) — the operator override
      2. Heuristic over BOTH catalogs (scanned DynamoDB rows + built-ins),
         best score wins, DynamoDB rows winning ties
      3. generic-recovery fallback

    Tiers 2 and 3 used to be sequential, and that was not a priority rule so
    much as an accident of which catalog got scanned first: the scan tier
    returned *any* match it found and the built-in tier was never consulted.
    Measured live — a `KubePodNotReady` alert scored 1 against the seeded
    `eks-pod-oom` row and 3 against the built-in `health-check-failure`, and the
    weaker match won because the stale table happened to hold it. Two heuristics
    over two catalogs have to be one heuristic over the union, or the deployed
    table's staleness silently caps what can ever be selected.

    Operator precedence is preserved where it is actually expressed: tier 1 is
    untouched, and scanned rows are scored first so they win ties.
    """
    alarm     = analyzer.detector.alarm
    incident  = analyzer.detector.normalized_incident
    resource_type = incident.resource_type if incident else None

    def _plan(runbook: dict[str, Any]) -> tuple[str, list[str], int | None, list[dict[str, Any]]]:
        steps = _resolve_runbook_steps(runbook, analyzer)
        # When steps resolve, they ARE the plan and `actions` is derived from them
        # in step order — so the Slack report, the incident record and every
        # existing consumer keep seeing the same shape, just correctly ordered.
        actions = [s["action"] for s in steps] if steps else _resolve_runbook_actions(runbook, analyzer)
        return runbook["runbook_id"], actions, runbook.get("rto_sec"), steps

    dynamo_rb = _lookup_dynamo(alarm.alarm_name)
    if dynamo_rb:
        return _plan(dynamo_rb)

    # One heuristic over both catalogs. Scanned rows come first so they win
    # ties; duplicates (the seed is a copy of the built-ins) are harmless for
    # the same reason. No generic fallback inside the scoring — it is the
    # answer for "nothing fit", which is the line below.
    candidates = [*_scan_dynamo_candidates(), *_BUILTIN_RUNBOOKS.values()]
    registry_rb = _match_runbook_registry(
        alarm,
        analyzer.root_cause,
        candidates,
        allow_generic=False,
        resource_type=resource_type,
    )
    if registry_rb:
        return _plan(registry_rb)

    return _plan(_BUILTIN_RUNBOOKS["generic-recovery"])


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
    item = normalise_runbook(item)
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
        # DynamoDB hands back Decimals; coerce before validating so a stored
        # rto_sec does not disqualify an otherwise-good runbook.
        item = normalise_runbook(item)
        if validate_runbook(item, require_alarm_name=True):
            logger.warning(
                "decision.candidate.invalid",
                runbook_id=item.get("runbook_id") if isinstance(item, dict) else None,
            )
            continue
        valid.append(item)
    return valid


def _match_builtin(
    alarm: AlarmContext, root_cause: str, *, resource_type: str | None = None
) -> dict[str, Any]:
    candidate = _match_runbook_registry(
        alarm, root_cause, _BUILTIN_RUNBOOKS.values(), resource_type=resource_type
    )
    if candidate:
        return candidate
    # generic-recovery is the answer when nothing fits, so it is never subject to
    # the resource-type gate — that is what makes the gate safe to apply above.
    return _BUILTIN_RUNBOOKS["generic-recovery"]


def _fits_resource(runbook: dict[str, Any], resource_type: str | None) -> bool:
    """Can this runbook's plan actually apply to this kind of resource?

    ``resource_types`` has been declared on every runbook since the catalog
    existed, parsed into the dataclass and serialised back out — and never
    consulted by selection. So nothing stopped an RDS runbook being chosen for a
    Kubernetes workload, and the consequence is not a clean failure:
    `_resolve_runbook_actions` catches the unresolvable capability and falls
    back to the runbook's **hardcoded AWS action names**, handing the executor
    actions for the wrong provider entirely.

    The rule itself now lives with the contract that declares the field
    (`runbooks/schema.py::fits_resource`) because GCP and Azure need the same
    one; this stays as the local name the matcher below reads.
    """
    return fits_resource(runbook, resource_type)


def _match_runbook_registry(
    alarm: AlarmContext,
    root_cause: str,
    registry: Iterable[dict[str, Any]],
    *,
    allow_generic: bool = True,
    resource_type: str | None = None,
) -> dict[str, Any] | None:
    """Score a registry and return the best match, or None.

    ``allow_generic=False`` makes "nothing scored" answer None instead of the
    registry's own generic-recovery row. That distinction decides whether the
    NEXT priority tier gets consulted at all: the seeded DynamoDB table contains
    a generic-recovery row, so with the fallback enabled the scan tier answered
    every unmatched alarm itself and **the built-in registry tier was never
    reached in any deployed environment** — priority 3 of the documented four
    was dead the moment the table was seeded. Measured, not theorised: a live
    scan of `incident-runbooks` returns exactly the five originally-seeded ids.
    """
    text = f"{alarm.metric_name} {alarm.reason} {root_cause}".lower()

    best_score = 0
    best_rb: dict[str, Any] | None = None
    generic_rb: dict[str, Any] | None = None

    for rb in registry:
        if rb.get("runbook_id") == "generic-recovery":
            generic_rb = rb
            continue
        if not _fits_resource(rb, resource_type):
            continue
        score = 0
        if any(alarm.namespace.startswith(ns) for ns in rb.get("namespaces", [])):
            score += 2
        score += sum(1 for kw in rb.get("keywords", []) if kw.lower() in text)
        if score > best_score:
            best_score = score
            best_rb = rb

    if best_rb:
        return best_rb
    return generic_rb if allow_generic else None


def _resolve_runbook_steps(
    runbook: dict[str, Any], analyzer: AnalyzerOutput
) -> list[dict[str, Any]]:
    """Resolve a runbook's declared ``steps`` into executable, ordered entries.

    Until now only the flat ``capabilities`` list was resolved, which throws away
    everything the step schema exists to express: order, conditions, on_failure,
    and the per-step ``verify`` that says how to prove the step actually helped.
    A runbook could declare all of it and the executor would still run an
    unordered, unconditional list.

    Returns [] when the runbook declares no steps — the caller then keeps the
    flat path, so nothing changes for the runbooks that have always used it.
    """
    # The runbook row wins (an operator editing DynamoDB must be able to change
    # the plan). The built-in capability catalog fills in when the row declares
    # no steps — which was EVERY row: all five selectable runbook ids also exist
    # in CAPABILITY_RUNBOOKS with full step definitions, and nothing referenced
    # that catalog outside its own tests. Nine runbooks' worth of ordering,
    # conditions and verification were dead data.
    declared = runbook.get("steps") or CAPABILITY_RUNBOOKS.get(
        runbook.get("runbook_id", ""), {}
    ).get("steps") or []
    incident = analyzer.detector.normalized_incident
    if not declared or not incident:
        return []

    provider = incident.provider or "aws"
    try:
        execution_adapter = get_execution_adapter(provider)
    except Exception as exc:
        logger.warning(
            "decision.step_resolution.error",
            runbook_id=runbook.get("runbook_id"), provider=provider, error=str(exc),
        )
        return []

    resolved: list[dict[str, Any]] = []
    for index, step in enumerate(declared):
        if not isinstance(step, dict) or not step.get("capability"):
            continue
        try:
            action = execution_adapter.resolve_action(step["capability"], incident)["action"]
        except Exception as exc:
            # One unresolvable capability must not discard the whole plan; the
            # step is dropped and the rest still run in order.
            logger.warning(
                "decision.step_resolution.skipped",
                runbook_id=runbook.get("runbook_id"),
                capability=step.get("capability"), error=str(exc),
            )
            continue
        resolved.append({
            "name": step.get("name") or f"step-{index + 1}",
            "capability": step["capability"],
            "action": action,
            "parameters": step.get("parameters") or {},
            "condition": step.get("condition"),
            "on_failure": step.get("on_failure", "abort"),
            "verify": step.get("verify"),
        })
    return resolved


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

    Override: a destructive action forces APPROVE regardless of severity.
    The verb set is `runbooks.schema.DESTRUCTIVE_ACTION_PATTERNS` — this used to
    be three verbs inline here while GCP and Azure shared four, so
    `AWS-DestroyStack` was APPROVE there and **AUTO here**.
    """
    if any(is_destructive_action(a) for a in actions):
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
