"""
Approval Bridge Agent — Lambda handler (orchestration + Step Functions callbacks).

Triggered by:
  1. SQS queue fed by Step Functions waitForTaskToken
  2. Slack interactive callback requests via Lambda Function URL

Responsibilities:
  1. Parse approval requests from SQS
  2. Persist pending approval state for later callback handling (request_store)
  3. Post Slack approval requests with interactive buttons (slack_interactive)
  4. On button click, resume Step Functions with SendTaskSuccess / SendTaskFailure

If Slack interactivity is not configured, the bridge falls back to the existing
default approve/reject policy so non-interactive environments still work.
"""

from __future__ import annotations

import json
import os
import time
from typing import Any

import boto3
import structlog

from src.agents.operations.aws.approval_bridge import request_store, slack_interactive
from src.agents.operations.aws.approval_bridge.payloads import (
    _normalise_decision,
    _request_kind,
    _request_subject,
)
from src.agents.operations.aws.approval_bridge.request_store import (
    _approval_id,
    _claim_request,
    _finalise_request,
    _request_to_callback_payload,
    _reset_request,
    _store_pending_request,
)
from src.agents.operations.aws.approval_bridge.slack_interactive import (
    _decision_from_action_id,
    _decision_message,
    _parse_slack_payload,
    _post_slack_request,
    _raw_body,
    _slack_actor,
    _slack_response,
    _verify_slack_signature,
    _http_response,
)

logger = structlog.get_logger(__name__)

_REGION = os.getenv("AWS_REGION", "ap-northeast-2")
_DEFAULT_DECISION = os.getenv("APPROVAL_DEFAULT_DECISION", "reject").strip().lower()

_SFN = boto3.client("stepfunctions", region_name=_REGION)


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    if "Records" in event:
        return _handle_queue_event(event)
    if _is_http_event(event):
        return _handle_http_event(event)
    raise ValueError("Unsupported approval bridge event shape")


def _handle_queue_event(event: dict[str, Any]) -> dict[str, Any]:
    processed: list[dict[str, str]] = []

    for record in event.get("Records", []):
        payload = _parse_record(record)
        log = logger.bind(
            subject=_request_subject(payload),
            severity=payload["severity"],
            runbook_id=payload["runbook_id"],
            request_kind=_request_kind(payload),
        )
        log.info("approval_bridge.start")

        if _interactive_dispatch_enabled():
            approval_id = _approval_id(payload)
            _store_pending_request(approval_id, payload)
            _post_slack_request(payload, approval_id=approval_id)
            decision = "pending"
        else:
            decision = _normalise_decision(_DEFAULT_DECISION)
            _post_slack_request(payload, default_decision=decision)

            if decision == "approve":
                _approve(payload)
            else:
                _reject(payload, reason=f"default approval decision: {decision}")

        processed.append(
            {
                "alarm_name": payload["alarm_name"],
                "decision": decision,
                "runbook_id": payload["runbook_id"],
                **({"approval_id": approval_id} if decision == "pending" else {}),
            }
        )
        log.info("approval_bridge.done", decision=decision)

    return {"processed": processed}


def _handle_http_event(event: dict[str, Any]) -> dict[str, Any]:
    if not _interactive_callback_enabled():
        return _http_response(503, {"ok": False, "error": "Slack interactive approval is not configured"})

    raw_body = _raw_body(event)
    if not _verify_slack_signature(event.get("headers", {}), raw_body):
        return _http_response(401, {"ok": False, "error": "Invalid Slack signature"})

    interaction = _parse_slack_payload(raw_body)
    if interaction.get("type") != "block_actions":
        return _slack_response(
            {
                "response_type": "ephemeral",
                "text": "Unsupported Slack interaction payload.",
            }
        )

    actions = interaction.get("actions", [])
    if not actions:
        return _slack_response(
            {
                "response_type": "ephemeral",
                "text": "No Slack action was provided.",
            }
        )

    action = actions[0]
    approval_id = action.get("value", "")
    decision = _decision_from_action_id(action.get("action_id", ""))
    actor = _slack_actor(interaction)

    status, approval_request = _claim_request(approval_id, decision, actor)
    if status == "not_found":
        return _slack_response(
            {
                "response_type": "ephemeral",
                "text": "Approval request was not found. It may have expired already.",
            }
        )

    if status == "already_processed" and approval_request is not None:
        return _slack_response(
            {
                "response_type": "ephemeral",
                "text": (
                    "This approval request was already handled "
                    f"(`{approval_request.get('status', 'UNKNOWN')}`)."
                ),
            }
        )

    assert approval_request is not None

    callback_payload = _request_to_callback_payload(approval_request)
    try:
        # On-prem 승인은 SFN task token이 없다(로컬 webhook API가 DynamoDB의 최종
        # 상태를 폴링해 실행). finalise만 하면 결정 전달이 완료된다.
        if _request_kind(approval_request) == "onprem":
            pass
        elif decision == "approve":
            _approve(callback_payload)
        else:
            _reject(callback_payload, reason=f"rejected by {actor}")
        _finalise_request(approval_id, decision, actor)
    except Exception as exc:
        logger.error("approval_bridge.callback.error", approval_id=approval_id, error=str(exc))
        _reset_request(approval_id, str(exc))
        return _slack_response(
            {
                "response_type": "ephemeral",
                "text": "Approval processing failed. Please try again.",
            }
        )

    return _slack_response(_decision_message(approval_request, decision, actor))


def _parse_record(record: dict[str, Any]) -> dict[str, Any]:
    body = record.get("body", "{}")
    payload = json.loads(body)

    required_keys = [
        "taskToken",
        "runbook_id",
        "actions",
        "severity",
        "alarm_name",
        "root_cause",
    ]
    missing = [key for key in required_keys if key not in payload]
    if missing:
        raise ValueError(f"Approval payload missing keys: {', '.join(missing)}")

    return payload


def _approve(payload: dict[str, Any]) -> None:
    _SFN.send_task_success(
        taskToken=payload["taskToken"],
        output=json.dumps(
            {
                "approved": True,
                "decision": "approve",
                "approved_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
        ),
    )


def _reject(payload: dict[str, Any], reason: str) -> None:
    _SFN.send_task_failure(
        taskToken=payload["taskToken"],
        error="ApprovalRejected",
        cause=reason[:32768],
    )


def _is_http_event(event: dict[str, Any]) -> bool:
    request_context = event.get("requestContext", {})
    return isinstance(request_context, dict) and "http" in request_context


def _interactive_dispatch_enabled() -> bool:
    # 모듈 어트리뷰트를 동적으로 읽는다 — 테스트/런타임에서 각 모듈의 설정
    # 전역을 바꾸면 즉시 반영되어야 한다.
    return bool(
        slack_interactive._SLACK_WEBHOOK
        and request_store._APPROVAL_REQUEST_TABLE
        and slack_interactive._SLACK_SIGNING_SECRET
    )


def _interactive_callback_enabled() -> bool:
    return bool(request_store._APPROVAL_REQUEST_TABLE and slack_interactive._SLACK_SIGNING_SECRET)
