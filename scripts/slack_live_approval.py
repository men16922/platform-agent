#!/usr/bin/env python3
"""Live Slack approval harness — validate Task 12 without an AWS deploy.

The approval-bridge code, unit tests, E2E tests and setup guide are already
complete; the only remaining gap is *seeing a real interactive message land in
Slack and driving the button callback end to end*. This CLI closes that gap by
reusing the real ``approval_bridge.handler`` internals — identical Block Kit
rendering and HMAC signature verification — so no Lambda/Step Functions deploy
is required.

Modes
-----
send       POST a real interactive approval message (Approve / Reject buttons)
           to ``$SLACK_WEBHOOK_URL``. Proves the outbound message renders.
simulate   Fully offline: run SQS-store -> signed button callback -> SFN resume
           against the real handler with an in-memory table and a fake Step
           Functions client. Proves the callback path with a real signature.
full       ``send`` (real Slack message) + ``simulate`` (local callback) using
           one shared approval id. The closest thing to production without AWS.

Environment
-----------
SLACK_WEBHOOK_URL     required for ``send`` / ``full``
SLACK_SIGNING_SECRET  required for ``simulate`` / ``full`` (any value; the same
                      secret signs and verifies the simulated callback)

Examples
--------
    export SLACK_WEBHOOK_URL='https://hooks.slack.com/services/...'
    python scripts/slack_live_approval.py send --severity P1 --alarm rds-cpu-high

    export SLACK_SIGNING_SECRET='local-demo-secret'
    python scripts/slack_live_approval.py simulate --decision approve

    # real message + local resume, one approval id
    python scripts/slack_live_approval.py full --decision reject --actor jane.ops
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import sys
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.agents.operations.approval_bridge import handler  # noqa: E402


# --- In-memory DynamoDB stand-in (mirrors the handler's expectations) -----


class _FakeTable:
    def __init__(self) -> None:
        self._items: dict[str, dict[str, Any]] = {}

    def put_item(self, *, Item: dict[str, Any]) -> None:
        self._items[Item["approval_id"]] = dict(Item)

    def get_item(self, *, Key: dict[str, Any]) -> dict[str, Any]:
        item = self._items.get(Key["approval_id"])
        return {"Item": item} if item else {}

    def update_item(self, *, Key: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        from botocore.exceptions import ClientError

        approval_id = Key["approval_id"]
        item = self._items.get(approval_id)
        condition = str(kwargs.get("ConditionExpression", ""))
        values = kwargs.get("ExpressionAttributeValues", {})

        if "attribute_exists(approval_id) AND #status = :pending" in condition:
            if item is None or item.get("status") != values.get(":pending", "PENDING"):
                raise ClientError(
                    {"Error": {"Code": "ConditionalCheckFailedException", "Message": ""}},
                    "UpdateItem",
                )

        if item is None:
            item = {"approval_id": approval_id}
            self._items[approval_id] = item

        alias = {
            ":processing": "status",
            ":status": "status",
            ":decision": "selected_decision",
            ":updated_at": "updated_at",
            ":responded_by": "responded_by",
            ":responded_at": "responded_at",
            ":last_error": "last_error",
        }
        for key, value in values.items():
            if key == ":pending":
                continue
            attr = alias.get(key)
            if attr:
                item[attr] = value
        if "REMOVE last_error" in str(kwargs.get("UpdateExpression", "")):
            item.pop("last_error", None)

        if kwargs.get("ReturnValues") == "ALL_NEW":
            return {"Attributes": dict(item)}
        return {}

    def get(self, approval_id: str) -> dict[str, Any] | None:
        return self._items.get(approval_id)


class _FakeSfn:
    """Records Step Functions callbacks instead of calling AWS."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def send_task_success(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(("send_task_success", kwargs))
        return {}

    def send_task_failure(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(("send_task_failure", kwargs))
        return {}


class _FakeResponse:
    status_code = 200

    def raise_for_status(self) -> None:
        return None


# --- Payload + signed-event builders --------------------------------------


def _build_payload(args: argparse.Namespace) -> dict[str, Any]:
    payload = {
        "taskToken": args.task_token,
        "runbook_id": args.runbook,
        "actions": args.actions,
        "severity": args.severity,
        "alarm_name": args.alarm,
        "root_cause": args.root_cause,
        "request_kind": args.request_kind,
        "request_subject": args.subject or args.alarm,
    }
    if args.summary:
        payload["request_summary"] = args.summary
    return payload


def _signed_callback_event(action_id: str, approval_id: str, actor: str, secret: str) -> dict[str, Any]:
    interaction = {
        "type": "block_actions",
        "user": {"id": "U-LOCAL", "username": actor},
        "actions": [{"action_id": action_id, "value": approval_id}],
    }
    body = urlencode({"payload": json.dumps(interaction)})
    ts = str(int(time.time()))
    basestring = f"v0:{ts}:{body}"
    signature = "v0=" + hmac.new(secret.encode(), basestring.encode(), hashlib.sha256).hexdigest()
    return {
        "requestContext": {"http": {"method": "POST", "path": "/"}},
        "headers": {"x-slack-signature": signature, "x-slack-request-timestamp": ts},
        "body": body,
        "isBase64Encoded": False,
    }


# --- Modes ----------------------------------------------------------------


def _do_send(args: argparse.Namespace, approval_id: str) -> None:
    webhook = os.getenv("SLACK_WEBHOOK_URL", "").strip()
    if not webhook:
        sys.exit("SLACK_WEBHOOK_URL is required for `send` / `full`.")
    handler._SLACK_WEBHOOK = webhook
    payload = _build_payload(args)
    print(f"→ Posting interactive approval message to Slack (approval_id={approval_id}) ...")
    handler._post_slack_request(payload, approval_id=approval_id)
    print("✓ Slack message sent. Check the target channel for the Approve / Reject buttons.")
    print("  (Buttons resolve only once the Slack App's Request URL points at a deployed"
          " ApprovalBridgeFunctionUrl; use `simulate` to exercise the callback locally.)")


def _do_simulate(args: argparse.Namespace, approval_id: str, offline: bool) -> None:
    secret = os.getenv("SLACK_SIGNING_SECRET", "").strip()
    if not secret:
        sys.exit("SLACK_SIGNING_SECRET is required for `simulate` / `full`.")

    table = _FakeTable()
    fake_sfn = _FakeSfn()
    handler._SLACK_SIGNING_SECRET = secret
    handler._APPROVAL_REQUEST_TABLE = "local-demo-approval-table"
    handler._SFN = fake_sfn
    handler._approval_request_table = lambda: table  # type: ignore[assignment]
    if offline:
        handler._SLACK_WEBHOOK = "https://hooks.slack.com/local-noop"
        handler.requests.post = lambda *a, **k: _FakeResponse()  # type: ignore[assignment]

    payload = _build_payload(args)
    print(f"→ [1/2] SQS approval request → handler (approval_id={approval_id}) ...")
    queue_result = handler.lambda_handler({"Records": [{"body": json.dumps(payload)}]}, None)
    decision = queue_result["processed"][0]["decision"]
    print(f"  stored decision={decision}, table status={table.get(approval_id)['status']}")

    action_id = "approve_approval" if args.decision == "approve" else "reject_approval"
    print(f"→ [2/2] Slack button click ({args.decision}) with real HMAC signature ...")
    event = _signed_callback_event(action_id, approval_id, args.actor, secret)
    callback = handler.lambda_handler(event, None)
    body = json.loads(callback["body"])
    header = body.get("blocks", [{}])[0].get("text", {}).get("text", body.get("text", ""))
    print(f"  HTTP {callback['statusCode']} — Slack reply: {header!r}")

    if fake_sfn.calls:
        name, kwargs = fake_sfn.calls[0]
        token = kwargs.get("taskToken")
        print(f"  Step Functions resume: {name}(taskToken={token!r})")
    final = table.get(approval_id)
    print(f"✓ Final table status={final['status']} responded_by={final.get('responded_by')!r}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Live Slack approval harness (no AWS deploy needed).")
    parser.add_argument("mode", choices=["send", "simulate", "full"])
    parser.add_argument("--decision", choices=["approve", "reject"], default="approve",
                        help="Simulated button click (simulate/full). Default: approve.")
    parser.add_argument("--actor", default="local.operator", help="Slack username for the click.")
    parser.add_argument("--severity", default="P2")
    parser.add_argument("--runbook", default="eks-pod-oom")
    parser.add_argument("--alarm", default="local-demo-alarm")
    parser.add_argument("--root-cause", default="OOMKilled in api pod (local demo)")
    parser.add_argument("--request-kind", default="incident",
                        choices=["incident", "provisioning", "deployment"])
    parser.add_argument("--subject", default="")
    parser.add_argument("--summary", default="")
    parser.add_argument("--actions", nargs="+", default=["AWS-RestartEKSPod"])
    parser.add_argument("--task-token", default=f"local-demo-token-{int(time.time())}")
    args = parser.parse_args()

    approval_id = handler._approval_id({"taskToken": args.task_token})
    print(f"platform-agent Slack approval harness — mode={args.mode}\n")

    if args.mode == "send":
        _do_send(args, approval_id)
    elif args.mode == "simulate":
        _do_simulate(args, approval_id, offline=True)
    else:  # full
        _do_send(args, approval_id)
        print()
        _do_simulate(args, approval_id, offline=False)


if __name__ == "__main__":
    main()
