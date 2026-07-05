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

A runbook must declare at least one of ``actions`` or ``capabilities``,
otherwise the decision stage would resolve no remediation.
"""

from __future__ import annotations

from typing import Any

_LIST_OF_STR_FIELDS = (
    "actions",
    "capabilities",
    "namespaces",
    "keywords",
    "resource_types",
)


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

    if "rto_sec" in item and item["rto_sec"] is not None and not isinstance(item["rto_sec"], int):
        problems.append("rto_sec must be an integer or null")

    if "provider" in item and not isinstance(item["provider"], str):
        problems.append("provider must be a string")

    return problems


def is_valid_runbook(item: Any, *, require_alarm_name: bool = False) -> bool:
    """True when ``item`` satisfies the runbook contract."""
    return not validate_runbook(item, require_alarm_name=require_alarm_name)


def _is_list_of_str(value: Any) -> bool:
    return isinstance(value, list) and all(isinstance(v, str) for v in value)
