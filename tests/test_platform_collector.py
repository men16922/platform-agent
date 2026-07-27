"""
Guards for push-based two-axis status collection.

Three properties carry the design, and all three are the kind that a happy-path
test suite passes while the system is broken:

1. **The hub never gains reach.** It authenticates pushes and stores them; it has
   no code path that reads a spoke. A test can only pin the negative space —
   identity comes from the verifying key, and a signer cannot write another
   tenant's rows.
2. **Absence is reported, not omitted.** A missing add-on and a dead agent are the
   two facts a drift dashboard exists to surface, and both look exactly like "no
   data" unless something insists otherwise.
3. **Stale is UNKNOWN.** The default reading of silence is "unchanged", which is
   how a monitoring system ends up frozen-healthy through an outage.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
import yaml

from src.agents.platform.addon_status import HealthState, SyncState
from src.agents.platform.collector import (
    PUSH_KEYS_ENV,
    StatusReport,
    StatusStore,
    TenancyPosture,
    UnauthenticatedReport,
    build_report,
    collect,
    collect_tenancy,
    load_push_keys,
    read_applications,
    sign,
    verify,
)
from src.agents.platform.registry import load_registry

NOW = 1_800_000_000.0


@pytest.fixture
def registry():
    return load_registry()


@pytest.fixture
def acme(registry):
    return registry.tenant("acme")


def _application(capability: str, sync: str, health: str, revision: str = "87.17.0") -> dict:
    return {
        "metadata": {
            "name": f"acme-dev-{capability}",
            "labels": {"platform-agent.io/capability": capability},
        },
        "spec": {"source": {"targetRevision": revision}},
        "status": {"sync": {"status": sync}, "health": {"status": health}},
    }


class TestCollect:
    def test_maps_both_axes_independently(self, acme):
        rows = collect(acme, "dev", [_application("observability", "OutOfSync", "Healthy")])
        row = next(r for r in rows if r.capability == "observability")
        # The pair that a single enum cannot express: drifted from git, yet healthy.
        assert row.sync_state is SyncState.DRIFTED
        assert row.health_state is HealthState.HEALTHY
        assert row.is_drifted is True

    def test_declared_but_absent_addon_is_reported_missing(self, acme):
        """The most important row is the one with nothing behind it.

        Iterating the cluster's objects instead of the registry's declarations would
        simply not emit this row, and a shorter list reads as "nothing wrong".
        """
        rows = collect(acme, "dev", [_application("observability", "Synced", "Healthy")])
        by_capability = {r.capability: r for r in rows}
        assert set(by_capability) == {"observability", "logging", "tracing", "progressive"}
        assert by_capability["logging"].health_state is HealthState.MISSING
        assert by_capability["logging"].sync_state is SyncState.DRIFTED

    def test_could_not_look_is_unknown_not_missing(self, acme):
        """'We could not read the cluster' and 'the add-on is gone' are different
        facts with different responses — collapsing them invents an outage or hides
        one, depending on which way you collapse."""
        rows = collect(acme, "dev", [], observed=False)
        assert {r.health_state for r in rows} == {HealthState.UNKNOWN}
        assert {r.sync_state for r in rows} == {SyncState.UNKNOWN}

    def test_declared_version_travels_with_the_row(self, acme):
        rows = collect(acme, "dev", [_application("observability", "Synced", "Healthy")])
        row = next(r for r in rows if r.capability == "observability")
        assert row.desired_version == "87.17.0"
        assert row.backend == "kube-prometheus-stack"

    def test_unknown_env_collects_nothing(self, acme):
        assert collect(acme, "nope", []) == []


class TestClusterScopedCapabilities:
    """A shared operator is not the tenant's to sync, and must not be reported as
    the tenant's own missing add-on.

    Without this, one cluster-level install that is running perfectly produces a
    "MISSING, drifted" row in EVERY tenant's view — four tenants, four false alarms
    about the same healthy thing. The sync axis genuinely is meaningless per tenant
    here, which is the fact `applicable=False` already models for managed backends.
    """

    def test_shared_capability_is_not_the_tenants_drift(self, acme, registry):
        rows = collect(acme, "dev", [], scope_of=registry.scope_of)
        progressive = next(r for r in rows if r.capability == "progressive")
        assert progressive.applicable is False
        assert progressive.sync_state is SyncState.NOT_APPLICABLE
        assert progressive.is_drifted is False
        assert progressive.native["scope"] == "cluster"

    def test_unseen_shared_install_is_unknown_not_missing(self, acme, registry):
        """Terraform-owned installs are invisible to a GitOps reader.

        Reporting MISSING would invent an outage for something running fine; the
        honest statement is that this view cannot see it.
        """
        rows = collect(acme, "dev", [], scope_of=registry.scope_of)
        progressive = next(r for r in rows if r.capability == "progressive")
        assert progressive.health_state is HealthState.UNKNOWN
        assert progressive.native["shared"] is False

    def test_health_of_an_observed_shared_install_is_reported(self, acme, registry):
        """Shared does not mean unreportable — the tenant still depends on it."""
        shared = {
            "metadata": {"labels": {"platform-agent.io/capability": "progressive"}},
            "status": {"sync": {"status": "Synced"}, "health": {"status": "Degraded"}},
        }
        rows = collect(acme, "dev", [shared], scope_of=registry.scope_of)
        progressive = next(r for r in rows if r.capability == "progressive")
        assert progressive.health_state is HealthState.DEGRADED
        assert progressive.native["shared"] is True
        # Still not the tenant's sync axis, even when observed.
        assert progressive.applicable is False

    def test_namespace_scoped_capabilities_are_unaffected(self, acme, registry):
        rows = collect(acme, "dev", [], scope_of=registry.scope_of)
        logging_row = next(r for r in rows if r.capability == "logging")
        assert logging_row.applicable is True
        assert logging_row.health_state is HealthState.MISSING

    def test_a_tenants_own_application_still_wins(self, acme, registry):
        """A tenant-labelled Application for a namespace-scoped capability is the
        tenant's, and must not be confused with a shared one."""
        owned = {
            "metadata": {
                "labels": {
                    "platform-agent.io/capability": "logging",
                    "platform-agent.io/tenant": "acme",
                }
            },
            "status": {"sync": {"status": "Synced"}, "health": {"status": "Healthy"}},
        }
        rows = collect(acme, "dev", [owned], scope_of=registry.scope_of)
        logging_row = next(r for r in rows if r.capability == "logging")
        assert logging_row.health_state is HealthState.HEALTHY

    def test_another_tenants_application_is_not_adopted(self, acme, registry):
        """globex's logging Application must never satisfy acme's declaration."""
        foreign = {
            "metadata": {
                "labels": {
                    "platform-agent.io/capability": "logging",
                    "platform-agent.io/tenant": "globex",
                }
            },
            "status": {"sync": {"status": "Synced"}, "health": {"status": "Healthy"}},
        }
        rows = collect(acme, "dev", [foreign], scope_of=registry.scope_of)
        logging_row = next(r for r in rows if r.capability == "logging")
        assert logging_row.health_state is HealthState.MISSING


