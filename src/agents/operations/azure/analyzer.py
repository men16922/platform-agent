"""
Azure Analyzer — Azure Function handler.

Receives DetectorOutput from Durable Functions orchestrator and:
  1. Sends context to Azure OpenAI GPT for root-cause reasoning
  2. Scores severity (P1 / P2 / P3)
  3. Looks up similar past incidents from Cosmos DB
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

_AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT", "")
_AZURE_OPENAI_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")
_AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")
_COSMOS_ENDPOINT = os.getenv("AZURE_COSMOS_ENDPOINT", "")
_COSMOS_DATABASE = os.getenv("AZURE_COSMOS_DATABASE", "platform-agent")
_INCIDENT_CONTAINER = os.getenv("AZURE_INCIDENT_CONTAINER", "incident-history")


def azure_function_handler(event: dict[str, Any]) -> dict[str, Any]:
    """
    Event: DetectorOutput dict (passed through Durable Functions orchestrator).
    """
    log = logger.bind(alarm_name=event.get("alarm", {}).get("alarm_name", "?"))
    log.info("azure_analyzer.start")

    detector = _deserialise_detector(event)

    root_cause, severity, confidence = _analyse(detector)
    log.info("azure_analyzer.llm_done", severity=severity, confidence=confidence)

    similar = _find_similar_incidents(detector.alarm.alarm_name)
    log.info("azure_analyzer.similar_done", count=len(similar))

    output = AnalyzerOutput(
        detector=detector,
        root_cause=root_cause,
        severity=severity,
        confidence=confidence,
        similar_incidents=similar,
    )

    log.info("azure_analyzer.done")
    return _serialise(output)


# ------------------------------------------------------------------
# LLM root-cause analysis (Azure OpenAI)
# ------------------------------------------------------------------

_SYSTEM_PROMPT = """\
You are an Azure incident response expert. Analyse the provided alert context and
log evidence, then return a JSON object with exactly these keys:
  {
    "root_cause": "<one paragraph, concise>",
    "severity":   "P1" | "P2" | "P3",
    "confidence": <float 0.0-1.0>
  }

Severity guide:
  P1 — production outage or data loss risk (e.g. AKS cluster down, SQL DB unresponsive)
  P2 — significant degradation, auto-remediable (e.g. pod OOM, function throttling)
  P3 — early warning, human review (e.g. CPU trending up, disk filling)

Return ONLY the JSON. No markdown fences.
"""


def _analyse(detector: DetectorOutput) -> tuple[str, Severity, float]:
    """Invoke Azure OpenAI GPT for root-cause analysis."""
    prompt = _build_prompt(detector)

    try:
        from openai import AzureOpenAI

        client = AzureOpenAI(
            azure_endpoint=_AZURE_OPENAI_ENDPOINT,
            api_version=_AZURE_OPENAI_API_VERSION,
        )

        response = client.chat.completions.create(
            model=_AZURE_OPENAI_DEPLOYMENT,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            max_tokens=1024,
            temperature=0.2,
        )

        text = response.choices[0].message.content
        parsed = _parse_llm_response(text)
        return (
            parsed["root_cause"],
            Severity(parsed["severity"]),
            float(parsed["confidence"]),
        )
    except ImportError:
        logger.warning("azure_analyzer.openai.not_available", reason="openai not installed")
        return _fallback_analysis(detector)
    except Exception as exc:
        logger.error("azure_analyzer.llm.error", error=str(exc))
        return _fallback_analysis(detector)


def _fallback_analysis(detector: DetectorOutput) -> tuple[str, Severity, float]:
    """Heuristic fallback when LLM is unavailable."""
    alarm = detector.alarm
    reason = alarm.reason.lower()
    normalized = detector.normalized_incident

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
        f"  [{r.get('TimeGenerated', r.get('@timestamp',''))}] {r.get('Message', r.get('@message',''))[:200]}"
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
Rule:      {alarm.alarm_name}
Namespace: {alarm.namespace}
Metric:    {alarm.metric_name}
State:     {alarm.state}
Reason:    {alarm.reason}
Dimensions: {json.dumps(alarm.dimensions)}

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
# Past incident lookup (Cosmos DB)
# ------------------------------------------------------------------

def _find_similar_incidents(alarm_name: str) -> list[str]:
    """Query Cosmos DB for similar past incidents."""
    try:
        from azure.cosmos import CosmosClient

        client = CosmosClient(_COSMOS_ENDPOINT, credential=_get_cosmos_credential())
        database = client.get_database_client(_COSMOS_DATABASE)
        container = database.get_container_client(_INCIDENT_CONTAINER)

        query = "SELECT c.id FROM c WHERE c.alarm_name = @alarm_name ORDER BY c.created_at DESC OFFSET 0 LIMIT 5"
        items = container.query_items(
            query=query,
            parameters=[{"name": "@alarm_name", "value": alarm_name}],
            enable_cross_partition_query=True,
        )

        return [item["id"] for item in items]

    except ImportError:
        logger.warning("azure_analyzer.cosmos.not_available")
        return []
    except Exception as exc:
        logger.warning("azure_analyzer.cosmos.error", error=str(exc))
        return []


def _get_cosmos_credential():
    """Get Cosmos DB credential (key or DefaultAzureCredential)."""
    key = os.getenv("AZURE_COSMOS_KEY", "")
    if key:
        return key
    try:
        from azure.identity import DefaultAzureCredential
        return DefaultAzureCredential()
    except ImportError:
        return ""


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
