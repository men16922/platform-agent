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

import re
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
from src.agents.platform.registry import Environment
from src.agents.platform.adapters.argocd import RESOURCES_FINALIZER, ArgoCDDeliveryAdapter
from src.agents.platform.adapters.flux import FluxDeliveryAdapter
from src.agents.platform.delivery import (
    ClusterSingletonCapability,
    DeliveryAdapter,
    desired_addons,
    reject_cluster_singletons,
)

REPO = Path(__file__).resolve().parents[1]
REGISTRY_ROOT = REPO / "platform"


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


class TestValuesSeam:
    """Most of the charts this platform declares cannot template without values.

    Found live and expensively: an Application rendered with chart+version alone
    reported `Unknown / Healthy` while installing nothing, and the real reason was
    buried in a status condition — `Please define loki.storage.bucketNames.chunks`.
    An add-on that cannot template is an add-on that can never sync, and the top
    line of the UI said Healthy the whole time.
    """

    def test_every_declared_values_file_resolves(self, registry):
        """A moved or misnamed path surfaces here, not as an ArgoCD ComparisonError."""
        assert registry.capabilities_missing_values() == []

    def test_values_come_from_the_file_not_a_copy(self, registry):
        """One source for "how is loki configured".

        Copying the values into the catalog would give Terraform and the delivery
        adapters separate copies of the same configuration, free to drift with
        nothing failing — which is precisely how the retired netpol chart ended up
        describing namespaces that never existed.
        """
        declared = registry.catalog["capabilities"]["logging"]["self_hosted_values"]
        on_disk = yaml.safe_load((REPO / declared).read_text(encoding="utf-8"))
        assert registry.values_for("logging") == on_disk

    def test_loki_values_carry_what_the_chart_demands(self, registry):
        """The specific thing whose absence broke the live render."""
        values = registry.values_for("logging")
        assert values["deploymentMode"] == "SingleBinary"
        assert values["loki"]["storage"]["type"] == "filesystem"

    def test_missing_file_degrades_to_empty_not_an_exception(self, registry, tmp_path):
        """The loader is fail-closed for structure; values are a rendering input.

        Refusing to load the whole platform because one add-on's values file moved
        would be a bigger outage than the one it prevents — and the gap is loud
        anyway, since the chart refuses to template.
        """
        assert registry.values_for("logging", repo_root=tmp_path) == {}

    def test_capability_with_no_declared_values_is_not_a_problem(self, registry):
        assert registry.values_for("not-a-capability") == {}

    def test_values_carry_pss_seccomp_for_namespace_scoped_addons(self, registry):
        """Tenant namespaces enforce PSS `restricted`; the charts do not comply alone.

        Measured, not predicted: with the charts' own defaults, the tenant's loki
        installed as ArgoCD **Synced / Progressing with zero pods** — admission was
        refusing every pod for a missing seccompProfile, and that error lives in
        StatefulSet events, three levels under a green badge. `enforce: restricted`
        arrived with Phase 2 tenancy, so values proven in the unlabelled
        `monitoring` namespace stopped working the moment they targeted a tenant.
        """
        for capability in ("logging", "tracing"):
            values = registry.values_for(capability)
            rendered = yaml.safe_dump(values)
            assert "seccompProfile" in rendered, (
                f"{capability} values must set seccompProfile: its namespace enforces "
                "PSS restricted, and the chart default does not"
            )

    def test_stateful_addon_does_not_auto_delete_its_volume(self, registry):
        """Unsubscribing must not silently destroy a tenant's data.

        The loki chart defaults `enableStatefulSetAutoDeletePVC: true`, which renders
        `whenDeleted: Delete` and inverts Kubernetes' Retain default. Live, deleting
        the Application took the PVC and the logs with it. Unsubscribe is about to
        become a dashboard-driven registry edit (Phase 5); an edit that destroys data
        with no warning is a policy nobody chose, inherited from a chart.
        """
        persistence = registry.values_for("logging")["singleBinary"]["persistence"]
        assert persistence["enableStatefulSetAutoDeletePVC"] is False

    def test_argocd_renders_values_as_an_object_not_a_string(self, registry):
        """`valuesObject`, not `values`.

        Argo parses the string form as YAML text, so a dict serialised into it
        round-trips through indentation nobody controls — and no-churn adoption
        depends on the manifest being diffable.
        """
        addons = [
            a
            for a in desired_addons(
                registry.tenant("acme"), registry.environment("acme", "dev"),
                registry.wave_for, registry.scope_of, registry.values_for,
            )
            if a.capability == "logging"
        ]
        rendered = ArgoCDDeliveryAdapter(repo_url="https://example.invalid").render(
            registry.tenant("acme"), registry.environment("acme", "dev"), addons
        )
        helm = rendered[0]["spec"]["source"]["helm"]
        assert isinstance(helm["valuesObject"], dict)
        assert helm["valuesObject"]["deploymentMode"] == "SingleBinary"

    def test_both_engines_install_the_same_configuration(self, registry):
        """Otherwise "the same add-on" means two different things per engine."""
        addons = [
            a
            for a in desired_addons(
                registry.tenant("acme"), registry.environment("acme", "dev"),
                registry.wave_for, registry.scope_of, registry.values_for,
            )
            if a.capability == "logging"
        ]
        tenant, env = registry.tenant("acme"), registry.environment("acme", "dev")
        argo = ArgoCDDeliveryAdapter(repo_url="https://example.invalid").render(tenant, env, addons)
        flux = FluxDeliveryAdapter().render(tenant, env, addons)
        assert argo[0]["spec"]["source"]["helm"]["valuesObject"] == flux[0]["spec"]["values"]

    def test_no_values_renders_no_empty_helm_block(self, registry):
        """An empty `helm: {}` is churn on every diff for no behaviour."""
        from src.agents.platform.delivery import DesiredAddon

        addon = DesiredAddon(
            tenant="acme", env="dev", capability="logging", backend="loki",
            version="7.1.0", wave=1, namespace="acme-dev-logging", scope="namespace",
        )
        rendered = ArgoCDDeliveryAdapter(repo_url="https://example.invalid").render(
            registry.tenant("acme"), registry.environment("acme", "dev"), [addon]
        )
        assert "helm" not in rendered[0]["spec"]["source"]


