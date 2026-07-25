"""
Guards for the delivery adapters (Phase 1b).

Two real engines exist so the contract gets pressure-tested — a single
implementation always fits its own abstraction. The tests below deliberately
target the three places ArgoCD and Flux disagree, because that is where a leaky
abstraction would surface:

  ordering primitive · status vocabulary · object shape

Plus the one thing neither engine can be trusted to remember: the ordering that
Terraform's `depends_on` provides today disappears at the Phase 1b handoff.
"""

from __future__ import annotations

import pytest
import yaml

from src.agents.platform.adapters import (
    ArgoCDDeliveryAdapter,
    FluxDeliveryAdapter,
    get_delivery_adapter,
)
from src.agents.platform.addon_status import HealthState, SyncState
from src.agents.platform.delivery import desired_addons
from src.agents.platform.registry import load_registry

CATALOG = {
    "capabilities": {
        "gitops": {"wave": 0, "backends": {"self_hosted": "argocd"}},
        "observability": {"wave": 1, "backends": {"self_hosted": "kube-prometheus-stack"}},
        "app": {"wave": 2, "backends": {"self_hosted": "platform-agent"}},
    }
}

TENANT = {
    "isolation": "soft",
    "naming_prefix": "acme",
    "quota": {"cpu": "4", "memory": "8Gi", "pods": 50},
    "environments": {
        "dev": {
            "cluster": "kind-platform-agent",
            "substrate": "kind",
            "delivery": "argocd",
            "addons": {
                "app": "platform-agent 0.1.0",
                "gitops": "argocd 10.1.4",
                "observability": "kube-prometheus-stack 87.17.0",
            },
        }
    },
}


@pytest.fixture
def registry(tmp_path):
    root = tmp_path / "platform"
    (root / "tenants").mkdir(parents=True)
    (root / "catalog.yaml").write_text(yaml.safe_dump(CATALOG), encoding="utf-8")
    (root / "tenants" / "acme.yaml").write_text(yaml.safe_dump(TENANT), encoding="utf-8")
    return load_registry(root)


@pytest.fixture
def addons(registry):
    return desired_addons(
        registry.tenant("acme"), registry.environment("acme", "dev"), registry.wave_for
    )


class TestRegistry:
    def test_both_engines_are_registered(self):
        assert get_delivery_adapter("argocd") is ArgoCDDeliveryAdapter
        assert get_delivery_adapter("flux") is FluxDeliveryAdapter

    def test_unknown_engine_raises_with_the_known_set(self):
        with pytest.raises(KeyError, match="argocd"):
            get_delivery_adapter("spinnaker")

    def test_both_satisfy_the_abstract_contract(self, registry, addons):
        """Instantiable => every abstract method is implemented."""
        for adapter in (ArgoCDDeliveryAdapter(), FluxDeliveryAdapter()):
            manifests = adapter.render(
                registry.tenant("acme"), registry.environment("acme", "dev"), addons
            )
            assert len(manifests) == len(addons)


class TestOrderingSurvivesTheHandoff:
    """
    TF `depends_on` holds install order today and vanishes when GitOps takes
    ownership. Each engine must render the neutral wave into its own primitive.
    """

    def test_argocd_uses_sync_wave_annotations(self, registry, addons):
        manifests = ArgoCDDeliveryAdapter().render(
            registry.tenant("acme"), registry.environment("acme", "dev"), addons
        )
        waves = {
            m["metadata"]["labels"]["platform-agent.io/capability"]:
                m["metadata"]["annotations"]["argocd.argoproj.io/sync-wave"]
            for m in manifests
        }
        assert waves == {"gitops": "0", "observability": "1", "app": "2"}

    def test_argocd_wave_is_a_string(self):
        """Kubernetes annotations are string-valued; an int serialises to a type error."""
        value = ArgoCDDeliveryAdapter().ordering_annotation(1)["argocd.argoproj.io/sync-wave"]
        assert isinstance(value, str)

    def test_flux_uses_dependson_references(self):
        """Flux orders by object reference, not by a number in an annotation."""
        assert FluxDeliveryAdapter().ordering_annotation(0) == {"dependsOn": []}
        depends = FluxDeliveryAdapter().ordering_annotation(2)["dependsOn"]
        assert depends[0]["name"] == "wave-1"

    def test_flux_renders_dependson_into_the_spec(self, registry, addons):
        manifests = FluxDeliveryAdapter().render(
            registry.tenant("acme"), registry.environment("acme", "dev"), addons
        )
        by_capability = {
            m["metadata"]["labels"]["platform-agent.io/capability"]: m for m in manifests
        }
        assert by_capability["gitops"]["spec"]["dependsOn"] == []
        assert by_capability["app"]["spec"]["dependsOn"][0]["name"] == "wave-1"

    def test_addons_arrive_wave_sorted_regardless_of_yaml_order(self, addons):
        """The YAML declares app first; ordering must not depend on mapping order."""
        assert [a.capability for a in addons] == ["gitops", "observability", "app"]


