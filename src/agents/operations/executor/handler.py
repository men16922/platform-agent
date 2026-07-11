"""
Executor Agent — Lambda handler.

Receives DecisionOutput from Step Functions and:
  1. Executes SSM Automation documents for AUTO / APPROVE modes
  2. Skips execution for MANUAL mode (ticket creation only)
  3. Posts a Slack incident report (root cause + actions taken + prevention)
  4. Records the incident in DynamoDB for future similar-incident lookup
"""

from __future__ import annotations

import json
import os
import time
import uuid
from typing import Any

import boto3
import structlog

from src.agents.adapters.registry import get_execution_adapter
from src.agents.adapters.slack_client import post_webhook
from src.agents.models import (
    AlarmContext, AnalyzerOutput, DetectorOutput, DecisionOutput,
    ExecutorOutput, NormalizedIncident, RemediationMode, Severity
)
from src.agents.operations.activity_writer import record_agent_activity

logger = structlog.get_logger(__name__)

_REGION         = os.getenv("AWS_REGION", "ap-northeast-2")
_SLACK_WEBHOOK  = os.getenv("SLACK_WEBHOOK_URL", "")
_INCIDENT_TABLE = os.getenv("INCIDENT_TABLE", "incident-history")

_SSM    = boto3.client("ssm",      region_name=_REGION)
_DYNAMO = boto3.resource("dynamodb", region_name=_REGION)


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """
    Event: DecisionOutput dict (Step Functions state output from Decision Agent).
    """
    decision = _deserialise_decision(event)
    alarm    = decision.analyzer.detector.alarm
    log = logger.bind(
        alarm_name=alarm.alarm_name,
        mode=decision.remediation_mode.value,
        runbook_id=decision.runbook_id,
    )
    log.info("executor.start")

    incident_id     = f"INC-{uuid.uuid4().hex[:8].upper()}"
    executed: list[str] = []
    skipped:  list[str] = []

    if decision.remediation_mode in (RemediationMode.AUTO, RemediationMode.APPROVE):
        executed, skipped = _run_ssm_actions(decision, log)
    else:
        skipped = decision.actions
        log.info("executor.manual_mode", skipped=skipped)

    resolved = bool(executed) and not skipped

    slack_ts = _post_slack_report(
        incident_id=incident_id,
        decision=decision,
        executed=executed,
        skipped=skipped,
        resolved=resolved,
    )

    _record_incident(
        incident_id=incident_id,
        decision=decision,
        executed=executed,
        resolved=resolved,
    )

    _record_activity(
        incident_id=incident_id,
        decision=decision,
        executed=executed,
    )

    output = ExecutorOutput(
        decision=decision,
        executed_actions=executed,
        skipped_actions=skipped,
        slack_ts=slack_ts,
        incident_id=incident_id,
        resolved=resolved,
    )

    log.info("executor.done", incident_id=incident_id, resolved=resolved)
    return _serialise(output)


# ------------------------------------------------------------------
# SSM Automation
# ------------------------------------------------------------------

def _run_ssm_actions(
    decision: DecisionOutput, log: Any
) -> tuple[list[str], list[str]]:
    executed: list[str] = []
    skipped:  list[str] = []
    alarm = decision.analyzer.detector.alarm
    normalized_incident = decision.analyzer.detector.normalized_incident
    provider = normalized_incident.provider if normalized_incident else "aws"

    for action in decision.actions:
        params = _build_action_params(action, alarm, normalized_incident, provider)

        if provider != "aws":
            try:
                _run_external_action(provider, action, params, log)
                executed.append(action)
            except Exception as exc:
                log.error("executor.external.failed", provider=provider, action=action, error=str(exc))
                skipped.append(action)
            continue

        # AWS path: execute via SSM Automation
        try:
            resp = _SSM.start_automation_execution(
                DocumentName    = action,
                DocumentVersion = "$DEFAULT",
                Parameters      = params,
            )
            execution_id = resp["AutomationExecutionId"]
            log.info("executor.ssm.started", action=action, execution_id=execution_id)

            # Poll for terminal state (max 5 min for AUTO, skip polling for APPROVE)
            if decision.remediation_mode == RemediationMode.AUTO:
                _wait_for_ssm(_SSM, execution_id, log)

            executed.append(action)
        except _SSM.exceptions.AutomationDefinitionNotFoundException:
            log.warning("executor.ssm.not_found", action=action)
            skipped.append(action)
        except Exception as exc:
            # Primary region execution failed; execute retry on fallback region
            failover_region = os.getenv("AWS_FAILOVER_REGION", "us-east-1")
            log.warning(
                "executor.ssm.primary_failed.retry_failover",
                action=action,
                primary_region=_REGION,
                failover_region=failover_region,
                error=str(exc)
            )
            try:
                ssm_failover = boto3.client("ssm", region_name=failover_region)
                resp = ssm_failover.start_automation_execution(
                    DocumentName    = action,
                    DocumentVersion = "$DEFAULT",
                    Parameters      = params,
                )
                execution_id = resp["AutomationExecutionId"]
                log.info("executor.ssm.failover.started", action=action, execution_id=execution_id)

                if decision.remediation_mode == RemediationMode.AUTO:
                    _wait_for_ssm(ssm_failover, execution_id, log)

                executed.append(action)
            except Exception as failover_exc:
                log.error(
                    "executor.ssm.failover_failed",
                    action=action,
                    failover_region=failover_region,
                    error=str(failover_exc)
                )
                skipped.append(action)

    return executed, skipped