class TestFakedManagedDescriptor:
    """Prove the `applicable=false` path BEFORE any billable managed backend exists.

    A faked descriptor is the point, not a shortcut: the plan requires this path
    proven without spending money, and a fake exercises exactly the code a real AMP
    subscription would. What it must prove is that a managed backend does not get
    reported as the tenant's missing add-on — this collector reads Kubernetes
    objects, and a service running fine in a cloud console has no Kubernetes object
    at all. Falling through would produce MISSING for something healthy: the same
    false alarm the cluster-scoped case produced, arriving from a different
    direction.
    """

    @staticmethod
    def _managed_tenant(tmp_path, registry_root=None):
        """A tenant on EKS subscribing to the catalog's managed observability."""
        root = registry_root or (tmp_path / "platform")
        (root / "tenants").mkdir(parents=True, exist_ok=True)
        catalog = Path(__file__).resolve().parents[1] / "platform" / "catalog.yaml"
        (root / "catalog.yaml").write_text(catalog.read_text(encoding="utf-8"), encoding="utf-8")
        (root / "tenants" / "initech.yaml").write_text(
            yaml.safe_dump({
                "isolation": "soft",
                "naming_prefix": "initech",
                "quota": {"cpu": "8", "memory": "16Gi", "pods": 50},
                "environments": {
                    "prod": {
                        "cluster": "initech-prod",
                        "substrate": "eks",
                        "delivery": "argocd",
                        "addons": {
                            # Straight out of the catalog's managed map for AWS.
                            "observability": "amazon-managed-prometheus",
                            # Alongside a self-hosted one, so the two paths are
                            # distinguished within a single env rather than by
                            # comparing two fixtures.
                            "logging": "loki 7.1.0",
                        },
                    }
                },
            }),
            encoding="utf-8",
        )
        return load_registry(root)

    def test_managed_backend_is_recognised_from_the_catalog(self, registry):
        """Derived, not declared twice — two facts about one choice can disagree."""
        assert registry.is_managed_backend("observability", "amazon-managed-prometheus")
        assert registry.is_managed_backend("logging", "cloud-logging")
        assert not registry.is_managed_backend("observability", "kube-prometheus-stack")

    def test_managed_row_has_no_sync_axis(self, tmp_path):
        managed = self._managed_tenant(tmp_path)
        rows = collect(
            managed.tenant("initech"), "prod", [],
            scope_of=managed.scope_of, is_managed=managed.is_managed_backend,
        )
        row = next(r for r in rows if r.capability == "observability")
        assert row.applicable is False
        assert row.sync_state is SyncState.NOT_APPLICABLE
        assert row.is_drifted is False

    def test_managed_row_is_not_reported_missing(self, tmp_path):
        """The failure this exists to prevent: a healthy cloud service read as gone."""
        managed = self._managed_tenant(tmp_path)
        rows = collect(
            managed.tenant("initech"), "prod", [],
            scope_of=managed.scope_of, is_managed=managed.is_managed_backend,
        )
        row = next(r for r in rows if r.capability == "observability")
        assert row.health_state is not HealthState.MISSING

    def test_unobserved_managed_health_is_unknown_never_healthy(self, tmp_path):
        """Asserting health for a backend nobody queried is a fabrication.

        A green badge for an unqueried cloud service is worse than "unknown": it is
        an answer to a question that was never asked. Real health needs the cloud
        API, which is Phase 4 and billable.
        """
        managed = self._managed_tenant(tmp_path)
        rows = collect(
            managed.tenant("initech"), "prod", [],
            scope_of=managed.scope_of, is_managed=managed.is_managed_backend,
        )
        row = next(r for r in rows if r.capability == "observability")
        assert row.health_state is HealthState.UNKNOWN

    def test_self_hosted_sibling_in_the_same_env_still_reports_normally(self, tmp_path):
        """Managed-ness is per capability, not per env."""
        managed = self._managed_tenant(tmp_path)
        rows = collect(
            managed.tenant("initech"), "prod", [],
            scope_of=managed.scope_of, is_managed=managed.is_managed_backend,
        )
        row = next(r for r in rows if r.capability == "logging")
        assert row.applicable is True
        assert row.health_state is HealthState.MISSING

    def test_report_survives_the_wire_with_applicability_intact(self, tmp_path):
        """`applicable` decides whether a UI shows a sync badge at all.

        If it is dropped in serialisation the dashboard fabricates a sync column for
        a backend that has none — and the boundary is exactly where this codebase
        has been bitten before.
        """
        managed = self._managed_tenant(tmp_path)
        report = build_report(
            managed.tenant("initech"), "prod", [], now=NOW,
            scope_of=managed.scope_of, is_managed=managed.is_managed_backend,
        )
        restored = StatusReport.from_dict(json.loads(json.dumps(report.to_dict())))
        row = next(r for r in restored.statuses if r.capability == "observability")
        assert row.applicable is False
        assert row.sync_state is SyncState.NOT_APPLICABLE


