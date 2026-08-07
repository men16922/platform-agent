"""
Soft-tier tenancy objects, rendered from the registry.

Phase 2's first slice. Everything downstream has been waiting on the *namespaces*
this produces: the per-tenant NetworkPolicy chart and the PSS work both target
``<prefix>-<env>-<capability>`` namespaces carrying ``platform-agent.io/tenant``,
and both are still default-OFF for exactly that reason — a policy applied to a
namespace that does not exist is a policy that protects nothing while reading as
"isolated" in an audit.

TWO DECISIONS WORTH STATING, because both are places where a plausible
implementation would quietly produce a false guarantee.

**1. Quota is a TENANT bound, not a namespace bound.**
A tenant declares ``cpu: "16"``. It gets four namespaces (one per subscribed
capability). Emitting a 16-CPU ResourceQuota into each namespace does not enforce
the declared bound — it grants 64. The failure is silent and in the generous
direction, which is the worst kind on a shared cluster: the registry says 16, the
dashboard says 16, and a co-tenant gets starved by a neighbour running at 4x its
stated ceiling. So the quota is rendered ONLY as a Capsule ``Tenant`` with
``resourceQuotas.scope: Tenant``. No Capsule, no quota object — an absent bound
is at least visibly absent.

How that scope actually behaves, measured rather than assumed (kind, Capsule
0.13.10): Capsule writes a ResourceQuota into every tenant namespace and then
**rewrites each one's ``hard`` to the tenant's REMAINING budget** as usage moves.
Reading them at rest is misleading — all four namespaces show ``limits.cpu: 16``
and it looks exactly like the 4x bug. Consuming 10 in one namespace drops the
others to ``limited: limits.cpu=6``, and a second 10-CPU request is refused.
Deleting the workload restores all of them to 16. The static read says "broken";
only the consumption test says "correct".

**2. Only the soft tier gets namespace-scoped tenancy.**
vcluster and dedicated draw their boundary elsewhere (a virtual control plane, a
physical cluster). Rendering namespace RBAC for them would produce objects that
look like isolation while the real boundary lives somewhere else entirely, which
invites someone to "verify tenancy" by reading the wrong artifact. Those tiers
render nothing here, loudly.
"""

from __future__ import annotations

from typing import Any

from src.agents.platform.registry import IsolationTier, Registry, Tenant

#: Label keys the rest of the platform already selects on. Changing these breaks
#: the NetworkPolicy chart's podSelector and the dashboard's grouping at once.
TENANT_LABEL = "platform-agent.io/tenant"
ENV_LABEL = "platform-agent.io/env"
CAPABILITY_LABEL = "platform-agent.io/capability"

CAPSULE_API_VERSION = "capsule.clastix.io/v1beta2"
#: Capsule's own membership label. Ours describe the namespace; this one decides
#: whether the tenant's quota applies to it.
CAPSULE_TENANT_LABEL = "capsule.clastix.io/tenant"

