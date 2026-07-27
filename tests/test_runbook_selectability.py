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
