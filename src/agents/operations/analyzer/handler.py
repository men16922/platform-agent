"""
Analyzer Agent — Lambda handler.

Receives DetectorOutput from Step Functions and:
  1. Sends context to Bedrock (Claude) for root-cause reasoning
  2. Scores severity (P1 / P2 / P3) based on LLM output + heuristics
  3. Looks up similar past incidents from DynamoDB
  4. Returns AnalyzerOutput for the Decision Agent
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

import boto3
import structlog

from src.agents.models import (
    AlarmContext, AnalyzerOutput, DetectorOutput, NormalizedIncident, Severity
)

logger = structlog.get_logger(__name__)

_REGION        = os.getenv("AWS_REGION", "ap-northeast-2")
_MODEL_ID      = os.getenv("BEDROCK_MODEL_ID", "us.anthropic.claude-sonnet-4-6")
_INCIDENT_TABLE = os.getenv("INCIDENT_TABLE", "incident-history")

_BEDROCK = boto3.client("bedrock-runtime", region_name=_REGION)
_DYNAMO  = boto3.resource("dynamodb",      region_name=_REGION)


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """
    Event: DetectorOutput dict (passed through Step Functions state output).
    """
    log = logger.bind(alarm_name=event.get("alarm", {}).get("alarm_name", "?"))
    log.info("analyzer.start")

    detector = _deserialise_detector(event)

    root_cause, severity, confidence = _analyse(detector)
    log.info("analyzer.llm_done", severity=severity, confidence=confidence)

    similar = _find_similar_incidents(detector.alarm.alarm_name, severity)
    log.info("analyzer.similar_done", count=len(similar))

    output = AnalyzerOutput(
        detector=detector,
        root_cause=root_cause,
        severity=severity,
        confidence=confidence,
        similar_incidents=similar,
    )

    log.info("analyzer.done")
    return _serialise(output)


# ------------------------------------------------------------------
# LLM root-cause analysis
# ------------------------------------------------------------------

_SYSTEM_PROMPT = """\
You are an AWS incident response expert. Analyse the provided alarm context and
log evidence, then return a JSON object with exactly these keys:
  {
    "root_cause": "<one paragraph, concise>",
    "severity":   "P1" | "P2" | "P3",
    "confidence": <float 0.0-1.0>
  }

Severity guide:
  P1 — production outage or data loss risk (e.g. DB down, payment failures, >50% error rate)
  P2 — significant degradation, auto-remediable (e.g. pod OOM, Lambda throttling, lag spike)
  P3 — early warning, human review (e.g. CPU trending up, single slow query)

Return ONLY the JSON. No markdown fences.
"""


def _analyse(detector: DetectorOutput) -> tuple[str, Severity, float]:
    prompt = _build_prompt(detector)
    body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 1024,
        "system": _SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": prompt}],
    })

    try:
        resp   = _BEDROCK.invoke_model(
            modelId=_MODEL_ID,
            contentType="application/json",
            accept="application/json",
            body=body,
        )
        text   = json.loads(resp["body"].read())["content"][0]["text"]
        parsed = _parse_llm_response(text)
        return (
            parsed["root_cause"],
            Severity(parsed["severity"]),
            float(parsed["confidence"]),
        )
    except Exception as exc:
        logger.error("analyzer.llm.error", error=str(exc))
        # Safe default: treat as P2 to avoid silent under-reaction
        return (f"LLM analysis failed: {exc}", Severity.P2, 0.0)


def _build_prompt(detector: DetectorOutput) -> str:
    alarm = detector.alarm
    normalized = detector.normalized_incident
    log_summary = "\n".join(
        f"  [{r.get('@timestamp','')}] {r.get('@message','')[:200]}"
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
## Alarm
Name:      {alarm.alarm_name}
Namespace: {alarm.namespace}
Metric:    {alarm.metric_name}
State:     {alarm.state}
Reason:    {alarm.reason}
Dimensions: {json.dumps(alarm.dimensions)}

## Recent Log Errors (last 5 min)
{log_summary}

## Related Metrics
{metrics_summary}

## X-Ray Trace IDs
{', '.join(detector.xray_trace_ids[:5]) or '(none)'}

## Normalized Incident
{normalized_summary}

Analyse and return the JSON object described in the system prompt.
"""


def _parse_llm_response(text: str) -> dict[str, Any]:
    # Strip accidental markdown fences
    text = re.sub(r"```json?\s*", "", text).strip(" `\n")
    parsed = json.loads(text)
    # Validate keys
    for key in ("root_cause", "severity", "confidence"):
        if key not in parsed:
            raise ValueError(f"LLM response missing key: {key}")
    return parsed


# ------------------------------------------------------------------
# Past incident lookup (DynamoDB)
# ------------------------------------------------------------------

def _find_similar_incidents(alarm_name: str, severity: Severity) -> list[str]:
    """
    Query DynamoDB incident history table for similar past incidents.
    Table schema: PK=alarm_name, SK=incident_id, attr: severity, root_cause, resolved_at
    """
    try:
        table  = _DYNAMO.Table(_INCIDENT_TABLE)
        resp   = table.query(
            KeyConditionExpression="alarm_name = :a",
            ExpressionAttributeValues={":a": alarm_name},
            ScanIndexForward=False,  # most recent first
            Limit=5,
        )
        return [item["incident_id"] for item in resp.get("Items", [])]
    except Exception as exc:
        logger.warning("analyzer.dynamo.error", error=str(exc))
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
    return DetectorOutput(
        alarm=alarm,
        log_insights_results=event.get("log_insights_results", []),
        xray_trace_ids=event.get("xray_trace_ids", []),
        related_metrics=event.get("related_metrics", {}),
        normalized_incident=_deserialise_normalized_incident(normalized_data),
    )


def _deserialise_normalized_incident(event: dict[str, Any] | None) -> NormalizedIncident | None:
    if not event:
        return None
    return NormalizedIncident(**event)


def _serialise(output: AnalyzerOutput) -> dict[str, Any]:
    from dataclasses import asdict
    return json.loads(json.dumps(asdict(output), default=str))
