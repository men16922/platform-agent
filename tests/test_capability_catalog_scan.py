"""
The GCP/Azure capability-based catalog scan — tier 2 of `_select_runbook`.

The tier was unreachable in principle, in both providers, for the same three
reasons stacked in one twelve-line block:

  1. `if not validate_runbook(rb): continue` — `validate_runbook` returns the
     *list of problems*, so an empty list means valid. The inverted test skipped
     every valid runbook and only ever proceeded on malformed ones. (`schema.py`
     ships `is_valid_runbook` for exactly the boolean form; AWS uses the truthy
     polarity correctly.)
  2. `rb.get("steps", [])` on a `BUILTIN_RUNBOOKS` entry — steps live in
     `CAPABILITY_RUNBOOKS`. The built-in entry declares `capabilities`. The
     derived set was empty for all nine entries, so the intersection could never
     be non-empty.
  3. `rb.get("estimated_rto_sec", 300)` — the schema contract field is
     `rto_sec`, so even a match would have reported the default, never the
     catalog's RTO.

The consequence was not a crash: every GCP and Azure incident fell through to
`generic-recovery`, whatever it matched. Actions still resolved from the
analyzer's recommended capabilities, so the decision looked populated — only
the runbook it claimed to be following, and its RTO, were wrong.

The tests it had asked `"runbook_id" in result` and `result["runbook_id"] != ""`.
Both are true of `"generic-recovery"` forever. So these enter from the other
end: given capabilities that match a specific catalog entry, *which* runbook
comes back, and does it carry that entry's RTO.
"""

from __future__ import annotations

import importlib
from unittest import mock

import pytest

from src.agents.models import (
    AlarmContext,
    AnalyzerOutput,
    DetectorOutput,
    NormalizedIncident,
    Severity,
)
from src.agents.runbooks.catalog import BUILTIN_RUNBOOKS

# The two providers that carry this tier. A third one copying the block is
# covered by adding its module path here.
PROVIDERS = ["gcp", "azure"]


def _decision(provider: str):
    return importlib.import_module(f"src.agents.operations.{provider}.decision")


def _analyzer(
    capabilities: list[str],
    provider: str = "gcp",
    resource_type: str = "kubernetes-workload",
) -> AnalyzerOutput:
    alarm = AlarmContext(
        alarm_name="capability-scan-alarm",
        alarm_arn="arn:...",
        state="ALARM",
        reason="threshold crossed",
        metric_name="memory_utilization",
        namespace="kubernetes.io/container",
    )
    return AnalyzerOutput(
        detector=DetectorOutput(
            alarm=alarm,
            normalized_incident=NormalizedIncident(
                provider=provider,
                service="checkout-api",
                resource_type=resource_type,
                resource_id="deploy/api",
                signal_type="reliability",
                recommended_capabilities=capabilities,
                source_metadata={"alarm_name": alarm.alarm_name},
            ),
        ),
        root_cause="container OOMKilled repeatedly",
        severity=Severity.P2,
        confidence=0.9,
    )


@pytest.fixture(autouse=True)
def _no_registry_lookup():
    """Tier 1 must not reach out; these tests are about tier 2.

    Both lookups already swallow every exception and return None offline, so
    this is about not depending on that — a machine with credentials would
    otherwise take a different path through the same test.
    """
    with mock.patch(
        "src.agents.operations.gcp.decision._lookup_firestore_runbook", return_value=None
    ), mock.patch(
        "src.agents.operations.azure.decision._lookup_cosmos_runbook", return_value=None
    ):
        yield


# ------------------------------------------------------------------
# The tier runs at all
# ------------------------------------------------------------------

