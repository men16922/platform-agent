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

import pytest

from src.agents.platform.addon_status import HealthState, SyncState
from src.agents.platform.collector import (
    PUSH_KEYS_ENV,
    StatusReport,
    StatusStore,
    UnauthenticatedReport,
    build_report,
    collect,
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
