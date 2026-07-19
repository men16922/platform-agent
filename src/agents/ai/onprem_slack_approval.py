"""On-Prem P2 승인 게이트의 Slack 버튼 프런트엔드 (옵트인).

로컬 webhook API는 인터넷에서 도달 불가하므로 Slack 버튼 콜백을 직접 받을 수
없다. 대신 AWS approval bridge(Lambda Function URL)와 **DynamoDB 승인 테이블을
공유 매체**로 쓴다:

    P2 parking → 이 모듈이 DynamoDB에 PENDING 기록(request_kind="onprem",
    task_token은 SFN 무관 센티넬) + Slack 버튼 메시지 송출
    → 사용자가 버튼 클릭 → Slack → Lambda(서명 검증)가 클레임·finalise
      (onprem kind는 SFN 콜백 생략 — DynamoDB 상태가 곧 결정 전달)
    → 로컬 webhook API의 폴러가 APPROVED/REJECTED를 읽어 실행/기각.

전부 옵트인: ``ONPREM_SLACK_APPROVAL=true`` + ``SLACK_WEBHOOK_URL`` +
``APPROVAL_REQUEST_TABLE``(+AWS 크레덴셜)이 모두 있어야 동작하고, 미설정이면
어떤 부작용도 없다(오프라인 완결성 유지). 모든 원격 호출은 best-effort —
실패해도 기존 대시보드 승인 경로는 그대로 살아 있다.
"""

from __future__ import annotations

import logging
import os
import time
from decimal import Decimal
from typing import Any, Callable

logger = logging.getLogger(__name__)

_TTL_SEC = int(os.getenv("APPROVAL_REQUEST_TTL_SEC", "86400"))


def enabled() -> bool:
    return (
        os.getenv("ONPREM_SLACK_APPROVAL", "").strip().lower() == "true"
        and bool(os.getenv("SLACK_WEBHOOK_URL"))
        and bool(os.getenv("APPROVAL_REQUEST_TABLE"))
    )


def _default_table():
    import boto3

    dynamo = boto3.resource("dynamodb", region_name=os.getenv("AWS_REGION", "us-east-1"))
    return dynamo.Table(os.environ["APPROVAL_REQUEST_TABLE"])


def _default_post(payload: dict[str, Any]) -> None:
    from src.agents.adapters.slack_client import post_webhook

    post_webhook(os.environ["SLACK_WEBHOOK_URL"], payload)


def announce(record: dict[str, Any], *, table: Any = None, post: Callable | None = None) -> bool:
    """Park된 P2 승인을 DynamoDB에 기록하고 Slack 버튼 메시지를 보낸다.

    approval bridge의 버튼 계약(action_id=approve_approval/reject_approval,
    value=approval_id)과 저장 스키마(Decimal confidence 등)를 그대로 따른다.
    실패는 로그만 남기고 False — 로컬 파이프라인은 절대 막지 않는다.
    """
    if table is None and post is None and not enabled():
        return False

    approval_id = record["approval_id"]
    analyzer = (record.get("decision") or {}).get("analyzer") or {}
    service = record.get("service") or "unknown"
    root_cause = analyzer.get("root_cause") or record.get("root_cause") or ""
    severity = record.get("severity") or "P2"
    actions = list(record.get("actions") or [])
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    item = {
        "approval_id": approval_id,
        "status": "PENDING",
        # SFN 무관 센티넬 — Lambda는 onprem kind에서 이 토큰을 사용하지 않는다.
        "task_token": f"onprem:{approval_id}",
        "runbook_id": record.get("runbook_id") or "unknown",
        "actions": actions,
        "severity": severity,
        "alarm_name": service,
        "root_cause": root_cause,
        "confidence": Decimal(str(analyzer.get("confidence") or 0.0)),
        "request_kind": "onprem",
        "request_subject": service,
        "request_summary": root_cause,
        "created_at": now,
        "updated_at": now,
        "ttl": int(time.time()) + _TTL_SEC,
    }

    try:
        (table if table is not None else _default_table()).put_item(Item=item)
        (post if post is not None else _default_post)(_slack_payload(item))
        logger.info("onprem_slack_approval.announced id=%s", approval_id)
        return True
    except Exception as exc:  # 원격 실패는 로컬 승인 흐름을 막지 않는다
        logger.warning("onprem_slack_approval.announce_failed id=%s error=%s", approval_id, exc)
        return False


def _slack_payload(item: dict[str, Any]) -> dict[str, Any]:
    approval_id = item["approval_id"]
    actions_text = "\n".join(f"  - `{a}`" for a in item["actions"]) or "  (none)"
    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"[{item['severity']}] On-Prem approval gate: {item['request_subject']}",
            },
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": "*Request Type:*\n`ONPREM`"},
                {"type": "mrkdwn", "text": f"*Subject:*\n`{item['request_subject']}`"},
                {"type": "mrkdwn", "text": f"*Runbook:*\n`{item['runbook_id']}`"},
                {"type": "mrkdwn", "text": f"*Approval ID:*\n`{approval_id}`"},
            ],
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Root Cause*\n{item['root_cause'] or 'No summary provided.'}"},
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Requested Actions*\n{actions_text}"},
        },
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
                },
            ],
        },
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": "On-prem remediation — the local webhook API executes on approval.",
                }
            ],
        },
    ]
    return {"blocks": blocks}


def sync_decisions(
    pending_ids: list[str],
    apply_approve: Callable[[str], Any],
    apply_reject: Callable[[str], Any],
    *,
    table: Any = None,
) -> list[tuple[str, str]]:
    """DynamoDB에서 Slack 결정(APPROVED/REJECTED)을 읽어 로컬에 적용한다.

    로컬에서 아직 pending인 승인만 조회한다(read-scope 최소화). 적용된
    (approval_id, decision) 목록을 반환하며, 개별 실패는 건너뛴다.
    """
    if table is None and not enabled():
        return []

    tbl = table if table is not None else _default_table()
    applied: list[tuple[str, str]] = []
    for approval_id in pending_ids:
        try:
            item = tbl.get_item(Key={"approval_id": approval_id}).get("Item")
            status = (item or {}).get("status")
            if status == "APPROVED":
                apply_approve(approval_id)
                applied.append((approval_id, "approved"))
            elif status == "REJECTED":
                apply_reject(approval_id)
                applied.append((approval_id, "rejected"))
        except Exception as exc:
            logger.warning("onprem_slack_approval.sync_failed id=%s error=%s", approval_id, exc)
    if applied:
        logger.info("onprem_slack_approval.synced %s", applied)
    return applied
