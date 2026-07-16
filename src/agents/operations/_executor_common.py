"""Provider-neutral helpers shared by the GCP and Azure Day-2 executors.

AWS runs through the generic ``operations/executor/handler.py``; GCP and Azure
have parallel serverless entrypoints (Cloud Function / Azure Function) that share
the same orchestration boilerplate — decision (de)serialisation, the action loop,
and the Slack incident report. Provider-specific pieces stay in each module:
the action→capability mapping, the incident-record backend (Firestore/Cosmos),
and single-action execution semantics.
"""

from __future__ import annotations

import json
from dataclasses import asdict, fields
from typing import Any, Callable

from src.agents.adapters.registry import get_execution_adapter
from src.agents.adapters.slack_client import post_webhook
from src.agents.models import (
    AlarmContext,
    AnalyzerOutput,
    DecisionOutput,
    DetectorOutput,
    ExecutorOutput,
    NormalizedIncident,
    RemediationMode,
    Severity,
)

# ``RemediationMode`` re-exported so caller modules can gate on AUTO/APPROVE
# without importing it twice.
__all__ = [
    "RemediationMode",
    "deserialise_decision",
    "serialise",
    "run_actions",
    "post_incident_slack",
]


def deserialise_decision(event: dict[str, Any]) -> DecisionOutput:
    """Rebuild a ``DecisionOutput`` from a plain state-machine event dict."""
    analyzer_data = event["analyzer"]
    detector_data = analyzer_data["detector"]
    alarm_data = detector_data["alarm"]

    alarm = AlarmContext(**{
        k: alarm_data[k] for k in (f.name for f in fields(AlarmContext))
        if k in alarm_data
    })
    normalized_data = detector_data.get("normalized_incident")
    normalized = NormalizedIncident(**normalized_data) if normalized_data else None

    detector = DetectorOutput(
        alarm=alarm,
        log_insights_results=detector_data.get("log_insights_results", []),
        xray_trace_ids=detector_data.get("xray_trace_ids", []),
        related_metrics=detector_data.get("related_metrics", {}),
        normalized_incident=normalized,
    )

    analyzer = AnalyzerOutput(
        detector=detector,
        root_cause=analyzer_data["root_cause"],
        severity=Severity(analyzer_data["severity"]),
        confidence=float(analyzer_data.get("confidence", 0.0)),
        similar_incidents=analyzer_data.get("similar_incidents", []),
    )

    return DecisionOutput(
        analyzer=analyzer,
        runbook_id=event["runbook_id"],
        remediation_mode=RemediationMode(event["remediation_mode"]),
        actions=event.get("actions", []),
        estimated_rto_sec=event.get("estimated_rto_sec"),
    )


def serialise(output: ExecutorOutput) -> dict[str, Any]:
    """JSON-round-trip an ``ExecutorOutput`` into a plain, serialisable dict."""
    return json.loads(json.dumps(asdict(output), default=str))


def run_actions(
    *,
    decision: DecisionOutput,
    adapter_key: str,
    execute_single_action: Callable[[str, NormalizedIncident, Any], dict[str, Any]],
    log: Any,
    log_prefix: str,
) -> tuple[list[str], list[str]]:
    """Run each remediation action, partitioning results into executed/skipped.

    ``execute_single_action`` is the provider-specific runner; everything else
    (adapter resolution, the loop, per-action logging) is identical across clouds.
    """
    executed: list[str] = []
    skipped: list[str] = []
    normalized = decision.analyzer.detector.normalized_incident

    if not normalized:
        log.warning(f"{log_prefix}.no_normalized_incident")
        return [], decision.actions

    adapter = get_execution_adapter(adapter_key)

    for action in decision.actions:
        try:
            log.info(f"{log_prefix}.action.start", action=action)
            result = execute_single_action(action, normalized, adapter)
            if result.get("success"):
                executed.append(action)
                log.info(f"{log_prefix}.action.success", action=action)
            else:
                skipped.append(action)
                log.warning(f"{log_prefix}.action.failed", action=action, error=result.get("error"))
        except Exception as exc:
            skipped.append(action)
            log.error(f"{log_prefix}.action.error", action=action, error=str(exc))

    return executed, skipped


def post_incident_slack(
    *,
    webhook_url: str,
    provider_label: str,
    incident_id: str,
    decision: DecisionOutput,
    executed: list[str],
    skipped: list[str],
    resolved: bool,
    log: Any,
) -> str | None:
    """Post the incident report to Slack. Returns ``None`` (webhook API has no ts).

    No-ops when ``webhook_url`` is empty. Any transport error is logged and
    swallowed so a Slack outage never fails the remediation pipeline.
    """
    if not webhook_url:
        return None

    alarm = decision.analyzer.detector.alarm
    severity = decision.analyzer.severity.value
    mode = decision.remediation_mode.value
    emoji = "✅" if resolved else "⚠️"

    blocks: list[dict[str, Any]] = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"{emoji} {provider_label} Incident: {incident_id}"},
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Alert:* {alarm.alarm_name}"},
                {"type": "mrkdwn", "text": f"*Severity:* {severity}"},
                {"type": "mrkdwn", "text": f"*Mode:* {mode}"},
                {"type": "mrkdwn", "text": f"*Runbook:* {decision.runbook_id}"},
            ],
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Root Cause:*\n{decision.analyzer.root_cause[:500]}"},
        },
    ]

    if executed:
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Executed:*\n{'  '.join(f'• {a}' for a in executed)}"},
        })

    if skipped:
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Skipped:*\n{'  '.join(f'• {a}' for a in skipped)}"},
        })

    try:
        post_webhook(webhook_url, {"blocks": blocks})
    except Exception as exc:
        log.warning("executor.slack.error", error=str(exc))

    return None
