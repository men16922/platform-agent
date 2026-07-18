"""알림성 액션(in-process) 실행 — 라이브 E2E가 표면화한 유령 SSM 문서 결함의 회귀 가드.

AWS-SendSlackAlert는 실존 SSM Automation 문서가 아니므로 SSM 호출 없이
executor의 Slack 리포트로 수행되고 executed로 집계돼야 한다(2026-07-19).
"""

from unittest import mock

from src.agents.models import (
    AlarmContext, AnalyzerOutput, DecisionOutput, DetectorOutput,
    RemediationMode, Severity,
)
from src.agents.operations.executor import handler


def _decision(actions: list[str]) -> DecisionOutput:
    alarm = AlarmContext(
        alarm_name="checkout-5xx",
        alarm_arn="arn:aws:cloudwatch:us-east-1:111122223333:alarm:checkout-5xx",
        state="ALARM",
        reason="threshold crossed",
        metric_name="HTTPCode_Target_5XX_Count",
        namespace="AWS/ApplicationELB",
    )
    analyzer = AnalyzerOutput(
        detector=DetectorOutput(alarm=alarm),
        root_cause="elevated 5xx",
        severity=Severity.P2,
        confidence=0.5,
    )
    return DecisionOutput(
        analyzer=analyzer,
        runbook_id="generic-recovery",
        remediation_mode=RemediationMode.AUTO,
        actions=actions,
    )


class TestNotificationAction:
    def test_executed_in_process_without_ssm_call(self):
        ssm = mock.MagicMock()
        with mock.patch.object(handler, "_SSM", ssm), \
             mock.patch.object(handler, "_SLACK_WEBHOOK", "https://hooks.slack.example/x"):
            executed, skipped = handler._run_ssm_actions(_decision(["AWS-SendSlackAlert"]), mock.MagicMock())
        assert executed == ["AWS-SendSlackAlert"]
        assert skipped == []
        ssm.start_automation_execution.assert_not_called()

    def test_skipped_when_webhook_unset(self):
        ssm = mock.MagicMock()
        with mock.patch.object(handler, "_SSM", ssm), \
             mock.patch.object(handler, "_SLACK_WEBHOOK", ""):
            executed, skipped = handler._run_ssm_actions(_decision(["AWS-SendSlackAlert"]), mock.MagicMock())
        assert executed == []
        assert skipped == ["AWS-SendSlackAlert"]
        ssm.start_automation_execution.assert_not_called()

    def test_mixed_actions_still_dispatch_real_ssm_documents(self):
        ssm = mock.MagicMock()
        ssm.start_automation_execution.return_value = {"AutomationExecutionId": "exec-1"}
        with mock.patch.object(handler, "_SSM", ssm), \
             mock.patch.object(handler, "_SLACK_WEBHOOK", "https://hooks.slack.example/x"), \
             mock.patch.object(handler, "_wait_for_ssm"):
            executed, skipped = handler._run_ssm_actions(
                _decision(["AWS-SendSlackAlert", "AWS-RestartEKSPod"]), mock.MagicMock()
            )
        assert executed == ["AWS-SendSlackAlert", "AWS-RestartEKSPod"]
        assert skipped == []
        ssm.start_automation_execution.assert_called_once()
        assert ssm.start_automation_execution.call_args.kwargs["DocumentName"] == "AWS-RestartEKSPod"
