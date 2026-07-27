"""Agent tools that stand up a tenant boundary and the add-ons inside it.

Until now the registry could describe a multi-tenant platform that only a human at
a prompt could create: `render_tenancy.py` and `render_addons.py` print manifests
and stop, on purpose, because applying them installs software into a shared
cluster. That left the last two steps of "set up a tenant" outside the agent — it
could provision a cluster from one sentence and then had nothing to say about who
the cluster was for.

These two tools close that gap and are deliberately the only mutating platform
tools the agent has. What they do NOT do is install the cluster-level stack (ArgoCD,
Capsule, kube-prometheus, Loki, Tempo, Rollouts): that stack is Terraform-owned,
and an agent applying Helm releases over a Terraform state produces two owners for
one object with nothing in either place saying so. The tools therefore assume the
stack is present and say plainly when it is not.

Three refusals are carried over from the scripts, because they are the difference
between "applied" and "enforced":

* An unknown tenant/env is an error, never an empty success.
* A quota that will not be enforced (no Capsule CRD) is reported in the same
  breath as the namespaces that were created. `kubectl apply` drops that object
  without erroring, and the tenant is then unbounded on a shared cluster while the
  registry and every dashboard still show its declared quota.
* Cluster-singleton capabilities are refused **by name**. A per-tenant
  argo-rollouts is a second controller reconciling the first one's objects, and a
  silent omission reads as "this tenant has no progressive delivery" rather than
  "progressive delivery is a shared cluster install".

And one refusal that is new here, because a tool driven by a sentence cannot be
asked "are you on the right cluster?": both tools compare the active kubeconfig
context against the cluster the registry says the env lives on, and refuse on
mismatch. `make demo-baseline` prints the context and trusts a human to read it;
nothing reads it on the agent's behalf.
"""

from __future__ import annotations

from typing import Any

from src.agents.platform.adapters import build_delivery_adapter
from src.agents.platform.cluster_io import (
    apply_manifests,
    capsule_crd_installed,
    current_context,
)
from src.agents.platform.delivery import desired_addons
from src.agents.platform.registry import Environment, Registry, Tenant, load_registry
from src.agents.platform.tenancy import (
    UnsupportedTier,
    namespaces_for,
    network_policies_apply_to,
    render_tenancy,
)


def _resolve(tenant_name: str, env_name: str) -> tuple[Registry, Tenant, Environment] | dict[str, Any]:
    """Registry lookup + context guard, or the error dict both tools return.

    The guard is the blast-radius invariant made mechanical: the tools can only
    write to the cluster the registry says this env is on. Without it, one sentence
    naming a tenant would apply to whatever context the operator last used, and on
    kind that always succeeds — the worst shape of failure, because it looks like
    it worked.
    """
    registry = load_registry()
    try:
        tenant = registry.tenant(tenant_name)
    except KeyError:
        known = ", ".join(sorted(registry.tenants)) or "none"
        return {"success": False, "error": f"no tenant {tenant_name!r} in the registry (known: {known})"}
    try:
        env = registry.environment(tenant_name, env_name)
    except KeyError:
        known = ", ".join(sorted(tenant.environments)) or "none"
        return {
            "success": False,
            "error": f"tenant {tenant_name!r} has no env {env_name!r} (known: {known})",
        }

    context = current_context()
    if context is None:
        return {
            "success": False,
            "error": "no reachable cluster — kubectl has no current context. Provision one first.",
        }
    if context != env.cluster:
        return {
            "success": False,
            "error": (
                f"refusing to write: kubectl context is {context!r} but the registry puts "
                f"{tenant_name}/{env_name} on cluster {env.cluster!r}. Switch context or fix the registry."
            ),
        }
    return registry, tenant, env


def setup_tenancy(tenant: str, env: str, service_account: str = "platform-agent") -> dict:
    """Create one tenant/env's isolation boundary from the registry. MUTATING.

    Applies the tenant's namespaces, RBAC, NetworkPolicies and Capsule quota object
    as the registry declares them. Run this before installing that tenant's add-ons:
    the add-ons are objects inside these namespaces.

    Args:
        tenant: Tenant name as declared in the registry (e.g. "acme").
        env: Environment name within that tenant (e.g. "dev").
        service_account: Service account the tenant's RBAC is bound to.

    Returns:
        Dict with success, the namespaces created, the declared quota, and
        ``enforced`` — per-axis truth about what this cluster will actually hold to.
        When an axis is not enforced, ``note`` says so explicitly: report that
        verbatim, because applied is not enforced and the difference is invisible
        in every view that shows the declared quota.
    """
    resolved = _resolve(tenant, env)
    if isinstance(resolved, dict):
        return resolved
    registry, tenant_obj, env_obj = resolved

    if not namespaces_for(tenant_obj, env):
        return {"success": False, "error": f"tenant {tenant!r} declares no namespaces for env {env!r}"}
    try:
        objects = render_tenancy(registry, tenant, env, service_account=service_account)
    except UnsupportedTier as exc:
        return {"success": False, "error": str(exc)}

    result = apply_manifests(objects)
    kinds = [o["kind"] for o in objects]
    namespaces = [o["metadata"]["name"] for o in objects if o["kind"] == "Namespace"]

    quota_declared = "Tenant" in kinds
    capsule = capsule_crd_installed() if quota_declared else None
    network = network_policies_apply_to(tenant_obj, env)

    gaps: list[str] = []
    if not quota_declared:
        gaps.append("the registry declares no quota for this tenant, so nothing bounds it")
    elif capsule is None:
        gaps.append("could not verify the Capsule CRD, so the quota is unconfirmed")
    elif not capsule:
        gaps.append(
            "QUOTA IS NOT ENFORCED: the Capsule CRD is absent, so the quota object was "
            "dropped without an error and this tenant is unbounded on a shared cluster"
        )
    if not network:
        gaps.append(
            f"NO DATA-PLANE ISOLATION: substrate {env_obj.substrate!r} is not in the "
            "proven-enforcing set, so no NetworkPolicy was rendered — any pod on this "
            "cluster can reach these namespaces"
        )

    note = f"{len(namespaces)} namespace(s) for {tenant}/{env} on {env_obj.cluster}"
    if gaps:
        note += " — but " + "; ".join(gaps)

    return {
        "success": result["ok"],
        "tenant": tenant,
        "env": env,
        "cluster": env_obj.cluster,
        "tier": tenant_obj.isolation.value,
        "credential_scope": tenant_obj.isolation.credential_scope,
        "namespaces": namespaces,
        "applied": result["applied"],
        "objects": {kind: kinds.count(kind) for kind in sorted(set(kinds))},
        "quota_declared": tenant_obj.quota.to_dict(),
        "enforced": {"quota": bool(capsule) if quota_declared else False, "network": network},
        "enforcement_gaps": gaps,
        "warnings": result["warnings"],
        "note": note,
        "error": result["error"],
    }


