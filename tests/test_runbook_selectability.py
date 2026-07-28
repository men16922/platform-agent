"""
Can anything actually choose these runbooks?

Four capability runbooks — disk-full, health-check-failure, certificate-expiry,
network-latency-high — shipped with complete steps, valid schemas, and a
capability→action mapping in all four provider adapters. Every test they had
passed. None of them could ever run: runbook *selection* iterates
`BUILTIN_RUNBOOKS`, and they had no entry there, so no alarm could reach them.

The existing catalog tests could not see it because each one starts from
`CAPABILITY_RUNBOOKS[<id>]` — they ask "is this plan well-formed", never "can
anyone get here". That is the same shape as every authorization defect this repo
has paid for: a thing that is declared, valid, and unreachable.

So these tests enter from the alarm end.
"""

from __future__ import annotations

import pytest

from src.agents.adapters.execution.onprem import _action_for
from src.agents.operations.aws.decision import _match_builtin, _match_runbook_registry
from src.agents.operations.runners.onprem_verify import _CHECKS
from src.agents.runbooks.catalog import BUILTIN_RUNBOOKS, CAPABILITY_RUNBOOKS
from src.agents.models import (
    AlarmContext,
    AnalyzerOutput,
    DetectorOutput,
    NormalizedIncident,
    Severity,
)


def _onprem_can_execute(capability: str) -> bool:
    """Does the on-prem adapter map this capability to an action for any resource?

    Asked through `_action_for` rather than by reading its table, so the answer
    stays true if the mapping moves.
    """
    for resource in (
        "kubernetes-workload", "serverless-service", "database-instance",
        "streaming-consumer", "storage-volume", "network-endpoint",
        "certificate", "cloud-resource",
    ):
        try:
            _action_for(capability, resource)
            return True
        except ValueError:
            continue
    return False


def make_alarm(namespace: str, metric: str) -> AlarmContext:
    return AlarmContext(
        alarm_name="test-alarm",
        alarm_arn="arn:...",
        state="ALARM",
        reason=f"{metric} threshold crossed",
        metric_name=metric,
        namespace=namespace,
        dimensions={},
    )


def _analyzer_for(namespace: str, metric: str, root_cause: str, resource_type: str) -> AnalyzerOutput:
    alarm = make_alarm(namespace, metric)
    return AnalyzerOutput(
        detector=DetectorOutput(
            alarm=alarm,
            normalized_incident=NormalizedIncident(
                provider="aws",
                service="checkout-api",
                resource_type=resource_type,
                resource_id="res-1",
                signal_type="reliability",
                source_metadata={"alarm_name": alarm.alarm_name},
            ),
        ),
        root_cause=root_cause,
        severity=Severity.P2,
        confidence=0.9,
    )


class TestEveryPlanIsReachable:
    def test_every_capability_runbook_has_a_selection_entry(self):
        """The structural invariant that was broken.

        A capability runbook with no built-in entry is a plan nothing can
        choose — it will pass every schema test forever while never running.
        """
        unreachable = sorted(set(CAPABILITY_RUNBOOKS) - set(BUILTIN_RUNBOOKS))
        assert unreachable == [], (
            f"{unreachable} declare steps but no alarm can select them"
        )

    def test_no_selection_entry_points_at_a_missing_plan(self):
        """The mirror failure: selectable, then nothing to execute."""
        dangling = sorted(set(BUILTIN_RUNBOOKS) - set(CAPABILITY_RUNBOOKS))
        assert dangling == [], f"{dangling} are selectable but declare no steps"


class TestTheFourAreNowSelectable:
    """Behavioural, from the alarm end — the entry no previous test used."""

    @pytest.mark.parametrize(
        "namespace,metric,root_cause,expected",
        [
            ("CWAgent", "disk_used_percent", "filesystem at 97%, no space left", "disk-full"),
            ("AWS/RDS", "FreeStorageSpace", "storage headroom exhausted", "disk-full"),
            (
                "AWS/ApplicationELB", "UnHealthyHostCount",
                "targets failing health check after deploy", "health-check-failure",
            ),
            (
                "AWS/CertificateManager", "DaysToExpiry",
                "certificate expiring in 5 days", "certificate-expiry",
            ),
            (
                "AWS/NetworkELB", "TargetResponseTime",
                "p99 latency doubled", "network-latency-high",
            ),
        ],
    )
    def test_alarm_selects_the_matching_runbook(self, namespace, metric, root_cause, expected):
        assert _match_builtin(make_alarm(namespace, metric), root_cause)["runbook_id"] == expected

    def test_selected_runbook_carries_executable_actions(self):
        """Selectable but actionless would just move the dead end one step later."""
        rb = _match_builtin(make_alarm("CWAgent", "disk_used_percent"), "disk full")
        assert rb["actions"], "a selectable runbook with no actions is still unreachable"
        assert rb["capabilities"] == ["cleanup_disk_space", "expand_storage"]


