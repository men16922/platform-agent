"""Approval request persistence — DynamoDB pending/claim/finalise lifecycle.

The table is the single shared medium between the SQS dispatch path, the Slack
callback path, and the on-prem decision poller (which reads final states).
"""

from __future__ import annotations

import hashlib
import os
import time
from decimal import Decimal
from typing import Any

import boto3
import structlog
from botocore.exceptions import ClientError

from src.agents.operations.aws.approval_bridge.payloads import _request_kind, _request_subject

logger = structlog.get_logger(__name__)

_REGION = os.getenv("AWS_REGION", "ap-northeast-2")
_APPROVAL_REQUEST_TABLE = os.getenv("APPROVAL_REQUEST_TABLE", "")
_APPROVAL_REQUEST_TTL_SEC = int(os.getenv("APPROVAL_REQUEST_TTL_SEC", "86400"))

_DYNAMO = boto3.resource("dynamodb", region_name=_REGION)


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