#: Substrates on which NetworkPolicy enforcement has been PROVEN by experiment
#: (``scripts/verify_netpol_enforcement.py`` reporting ENFORCED), not by reading a
#: support matrix:
#:
#:   kind — kindnet, k8s v1.34.0, re-probed 2026-07-26
#:         (docs/evidence/onprem-netpol-tenancy-e2e.log)
#:
#: Anything absent here is *unverified*, which is not the same as unsupported. The
#: distinction matters because the failure is silent and inverted: a policy applied
#: to a CNI that ignores it leaves `kubectl get netpol` healthy and every audit view
#: reading "isolated" while traffic flows. Rendering nothing is honestly insecure;
#: rendering an unenforced policy is dishonestly secure.
#:
#: k3s — MEASURED 2026-07-29, DELIBERATELY NOT ADDED YET.
#:   k3s v1.31.4+k3s1 (flannel + k3s's built-in kube-router policy controller,
#:   server started with no `--disable-network-policy`). Three facts, all live,
#:   evidence in docs/evidence/k3s-netpol-enforcement.log:
#:     * verify_netpol_enforcement.py -> ENFORCED, with its control valid
#:       (B->A reachable with no policy first, then blocked by default-deny)
#:     * a readinessProbe pod born UNDER default-deny still reaches Ready, so the
#:       node-sourced probes no namespaceSelector can match are not blocked
#:     * DNS resolves under the same policy (policyTypes is [Ingress] only)
#:   What is still missing is the claim this set actually licenses: that OUR
#:   rendered policy shape isolates correctly — same-tenant reachable,
#:   cross-tenant denied. `verify_tenant_isolation.py` exists for exactly that.
#:
#:   This comment used to say the probe "cannot run here because acme/prod is the
#:   only env on k3s-lab". That was true and was NOT the binding reason — it was
#:   repeated in four files and none of them named the two that matter (D40,
#:   docs/plans/2026-08-01-k3s-proven-substrate.md). Measured 2026-08-01:
#:     * acme/prod subscribes ONE add-on, so it renders ONE namespace; the probe's
#:       same-tenant leg needs two and exits before it ever looks at the peer.
#:     * THE GATE IS CIRCULAR. The probe refuses to start unless
#:       `network_policies_apply_to` is true, and that reads this very set — so a
#:       candidate substrate fails the precondition no matter how the registry is
#:       arranged. Promotion means flipping this set FIRST and reverting if the
#:       probe disagrees. kind passed because kind was already inside; what the
#:       probe actually performs is regression, not promotion.
#:     * `k3s-lab` has no tenancy at all — no Capsule, no Flux, zero
#:       NetworkPolicies, and `acme-prod-*` has never existed on that 20-day-old
#:       cluster. Nothing reconciles it, so a registry edit provisions nothing,
#:       and adding k3s here would protect zero workloads today.
#:   k3s stays out: enforcement proven, semantics unproven, and the value is
#:   entirely future value. Reopen the moment something actually runs on k3s-lab.
#:   `tests/test_substrate_promotion_reachable.py` fails if anything is added here
#:   whose claim the registry cannot falsify.
PROVEN_ENFORCING_SUBSTRATES = frozenset({"kind"})

#: Namespaces every tenant namespace still accepts ingress from.
#:
#: Note on what this does NOT do, because the first version of this policy carried
#: the opposite claim: these policies set ``policyTypes: [Ingress]`` only, so egress
#: is untouched and DNS — which is egress, from the pod to kube-dns — keeps working
#: with or without this entry. Verified live rather than reasoned about: a policied
#: pod resolved ``kubernetes.default`` with kube-system NOT in this list.
#: What the entry is actually for is kube-system components that OPEN connections to
#: tenant pods. Empty by default: on kind nothing in kube-system does, kubelet probes
#: come from the node (not a pod, so no namespaceSelector can match them and kindnet
#: permits them regardless — live-verified with a readinessProbe under default-deny),
#: and an allowance nobody needs is just a hole nobody audits.
DEFAULT_SHARED_NAMESPACES: tuple[str, ...] = ()

#: Pod Security Standards applied at the namespace, matching the chart-side
#: securityContext that was shipped and live-verified with ⑥.
_PSS_LABELS = {
    "pod-security.kubernetes.io/enforce": "restricted",
    "pod-security.kubernetes.io/enforce-version": "latest",
}

#: The remediation surface an agent needs inside its own tenant. Deliberately
#: enumerated — a wildcard here would silently re-grant everything Phase 1a spent
#: its effort taking away.
_AGENT_RULES: list[dict[str, Any]] = [
    {
        "apiGroups": [""],
        "resources": ["pods", "pods/log", "events", "services", "configmaps"],
        "verbs": ["get", "list", "watch"],
    },
    {"apiGroups": [""], "resources": ["pods"], "verbs": ["delete"]},
    {
        "apiGroups": ["apps"],
        "resources": ["deployments", "statefulsets", "replicasets", "daemonsets"],
        "verbs": ["get", "list", "watch", "patch", "update"],
    },
    {
        "apiGroups": ["apps"],
        "resources": ["deployments/scale", "statefulsets/scale"],
        "verbs": ["get", "update", "patch"],
    },
    {
        "apiGroups": ["argoproj.io"],
        "resources": ["rollouts"],
        "verbs": ["get", "list", "watch", "patch", "update"],
    },
]


