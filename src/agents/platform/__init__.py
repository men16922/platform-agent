"""
Multi-tenant / multi-cloud platform layer (Phase 0 — model + contracts only).

Plan: docs/plans/2026-07-21-multi-tenant-env-addons.md (v5, grade S 93.5).
Phase 0 is deliberately inert: schema, loader, adapter contract and the
normalized status type. No runtime behaviour changes here — credential isolation
is Phase 1a and the delivery adapters are Phase 1b.
"""

from src.agents.platform.addon_status import (
    HealthState,
    NormalizedAddonStatus,
    SyncState,
    from_argocd,
    from_flux,
    from_managed,
)
from src.agents.platform.adapters import (
    ArgoCDDeliveryAdapter,
    FluxDeliveryAdapter,
    get_delivery_adapter,
)
from src.agents.platform.delivery import DeliveryAdapter, DesiredAddon
from src.agents.platform.registry import (
    Environment,
    IsolationTier,
    Quota,
    Registry,
    Tenant,
    load_registry,
    validate_registry,
)

__all__ = [
    "ArgoCDDeliveryAdapter",
    "DeliveryAdapter",
    "FluxDeliveryAdapter",
    "DesiredAddon",
    "Environment",
    "HealthState",
    "IsolationTier",
    "NormalizedAddonStatus",
    "Quota",
    "Registry",
    "SyncState",
    "Tenant",
    "from_argocd",
    "from_flux",
    "from_managed",
    "get_delivery_adapter",
    "load_registry",
    "validate_registry",
]
