"""
GCP Analyzer — Cloud Function handler.

Receives DetectorOutput from Cloud Workflows and:
  1. Sends context to Vertex AI Gemini for root-cause reasoning
  2. Scores severity (P1 / P2 / P3) based on LLM output + heuristics
  3. Looks up similar past incidents from Firestore
  4. Returns AnalyzerOutput for the Decision Agent
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

import structlog

from src.agents.models import (
    AlarmContext, AnalyzerOutput, DetectorOutput, NormalizedIncident, Severity
)

logger = structlog.get_logger(__name__)

_PROJECT_ID = os.getenv("GCP_PROJECT_ID", "")
_LOCATION = os.getenv("GCP_LOCATION", "asia-northeast3")
_MODEL_ID = os.getenv("VERTEX_MODEL_ID", "gemini-2.5-flash")
_INCIDENT_COLLECTION = os.getenv("INCIDENT_COLLECTION", "incident-history")


def cloud_function_handler(event: dict[str, Any]) -> dict[str, Any]:
    """
    Event: DetectorOutput dict (passed through Cloud Workflows).
    """
    log = logger.bind(alarm_name=event.get("alarm", {}).get("alarm_name", "?"))
    log.info("gcp_analyzer.start")

    detector = _deserialise_detector(event)

    root_cause, severity, confidence = _analyse(detector)
    log.info("gcp_analyzer.llm_done", severity=severity, confidence=confidence)

    similar = _find_similar_incidents(detector.alarm.alarm_name)
    log.info("gcp_analyzer.similar_done", count=len(similar))

    output = AnalyzerOutput(
        detector=detector,
        root_cause=root_cause,
        severity=severity,
        confidence=confidence,
        similar_incidents=similar,
    )

    log.info("gcp_analyzer.done")
    return _serialise(output)


# ------------------------------------------------------------------
# LLM root-cause analysis (Vertex AI Gemini)
# ------------------------------------------------------------------

_SYSTEM_PROMPT = """\
You are a GCP incident response expert. Analyse the provided alert context and
log evidence, then return a JSON object with exactly these keys:
  {
    "root_cause": "<one paragraph, concise>",
    "severity":   "P1" | "P2" | "P3",
    "confidence": <float 0.0-1.0>
  }

Severity guide:
  P1 — production outage or data loss risk (e.g. DB down, Cloud Run 5xx spike >50%)
  P2 — significant degradation, auto-remediable (e.g. pod OOM, consumer lag spike)
  P3 — early warning, human review (e.g. CPU trending up, single slow query)

Return ONLY the JSON. No markdown fences.
"""


def _analyse(detector: DetectorOutput) -> tuple[str, Severity, float]:
    """Invoke Vertex AI Gemini for root-cause analysis."""
    prompt = _build_prompt(detector)

    try:
        import vertexai
        from vertexai.generative_models import GenerativeModel

        vertexai.init(project=_PROJECT_ID or None, location=_LOCATION)
        model = GenerativeModel(
            _MODEL_ID,
            system_instruction=[_SYSTEM_PROMPT],
        )

        response = model.generate_content(prompt)
        text = response.text
        parsed = _parse_llm_response(text)
        return (
            parsed["root_cause"],
            Severity(parsed["severity"]),
            float(parsed["confidence"]),
        )
    except ImportError:
        logger.warning("gcp_analyzer.vertexai.not_available", reason="vertexai not installed")
        return _fallback_analysis(detector)
    except Exception as exc:
        logger.error("gcp_analyzer.llm.error", error=str(exc))
        return _fallback_analysis(detector)


def _fallback_analysis(detector: DetectorOutput) -> tuple[str, Severity, float]:
    """Heuristic fallback when LLM is unavailable."""
    alarm = detector.alarm
    reason = alarm.reason.lower()
    normalized = detector.normalized_incident

    # Simple heuristic severity based on signal
    if normalized and normalized.signal_type == "reliability":
        severity = Severity.P2
    elif any(word in reason for word in ("down", "outage", "unavailable", "crash")):
        severity = Severity.P1
    elif any(word in reason for word in ("high", "spike", "oom", "throttl")):
        severity = Severity.P2
    else:
        severity = Severity.P3

    root_cause = f"Heuristic analysis (LLM unavailable): {alarm.reason or 'Alert triggered'}"
    return root_cause, severity, 0.3


def _build_prompt(detector: DetectorOutput) -> str:
    alarm = detector.alarm
    normalized = detector.normalized_incident
    log_summary = "\n".join(
        f"  [{r.get('@timestamp','')}] [{r.get('@severity','')}] {r.get('@message','')[:200]}"
        for r in detector.log_insights_results[:10]
    ) or "  (no log results)"

    metrics_summary = "\n".join(
        f"  {k}: {v:.2f}" for k, v in detector.related_metrics.items()
    ) or "  (none)"

    normalized_summary = "(none)"
    if normalized:
        normalized_summary = (
            f"Provider:   {normalized.provider}\n"
            f"Service:    {normalized.service}\n"
            f"Resource:   {normalized.resource_type} / {normalized.resource_id}\n"
            f"Signal:     {normalized.signal_type}\n"
            f"Capabilities: {', '.join(normalized.recommended_capabilities) or '(none)'}"
        )

    return f"""\