class TestTenancyPosture:
    """The isolation axes a platform engineer checks before trusting a boundary.

    The rule these guards exist for: **a badge that cannot turn red is worthless.**
    Live-falsified by deleting one NetworkPolicy and watching the axis flip to
    False, then restoring it.
    """

    @staticmethod
    def _cluster(**overrides):
        """A fake kubectl returning one canned document per resource kind."""
        docs = {
            "tenant.capsule.clastix.io": {"status": {"size": 4}},
            "resourcequota": {"items": [
                {"metadata": {"namespace": "acme-dev-logging"},
                 "status": {"used": {"limits.cpu": "2", "pods": "3"}}},
                {"metadata": {"namespace": "acme-dev-tracing"},
                 "status": {"used": {"limits.cpu": "500m", "pods": "1"}}},
            ]},
            "networkpolicy": {"items": [
                {"metadata": {"namespace": ns, "name": "deny-cross-tenant"}}
                for ns in ("acme-dev-logging", "acme-dev-observability",
                           "acme-dev-tracing", "acme-dev-progressive")
            ]},
            "rolebinding": {"items": [
                {"metadata": {"namespace": ns, "name": "acme-agent"}}
                for ns in ("acme-dev-logging", "acme-dev-observability",
                           "acme-dev-tracing", "acme-dev-progressive")
            ]},
            "namespace": {"items": [
                {"metadata": {"name": ns, "labels": {
                    "pod-security.kubernetes.io/enforce": "restricted"}}}
                for ns in ("acme-dev-logging", "acme-dev-observability",
                           "acme-dev-tracing", "acme-dev-progressive")
            ]},
        }
        docs.update(overrides)

        def runner(*args):
            kind = args[1] if len(args) > 1 else ""
            doc = docs.get(kind)
            if doc is None:
                return type("P", (), {"returncode": 1, "stdout": ""})()
            return type("P", (), {"returncode": 0, "stdout": json.dumps(doc)})()

        return runner

    def test_all_axes_green_when_everything_is_in_place(self, acme):
        posture = collect_tenancy(acme, "dev", kubectl=self._cluster())
        assert posture.isolation == {
            "quota": True, "network": True, "rbac": True, "pod_security": True
        }
        assert posture.adopted_namespaces == 4
        assert posture.declared_namespaces == 4

    def test_partial_coverage_is_not_isolation(self, acme):
        """One uncovered namespace IS the exposure — so the axis is ALL, not ANY."""
        posture = collect_tenancy(acme, "dev", kubectl=self._cluster(
            networkpolicy={"items": [
                {"metadata": {"namespace": "acme-dev-logging", "name": "deny-cross-tenant"}}
            ]},
        ))
        assert posture.isolation["network"] is False

    def test_unreadable_axis_is_none_not_false(self, acme):
        """"We could not look" must not render as "not isolated".

        A screen that cries breach because the agent lost permission burns its own
        credibility; one that renders green in that case is worse.
        """
        posture = collect_tenancy(acme, "dev", kubectl=self._cluster(networkpolicy=None))
        assert posture.isolation["network"] is None
        assert posture.isolation["quota"] is True

    def test_adopted_short_of_declared_fails_the_quota_axis(self, acme):
        """The failure this platform hit twice: labelled but not owned.

        An Active tenant owning zero namespaces reads as bounded everywhere while
        bounding nothing, so the axis tracks ownership, not the object's existence.
        """
        posture = collect_tenancy(acme, "dev", kubectl=self._cluster(
            **{"tenant.capsule.clastix.io": {"status": {"size": 2}}}
        ))
        assert posture.adopted_namespaces == 2
        assert posture.isolation["quota"] is False

    def test_quota_used_is_summed_across_namespaces(self, acme):
        """A tenant bound is a tenant total; per-namespace numbers hide the sum."""
        posture = collect_tenancy(acme, "dev", kubectl=self._cluster())
        assert posture.quota_used["limits.cpu"] == "2500m"
        assert posture.quota_used["pods"] == "4"
        assert posture.quota_hard["limits.cpu"] == "16"

    def test_unsummable_units_are_left_alone(self, acme):
        """Memory units are not converted.

        A wrong unit conversion produces a number that looks as authoritative as a
        right one, and nobody re-checks a number on a dashboard.
        """
        posture = collect_tenancy(acme, "dev", kubectl=self._cluster(
            resourcequota={"items": [
                {"metadata": {"namespace": "acme-dev-logging"},
                 "status": {"used": {"limits.memory": "2Gi"}}},
            ]},
        ))
        assert posture.quota_used["limits.memory"] == "2Gi"

    def test_env_with_no_namespaces_has_no_posture(self, acme):
        assert collect_tenancy(acme, "nope", kubectl=self._cluster()) is None

    def test_tier_travels_with_the_posture(self, acme):
        """A green isolation row means different things per tier.

        On a shared control plane "isolated" is a much weaker claim than on a
        dedicated cluster, and nothing else on the screen distinguishes them.
        """
        posture = collect_tenancy(acme, "dev", kubectl=self._cluster())
        assert posture.tier == "soft"
        # Under soft, several tenants share a cluster, so a per-ENV credential
        # would reach co-tenant namespaces — the unit has to be the tenant.
        assert posture.credential_scope == "tenant"
        assert posture.namespaces == [
            "acme-dev-logging", "acme-dev-observability",
            "acme-dev-progressive", "acme-dev-tracing",
        ]

    def test_a_report_without_the_newer_fields_still_parses(self):
        """A hub serves reports from agents older than itself during any upgrade.

        Learned at runtime, not in review: the UI read `namespaces.length` on a
        payload pushed by a pre-upgrade agent and took the page down. Both ends
        have to tolerate the older shape, so the parser fills defaults rather than
        raising — and the TS side made the same fields optional.
        """
        old_payload = {
            "adopted_namespaces": 4,
            "declared_namespaces": 4,
            "quota_hard": {"limits.cpu": "16"},
            "quota_used": {},
            "isolation": {"quota": True},
        }
        restored = TenancyPosture.from_dict(old_payload)
        assert restored.tier == ""
        assert restored.namespaces == []
        assert restored.isolation["quota"] is True

    def test_posture_survives_the_wire(self, acme):
        """`isolation` decides badge colour; dropping it in transit paints grey."""
        posture = collect_tenancy(acme, "dev", kubectl=self._cluster())
        report = build_report(acme, "dev", [], now=NOW, tenancy=posture)
        restored = StatusReport.from_dict(json.loads(json.dumps(report.to_dict())))
        assert restored.tenancy.isolation == posture.isolation
        assert restored.tenancy.quota_used == posture.quota_used

    def test_store_serves_posture_per_identity(self, acme):
        posture = collect_tenancy(acme, "dev", kubectl=self._cluster())
        store = StatusStore()
        store.ingest(build_report(acme, "dev", [], now=NOW, tenancy=posture), received_at=NOW)
        assert store.tenancy()["acme/dev"]["isolation"]["network"] is True

    def test_stale_report_keeps_its_posture(self, acme):
        """A boundary does not stop existing because the agent went quiet.

        Blanking it would read as "the isolation went away"; staleness is already
        reported separately, which is the honest place for "how old is this".
        """
        posture = collect_tenancy(acme, "dev", kubectl=self._cluster())
        store = StatusStore(stale_after_sec=1)
        store.ingest(build_report(acme, "dev", [], now=NOW, tenancy=posture), received_at=NOW)
        assert store.is_stale("acme/dev", now=NOW + 3600) is True
        assert store.tenancy()["acme/dev"]["isolation"]["quota"] is True


