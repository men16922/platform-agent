"""
Canary judgment — the agent as the release gate.

Stage 1 of the AnalysisTemplate work let Prometheus abort a bad canary on a raw
metric (container restarts). That answers "is it crashing", which is the easy
half. This is the half only this project can do: the same detect→analyze→decide
pipeline that handles incidents also judges a release, so the canary gate inherits
the LLM's root-cause reasoning and confidence instead of a single threshold.

Layering (D19 stays intact): Argo Rollouts remains the k8s-native progressive
delivery mechanism and the cloud-neutral deployment runner is untouched. Rollouts
simply *consumes* the agent as an AnalysisRun provider — the agent is not
reimplementing progressive delivery.

The contract with Argo's `web` provider is deliberately tiny: one JSON object
with a scalar ``verdict`` it can assert on via jsonPath. Everything else in the
payload is for humans reading the AnalysisRun afterwards.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

#: Where to look for alerts actually firing against the canary. Empty means the
#: gate has no way to observe the canary — which is `unknown`, never `pass`.
ALERT_SOURCE_ENV = "CANARY_ALERT_SOURCE"

#: Returned when the agent cannot form an opinion. Treated as a FAILURE by the
#: AnalysisTemplate's successCondition: a gate that cannot judge must not promote.
VERDICT_UNKNOWN = "unknown"
VERDICT_PASS = "pass"
VERDICT_FAIL = "fail"

#: Below this the analysis is not trustworthy enough to promote on. 0.0 means the
#: heuristic fallback ran (no model reachable), which must never read as approval.
DEFAULT_MIN_CONFIDENCE = 0.4


@dataclass
class CanaryVerdict:
    verdict: str
    confidence: float
    reason: str
    severity: str = ""
    runbook_id: str = ""
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            # `verdict` is the only field Argo asserts on (jsonPath {$.verdict}).
            "verdict": self.verdict,
            "confidence": round(self.confidence, 4),
            "reason": self.reason,
            "severity": self.severity,
            "runbook_id": self.runbook_id,
            "details": self.details,
        }


def _as_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def judge_from_analysis(
    analysis: dict[str, Any],
    *,
    min_confidence: float = DEFAULT_MIN_CONFIDENCE,
    failing_severities: tuple[str, ...] = ("P1", "P2"),
) -> CanaryVerdict:
    """
    Turn a pipeline result into a promote/abort verdict.

    Three rules, each chosen so the *safe* direction is the default:

    * **No signal → pass.** If the pipeline found nothing wrong there is nothing
      to abort on; a canary must not be blocked because the workload is quiet.
    * **Low confidence → unknown (i.e. do not promote).** Confidence 0.0 is the
      heuristic fallback that runs when no model is reachable. Promoting on that
      would let an offline analyzer silently rubber-stamp every release.
    * **Severe finding → fail.** P1/P2 during a canary is exactly the situation
      the gate exists for.
    """
    severity = str(analysis.get("severity") or "")
    confidence = _as_float(analysis.get("confidence"))
    root_cause = str(analysis.get("root_cause") or "")
    runbook_id = str(analysis.get("runbook_id") or "")
    details = {
        "actions": analysis.get("actions") or [],
        "remediation_mode": analysis.get("remediation_mode") or "",
        "trace_id": analysis.get("trace_id") or "",
    }

    if not severity:
        return CanaryVerdict(
            verdict=VERDICT_PASS,
            confidence=confidence,
            reason="no incident signal for this canary",
            details=details,
        )

    if confidence < min_confidence:
        return CanaryVerdict(
            verdict=VERDICT_UNKNOWN,
            confidence=confidence,
            reason=(
                f"analysis confidence {confidence:.2f} below {min_confidence:.2f} "
                "— refusing to promote on an untrustworthy judgment"
            ),
            severity=severity,
            runbook_id=runbook_id,
            details=details,
        )

    if severity in failing_severities:
        return CanaryVerdict(
            verdict=VERDICT_FAIL,
            confidence=confidence,
            reason=f"{severity}: {root_cause}"[:300],
            severity=severity,
            runbook_id=runbook_id,
            details=details,
        )

    return CanaryVerdict(
        verdict=VERDICT_PASS,
        confidence=confidence,
        reason=f"{severity} is below the abort threshold: {root_cause}"[:300],
        severity=severity,
        runbook_id=runbook_id,
        details=details,
    )


def fetch_canary_alerts(
    namespace: str,
    pod_prefix: str,
    *,
    alert_source: str = "",
    http_get: Any = None,
    timeout: float = 10.0,
) -> list[dict[str, Any]] | None:
    """Return the alerts actually firing against this canary.

    ``None`` means "could not look" (no source configured, or it was
    unreachable) — deliberately distinct from ``[]``, which means "looked and
    the canary is quiet". Collapsing the two is how a gate starts approving
    releases it never observed.
    """
    source = alert_source or os.getenv(ALERT_SOURCE_ENV, "")
    if not source:
        return None

    fetch = http_get
    if fetch is None:  # pragma: no cover - exercised live, injected in tests
        import requests

        def fetch(url, timeout):
            resp = requests.get(url, timeout=timeout)
            resp.raise_for_status()
            return resp.json()

    try:
        alerts = fetch(f"{source.rstrip('/')}/api/v2/alerts?active=true", timeout=timeout)
    except Exception:
        return None
    if not isinstance(alerts, list):
        return None

    matched = []
    for alert in alerts:
        labels = (alert or {}).get("labels") or {}
        if labels.get("namespace") != namespace:
            continue
        # Rollouts gives us the canary ReplicaSet's pod-template-hash; stable pods
        # live under a different hash, so prefix matching is what keeps a stable-pod
        # alert from aborting a healthy canary.
        pod = str(labels.get("pod") or "")
        if pod_prefix and not pod.startswith(pod_prefix):
            continue
        matched.append(alert)
    return matched


def judge_observed_canary(
    namespace: str,
    pod_prefix: str,
    *,
    run_pipeline: Any,
    alert_source: str = "",
    http_get: Any = None,
    min_confidence: float = DEFAULT_MIN_CONFIDENCE,
) -> CanaryVerdict:
    """
    Judge a canary from what is ACTUALLY firing against it.

    The bug this exists to fix: the AnalysisTemplate used to post a synthetic
    "CanaryUnderJudgement" alert and ask the analyzer what it thought. But that
    payload asserts a problem, so the analyzer — correctly — reported one. Live,
    a perfectly healthy canary came back ``fail`` with confidence 0.80 and a
    fluent explanation. The "no signal → pass" rule was unreachable, because the
    gate manufactured the signal it then judged.

    So the caller now supplies IDENTITY, not a verdict-shaped claim, and the
    gate goes and looks.
    """
    alerts = fetch_canary_alerts(
        namespace, pod_prefix, alert_source=alert_source, http_get=http_get
    )

    if alerts is None:
        return CanaryVerdict(
            verdict=VERDICT_UNKNOWN,
            confidence=0.0,
            reason=(
                "no reachable alert source — cannot tell a quiet canary from an "
                "unobserved one, so refusing to promote"
            ),
        )

    if not alerts:
        return CanaryVerdict(
            verdict=VERDICT_PASS,
            confidence=1.0,
            reason=f"no alerts firing for {pod_prefix}* in {namespace}",
        )

    return judge_canary(
        {"status": "firing", "alerts": alerts},
        run_pipeline=run_pipeline,
        min_confidence=min_confidence,
    )


def judge_canary(
    signal: dict[str, Any],
    *,
    run_pipeline: Any,
    min_confidence: float = DEFAULT_MIN_CONFIDENCE,
) -> CanaryVerdict:
    """
    Run the analysis pipeline over a canary's signal and return a verdict.

    ``run_pipeline`` is injected so this stays testable without a live analyzer.
    Execution is never triggered — judging a release must not remediate it, or a
    canary check would silently become an unreviewed remediation.
    """
    try:
        analysis = run_pipeline(signal, execute=False)
    except Exception as exc:  # pragma: no cover - defensive
        return CanaryVerdict(
            verdict=VERDICT_UNKNOWN,
            confidence=0.0,
            reason=f"analysis failed: {exc}"[:300],
        )
    return judge_from_analysis(analysis, min_confidence=min_confidence)
