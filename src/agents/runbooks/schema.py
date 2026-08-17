"""
Runbook item schema contract.

Shared by the built-in catalog, the deploy-time seeder, and the decision-time
lookup so that operator-registered ``alarm_name`` overrides follow the same
shape as the built-in runbooks. Operators register overrides out-of-band
(directly into the ``incident-runbooks`` DynamoDB table), so this contract is
the single place that defines what a valid runbook item looks like.

A runbook item is a plain dict (DynamoDB-friendly) with:

  runbook_id      (required) str   — stable identifier
  alarm_name      (required for registry items) str — DynamoDB partition key
  actions         list[str]        — concrete executor actions (e.g. SSM docs)
  capabilities    list[str]        — provider-neutral capabilities resolved per provider
  namespaces      list[str]        — metric namespaces used for heuristic matching
  keywords        list[str]        — keywords used for heuristic matching
  resource_types  list[str]        — normalized resource types
  provider        str              — owning provider (default "aws")
  rto_sec         int | None       — estimated recovery time objective
  steps           list[dict]       — ordered capability steps; only ``condition``
                                     is validated here (see ``_step_problems``)

A runbook must declare at least one of ``actions`` or ``capabilities``,
otherwise the decision stage would resolve no remediation.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

_LIST_OF_STR_FIELDS = (
    "actions",
    "capabilities",
    "namespaces",
    "keywords",
    "resource_types",
)


def fits_resource(runbook: Any, resource_type: str | None) -> bool:
    """Can this runbook's plan actually apply to this kind of resource?

    ``resource_types`` is part of the contract above, and selection is the only
    thing that can honour it. AWS reads it; GCP and Azure matched on capability
    overlap alone, so 67 of 81 (runbook, resource_type) pairs AWS excludes were
    still selectable there — an incident on a Kubernetes workload could select
    ``certificate-expiry``, keep its RTO, and quietly drop the renew action
    because no adapter maps that capability to that resource type.

    Lives here rather than in a provider module because what is shared between
    the providers is the *contract*, not an SDK: a copy per provider is how the
    next fix lands in one of them and rots in the other.

    Unknown on either side means "do not exclude" — a runbook that declares no
    resource types is as broad as it was yesterday, and an incident whose
    resource type could not be inferred must not lose every candidate.
    """
    declared = (runbook.get("resource_types") if isinstance(runbook, dict) else None) or []
    if not declared or not resource_type:
        return True
    return resource_type in declared


# Actions whose *name* says they remove something. A plan carrying one of these
# never runs unattended, whatever the severity — the guardrail this repo states
# as "Delete/Drop/Terminate 액션은 강제 APPROVE".
#
# Kept here, once, because three provider decision modules each enforced it and
# they had already drifted: `gcp` and `azure` shared a four-verb set while
# `aws/decision.py` matched three verbs inline and was missing ``Destroy``. So an
# action named ``AWS-DestroyStack`` was APPROVE on two clouds and **AUTO — i.e.
# unattended — on the third**. Two copies is how a fix lands in one and rots in
# the other; here it was three, and the odd one out was the destructive path.
#
# Matched against the action name as the execution adapters emit it, which is
# ``PROVIDER-PascalCase`` for all four (``AWS-CleanupEBSVolume``,
# ``ONPREM-RolloutRestartWorkload``). Deliberately **not** case-folded: no
# adapter emits a lowercase action name, and a guard for a form nothing produces
# carries no load. If one ever does, this is the single place to widen.
DESTRUCTIVE_ACTION_PATTERNS = ("Delete", "Drop", "Terminate", "Destroy")


def is_destructive_action(action: Any) -> bool:
    """True when an action's name says it removes something.

    Operators register runbooks out-of-band (see the module docstring), so the
    action names this sees are not limited to the built-in catalog — which is
    exactly why the rule must not differ per provider.
    """
    return any(pattern in str(action) for pattern in DESTRUCTIVE_ACTION_PATTERNS)


def validate_runbook(item: Any, *, require_alarm_name: bool = False) -> list[str]:
    """
    Validate a runbook item against the shared contract.

    Returns a list of human-readable problems. An empty list means the item is
    valid. Never raises — callers decide whether to skip, log, or fail.
    """
    problems: list[str] = []

    if not isinstance(item, dict):
        return [f"runbook must be a dict, got {type(item).__name__}"]

    runbook_id = item.get("runbook_id")
    if not isinstance(runbook_id, str) or not runbook_id.strip():
        problems.append("runbook_id must be a non-empty string")

    if require_alarm_name:
        alarm_name = item.get("alarm_name")
        if not isinstance(alarm_name, str) or not alarm_name.strip():
            problems.append("alarm_name must be a non-empty string")

    for field in _LIST_OF_STR_FIELDS:
        if field in item and not _is_list_of_str(item[field]):
            problems.append(f"{field} must be a list of strings")

    has_actions = bool(item.get("actions")) and _is_list_of_str(item.get("actions"))
    has_capabilities = bool(item.get("capabilities")) and _is_list_of_str(item.get("capabilities"))
    if not has_actions and not has_capabilities:
        problems.append("runbook must declare at least one of 'actions' or 'capabilities'")

    if "rto_sec" in item and item["rto_sec"] is not None and not _is_integer_like(item["rto_sec"]):
        problems.append("rto_sec must be an integer or null")

    if "provider" in item and not isinstance(item["provider"], str):
        problems.append("provider must be a string")

    problems.extend(_step_problems(item.get("steps")))

    return problems


def _step_problems(steps: Any) -> list[str]:
    """
    Problems in a runbook's ``steps``, which this contract did not look at.

    Measured 2026-08-17: `validate_runbook` checked every top-level field and
    **nothing inside `steps`**, so tier 1 — the operator-registered store that
    M28 established is the side that *can* be malformed — handed unvalidated
    steps straight to the walk that reads them.

    Only ``condition`` is checked here, because that is the field whose malformed
    forms are silent rather than loud. A bad ``capability`` is dropped by
    `resolve_action` with a raised ValueError the caller already handles; a bad
    ``condition`` changes *whether a step runs at all*:

      - an unknown key (``previous_step_fail``) matches no branch in
        `evaluate_condition`, which returns True — so a step gated as an
        escalation runs on every incident;
      - a non-dict ``condition`` makes ``"previous_step_failed" in condition``
        raise TypeError from inside the walk, outside its try block, which is the
        500 the tier-1 validation comment says this check exists to prevent.

    Rejecting the runbook (rather than the step) is M28's established choice: a
    malformed hand-registered entry falls back to heuristic matching instead of
    producing a broken decision downstream. Never raises — same contract as the
    caller (`validate_runbook`), so a junk document stays a logged fallback.
    """
    from src.agents.runbooks.capability_schema import CONDITION_KEYS

    if steps is None:
        return []
    if not isinstance(steps, list):
        return [f"steps must be a list or null, got {type(steps).__name__}"]

    problems: list[str] = []
    for i, step in enumerate(steps):
        prefix = f"steps[{i}]"
        if not isinstance(step, dict):
            problems.append(f"{prefix} must be a dict, got {type(step).__name__}")
            continue

        condition = step.get("condition")
        if condition is None:
            continue
        if not isinstance(condition, dict):
            problems.append(
                f"{prefix}.condition must be a dict or null, "
                f"got {type(condition).__name__}"
            )
            continue

        unknown = sorted(set(condition) - set(CONDITION_KEYS))
        if unknown:
            problems.append(
                f"{prefix}.condition has unknown key(s) {unknown}; "
                f"supported: {sorted(CONDITION_KEYS)} — an unrecognised key is "
                "ignored by the evaluator, which makes the step unconditional"
            )
        if "previous_step_failed" in condition and not isinstance(
            condition["previous_step_failed"], bool
        ):
            problems.append(f"{prefix}.condition.previous_step_failed must be a boolean")
        if "severity_in" in condition and not _is_list_of_str(condition["severity_in"]):
            problems.append(
                f"{prefix}.condition.severity_in must be a list of strings "
                "(a bare string is matched as a substring, not as membership)"
            )
        if "provider" in condition and not isinstance(condition["provider"], str):
            problems.append(f"{prefix}.condition.provider must be a string")

    return problems


def is_valid_runbook(item: Any, *, require_alarm_name: bool = False) -> bool:
    """True when ``item`` satisfies the runbook contract."""
    return not validate_runbook(item, require_alarm_name=require_alarm_name)


def _is_list_of_str(value: Any) -> bool:
    return isinstance(value, list) and all(isinstance(v, str) for v in value)


def _is_integer_like(value: Any) -> bool:
    """
    True for an integer-valued number, whatever numeric type carries it.

    DynamoDB returns every number as ``Decimal``, and ``isinstance(Decimal(180), int)``
    is False — so a strict ``int`` check silently rejected every registry runbook
    that declared an ``rto_sec``. That is not a cosmetic validation nit: an invalid
    runbook is dropped from the candidate set, so *every* incident fell back to
    ``generic-recovery`` (notify only) instead of the restart/scale/rollback runbook
    it matched. Only ``generic-recovery`` survived, because its rto_sec is null.

    Strings stay invalid — the point is to accept the storage layer's numeric type,
    not to start parsing text.
    """
    if isinstance(value, bool):
        # bool is a subclass of int; an RTO of True/False is a typo, not a duration.
        return False
    if isinstance(value, int):
        return True
    if isinstance(value, (Decimal, float)):
        try:
            return int(value) == value
        except (ValueError, OverflowError):  # NaN / inf
            return False
    return False


def normalise_runbook(item: Any) -> Any:
    """
    Return the item with storage-layer numeric types coerced to plain ints.

    Applied at the DynamoDB read boundary so downstream code (RTO comparisons,
    Slack rendering, JSON serialisation) never has to know a ``Decimal`` could
    appear. Non-dicts and absent/None values pass through untouched.
    """
    if not isinstance(item, dict):
        return item
    rto = item.get("rto_sec")
    if rto is None or isinstance(rto, bool) or isinstance(rto, int):
        return item
    if _is_integer_like(rto):
        coerced = dict(item)
        coerced["rto_sec"] = int(rto)
        return coerced
    return item
