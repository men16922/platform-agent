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
from decimal import Decimal
from typing import Any

import boto3
import structlog

from src.agents.adapters.aws_session import assume_role_arn_from_env, assume_role_session
from src.agents.adapters.registry import get_execution_adapter
from src.agents.adapters.slack_client import post_webhook
from src.agents.models import (
    AlarmContext, AnalyzerOutput, DetectorOutput, DecisionOutput,
    ExecutorOutput, NormalizedIncident, RemediationMode, Severity
)
from src.agents.operations.activity_writer import record_agent_activity
from src.agents.runbooks.capability_schema import resolution_verdict

logger = structlog.get_logger(__name__)

_REGION         = os.getenv("AWS_REGION", "ap-northeast-2")
_SLACK_WEBHOOK  = os.getenv("SLACK_WEBHOOK_URL", "")
_INCIDENT_TABLE = os.getenv("INCIDENT_TABLE", "incident-history")

def _ssm_client(region: str):
    # Honor an optional cross-account role (AWS_ASSUME_ROLE_ARN) with graceful
    # in-account fallback; unset → in-account, equivalent to boto3.client("ssm").
    return assume_role_session(assume_role_arn_from_env(), region=region).session.client("ssm", region_name=region)


_SSM    = _ssm_client(_REGION)
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

    verifications: list[Any] = []
    not_applicable: list[str] = []
    if decision.remediation_mode in (RemediationMode.AUTO, RemediationMode.APPROVE):
        executed, skipped, verifications, not_applicable = _run_ssm_actions(decision, log)
    else:
        skipped = decision.actions
        log.info("executor.manual_mode", skipped=skipped)

    # Resolution goes through the shared verdict so both axes have one definition.
    # With no verifications (AWS/GCP/Azure paths, or actions with nothing declared
    # to check) this is exactly the historical rule `bool(executed) and not skipped`
    # and `verified` reports None ("unknown") rather than claiming proof. Where a
    # check DID run, a required failure now withholds resolution.
    verdict  = resolution_verdict(executed, skipped, verifications, not_applicable)
    resolved = verdict.resolved
    if verifications:
        log.info("executor.verified", **verdict.to_dict())

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

# 알림성 액션은 SSM 문서가 아니라 executor 자신의 Slack 인시던트 리포트로 수행된다.
# AWS-SendSlackAlert는 실존하는 SSM Automation 문서가 아님 — open_change_request
# 캐퍼빌리티의 실체는 "사람에게 알리기"이고, 그 전달은 아래 _post_slack_report가 담당.
_NOTIFICATION_ACTIONS = frozenset({"AWS-SendSlackAlert"})


def _resolve_incident_scope(normalized_incident: NormalizedIncident | None, log: Any) -> Any:
    """
    Mint the per-incident scoped credential, or return None (fail-closed downstream).

    Thin delegation on purpose (Phase 3): the implementation moved to
    ``platform.scope`` because this is not the only dispatch path into the
    runners, and a second copy here is how the GCP path ended up with no scope
    at all. Kept as a module-level name because callers patch it in tests.
    """
    from src.agents.platform.scope import resolve_incident_scope

    return resolve_incident_scope(normalized_incident, log)