class TestCapabilityScanReachesTheCatalog:
    @pytest.mark.parametrize("provider", PROVIDERS)
    @pytest.mark.parametrize(
        "capabilities,expected",
        [
            (["restart_workload", "scale_out"], "eks-pod-oom"),
            (["cleanup_disk_space", "expand_storage"], "disk-full"),
            (["rollback_release"], "health-check-failure"),
            (["renew_certificate"], "certificate-expiry"),
            (["scale_database_primary"], "rds-cpu-high"),
            (["scale_out_workers"], "kafka-lag-spike"),
            (["increase_function_concurrency"], "lambda-throttle"),
            (["drain_node"], "network-latency-high"),
        ],
    )
    def test_recommended_capabilities_select_the_matching_runbook(
        self, provider, capabilities, expected
    ):
        # Ask each entry as the kind of resource it declares. The fixture used to
        # ask every one of them as a Kubernetes workload, which only worked while
        # selection ignored `resource_types` — a lambda runbook is not reachable
        # from a Kubernetes incident and should not be.
        runbook_id, _actions, rto = _decision(provider)._select_runbook(
            _analyzer(
                capabilities,
                provider,
                resource_type=BUILTIN_RUNBOOKS[expected]["resource_types"][0],
            )
        )

        assert runbook_id == expected, (
            f"{provider}: {capabilities} matched {runbook_id!r}; "
            f"{expected!r} declares those capabilities in the catalog"
        )
        # Asserted here, across every case, rather than only in a single-runbook
        # test: the first version of that test picked `disk-full`, whose RTO is
        # 300 — the exact value the misread field defaulted to. It passed against
        # the defect. Spread over eight entries with six distinct RTOs, no single
        # default can collude with all of them.
        assert rto == BUILTIN_RUNBOOKS[expected]["rto_sec"], (
            f"{provider}: {expected} reported rto={rto}, catalog says "
            f"{BUILTIN_RUNBOOKS[expected]['rto_sec']}"
        )

    def test_the_catalog_still_holds_rtos_a_default_cannot_impersonate(self):
        """Keeps the assertion above load-bearing as the catalog is retuned.

        If every entry were ever retuned to one value, the check above would go
        quiet without going red — a guard that passes for a reason nobody chose.
        """
        selectable = {k: v["rto_sec"] for k, v in BUILTIN_RUNBOOKS.items() if v["rto_sec"]}

        assert len(set(selectable.values())) > 1, (
            f"every runbook now declares the same RTO ({selectable}); the "
            "selection tests can no longer tell a real RTO from a default"
        )

    @pytest.mark.parametrize("provider", PROVIDERS)
    def test_every_catalog_entry_is_reachable_through_its_own_capabilities(self, provider):
        """No entry may be selectable in name only.

        Asks each entry with its own first declared capability, on a resource
        type it declares — the pairing the entry actually claims to handle.
        An entry that answers with a *different* runbook is legitimate —
        capabilities overlap and the first match wins — so the claim is the
        weaker, honest one: some catalog entry answers, and it is never the
        fallback.
        """
        select = _decision(provider)._select_runbook

        unmatched = []
        for rb_id, rb in BUILTIN_RUNBOOKS.items():
            if rb_id == "generic-recovery":
                continue  # its capability *is* the fallback's
            resource_type = (rb.get("resource_types") or [""])[0]
            for capability in rb["capabilities"]:
                chosen, _actions, _rto = select(
                    _analyzer([capability], provider, resource_type=resource_type)
                )
                if chosen == "generic-recovery":
                    unmatched.append((rb_id, capability))

        assert unmatched == [], (
            f"{provider}: these declared capabilities reach nothing but the fallback: {unmatched}"
        )


# ------------------------------------------------------------------
# ...and still refuses what it should
# ------------------------------------------------------------------

class TestTheScanStillFallsThrough:
    @pytest.mark.parametrize("provider", PROVIDERS)
    def test_an_unknown_capability_falls_back_to_generic(self, provider):
        """The other side of the load: matching must not become matching anything."""
        runbook_id, _actions, rto = _decision(provider)._select_runbook(
            _analyzer(["teleport_the_datacentre"], provider)
        )

        assert runbook_id == "generic-recovery"
        assert rto is None

    @pytest.mark.parametrize("provider", PROVIDERS)
    def test_no_recommended_capabilities_falls_back_to_generic(self, provider):
        runbook_id, _actions, _rto = _decision(provider)._select_runbook(
            _analyzer([], provider)
        )

        assert runbook_id == "generic-recovery"

    @pytest.mark.parametrize("provider", PROVIDERS)
    def test_a_malformed_catalog_entry_is_skipped_not_selected(self, provider):
        """The validity check must still be doing work, in the correct direction.

        The decoy matches on capabilities and is placed first, so the only thing
        that can keep it from being chosen is validation. Without it the tier
        would happily select a runbook whose contract is broken.
        """
        decoy = {
            "runbook_id": "decoy",
            "capabilities": ["restart_workload"],
            "actions": ["GCP-RolloutRestartGKEWorkload"],
            "rto_sec": "soon",  # must be an integer or null → invalid
        }
        catalog = {"decoy": decoy, **BUILTIN_RUNBOOKS}

        with mock.patch.object(_decision(provider), "BUILTIN_RUNBOOKS", catalog):
            runbook_id, _actions, _rto = _decision(provider)._select_runbook(
                _analyzer(["restart_workload"], provider)
            )

        assert runbook_id == "eks-pod-oom", (
            f"{provider}: selected {runbook_id!r} — a runbook failing the schema "
            "contract must be skipped, not executed"
        )


