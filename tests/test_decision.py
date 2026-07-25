"""
Tests for Decision Agent (src/agents/operations/decision/handler.py)

런북 매칭 로직과 실행 모드 결정 로직 검증.
DynamoDB / SNS 호출은 mock 처리.
"""

from unittest.mock import patch, MagicMock

from src.agents.operations.aws.decision import (
    _lookup_dynamo,
    _match_builtin,
    _match_runbook_registry,
    _scan_dynamo_candidates,
    _select_runbook,
    _determine_mode,
)
from src.agents.operations.aws.executor import _build_ssm_params
from src.agents.models import (
    AlarmContext,
    AnalyzerOutput,
    DetectorOutput,
    NormalizedIncident,
    RemediationMode,
    Severity,
)


# ─────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────

def make_alarm(namespace: str, metric: str = "cpu", dimensions: dict = None) -> AlarmContext:
    return AlarmContext(
        alarm_name="test-alarm",
        alarm_arn="arn:...",
        state="ALARM",
        reason=f"{metric} threshold crossed",
        metric_name=metric,
        namespace=namespace,
        dimensions=dimensions or {},
    )


# ─────────────────────────────────────────────────────────────
# _match_builtin
# ─────────────────────────────────────────────────────────────

class TestMatchBuiltin:
    def test_eks_oom_keyword(self):
        alarm = make_alarm("AWS/EKS", metric="pod_restart_total")
        rb    = _match_builtin(alarm, "pod OOMKilled, memory limit exceeded")
        assert rb["runbook_id"] == "eks-pod-oom"

    def test_lambda_throttle_keyword(self):
        alarm = make_alarm("AWS/Lambda", metric="Throttles")
        rb    = _match_builtin(alarm, "lambda throttling detected")
        assert rb["runbook_id"] == "lambda-throttle"

    def test_rds_cpu(self):
        alarm = make_alarm("AWS/RDS", metric="CPUUtilization")
        rb    = _match_builtin(alarm, "high cpu usage on rds instance")
        assert rb["runbook_id"] == "rds-cpu-high"

    def test_kafka_lag(self):
        alarm = make_alarm("AWS/Kafka", metric="ConsumerLag")
        rb    = _match_builtin(alarm, "consumer lag spike detected")
        assert rb["runbook_id"] == "kafka-lag-spike"

    def test_unknown_falls_back_to_generic(self):
        alarm = make_alarm("Custom/Unknown", metric="WeirdMetric")
        rb    = _match_builtin(alarm, "some obscure error")
        assert rb["runbook_id"] == "generic-recovery"

    def test_runbook_has_actions(self):
        alarm = make_alarm("AWS/EKS", metric="pod_restart_total")
        rb    = _match_builtin(alarm, "OOM")
        assert len(rb["actions"]) > 0
        assert rb["capabilities"] == ["restart_workload", "scale_out"]

    @patch("src.agents.operations.aws.decision._scan_dynamo_candidates", return_value=[])
    @patch("src.agents.operations.aws.decision._lookup_dynamo", return_value=None)
    def test_select_runbook_resolves_capabilities_to_actions(self, lookup_dynamo, scan_candidates):
        alarm = make_alarm(
            "AWS/EKS",
            metric="pod_restart_total",
            dimensions={
                "ClusterName": "prod",
                "Namespace": "checkout",
                "PodName": "checkout-api-7d9f6b88d8-xk2lm",
            },
        )
        detector = DetectorOutput(
            alarm=alarm,
            normalized_incident=NormalizedIncident(
                provider="aws",
                service="checkout-api",
                resource_type="kubernetes-workload",
                resource_id="checkout-api-7d9f6b88d8-xk2lm",
                signal_type="reliability",
                recommended_capabilities=["restart_workload", "scale_out"],
                source_metadata={"dimensions": alarm.dimensions, "alarm_name": alarm.alarm_name},
            ),
        )
        analyzer = AnalyzerOutput(
            detector=detector,
            root_cause="pod OOMKilled, memory limit exceeded",
            severity=Severity.P2,
            confidence=0.8,
        )

        runbook_id, actions, rto, _steps = _select_runbook(analyzer)

        assert runbook_id == "eks-pod-oom"
        assert actions == ["AWS-RestartEKSPod", "AWS-ScaleOutEKSNodeGroup"]
        assert rto == 180
        lookup_dynamo.assert_called_once_with("test-alarm")

    @patch("src.agents.operations.aws.decision._scan_dynamo_candidates")
    @patch("src.agents.operations.aws.decision._lookup_dynamo", return_value=None)
    def test_select_runbook_uses_seeded_dynamo_catalog_when_exact_lookup_misses(
        self,
        lookup_dynamo,
        scan_dynamo_candidates,
    ):
        alarm = make_alarm("AWS/Lambda", metric="Throttles", dimensions={"FunctionName": "checkout-fn"})
        detector = DetectorOutput(
            alarm=alarm,
            normalized_incident=NormalizedIncident(
                provider="aws",
                service="checkout-fn",
                resource_type="lambda-function",
                resource_id="checkout-fn",
                signal_type="reliability",
                recommended_capabilities=["increase_function_concurrency"],
                source_metadata={"dimensions": alarm.dimensions, "alarm_name": alarm.alarm_name},
            ),
        )
        analyzer = AnalyzerOutput(
            detector=detector,
            root_cause="lambda throttling detected",
            severity=Severity.P1,
            confidence=0.92,
        )
        scan_dynamo_candidates.return_value = [
            {
                "alarm_name": "lambda-throttle",
                "runbook_id": "lambda-throttle",
                "namespaces": ["AWS/Lambda"],
                "keywords": ["Throttles", "throttl"],
                "capabilities": ["increase_function_concurrency"],
                "actions": ["AWS-IncreaseLambdaConcurrency"],
                "rto_sec": 60,
            }
        ]

        runbook_id, actions, rto, _steps = _select_runbook(analyzer)

        assert runbook_id == "lambda-throttle"
        assert actions == ["AWS-IncreaseLambdaConcurrency"]
        assert rto == 60
        lookup_dynamo.assert_called_once_with("test-alarm")
        scan_dynamo_candidates.assert_called_once_with()

    def test_match_runbook_registry_returns_generic_when_only_generic_exists(self):
        alarm = make_alarm("Custom/Unknown", metric="WeirdMetric")

        rb = _match_runbook_registry(
            alarm,
            "some obscure error",
            [
                {
                    "alarm_name": "generic-recovery",
                    "runbook_id": "generic-recovery",
                    "namespaces": [],
                    "keywords": [],
                    "actions": ["AWS-SendSlackAlert"],
                    "capabilities": ["open_change_request"],
                }
            ],
        )

        assert rb is not None
        assert rb["runbook_id"] == "generic-recovery"


