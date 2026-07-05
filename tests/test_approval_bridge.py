"""
Tests for Approval Bridge Agent.
"""

from __future__ import annotations

import json
from urllib.parse import urlencode
from unittest.mock import patch

import pytest

from src.agents.operations.approval_bridge.handler import (
    _approval_id,
    _decision_from_action_id,
    _normalise_decision,
    _parse_record,
    lambda_handler,
)


SAMPLE_RECORD = {
    "body": json.dumps(
        {
            "taskToken": "token-123",
            "runbook_id": "eks-pod-oom",
            "actions": ["AWS-RestartEKSPod"],
            "severity": "P2",
            "alarm_name": "eks-pod-oom",
            "root_cause": "OOMKilled in api pod",
        }
    )
}


class TestParseRecord:
    def test_parse_record(self):
        payload = _parse_record(SAMPLE_RECORD)

        assert payload["taskToken"] == "token-123"
        assert payload["runbook_id"] == "eks-pod-oom"

    def test_missing_required_keys_raises(self):
        with pytest.raises(ValueError):
            _parse_record({"body": json.dumps({"taskToken": "missing"})})


class TestDecisionPolicy:
    def test_normalise_approve(self):
        assert _normalise_decision("auto_approve") == "approve"

    def test_normalise_unknown_defaults_to_reject(self):
        assert _normalise_decision("manual") == "reject"

    def test_decision_from_action_id(self):
        assert _decision_from_action_id("approve_approval") == "approve"
        assert _decision_from_action_id("reject_approval") == "reject"