def _run_capability_steps(
    decision: DecisionOutput, log: Any
) -> tuple[list[str], list[str], list[Any], list[str]]:
    """Walk a runbook's declared steps in order, honouring the step contract.

    The flat path below treats every action as unconditional, independent and
    unordered. The step schema has always been able to express more than that —
    ordering, `condition`, `on_failure`, and a per-step `verify` naming how to
    prove the step helped — but nothing consumed it, so a runbook could declare
    the lot and still be run as a bag of actions.

    Two rules worth stating because they are the ones that bite:

    * A step whose ``condition`` is false is NOT a failure. It is reported as
      skipped, and it must not mark the run unresolved — "we correctly chose not
      to do this" is not "we tried and could not".
    * ``on_failure: abort`` stops the remaining steps. Those are reported as
      skipped too, because a plan that stopped halfway did not finish.
    """
    from src.agents.runbooks.capability_schema import evaluate_condition

    executed: list[str] = []
    skipped:  list[str] = []
    # Steps whose condition was false: reported, but not counted as a failure to act.
    not_applicable: list[str] = []
    verifications: list[Any] = []

    alarm = decision.analyzer.detector.alarm
    normalized_incident = decision.analyzer.detector.normalized_incident
    provider = normalized_incident.provider if normalized_incident else "aws"
    incident_scope = _resolve_incident_scope(normalized_incident, log)

    context: dict[str, Any] = {
        "severity": decision.analyzer.severity.value,
        "provider": provider,
        "previous_step_failed": False,
    }

    aborted = False
    for step in decision.steps:
        action = step.get("action", "")
        name = step.get("name", action)

        if aborted:
            skipped.append(action)
            continue

        if not evaluate_condition(step.get("condition"), context):
            log.info("executor.step.condition_false", step=name, action=action)
            skipped.append(action)
            not_applicable.append(action)
            continue

        params = _build_action_params(action, alarm, normalized_incident, provider)
        try:
            if action in _NOTIFICATION_ACTIONS:
                if not _SLACK_WEBHOOK:
                    raise RuntimeError("no slack webhook configured")
                log.info("executor.notify.in_process", step=name, action=action)
            elif provider != "aws":
                _run_external_action(provider, action, params, log, incident_scope)
            else:
                resp = _SSM.start_automation_execution(
                    DocumentName=action, DocumentVersion="$DEFAULT", Parameters=params,
                )
                if decision.remediation_mode == RemediationMode.AUTO:
                    _wait_for_ssm(_SSM, resp["AutomationExecutionId"], log)
            executed.append(action)
            context["previous_step_failed"] = False
        except Exception as exc:
            log.error("executor.step.failed", step=name, action=action, error=str(exc))
            skipped.append(action)
            context["previous_step_failed"] = True
            if step.get("on_failure", "abort") == "abort":
                log.warning("executor.step.abort", step=name)
                aborted = True
            continue

        # The runbook's own `verify` wins over the action→capability table: the
        # author saying how to prove THIS step beats a global guess.
        if provider == "onprem":
            from src.agents.operations.runners.onprem_verify import verify_onprem_action

            declared = step.get("verify") or {}
            result = verify_onprem_action(
                action, params, log, incident_scope,
                capability=declared.get("capability") or None,
                step_name=name,
            )
            if result is not None:
                verifications.append(result)
                if not result.passed and declared.get("required", True) is False:
                    log.info("executor.step.verify_advisory_failed", step=name)

    return executed, skipped, verifications, not_applicable