# ─────────────────────────────────────────────────────────────
# _determine_mode
# ─────────────────────────────────────────────────────────────

class TestDetermineMode:
    def test_p1_auto(self):
        assert _determine_mode(Severity.P1, ["AWS-RestartEKSPod"]) == RemediationMode.AUTO

    def test_p2_approve(self):
        assert _determine_mode(Severity.P2, ["AWS-RestartEKSPod"]) == RemediationMode.APPROVE

    def test_p3_manual(self):
        assert _determine_mode(Severity.P3, ["AWS-SendSlackAlert"]) == RemediationMode.MANUAL

    def test_delete_action_forces_approve_even_p1(self):
        # P1 이라도 Delete 액션이 있으면 APPROVE 필요
        mode = _determine_mode(Severity.P1, ["AWS-DeleteRDSInstance"])
        assert mode == RemediationMode.APPROVE

    def test_terminate_action_forces_approve(self):
        mode = _determine_mode(Severity.P1, ["AWS-TerminateEC2Instance"])
        assert mode == RemediationMode.APPROVE

    def test_drop_action_forces_approve(self):
        mode = _determine_mode(Severity.P2, ["AWS-DropSQSQueue"])
        assert mode == RemediationMode.APPROVE

    def test_safe_actions_respect_severity(self):
        # 안전한 액션은 severity 그대로 반영
        assert _determine_mode(Severity.P1, ["AWS-RestartEKSPod"]) == RemediationMode.AUTO
        assert _determine_mode(Severity.P2, ["AWS-RestartEKSPod"]) == RemediationMode.APPROVE


# ─────────────────────────────────────────────────────────────
# _build_ssm_params
# ─────────────────────────────────────────────────────────────