class UnsupportedTier(ValueError):
    """Raised for tiers whose boundary is not the namespace."""


def namespaces_for(tenant: Tenant, env_name: str) -> list[tuple[str, str]]:
    """``(capability, namespace)`` for every add-on the env subscribes to."""
    env = tenant.environments.get(env_name)
    if env is None:
        return []
    return [
        (capability, tenant.namespace_for(env_name, capability))
        for capability in sorted(env.addons)
    ]


def render_namespaces(tenant: Tenant, env_name: str) -> list[dict[str, Any]]:
    """Namespace objects carrying the labels every downstream policy selects on."""
    if tenant.isolation is not IsolationTier.SOFT:
        raise UnsupportedTier(
            f"{tenant.name} is {tenant.isolation.value}: its boundary is not the namespace"
        )
    objects = []
    for capability, namespace in namespaces_for(tenant, env_name):
        objects.append({
            "apiVersion": "v1",
            "kind": "Namespace",
            "metadata": {
                "name": namespace,
                "labels": {
                    TENANT_LABEL: tenant.name,
                    ENV_LABEL: env_name,
                    CAPABILITY_LABEL: capability,
                    # What actually puts the namespace INSIDE the tenant. Without
                    # it the namespace exists, carries our tenant labels, and is
                    # not in the tenant at all — quota bounds nothing while every
                    # view reads "acme, 16 CPU". Capsule only honours this from an
                    # identity listed as an administrator in its configuration.
                    CAPSULE_TENANT_LABEL: f"{tenant.naming_prefix}-{env_name}",
                    **_PSS_LABELS,
                },
            },
        })
    return objects


def render_rbac(tenant: Tenant, env_name: str, *, service_account: str) -> list[dict[str, Any]]:
    """A ServiceAccount + Role + RoleBinding per namespace, granting only the
    remediation surface.

    Namespaced on purpose: a ClusterRole would make the credential reach every
    tenant on the cluster, which is precisely the blast radius Phase 1a closed.

    The ServiceAccount is rendered here rather than assumed to exist. It was
    assumed through Phase 1a, and live inspection in Phase 3 found the result: the
    RoleBinding pointed at ``platform-agent`` in a namespace that had no such
    ServiceAccount, so the identity this entire boundary rests on had never been
    created. Kubernetes accepts a binding to an absent subject without complaint,
    so ``kubectl get rolebinding`` showed a healthy-looking grant that could not
    be exercised by anybody. It failed closed, which is why nothing broke and
    nothing surfaced — the same "no error, just not read" shape as the values-file
    and Capsule-deprecation defects.
    """
    if tenant.isolation is not IsolationTier.SOFT:
        raise UnsupportedTier(
            f"{tenant.name} is {tenant.isolation.value}: its boundary is not the namespace"
        )
    objects: list[dict[str, Any]] = []
    for _capability, namespace in namespaces_for(tenant, env_name):
        role_name = f"{tenant.naming_prefix}-agent"
        labels = {TENANT_LABEL: tenant.name, ENV_LABEL: env_name}
        objects.append({
            "apiVersion": "v1",
            "kind": "ServiceAccount",
            "metadata": {"name": service_account, "namespace": namespace, "labels": labels},
        })
        objects.append({
            "apiVersion": "rbac.authorization.k8s.io/v1",
            "kind": "Role",
            "metadata": {"name": role_name, "namespace": namespace, "labels": labels},
            "rules": _AGENT_RULES,
        })
        objects.append({
            "apiVersion": "rbac.authorization.k8s.io/v1",
            "kind": "RoleBinding",
            "metadata": {"name": role_name, "namespace": namespace, "labels": labels},
            "roleRef": {
                "apiGroup": "rbac.authorization.k8s.io",
                "kind": "Role",
                "name": role_name,
            },
            "subjects": [{
                "kind": "ServiceAccount",
                "name": service_account,
                "namespace": namespace,
            }],
        })
    return objects