# ------------------------------------------------------------------
# Tier 1 reads the same contract
# ------------------------------------------------------------------

class TestRegistryRunbookUsesTheContractField:
    """The operator-registered document is validated by `runbooks/schema.py`.

    That contract names the field `rto_sec`, and the AWS DynamoDB path reads
    `rto_sec`. GCP/Azure read `estimated_rto_sec` — which is the *output* field
    name on `DecisionOutput`, not the runbook item's. Nothing seeds Firestore or
    Cosmos today, so this was latent rather than live: an operator following the
    documented contract would have got no RTO at all.
    """

    @pytest.mark.parametrize(
        "provider,lookup",
        [
            ("gcp", "src.agents.operations.gcp.decision._lookup_firestore_runbook"),
            ("azure", "src.agents.operations.azure.decision._lookup_cosmos_runbook"),
        ],
    )
    def test_registry_rto_is_read_from_rto_sec(self, provider, lookup):
        registered = {
            "runbook_id": "operator-override",
            "alarm_name": "capability-scan-alarm",
            "capabilities": ["restart_workload"],
            "actions": ["Custom-RestartWorkload"],
            "rto_sec": 42,
            "steps": [{"name": "restart", "capability": "restart_workload"}],
        }

        with mock.patch(lookup, return_value=registered):
            runbook_id, _actions, rto = _decision(provider)._select_runbook(
                _analyzer(["restart_workload"], provider)
            )

        assert runbook_id == "operator-override"
        assert rto == 42, "the registry path must read the contract's rto_sec"


# ------------------------------------------------------------------
# The two implementations are the same implementation
# ------------------------------------------------------------------

class TestProvidersAgree:
    @pytest.mark.parametrize(
        "capabilities",
        [
            ["restart_workload", "scale_out"],
            ["cleanup_disk_space"],
            ["rollback_release"],
            ["teleport_the_datacentre"],
        ],
    )
    def test_same_capabilities_select_the_same_runbook_everywhere(self, capabilities):
        """The defect was one block copied into two files, and it diverging is
        how it stays fixed in one and rots in the other.

        Only the runbook choice is compared — the resolved *actions* are
        provider-specific by design.
        """
        chosen = {
            provider: _decision(provider)._select_runbook(
                _analyzer(capabilities, provider)
            )[0]
            for provider in PROVIDERS
        }

        assert len(set(chosen.values())) == 1, (
            f"{capabilities} selects different runbooks per provider: {chosen}"
        )


# ------------------------------------------------------------------
# The tier reads the resource type the runbook declares
# ------------------------------------------------------------------

# Every resource type the catalog names, so the sweep below cannot silently
# shrink when a runbook adds one.
ALL_RESOURCE_TYPES = sorted(
    {rt for rb in BUILTIN_RUNBOOKS.values() for rt in (rb.get("resource_types") or [])}
)