class TestReadApplications:
    def test_unreadable_cluster_yields_no_observation(self):
        """Not an empty cluster — the caller must pass observed=False for that."""
        class _Failed:
            returncode = 1
            stdout = ""

        assert read_applications(kubectl=lambda *a: _Failed()) == []

    def test_parses_items(self):
        class _Ok:
            returncode = 0
            stdout = json.dumps({"items": [{"metadata": {"name": "a"}}]})

        assert read_applications(kubectl=lambda *a: _Ok()) == [{"metadata": {"name": "a"}}]


class TestSigning:
    def test_identity_comes_from_the_key_not_the_body(self, acme):
        """A report claiming to be acme/dev must be signed with acme/dev's key.

        The release gate learned this the expensive way (D24): a caller's claim
        about itself is not evidence.
        """
        report = build_report(acme, "dev", [], now=NOW)
        payload = report.to_dict()
        keys = {"acme/dev": "acme-key", "globex/dev": "globex-key"}

        assert verify(payload, sign(payload, "acme-key"), keys).identity == "acme/dev"
        with pytest.raises(UnauthenticatedReport):
            verify(payload, sign(payload, "globex-key"), keys)

    def test_unknown_identity_and_bad_signature_are_indistinguishable(self, acme):
        """Different errors would enumerate which tenants exist."""
        payload = build_report(acme, "dev", [], now=NOW).to_dict()
        keys = {"acme/dev": "acme-key"}
        unknown = dict(payload, tenant="ghost")

        with pytest.raises(UnauthenticatedReport) as bad_sig:
            verify(payload, "deadbeef", keys)
        with pytest.raises(UnauthenticatedReport) as no_tenant:
            verify(unknown, sign(unknown, "acme-key"), keys)
        assert str(bad_sig.value) == str(no_tenant.value)

    def test_missing_signature_is_rejected(self, acme):
        payload = build_report(acme, "dev", [], now=NOW).to_dict()
        with pytest.raises(UnauthenticatedReport):
            verify(payload, "", {"acme/dev": "acme-key"})

    def test_signer_cannot_write_another_tenants_rows(self, acme, registry):
        """Reporting is a write. Without this, acme's key edits globex's status.

        The blast-radius invariant is usually discussed on the remediation path;
        it applies to the read path the moment reads are pushed.
        """
        report = build_report(acme, "dev", [_application("observability", "Synced", "Healthy")],
                              now=NOW)
        payload = report.to_dict()
        payload["statuses"][0]["tenant"] = "globex"
        with pytest.raises(UnauthenticatedReport, match="globex"):
            verify(payload, sign(payload, "acme-key"), {"acme/dev": "acme-key"})

    def test_signature_survives_key_reordering(self, acme):
        """The hub verifies a re-serialised body, so signing must be order-stable."""
        payload = build_report(acme, "dev", [], now=NOW).to_dict()
        signature = sign(payload, "k")
        shuffled = json.loads(json.dumps(dict(reversed(list(payload.items())))))
        assert verify(shuffled, signature, {"acme/dev": "k"}).identity == "acme/dev"

    def test_keys_absent_means_nothing_is_accepted(self, acme):
        payload = build_report(acme, "dev", [], now=NOW).to_dict()
        with pytest.raises(UnauthenticatedReport):
            verify(payload, sign(payload, "k"), {})

    def test_load_push_keys_tolerates_garbage(self):
        assert load_push_keys({}) == {}
        assert load_push_keys({PUSH_KEYS_ENV: "not json"}) == {}
        assert load_push_keys({PUSH_KEYS_ENV: '["a"]'}) == {}
        assert load_push_keys({PUSH_KEYS_ENV: '{"acme/dev": "k"}'}) == {"acme/dev": "k"}