def _build_action_params(
    action: str,
    alarm: AlarmContext,
    normalized_incident: NormalizedIncident | None,
    provider: str,
) -> dict[str, list[str]]:
    """Resolve action parameters via the provider's ExecutionAdapter."""
    if normalized_incident:
        try:
            params = get_execution_adapter(provider).parameters_for_action(action, normalized_incident)
            if params:
                return params
        except Exception:
            pass

    # AWS alarm-dimension fallback (used when normalized_incident is unavailable)
    base: dict[str, list[str]] = {}
    if "EKS" in action or "Pod" in action:
        cluster = alarm.dimensions.get("ClusterName", "")
        ns      = alarm.dimensions.get("Namespace", "default")
        pod     = alarm.dimensions.get("PodName", "")
        if cluster: base["ClusterName"] = [cluster]
        if ns:      base["Namespace"]   = [ns]
        if pod:     base["PodName"]     = [pod]
    elif "Lambda" in action:
        fn = alarm.dimensions.get("FunctionName", "")
        if fn: base["FunctionName"] = [fn]
    elif "RDS" in action:
        db = alarm.dimensions.get("DBInstanceIdentifier", "")
        if db: base["DBInstanceIdentifier"] = [db]
    return base


# Keep old name as alias so existing tests that import _build_ssm_params still work
def _build_ssm_params(
    action: str,
    alarm: AlarmContext,
    normalized_incident: NormalizedIncident | None = None,
) -> dict[str, list[str]]:
    provider = normalized_incident.provider if normalized_incident else "aws"
    return _build_action_params(action, alarm, normalized_incident, provider)


def _wait_for_ssm(client: Any, execution_id: str, log: Any, timeout_sec: int = 300) -> None:
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        resp   = client.get_automation_execution(AutomationExecutionId=execution_id)
        status = resp["AutomationExecution"]["AutomationExecutionStatus"]
        if status in {"Success", "Failed", "Cancelled", "TimedOut"}:
            log.info("executor.ssm.terminal", execution_id=execution_id, status=status)
            return
        time.sleep(10)
    log.warning("executor.ssm.poll_timeout", execution_id=execution_id)


# ------------------------------------------------------------------
# Slack report
# ------------------------------------------------------------------

_SEVERITY_EMOJI = {Severity.P1: ":red_circle:", Severity.P2: ":large_yellow_circle:", Severity.P3: ":large_green_circle:"}
_SEVERITY_COLOR = {Severity.P1: "#E74C3C",      Severity.P2: "#F39C12",               Severity.P3: "#2ECC71"}


def _post_slack_report(
    incident_id: str,
    decision: DecisionOutput,
    executed: list[str],
    skipped: list[str],
    resolved: bool,
) -> str | None:
    if not _SLACK_WEBHOOK:
        logger.warning("executor.slack.skip", reason="SLACK_WEBHOOK_URL not set")
        return None

    analyzer = decision.analyzer
    alarm    = analyzer.detector.alarm
    sev      = analyzer.severity
    emoji    = _SEVERITY_EMOJI[sev]
    color    = _SEVERITY_COLOR[sev]

    executed_text = "\n".join(f"  ✅ `{a}`" for a in executed) or "  (none)"
    skipped_text  = "\n".join(f"  ⏭ `{a}`" for a in skipped)  or "  (none)"

    payload = {
        "attachments": [{
            "color": color,
            "blocks": [
                {
                    "type": "header",
                    "text": {"type": "plain_text", "text": f"{emoji} [{sev.value}] {alarm.alarm_name}"}
                },
                {
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": f"*Incident ID:*\n`{incident_id}`"},
                        {"type": "mrkdwn", "text": f"*Status:*\n{'Resolved ✅' if resolved else 'In Progress ⚠️'}"},
                        {"type": "mrkdwn", "text": f"*Runbook:*\n`{decision.runbook_id}`"},
                        {"type": "mrkdwn", "text": f"*Confidence:*\n{analyzer.confidence:.0%}"},
                    ]
                },
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": f"*Root Cause*\n{analyzer.root_cause}"}
                },
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": f"*Actions Executed*\n{executed_text}"}
                },
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": f"*Actions Skipped*\n{skipped_text}"}
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": (
                            f"*Prevention*\nReview `{decision.runbook_id}` runbook. "
                            f"Consider increasing alarm threshold or adding auto-scaling policy. "
                            f"Past similar incidents: {', '.join(f'`{i}`' for i in analyzer.similar_incidents) or 'none'}."
                        )
                    }
                },
            ]
        }]
    }

    try:
        post_webhook(_SLACK_WEBHOOK, payload)
        logger.info("executor.slack.sent", incident_id=incident_id)
    except Exception as exc:
        logger.error("executor.slack.error", error=str(exc))
    return None


