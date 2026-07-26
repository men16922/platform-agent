"""
ArgoCD delivery adapter.

Renders one ``Application`` per (tenant, env, capability) and maps ArgoCD's two
native status fields onto our two axes. Argo already separates sync from health,
so the status mapping is close to a rename — the value is that Flux and managed
backends end up in the same shape.

Ordering: ``argocd.argoproj.io/sync-wave``. This matters more than it looks. Today
the add-on install order is held by Terraform ``depends_on``; when Phase 1b hands
ownership to GitOps that ordering disappears with it, so the wave annotation is
its replacement, not a nicety.
"""

from __future__ import annotations

from typing import Any

from src.agents.platform.addon_status import NormalizedAddonStatus, from_argocd
from src.agents.platform.delivery import (
    DeliveryAdapter,
    DesiredAddon,
    reject_cluster_singletons,
)
from src.agents.platform.registry import Environment, Tenant

#: Argo resolves the in-cluster destination by this well-known address.
IN_CLUSTER_SERVER = "https://kubernetes.default.svc"

#: Makes deleting an Application delete what it installed. Argo's default is to
#: orphan, which is the opposite of what "the tenant unsubscribed" means.
RESOURCES_FINALIZER = "resources-finalizer.argocd.argoproj.io"


class ArgoCDDeliveryAdapter(DeliveryAdapter):
    engine = "argocd"

    def __init__(self, repo_url: str = "", target_revision: str = "main", project: str = "default"):
        self.repo_url = repo_url
        self.target_revision = target_revision
        self.project = project

    def ordering_annotation(self, wave: int) -> dict[str, Any]:
        # String on purpose: Argo parses the annotation value, and Kubernetes
        # annotations are string-valued — an int here serialises to a type error.
        return {"argocd.argoproj.io/sync-wave": str(wave)}

    def render(
        self, tenant: Tenant, env: Environment, addons: list[DesiredAddon]
    ) -> list[dict[str, Any]]:
        # Before anything is rendered: a cluster singleton rendered per tenant is a
        # second controller, not a second copy.
        reject_cluster_singletons(addons)
        manifests: list[dict[str, Any]] = []
        for addon in addons:
            name = f"{tenant.naming_prefix}-{env.name}-{addon.capability}"
            manifests.append(
                {
                    "apiVersion": "argoproj.io/v1alpha1",
                    "kind": "Application",
                    "metadata": {
                        "name": name,
                        "namespace": "argocd",
                        # Deleting this Application removes what it installed.
                        #
                        # Without the finalizer Argo drops the Application and leaves
                        # every resource running, which a live run confirmed: the
                        # Application was gone and its two controller pods were still
                        # there. `prune: true` does not cover this — pruning removes
                        # resources that fell out of a sync, and a deleted Application
                        # never syncs again.
                        #
                        # It also makes the two engines mean the same thing by
                        # deletion: Flux uninstalls its release, so without this,
                        # "unsubscribe from an add-on" would leave a workload behind
                        # on ArgoCD clusters and not on Flux ones — the same declared
                        # intent with opposite outcomes per engine.
                        #
                        # Caveat that survives this fix: the cascade covers what the
                        # ENGINE manages. PVCs created from a StatefulSet's
                        # volumeClaimTemplates are created by Kubernetes, not by Argo,
                        # so they outlive it. Unsubscribing a stateful add-on still
                        # leaves disks; that is a data-retention default, not an
                        # accident, but it must not be mistaken for a clean removal.
                        "finalizers": [RESOURCES_FINALIZER],
                        "annotations": self.ordering_annotation(addon.wave),
                        "labels": {
                            # Tenancy is queryable from the object itself; the
                            # dashboard must not have to parse names to group by tenant.
                            "platform-agent.io/tenant": tenant.name,
                            "platform-agent.io/env": env.name,
                            "platform-agent.io/capability": addon.capability,
                        },
                    },
                    "spec": {
                        "project": self.project,
                        # For a Helm chart source `targetRevision` IS the chart
                        # version (for a git source it would be the branch), so the
                        # add-on's pinned version wins over the adapter default.
                        "source": {
                            "repoURL": self.repo_url,
                            "chart": addon.backend,
                            "targetRevision": addon.version or self.target_revision,
                        },
                        "destination": {"server": IN_CLUSTER_SERVER, "namespace": addon.namespace},
                        "syncPolicy": {
                            "automated": {"prune": True, "selfHeal": True},
                            "syncOptions": ["CreateNamespace=true"],
                        },
                    },
                }
            )
        return manifests

    def observe(self, tenant: Tenant, env: Environment) -> list[NormalizedAddonStatus]:
        """
        Map observed Applications onto the two axes.

        Live reading is Phase 2 (and is a *push* from an in-cluster agent, so the
        hub holds no spoke credentials). This method exists so the contract is
        exercised now; ``observations`` is injected by the caller in tests.
        """
        return []

    @staticmethod
    def normalise(
        tenant: str, env: str, capability: str, application: dict[str, Any]
    ) -> NormalizedAddonStatus:
        """Translate one Application's status dict into the normalized shape."""
        status = application.get("status") or {}
        return from_argocd(
            tenant=tenant,
            env=env,
            capability=capability,
            sync_status=(status.get("sync") or {}).get("status", ""),
            health_status=(status.get("health") or {}).get("status", ""),
            desired_version=(application.get("spec") or {}).get("source", {}).get("targetRevision"),
        )