def _run_ssm_actions(
    decision: DecisionOutput, log: Any
) -> tuple[list[str], list[str], list[Any], list[str]]:
    if decision.steps:
        return _run_capability_steps(decision, log)

    executed: list[str] = []
    skipped:  list[str] = []
    # Post-execution evidence: "dispatched" and "actually helped" are different
    # facts, and only the second justifies calling an incident resolved.
    verifications: list[Any] = []
    alarm = decision.analyzer.detector.alarm
    normalized_incident = decision.analyzer.detector.normalized_incident
    provider = normalized_incident.provider if normalized_incident else "aws"
    incident_scope = _resolve_incident_scope(normalized_incident, log)

    for action in decision.actions:
        if action in _NOTIFICATION_ACTIONS:
            if _SLACK_WEBHOOK:
                log.info("executor.notify.in_process", action=action)
                executed.append(action)
            else:
                log.warning("executor.notify.no_webhook", action=action)
                skipped.append(action)
            continue

        params = _build_action_params(action, alarm, normalized_incident, provider)

        if provider != "aws":
            try:
                _run_external_action(provider, action, params, log, incident_scope)
                executed.append(action)
                if provider == "onprem":
                    # Verify with the SAME scoped credential as the action, so a
                    # check can never reach further than the remediation it proves.
                    from src.agents.operations.runners.onprem_verify import verify_onprem_action

                    result = verify_onprem_action(action, params, log, incident_scope)
                    if result is not None:
                        verifications.append(result)
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
                ssm_failover = _ssm_client(failover_region)
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

    # The flat path has no conditions, so nothing can be "not applicable".
    return executed, skipped, verifications, []


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
        item = {
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
            "ttl":             int(time.time()) + 90 * 86400,  # 90-day retention
        }
        # When the remediation finished. This function runs immediately after the
        # actions do, so the write moment IS the resolution moment — but only
        # where there was a resolution.
        #
        # It used to be set unconditionally to `recorded_at`, i.e. to the exact
        # value of `created_at` on the same row. Two consequences, and the second
        # is the expensive one: an unresolved incident carried a resolution
        # timestamp, and the pair (`started_at`, `resolved_at`) that the weekly
        # on-call report subtracts for MTTR was two copies of one number. Every
        # incident in every weekly report has therefore been resolved in exactly
        # zero minutes since the report was written.
        #
        # Absent when unresolved, the same rule tenancy and `triggered_at`
        # follow here: no value means "not resolved yet", which a reader can act
        # on. A defaulted value means "resolved instantly", which it cannot.
        if resolved:
            item["resolved_at"] = recorded_at
        # Whose incident this is. `NormalizedIncident` has carried tenant/env as
        # first-class fields since Phase 1a, and this writer dropped them — so
        # the read side had nothing to partition on and the dashboard showed
        # every tenant's incidents to everyone. Stored only when non-empty:
        # absent means "this incident predates tenancy or has none", which the
        # reader must be able to tell apart from "belongs to a tenant".
        if normalized_incident:
            if normalized_incident.tenant:
                item["tenant"] = normalized_incident.tenant
            if normalized_incident.env:
                item["env"] = normalized_incident.env
            # When the alert actually fired, per the source. `created_at` above is
            # when this row was written, so without this the incident lands on the
            # timeline at the moment we happened to process it and the gap between
            # breaking and noticing is not derivable. Same field, same omission,
            # same fix as tenant/env directly above — the on-prem writer was
            # corrected first; this is the cloud half.
            if normalized_incident.triggered_at:
                item["triggered_at"] = normalized_incident.triggered_at

        # The analyser's confidence. The dashboard has always rendered it — and
        # has therefore always rendered "confidence n/a" for every cloud
        # incident, because this writer never stored it.
        #
        # Decimal, not float: boto3's resource layer *rejects* Python floats
        # outright (see approval_bridge/request_store.py, which already paid for
        # this). The raise would be swallowed by the except below and the entire
        # incident record would be lost — so the wrong type here does not degrade
        # one field, it deletes the row.
        if isinstance(analyzer.confidence, (int, float)):
            item["confidence"] = Decimal(str(analyzer.confidence))

        # Surface the reconciliation gate result so the dashboard can show WHY an
        # AUTO decision was downgraded (parity with the on-prem incident pipeline).
        if decision.reconciliation:
            item["reconciliation"] = decision.reconciliation
        table.put_item(Item=item)
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
        # Dropping this silently reinstates the flat path: the executor sees no
        # steps, walks `actions` unconditionally, and every condition/on_failure/
        # verify the runbook declared is lost — with nothing in the logs to say
        # so. In-memory unit tests cannot catch it because they never cross this
        # boundary; running the real pipeline is what surfaced it.
        steps=event.get("steps", []),
        estimated_rto_sec=event.get("estimated_rto_sec"),
    )


def _deserialise_normalized_incident(event: dict[str, Any] | None) -> NormalizedIncident | None:
    if not event:
        return None
    return NormalizedIncident(**event)


def _serialise(output: ExecutorOutput) -> dict[str, Any]:
    from dataclasses import asdict
    return json.loads(json.dumps(asdict(output), default=str))


def _run_external_action(
    provider: str,
    action: str,
    params: dict[str, list[str]],
    log: Any,
    incident_scope: Any = None,
) -> None:
    """Dispatch one action to a non-AWS runner.

    ``incident_scope`` is the per-incident scoped credential handle (Phase 1a).
    This function used to drop the incident entirely and forward only ``params``,
    which is why blast radius depended on label/routing correctness instead of on
    a credential. Every cluster-touching runner now refuses a live run without it.

    Phase 3 closed the asymmetry here: the scope reached only the on-prem runner,
    so a GKE or AKS remediation still ran on routing correctness alone. Every
    branch below forwards it, and ``test_scope_reaches_every_runner`` fails if a
    future provider is added without doing the same.
    """
    if provider == "gcp":
        from src.agents.operations.runners.gcp_runner import run_gcp_action
        run_gcp_action(action, params, log, incident_scope)
    elif provider == "azure":
        from src.agents.operations.runners.azure_runner import run_azure_action
        run_azure_action(action, params, log, incident_scope)
    elif provider == "onprem":
        # Real kubectl remediation, gated off by default (ONPREM_EXECUTOR_LIVE)
        # and refused outright when no scoped credential was resolved.
        from src.agents.operations.runners.onprem_runner import run_onprem_action
        run_onprem_action(action, params, log, incident_scope)
    else:
        # Default mock fallback for other providers.
        log.info(
            "executor.external.pending",
            provider=provider,
            action=action,
            parameters=params,
        )