def substrate_enforces_network_policy(substrate: str) -> bool:
    """Has NetworkPolicy enforcement been *proven* on this substrate?"""
    return substrate in PROVEN_ENFORCING_SUBSTRATES


def render_network_policies(
    tenant: Tenant,
    env_name: str,
    *,
    shared_namespaces: tuple[str, ...] = DEFAULT_SHARED_NAMESPACES,
) -> list[dict[str, Any]]:
    """Default-deny ingress + same-tenant allowance, one policy per namespace.

    This narrows the soft tier's documented "no data-plane isolation"
    non-guarantee: without it, any pod on the cluster can reach any tenant's pods,
    and the only thing separating two tenants is that they do not know each
    other's Service names.

    Rendered from the registry, and that is the whole point of moving it here. The
    predecessor was a Helm chart carrying its own hand-maintained lists of tenants
    x envs x capabilities — a cartesian product of 16 namespaces against a registry
    that subscribes 6. Ten of those policies named namespaces that will never
    exist, and no ``helm_release`` ever installed the chart, so the isolation it
    described was never applied anywhere. Deriving the policy set from the same
    call that renders the namespaces (``namespaces_for``) makes the two sets equal
    by construction rather than by a test that notices they drifted.

    Selection is by the ``platform-agent.io/tenant`` LABEL, not by namespace name:
    NetworkPolicy peers cannot match names by prefix, so the label is what makes
    "same tenant" expressible at all. The namespace must therefore carry it, which
    ``render_namespaces`` and the Capsule tenant both ensure.
    """
    if tenant.isolation is not IsolationTier.SOFT:
        raise UnsupportedTier(
            f"{tenant.name} is {tenant.isolation.value}: its boundary is not the namespace"
        )
    peers: list[dict[str, Any]] = [
        {"namespaceSelector": {"matchLabels": {TENANT_LABEL: tenant.name}}}
    ]
    peers.extend(
        {"namespaceSelector": {"matchLabels": {"kubernetes.io/metadata.name": shared}}}
        for shared in shared_namespaces
    )

    objects: list[dict[str, Any]] = []
    for _capability, namespace in namespaces_for(tenant, env_name):
        objects.append({
            "apiVersion": "networking.k8s.io/v1",
            "kind": "NetworkPolicy",
            "metadata": {
                "name": "deny-cross-tenant",
                "namespace": namespace,
                "labels": {TENANT_LABEL: tenant.name, ENV_LABEL: env_name},
            },
            "spec": {
                # Empty selector = every pod in this namespace.
                "podSelector": {},
                # Ingress only. A default-deny EGRESS would also block DNS and image
                # pulls, and the symptom (name resolution failing) reads as an
                # application bug rather than a policy effect.
                "policyTypes": ["Ingress"],
                "ingress": [{"from": peers}],
            },
        })
    return objects


#: Per-container defaults for tenant namespaces. Kept next to the quota they serve,
#: because they are only meaningful together — see ``render_limit_ranges``.
_CONTAINER_DEFAULTS = {
    "type": "Container",
    "default": {"cpu": "500m", "memory": "512Mi"},
    "defaultRequest": {"cpu": "50m", "memory": "64Mi"},
}


