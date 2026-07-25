"""
Guards for soft-tier tenancy rendering (Phase 2, first slice).

Two failure modes drive most of these, and both produce objects that LOOK like
isolation:

* a quota that does not bound what it claims to bound, and
* namespace-scoped RBAC rendered for a tier whose boundary is not the namespace.

The third theme is the one this codebase keeps relearning: an artifact is only
real once something consumes it. The NetworkPolicy chart has been default-OFF
waiting for exactly these namespaces, so a test pins that the two agree instead
of drifting apart silently.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from src.agents.platform.registry import IsolationTier, load_registry
from src.agents.platform.tenancy import (
    CAPABILITY_LABEL,
    ENV_LABEL,
    TENANT_LABEL,
    UnsupportedTier,
    namespaces_for,
    render_capsule_tenant,
    render_namespaces,
    render_rbac,
    render_tenancy,
    unbounded_soft_tenants,
)

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture
def registry():
    return load_registry()


@pytest.fixture
def acme(registry):
    return registry.tenant("acme")


class TestNamespaces:
    def test_names_follow_the_registry_convention(self, acme):
        names = [ns for _cap, ns in namespaces_for(acme, "dev")]
        assert "acme-dev-observability" in names
        assert all(n.startswith("acme-dev-") for n in names)

    def test_only_subscribed_capabilities_get_a_namespace(self, acme):
        """prod subscribes to a subset — a partial add-on set is normal, not a gap."""
        dev = {cap for cap, _ in namespaces_for(acme, "dev")}
        prod = {cap for cap, _ in namespaces_for(acme, "prod")}
        assert prod < dev, "prod is deliberately a subset"
        assert prod == {"observability"}

    def test_labels_carry_tenant_env_and_capability(self, acme):
        ns = next(n for n in render_namespaces(acme, "dev")
                  if n["metadata"]["name"] == "acme-dev-observability")
        labels = ns["metadata"]["labels"]
        assert labels[TENANT_LABEL] == "acme"
        assert labels[ENV_LABEL] == "dev"
        assert labels[CAPABILITY_LABEL] == "observability"

    def test_namespaces_carry_pss_restricted(self, acme):
        """The chart-side securityContext was shipped with ⑥; this is its other half."""
        ns = render_namespaces(acme, "dev")[0]
        assert ns["metadata"]["labels"]["pod-security.kubernetes.io/enforce"] == "restricted"

    def test_unknown_env_renders_nothing_rather_than_guessing(self, acme):
        assert namespaces_for(acme, "staging") == []


class TestQuotaIsATenantBound:
    """A tenant declaring cpu:16 across four namespaces must not receive 64."""

    def test_quota_is_scoped_to_the_tenant_not_the_namespace(self, acme):
        capsule = render_capsule_tenant(acme, "dev", owner="platform-agent")
        assert capsule is not None
        assert capsule["spec"]["resourceQuotas"]["scope"] == "Tenant"

    def test_no_per_namespace_resourcequota_is_emitted(self, registry):
        """Emitting one per namespace is the silent 4x — it must not appear at all."""
        kinds = [o["kind"] for o in render_tenancy(registry, "acme", "dev")]
        assert "ResourceQuota" not in kinds

    def test_declared_bounds_reach_the_object(self, acme):
        hard = render_capsule_tenant(acme, "dev", owner="x")["spec"]["resourceQuotas"]["items"][0]["hard"]
        assert hard["limits.cpu"] == "16"
        assert hard["limits.memory"] == "64Gi"
        assert hard["pods"] == "200"

    def test_a_tenant_without_quota_gets_no_object_rather_than_an_empty_one(self, acme):
        import dataclasses

        from src.agents.platform.registry import Quota

        unbounded = dataclasses.replace(acme, quota=Quota())
        assert render_capsule_tenant(unbounded, "dev", owner="x") is None, (
            "an empty ResourceQuota reads as 'bounded' while bounding nothing"
        )

    def test_limitrange_default_exists_so_the_quota_means_something(self, acme):
        """Without a per-container default, one workload can eat the whole tenant quota."""
        limits = render_capsule_tenant(acme, "dev", owner="x")["spec"]["limitRanges"]["items"][0]["limits"][0]
        assert limits["default"]["cpu"] and limits["defaultRequest"]["cpu"]


class TestRbacStaysInsideTheTenant:
    def test_role_is_namespaced_never_cluster_scoped(self, registry):
        objects = render_rbac(registry.tenant("acme"), "dev", service_account="platform-agent")
        assert {o["kind"] for o in objects} == {"Role", "RoleBinding"}
        assert all(o["metadata"].get("namespace") for o in objects), (
            "a ClusterRole here re-grants the blast radius Phase 1a closed"
        )

    def test_no_wildcards_anywhere(self, registry):
        for obj in render_rbac(registry.tenant("acme"), "dev", service_account="pa"):
            for rule in obj.get("rules", []):
                assert "*" not in rule["apiGroups"]
                assert "*" not in rule["resources"]
                assert "*" not in rule["verbs"]

    def test_binding_targets_the_service_account_in_that_namespace(self, registry):
        binding = next(o for o in render_rbac(registry.tenant("acme"), "dev", service_account="pa")
                       if o["kind"] == "RoleBinding")
        subject = binding["subjects"][0]
        assert subject["name"] == "pa"
        assert subject["namespace"] == binding["metadata"]["namespace"]

    def test_scale_subresource_is_granted_because_scaling_is_a_remediation(self, registry):
        rules = next(o for o in render_rbac(registry.tenant("acme"), "dev", service_account="pa")
                     if o["kind"] == "Role")["rules"]
        scale = [r for r in rules if "deployments/scale" in r["resources"]]
        assert scale, "the executor's scale action would 403 without this"


class TestTierBoundary:
    @pytest.mark.parametrize("tier", [IsolationTier.VCLUSTER, IsolationTier.DEDICATED])
    def test_non_soft_tiers_refuse_to_render_namespace_tenancy(self, acme, tier):
        """Their boundary lives elsewhere; objects here would be read as the boundary."""
        import dataclasses

        tenant = dataclasses.replace(acme, isolation=tier)
        with pytest.raises(UnsupportedTier):
            render_namespaces(tenant, "dev")
        with pytest.raises(UnsupportedTier):
            render_rbac(tenant, "dev", service_account="pa")


class TestReporting:
    def test_unbounded_soft_tenants_are_reportable(self, registry):
        """On a shared cluster this is a co-tenant outage waiting for a bad deploy."""
        assert unbounded_soft_tenants(registry) == []


class TestNetworkPolicyChartAgrees:
    """The chart has been default-OFF waiting for these namespaces.

    If the two drift, the policies apply to namespaces that do not exist — which
    still reads as "isolated" in an audit. Pin them together.
    """

    @staticmethod
    def _chart_values() -> dict:
        path = REPO / "infra" / "onprem" / "addons" / "charts" / "tenancy-netpol" / "values.yaml"
        return yaml.safe_load(path.read_text(encoding="utf-8"))

    def test_chart_prefixes_match_the_registry(self, registry):
        chart = {t["prefix"] for t in self._chart_values()["tenants"]}
        assert chart == {t.naming_prefix for t in registry.tenants.values()}

    def test_chart_capabilities_cover_what_we_render(self, registry):
        chart = set(self._chart_values()["capabilities"])
        rendered = {
            cap
            for tenant in registry.tenants.values()
            for env in tenant.environments
            for cap, _ns in namespaces_for(tenant, env)
        }
        assert rendered <= chart, f"unpolicied namespaces would be created: {rendered - chart}"

    def test_chart_environments_cover_what_we_render(self, registry):
        chart = set(self._chart_values()["environments"])
        rendered = {env for t in registry.tenants.values() for env in t.environments}
        assert rendered <= chart