class TestExistingSelectionsAreUnchanged:
    """Four new entries in a scored matcher can quietly steal existing matches.

    `_match_runbook_registry` gives 2 for a namespace prefix hit and 1 per
    keyword, and keeps the first entry on a tie — so the new rows are appended,
    and these assert that the appending did not move anything.
    """

    @pytest.mark.parametrize(
        "namespace,metric,root_cause,expected",
        [
            ("AWS/EKS", "pod_restart_total", "pod OOMKilled, memory limit exceeded", "eks-pod-oom"),
            ("AWS/Lambda", "Throttles", "lambda throttling detected", "lambda-throttle"),
            ("AWS/RDS", "CPUUtilization", "high cpu usage on rds instance", "rds-cpu-high"),
            ("AWS/Kafka", "ConsumerLag", "consumer lag spike detected", "kafka-lag-spike"),
            ("Custom/Unknown", "WeirdMetric", "some obscure error", "generic-recovery"),
        ],
    )
    def test_previously_matching_alarms_still_match(self, namespace, metric, root_cause, expected):
        assert _match_builtin(make_alarm(namespace, metric), root_cause)["runbook_id"] == expected

    def test_rds_disk_and_rds_cpu_stay_separable(self):
        """Both claim the AWS/RDS namespace; the keyword has to break the tie."""
        cpu = _match_builtin(make_alarm("AWS/RDS", "CPUUtilization"), "cpu saturated")
        disk = _match_builtin(make_alarm("AWS/RDS", "FreeStorageSpace"), "storage exhausted")
        assert cpu["runbook_id"] == "rds-cpu-high"
        assert disk["runbook_id"] == "disk-full"