class TestStore:
    def _stored(self, acme, *, received_at: float, stale_after: float = 300.0) -> StatusStore:
        store = StatusStore(stale_after_sec=stale_after)
        store.ingest(
            build_report(acme, "dev", [_application("observability", "Synced", "Healthy")],
                         now=received_at),
            received_at=received_at,
        )
        return store

    def test_fresh_report_reads_through(self, acme):
        store = self._stored(acme, received_at=NOW)
        row = next(r for r in store.statuses(now=NOW + 10) if r.capability == "observability")
        assert row.health_state is HealthState.HEALTHY

    def test_stale_report_degrades_to_unknown_rather_than_freezing(self, acme):
        """A dead push agent must not leave a healthy dashboard behind it."""
        store = self._stored(acme, received_at=NOW)
        rows = store.statuses(now=NOW + 3600)
        assert {r.health_state for r in rows} == {HealthState.UNKNOWN}
        assert {r.sync_state for r in rows} == {SyncState.UNKNOWN}
        assert rows[0].native["stale_sec"] == 3600.0

    def test_stale_rows_are_degraded_not_dropped(self, acme):
        """Dropping them reads as decommissioned; the fact is 'we stopped hearing'."""
        store = self._stored(acme, received_at=NOW)
        assert len(store.statuses(now=NOW + 3600)) == len(store.statuses(now=NOW))

    def test_staleness_uses_receive_time_not_the_spokes_clock(self, acme):
        """A spoke with a skewed clock — or a replayed report — must not look fresh."""
        store = StatusStore(stale_after_sec=300.0)
        future = StatusReport(tenant="acme", env="dev", cluster="c",
                              collected_at=NOW + 10_000, statuses=[])
        store.ingest(future, received_at=NOW)
        assert store.is_stale("acme/dev", now=NOW + 3600) is True

    def test_never_pushed_identity_is_stale(self, acme):
        assert StatusStore().is_stale("acme/dev", now=NOW) is True

    def test_declared_but_never_seen_identities_are_listed(self, acme, registry):
        """A cluster nobody is watching looks identical to a healthy one at rest."""
        store = self._stored(acme, received_at=NOW)
        assert store.missing_identities(registry) == ["acme/prod", "globex/dev"]

    def test_freshness_exposes_the_heartbeat(self, acme):
        store = self._stored(acme, received_at=NOW)
        beat = store.freshness(now=NOW + 60)
        assert beat == [{"identity": "acme/dev", "cluster": "kind-platform-agent",
                         "age_sec": 60.0, "stale": False}]

    def test_latest_report_wins(self, acme):
        store = self._stored(acme, received_at=NOW)
        store.ingest(
            build_report(acme, "dev", [_application("observability", "OutOfSync", "Degraded")],
                         now=NOW + 60),
            received_at=NOW + 60,
        )
        row = next(r for r in store.statuses(now=NOW + 61) if r.capability == "observability")
        assert row.sync_state is SyncState.DRIFTED
        assert row.health_state is HealthState.DEGRADED


