"""
Git registry loader — the platform SSOT (`platform/`).

Layout (partitioned so no god-object forms and CODEOWNERS can gate per tenant):

    platform/catalog.yaml        shared capability catalog (+ reconcile wave)
    platform/tenants/<name>.yaml one file per tenant, owned by that tenant

The loader is read-only and pure: Phase 0 changes no runtime behaviour. Writes
(dashboard "attach add-on" -> PR against one tenant file) are Phase 5.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

import yaml

# Repo-root/platform — the registry is a git artifact, not packaged code.
DEFAULT_REGISTRY_ROOT = Path(__file__).resolve().parents[3] / "platform"

# Namespace-safe: the prefix becomes part of Kubernetes object names.
_PREFIX_RE = re.compile(r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?$")

_SUBSTRATES = frozenset({"kind", "k3s", "eks", "gke", "aks"})
_DELIVERY_ENGINES = frozenset({"argocd", "flux", "config-sync"})

#: Whether a capability's backend can exist once per tenant or only once per
#: cluster. See the rationale block in platform/catalog.yaml — this axis exists
#: because a live run installed a second cluster-scoped controller that then
#: fought the first one silently.
CAPABILITY_SCOPES = frozenset({"cluster", "namespace"})


class IsolationTier(str, Enum):
    """
    Isolation strength — and therefore the **credential boundary unit**.

    Not interchangeable options: a spectrum of strength vs cost. The tier decides
    whether credentials are scoped per tenant or per cluster, which is why it is
    a first-class registry field rather than a deployment detail.
    """

    # Several tenants share one cluster by namespace -> boundary is per-TENANT.
    SOFT = "soft"
    # Virtual control plane per tenant -> boundary is per-vcluster kubeconfig.
    VCLUSTER = "vcluster"
    # Physical cluster per tenant -> only here does env == cluster == tenant.
    DEDICATED = "dedicated"

    @property
    def credential_scope(self) -> str:
        """What a scoped credential is issued *for* under this tier."""
        if self is IsolationTier.SOFT:
            # Per-env would reach co-tenant namespaces on the shared cluster.
            return "tenant"
        return "env"


@dataclass(frozen=True)
class Quota:
    """Capsule-enforced ResourceQuota/LimitRange bounds (API objects only)."""

    cpu: str | None = None
    memory: str | None = None
    pods: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in {"cpu": self.cpu, "memory": self.memory, "pods": self.pods}.items() if v is not None}


@dataclass(frozen=True)
class Environment:
    """One env of one tenant: a cluster, a substrate, and a subset of add-ons."""

    name: str
    cluster: str
    substrate: str
    delivery: str = "argocd"
    # capability -> "<chart> <version>" as declared; versions are per-env on
    # purpose (dev bump -> verify -> promote to prod by PR, never lockstep).
    addons: dict[str, str] = field(default_factory=dict)

    def addon_version(self, capability: str) -> str | None:
        """Declared version for a capability, or None when not subscribed."""
        declared = self.addons.get(capability)
        if not declared:
            return None
        parts = declared.split()
        return parts[-1] if len(parts) > 1 else None


@dataclass(frozen=True)
class Tenant:
    name: str
    isolation: IsolationTier
    naming_prefix: str
    quota: Quota
    environments: dict[str, Environment]

    @property
    def credential_scope(self) -> str:
        return self.isolation.credential_scope

    def namespace_for(self, env: str, component: str) -> str:
        """
        Prefixed namespace name — structural collision avoidance on a shared cluster.

        Two tenants subscribing to the same capability in the same cluster must not
        land on the same namespace; the prefix is what makes that impossible.
        """
        return f"{self.naming_prefix}-{env}-{component}"


@dataclass(frozen=True)
class Registry:
    catalog: dict[str, Any]
    tenants: dict[str, Tenant]

    def tenant(self, name: str) -> Tenant:
        try:
            return self.tenants[name]
        except KeyError as exc:
            raise KeyError(f"unknown tenant '{name}'") from exc

    def environment(self, tenant: str, env: str) -> Environment:
        found = self.tenant(tenant).environments.get(env)
        if found is None:
            raise KeyError(f"tenant '{tenant}' has no env '{env}'")
        return found

    def wave_for(self, capability: str) -> int:
        """
        Reconcile order for a capability.

        Terraform's `depends_on` disappears when Phase 1b hands ownership to
        GitOps; delivery adapters render this into ArgoCD `sync-wave` / Flux
        `dependsOn`. Unknown capabilities default to the workload wave.
        """
        entry = self.catalog.get("capabilities", {}).get(capability) or {}
        wave = entry.get("wave", 2)
        return wave if isinstance(wave, int) else 2

    def scope_of(self, capability: str) -> str:
        """``"cluster"`` or ``"namespace"`` — can this run once per tenant?

        Defaults to ``cluster`` for an unknown capability, which is the direction
        that fails safe: the wrong answer for a namespace-scoped add-on is a
        refusal someone must correct in the catalog, while the wrong answer for a
        cluster singleton is two controllers fighting over the same objects with
        nothing in any log to say so.
        """
        entry = self.catalog.get("capabilities", {}).get(capability) or {}
        scope = entry.get("scope")
        return scope if scope in CAPABILITY_SCOPES else "cluster"

    def is_cluster_scoped(self, capability: str) -> bool:
        return self.scope_of(capability) == "cluster"

    def capabilities_missing_scope(self) -> list[str]:
        """Catalog entries with no declared scope — a reporting concern, not fatal.

        They behave as cluster-scoped (so nothing gets silently duplicated), which
        means the symptom is an adapter refusing to render them. Naming them here
        keeps that refusal from looking like a bug in the adapter.
        """
        return sorted(
            name
            for name, entry in (self.catalog.get("capabilities") or {}).items()
            if not isinstance(entry, dict) or entry.get("scope") not in CAPABILITY_SCOPES
        )

    def backend_for(self, capability: str, substrate: str, *, managed: bool = False) -> str | None:
        """Resolve capability -> backend. Managed resolution is substrate-keyed."""
        entry = self.catalog.get("capabilities", {}).get(capability) or {}
        backends = entry.get("backends") or {}
        if not managed:
            return backends.get("self_hosted")
        managed_map = backends.get("managed") or {}
        return managed_map.get(_cloud_of(substrate))

    def environments_of_cluster(self, cluster: str) -> list[tuple[str, str]]:
        """
        Every (tenant, env) landing on one cluster.

        Used to reason about blast radius: under the soft tier this list having
        more than one tenant is exactly why credentials must be per-tenant.
        """
        return [
            (tenant.name, env.name)
            for tenant in self.tenants.values()
            for env in tenant.environments.values()
            if env.cluster == cluster
        ]


def _cloud_of(substrate: str) -> str:
    return {"eks": "aws", "gke": "gcp", "aks": "azure"}.get(substrate, "onprem")


def validate_registry(catalog: Any, tenants: dict[str, Any]) -> list[str]:
    """Return a list of problems. Empty list = valid."""
    problems: list[str] = []

    if not isinstance(catalog, dict) or not isinstance(catalog.get("capabilities"), dict):
        problems.append("catalog must be a dict with a 'capabilities' mapping")
        known_capabilities: set[str] = set()
    else:
        known_capabilities = set(catalog["capabilities"])
        for name, entry in catalog["capabilities"].items():
            if not isinstance(entry, dict):
                problems.append(f"catalog.capabilities.{name} must be a dict")
                continue
            wave = entry.get("wave")
            if not isinstance(wave, int) or wave < 0:
                problems.append(f"catalog.capabilities.{name}.wave must be a non-negative int")
            # A *wrong* scope is a problem; a missing one is not.
            #
            # The first version of this rejected an absent scope too, and that made
            # the loader — which is fail-closed by design — refuse to load any
            # registry written before this field existed. Turning a documentation
            # gap into "the platform view will not load at all" is a worse failure
            # than the one being guarded against, especially when the guard is
            # already elsewhere: `scope_of` defaults to cluster, so an omission
            # makes the adapters REFUSE to render per tenant. Loud, safe, one line
            # to fix. Omissions in our own catalog are caught by a test instead,
            # and `capabilities_missing_scope` makes them reportable anywhere else.
            scope = entry.get("scope")
            if scope is not None and scope not in CAPABILITY_SCOPES:
                problems.append(
                    f"catalog.capabilities.{name}.scope must be one of cluster|namespace"
                )

    for tenant_name, data in tenants.items():
        prefix = f"tenants.{tenant_name}"
        if not isinstance(data, dict):
            problems.append(f"{prefix} must be a dict")
            continue

        isolation = data.get("isolation")
        if isolation not in {t.value for t in IsolationTier}:
            problems.append(f"{prefix}.isolation must be one of soft|vcluster|dedicated")

        naming_prefix = data.get("naming_prefix")
        if not isinstance(naming_prefix, str) or not _PREFIX_RE.match(naming_prefix or ""):
            problems.append(f"{prefix}.naming_prefix must be a DNS-label-safe string")

        environments = data.get("environments")
        if not isinstance(environments, dict) or not environments:
            problems.append(f"{prefix}.environments must be a non-empty mapping")
            continue

        for env_name, env in environments.items():
            env_prefix = f"{prefix}.environments.{env_name}"
            if not isinstance(env, dict):
                problems.append(f"{env_prefix} must be a dict")
                continue
            if not isinstance(env.get("cluster"), str) or not env["cluster"].strip():
                problems.append(f"{env_prefix}.cluster must be a non-empty string")
            if env.get("substrate") not in _SUBSTRATES:
                problems.append(f"{env_prefix}.substrate must be one of {sorted(_SUBSTRATES)}")
            delivery = env.get("delivery", "argocd")
            if delivery not in _DELIVERY_ENGINES:
                problems.append(f"{env_prefix}.delivery must be one of {sorted(_DELIVERY_ENGINES)}")
            addons = env.get("addons", {})
            if not isinstance(addons, dict):
                problems.append(f"{env_prefix}.addons must be a mapping")
                continue
            # An add-on the catalog never defined cannot be resolved to a backend.
            for capability in addons:
                if known_capabilities and capability not in known_capabilities:
                    problems.append(f"{env_prefix}.addons.{capability} is not in the catalog")

    return problems


def load_registry(root: Path | str | None = None) -> Registry:
    """
    Load and validate the registry. Raises ValueError on invalid content.

    Fail-closed on purpose: a malformed registry must not silently degrade into a
    partial platform view where a tenant's isolation tier is missing.
    """
    root = Path(root) if root is not None else DEFAULT_REGISTRY_ROOT
    catalog_path = root / "catalog.yaml"
    if not catalog_path.is_file():
        raise FileNotFoundError(f"registry catalog not found: {catalog_path}")

    catalog = yaml.safe_load(catalog_path.read_text(encoding="utf-8")) or {}
    raw_tenants: dict[str, Any] = {}
    for path in sorted((root / "tenants").glob("*.yaml")):
        raw_tenants[path.stem] = yaml.safe_load(path.read_text(encoding="utf-8")) or {}

    problems = validate_registry(catalog, raw_tenants)
    if problems:
        raise ValueError("invalid platform registry: " + "; ".join(problems))

    tenants: dict[str, Tenant] = {}
    for name, data in raw_tenants.items():
        quota_raw = data.get("quota") or {}
        environments = {
            env_name: Environment(
                name=env_name,
                cluster=env["cluster"],
                substrate=env["substrate"],
                delivery=env.get("delivery", "argocd"),
                addons=dict(env.get("addons") or {}),
            )
            for env_name, env in data["environments"].items()
        }
        tenants[name] = Tenant(
            name=name,
            isolation=IsolationTier(data["isolation"]),
            naming_prefix=data["naming_prefix"],
            quota=Quota(
                cpu=quota_raw.get("cpu"),
                memory=quota_raw.get("memory"),
                pods=quota_raw.get("pods"),
            ),
            environments=environments,
        )

    return Registry(catalog=catalog, tenants=tenants)