class TestBuildSsmParams:
    def test_eks_params(self):
        alarm = make_alarm("AWS/EKS", dimensions={
            "ClusterName": "prod", "Namespace": "default", "PodName": "api-xyz"
        })
        params = _build_ssm_params("AWS-RestartEKSPod", alarm)
        assert params["ClusterName"] == ["prod"]
        assert params["Namespace"]   == ["default"]
        assert params["PodName"]     == ["api-xyz"]

    def test_lambda_params(self):
        alarm = make_alarm("AWS/Lambda", dimensions={"FunctionName": "my-fn"})
        params = _build_ssm_params("AWS-IncreaseLambdaConcurrency", alarm)
        assert params["FunctionName"] == ["my-fn"]

    def test_rds_params(self):
        alarm = make_alarm("AWS/RDS", dimensions={"DBInstanceIdentifier": "prod-db"})
        params = _build_ssm_params("AWS-ScaleRDSInstance", alarm)
        assert params["DBInstanceIdentifier"] == ["prod-db"]

    def test_missing_dimensions_returns_empty(self):
        alarm  = make_alarm("AWS/EKS", dimensions={})
        params = _build_ssm_params("AWS-RestartEKSPod", alarm)
        # 없는 dimension 은 params 에 포함되지 않아야 함
        assert "ClusterName" not in params

    def test_normalized_incident_overrides_alarm_heuristics(self):
        alarm = make_alarm("AWS/EKS", dimensions={})
        normalized_incident = NormalizedIncident(
            provider="aws",
            service="checkout-api",
            resource_type="kubernetes-workload",
            resource_id="checkout-api-7d9f6b88d8-xk2lm",
            signal_type="reliability",
            source_metadata={
                "alarm_name": "test-alarm",
                "dimensions": {
                    "ClusterName": "prod",
                    "Namespace": "checkout",
                    "PodName": "checkout-api-7d9f6b88d8-xk2lm",
                },
            },
        )

        params = _build_ssm_params("AWS-RestartEKSPod", alarm, normalized_incident)

        assert params["ClusterName"] == ["prod"]
        assert params["Namespace"] == ["checkout"]
        assert params["PodName"] == ["checkout-api-7d9f6b88d8-xk2lm"]


class TestScanDynamoCandidates:
    def test_scan_dynamo_candidates_handles_pagination(self):
        eks = {"alarm_name": "eks-pod-oom", "runbook_id": "eks-pod-oom", "actions": ["AWS-RestartEKSPod"]}
        lam = {"alarm_name": "lambda-throttle", "runbook_id": "lambda-throttle", "actions": ["AWS-IncreaseLambdaConcurrency"]}
        table = MagicMock()
        table.scan.side_effect = [
            {
                "Items": [eks],
                "LastEvaluatedKey": {"alarm_name": "eks-pod-oom"},
            },
            {
                "Items": [lam],
            },
        ]

        with patch("src.agents.operations.aws.decision._DYNAMO") as dynamo:
            dynamo.Table.return_value = table

            items = _scan_dynamo_candidates()

        assert items == [eks, lam]
        dynamo.Table.assert_called_once()
        assert table.scan.call_count == 2

    def test_scan_dynamo_candidates_filters_invalid_items(self):
        valid = {"alarm_name": "eks-pod-oom", "runbook_id": "eks-pod-oom", "actions": ["AWS-RestartEKSPod"]}
        invalid = {"alarm_name": "broken"}  # no runbook_id / actions / capabilities
        table = MagicMock()
        table.scan.side_effect = [{"Items": [valid, invalid]}]

        with patch("src.agents.operations.aws.decision._DYNAMO") as dynamo:
            dynamo.Table.return_value = table

            items = _scan_dynamo_candidates()

        assert items == [valid]

    def test_lookup_dynamo_returns_valid_override(self):
        override = {
            "alarm_name": "MyService-5xx",
            "runbook_id": "myservice-5xx-restart",
            "actions": ["AWS-RestartEKSPod"],
            "rto_sec": 120,
        }
        table = MagicMock()
        table.get_item.return_value = {"Item": override}

        with patch("src.agents.operations.aws.decision._DYNAMO") as dynamo:
            dynamo.Table.return_value = table

            result = _lookup_dynamo("MyService-5xx")

        assert result == override

    def test_lookup_dynamo_skips_malformed_override(self):
        # operator registered an entry with no actions/capabilities
        table = MagicMock()
        table.get_item.return_value = {"Item": {"alarm_name": "MyService-5xx", "runbook_id": "broken"}}

        with patch("src.agents.operations.aws.decision._DYNAMO") as dynamo:
            dynamo.Table.return_value = table

            result = _lookup_dynamo("MyService-5xx")

        assert result is None

    def test_lookup_dynamo_returns_none_when_absent(self):
        table = MagicMock()
        table.get_item.return_value = {}

        with patch("src.agents.operations.aws.decision._DYNAMO") as dynamo:
            dynamo.Table.return_value = table

            assert _lookup_dynamo("Nope") is None