class TestTheSeededTableDoesNotShadowTheBuiltInTier:
    """The second layer, and the one that actually mattered in production.

    `_select_runbook` documents four priority tiers: exact DynamoDB lookup,
    DynamoDB scan heuristic, built-in registry, generic fallback. The scan tier
    used to answer "nothing matched" with the *table's own* generic-recovery
    row — and the seeded table has one — so tier 3 was unreachable in every
    deployed environment. A live scan of `incident-runbooks` returns exactly the
    five ids seeded before this change, which is why the four new runbooks
    resolved to generic-recovery end to end while `_match_builtin` picked them
    correctly in isolation.
    """

    SEEDED = [dict(BUILTIN_RUNBOOKS[k]) for k in
              ("eks-pod-oom", "lambda-throttle", "rds-cpu-high", "kafka-lag-spike", "generic-recovery")]

    def test_scan_tier_declines_instead_of_answering_generic(self):
        alarm = make_alarm("CWAgent", "disk_used_percent")
        assert _match_runbook_registry(
            alarm, "disk full", self.SEEDED, allow_generic=False
        ) is None, "an unmatched scan must fall through, not answer for the tier below"

    def test_generic_fallback_still_exists_where_it_belongs(self):
        """Removing the fallback from one tier must not remove it from the flow."""
        alarm = make_alarm("Custom/Unknown", "WeirdMetric")
        assert _match_runbook_registry(alarm, "obscure", self.SEEDED)["runbook_id"] == "generic-recovery"
        assert _match_builtin(alarm, "obscure")["runbook_id"] == "generic-recovery"

    def test_a_seeded_table_still_wins_when_it_actually_matches(self):
        """The tier order is unchanged for the case it exists to serve."""
        alarm = make_alarm("AWS/EKS", "pod_restart_total")
        matched = _match_runbook_registry(alarm, "OOMKilled", self.SEEDED, allow_generic=False)
        assert matched["runbook_id"] == "eks-pod-oom"

    def test_a_weak_seeded_match_does_not_beat_a_strong_built_in_one(self, monkeypatch):
        """The deeper half of the same defect, found live after the first fix.

        `allow_generic=False` stopped the stale table answering when *nothing*
        matched. It did nothing about the table answering with a *worse* match:
        a `KubePodNotReady` alert scored 1 against the seeded `eks-pod-oom`
        (its root cause mentioned OOMKilled) and 3 against the built-in
        `health-check-failure`, and the weaker one won purely because its
        catalog was scanned first. Two heuristics over two catalogs have to be
        one heuristic over the union.
        """
        import src.agents.operations.aws.decision as decision

        monkeypatch.setattr(decision, "_lookup_dynamo", lambda _name: None)
        monkeypatch.setattr(decision, "_scan_dynamo_candidates", lambda: self.SEEDED)

        analyzer = _analyzer_for(
            "ONPREM/kubernetes-workload",
            "availability",
            "the readiness probe never passes; possibly OOMKilled before logging",
            "kubernetes-workload",
        )
        analyzer.detector.alarm.reason = "KubePodNotReady pod stuck in a non-ready state"
        runbook_id, _actions, _rto, _steps = decision._select_runbook(analyzer)
        assert runbook_id == "health-check-failure", (
            "a stale seed must not cap what selection can reach"
        )

    def test_a_seeded_row_still_wins_an_equal_score(self):
        """Operator precedence is real where it is expressed — on ties."""
        alarm = AlarmContext(
            alarm_name="a", alarm_arn="", state="ALARM",
            reason="OOM observed", metric_name="availability",
            namespace="ONPREM/kubernetes-workload", dimensions={},
        )
        seeded = [{**BUILTIN_RUNBOOKS["eks-pod-oom"], "runbook_id": "operator-eks-pod-oom"}]
        picked = _match_runbook_registry(
            alarm, "OOMKilled", [*seeded, *BUILTIN_RUNBOOKS.values()],
            allow_generic=False, resource_type="kubernetes-workload",
        )
        assert picked["runbook_id"] == "operator-eks-pod-oom"

    def test_selection_reaches_the_built_in_tier_through_a_seeded_table(self, monkeypatch):
        """Asserted at the CALL SITE, because the parameter alone proves nothing.

        Written after the fact: reverting the caller to the defaulting call left
        every test above passing — they exercise `_match_runbook_registry`
        directly with the flag already set, so they cannot see a caller that
        forgot it. Only an end-to-end selection catches that, and this is it.
        """
        import src.agents.operations.aws.decision as decision

        monkeypatch.setattr(decision, "_lookup_dynamo", lambda _name: None)
        monkeypatch.setattr(decision, "_scan_dynamo_candidates", lambda: self.SEEDED)

        runbook_id, actions, rto, steps = decision._select_runbook(
            _analyzer_for("CWAgent", "disk_used_percent", "filesystem full", "storage-volume")
        )
        assert runbook_id == "disk-full", (
            "a seeded table without this runbook must not answer for it"
        )
        assert [s["action"] for s in steps] == ["AWS-CleanupEBSVolume", "AWS-ExpandEBSVolume"]
        assert rto == 300


