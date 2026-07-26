"""
Guards for the platform layer (Phase 0 — model + contracts, no behaviour change).

Plan: docs/plans/2026-07-21-multi-tenant-env-addons.md (v5).
The three contracts under test:
  1. The registry loads, validates, and **fails closed** on bad content.
  2. Cardinality follows the isolation tier (soft => credential unit is TENANT).
  3. Add-on status has two orthogonal axes, and managed backends honestly report
     the sync axis as not-applicable instead of faking "synced".
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from src.agents.platform import (
    HealthState,
    IsolationTier,
    NormalizedAddonStatus,
    SyncState,
    from_argocd,
    from_flux,
    from_managed,
    load_registry,
    validate_registry,
)
from src.agents.platform.adapters.argocd import RESOURCES_FINALIZER, ArgoCDDeliveryAdapter
from src.agents.platform.adapters.flux import FluxDeliveryAdapter
from src.agents.platform.delivery import (
    ClusterSingletonCapability,
    DeliveryAdapter,
    desired_addons,
    reject_cluster_singletons,
)

REGISTRY_ROOT = Path(__file__).resolve().parents[1] / "platform"


@pytest.fixture(scope="module")
def registry():
    return load_registry(REGISTRY_ROOT)


class TestRegistryLoads:
    def test_repo_registry_is_valid(self, registry):
        assert set(registry.tenants) == {"acme", "globex"}

    def test_catalog_declares_waves_for_every_capability(self, registry):
        for capability in registry.catalog["capabilities"]:
            assert isinstance(registry.wave_for(capability), int)

    def test_gitops_and_tenancy_reconcile_before_addons(self, registry):
        """Wave 0 = CRDs/namespaces. This replaces Terraform depends_on at handoff."""
        assert registry.wave_for("gitops") == 0
        assert registry.wave_for("tenancy") == 0
        assert registry.wave_for("observability") == 1

    def test_unknown_capability_defaults_to_the_workload_wave(self, registry):
        assert registry.wave_for("not-a-capability") == 2

    def test_per_env_versions_are_not_lockstep(self, registry):
        """dev bumps first, prod is promoted by PR — divergence is the feature."""
        dev = registry.environment("acme", "dev")
        prod = registry.environment("acme", "prod")
        assert dev.addon_version("tracing") is not None
        assert prod.addons.get("tracing") is None, "prod subscribes to a subset"

    def test_delivery_engine_is_overridable_per_env(self, registry):
        """A second real engine is what stops the adapter contract being argocd-shaped."""
        assert registry.environment("acme", "dev").delivery == "argocd"
        assert registry.environment("acme", "prod").delivery == "flux"

    def test_unknown_tenant_or_env_raises(self, registry):
        with pytest.raises(KeyError):
            registry.tenant("nope")
        with pytest.raises(KeyError):
            registry.environment("acme", "nope")

    def test_missing_catalog_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_registry(tmp_path)


class TestIsolationDrivesCardinality:
    def test_soft_tier_credential_unit_is_the_tenant(self, registry):
        """
        The plan's Critical#2: `1 env = 1 cluster` holds only for `dedicated`.
        Under soft, a per-env credential would reach co-tenant namespaces.
        """
        assert registry.tenant("acme").isolation is IsolationTier.SOFT
        assert registry.tenant("acme").credential_scope == "tenant"

    def test_dedicated_tier_credential_unit_is_the_env(self):
        assert IsolationTier.DEDICATED.credential_scope == "env"
        assert IsolationTier.VCLUSTER.credential_scope == "env"

    def test_two_tenants_really_share_one_cluster(self, registry):
        """Single-tenant fixtures cannot falsify cross-tenant isolation."""
        occupants = registry.environments_of_cluster("kind-platform-agent")
        assert {t for t, _ in occupants} == {"acme", "globex"}

    def test_naming_prefix_prevents_cross_tenant_collisions(self, registry):
        acme = registry.tenant("acme").namespace_for("dev", "observability")
        globex = registry.tenant("globex").namespace_for("dev", "observability")
        assert acme != globex
        assert acme.startswith("acme-") and globex.startswith("globex-")

    def test_quota_is_declared_for_soft_tenants(self, registry):
        """soft = shared cluster, so noisy-neighbour bounds are not optional."""
        quota = registry.tenant("acme").quota.to_dict()
        assert {"cpu", "memory", "pods"} <= set(quota)


class TestValidationFailsClosed:
    """A malformed registry must raise, never degrade into a partial view."""

    @staticmethod
    def _tenant(**overrides):
        base = {
            "isolation": "soft",
            "naming_prefix": "acme",
            "environments": {
                "dev": {"cluster": "c", "substrate": "kind", "delivery": "argocd", "addons": {}}
            },
        }
        base.update(overrides)
        return base

    CATALOG = {"capabilities": {"observability": {"wave": 1, "scope": "cluster"}}}

    def test_valid_minimal_registry(self):
        assert validate_registry(self.CATALOG, {"acme": self._tenant()}) == []

    def test_a_missing_scope_does_not_block_loading(self):
        """A registry written before this field existed must still load.

        The loader is fail-closed, so rejecting an absent scope would turn a
        documentation gap into "the platform view does not load at all" — a worse
        failure than the one being guarded against, and the guard is elsewhere:
        an absent scope reads as cluster, so adapters refuse to duplicate it.
        """
        catalog = {"capabilities": {"observability": {"wave": 1}}}
        assert validate_registry(catalog, {"acme": self._tenant()}) == []

    def test_unknown_scope_value_is_rejected(self):
        """Absent is a gap; wrong is a claim, and a wrong claim gets believed."""
        catalog = {"capabilities": {"observability": {"wave": 1, "scope": "per-tenant"}}}
        assert any("scope" in p for p in validate_registry(catalog, {"acme": self._tenant()}))

    def test_bad_isolation_tier_rejected(self):
        problems = validate_registry(self.CATALOG, {"acme": self._tenant(isolation="kinda")})
        assert any("isolation" in p for p in problems)

    def test_non_dns_safe_prefix_rejected(self):
        """The prefix becomes part of Kubernetes object names."""
        problems = validate_registry(self.CATALOG, {"acme": self._tenant(naming_prefix="Acme_Corp")})
        assert any("naming_prefix" in p for p in problems)

    def test_unknown_substrate_rejected(self):
        tenant = self._tenant()
        tenant["environments"]["dev"]["substrate"] = "openshift"
        problems = validate_registry(self.CATALOG, {"acme": tenant})
        assert any("substrate" in p for p in problems)

    def test_unknown_delivery_engine_rejected(self):
        tenant = self._tenant()
        tenant["environments"]["dev"]["delivery"] = "spinnaker"
        problems = validate_registry(self.CATALOG, {"acme": tenant})
        assert any("delivery" in p for p in problems)

    def test_addon_not_in_catalog_rejected(self):
        """An uncatalogued capability cannot be resolved to a backend."""
        tenant = self._tenant()
        tenant["environments"]["dev"]["addons"] = {"service-mesh": "istio 1.0.0"}
        problems = validate_registry(self.CATALOG, {"acme": tenant})
        assert any("service-mesh" in p for p in problems)

    def test_empty_environments_rejected(self):
        problems = validate_registry(self.CATALOG, {"acme": self._tenant(environments={})})
        assert any("environments" in p for p in problems)

    def test_loader_raises_on_invalid_content(self, tmp_path):
        (tmp_path / "tenants").mkdir()
        (tmp_path / "catalog.yaml").write_text(yaml.safe_dump(self.CATALOG), encoding="utf-8")
        (tmp_path / "tenants" / "bad.yaml").write_text(
            yaml.safe_dump(self._tenant(isolation="nope")), encoding="utf-8"
        )
        with pytest.raises(ValueError, match="invalid platform registry"):
            load_registry(tmp_path)


class TestBackendResolution:
    def test_self_hosted_backend(self, registry):
        assert registry.backend_for("observability", "kind") == "kube-prometheus-stack"

    def test_managed_backend_is_substrate_keyed(self, registry):
        assert registry.backend_for("observability", "gke", managed=True) == "google-managed-prometheus"
        assert registry.backend_for("observability", "eks", managed=True) == "amazon-managed-prometheus"

    def test_capability_without_managed_variant(self, registry):
        """Progressive delivery is cluster-side everywhere — no managed answer."""
        assert registry.backend_for("progressive", "gke", managed=True) is None


class TestDesiredAddons:
    def test_expanded_and_wave_sorted(self, registry):
        acme = registry.tenant("acme")
        addons = desired_addons(acme, registry.environment("acme", "dev"), registry.wave_for)
        assert [a.wave for a in addons] == sorted(a.wave for a in addons)
        assert all(a.tenant == "acme" and a.env == "dev" for a in addons)

    def test_backend_and_version_split_from_declaration(self, registry):
        addons = desired_addons(
            registry.tenant("acme"), registry.environment("acme", "dev"), registry.wave_for
        )
        tracing = [a for a in addons if a.capability == "tracing"][0]
        assert tracing.backend == "tempo"
        assert tracing.version == "1.24.4"
        assert tracing.namespace == "acme-dev-tracing"

    def test_ordering_is_stable_regardless_of_yaml_order(self, registry):
        env = registry.environment("acme", "dev")
        first = desired_addons(registry.tenant("acme"), env, registry.wave_for)
        reversed_env = type(env)(
            name=env.name,
            cluster=env.cluster,
            substrate=env.substrate,
            delivery=env.delivery,
            addons=dict(reversed(list(env.addons.items()))),
        )
        second = desired_addons(registry.tenant("acme"), reversed_env, registry.wave_for)
        assert [a.capability for a in first] == [a.capability for a in second]


class TestClusterSingletonScope:
    """A cluster-scoped capability must never be rendered per tenant.

    This axis exists because of a live run, not a design review: applying the
    adapter's own per-tenant `progressive` Application installed a SECOND
    cluster-scoped argo-rollouts controller (ClusterRoleBinding, no --namespaced),
    and both controllers then reconciled the same Rollout objects. Leader election
    is per-namespace, so both were leaders. Nothing errored — that is the whole
    problem. `kubectl get application` read Synced/Healthy throughout.
    """

    def test_catalog_marks_the_singletons(self, registry):
        assert registry.is_cluster_scoped("progressive") is True
        assert registry.is_cluster_scoped("observability") is True
        assert registry.is_cluster_scoped("gitops") is True
        assert registry.is_cluster_scoped("tenancy") is True
        # Loki/Tempo carry no CRDs and no cluster controller: a per-tenant install
        # is a normal deployment, not a competing operator.
        assert registry.is_cluster_scoped("logging") is False
        assert registry.is_cluster_scoped("tracing") is False

    def test_our_own_catalog_answers_the_question_for_every_capability(self, registry):
        """Strictness where it belongs: this repo's catalog, not everyone's.

        An undeclared capability still fails safe (it reads as cluster-scoped), but
        the symptom is an adapter refusing to render it, which looks like an adapter
        bug rather than an unanswered question.
        """
        assert registry.capabilities_missing_scope() == []

    def test_unknown_capability_defaults_to_cluster(self, registry):
        """Fails safe in the only direction that is recoverable.

        Guessing "namespace" for a singleton yields two controllers fighting with
        nothing in any log; guessing "cluster" for a namespace-scoped add-on yields
        a refusal someone fixes in the catalog in a minute.
        """
        assert registry.scope_of("nonexistent-capability") == "cluster"

    def test_scope_travels_on_the_desired_addon(self, registry):
        addons = desired_addons(
            registry.tenant("acme"),
            registry.environment("acme", "dev"),
            registry.wave_for,
            registry.scope_of,
        )
        by_capability = {a.capability: a for a in addons}
        assert by_capability["progressive"].is_cluster_singleton is True
        assert by_capability["tracing"].is_cluster_singleton is False

    @pytest.mark.parametrize(
        "adapter",
        [ArgoCDDeliveryAdapter(repo_url="https://example.invalid"), FluxDeliveryAdapter()],
        ids=["argocd", "flux"],
    )
    def test_both_engines_refuse_to_render_a_singleton(self, registry, adapter):
        """The guard lives on the contract, so a third engine inherits it."""
        addons = desired_addons(
            registry.tenant("acme"),
            registry.environment("acme", "dev"),
            registry.wave_for,
            registry.scope_of,
        )
        with pytest.raises(ClusterSingletonCapability, match="progressive"):
            adapter.render(registry.tenant("acme"), registry.environment("acme", "dev"), addons)

    def test_namespace_scoped_addons_still_render(self, registry):
        """The refusal must be about the singleton, not about tenancy in general."""
        addons = [
            a
            for a in desired_addons(
                registry.tenant("acme"),
                registry.environment("acme", "dev"),
                registry.wave_for,
                registry.scope_of,
            )
            if not a.is_cluster_singleton
        ]
        rendered = ArgoCDDeliveryAdapter(repo_url="https://example.invalid").render(
            registry.tenant("acme"), registry.environment("acme", "dev"), addons
        )
        assert {m["metadata"]["labels"]["platform-agent.io/capability"] for m in rendered} == {
            "logging",
            "tracing",
        }

    def test_the_error_names_what_to_do_instead(self):
        """An error that only says "no" gets worked around."""
        from src.agents.platform.delivery import DesiredAddon

        addon = DesiredAddon(
            tenant="acme", env="dev", capability="progressive", backend="argo-rollouts",
            version="2.41.1", wave=1, namespace="acme-dev-progressive", scope="cluster",
        )
        with pytest.raises(ClusterSingletonCapability) as exc:
            reject_cluster_singletons([addon])
        assert "once per cluster" in str(exc.value)


class TestDeletionCascades:
    """Removing a rendered object must remove what it installed.

    The engines disagree by default, which is exactly why the contract has to say
    it: Flux uninstalls its release on delete, ArgoCD orphans everything unless the
    Application carries the resources finalizer. Live confirmation of the Argo side
    — the Application was deleted and its two pods kept running, holding a
    ClusterRoleBinding, with nothing owning them.
    """

    @staticmethod
    def _addon():
        from src.agents.platform.delivery import DesiredAddon

        return DesiredAddon(
            tenant="acme", env="dev", capability="logging", backend="loki",
            version="7.1.0", wave=1, namespace="acme-dev-logging", scope="namespace",
        )

    def test_argocd_application_carries_the_resources_finalizer(self, registry):
        rendered = ArgoCDDeliveryAdapter(repo_url="https://example.invalid").render(
            registry.tenant("acme"), registry.environment("acme", "dev"), [self._addon()]
        )
        assert rendered[0]["metadata"]["finalizers"] == [RESOURCES_FINALIZER]

    def test_prune_does_not_substitute_for_the_finalizer(self, registry):
        """`prune: true` removes resources that fell out of a SYNC.

        A deleted Application never syncs again, so pruning has nothing to do with
        deletion — the two were conflated until a live delete left the workload up.
        """
        rendered = ArgoCDDeliveryAdapter(repo_url="https://example.invalid").render(
            registry.tenant("acme"), registry.environment("acme", "dev"), [self._addon()]
        )
        assert rendered[0]["spec"]["syncPolicy"]["automated"]["prune"] is True
        assert "finalizers" in rendered[0]["metadata"], "prune is not a deletion policy"

    def test_flux_does_not_disable_its_uninstall(self, registry):
        """Flux cascades by default; the guard is that we never turn that off.

        Asserting the absence of a setting is unusual, but the failure mode here is
        someone adding `uninstall.disableWait`-style config that quietly makes the
        two engines disagree again.
        """
        rendered = FluxDeliveryAdapter().render(
            registry.tenant("acme"), registry.environment("acme", "dev"), [self._addon()]
        )
        spec = rendered[0]["spec"]
        assert spec.get("suspend") is not True
        assert "uninstall" not in spec or spec["uninstall"].get("keepHistory") is not True

    def test_the_contract_states_the_semantic(self):
        """Otherwise a third engine inherits its own default, silently."""
        assert "cascade" in (DeliveryAdapter.render.__doc__ or "").lower()


class TestDeliveryContract:
    def test_adapter_cannot_be_instantiated_without_implementing_the_contract(self):
        with pytest.raises(TypeError):
            DeliveryAdapter()  # type: ignore[abstract]

    def test_contract_threads_tenant_and_env(self):
        """
        blast radius = 1 tenant/env has to be expressible in the signature —
        a method that cannot say "which tenant" cannot be audited for it.
        """
        import inspect

        for method in ("render", "observe"):
            params = inspect.signature(getattr(DeliveryAdapter, method)).parameters
            assert "tenant" in params and "env" in params, method


class TestTwoAxisStatus:
    def test_argocd_outofsync_but_healthy_is_drift(self):
        """The case a single enum destroys: healthy app, drifted cluster."""
        status = from_argocd(
            tenant="acme", env="dev", capability="observability",
            sync_status="OutOfSync", health_status="Healthy",
        )
        assert status.sync_state is SyncState.DRIFTED
        assert status.health_state is HealthState.HEALTHY
        assert status.is_drifted is True

    def test_argocd_synced_but_degraded_is_not_drift(self):
        status = from_argocd(
            tenant="acme", env="dev", capability="observability",
            sync_status="Synced", health_status="Degraded",
        )
        assert status.sync_state is SyncState.SYNCED
        assert status.health_state is HealthState.DEGRADED
        assert status.is_drifted is False, "an app problem must not read as drift"

    def test_argocd_unknown_values_do_not_become_healthy(self):
        status = from_argocd(
            tenant="acme", env="dev", capability="x",
            sync_status="Weird", health_status="Weird",
        )
        assert status.sync_state is SyncState.UNKNOWN
        assert status.health_state is HealthState.UNKNOWN

    def test_flux_not_ready_leaves_sync_unknown_not_drifted(self):
        """Flux collapses both axes into Ready; inventing `drifted` would be a lie."""
        status = from_flux(tenant="acme", env="prod", capability="observability", ready=False)
        assert status.health_state is HealthState.DEGRADED
        assert status.sync_state is SyncState.UNKNOWN

    def test_flux_ready_is_synced_and_healthy(self):
        status = from_flux(tenant="acme", env="prod", capability="observability", ready=True)
        assert status.sync_state is SyncState.SYNCED
        assert status.health_state is HealthState.HEALTHY

    def test_flux_suspended_is_progressing_not_healthy(self):
        status = from_flux(
            tenant="acme", env="prod", capability="observability", ready=None, suspended=True
        )
        assert status.health_state is HealthState.PROGRESSING

    def test_managed_backend_marks_sync_axis_not_applicable(self):
        """
        The `applicable=False` path, proven with a faked descriptor so it is
        falsified in a non-optional phase rather than waiting on a billable backend.
        """
        status = from_managed(
            tenant="acme", env="prod", capability="observability",
            backend="amazon-managed-prometheus",
        )
        assert status.applicable is False
        assert status.sync_state is SyncState.NOT_APPLICABLE
        assert status.health_state is HealthState.HEALTHY
        assert status.is_drifted is False

    def test_managed_unknown_health_stays_unknown(self):
        status = from_managed(
            tenant="acme", env="prod", capability="observability",
            backend="amp", healthy=None,
        )
        assert status.health_state is HealthState.UNKNOWN

    def test_serialisation_keeps_both_axes_and_applicability(self):
        status = NormalizedAddonStatus(
            tenant="acme", env="dev", capability="logging", backend="loki",
            sync_state=SyncState.DRIFTED, health_state=HealthState.HEALTHY,
            desired_version="7.1.0",
        )
        payload = status.to_dict()
        assert payload["sync_state"] == "drifted"
        assert payload["health_state"] == "healthy"
        assert payload["applicable"] is True
        assert payload["desired_version"] == "7.1.0"
