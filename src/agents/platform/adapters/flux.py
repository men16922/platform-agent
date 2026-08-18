"""
Flux delivery adapter.

Exists to keep the contract honest: ArgoCD alone would let the interface quietly
become Argo-shaped. Flux disagrees in the three places that matter, and each
disagreement is where a leaky abstraction would show up:

* **Ordering** is ``spec.dependsOn`` (a reference to another object), not an
  annotation carrying a number. So the contract's ``wave`` must be an engine-
  neutral integer that each adapter renders its own way — the adapter turns a
  wave into "depends on everything in the previous wave".
* **Status** collapses sync and health into one ``Ready`` condition, so the
  mapping is lossy by nature. Not-ready means "did not reconcile", which is a
  health fact; claiming ``drifted`` would invent information Flux never reported.
* **Objects** are a pair (``HelmRepository`` + ``HelmRelease``) rather than one
  ``Application``, so ``render`` returning a *list* is load-bearing.
"""

from __future__ import annotations

from typing import Any

from src.agents.platform.addon_status import NormalizedAddonStatus, from_flux
from src.agents.platform.delivery import (
    DeliveryAdapter,
    DesiredAddon,
    reject_cluster_singletons,
)
from src.agents.platform.registry import Environment, Tenant


class FluxDeliveryAdapter(DeliveryAdapter):
    engine = "flux"

    def __init__(self, repo_url: str = "", interval: str = "5m", namespace: str = "flux-system"):
        self.repo_url = repo_url
        self.interval = interval
        self.namespace = namespace

    def ordering_annotation(self, wave: int) -> dict[str, Any]:
        """
        Flux orders by object reference, not by a number.

        A wave becomes "depend on the previous wave's marker object", which is how
        an engine-neutral integer survives translation into Flux's model. Wave 0
        has nothing to wait for.
        """
        if wave <= 0:
            return {"dependsOn": []}
        return {"dependsOn": [{"name": f"wave-{wave - 1}", "namespace": self.namespace}]}

    def render(
        self, tenant: Tenant, env: Environment, addons: list[DesiredAddon]
    ) -> list[dict[str, Any]]:
        reject_cluster_singletons(addons)
        manifests: list[dict[str, Any]] = []
        for addon in addons:
            if addon.managed:
                # Nothing to install: the cloud operates this backend. Skipped here
                # rather than filtered by the caller so both engines behave the same
                # way, and it is not a silent drop — the collector reports the same
                # add-on via `from_managed` (`applicable=False`, sync n/a), which is
                # what distinguishes "served elsewhere" from "delivery is lagging".
                continue
            name = f"{tenant.naming_prefix}-{env.name}-{addon.capability}"
            labels = {
                "platform-agent.io/tenant": tenant.name,
                "platform-agent.io/env": env.name,
                "platform-agent.io/capability": addon.capability,
            }
            manifests.append(
                {
                    "apiVersion": "helm.toolkit.fluxcd.io/v2",
                    "kind": "HelmRelease",
                    "metadata": {
                        "name": name,
                        "namespace": addon.namespace,
                        "labels": labels,
                    },
                    "spec": {
                        "interval": self.interval,
                        # `releaseName` and `targetNamespace` must match whatever a
                        # pre-existing Helm release used, or adoption becomes a
                        # delete-and-recreate (PVC loss) instead of a no-op.
                        "releaseName": name,
                        "targetNamespace": addon.namespace,
                        "chart": {
                            "spec": {
                                "chart": addon.backend,
                                **({"version": addon.version} if addon.version else {}),
                                "sourceRef": {
                                    "kind": "HelmRepository",
                                    "name": f"{addon.capability}-repo",
                                    "namespace": self.namespace,
                                },
                            }
                        },
                        "install": {"createNamespace": True},
                        # Flux takes values inline on the HelmRelease. Same baseline
                        # dict as ArgoCD receives, so the two engines install the
                        # same thing rather than each engine's chart defaults.
                        **({"values": addon.values} if addon.values else {}),
                        **self.ordering_annotation(addon.wave),
                    },
                }
            )
        return manifests

    def observe(self, tenant: Tenant, env: Environment) -> list[NormalizedAddonStatus]:
        """Live reading is Phase 2 (push-based). See ArgoCD adapter for the rationale."""
        return []

    @staticmethod
    def normalise(
        tenant: str, env: str, capability: str, helm_release: dict[str, Any]
    ) -> NormalizedAddonStatus:
        """Translate one HelmRelease's Ready condition into the normalized shape."""
        status = helm_release.get("status") or {}
        conditions = status.get("conditions") or []
        ready_condition = next((c for c in conditions if c.get("type") == "Ready"), {})
        # Absent/"Unknown" all collapse to None = "Flux has not said" — which must
        # stay distinguishable from an explicit False.
        raw = str(ready_condition.get("status") or "")
        ready = {"True": True, "False": False}.get(raw)
        spec = helm_release.get("spec") or {}
        return from_flux(
            tenant=tenant,
            env=env,
            capability=capability,
            ready=ready,
            suspended=bool(spec.get("suspend")),
            desired_version=((spec.get("chart") or {}).get("spec") or {}).get("version"),
            reason=ready_condition.get("reason"),
        )