class TestOnPremAlertsReachTheseRunbooks:
    """Selectable on the AWS path is not selectable.

    Found by running the live webhook after making the four reachable: an
    on-prem disk-filling alert still resolved to generic-recovery. The detector
    builds a synthetic alarm for non-AWS signals and set ``reason`` to
    ``signal_type`` — a duplicate of ``metric_name`` on the next line — so the
    matcher scored keywords against "availability availability …". The alertname
    and summary were normalised and stored the whole time and simply never
    reached selection.

    These enter from an Alertmanager payload, which is the only entry that could
    have caught it.
    """

    @staticmethod
    def _select(alertname: str, summary: str, labels: dict, root_cause: str):
        from src.agents.operations.aws.decision import _select_runbook
        from src.agents.operations.aws.detector import lambda_handler as detect

        payload = {
            "status": "firing",
            "groupLabels": {"alertname": alertname},
            "commonLabels": {"alertname": alertname, "severity": "warning", **labels},
            "commonAnnotations": {"summary": summary},
            "alerts": [
                {
                    "status": "firing",
                    "labels": {"alertname": alertname, **labels},
                    "annotations": {"summary": summary},
                }
            ],
        }
        detected = detect(payload, None)
        detector = DetectorOutput(
            alarm=AlarmContext(**detected["alarm"]),
            normalized_incident=NormalizedIncident(**detected["normalized_incident"]),
        )
        analyzer = AnalyzerOutput(
            detector=detector, root_cause=root_cause, severity=Severity.P2, confidence=0.9
        )
        return _select_runbook(analyzer)

    # Real kube-prometheus-stack alert names and the kind of summary text they
    # actually carry. The first draft of these cases planted the runbook's own
    # keyword in the summary ("…, disk full projected in 18h") and passed while
    # the live webhook still answered generic-recovery for the same alert — the
    # test was fitted to the keyword list rather than to what Alertmanager sends.
    # Nothing here contains a literal keyword phrase; matching has to come from
    # the alert name and ordinary wording.
    @pytest.mark.parametrize(
        "alertname,summary,labels,root_cause,expected",
        [
            (
                "NodeFilesystemSpaceFillingUp",
                "Filesystem on /var will fill in ~18 hours; currently 78% used",
                {"namespace": "monitoring", "service": "reporting-worker"},
                "volume usage on the reporting worker is climbing steadily",
                "disk-full",
            ),
            (
                "KubePodNotReady",
                "Pod payments-api has been in a non-ready state for 15 minutes",
                {"namespace": "payments", "service": "payments-api", "pod": "p-1"},
                "the container fails its startup check shortly after rollout",
                "health-check-failure",
            ),
            (
                "CertManagerCertExpirySoon",
                "TLS cert for ingress renews in 5 days and has not rotated",
                {"service": "ingress"},
                "automatic rotation has not run for this ingress",
                "certificate-expiry",
            ),
            (
                "HighRequestLatency",
                "p99 for the api service doubled over the last 30 minutes",
                {"namespace": "payments", "service": "api", "pod": "a-1"},
                "response times rose sharply across endpoints",
                "network-latency-high",
            ),
        ],
    )
    def test_alertmanager_alert_selects_the_matching_runbook(
        self, alertname, summary, labels, root_cause, expected
    ):
        runbook_id, _actions, _rto, _steps = self._select(alertname, summary, labels, root_cause)
        assert runbook_id == expected

    def test_selected_actions_are_on_prem_not_the_aws_fallback(self):
        """The fallback that hides a mismatch: `_resolve_runbook_actions` catches
        an unresolvable capability and returns the runbook's hardcoded AWS
        action names, so a wrong pick surfaces as AWS-* actions on an on-prem
        incident rather than as an error."""
        _id, actions, _rto, _steps = self._select(
            "NodeFilesystemSpaceFillingUp",
            "Filesystem /var 78% used, disk full projected in 18h",
            {"namespace": "monitoring", "service": "reporting-worker"},
            "disk usage climbing",
        )
        assert actions and all(a.startswith("ONPREM-") for a in actions), actions

    def test_existing_onprem_selection_is_unchanged(self):
        runbook_id, _a, _r, _s = self._select(
            "KubePodCrashLooping",
            "pod OOMKilled repeatedly, MemoryPressure",
            {"namespace": "payments", "service": "payments-api", "pod": "p-2"},
            "pod OOMKilled, memory limit exceeded",
        )
        assert runbook_id == "eks-pod-oom"


class TestReasonCarriesWhatFired:
    """`reason` is the text selection reads; it was a copy of `metric_name`."""

    @staticmethod
    def _alarm(**incident_kwargs):
        from src.agents.operations.aws.detector import _synthetic_alarm

        return _synthetic_alarm(
            NormalizedIncident(
                provider="onprem",
                service="svc",
                resource_type="kubernetes-workload",
                resource_id="r",
                signal_type="availability",
                **incident_kwargs,
            ),
            "onprem",
        )

    def test_rule_name_and_description_reach_the_alarm(self):
        alarm = self._alarm(
            source_metadata={"alertname": "NodeFilesystemSpaceFillingUp"},
            observations={"summary": "disk 78% used"},
        )
        assert "NodeFilesystemSpaceFillingUp" in alarm.reason
        assert "disk 78% used" in alarm.reason
        assert alarm.reason != alarm.metric_name, "reason must not duplicate metric_name"

    @pytest.mark.parametrize(
        "metadata,expected",
        [
            ({"policy_name": "gcp-disk-policy"}, "gcp-disk-policy"),
            ({"alert_rule": "azure-disk-rule"}, "azure-disk-rule"),
        ],
    )
    def test_other_providers_are_looked_up_not_special_cased(self, metadata, expected):
        assert expected in self._alarm(source_metadata=metadata).reason

    def test_falls_back_to_signal_type_when_nothing_descriptive_exists(self):
        """An adapter carrying none of these must not hand matching an empty
        string — that would be worse than the duplicate it replaced."""
        assert self._alarm().reason == "availability"