def install_tenant_addons(tenant: str, env: str, capability: str | None = None) -> dict:
    """Install one tenant/env's declared add-ons inside its namespaces. MUTATING.

    Renders the tenant's subscriptions from the registry — repository, chart,
    version and values all come from there — and applies them as delivery objects
    (ArgoCD Applications or Flux HelmReleases, whichever the env declares). Requires
    the tenant's namespaces to exist already: call `setup_tenancy` first.

    Args:
        tenant: Tenant name as declared in the registry (e.g. "acme").
        env: Environment name within that tenant (e.g. "dev").
        capability: Install only this capability (e.g. "logging"); omit for all
            of the env's declared add-ons.

    Returns:
        Dict with success, the capabilities installed, and two fields that must be
        reported rather than dropped: ``shared_not_per_tenant`` (cluster-scoped
        capabilities this tenant uses but does not get a copy of) and
        ``not_installable`` (declared add-ons the registry cannot produce an
        installable manifest for, with the reason).
    """
    resolved = _resolve(tenant, env)
    if isinstance(resolved, dict):
        return resolved
    registry, tenant_obj, env_obj = resolved

    declared = desired_addons(
        tenant_obj, env_obj, registry.wave_for, registry.scope_of, registry.values_for
    )
    if capability:
        if capability not in {a.capability for a in declared}:
            known = ", ".join(sorted(a.capability for a in declared)) or "none"
            return {
                "success": False,
                "error": f"{tenant}/{env} declares no capability {capability!r} (declared: {known})",
            }
        declared = [a for a in declared if a.capability == capability]

    shared = sorted(a.capability for a in declared if a.is_cluster_singleton)
    renderable = [a for a in declared if not a.is_cluster_singleton]
    problems = {
        a.capability: reason
        for a in renderable
        if (reason := registry.uninstallable_reason(a.capability))
    }
    installable = [a for a in renderable if a.capability not in problems]

    manifests: list[dict[str, Any]] = []
    for addon in installable:
        adapter = build_delivery_adapter(env_obj.delivery, registry.repo_for(addon.capability))
        manifests.extend(adapter.render(tenant_obj, env_obj, [addon]))

    installed = [a.capability for a in installable]
    if not manifests:
        # Not an error and not a success: "nothing to do" and "everything here is
        # shared" are different facts, and a bare empty result states neither.
        note = f"nothing applied for {tenant}/{env}"
        if shared:
            note += (
                f" — {', '.join(shared)} {'is' if len(shared) == 1 else 'are'} cluster-scoped, "
                "one installation serves every tenant"
            )
        return {
            "success": False, "tenant": tenant, "env": env, "installed": [],
            "shared_not_per_tenant": shared, "not_installable": problems,
            "note": note, "error": None,
        }

    result = apply_manifests(manifests)
    note = (
        f"{len(manifests)} {env_obj.delivery} object(s) for {', '.join(installed)} "
        f"in {tenant}/{env} on {env_obj.cluster}; they reconcile asynchronously, so "
        "health is not immediate"
    )
    if shared:
        note += f". Shared cluster installs (no per-tenant copy): {', '.join(shared)}"
    if problems:
        note += f". NOT INSTALLABLE: {'; '.join(f'{c} — {w}' for c, w in sorted(problems.items()))}"

    return {
        "success": result["ok"] and not problems,
        "tenant": tenant,
        "env": env,
        "cluster": env_obj.cluster,
        "delivery": env_obj.delivery,
        "installed": installed,
        "applied": result["applied"],
        "shared_not_per_tenant": shared,
        "not_installable": problems,
        "warnings": result["warnings"],
        "note": note,
        "error": result["error"],
    }


TENANCY_TOOLS = [setup_tenancy, install_tenant_addons]
