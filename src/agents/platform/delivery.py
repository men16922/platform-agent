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
from dataclasses import dataclass, field
from typing import Any

from src.agents.platform.addon_status import NormalizedAddonStatus
from src.agents.platform.registry import Environment, Tenant


class ClusterSingletonCapability(ValueError):
    """Raised when a cluster-scoped capability is asked to be rendered per tenant.

    An error rather than a silent skip. A skip would produce a manifest set that
    installs *most* of what the tenant declared, and the missing part is precisely
    the shared infrastructure whose absence looks identical to a delivery lag.
    """


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
    #: From the catalog: is this backend operated by the cloud rather than by us?
    #:
    #: Carried on the addon for the same reason as `scope` below — both engines must
    #: answer it identically and neither may forget to ask. A managed backend has
    #: nothing to install, so the adapters render **no manifest** for it. That is not
    #: a silent drop: the collector reports the same add-on through `from_managed`
    #: with `applicable=False` and `sync_state=NOT_APPLICABLE`, so the absence from
    #: the render is explained by the read model instead of looking like delivery lag.
    #: The two halves are a pair, and `test_managed_backend_renders_nothing.py` fails
    #: if either one disappears alone.
    managed: bool = False

    #: From the catalog: can this backend exist once per tenant?
    #:
    #: Carried on the addon rather than looked up inside each adapter, so both
    #: engines answer the question the same way and neither can forget to ask it.
    #: Defaults to namespace only because this field arrived after the adapters;
    #: `desired_addons_for`, which reads the catalog, fills it in for real callers.
    scope: str = "namespace"

    #: Baseline Helm values from the catalog's declared file.
    #:
    #: Not optional decoration: most of the charts this platform declares fail
    #: `helm template` outright without them (loki demands
    #: `loki.storage.bucketNames.chunks`), so an adapter that renders chart+version
    #: alone produces an Application that can never sync. Found live, on an
    #: Application that reported Unknown/Healthy while installing nothing.
    values: dict[str, Any] = field(default_factory=dict)

    @property
    def is_cluster_singleton(self) -> bool:
        """Cluster-scoped **and** something we install.

        A managed backend is excluded because the failure this property guards is
        "two controllers reconciling the same objects", and nothing is installed for
        a managed one — there is no second controller to create. Excluding it is also
        what stops the singleton message from being wrong: it tells the reader to
        "give the tenant an instance (a Prometheus CR)", which for AMP sends them to
        build something that cannot exist (the worry recorded in the Phase 4 plan's
        correction box, and in `TestManagedBackendRendersNothing`).
        """
        return self.scope == "cluster" and not self.managed


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

        **Deletion must cascade.** Removing the rendered object must remove what it
        installed, because the only reason to remove it is that the tenant no longer
        subscribes to that capability. This has to be stated here rather than left to
        each engine, since the engines disagree by default: Flux uninstalls its
        release, while ArgoCD orphans every resource unless the Application carries
        `resources-finalizer.argocd.argoproj.io`. Left unstated, one declared intent
        produces a cleaned-up cluster on Flux and a running workload nobody owns on
        Argo — and the Argo side was observed live, with the Application gone and its
        pods still serving.
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


def reject_cluster_singletons(addons: list[DesiredAddon]) -> None:
    """Guard every adapter's ``render`` must pass through.

    Lives on the contract rather than inside each engine because the failure it
    prevents is engine-independent: a cluster-scoped backend rendered once per
    tenant installs a second controller that reconciles the same objects as the
    first. Nothing errors, nothing logs; the two simply fight. Duplicating the
    check per adapter would mean a future third engine can omit it and inherit the
    bug — the same shape as the ordering primitive this contract already centralises.
    """
    singletons = sorted({a.capability for a in addons if a.is_cluster_singleton})
    if singletons:
        raise ClusterSingletonCapability(
            f"{', '.join(singletons)} are cluster-scoped in the catalog and cannot be "
            "rendered per tenant: a second installation would reconcile the same "
            "objects as the existing one. Install once per cluster; give the tenant "
            "an instance (a Prometheus CR, a Rollout), not another operator."
        )


def desired_addons(
    tenant: Tenant,
    env: Environment,
    wave_of: Any,
    scope_of: Any = None,
    values_of: Any = None,
    is_managed: Any = None,
) -> list[DesiredAddon]:
    """
    Expand a tenant/env's declared add-ons into DesiredAddon records, wave-sorted.

    ``wave_of`` is a callable (capability -> int), normally ``Registry.wave_for``.
    ``scope_of`` is (capability -> "cluster"|"namespace"), normally
    ``Registry.scope_of``; omitted, every add-on is treated as namespace-scoped,
    which is only safe for callers that are not about to install anything.
    ``is_managed`` is (capability, backend -> bool), normally
    ``Registry.is_managed_backend`` — the same callable the collector already
    takes, so the read and render paths answer "is this managed?" the same way
    instead of growing two answers. Omitted, no add-on is treated as managed,
    which is only right where the registry declares none — `globex/dev` declares one
    since 2026-08-17.
    Sorting here means every adapter receives the same order regardless of the
    mapping order in YAML.
    """
    expanded: list[DesiredAddon] = []
    for capability, declared in env.addons.items():
        parts = declared.split()
        backend = parts[0] if parts else capability
        version = parts[-1] if len(parts) > 1 else None
        # Marked, not dropped and not an error. Until 2026-08-17 this raised
        # `ManagedBackendNotRenderable`, because passing a managed backend through as
        # a chart name would make the engine chase a chart the self-hosted repo does
        # not publish — true, but it also left a tenant unable to declare one at all,
        # which is Phase 4a's DoD ①②. The decision that was deferred: a managed
        # backend expands into a record the adapters recognise and render *nothing*
        # for, and the read model explains the absence (`from_managed`,
        # `applicable=False`). No new manifest kind was invented for it.
        expanded.append(
            DesiredAddon(
                tenant=tenant.name,
                env=env.name,
                capability=capability,
                backend=backend,
                version=version,
                wave=wave_of(capability),
                namespace=tenant.namespace_for(env.name, capability),
                managed=bool(is_managed and is_managed(capability, backend)),
                scope=scope_of(capability) if scope_of else "namespace",
                values=values_of(capability) if values_of else {},
            )
        )
    return sorted(expanded, key=lambda a: (a.wave, a.capability))