## Alert
Policy:    {alarm.alarm_name}
Namespace: {alarm.namespace}
Metric:    {alarm.metric_name}
State:     {alarm.state}
Summary:   {alarm.reason}
Labels:    {json.dumps(alarm.dimensions)}

## Recent Log Errors (last 5 min)
{log_summary}

## Related Metrics
{metrics_summary}

## Normalized Incident
{normalized_summary}

Analyse and return the JSON object described in the system prompt.
"""


def _parse_llm_response(text: str) -> dict[str, Any]:
    text = re.sub(r"```json?\s*", "", text).strip(" `\n")
    parsed = json.loads(text)
    for key in ("root_cause", "severity", "confidence"):
        if key not in parsed:
            raise ValueError(f"LLM response missing key: {key}")
    return parsed


# ------------------------------------------------------------------
# Past incident lookup (Firestore)
# ------------------------------------------------------------------

def _find_similar_incidents(alarm_name: str) -> list[str]:
    """Query Firestore incident history for similar past incidents."""
    try:
        from google.cloud import firestore

        db = firestore.Client(project=_PROJECT_ID or None)
        collection = db.collection(_INCIDENT_COLLECTION)

        docs = (
            collection
            .where("alarm_name", "==", alarm_name)
            .order_by("created_at", direction=firestore.Query.DESCENDING)
            .limit(5)
            .stream()
        )

        return [doc.id for doc in docs]

    except ImportError:
        logger.warning("gcp_analyzer.firestore.not_available")
        return []
    except Exception as exc:
        logger.warning("gcp_analyzer.firestore.error", error=str(exc))
        return []


# ------------------------------------------------------------------
# Serialisation
# ------------------------------------------------------------------

def _deserialise_detector(event: dict[str, Any]) -> DetectorOutput:
    from dataclasses import fields

    alarm_data = event["alarm"]
    alarm = AlarmContext(**{
        k: alarm_data[k] for k in (f.name for f in fields(AlarmContext))
        if k in alarm_data
    })
    normalized_data = event.get("normalized_incident")
    normalized = NormalizedIncident(**normalized_data) if normalized_data else None

    return DetectorOutput(
        alarm=alarm,
        log_insights_results=event.get("log_insights_results", []),
        xray_trace_ids=event.get("xray_trace_ids", []),
        related_metrics=event.get("related_metrics", {}),
        normalized_incident=normalized,
    )


def _serialise(output: AnalyzerOutput) -> dict[str, Any]:
    from dataclasses import asdict
    return json.loads(json.dumps(asdict(output), default=str))
