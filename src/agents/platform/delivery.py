"""
Delivery adapter contract — capability in, engine-specific manifests out.

Phase 0 defines the interface only; the two real implementations (argocd + flux)
land in Phase 1b, which is when the contract gets pressure-tested. Two backends
is the point: one implementation always fits its own abstraction.

**tenant/env are threaded through every method on purpose.** The plan's top
invariant is that an agent's blast radius is one tenant/env, and the enforcement
has to live in the code seam rather than in prose — a signature that cannot
express "which tenant" cannot be audited for it later.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from src.agents.platform.addon_status import NormalizedAddonStatus
from src.agents.platform.registry import Environment, Tenant


@dataclass(frozen=True)
class DesiredAddon:
    """One (tenant, env, capability) the delivery engine must reconcile."""

    tenant: str
    env: str
    capability: str
    backend: str
    version: str | None
    # Reconcile order from the catalog; each engine renders it into its own
    # primitive (ArgoCD sync-wave / Flux dependsOn) — this replaces the Terraform
    # `depends_on` ordering that disappears at the Phase 1b handoff.
    wave: int
    # Prefixed target namespace, so two tenants on one cluster cannot collide.
    namespace: str


class DeliveryAdapter(ABC):
    """
    A GitOps engine behind one interface (ArgoCD | Flux | Config Sync).

    Implementations must be *pure renderers plus readers*: they translate desired
    state into their engine's objects and translate observed state back into
    NormalizedAddonStatus. They must not execute remediation — that path has its
    own scoped-credential seam (Phase 1a) and must not be reachable from here.
    """

    #: Engine identifier matching the registry's `delivery` field.
    engine: str = ""

    @abstractmethod
    def render(self, tenant: Tenant, env: Environment, addons: list[DesiredAddon]) -> list[dict[str, Any]]:
        """
        Render desired add-ons into engine-specific manifests.

        Must be deterministic: the Phase 1b DoD requires adoption of already-installed
        releases to be a **no-churn** no-op, and a renderer whose output wobbles
        between runs would trigger delete-and-recreate (PVC loss).
        """

    @abstractmethod
    def observe(self, tenant: Tenant, env: Environment) -> list[NormalizedAddonStatus]:
        """
        Read back observed state as normalized two-axis status.

        Implementations must not fabricate the sync axis when their engine does not
        report it (Flux collapses sync+health into one condition) — UNKNOWN is the
        honest answer, and `applicable=False` is for backends with no sync concept.
        """

    @abstractmethod
    def ordering_annotation(self, wave: int) -> dict[str, Any]:
        """
        The engine's ordering primitive for a wave (sync-wave vs dependsOn).

        Exists as its own method because ordering is the one thing the handoff
        silently drops; making it explicit keeps it from being forgotten again.
        """


def desired_addons(tenant: Tenant, env: Environment, wave_of: Any) -> list[DesiredAddon]:
    """
    Expand a tenant/env's declared add-ons into DesiredAddon records, wave-sorted.

    ``wave_of`` is a callable (capability -> int), normally ``Registry.wave_for``.
    Sorting here means every adapter receives the same order regardless of the
    mapping order in YAML.
    """
    expanded: list[DesiredAddon] = []
    for capability, declared in env.addons.items():
        parts = declared.split()
        backend = parts[0] if parts else capability
        version = parts[-1] if len(parts) > 1 else None
        expanded.append(
            DesiredAddon(
                tenant=tenant.name,
                env=env.name,
                capability=capability,
                backend=backend,
                version=version,
                wave=wave_of(capability),
                namespace=tenant.namespace_for(env.name, capability),
            )
        )
    return sorted(expanded, key=lambda a: (a.wave, a.capability))