class TestRenderIsDeterministic:
    """Phase 1b's no-churn adoption DoD depends on this: a wobbling renderer
    triggers delete-and-recreate, which destroys PVCs."""

    @pytest.mark.parametrize("adapter_cls", [ArgoCDDeliveryAdapter, FluxDeliveryAdapter])
    def test_same_input_same_output(self, registry, addons, adapter_cls):
        tenant, env = registry.tenant("acme"), registry.environment("acme", "dev")
        adapter = adapter_cls()
        assert adapter.render(tenant, env, addons) == adapter.render(tenant, env, addons)

    @pytest.mark.parametrize("adapter_cls", [ArgoCDDeliveryAdapter, FluxDeliveryAdapter])
    def test_namespaces_are_tenant_prefixed(self, registry, addons, adapter_cls):
        manifests = adapter_cls().render(
            registry.tenant("acme"), registry.environment("acme", "dev"), addons
        )
        for manifest in manifests:
            namespace = (
                manifest["spec"].get("targetNamespace")
                or manifest["spec"]["destination"]["namespace"]
            )
            assert namespace.startswith("acme-"), "two tenants must not collide on a shared cluster"

    @pytest.mark.parametrize("adapter_cls", [ArgoCDDeliveryAdapter, FluxDeliveryAdapter])
    def test_tenancy_is_queryable_from_labels(self, registry, addons, adapter_cls):
        """The dashboard must group by tenant without parsing object names."""
        manifests = adapter_cls().render(
            registry.tenant("acme"), registry.environment("acme", "dev"), addons
        )
        for manifest in manifests:
            labels = manifest["metadata"]["labels"]
            assert labels["platform-agent.io/tenant"] == "acme"
            assert labels["platform-agent.io/env"] == "dev"

    def test_pinned_version_wins_over_the_adapter_default(self, registry, addons):
        """For a Helm chart source targetRevision IS the chart version."""
        manifests = ArgoCDDeliveryAdapter(target_revision="main").render(
            registry.tenant("acme"), registry.environment("acme", "dev"), addons
        )
        by_capability = {
            m["metadata"]["labels"]["platform-agent.io/capability"]: m for m in manifests
        }
        assert by_capability["observability"]["spec"]["source"]["targetRevision"] == "87.17.0"

    def test_flux_release_name_is_stable_for_adoption(self, registry, addons):
        """Adoption must be a no-op; a changed releaseName is a delete-and-recreate."""
        manifests = FluxDeliveryAdapter().render(
            registry.tenant("acme"), registry.environment("acme", "dev"), addons
        )
        for manifest in manifests:
            assert manifest["spec"]["releaseName"] == manifest["metadata"]["name"]


class TestStatusVocabularyDiffers:
    def test_argocd_reports_both_axes_independently(self):
        status = ArgoCDDeliveryAdapter.normalise(
            "acme", "dev", "observability",
            {"status": {"sync": {"status": "OutOfSync"}, "health": {"status": "Healthy"}}},
        )
        assert status.sync_state is SyncState.DRIFTED
        assert status.health_state is HealthState.HEALTHY

    def test_argocd_synced_but_degraded_is_not_drift(self):
        status = ArgoCDDeliveryAdapter.normalise(
            "acme", "dev", "observability",
            {"status": {"sync": {"status": "Synced"}, "health": {"status": "Degraded"}}},
        )
        assert status.is_drifted is False

    def test_flux_not_ready_does_not_invent_drift(self):
        """Flux never reported a sync fact; claiming one would be fabrication."""
        status = FluxDeliveryAdapter.normalise(
            "acme", "dev", "observability",
            {"status": {"conditions": [{"type": "Ready", "status": "False", "reason": "InstallFailed"}]}},
        )
        assert status.health_state is HealthState.DEGRADED
        assert status.sync_state is SyncState.UNKNOWN

    def test_flux_ready_is_synced_and_healthy(self):
        status = FluxDeliveryAdapter.normalise(
            "acme", "dev", "observability",
            {"status": {"conditions": [{"type": "Ready", "status": "True"}]},
             "spec": {"chart": {"spec": {"version": "87.17.0"}}}},
        )
        assert status.sync_state is SyncState.SYNCED
        assert status.health_state is HealthState.HEALTHY
        assert status.desired_version == "87.17.0"

    def test_flux_suspended_is_progressing(self):
        status = FluxDeliveryAdapter.normalise(
            "acme", "dev", "observability", {"spec": {"suspend": True}, "status": {}}
        )
        assert status.health_state is HealthState.PROGRESSING

    def test_missing_status_is_unknown_not_healthy(self):
        """A backend that told us nothing must never read as working."""
        for status in (
            ArgoCDDeliveryAdapter.normalise("acme", "dev", "x", {}),
            FluxDeliveryAdapter.normalise("acme", "dev", "x", {}),
        ):
            assert status.health_state is HealthState.UNKNOWN

    def test_both_engines_produce_the_same_shape(self):
        """The whole point of normalisation: one read model, many backends."""
        argo = ArgoCDDeliveryAdapter.normalise(
            "acme", "dev", "observability",
            {"status": {"sync": {"status": "Synced"}, "health": {"status": "Healthy"}}},
        )
        flux = FluxDeliveryAdapter.normalise(
            "acme", "dev", "observability",
            {"status": {"conditions": [{"type": "Ready", "status": "True"}]}},
        )
        assert argo.to_dict().keys() == flux.to_dict().keys()
        assert argo.sync_state is flux.sync_state
        assert argo.health_state is flux.health_state