# ------------------------------------------------------------------
# DynamoDB incident record
# ------------------------------------------------------------------

def _record_incident(
    incident_id: str,
    decision: DecisionOutput,
    executed: list[str],
    resolved: bool,
) -> None:
    analyzer = decision.analyzer
    alarm = analyzer.detector.alarm
    normalized_incident = analyzer.detector.normalized_incident
    provider = normalized_incident.provider if normalized_incident else "aws"
    recorded_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    try:
        table = _DYNAMO.Table(_INCIDENT_TABLE)
        table.put_item(Item={
            "alarm_name":      alarm.alarm_name,
            "incident_id":     incident_id,
            "provider":        provider,
            "severity":        analyzer.severity.value,
            "mode":            decision.remediation_mode.value,
            "root_cause":      analyzer.root_cause,
            "runbook_id":      decision.runbook_id,
            "executed":        executed,  # backward-compatible analyzer lookup
            "executed_actions": executed,
            "resolved":        resolved,
            "created_at":      recorded_at,
            "resolved_at":     recorded_at,
            "ttl":             int(time.time()) + 90 * 86400,  # 90-day retention
        })
    except Exception as exc:
        logger.error("executor.dynamo.error", error=str(exc))


def _record_activity(
    incident_id: str,
    decision: DecisionOutput,
    executed: list[str],
) -> None:
    """Record executor activity to the platform-agent-activity table for the dashboard."""
    analyzer = decision.analyzer
    normalized_incident = analyzer.detector.normalized_incident
    provider = normalized_incident.provider if normalized_incident else "aws"

    agent_name = {
        "aws": "Executor (AWS)",
        "gcp": "Executor (GCP)",
        "azure": "Executor (Azure)",
        "onprem": "Executor (On-Prem)",
    }.get(provider, f"Executor ({provider})")

    record_agent_activity(
        agent=agent_name,
        provider=provider,
        action=f"Incident remediation: {decision.runbook_id} ({incident_id})",
        tool_calls=executed,
        status="success" if executed else "failed",
    )


# ------------------------------------------------------------------
# Serialisation
# ------------------------------------------------------------------

def _deserialise_decision(event: dict[str, Any]) -> DecisionOutput:
    from dataclasses import fields as dc_fields

    ana_data = event["analyzer"]
    det_data = ana_data["detector"]
    alarm    = AlarmContext(**{
        k: det_data["alarm"][k]
        for k in (f.name for f in dc_fields(AlarmContext))
        if k in det_data["alarm"]
    })
    detector = DetectorOutput(
        alarm=alarm,
        log_insights_results=det_data.get("log_insights_results", []),
        xray_trace_ids=det_data.get("xray_trace_ids", []),
        related_metrics=det_data.get("related_metrics", {}),
        normalized_incident=_deserialise_normalized_incident(det_data.get("normalized_incident")),
    )
    analyzer = AnalyzerOutput(
        detector=detector,
        root_cause=ana_data["root_cause"],
        severity=Severity(ana_data["severity"]),
        confidence=float(ana_data["confidence"]),
        similar_incidents=ana_data.get("similar_incidents", []),
    )
    return DecisionOutput(
        analyzer=analyzer,
        runbook_id=event["runbook_id"],
        remediation_mode=RemediationMode(event["remediation_mode"]),
        actions=event.get("actions", []),
        estimated_rto_sec=event.get("estimated_rto_sec"),
    )


def _deserialise_normalized_incident(event: dict[str, Any] | None) -> NormalizedIncident | None:
    if not event:
        return None
    return NormalizedIncident(**event)


def _serialise(output: ExecutorOutput) -> dict[str, Any]:
    from dataclasses import asdict
    return json.loads(json.dumps(asdict(output), default=str))


def _run_external_action(provider: str, action: str, params: dict[str, list[str]], log: Any) -> None:
    if provider == "gcp":
        from src.agents.operations.executor.gcp_runner import run_gcp_action
        run_gcp_action(action, params, log)
    elif provider == "azure":
        from src.agents.operations.executor.azure_runner import run_azure_action
        run_azure_action(action, params, log)
    else:
        # Default mock fallback for onprem or other cloud providers
        log.info(
            "executor.external.pending",
            provider=provider,
            action=action,
            parameters=params,
        )
