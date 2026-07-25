"""
Delivery adapters — one GitOps engine each, behind the shared contract.

Two real implementations exist on purpose (plan Phase 1b): a single
implementation always fits its own abstraction, so the contract is only tested
once a second engine has to satisfy it. ArgoCD and Flux disagree in exactly the
places that matter — ordering primitive, status vocabulary, and object shape —
which is what makes them a useful pair.
"""

from src.agents.platform.adapters.argocd import ArgoCDDeliveryAdapter
from src.agents.platform.adapters.flux import FluxDeliveryAdapter

#: Registry keyed by the registry's `delivery` field.
DELIVERY_ADAPTERS = {
    ArgoCDDeliveryAdapter.engine: ArgoCDDeliveryAdapter,
    FluxDeliveryAdapter.engine: FluxDeliveryAdapter,
}


def get_delivery_adapter(engine: str):
    """Resolve an engine name to its adapter class. Raises KeyError if unknown."""
    try:
        return DELIVERY_ADAPTERS[engine]
    except KeyError as exc:
        raise KeyError(
            f"unknown delivery engine {engine!r}; known: {sorted(DELIVERY_ADAPTERS)}"
        ) from exc


__all__ = ["ArgoCDDeliveryAdapter", "FluxDeliveryAdapter", "DELIVERY_ADAPTERS", "get_delivery_adapter"]
