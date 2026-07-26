"""
Guards for soft-tier tenancy rendering (Phase 2, first slice).

Two failure modes drive most of these, and both produce objects that LOOK like
isolation:

* a quota that does not bound what it claims to bound, and
* namespace-scoped RBAC rendered for a tier whose boundary is not the namespace.

The third theme is the one this codebase keeps relearning: an artifact is only real
once something consumes it. The NetworkPolicies here were previously a Helm chart
that no `helm_release` installed, describing 16 namespaces against a registry that
subscribes 6 — green tests, zero effect. They are now rendered from the same
registry call that renders the namespaces, so the two sets are equal by
construction rather than by a test that notices when they diverge.

The fourth is newer and cost a live run to find: rendering the right OBJECTS is not
the same as rendering them in an appliable ORDER.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from src.agents.platform.registry import IsolationTier, load_registry
from src.agents.platform.tenancy import (
    CAPABILITY_LABEL,
    ENV_LABEL,
    PROVEN_ENFORCING_SUBSTRATES,
    TENANT_LABEL,
    UnsupportedTier,
    namespaces_for,
    network_policies_apply_to,
    render_capsule_tenant,
    render_namespaces,
    render_network_policies,
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


class TestNetworkPolicies:
    """Data-plane isolation for the soft tier, rendered from the same registry call
    that renders the namespaces.

    The predecessor was a Helm chart with its own hand-kept lists of tenants x envs
    x capabilities. Those lists could only ever be *checked* against the registry
    after the fact, and they were already wrong: 16 policies against 6 real
    namespaces, ten of them naming namespaces that will never exist. Rendering both
    sets from ``namespaces_for`` removes the drift class instead of testing for it.
    """

    def test_one_policy_per_namespace_no_more_no_less(self, registry):
        tenant = registry.tenant("acme")
        namespaces = {ns for _cap, ns in namespaces_for(tenant, "dev")}
        policies = render_network_policies(tenant, "dev")
        assert {p["metadata"]["namespace"] for p in policies} == namespaces
        assert len(policies) == len(namespaces), "a namespace must not get two policies"

    def test_policy_is_default_deny_ingress_over_every_pod(self, registry):
        policy = render_network_policies(registry.tenant("acme"), "dev")[0]
        assert policy["spec"]["podSelector"] == {}, "must cover every pod in the namespace"
        assert policy["spec"]["policyTypes"] == ["Ingress"]

    def test_same_tenant_allowance_is_by_label_not_by_name(self, registry):
        """NetworkPolicy peers cannot match namespace names by prefix.

        The tenant label is what makes "same tenant" expressible at all — and it is
        set by Capsule, which also reconciles it back when someone edits it, so a
        co-tenant cannot relabel their way into this allowance (live-verified:
        `kubectl label` on a peer namespace was reverted).
        """
        policy = render_network_policies(registry.tenant("acme"), "dev")[0]
        peers = policy["spec"]["ingress"][0]["from"]
        assert {"namespaceSelector": {"matchLabels": {TENANT_LABEL: "acme"}}} in peers

    def test_egress_is_untouched_so_dns_keeps_working(self, registry):
        """A default-deny egress would break name resolution, and the symptom reads
        as an application bug rather than a policy effect."""
        policy = render_network_policies(registry.tenant("acme"), "dev")[0]
        assert "Egress" not in policy["spec"]["policyTypes"]

    def test_non_soft_tiers_render_nothing(self, registry):
        tenant = registry.tenant("acme")
        vcluster = replace(tenant, isolation=IsolationTier.VCLUSTER)
        with pytest.raises(UnsupportedTier):
            render_network_policies(vcluster, "dev")

    def test_unproven_substrate_gets_no_policy(self, registry):
        """acme/prod is k3s (flannel), where enforcement has not been probed.

        Rendering nothing is honestly insecure; rendering an unenforced policy is
        dishonestly secure, and only the second one survives an audit unnoticed.
        """
        tenant = registry.tenant("acme")
        assert network_policies_apply_to(tenant, "dev") is True
        assert network_policies_apply_to(tenant, "prod") is False
        kinds = [o["kind"] for o in render_tenancy(registry, "acme", "prod")]
        assert "NetworkPolicy" not in kinds
        assert "Namespace" in kinds, "an unproven substrate must still be provisionable"

    def test_proven_substrates_are_only_those_with_evidence(self):
        """Adding a substrate here is a security claim; it needs a probe run behind it."""
        assert PROVEN_ENFORCING_SUBSTRATES == frozenset({"kind"})

    def test_tenant_semantics_have_their_own_verifier(self):
        """The CNI probe and the tenancy probe answer different questions.

        `verify_netpol_enforcement.py` proves the CNI enforces a bare default-deny.
        It says nothing about whether OUR policy lets a tenant reach itself and
        blocks everyone else — that is a property of the labels and selectors this
        module renders, and it needs its own experiment.
        """
        probe = REPO / "scripts" / "verify_tenant_isolation.py"
        assert probe.is_file()
        source = probe.read_text(encoding="utf-8")
        # It must test against the shipped renderer, not a policy shape of its own.
        assert "render_tenancy" in source or "network_policies_apply_to" in source


class TestDisasterRecovery:
    """The registry must be sufficient to rebuild a tenant, and "rebuilt" must be
    checkable rather than assumed.

    A live drill destroyed globex/dev entirely (namespace + Capsule Tenant) and
    rebuilt it from `render_tenancy` alone: labels came back byte-identical and every
    object was recreated. But for ~10 seconds the Tenant still reported NAMESPACE
    COUNT = 0 — namespace present, correctly labelled, quota binding nothing. That
    window is indistinguishable at a glance from the permanent version of the same
    state (Capsule refusing to adopt at all), which is exactly where the first Phase
    2 apply got stuck.
    """

    def test_render_is_deterministic(self, registry):
        """A rebuild that produces different objects is not a rebuild."""
        first = render_tenancy(registry, "globex", "dev")
        second = render_tenancy(registry, "globex", "dev")
        assert first == second

    def test_rebuild_needs_nothing_but_the_registry(self, registry):
        """No cluster reads in the render path: DR cannot depend on the thing that died."""
        objects = render_tenancy(registry, "globex", "dev")
        kinds = [o["kind"] for o in objects]
        assert {"Tenant", "Namespace", "Role", "RoleBinding"} <= set(kinds)

    def test_adoption_has_a_verifier(self):
        """Because "objects exist" and "the quota binds them" are different facts."""
        probe = REPO / "scripts" / "verify_tenancy_adoption.py"
        assert probe.is_file()
        source = probe.read_text(encoding="utf-8")
        # It must compare the env's declared cluster with the current context: the
        # first version reported a tenant on another cluster as unenforced, which is
        # the false alarm the script exists to prevent.
        assert "current_cluster" in source
        assert "status" in source and "size" in source, "must read the tenant's owned count"


class TestApplyOrder:
    """`render_tenancy` claims to emit objects in apply order, and that claim is
    load-bearing rather than cosmetic.

    Live `kubectl apply -f -` of a NEW tenant failed until this was fixed: each
    namespace carries `capsule.clastix.io/tenant`, and Capsule's mutating webhook
    rejects a namespace naming a tenant that does not exist yet. Every unit test
    passed throughout, because they assert the SET of rendered objects and never the
    sequence — and the one existing tenant had been applied piecemeal, so the wrong
    order was never exercised.
    """

    def test_capsule_tenant_precedes_its_namespaces(self, registry):
        kinds = [o["kind"] for o in render_tenancy(registry, "acme", "dev")]
        assert kinds.index("Tenant") < kinds.index("Namespace"), (
            "Capsule's mutating webhook rejects a namespace whose tenant does not exist"
        )

    def test_namespaces_precede_everything_namespaced(self, registry):
        kinds = [o["kind"] for o in render_tenancy(registry, "acme", "dev")]
        last_namespace = max(i for i, k in enumerate(kinds) if k == "Namespace")
        for kind in ("Role", "RoleBinding", "NetworkPolicy"):
            assert min(i for i, k in enumerate(kinds) if k == kind) > last_namespace, (
                f"{kind} would be applied into a namespace that does not exist yet"
            )