class TestChartRepoSeam:
    """A chart name with no repository is not an installable add-on.

    Until this axis existed the URL lived only in `infra/onprem/addons/*.tf`, so the
    registry described add-ons it could not produce a manifest for: every live
    install was hand-assembled with the repo pasted in at the prompt, and the
    reproducible path stopped at "render something ArgoCD reports as
    ComparisonError". Same family as the values gap — declared, unusable, green.
    """

    def test_every_self_hosted_backend_has_somewhere_to_fetch_from(self, registry):
        assert registry.capabilities_missing_repo() == []

    def test_catalog_repos_match_terraform(self, registry):
        """The check that makes this field's duplication safe.

        Values are pointed at rather than copied precisely so two answers cannot
        drift apart; a URL is a scalar with no file to point at, so the copy is
        allowed and then verified. Terraform installs the cluster-wide copy of these
        same charts, and if the two sources ever named different repositories, the
        tenant-scoped add-on would silently come from somewhere else than the
        platform's own.
        """
        declared: dict[str, str] = {}
        for tf in sorted((REPO / "infra/onprem/addons").glob("*.tf")):
            for chart, repo in _helm_release_pairs(tf.read_text(encoding="utf-8")):
                declared[chart] = repo

        assert declared, "no helm_release blocks parsed — the guard would pass vacuously"

        for capability, entry in registry.catalog["capabilities"].items():
            chart = (entry.get("backends") or {}).get("self_hosted")
            if chart not in declared:
                # Not every catalogued chart is installed by this Terraform root
                # (argo-cd is bootstrapped, capsule is opt-in): nothing to compare.
                continue
            assert registry.repo_for(capability) == declared[chart], (
                f"{capability}: catalog says {registry.repo_for(capability)}, "
                f"Terraform installs {chart} from {declared[chart]}"
            )

    def test_rendered_application_points_at_the_registry_repo(self, registry):
        """The whole point: manifest built from the registry alone is installable."""
        tenant, env = registry.tenant("acme"), registry.environment("acme", "dev")
        addons = [
            a
            for a in desired_addons(
                tenant, env, registry.wave_for, registry.scope_of, registry.values_for
            )
            if a.capability == "logging"
        ]
        rendered = ArgoCDDeliveryAdapter(repo_url=registry.repo_for("logging")).render(
            tenant, env, addons
        )
        source = rendered[0]["spec"]["source"]
        assert source["repoURL"] == "https://grafana.github.io/helm-charts"
        assert source["chart"] == "loki"