class TestLambdaHandler:
    @patch("src.agents.operations.approval_bridge.handler._post_slack_request")
    @patch("src.agents.operations.approval_bridge.handler._approve")
    @patch("src.agents.operations.approval_bridge.handler._DEFAULT_DECISION", "approve")
    def test_auto_approve_path(self, approve, post_slack):
        result = lambda_handler({"Records": [SAMPLE_RECORD]}, None)

        assert result["processed"][0]["decision"] == "approve"
        approve.assert_called_once()
        post_slack.assert_called_once()

    @patch("src.agents.operations.approval_bridge.handler._post_slack_request")
    @patch("src.agents.operations.approval_bridge.handler._reject")
    @patch("src.agents.operations.approval_bridge.handler._DEFAULT_DECISION", "reject")
    def test_default_reject_path(self, reject, post_slack):
        result = lambda_handler({"Records": [SAMPLE_RECORD]}, None)

        assert result["processed"][0]["decision"] == "reject"
        reject.assert_called_once()
        post_slack.assert_called_once()

    @patch("src.agents.operations.approval_bridge.handler._post_slack_request")
    @patch("src.agents.operations.approval_bridge.handler._store_pending_request")
    @patch("src.agents.operations.approval_bridge.handler._interactive_dispatch_enabled", return_value=True)
    def test_interactive_queue_path_stores_request(self, interactive_enabled, store_pending, post_slack):
        result = lambda_handler({"Records": [SAMPLE_RECORD]}, None)

        approval_id = _approval_id(json.loads(SAMPLE_RECORD["body"]))
        assert result["processed"][0]["decision"] == "pending"
        assert result["processed"][0]["approval_id"] == approval_id
        store_pending.assert_called_once()
        post_slack.assert_called_once()

    @patch("src.agents.operations.approval_bridge.handler._interactive_callback_enabled", return_value=True)
    @patch("src.agents.operations.approval_bridge.handler._verify_slack_signature", return_value=True)
    @patch("src.agents.operations.approval_bridge.handler._finalise_request")
    @patch("src.agents.operations.approval_bridge.handler._approve")
    @patch(
        "src.agents.operations.approval_bridge.handler._claim_request",
        return_value=(
            "claimed",
            {
                "approval_id": "APR-123",
                "task_token": "token-123",
                "runbook_id": "eks-pod-oom",
                "actions": ["AWS-RestartEKSPod"],
                "severity": "P2",
                "alarm_name": "eks-pod-oom",
                "root_cause": "OOMKilled in api pod",
                "confidence": 0.75,
            },
        ),
    )
    def test_http_approve_path(self, claim_request, approve, finalise_request, verify_sig, interactive_enabled):
        event = _slack_action_event("approve_approval", "APR-123")

        result = lambda_handler(event, None)

        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["replace_original"] is True
        assert "Remediation approved" in body["blocks"][0]["text"]["text"]
        approve.assert_called_once()
        finalise_request.assert_called_once_with("APR-123", "approve", "platform-user")

    @patch("src.agents.operations.approval_bridge.handler._interactive_callback_enabled", return_value=True)
    @patch("src.agents.operations.approval_bridge.handler._verify_slack_signature", return_value=True)
    @patch("src.agents.operations.approval_bridge.handler._finalise_request")
    @patch("src.agents.operations.approval_bridge.handler._reject")
    @patch(
        "src.agents.operations.approval_bridge.handler._claim_request",
        return_value=(
            "claimed",
            {
                "approval_id": "APR-123",
                "task_token": "token-123",
                "runbook_id": "eks-pod-oom",
                "actions": ["AWS-RestartEKSPod"],
                "severity": "P2",
                "alarm_name": "eks-pod-oom",
                "root_cause": "OOMKilled in api pod",
                "confidence": 0.75,
            },
        ),
    )
    def test_http_reject_path(self, claim_request, reject, finalise_request, verify_sig, interactive_enabled):
        event = _slack_action_event("reject_approval", "APR-123")

        result = lambda_handler(event, None)

        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert "Remediation rejected" in body["blocks"][0]["text"]["text"]
        reject.assert_called_once()
        finalise_request.assert_called_once_with("APR-123", "reject", "platform-user")

    @patch("src.agents.operations.approval_bridge.handler._interactive_callback_enabled", return_value=True)
    @patch("src.agents.operations.approval_bridge.handler._verify_slack_signature", return_value=False)
    def test_http_rejects_invalid_signature(self, verify_sig, interactive_enabled):
        result = lambda_handler(_slack_action_event("approve_approval", "APR-123"), None)

        assert result["statusCode"] == 401
        body = json.loads(result["body"])
        assert body["error"] == "Invalid Slack signature"

    @patch("src.agents.operations.approval_bridge.handler._post_slack_request")
    @patch("src.agents.operations.approval_bridge.handler._approve")
    @patch("src.agents.operations.approval_bridge.handler._DEFAULT_DECISION", "approve")
    def test_provisioning_payload_keeps_generic_request_metadata(self, approve, post_slack):
        payload = {
            "taskToken": "token-456",
            "runbook_id": "provisioning-approval",
            "actions": ["Approve CDK deploy for orders-api"],
            "severity": "P2",
            "alarm_name": "orders-api",
            "root_cause": "Provisioning request for orders-api",
            "request_kind": "provisioning",
            "request_subject": "orders-api",
            "request_summary": "Requester eng-alice asked for orders-api on eks",
        }

        result = lambda_handler({"Records": [{"body": json.dumps(payload)}]}, None)

        assert result["processed"][0]["decision"] == "approve"
        posted_payload = post_slack.call_args.args[0]
        assert posted_payload["request_kind"] == "provisioning"
        assert posted_payload["request_subject"] == "orders-api"


class TestMessageFormatting:
    def test_provisioning_header_uses_request_kind(self):
        from src.agents.operations.approval_bridge.handler import _decision_message

        body = _decision_message(
            {
                "alarm_name": "orders-api",
                "runbook_id": "provisioning-approval",
                "actions": ["Approve CDK deploy for orders-api"],
                "request_kind": "provisioning",
                "request_subject": "orders-api",
                "request_summary": "Requester eng-alice asked for orders-api on eks",
                "root_cause": "fallback summary",
            },
            "approve",
            "platform-user",
        )

        fields = body["blocks"][1]["fields"]
        assert fields[0]["text"] == "*Request Type:*\n`PROVISIONING`"
        assert fields[1]["text"] == "*Subject:*\n`orders-api`"
        assert "Request Summary" in body["blocks"][2]["text"]["text"]


def _slack_action_event(action_id: str, approval_id: str) -> dict[str, object]:
    payload = {
        "type": "block_actions",
        "user": {"id": "U123", "username": "platform-user"},
        "actions": [{"action_id": action_id, "value": approval_id}],
    }
    return {
        "requestContext": {"http": {"method": "POST", "path": "/"}},
        "headers": {
            "x-slack-signature": "v0=test",
            "x-slack-request-timestamp": "1234567890",
        },
        "body": urlencode({"payload": json.dumps(payload)}),
        "isBase64Encoded": False,
    }