def render_limit_ranges(tenant: Tenant, env_name: str) -> list[dict[str, Any]]:
    """Per-container defaults, one ``LimitRange`` per tenant namespace.

    These are NOT cosmetic, and the live measurement is why this function exists as
    an object rather than a Capsule ``Tenant`` field. ``render_capsule_tenant``
    declares the quota in terms of ``limits.cpu``/``limits.memory``, and Kubernetes
    turns that into an admission requirement: every container in the namespace must
    state its own limits or be rejected. Measured on kind with the LimitRange
    removed (docs/evidence/capsule-limitranges-direct.log):

        pods "lr-probe-nolimits" is forbidden: failed quota: capsule-acme-dev-0:
        must specify limits.cpu for: c; limits.memory for: c

    None of the four add-on values files sets limits, so every tenant workload
    depends on these defaults. The failure would also be invisible where it matters:
    a chart whose pods are refused at admission still reports Synced with zero pods
    (STATUS Open Risk 8).

    Why not Capsule's ``spec.limitRanges``: that field is deprecated in favour of
    Tenant Replications, and both replacements cost something this repo does not
    want to pay — ``GlobalTenantResource`` is cluster-scoped (D30 forbids the agent
    reaching past the tenant) and ``TenantResource`` needs a ServiceAccount plus
    RBAC so Capsule can do the replicating on our behalf. Rendering the object
    directly needs neither, because there is no deputy to authorise: the identity
    that already creates this namespace's ServiceAccount, Role, RoleBinding and
    NetworkPolicy can create a LimitRange. It is the same move this module already
    made for ``spec.networkPolicies``, which is deprecated for the same reason.

    What is given up is Capsule's reconciliation — delete this object and nothing
    restores it. That is the identical trade already accepted for the
    NetworkPolicies above, and the namespace set comes from ``namespaces_for``
    either way, so a namespace cannot appear without one.
    """
    if tenant.isolation is not IsolationTier.SOFT:
        raise UnsupportedTier(
            f"{tenant.name} is {tenant.isolation.value}: its boundary is not the namespace"
        )
    return [
        {
            "apiVersion": "v1",
            "kind": "LimitRange",
            "metadata": {
                "name": f"{tenant.naming_prefix}-defaults",
                "namespace": namespace,
                "labels": {TENANT_LABEL: tenant.name, ENV_LABEL: env_name},
            },
            "spec": {"limits": [dict(_CONTAINER_DEFAULTS)]},
        }
        for _capability, namespace in namespaces_for(tenant, env_name)
    ]


def service_account_owner(namespace: str, name: str) -> str:
    """Capsule's required owner spelling for a ServiceAccount.

    Its validating webhook rejects a bare name:
      "Username must be in the form system:serviceaccount:namespace:name"
    Caught by the first live apply — the unit tests had only ever asserted the
    shape this module invented, which is exactly the gap a live run closes.
    """
    return f"system:serviceaccount:{namespace}:{name}"


def render_capsule_tenant(
    tenant: Tenant, env_name: str, *, owner: str
) -> dict[str, Any] | None:
    """A Capsule ``Tenant`` — the only object that can enforce the declared bound.

    Returns None when the tenant declares no quota: emitting an empty
    ResourceQuota would read as "bounded" in every view while bounding nothing.
    """
    if tenant.isolation is not IsolationTier.SOFT:
        raise UnsupportedTier(
            f"{tenant.name} is {tenant.isolation.value}: its boundary is not the namespace"
        )
    hard = {}
    if tenant.quota.cpu:
        hard["limits.cpu"] = tenant.quota.cpu
    if tenant.quota.memory:
        hard["limits.memory"] = tenant.quota.memory
    if tenant.quota.pods is not None:
        hard["pods"] = str(tenant.quota.pods)
    if not hard:
        return None

    return {
        "apiVersion": CAPSULE_API_VERSION,
        "kind": "Tenant",
        "metadata": {
            "name": f"{tenant.naming_prefix}-{env_name}",
            "labels": {TENANT_LABEL: tenant.name, ENV_LABEL: env_name},
        },
        "spec": {
            "owners": [{"name": owner, "kind": "ServiceAccount"}],
            # scope: Tenant aggregates across the tenant's namespaces. Per-namespace
            # scope would multiply the declared bound by the namespace count.
            "resourceQuotas": {"scope": "Tenant", "items": [{"hard": hard}]},
            # NOTE: no `limitRanges` here. It is deprecated in favour of Tenant
            # Replications, and the per-container defaults it used to carry are now
            # rendered as plain LimitRange objects — see `render_limit_ranges` for
            # why that beats both replacements. Capsule reclaims the LimitRanges it
            # owns when this field disappears (measured), so the two never overlap.
            "namespaceOptions": {
                # `additionalMetadata` (singular) is deprecated in favour of this
                # list form. Migrated because of *how* that deprecation will
                # fail: Capsule drops unknown spec fields rather than rejecting
                # them, so on the release that removes it the PSS labels would
                # simply stop being placed on tenant namespaces — no error, no
                # event, and `enforce: restricted` silently absent. Same failure
                # mode as the add-on values files (Open Risk 5): not an error,
                # just not read.
                "additionalMetadataList": [
                    {"labels": {TENANT_LABEL: tenant.name, ENV_LABEL: env_name, **_PSS_LABELS}},
                ],
            },
        },
    }