def _helm_release_pairs(body: str) -> list[tuple[str, str]]:
    """(chart, repository) for each `helm_release` block in a Terraform file.

    Parsed per block rather than per file: `tracing.tf` declares more than one
    release, and pairing a file's first chart with its first repository would
    quietly compare the wrong two strings.
    """
    pairs: list[tuple[str, str]] = []
    for block in re.split(r'resource\s+"helm_release"', body)[1:]:
        chart = re.search(r'\n\s*chart\s*=\s*"([^"]+)"', block)
        repo = re.search(r'\n\s*repository\s*=\s*"([^"]+)"', block)
        if chart and repo:
            pairs.append((chart.group(1), repo.group(1)))
    return pairs


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


class TestManagedBackendRendersNothing:
    """The three paths disagreed about managed backends; only delivery was wrong.

    The collector recognises them (`from_managed`, applicable=False) and
    `registry_write` cannot produce one — it resolves `backend_for(...)` without
    `managed=True`. Delivery passed the backend straight through as a Helm chart
    name (`adapters/argocd.py`: `"chart": addon.backend`), so a managed declaration
    would have GitOps chase a chart the self-hosted repo does not publish.

    **The env here is built, not taken from the registry, and that is the point.**
    Managed backends are substrate-keyed to clouds (`_cloud_of`: eks/gke/aks), and
    today every env is `kind` or `k3s` — so `backend_for(..., managed=True)` is
    `None` everywhere and this path is unreachable from the shipped registry. A
    cloud substrate is exactly what Phase 4 creates; building one here is what lets
    the guard exist before the billable resource does.
    """

    CLOUD_SUBSTRATE = "eks"
    #: Namespace-scoped AND managed — the combination nothing else catches.
    #: `observability` is also managed but cluster-scoped, so the singleton guard
    #: fires first (see `test_a_cluster_scoped_managed_backend_...` below).
    CAPABILITY = "logging"

    def _managed_env(self, registry, capability=CAPABILITY):
        managed = registry.backend_for(capability, self.CLOUD_SUBSTRATE, managed=True)
        assert managed, "the catalog declares no managed backend for this cloud"
        env = Environment(
            name="prod",
            cluster="managed-spoke",
            substrate=self.CLOUD_SUBSTRATE,
            delivery="argocd",
            addons={capability: f"{managed} 1.0.0"},
        )
        return registry.tenant("acme"), env, managed

    def test_todays_registry_cannot_reach_this_path(self, registry):
        """Why the guard needs a built env — and what changes when Phase 4 lands."""
        for tenant in registry.tenants.values():
            for env in tenant.environments.values():
                for capability in registry.catalog["capabilities"]:
                    assert registry.backend_for(capability, env.substrate, managed=True) is None

    def test_the_catalog_really_declares_a_managed_backend(self, registry):
        """If this fails the rest of the class is vacuous, not passing."""
        assert registry.backend_for(self.CAPABILITY, self.CLOUD_SUBSTRATE, managed=True)

    def test_the_capability_under_test_is_namespace_scoped(self, registry):
        """Otherwise the singleton guard fires first and this class proves nothing.

        Pinned rather than assumed: if the catalog ever makes `logging`
        cluster-scoped, this fails instead of the class quietly measuring the
        wrong guard.
        """
        assert registry.scope_of(self.CAPABILITY) == "namespace"

    def test_a_cluster_scoped_managed_backend_is_caught_but_misadvised(self, registry):
        """`observability` is managed AND cluster-scoped, so the older guard wins.

        It refuses — but its advice ("install once per cluster; give the tenant an
        instance, a Prometheus CR") is wrong for a managed backend, where there is
        nothing to install at all. Recorded, not fixed: reordering the two guards
        changes an existing error's identity and belongs with the Phase 4 decision
        about what managed *should* render.
        """
        managed = registry.backend_for("observability", self.CLOUD_SUBSTRATE, managed=True)
        assert managed and registry.scope_of("observability") == "cluster"
        env = Environment(
            name="prod", cluster="managed-spoke", substrate=self.CLOUD_SUBSTRATE,
            delivery="argocd", addons={"observability": f"{managed} 1.0.0"},
        )
        tenant = registry.tenant("acme")
        addons = desired_addons(tenant, env, registry.wave_for, registry.scope_of)
        with pytest.raises(ClusterSingletonCapability):
            ArgoCDDeliveryAdapter(repo_url="https://example.invalid").render(tenant, env, addons)

    def test_a_managed_backend_expands_into_a_record_marked_managed(self, registry):
        """The Phase 4a decision, replacing the refusal that stood in for it.

        This used to raise `ManagedBackendNotRenderable`. The reason was sound —
        passing the backend through as a chart name makes the engine chase a chart
        the self-hosted repo does not publish — but it also left a tenant unable to
        declare a managed backend at all, which is DoD ①②. What was deferred is now
        decided: expansion marks it, the adapters render nothing, and the read model
        explains the absence (`from_managed`, `applicable=False`).
        """
        tenant, env, managed = self._managed_env(registry)
        addons = desired_addons(
            tenant, env, registry.wave_for, registry.scope_of,
            is_managed=registry.is_managed_backend,
        )
        by_capability = {a.capability: a for a in addons}
        assert by_capability[self.CAPABILITY].managed is True, (
            f"{managed} expanded without `managed=True`, so the adapters cannot tell "
            "it apart from a chart they must install"
        )
        assert by_capability[self.CAPABILITY].backend == managed

    def test_the_declaration_is_not_dropped_from_the_expansion(self, registry):
        """Dropping it in expansion would be the failure the old error prevented.

        A silent drop makes a declared add-on vanish with no signal, which is
        indistinguishable from delivery lag. It has to be *present* and *marked*.
        """
        tenant, env, _ = self._managed_env(registry)
        addons = desired_addons(
            tenant, env, registry.wave_for, registry.scope_of,
            is_managed=registry.is_managed_backend,
        )
        assert self.CAPABILITY in {a.capability for a in addons}, (
            "the managed capability disappeared during expansion"
        )

    def test_a_cluster_scoped_managed_backend_is_not_a_singleton_problem(self, registry):
        """The case where both rules could fire — and now neither should.

        `observability` is cluster-scoped *and* managed, so a declaration of it used
        to trip a guard either way. The singleton rule exists to stop two controllers
        reconciling the same objects; nothing is installed for a managed backend, so
        there is no second controller. That also retires the advice the Phase 4 plan's
        correction box flagged as wrong: *"give the tenant an instance (a Prometheus
        CR…)"* — for AMP that sends the reader to build something that cannot exist.
        """
        assert registry.scope_of("observability") == "cluster", "premise of this test"
        tenant, env, managed = self._managed_env(registry, capability="observability")
        addons = desired_addons(
            tenant, env, registry.wave_for, registry.scope_of,
            is_managed=registry.is_managed_backend,
        )
        observability = next(a for a in addons if a.capability == "observability")
        assert observability.managed is True
        assert observability.is_cluster_singleton is False, (
            f"{managed} is cluster-scoped and managed; treating it as a singleton "
            "raises an error whose advice cannot be followed"
        )
        manifests = ArgoCDDeliveryAdapter(repo_url="https://example.invalid").render(
            tenant, env, addons
        )
        # This env declares the managed capability and nothing else, so an empty
        # render is the honest answer — not a swallowed error. The next test proves
        # the same env still shows up in the read model, which is what keeps the
        # emptiness distinguishable from delivery lag.
        assert manifests == [], (
            f"a managed backend must render no manifest — got {manifests}"
        )

    def test_self_hosted_backends_still_render(self, registry):
        """The refusal must be about managed, not about this capability."""
        tenant = registry.tenant("acme")
        env = registry.environment("acme", "dev")
        addons = desired_addons(
            tenant, env, registry.wave_for, registry.scope_of,
            is_managed=registry.is_managed_backend,
        )
        assert addons, "the self-hosted fanout still renders"
        assert all(not registry.is_managed_backend(a.capability, a.backend) for a in addons)

    def test_omitting_the_callable_keeps_todays_behaviour(self, registry):
        """No existing caller is forced to pass it.

        Without this the guard would be a silent behaviour change for every current
        caller of `desired_addons` rather than an added refusal.
        """
        tenant, env, _ = self._managed_env(registry)
        addons = desired_addons(tenant, env, registry.wave_for, registry.scope_of)
        assert any(a.capability == self.CAPABILITY for a in addons)

    def test_the_read_path_and_the_render_path_take_one_answer(self):
        """Both accept the same callable, so "is this managed?" cannot fork.

        A second predicate here is how the two paths would drift apart with nothing
        failing — the shape this repo removed from the dashboard (431aeab).
        """
        import inspect

        from src.agents.platform import collector as collector_mod

        assert "is_managed" in inspect.signature(desired_addons).parameters
        assert "is_managed" in inspect.signature(collector_mod.collect).parameters
