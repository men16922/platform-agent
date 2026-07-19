"""Slack-facing side of the approval bridge.

Owns everything that touches Slack: outbound approval-request messages
(webhook), inbound interactive callback parsing, request signature
verification, and the Block Kit response messages.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from typing import Any
from urllib.parse import parse_qs

import requests
import structlog

from src.agents.operations.aws.approval_bridge.payloads import (
    _header_text,
    _request_kind,
    _request_subject,
    _summary_heading,
    _summary_text,
)

logger = structlog.get_logger(__name__)

_SLACK_WEBHOOK = os.getenv("SLACK_WEBHOOK_URL", "")
_SLACK_SIGNING_SECRET = os.getenv("SLACK_SIGNING_SECRET", "")


def _post_slack_request(
    payload: dict[str, Any],
    approval_id: str | None = None,
    default_decision: str = "reject",
) -> None:
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
                        else f"*Default decision:*\n`{default_decision.upper()}`"
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
