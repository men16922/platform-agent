"""
E2E flow tests for Approval Bridge — Slack interactive buttons.

Tests the full pipeline:
  SQS message → DynamoDB store → Slack Block Kit post → HTTP callback (real signature) → SFN resolve

Unlike test_approval_bridge.py which mocks most internals, these tests exercise the actual
signature verification, DynamoDB operations (via moto or stubbed table), and the complete
request lifecycle including edge cases.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from unittest.mock import MagicMock, patch
from urllib.parse import urlencode

import pytest

from src.agents.operations.aws.approval_bridge.handler import lambda_handler
from src.agents.operations.aws.approval_bridge.payloads import _header_text
from src.agents.operations.aws.approval_bridge.request_store import _approval_id
from src.agents.operations.aws.approval_bridge.slack_interactive import (
    _post_slack_request,
    _verify_slack_signature,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SIGNING_SECRET = "test_signing_secret_for_e2e"


def _generate_slack_signature(body: str, timestamp: str, secret: str = SIGNING_SECRET) -> str:
    """Generate a valid Slack request signature (same algorithm as Slack uses)."""
    basestring = f"v0:{timestamp}:{body}"
    sig = hmac.new(
        secret.encode("utf-8"),
        basestring.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"v0={sig}"


def _make_slack_callback_event(
    action_id: str,
    approval_id: str,
    username: str = "ops-engineer",
    signing_secret: str = SIGNING_SECRET,
    timestamp: str | None = None,
) -> dict:
    """Build a complete Slack interactive callback event with valid signature."""
    payload = {
        "type": "block_actions",
        "user": {"id": "U999", "username": username},
        "actions": [{"action_id": action_id, "value": approval_id}],
    }
    body = urlencode({"payload": json.dumps(payload)})
    ts = timestamp or str(int(time.time()))
    signature = _generate_slack_signature(body, ts, signing_secret)

    return {
        "requestContext": {"http": {"method": "POST", "path": "/"}},
        "headers": {
            "x-slack-signature": signature,
            "x-slack-request-timestamp": ts,
        },
        "body": body,
        "isBase64Encoded": False,
    }


def _make_sqs_event(
    task_token: str = "sfn-token-e2e-001",
    runbook_id: str = "eks-pod-oom",
    actions: list[str] | None = None,
    severity: str = "P2",
    alarm_name: str = "eks-oom-alarm",
    root_cause: str = "OOMKilled in api pod",
    **extra,
) -> dict:
    """Build an SQS event (Step Functions waitForTaskToken)."""
    payload = {
        "taskToken": task_token,
        "runbook_id": runbook_id,
        "actions": actions or ["AWS-RestartEKSPod"],
        "severity": severity,
        "alarm_name": alarm_name,
        "root_cause": root_cause,
        **extra,
    }
    return {"Records": [{"body": json.dumps(payload)}]}


# ---------------------------------------------------------------------------
# Fake DynamoDB table for E2E flow
# ---------------------------------------------------------------------------

class FakeDynamoTable:
    """In-memory DynamoDB table stub for E2E tests."""

    def __init__(self):
        self._items: dict[str, dict] = {}

    def put_item(self, *, Item: dict):
        self._reject_floats(Item)
        self._items[Item["approval_id"]] = Item.copy()

    @classmethod
    def _reject_floats(cls, value):
        # 실 DynamoDB(boto3 resource) 시리얼라이저와 동일 계약: float 거부(Decimal만 허용).
        # 라이브에서 confidence float가 TypeError로 터진 회귀 가드(2026-07-18).
        if isinstance(value, float):
            raise TypeError("Float types are not supported. Use Decimal types instead.")
        if isinstance(value, dict):
            for v in value.values():
                cls._reject_floats(v)
        elif isinstance(value, (list, tuple, set)):
            for v in value:
                cls._reject_floats(v)

    def get_item(self, *, Key: dict) -> dict:
        item = self._items.get(Key["approval_id"])
        if item:
            return {"Item": item}
        return {}

    def update_item(self, *, Key: dict, **kwargs):
        approval_id = Key["approval_id"]
        item = self._items.get(approval_id)

        condition = kwargs.get("ConditionExpression", "")
        expr_values = kwargs.get("ExpressionAttributeValues", {})

        if "attribute_exists(approval_id) AND #status = :pending" in str(condition):
            if item is None:
                from botocore.exceptions import ClientError

                raise ClientError(
                    {"Error": {"Code": "ConditionalCheckFailedException", "Message": ""}},
                    "UpdateItem",
                )
            if item.get("status") != expr_values.get(":pending", "PENDING"):
                from botocore.exceptions import ClientError

                raise ClientError(
                    {"Error": {"Code": "ConditionalCheckFailedException", "Message": ""}},
                    "UpdateItem",
                )

        if item is None:
            item = {"approval_id": approval_id}
            self._items[approval_id] = item

        for key, value in expr_values.items():
            clean_key = key.lstrip(":")
            if clean_key in ("pending",):
                continue
            if clean_key == "status":
                item["status"] = value
            elif clean_key == "processing":
                item["status"] = value
            elif clean_key == "decision":
                item["selected_decision"] = value
            elif clean_key == "updated_at":
                item["updated_at"] = value
            elif clean_key == "responded_by":
                item["responded_by"] = value
            elif clean_key == "responded_at":
                item["responded_at"] = value
            elif clean_key == "last_error":
                item["last_error"] = value

        return_values = kwargs.get("ReturnValues", "")
        if return_values == "ALL_NEW":
            return {"Attributes": item.copy()}
        return {}

    def get(self, approval_id: str) -> dict | None:
        return self._items.get(approval_id)


# ---------------------------------------------------------------------------
# E2E Test Class: Full Pipeline
# ---------------------------------------------------------------------------

class TestE2EApprovalFlow:
    """Test the full SQS → DDB → Slack callback → SFN resolution flow."""

    @pytest.fixture(autouse=True)
    def setup_env(self, monkeypatch):
        """Configure environment for interactive mode."""
        monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/test")
        monkeypatch.setenv("SLACK_SIGNING_SECRET", SIGNING_SECRET)
        monkeypatch.setenv("APPROVAL_REQUEST_TABLE", "test-approval-table")

        self.fake_table = FakeDynamoTable()
        self.sfn_mock = MagicMock()

        monkeypatch.setattr(
            "src.agents.operations.aws.approval_bridge.slack_interactive._SLACK_WEBHOOK",
            "https://hooks.slack.com/test",
        )
        monkeypatch.setattr(
            "src.agents.operations.aws.approval_bridge.slack_interactive._SLACK_SIGNING_SECRET",
            SIGNING_SECRET,
        )
        monkeypatch.setattr(
            "src.agents.operations.aws.approval_bridge.request_store._APPROVAL_REQUEST_TABLE",
            "test-approval-table",
        )
        monkeypatch.setattr(
            "src.agents.operations.aws.approval_bridge.handler._SFN",
            self.sfn_mock,
        )

    def _patch_table(self):
        return patch(
            "src.agents.operations.aws.approval_bridge.request_store._approval_request_table",
            return_value=self.fake_table,
        )

    @patch("src.agents.operations.aws.approval_bridge.slack_interactive.requests.post")
    def test_full_approve_flow(self, mock_post):
        """SQS → store → Slack buttons → approve callback → SFN success."""
        mock_post.return_value = MagicMock(status_code=200, raise_for_status=MagicMock())

        with self._patch_table():
            # Step 1: SQS message arrives (Step Functions waitForTaskToken)
            sqs_event = _make_sqs_event(task_token="token-full-e2e-approve")
            result = lambda_handler(sqs_event, None)

            assert result["processed"][0]["decision"] == "pending"
            approval_id = result["processed"][0]["approval_id"]

            # Verify DynamoDB state is PENDING
            stored = self.fake_table.get(approval_id)
            assert stored is not None
            assert stored["status"] == "PENDING"
            assert stored["task_token"] == "token-full-e2e-approve"

            # Verify Slack was called with Block Kit buttons
            slack_call = mock_post.call_args
            slack_body = slack_call.kwargs.get("json") or slack_call[1].get("json")
            blocks = slack_body["blocks"]
            action_block = next(b for b in blocks if b["type"] == "actions")
            buttons = action_block["elements"]
            assert len(buttons) == 2
            assert buttons[0]["action_id"] == "approve_approval"
            assert buttons[1]["action_id"] == "reject_approval"
            assert buttons[0]["value"] == approval_id

            # Step 2: User clicks Approve in Slack (HTTP callback with real signature)
            callback_event = _make_slack_callback_event(
                action_id="approve_approval",
                approval_id=approval_id,
                username="senior-ops",
            )
            callback_result = lambda_handler(callback_event, None)

            assert callback_result["statusCode"] == 200
            body = json.loads(callback_result["body"])
            assert body["replace_original"] is True
            assert "approved" in body["blocks"][0]["text"]["text"].lower()

            # Verify SFN was called with SendTaskSuccess
            self.sfn_mock.send_task_success.assert_called_once()
            sfn_call = self.sfn_mock.send_task_success.call_args
            assert sfn_call.kwargs["taskToken"] == "token-full-e2e-approve"
            output = json.loads(sfn_call.kwargs["output"])
            assert output["approved"] is True
            assert output["decision"] == "approve"

            # Verify DynamoDB final state
            final = self.fake_table.get(approval_id)
            assert final["status"] == "APPROVED"
            assert final["responded_by"] == "senior-ops"

    @patch("src.agents.operations.aws.approval_bridge.slack_interactive.requests.post")
    def test_full_reject_flow(self, mock_post):
        """SQS → store → Slack buttons → reject callback → SFN failure."""
        mock_post.return_value = MagicMock(status_code=200, raise_for_status=MagicMock())

        with self._patch_table():
            sqs_event = _make_sqs_event(task_token="token-full-e2e-reject")
            result = lambda_handler(sqs_event, None)
            approval_id = result["processed"][0]["approval_id"]

            # User clicks Reject
            callback_event = _make_slack_callback_event(
                action_id="reject_approval",
                approval_id=approval_id,
                username="cautious-ops",
            )
            callback_result = lambda_handler(callback_event, None)

            assert callback_result["statusCode"] == 200
            body = json.loads(callback_result["body"])
            assert "rejected" in body["blocks"][0]["text"]["text"].lower()

            # Verify SFN was called with SendTaskFailure
            self.sfn_mock.send_task_failure.assert_called_once()
            sfn_call = self.sfn_mock.send_task_failure.call_args
            assert sfn_call.kwargs["taskToken"] == "token-full-e2e-reject"
            assert sfn_call.kwargs["error"] == "ApprovalRejected"
            assert "cautious-ops" in sfn_call.kwargs["cause"]

            # Verify DynamoDB final state
            final = self.fake_table.get(approval_id)
            assert final["status"] == "REJECTED"


# ---------------------------------------------------------------------------
# Signature Verification (real HMAC)
# ---------------------------------------------------------------------------

class TestSlackSignatureVerification:
    """Test _verify_slack_signature with actual HMAC computation."""

    @pytest.fixture(autouse=True)
    def setup_secret(self, monkeypatch):
        monkeypatch.setattr(
            "src.agents.operations.aws.approval_bridge.slack_interactive._SLACK_SIGNING_SECRET",
            SIGNING_SECRET,
        )

    def test_valid_signature_passes(self):
        body = "payload=%7B%22type%22%3A%22block_actions%22%7D"
        ts = str(int(time.time()))
        sig = _generate_slack_signature(body, ts)

        headers = {
            "x-slack-request-timestamp": ts,
            "x-slack-signature": sig,
        }
        assert _verify_slack_signature(headers, body) is True

    def test_wrong_secret_fails(self):
        body = "payload=%7B%22type%22%3A%22block_actions%22%7D"
        ts = str(int(time.time()))
        sig = _generate_slack_signature(body, ts, secret="wrong_secret")

        headers = {
            "x-slack-request-timestamp": ts,
            "x-slack-signature": sig,
        }
        assert _verify_slack_signature(headers, body) is False

    def test_tampered_body_fails(self):
        body = "payload=%7B%22type%22%3A%22block_actions%22%7D"
        ts = str(int(time.time()))
        sig = _generate_slack_signature(body, ts)

        headers = {
            "x-slack-request-timestamp": ts,
            "x-slack-signature": sig,
        }
        assert _verify_slack_signature(headers, body + "&tampered=true") is False

    def test_expired_timestamp_fails(self):
        body = "payload=%7B%22type%22%3A%22block_actions%22%7D"
        ts = str(int(time.time()) - 600)  # 10 minutes ago (> 5 min threshold)
        sig = _generate_slack_signature(body, ts)

        headers = {
            "x-slack-request-timestamp": ts,
            "x-slack-signature": sig,
        }
        assert _verify_slack_signature(headers, body) is False

    def test_missing_timestamp_fails(self):
        body = "payload=test"
        headers = {"x-slack-signature": "v0=abc123"}
        assert _verify_slack_signature(headers, body) is False

    def test_missing_signature_fails(self):
        body = "payload=test"
        headers = {"x-slack-request-timestamp": str(int(time.time()))}
        assert _verify_slack_signature(headers, body) is False

    def test_empty_secret_fails(self, monkeypatch):
        monkeypatch.setattr(
            "src.agents.operations.aws.approval_bridge.slack_interactive._SLACK_SIGNING_SECRET",
            "",
        )
        body = "payload=test"
        ts = str(int(time.time()))
        headers = {
            "x-slack-request-timestamp": ts,
            "x-slack-signature": _generate_slack_signature(body, ts),
        }
        assert _verify_slack_signature(headers, body) is False

    def test_non_numeric_timestamp_fails(self):
        body = "payload=test"
        headers = {
            "x-slack-request-timestamp": "not-a-number",
            "x-slack-signature": "v0=abc",
        }
        assert _verify_slack_signature(headers, body) is False

    def test_case_insensitive_headers(self):
        """Slack sends headers in various cases; our code normalises them."""
        body = "payload=%7B%22type%22%3A%22block_actions%22%7D"
        ts = str(int(time.time()))
        sig = _generate_slack_signature(body, ts)

        headers = {
            "X-Slack-Request-Timestamp": ts,
            "X-Slack-Signature": sig,
        }
        assert _verify_slack_signature(headers, body) is True


# ---------------------------------------------------------------------------
# Edge Cases: Duplicate Click, Expired Request, DDB Errors
# ---------------------------------------------------------------------------

class TestEdgeCases:
    """Edge cases: duplicate clicks, expired requests, SFN callback failures."""

    @pytest.fixture(autouse=True)
    def setup_env(self, monkeypatch):
        monkeypatch.setattr(
            "src.agents.operations.aws.approval_bridge.slack_interactive._SLACK_WEBHOOK",
            "https://hooks.slack.com/test",
        )
        monkeypatch.setattr(
            "src.agents.operations.aws.approval_bridge.slack_interactive._SLACK_SIGNING_SECRET",
            SIGNING_SECRET,
        )
        monkeypatch.setattr(
            "src.agents.operations.aws.approval_bridge.request_store._APPROVAL_REQUEST_TABLE",
            "test-approval-table",
        )

        self.fake_table = FakeDynamoTable()
        self.sfn_mock = MagicMock()
        monkeypatch.setattr(
            "src.agents.operations.aws.approval_bridge.handler._SFN",
            self.sfn_mock,
        )

    def _patch_table(self):
        return patch(
            "src.agents.operations.aws.approval_bridge.request_store._approval_request_table",
            return_value=self.fake_table,
        )

    @patch("src.agents.operations.aws.approval_bridge.slack_interactive.requests.post")
    def test_duplicate_click_returns_already_processed(self, mock_post):
        """Second click on same approval returns ephemeral 'already handled' message."""
        mock_post.return_value = MagicMock(status_code=200, raise_for_status=MagicMock())

        with self._patch_table():
            # First: create and approve
            sqs_event = _make_sqs_event(task_token="token-dup-test")
            result = lambda_handler(sqs_event, None)
            approval_id = result["processed"][0]["approval_id"]

            # First click: approve
            event1 = _make_slack_callback_event("approve_approval", approval_id)
            r1 = lambda_handler(event1, None)
            assert r1["statusCode"] == 200

            # Second click: same approval_id
            event2 = _make_slack_callback_event("reject_approval", approval_id)
            r2 = lambda_handler(event2, None)

            assert r2["statusCode"] == 200
            body = json.loads(r2["body"])
            assert "already handled" in body.get("text", "").lower() or "already" in json.dumps(body).lower()

    @patch("src.agents.operations.aws.approval_bridge.slack_interactive.requests.post")
    def test_expired_request_not_found(self, mock_post):
        """Clicking a button for a non-existent (expired TTL) request returns not found."""
        mock_post.return_value = MagicMock(status_code=200, raise_for_status=MagicMock())

        with self._patch_table():
            event = _make_slack_callback_event("approve_approval", "APR-NONEXIST999")
            result = lambda_handler(event, None)

            assert result["statusCode"] == 200
            body = json.loads(result["body"])
            assert "not found" in body.get("text", "").lower() or "expired" in body.get("text", "").lower()

    @patch("src.agents.operations.aws.approval_bridge.slack_interactive.requests.post")
    def test_sfn_callback_failure_resets_to_pending(self, mock_post):
        """If SFN SendTaskSuccess fails, request is reset to PENDING for retry."""
        mock_post.return_value = MagicMock(status_code=200, raise_for_status=MagicMock())
        self.sfn_mock.send_task_success.side_effect = Exception("SFN timeout")

        with self._patch_table():
            sqs_event = _make_sqs_event(task_token="token-sfn-fail")
            result = lambda_handler(sqs_event, None)
            approval_id = result["processed"][0]["approval_id"]

            event = _make_slack_callback_event("approve_approval", approval_id)
            callback_result = lambda_handler(event, None)

            assert callback_result["statusCode"] == 200
            body = json.loads(callback_result["body"])
            assert "failed" in body.get("text", "").lower() or "try again" in body.get("text", "").lower()

            # DynamoDB should be reset to PENDING
            stored = self.fake_table.get(approval_id)
            assert stored["status"] == "PENDING"
            assert "SFN timeout" in stored.get("last_error", "")

    @patch("src.agents.operations.aws.approval_bridge.slack_interactive.requests.post")
    def test_multiple_sqs_records_each_stored(self, mock_post):
        """Multiple SQS records in one batch are all stored in DDB."""
        mock_post.return_value = MagicMock(status_code=200, raise_for_status=MagicMock())

        records = [
            {"body": json.dumps({
                "taskToken": f"token-batch-{i}",
                "runbook_id": "rds-cpu-high",
                "actions": [f"action-{i}"],
                "severity": "P2",
                "alarm_name": f"alarm-{i}",
                "root_cause": f"Root cause {i}",
            })}
            for i in range(3)
        ]

        with self._patch_table():
            result = lambda_handler({"Records": records}, None)

            assert len(result["processed"]) == 3
            for entry in result["processed"]:
                assert entry["decision"] == "pending"
                stored = self.fake_table.get(entry["approval_id"])
                assert stored is not None
                assert stored["status"] == "PENDING"

    def test_unsupported_event_raises(self):
        """Non-SQS, non-HTTP events raise ValueError."""
        with pytest.raises(ValueError, match="Unsupported"):
            lambda_handler({"unexpected": "shape"}, None)

    @patch("src.agents.operations.aws.approval_bridge.slack_interactive.requests.post")
    def test_interactive_disabled_falls_back_to_default(self, mock_post, monkeypatch):
        """When interactive mode is disabled, falls back to default decision."""
        monkeypatch.setattr(
            "src.agents.operations.aws.approval_bridge.slack_interactive._SLACK_SIGNING_SECRET",
            "",
        )
        monkeypatch.setattr(
            "src.agents.operations.aws.approval_bridge.handler._DEFAULT_DECISION",
            "approve",
        )
        mock_post.return_value = MagicMock(status_code=200, raise_for_status=MagicMock())

        with self._patch_table():
            sqs_event = _make_sqs_event(task_token="token-fallback")
            result = lambda_handler(sqs_event, None)

            assert result["processed"][0]["decision"] == "approve"
            self.sfn_mock.send_task_success.assert_called_once()


# ---------------------------------------------------------------------------
# Block Kit Message Structure
# ---------------------------------------------------------------------------

class TestBlockKitStructure:
    """Verify Block Kit message structure for Approve/Reject buttons."""

    @pytest.fixture(autouse=True)
    def setup_env(self, monkeypatch):
        monkeypatch.setattr(
            "src.agents.operations.aws.approval_bridge.slack_interactive._SLACK_WEBHOOK",
            "https://hooks.slack.com/test",
        )
        monkeypatch.setattr(
            "src.agents.operations.aws.approval_bridge.slack_interactive._SLACK_SIGNING_SECRET",
            SIGNING_SECRET,
        )
        monkeypatch.setattr(
            "src.agents.operations.aws.approval_bridge.request_store._APPROVAL_REQUEST_TABLE",
            "test-approval-table",
        )

    @patch("src.agents.operations.aws.approval_bridge.slack_interactive.requests.post")
    def test_interactive_message_has_action_buttons(self, mock_post):
        """Interactive message includes Approve (primary) and Reject (danger) buttons."""
        mock_post.return_value = MagicMock(status_code=200, raise_for_status=MagicMock())

        payload = {
            "taskToken": "token-blockkit",
            "runbook_id": "lambda-throttle",
            "actions": ["IncreaseConcurrency"],
            "severity": "P2",
            "alarm_name": "lambda-throttle-alarm",
            "root_cause": "Lambda throttling detected",
        }
        approval_id = _approval_id(payload)

        _post_slack_request(payload, approval_id=approval_id)

        slack_body = mock_post.call_args.kwargs.get("json") or mock_post.call_args[1].get("json")
        blocks = slack_body["blocks"]

        # Header block
        header = blocks[0]
        assert header["type"] == "header"
        assert "P2" in header["text"]["text"]
        assert "lambda-throttle-alarm" in header["text"]["text"]

        # Actions block with buttons
        action_blocks = [b for b in blocks if b["type"] == "actions"]
        assert len(action_blocks) == 1
        elements = action_blocks[0]["elements"]
        assert len(elements) == 2

        approve_btn = elements[0]
        assert approve_btn["type"] == "button"
        assert approve_btn["text"]["text"] == "Approve"
        assert approve_btn["style"] == "primary"
        assert approve_btn["action_id"] == "approve_approval"
        assert approve_btn["value"] == approval_id

        reject_btn = elements[1]
        assert reject_btn["type"] == "button"
        assert reject_btn["text"]["text"] == "Reject"
        assert reject_btn["style"] == "danger"
        assert reject_btn["action_id"] == "reject_approval"
        assert "confirm" in reject_btn  # Reject has confirmation dialog

    @patch("src.agents.operations.aws.approval_bridge.slack_interactive.requests.post")
    def test_non_interactive_message_has_no_buttons(self, mock_post):
        """Without approval_id, message has context note but no action buttons."""
        mock_post.return_value = MagicMock(status_code=200, raise_for_status=MagicMock())

        payload = {
            "taskToken": "token-nobutton",
            "runbook_id": "generic",
            "actions": ["NotifyOnly"],
            "severity": "P3",
            "alarm_name": "p3-alert",
            "root_cause": "Non-critical",
        }

        _post_slack_request(payload, approval_id=None)

        slack_body = mock_post.call_args.kwargs.get("json") or mock_post.call_args[1].get("json")
        blocks = slack_body["blocks"]

        action_blocks = [b for b in blocks if b["type"] == "actions"]
        assert len(action_blocks) == 0

        # Context block should mention non-interactive
        context_blocks = [b for b in blocks if b["type"] == "context"]
        assert len(context_blocks) >= 1
        context_text = context_blocks[0]["elements"][0]["text"]
        assert "not configured" in context_text.lower() or "default" in context_text.lower()

    def test_header_text_formats_correctly(self):
        """Header text includes severity, request kind, and subject."""
        payload = {
            "severity": "P1",
            "alarm_name": "critical-db-failure",
            "request_kind": "incident",
        }
        header = _header_text(payload)
        assert "[P1]" in header
        assert "critical-db-failure" in header

    def test_header_text_provisioning_kind(self):
        """Provisioning requests show 'Provisioning approval' label."""
        payload = {
            "severity": "P2",
            "alarm_name": "orders-api",
            "request_kind": "provisioning",
            "request_subject": "orders-api",
        }
        header = _header_text(payload)
        assert "Provisioning approval" in header

    def test_header_text_deployment_kind(self):
        """Deployment requests show 'Deployment approval' label."""
        payload = {
            "severity": "P2",
            "alarm_name": "orders-api",
            "request_kind": "deployment",
            "request_subject": "orders-api",
        }
        header = _header_text(payload)
        assert "Deployment approval" in header


# ---------------------------------------------------------------------------
# Approval ID Generation
# ---------------------------------------------------------------------------

class TestApprovalIdGeneration:
    """Test approval ID generation is deterministic and collision-resistant."""

    def test_deterministic_for_same_token(self):
        payload1 = {"taskToken": "same-token-abc"}
        payload2 = {"taskToken": "same-token-abc"}
        assert _approval_id(payload1) == _approval_id(payload2)

    def test_different_tokens_produce_different_ids(self):
        id1 = _approval_id({"taskToken": "token-aaa"})
        id2 = _approval_id({"taskToken": "token-bbb"})
        assert id1 != id2

    def test_format_is_apr_prefix_hex(self):
        result = _approval_id({"taskToken": "any-token"})
        assert result.startswith("APR-")
        hex_part = result[4:]
        assert len(hex_part) == 12
        assert all(c in "0123456789ABCDEF" for c in hex_part)