class TestSelectionRespectsResourceType:
    """Tier 2 matched on capabilities alone and never read `resource_types`.

    AWS closed this: `aws/decision.py::_fits_resource` excludes a runbook whose
    declared types do not contain the incident's, because "nothing stopped an
    RDS runbook being chosen for a Kubernetes workload". The field has been
    declared on every catalog entry since the catalog existed, and on GCP/Azure
    it had no consumer in the selection path at all — 67 of 81
    (runbook, resource_type) pairs that AWS excludes were still selectable here.

    The failure is quiet, and quieter than the AWS one. AWS falls back to the
    runbook's hardcoded action names and hands the executor another provider's
    actions; GCP/Azure drop the unresolvable capability and return a *shorter*
    action list. So `certificate-expiry` on a Kubernetes workload came back
    selected, with rto=600, carrying only the notify action — a plan that
    claims to renew a certificate and does not.

    Ground truth here is the catalog's own declaration, not a provider's helper,
    so the guard cannot be satisfied by the two implementations agreeing on
    something wrong.
    """

    @pytest.mark.parametrize("provider", PROVIDERS)
    @pytest.mark.parametrize(
        "capability,resource_type,must_not_select",
        [
            # eks-pod-oom and health-check-failure both declare `restart_workload`
            # and neither declares a database.
            ("restart_workload", "database-instance", {"eks-pod-oom", "health-check-failure"}),
            # disk-full declares three types; a function is not one of them.
            ("cleanup_disk_space", "lambda-function", {"disk-full"}),
            # kafka-lag-spike is the only holder of `scale_out_workers`.
            ("scale_out_workers", "certificate", {"kafka-lag-spike"}),
            # certificate-expiry: the pair that made this visible.
            ("renew_certificate", "kubernetes-workload", {"certificate-expiry"}),
        ],
    )
    def test_runbook_is_not_selected_for_a_type_it_does_not_declare(
        self, provider, capability, resource_type, must_not_select
    ):
        runbook_id, _actions, _rto = _decision(provider)._select_runbook(
            _analyzer([capability], provider, resource_type=resource_type)
        )

        assert runbook_id not in must_not_select, (
            f"{provider} selected {runbook_id!r} for resource_type={resource_type!r}, "
            f"which it does not declare: {BUILTIN_RUNBOOKS[runbook_id]['resource_types']}"
        )

    @pytest.mark.parametrize("provider", PROVIDERS)
    @pytest.mark.parametrize("resource_type", ALL_RESOURCE_TYPES)
    def test_whatever_is_selected_declares_the_incident_resource_type(
        self, provider, resource_type
    ):
        """The sweep: every runbook, every resource type it does not declare.

        Asking one pair at a time is how the previous version of this file
        passed while the tier was dead — so drive every capability the catalog
        knows against every type it knows, and assert the invariant on whatever
        comes back rather than on a runbook named in advance.
        """
        offenders = []
        for rb_id, rb in BUILTIN_RUNBOOKS.items():
            for capability in rb.get("capabilities", ()):
                selected, _actions, _rto = _decision(provider)._select_runbook(
                    _analyzer([capability], provider, resource_type=resource_type)
                )
                if selected == "generic-recovery":
                    continue  # tier 3 is the unconditional fallback
                declared = BUILTIN_RUNBOOKS[selected].get("resource_types") or []
                if declared and resource_type not in declared:
                    offenders.append((capability, selected, declared))

        assert not offenders, (
            f"{provider}: resource_type={resource_type!r} selected runbooks that do "
            f"not declare it: {offenders}"
        )

    @pytest.mark.parametrize("provider", PROVIDERS)
    def test_a_declared_type_still_selects_its_runbook(self, provider):
        """Load-bearing in the other direction.

        A filter that excluded everything would satisfy the tests above and
        leave every incident on `generic-recovery` — which is the exact state
        tier 2 was already in before it was repaired.
        """
        runbook_id, _actions, rto = _decision(provider)._select_runbook(
            _analyzer(["restart_workload"], provider, resource_type="kubernetes-workload")
        )

        assert runbook_id == "eks-pod-oom"
        assert rto == BUILTIN_RUNBOOKS["eks-pod-oom"]["rto_sec"]

    @pytest.mark.parametrize("provider", PROVIDERS)
    def test_an_uninferred_resource_type_excludes_nothing(self, provider):
        """AWS's rule is "unknown on either side means do not exclude".

        An incident whose resource type could not be inferred must not lose
        every candidate — otherwise adding this filter silently downgrades the
        detectors that do not set the field.
        """
        runbook_id, _actions, _rto = _decision(provider)._select_runbook(
            _analyzer(["restart_workload"], provider, resource_type="")
        )

        assert runbook_id == "eks-pod-oom"

    @pytest.mark.parametrize("provider", PROVIDERS)
    def test_the_fallback_is_never_gated_by_resource_type(self, provider):
        """AWS states this outright (`test_generic_recovery_is_never_gated`).

        `generic-recovery` declares `cloud-resource` and is the answer when
        nothing else fits, so filtering it by resource type would leave those
        incidents with no runbook at all. Here it holds because tier 3 returns it
        unconditionally rather than because tier 2 exempts it — which is exactly
        why it is worth asserting: the reason is structural and invisible, and a
        later tidy-up that pushed the filter down into tier 3 would break it
        without touching anything this file otherwise reads.
        """
        runbook_id, _actions, _rto = _decision(provider)._select_runbook(
            _analyzer(["open_change_request"], provider, resource_type="streaming-consumer")
        )

        assert runbook_id == "generic-recovery"
