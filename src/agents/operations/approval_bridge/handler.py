"""
Approval Bridge Agent — Lambda handler.

Triggered by:
  1. SQS queue fed by Step Functions waitForTaskToken
  2. Slack interactive callback requests via Lambda Function URL

Responsibilities:
  1. Parse approval requests from SQS
  2. Persist pending approval state for later callback handling
  3. Post Slack approval requests with interactive Approve / Reject buttons
  4. On button click, resume Step Functions with SendTaskSuccess / SendTaskFailure

If Slack interactivity is not configured, the bridge falls back to the existing
default approve/reject policy so non-interactive environments still work.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from decimal import Decimal
from typing import Any
from urllib.parse import parse_qs

import boto3
import requests
import structlog
from botocore.exceptions import ClientError

logger = structlog.get_logger(__name__)

_REGION = os.getenv("AWS_REGION", "ap-northeast-2")
_SLACK_WEBHOOK = os.getenv("SLACK_WEBHOOK_URL", "")
_DEFAULT_DECISION = os.getenv("APPROVAL_DEFAULT_DECISION", "reject").strip().lower()
_APPROVAL_REQUEST_TABLE = os.getenv("APPROVAL_REQUEST_TABLE", "")
_SLACK_SIGNING_SECRET = os.getenv("SLACK_SIGNING_SECRET", "")
_APPROVAL_REQUEST_TTL_SEC = int(os.getenv("APPROVAL_REQUEST_TTL_SEC", "86400"))

_SFN = boto3.client("stepfunctions", region_name=_REGION)
_DYNAMO = boto3.resource("dynamodb", region_name=_REGION)


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
            _post_slack_request(payload)

            decision = _normalise_decision(_DEFAULT_DECISION)
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


def _post_slack_request(payload: dict[str, Any], approval_id: str | None = None) -> None:
    if not _SLACK_WEBHOOK:
        logger.warning("approval_bridge.slack.skip", reason="SLACK_WEBHOOK_URL not set")
        return

    actions_text = "\n".join(f"  - `{action}`" for action in payload["actions"]) or "  (none)"
    request_kind = _request_kind(payload)
    request_subject = _request_subject(payload)
    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": _header_text(payload)},
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Request Type:*\n`{request_kind.upper()}`"},
                {"type": "mrkdwn", "text": f"*Subject:*\n`{request_subject}`"},
                {"type": "mrkdwn", "text": f"*Runbook:*\n`{payload['runbook_id']}`"},
                {
                    "type": "mrkdwn",
                    "text": (
                        f"*Approval ID:*\n`{approval_id}`"
                        if approval_id
                        else f"*Default decision:*\n`{_normalise_decision(_DEFAULT_DECISION).upper()}`"
                    ),
                },
            ],
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*{_summary_heading(payload)}*\n{_summary_text(payload)}"},
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Requested Actions*\n{actions_text}"},
        },
    ]

    if approval_id:
        blocks.extend(
            [
                {
                    "type": "actions",
                    "block_id": "approval_actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "Approve"},
                            "style": "primary",
                            "action_id": "approve_approval",
                            "value": approval_id,
                        },
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "Reject"},
                            "style": "danger",
                            "action_id": "reject_approval",
                            "value": approval_id,
                            "confirm": {
                                "title": {"type": "plain_text", "text": "Reject remediation?"},
                                "text": {
                                    "type": "mrkdwn",
                                    "text": "Step Functions will resume with a rejection outcome.",
                                },
                                "confirm": {"type": "plain_text", "text": "Reject"},
                                "deny": {"type": "plain_text", "text": "Cancel"},
                            },
                        },
                    ],
                },
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": "Use the Slack buttons to approve or reject this remediation request.",
                        }
                    ],
                },
            ]
        )
    else:
        blocks.append(
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": (
                            "Interactive approval is not configured. "
                            "This bridge applied the default decision policy."
                        ),
                    }
                ],
            }
        )

    resp = requests.post(_SLACK_WEBHOOK, json={"blocks": blocks}, timeout=10)
    resp.raise_for_status()


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


def _normalise_decision(decision: str) -> str:
    if decision in {"approve", "approved", "auto_approve"}:
        return "approve"
    return "reject"


def _is_http_event(event: dict[str, Any]) -> bool:
    request_context = event.get("requestContext", {})
    return isinstance(request_context, dict) and "http" in request_context


def _interactive_dispatch_enabled() -> bool:
    return bool(_SLACK_WEBHOOK and _APPROVAL_REQUEST_TABLE and _SLACK_SIGNING_SECRET)


def _interactive_callback_enabled() -> bool:
    return bool(_APPROVAL_REQUEST_TABLE and _SLACK_SIGNING_SECRET)


def _approval_request_table():
    if not _APPROVAL_REQUEST_TABLE:
        raise RuntimeError("APPROVAL_REQUEST_TABLE is not configured")
    return _DYNAMO.Table(_APPROVAL_REQUEST_TABLE)


def _approval_id(payload: dict[str, Any]) -> str:
    digest = hashlib.sha256(payload["taskToken"].encode("utf-8")).hexdigest()[:12].upper()
    return f"APR-{digest}"


def _store_pending_request(approval_id: str, payload: dict[str, Any]) -> None:
    existing = _get_request(approval_id)
    if existing and existing.get("status") != "PENDING":
        logger.info(
            "approval_bridge.request.skip_store",
            approval_id=approval_id,
            status=existing.get("status"),
        )
        return

    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    item = {
        "approval_id": approval_id,
        "status": "PENDING",
        "task_token": payload["taskToken"],
        "runbook_id": payload["runbook_id"],
        "actions": payload["actions"],
        "severity": payload["severity"],
        "alarm_name": payload["alarm_name"],
        "root_cause": payload["root_cause"],
        # DynamoDB(boto3 resource)는 Python float를 거부한다 — Decimal만 허용.
        "confidence": Decimal(str(payload.get("confidence", 0.0))),
        "request_kind": _request_kind(payload),
        "request_subject": _request_subject(payload),
        "request_summary": payload.get("request_summary", ""),
        "created_at": now,
        "updated_at": now,
        "ttl": int(time.time()) + _APPROVAL_REQUEST_TTL_SEC,
    }
    _approval_request_table().put_item(Item=item)


def _get_request(approval_id: str) -> dict[str, Any] | None:
    if not approval_id or not _APPROVAL_REQUEST_TABLE:
        return None
    response = _approval_request_table().get_item(Key={"approval_id": approval_id})
    return response.get("Item")


def _claim_request(
    approval_id: str,
    decision: str,
    actor: str,
) -> tuple[str, dict[str, Any] | None]:
    table = _approval_request_table()
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    try:
        response = table.update_item(
            Key={"approval_id": approval_id},
            UpdateExpression=(
                "SET #status = :processing, selected_decision = :decision, "
                "updated_at = :updated_at, responded_by = :responded_by, responded_at = :responded_at"
            ),
            ConditionExpression="attribute_exists(approval_id) AND #status = :pending",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={
                ":pending": "PENDING",
                ":processing": "PROCESSING",
                ":decision": decision.upper(),
                ":updated_at": now,
                ":responded_by": actor,
                ":responded_at": now,
            },
            ReturnValues="ALL_NEW",
        )
        return "claimed", response.get("Attributes")
    except ClientError as exc:
        if exc.response["Error"]["Code"] != "ConditionalCheckFailedException":
            raise
        current = _get_request(approval_id)
        if current is None:
            return "not_found", None
        return "already_processed", current


def _finalise_request(approval_id: str, decision: str, actor: str) -> None:
    table = _approval_request_table()
    final_status = "APPROVED" if decision == "approve" else "REJECTED"
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    table.update_item(
        Key={"approval_id": approval_id},
        UpdateExpression=(
            "SET #status = :status, selected_decision = :decision, "
            "updated_at = :updated_at, responded_by = :responded_by, responded_at = :responded_at "
            "REMOVE last_error"
        ),
        ExpressionAttributeNames={"#status": "status"},
        ExpressionAttributeValues={
            ":status": final_status,
            ":decision": decision.upper(),
            ":updated_at": now,
            ":responded_by": actor,
            ":responded_at": now,
        },
    )


def _reset_request(approval_id: str, error: str) -> None:
    table = _approval_request_table()
    table.update_item(
        Key={"approval_id": approval_id},
        UpdateExpression="SET #status = :status, updated_at = :updated_at, last_error = :last_error",
        ExpressionAttributeNames={"#status": "status"},
        ExpressionAttributeValues={
            ":status": "PENDING",
            ":updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            ":last_error": error[:1024],
        },
    )


def _request_to_callback_payload(approval_request: dict[str, Any]) -> dict[str, Any]:
    return {
        "taskToken": approval_request["task_token"],
        "runbook_id": approval_request["runbook_id"],
        "actions": approval_request.get("actions", []),
        "severity": approval_request["severity"],
        "alarm_name": approval_request["alarm_name"],
        "root_cause": approval_request["root_cause"],
        "confidence": float(approval_request.get("confidence", 0.0)),
        "request_kind": approval_request.get("request_kind", ""),
        "request_subject": approval_request.get("request_subject", ""),
        "request_summary": approval_request.get("request_summary", ""),
    }


def _raw_body(event: dict[str, Any]) -> str:
    body = event.get("body", "")
    if event.get("isBase64Encoded"):
        return base64.b64decode(body).decode("utf-8")
    return body


def _verify_slack_signature(headers: dict[str, Any], raw_body: str) -> bool:
    if not _SLACK_SIGNING_SECRET:
        return False

    normalised_headers = {str(key).lower(): str(value) for key, value in headers.items()}
    timestamp = normalised_headers.get("x-slack-request-timestamp", "")
    signature = normalised_headers.get("x-slack-signature", "")
    if not timestamp or not signature:
        return False

    try:
        request_ts = int(timestamp)
    except ValueError:
        return False

    if abs(int(time.time()) - request_ts) > 300:
        return False

    basestring = f"v0:{timestamp}:{raw_body}"
    expected = "v0=" + hmac.new(
        _SLACK_SIGNING_SECRET.encode("utf-8"),
        basestring.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


def _parse_slack_payload(raw_body: str) -> dict[str, Any]:
    form = parse_qs(raw_body, keep_blank_values=True)
    payload = form.get("payload", ["{}"])[0]
    return json.loads(payload)


def _decision_from_action_id(action_id: str) -> str:
    return "approve" if "approve" in action_id.lower() else "reject"


def _slack_actor(interaction: dict[str, Any]) -> str:
    user = interaction.get("user", {})
    return user.get("username") or user.get("name") or user.get("id") or "unknown"


def _decision_message(
    approval_request: dict[str, Any],
    decision: str,
    actor: str,
) -> dict[str, Any]:
    status_text = "approved" if decision == "approve" else "rejected"
    header = "Remediation approved" if decision == "approve" else "Remediation rejected"
    style_text = "APPROVED" if decision == "approve" else "REJECTED"
    actions_text = "\n".join(f"  - `{action}`" for action in approval_request.get("actions", [])) or "  (none)"
    return {
        "replace_original": True,
        "blocks": [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": header},
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Request Type:*\n`{_request_kind(approval_request).upper()}`"},
                    {"type": "mrkdwn", "text": f"*Subject:*\n`{_request_subject(approval_request)}`"},
                    {"type": "mrkdwn", "text": f"*Status:*\n`{style_text}`"},
                    {"type": "mrkdwn", "text": f"*Runbook:*\n`{approval_request['runbook_id']}`"},
                    {"type": "mrkdwn", "text": f"*Operator:*\n`{actor}`"},
                ],
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*{_summary_heading(approval_request)}*\n{_summary_text(approval_request)}",
                },
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*Requested Actions*\n{actions_text}"},
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"Request {status_text} by `{actor}` through Slack interactive approval.",
                    }
                ],
            },
        ],
    }


def _slack_response(payload: dict[str, Any]) -> dict[str, Any]:
    return _http_response(200, payload)


def _http_response(status_code: int, body: dict[str, Any]) -> dict[str, Any]:
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }


def _request_kind(payload: dict[str, Any]) -> str:
    value = str(payload.get("request_kind", "incident")).strip().lower()
    return value or "incident"


def _request_subject(payload: dict[str, Any]) -> str:
    return str(payload.get("request_subject") or payload.get("alarm_name") or "unknown")


def _summary_text(payload: dict[str, Any]) -> str:
    return str(payload.get("request_summary") or payload.get("root_cause") or "No summary provided.")


def _summary_heading(payload: dict[str, Any]) -> str:
    if _request_kind(payload) == "incident":
        return "Root Cause"
    return "Request Summary"


def _header_text(payload: dict[str, Any]) -> str:
    severity = payload.get("severity", "P2")
    request_kind = _request_kind(payload)
    subject = _request_subject(payload)
    label = {
        "incident": "Approval gate",
        "provisioning": "Provisioning approval",
        "deployment": "Deployment approval",
    }.get(request_kind, "Approval request")
    return f"[{severity}] {label}: {subject}"