def render_tenancy(
    registry: Registry,
    tenant_name: str,
    env_name: str,
    *,
    service_account: str = "platform-agent",
    service_account_namespace: str = "default",
    owner: str | None = None,
    include_network_policies: bool = True,
) -> list[dict[str, Any]]:
    """Every soft-tier object for one tenant/env, in apply order.

    NetworkPolicies are included by default but **skipped on a substrate whose
    enforcement has not been proven** (see ``PROVEN_ENFORCING_SUBSTRATES``). The
    skip is silent here on purpose — this function is pure, and the caller that can
    actually tell a human (``scripts/render_tenancy.py``) reports it as a
    non-guarantee. Both directions of the alternative are worse: refusing to render
    would make an unverified substrate unprovisionable, and rendering anyway would
    ship a policy that reads as isolation and enforces nothing.
    """
    tenant = registry.tenant(tenant_name)
    # ORDER IS LOAD-BEARING: the Capsule Tenant must exist before its namespaces.
    # Each namespace carries `capsule.clastix.io/tenant`, and Capsule's MUTATING
    # webhook rejects a namespace claiming membership in a tenant it cannot find:
    #   admission webhook "namespaces.mutating.projectcapsule.dev" denied the
    #   request: tenants.capsule.clastix.io "globex-dev" not found
    # This module previously emitted namespaces first while its docstring claimed
    # "in apply order", and every unit test passed because they assert the SET of
    # objects, never the sequence. It only surfaced when a *new* tenant was applied
    # in one `kubectl apply -f -`; the existing tenant had been built up piecemeal,
    # so the wrong order had never been exercised.
    objects: list[dict[str, Any]] = []
    capsule = render_capsule_tenant(
        tenant,
        env_name,
        owner=owner or service_account_owner(service_account_namespace, service_account),
    )
    if capsule is not None:
        objects.append(capsule)
    objects.extend(render_namespaces(tenant, env_name))
    # After the namespaces, before anything that runs in them: the quota above only
    # admits containers that state limits, and these supply the defaults that let
    # them. Emitted whenever a Capsule Tenant was emitted, because that is exactly
    # when a `limits.*` quota exists to satisfy.
    if capsule is not None:
        objects.extend(render_limit_ranges(tenant, env_name))
    objects.extend(render_rbac(tenant, env_name, service_account=service_account))
    if include_network_policies and network_policies_apply_to(tenant, env_name):
        objects.extend(render_network_policies(tenant, env_name))
    return objects


def network_policies_apply_to(tenant: Tenant, env_name: str) -> bool:
    """Will this tenant/env get data-plane isolation, and can the cluster enforce it?"""
    env = tenant.environments.get(env_name)
    if env is None:
        return False
    return tenant.isolation is IsolationTier.SOFT and substrate_enforces_network_policy(
        env.substrate
    )


def unbounded_soft_tenants(registry: Registry) -> list[str]:
    """Soft-tier tenants sharing a cluster with no declared quota.

    Not a rendering concern — a reporting one. On a shared cluster an unbounded
    tenant is a co-tenant outage waiting for a bad deploy, and the registry is
    the only place that fact is visible before it happens.
    """
    return sorted(
        name
        for name, tenant in registry.tenants.items()
        if tenant.isolation is IsolationTier.SOFT and not tenant.quota.to_dict()
    )