class TestRoundTrip:
    def test_report_survives_serialisation(self, acme):
        """The boundary that unit tests structurally miss (M10's lesson): objects
        built in memory never cross the wire, and the wire is what production uses."""
        original = build_report(
            acme, "dev", [_application("observability", "OutOfSync", "Degraded")], now=NOW
        )
        restored = StatusReport.from_dict(json.loads(json.dumps(original.to_dict())))
        assert restored.identity == original.identity
        assert restored.cluster == original.cluster
        assert [r.to_dict() for r in restored.statuses] == [
            r.to_dict() for r in original.statuses
        ]


class TestPusherCLI:
    """The spoke agent's documented invocations must actually parse.

    Not a hypothetical: the docstring advertised `--once`, only `--interval` was
    implemented, and the documented command died at argparse. It went unnoticed
    because `make dev-up` passes `--interval 60` — the one form nobody reads the
    docs for. The same shape as the rest of this codebase's expensive bugs:
    declared, never exercised, and green everywhere.
    """

    @staticmethod
    def _cli():
        import importlib.util

        path = Path(__file__).resolve().parents[1] / "scripts" / "push_addon_status.py"
        spec = importlib.util.spec_from_file_location("push_addon_status", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    @pytest.mark.parametrize(
        "argv", [["--once"], []], ids=["explicit-once", "default-is-once"]
    )
    def test_single_shot_forms_parse_and_exit(self, monkeypatch, argv):
        cli = self._cli()
        monkeypatch.setenv("PLATFORM_PUSH_KEY", "k")
        monkeypatch.setattr(
            sys, "argv", ["push_addon_status.py", "--tenant", "acme", "--env", "dev", *argv]
        )
        # Parsing is the assertion; the push itself needs a hub and a cluster.
        monkeypatch.setattr(cli, "push_once", lambda *a, **k: (0, "ok"))
        assert cli.main() == 0

    def test_interval_form_parses_and_loops(self, monkeypatch):
        """Asserted by interrupting the sleep — the loop is meant not to exit.

        Calling `main()` on this form without a stop is how the first version of
        this test hung the suite: it parsed fine and then slept for a minute at a
        time, forever.
        """
        cli = self._cli()
        monkeypatch.setenv("PLATFORM_PUSH_KEY", "k")
        monkeypatch.setattr(
            sys, "argv",
            ["push_addon_status.py", "--tenant", "acme", "--env", "dev", "--interval", "60"],
        )
        pushes: list[int] = []
        monkeypatch.setattr(cli, "push_once", lambda *a, **k: (pushes.append(1), (0, "ok"))[1])
        monkeypatch.setattr(cli.time, "sleep", lambda _s: (_ for _ in ()).throw(StopIteration))
        with pytest.raises(StopIteration):
            cli.main()
        assert pushes == [1], "the interval form must push before it first sleeps"

    def test_once_and_interval_are_mutually_exclusive(self, monkeypatch):
        """Both spellings mean the same run, so accepting both together would
        silently honour one and ignore the other."""
        cli = self._cli()
        monkeypatch.setenv("PLATFORM_PUSH_KEY", "k")
        monkeypatch.setattr(
            sys, "argv",
            ["push_addon_status.py", "--tenant", "acme", "--env", "dev",
             "--once", "--interval", "60"],
        )
        with pytest.raises(SystemExit):
            cli.main()

    def test_unsigned_report_is_refused_before_any_read(self, monkeypatch):
        """No key means no identity; a hub that accepted it would be an open
        write endpoint reachable by anything on the network."""
        cli = self._cli()
        monkeypatch.delenv("PLATFORM_PUSH_KEY", raising=False)
        monkeypatch.setattr(sys, "argv", ["push_addon_status.py", "--tenant", "acme", "--env", "dev"])
        assert cli.main() == 2
