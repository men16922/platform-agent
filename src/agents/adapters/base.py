"""
Common adapter contracts for provider-specific integrations.
"""

from __future__ import annotations

from typing import Any

from src.agents.models import NormalizedIncident


class SignalAdapter:
    provider = "unknown"

    def normalise(self, event: dict[str, Any]) -> NormalizedIncident:
        raise NotImplementedError

    def collect_observations(self, incident: NormalizedIncident) -> dict[str, Any]:
        return incident.observations


class ExecutionAdapter:
    provider = "unknown"

    def resolve_action(self, capability: str, incident: NormalizedIncident) -> dict[str, Any]:
        raise NotImplementedError

    # Declared 2026-09-01. All four execution adapters already implemented this
    # and `aws/executor.py::_build_action_params` already called it **through this
    # base type** — the contract simply did not say so. mypy strict is what
    # pointed at it (`"ExecutionAdapter" has no attribute "parameters_for_action"`);
    # no test asked about the method at all.
    #
    # ⚠️ Why an undeclared method mattered here more than usual: the call site
    # wraps it in `except Exception: pass` and falls through to an
    # **AWS-shaped alarm-dimension fallback**. A fifth provider whose adapter
    # satisfied this class (only `resolve_action` was required) would have raised
    # `AttributeError`, had it swallowed, and been handed AWS's parameter shape —
    # failing in the way that does not error, which is this repo's recurring cost.
    def parameters_for_action(
        self, action: str, incident: NormalizedIncident
    ) -> dict[str, list[str]]:
        raise NotImplementedError


# ------------------------------------------------------------------
# Incident reason — the words downstream keyword matching reads
# ------------------------------------------------------------------
#
# Where the rule's own name lives differs per provider, so the keys are looked
# up rather than special-cased. Every signal adapter in this package already
# writes them: Alertmanager `alertname`, GCP `policy_name`/`condition_name`,
# Azure `alert_rule` (all into ``source_metadata``), and the human-written text
# into ``observations``.
_RULE_NAME_KEYS = ("alertname", "policy_name", "condition_name", "alert_rule")
_DESCRIPTION_KEYS = ("summary", "description")


def incident_reason(incident: NormalizedIncident) -> str:
    """What actually fired, in words — the text downstream keyword matching reads.

    This is a **contract, not an SDK detail**: the rule name and the human
    description are normalised by every adapter, and several consumers score
    keywords over the result — AWS runbook selection (``aws/decision.py``) and
    the GCP/Azure severity fallback (``_fallback_analysis``), which grades an
    incident by looking for words like "outage"/"crash" in it. Anything not
    surfaced here is invisible to all of them.

    It lives here rather than in one provider's detector because it was already
    written provider-neutral (it looks up GCP and Azure keys) while only
    ``aws/detector.py`` called it — so GCP and Azure passed a single raw field
    through and lost the rule name their own operators had written. Keeping one
    copy is the same rule ``runbooks/schema.py::fits_resource`` follows.
    """
    metadata = incident.source_metadata or {}
    observations = incident.observations or {}
    parts = [
        str(metadata.get(key, "")).strip()
        for key in _RULE_NAME_KEYS
    ] + [
        str(observations.get(key, "")).strip()
        for key in _DESCRIPTION_KEYS
    ]
    reason = " ".join(part for part in parts if part)
    # Falling back to signal_type keeps the previous behaviour for any adapter
    # that carries none of these, rather than handing matching an empty string.
    return reason or (incident.signal_type or "")
