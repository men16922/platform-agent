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

    similar = _find_similar_incidents(detector.alarm.alarm_name)
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

When an "Operator-declared severity" is given, it is the classification a human
put in the alert rule ahead of time. Treat it as strong evidence and say in the
root_cause why you departed from it if you do. It is not binding — the evidence
can show an alert is worse or milder than its label — but disagreeing with it
silently is what it exists to prevent.

Return ONLY the JSON. No markdown fences.
"""


def _analyse(detector: DetectorOutput) -> tuple[str, Severity, float]:
    prompt = _build_prompt(detector)

    try:
        text   = _invoke_llm(_SYSTEM_PROMPT, prompt)
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


def _invoke_llm(system: str, user: str) -> str:
    """Return the model's raw JSON text from the configured backend.

    On-prem prioritises a local OpenAI-compatible model (Qwen via the MLX proxy)
    when ``ANALYZER_LLM_ENDPOINT`` is set; otherwise the cloud path uses Bedrock.
    Either backend returns the same ``{root_cause, severity, confidence}`` JSON,
    so the caller parses it identically.
    """
    endpoint = os.getenv("ANALYZER_LLM_ENDPOINT")
    if endpoint:
        return _invoke_openai_compatible(endpoint, system, user)
    return _invoke_bedrock(system, user)


def _invoke_openai_compatible(endpoint: str, system: str, user: str) -> str:
    """Local/offline path — OpenAI-compatible chat endpoint (e.g. Qwen on MLX)."""
    import requests

    model = os.getenv("ANALYZER_LLM_MODEL", "local-qwen")
    resp = requests.post(
        f"{endpoint.rstrip('/')}/chat/completions",
        json={
            "model": model,
            "max_tokens": 1024,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        },
        timeout=float(os.getenv("ANALYZER_LLM_TIMEOUT", "60")),
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def _invoke_bedrock(system: str, user: str) -> str:
    """Cloud path — Bedrock (Claude)."""
    body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 1024,
        "system": system,
        "messages": [{"role": "user", "content": user}],
    })
    resp = _BEDROCK.invoke_model(
        modelId=_MODEL_ID,
        contentType="application/json",
        accept="application/json",
        body=body,
    )
    return json.loads(resp["body"].read())["content"][0]["text"]


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
        # The alert's own summary/description is often the single richest piece of
        # evidence (e.g. "OOMKilled, memory limit 256Mi exceeded") — surface it so
        # the model can reason about the actual failure, not just the signal type.
        observations = normalized.observations or {}
        alert_text = " ".join(
            str(observations.get(k, "")) for k in ("summary", "description")
        ).strip()
        if alert_text:
            normalized_summary += f"\nAlert detail: {alert_text}"
        # The severity the *operator* wrote into the alert rule. Every signal
        # adapter has populated this since they were written — Alertmanager's
        # `severity` label, GCP/Azure severity, the AWS alarm state — and nothing
        # read it, here or anywhere else. So the one classification a human made
        # in advance was normalised, stored on the incident, and dropped, leaving
        # severity to be inferred from prose alone. That matters because severity
        # is what decides AUTO vs APPROVE: a rule labelled `warning` has been
        # observed being graded P1 and remediated with no human in the loop.
        # Surfaced as evidence, not as an override — the mapping from a provider's
        # severity vocabulary to P1/P2/P3 is a policy call, not this function's.
        if normalized.severity_hint:
            normalized_summary += f"\nOperator-declared severity: {normalized.severity_hint}"

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
    parsed = _extract_first_json_object(text)
    # Validate keys
    for key in ("root_cause", "severity", "confidence"):
        if key not in parsed:
            raise ValueError(f"LLM response missing key: {key}")
    return parsed


def _extract_first_json_object(text: str) -> dict[str, Any]:
    """Parse the first JSON object in ``text``, tolerating prose around it.

    Bedrock/Claude returns bare JSON (system prompt: "Return ONLY the JSON"), but
    local coder models (Qwen) often wrap it in commentary — ``raw_decode`` from
    the first brace consumes exactly one object and ignores any trailing text,
    which plain ``json.loads`` rejects with "Extra data".
    """
    start = text.find("{")
    if start == -1:
        raise ValueError("no JSON object found in LLM response")
    obj, _ = json.JSONDecoder().raw_decode(text[start:])
    if not isinstance(obj, dict):
        raise ValueError("LLM response is not a JSON object")
    return obj


# ------------------------------------------------------------------
# Past incident lookup (DynamoDB)
# ------------------------------------------------------------------

_SIMILAR_LIMIT = 5
# Rows read per lookup before we stop paging. A partition is one alarm_name and
# rows expire at 90 days (`executor.py` ttl), so this is generous for a real
# alarm; hitting it is logged rather than silently truncating the ordering.
_SIMILAR_SCAN_CAP = 500


def _find_similar_incidents(alarm_name: str) -> list[str]:
    """The most recent past incidents for this alarm, newest first.

    Table schema: PK=alarm_name, SK=incident_id, attr: severity, root_cause,
    created_at, resolved_at.

    ``ScanIndexForward=False`` used to sit here under the comment "most recent
    first". **It was not.** The sort key is `incident_id`
    (`src/stacks/incident_agent_stack.ts:30`) and that is `INC-<random hex>`
    (`executor.py:62`), so descending sort-key order is descending *hex* —
    unrelated to time. The five ids handed to a human were the five
    lexicographically largest in the partition.

    That is worse than arbitrary, because it is **stable**: a newly written
    incident enters the list only if its random id beats the current
    fifth-largest, and those odds fall as ``5/N``. So the list **freezes as the
    alarm accumulates history** — the exact opposite of what its reader is told,
    and the reader is a human deciding whether to approve a remediation
    (`executor.py`, the Slack "Past similar incidents" line).

    This key schema cannot answer "most recent", so the partition is paged and
    ordered here on `created_at`, which every row carries. That is what GCP
    (Firestore ``order_by("created_at", DESCENDING)``) and Azure (Cosmos
    ``ORDER BY c.created_at DESC``) already do — this makes AWS agree with the
    other two rather than inventing a third answer.

    `severity` used to be a parameter and was never read in the body; GCP and
    Azure never took it. Dropped rather than given a meaning it never had.
    """
    try:
        table = _DYNAMO.Table(_INCIDENT_TABLE)
        items: list[dict[str, Any]] = []
        kwargs: dict[str, Any] = {
            "KeyConditionExpression": "alarm_name = :a",
            "ExpressionAttributeValues": {":a": alarm_name},
        }
        while True:
            resp = table.query(**kwargs)
            items.extend(resp.get("Items", []))
            start_key = resp.get("LastEvaluatedKey")
            if not start_key or len(items) >= _SIMILAR_SCAN_CAP:
                if start_key:
                    logger.warning(
                        "analyzer.similar.scan_capped",
                        alarm_name=alarm_name,
                        read=len(items),
                        cap=_SIMILAR_SCAN_CAP,
                    )
                break
            kwargs["ExclusiveStartKey"] = start_key

        # Rows written before `created_at` existed sort last rather than crashing
        # the lookup — absent is older than any timestamp we have.
        items.sort(key=lambda i: str(i.get("created_at") or ""), reverse=True)
        return [i["incident_id"] for i in items[:_SIMILAR_LIMIT] if "incident_id" in i]
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
