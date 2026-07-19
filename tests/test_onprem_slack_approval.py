"""On-Prem P2 승인의 Slack 버튼 프런트엔드 — 오프라인 테스트.

경계 계약: (1) 옵트인 미설정=완전 no-op, (2) announce는 approval bridge의
저장 스키마(Decimal confidence·request_kind=onprem·SFN 무관 센티넬 토큰)와
버튼 계약(action_id/value)을 따름, (3) sync_decisions는 APPROVED/REJECTED만
로컬 콜백으로 되돌리고 개별 실패는 전파하지 않음, (4) Lambda는 onprem kind에서
SFN 콜백을 생략하고 finalise만 수행.
"""

from decimal import Decimal
from unittest import mock

from src.agents.ai import onprem_slack_approval as osa


class _FakeTable:
    def __init__(self, items: dict | None = None):
        self.items = dict(items or {})
        self.put_calls: list[dict] = []

    def put_item(self, *, Item: dict):
        self._reject_floats(Item)
        self.put_calls.append(Item)
        self.items[Item["approval_id"]] = Item

    def get_item(self, *, Key: dict) -> dict:
        item = self.items.get(Key["approval_id"])
        return {"Item": item} if item else {}

    @classmethod
    def _reject_floats(cls, value):
        # 실 DynamoDB 시리얼라이저 계약(float 거부) — approval_bridge 회귀와 동일 가드.
        if isinstance(value, float):
            raise TypeError("Float types are not supported. Use Decimal types instead.")
        if isinstance(value, dict):
            for v in value.values():
                cls._reject_floats(v)
        elif isinstance(value, (list, tuple, set)):
            for v in value:
                cls._reject_floats(v)


_RECORD = {
    "approval_id": "APR-DEADBEEF",
    "service": "payments-api",
    "severity": "P2",
    "runbook_id": "onprem-generic",
    "actions": ["onprem-restart-workload"],
    "decision": {"analyzer": {"root_cause": "OOM in payments-api", "confidence": 0.61}},
}


class TestEnabled:
    def test_disabled_without_env(self, monkeypatch):
        monkeypatch.delenv("ONPREM_SLACK_APPROVAL", raising=False)
        assert osa.enabled() is False
        assert osa.announce(_RECORD) is False
        assert osa.sync_decisions(["APR-X"], lambda i: i, lambda i: i) == []

    def test_enabled_requires_all_three(self, monkeypatch):
        monkeypatch.setenv("ONPREM_SLACK_APPROVAL", "true")
        monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.example/x")
        monkeypatch.delenv("APPROVAL_REQUEST_TABLE", raising=False)
        assert osa.enabled() is False
        monkeypatch.setenv("APPROVAL_REQUEST_TABLE", "incident-approval-requests")
        assert osa.enabled() is True


class TestAnnounce:
    def test_writes_bridge_schema_and_posts_buttons(self):
        table, posts = _FakeTable(), []
        assert osa.announce(_RECORD, table=table, post=posts.append) is True

        item = table.put_calls[0]
        assert item["approval_id"] == "APR-DEADBEEF"
        assert item["status"] == "PENDING"
        assert item["request_kind"] == "onprem"
        assert item["task_token"] == "onprem:APR-DEADBEEF"
        assert item["confidence"] == Decimal("0.61")
        assert item["alarm_name"] == "payments-api"

        blocks = posts[0]["blocks"]
        buttons = next(b for b in blocks if b["type"] == "actions")["elements"]
        assert {b["action_id"] for b in buttons} == {"approve_approval", "reject_approval"}
        assert all(b["value"] == "APR-DEADBEEF" for b in buttons)

    def test_remote_failure_is_swallowed(self):
        class _Boom:
            def put_item(self, **_):
                raise RuntimeError("dynamo down")

        assert osa.announce(_RECORD, table=_Boom(), post=lambda p: None) is False


class TestSyncDecisions:
    def test_applies_only_decided(self):
        table = _FakeTable({
            "APR-A": {"approval_id": "APR-A", "status": "APPROVED"},
            "APR-B": {"approval_id": "APR-B", "status": "REJECTED"},
            "APR-C": {"approval_id": "APR-C", "status": "PENDING"},
        })
        approved, rejected = [], []
        applied = osa.sync_decisions(
            ["APR-A", "APR-B", "APR-C", "APR-MISSING"],
            approved.append, rejected.append, table=table,
        )
        assert approved == ["APR-A"] and rejected == ["APR-B"]
        assert ("APR-C", "approved") not in applied and len(applied) == 2

    def test_one_failure_does_not_stop_others(self):
        table = _FakeTable({
            "APR-A": {"approval_id": "APR-A", "status": "APPROVED"},
            "APR-B": {"approval_id": "APR-B", "status": "APPROVED"},
        })
        def flaky(approval_id):
            if approval_id == "APR-A":
                raise RuntimeError("executor busy")
        applied = osa.sync_decisions(["APR-A", "APR-B"], flaky, lambda i: i, table=table)
        assert applied == [("APR-B", "approved")]


class TestBridgeOnpremKind:
    def test_onprem_claim_skips_sfn_and_finalises(self):
        """Lambda 회귀 가드: onprem kind 클레임은 SendTaskSuccess를 호출하지 않는다."""
        from src.agents.operations.aws.approval_bridge import handler as bridge

        record = {
            "approval_id": "APR-DEADBEEF",
            "task_token": "onprem:APR-DEADBEEF",
            "runbook_id": "onprem-generic",
            "actions": ["onprem-restart-workload"],
            "severity": "P2",
            "alarm_name": "payments-api",
            "root_cause": "OOM",
            "confidence": Decimal("0.61"),
            "request_kind": "onprem",
        }
        sfn = mock.MagicMock()
        with mock.patch.object(bridge, "_SFN", sfn), \
             mock.patch.object(bridge, "_claim_request", return_value=("claimed", dict(record))), \
             mock.patch.object(bridge, "_finalise_request") as finalise, \
             mock.patch.object(bridge, "_verify_slack_signature", return_value=True), \
             mock.patch.object(bridge, "_interactive_callback_enabled", return_value=True), \
             mock.patch.object(bridge, "_parse_slack_payload", return_value={
                 "type": "block_actions",
                 "user": {"username": "operator"},
                 "actions": [{"action_id": "approve_approval", "value": "APR-DEADBEEF"}],
             }):
            resp = bridge._handle_http_event({"headers": {}, "body": ""})

        assert resp["statusCode"] == 200
        sfn.send_task_success.assert_not_called()
        sfn.send_task_failure.assert_not_called()
        finalise.assert_called_once()
