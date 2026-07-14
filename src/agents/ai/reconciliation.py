"""Reconciliation gate — deterministic grounding check (deterministic-tool-first).

Before an auto-remediation fires, verify the analyzer's *LLM* conclusions
(severity, root_cause) are grounded in the detector's *actual* evidence — alarm
state, metrics, logs, normalized incident. Ungrounded or hallucinated analysis is
never allowed to drive an unattended action: the gate downgrades AUTO → APPROVE so
a human reviews it. This is the last defence line for the Day-2 executor once it
runs real kubectl (`ONPREM_EXECUTOR_LIVE`).

Pure Python, no LLM — the whole point is that the *check* is deterministic even
though the thing it checks came from a model.

Pattern ref: AWSome AI Gateway "reconciliation gate / deterministic-tool-first".
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from src.agents.models import AnalyzerOutput, DetectorOutput, RemediationMode, Severity

# Alarm/monitor states that represent an actually-firing signal.
_FIRING_STATES = {"ALARM", "FIRING", "IN_ALARM", "BREACHING", "TRIGGERED"}

# Low-signal words to drop before comparing root_cause against evidence.
_STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "were", "of", "to", "in", "on", "and",
    "or", "for", "with", "by", "due", "this", "that", "from", "at", "as", "it",
    "its", "be", "been", "has", "have", "had", "which", "likely", "caused",
    "causing", "cause", "root", "high", "low", "error", "errors", "failure",
    "failed", "issue", "problem", "seems", "appears", "may", "might",
}

_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9_\-]{2,}")


@dataclass
class ReconciliationResult:
    grounded: bool
    issues: list[str] = field(default_factory=list)
    # When not grounded, the mode an AUTO decision must be downgraded to.
    mode_override: RemediationMode | None = None
    grounding_ratio: float = 1.0

    def to_dict(self) -> dict:
        return {
            "grounded": self.grounded,
            "issues": self.issues,
            "mode_override": self.mode_override.value if self.mode_override else None,
            "grounding_ratio": round(self.grounding_ratio, 2),
        }


def _tokens(text: str) -> set[str]:
    return {t for t in _TOKEN_RE.findall((text or "").lower()) if t not in _STOPWORDS}


def _evidence_text(detector: DetectorOutput) -> str:
    alarm = detector.alarm
    parts: list[str] = [
        alarm.alarm_name, alarm.namespace, alarm.metric_name, alarm.reason,
        " ".join(f"{k} {v}" for k, v in (alarm.dimensions or {}).items()),
    ]
    parts += list(detector.related_metrics.keys())
    parts += [str(r.get("@message", "")) for r in detector.log_insights_results[:20]]
    ni = detector.normalized_incident
    if ni is not None:
        parts += [
            ni.provider or "", ni.service or "", ni.resource_type or "",
            getattr(ni, "resource_id", "") or "", ni.signal_type or "",
        ]
    return " ".join(p for p in parts if p)


def reconcile(
    detector: DetectorOutput,
    analyzer: AnalyzerOutput,
    *,
    min_grounding: float = 0.3,
) -> ReconciliationResult:
    """Check whether the analyzer's conclusions are supported by detector evidence."""
    issues: list[str] = []

    # 1. The signal must actually be firing for any unattended action.
    state = (detector.alarm.state or "").upper()
    if state and state not in _FIRING_STATES:
        issues.append(f"alarm state {state!r} is not a firing state")

    # 2. There must be *some* evidence to reason from.
    has_evidence = bool(
        detector.related_metrics or detector.log_insights_results or detector.alarm.reason
    )
    if not has_evidence:
        issues.append("no supporting evidence (no metrics, logs, or alarm reason)")

    # 3. A high-severity (auto-executed) claim needs real model confidence.
    if analyzer.severity == Severity.P1 and analyzer.confidence < 0.5:
        issues.append(f"P1 severity with low confidence {analyzer.confidence:.2f}")

    # 4. When there is STRUCTURED evidence (logs/metrics), the root_cause
    #    narrative must overlap its vocabulary — a story about resources/metrics
    #    that never appear in the signal is a hallucination red flag. Skipped for
    #    thin-evidence signals (e.g. a normalized on-prem alert with no logs or
    #    metrics), where the overlap ratio is unreliable and would false-positive.
    ratio = 1.0
    if detector.log_insights_results or detector.related_metrics:
        evidence_kw = _tokens(_evidence_text(detector))
        rc_kw = _tokens(analyzer.root_cause)
        if rc_kw and evidence_kw:
            ratio = len(rc_kw & evidence_kw) / len(rc_kw)
            if ratio < min_grounding:
                issues.append(
                    f"root_cause grounding {ratio:.2f} < {min_grounding:.2f} "
                    "(root cause not supported by evidence — possible hallucination)"
                )

    grounded = not issues
    return ReconciliationResult(
        grounded=grounded,
        issues=issues,
        mode_override=None if grounded else RemediationMode.APPROVE,
        grounding_ratio=ratio,
    )


def apply_gate(mode: RemediationMode, result: ReconciliationResult) -> RemediationMode:
    """Downgrade an AUTO decision to the reconciliation override when ungrounded.

    Only ever downgrades (AUTO → APPROVE); never upgrades a human-gated decision.
    """
    if result.mode_override is None:
        return mode
    if mode == RemediationMode.AUTO:
        return result.mode_override
    return mode
