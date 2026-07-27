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


def build_delivery_adapter(engine: str, repo_url: str = ""):
    """Instantiate an engine's adapter for one chart's repository.

    One adapter per add-on, not per env: the repository is a property of the chart.
    ArgoCD renders the URL into the Application's Source, so it has to be on the
    adapter; Flux reads it from the HelmRepository the manifest references, so it
    keeps the value and never renders it. Threading it in uniformly means callers
    do not branch on the engine — which is where the third caller would go wrong.
    """
    return get_delivery_adapter(engine)(repo_url=repo_url)


__all__ = ["ArgoCDDeliveryAdapter", "FluxDeliveryAdapter", "DELIVERY_ADAPTERS", "get_delivery_adapter"]