class TestStepResolution:
    """`steps` must reach the executor, or the schema is documentation.

    Before this, only the flat `capabilities` list was resolved — so a runbook
    could declare ordering, conditions, on_failure and per-step verification and
    every one of them would be silently discarded on the way to the executor.
    """

    @staticmethod
    def _analyzer(provider: str = "aws"):
        alarm = AlarmContext(
            alarm_name="test-alarm",
            alarm_arn="arn:aws:cloudwatch:ap-northeast-2:111122223333:alarm:test-alarm",
            state="ALARM",
            reason="threshold crossed",
            metric_name="pod_memory_utilization",
            namespace="ContainerInsights",
        )
        detector = DetectorOutput(
            alarm=alarm,
            normalized_incident=NormalizedIncident(
                provider=provider,
                service="checkout-api",
                resource_type="kubernetes-workload",
                resource_id="checkout-api-7d9f6b88d8-xk2lm",
                signal_type="reliability",
                recommended_capabilities=["restart_workload"],
                source_metadata={"alarm_name": alarm.alarm_name},
            ),
        )
        return AnalyzerOutput(
            detector=detector, root_cause="OOMKilled", severity=Severity.P2, confidence=0.8,
        )

    def test_declared_steps_are_resolved_to_actions_in_order(self):
        from src.agents.operations.aws.decision import _resolve_runbook_steps

        runbook = {
            "runbook_id": "eks-pod-oom",
            "steps": [
                {"name": "restart", "capability": "restart_workload"},
                {"name": "scale", "capability": "scale_out",
                 "condition": {"previous_step_failed": True},
                 "on_failure": "continue",
                 "verify": {"capability": "assert_workload_ready"}},
            ],
        }
        steps = _resolve_runbook_steps(runbook, self._analyzer())
        assert [s["name"] for s in steps] == ["restart", "scale"]
        assert all(s["action"] for s in steps), "every step must carry a resolved action"
        assert steps[1]["condition"] == {"previous_step_failed": True}
        assert steps[1]["on_failure"] == "continue"
        assert steps[1]["verify"] == {"capability": "assert_workload_ready"}

    def test_no_steps_declared_yields_nothing(self):
        """The flat path stays the flat path — this is what keeps it backward compatible."""
        from src.agents.operations.aws.decision import _resolve_runbook_steps

        assert _resolve_runbook_steps({"runbook_id": "x", "capabilities": ["restart_workload"]},
                                      self._analyzer()) == []

    def test_one_unresolvable_capability_does_not_discard_the_plan(self):
        from src.agents.operations.aws.decision import _resolve_runbook_steps

        runbook = {
            "runbook_id": "x",
            "steps": [
                {"name": "good", "capability": "restart_workload"},
                {"name": "bogus", "capability": "no_such_capability_exists"},
            ],
        }
        steps = _resolve_runbook_steps(runbook, self._analyzer())
        assert [s["name"] for s in steps] == ["good"]

    def test_steps_become_the_action_list_in_step_order(self):
        """`actions` stays populated so reports and records are unchanged."""
        from src.agents.operations.aws.decision import _resolve_runbook_steps

        runbook = {"runbook_id": "x", "steps": [{"name": "a", "capability": "restart_workload"}]}
        steps = _resolve_runbook_steps(runbook, self._analyzer())
        assert [s["action"] for s in steps] == [steps[0]["action"]]

    def test_builtin_capability_catalog_fills_in_when_the_row_declares_none(self):
        """CAPABILITY_RUNBOOKS was dead data — nothing outside its own tests read it.

        Every selectable runbook id also lives there with full steps, so without
        this lookup the entire step contract stayed unreachable in production.
        """
        from src.agents.operations.aws.decision import _resolve_runbook_steps

        steps = _resolve_runbook_steps({"runbook_id": "eks-pod-oom"}, self._analyzer())
        assert [s["name"] for s in steps] == ["restart_pod", "scale_nodes"]
        assert steps[1]["condition"] == {"previous_step_failed": True}
        assert steps[0]["verify"]["capability"] == "assert_workload_ready"

    def test_the_row_wins_over_the_builtin_catalog(self):
        """An operator editing the DynamoDB row must be able to change the plan."""
        from src.agents.operations.aws.decision import _resolve_runbook_steps

        steps = _resolve_runbook_steps(
            {"runbook_id": "eks-pod-oom",
             "steps": [{"name": "only_this", "capability": "restart_workload"}]},
            self._analyzer(),
        )
        assert [s["name"] for s in steps] == ["only_this"]

    def test_every_selectable_runbook_declares_steps_somewhere(self):
        """Data-level claim: the lookup has something to find for each of them."""
        from src.agents.runbooks.catalog import BUILTIN_RUNBOOKS, CAPABILITY_RUNBOOKS

        for runbook in BUILTIN_RUNBOOKS.values():
            runbook_id = runbook["runbook_id"]
            assert CAPABILITY_RUNBOOKS.get(runbook_id, {}).get("steps"), (
                f"{runbook_id} is selectable but has no step definition to reach the executor"
            )

    def test_capability_must_suit_the_incident_or_the_step_is_dropped(self):
        """A lambda capability against a kubernetes workload cannot resolve.

        Worth pinning: the fill-in must not smuggle a plan that does not fit the
        incident just because the ids happen to match.
        """
        from src.agents.operations.aws.decision import _resolve_runbook_steps

        steps = _resolve_runbook_steps({"runbook_id": "lambda-throttle"}, self._analyzer())
        assert steps == [], "an unresolvable capability must not become an action"