class TestResourceTypeGate:
    """`resource_types` was declared on every runbook and read by nothing.

    Without it, a keyword hit could select a database runbook for a Kubernetes
    workload — and the failure is quiet, because unresolvable capabilities fall
    back to the runbook's hardcoded AWS action names.
    """

    def test_a_database_runbook_is_not_chosen_for_a_kubernetes_workload(self):
        alarm = AlarmContext(
            alarm_name="a", alarm_arn="", state="ALARM",
            reason="CPUUtilization cpu saturated on the pod",
            metric_name="availability", namespace="ONPREM/kubernetes-workload", dimensions={},
        )
        picked = _match_runbook_registry(
            alarm, "cpu high", BUILTIN_RUNBOOKS.values(), resource_type="kubernetes-workload"
        )
        assert picked is None or picked["runbook_id"] != "rds-cpu-high"

    def test_the_same_alarm_still_reaches_it_for_a_database(self):
        """Guard the guard: a gate that excluded everything would pass the test
        above while breaking selection entirely."""
        alarm = AlarmContext(
            alarm_name="a", alarm_arn="", state="ALARM",
            reason="CPUUtilization cpu saturated", metric_name="cpu",
            namespace="AWS/RDS", dimensions={},
        )
        picked = _match_runbook_registry(
            alarm, "cpu high", BUILTIN_RUNBOOKS.values(), resource_type="database-instance"
        )
        assert picked["runbook_id"] == "rds-cpu-high"

    def test_unknown_resource_type_does_not_exclude_anything(self):
        alarm = make_alarm("AWS/EKS", "pod_restart_total")
        assert _match_builtin(alarm, "OOMKilled")["runbook_id"] == "eks-pod-oom"

    def test_generic_recovery_is_never_gated(self):
        """It is the answer when nothing fits, so gating it by resource type
        would leave some incidents with no runbook at all."""
        alarm = make_alarm("Custom/Unknown", "WeirdMetric")
        picked = _match_builtin(alarm, "obscure", resource_type="streaming-consumer")
        assert picked["runbook_id"] == "generic-recovery"


class TestDeclaredVerificationsExist:
    """A declared check nobody implements is a *failed* check, by design.

    That is the right default, and it means making a runbook selectable can turn
    a dormant gap into a live one: `health-check-failure` verifies its restart
    with `assert_health_check_passing`, so an unimplemented check would have made
    the runbook cascade to rollback every time the restart actually worked.
    """

    def test_every_reachable_verify_capability_is_implemented(self):
        """Scoped to steps on-prem can actually execute.

        `_CHECKS` is the on-prem check registry, so demanding it cover every
        declared verification would demand an on-prem implementation for
        `assert_concurrency_applied` — whose step (`increase_function_concurrency`,
        a Lambda capability) on-prem cannot execute at all and therefore never
        verifies. A check for an unreachable action is not a gap; asserting it
        would be inventing work.
        """
        declared = {
            step["verify"]["capability"]
            for rb in CAPABILITY_RUNBOOKS.values()
            for step in rb["steps"]
            if step.get("verify") and _onprem_can_execute(step["capability"])
        }
        missing = sorted(declared - set(_CHECKS))
        assert missing == [], (
            f"{missing} are declared as proof for steps on-prem runs, but cannot "
            "be run — those steps would fail verification while working correctly"
        )

    def test_the_scoping_is_not_vacuous(self):
        """Guard the guard: a mis-scoped filter that excluded everything would
        make the test above pass by checking nothing."""
        assert _onprem_can_execute("restart_workload")
        assert not _onprem_can_execute("increase_function_concurrency")
