"""Rollback deployment tool for Strands deployer agent."""

from __future__ import annotations

from strands.tools import tool

from src.agents.adapters.deployment import ServiceSpec, get_deployment_adapters


@tool
def rollback_deployment(
    service_name: str,
    provider: str = "local",
    namespace: str = "default",
) -> dict:
    """Rollback a deployment to its previous version.

    Args:
        service_name: Name of the deployment to rollback.
        provider: Deployment provider (local, aws, gcp, azure).
        namespace: Kubernetes namespace.

    Returns:
        Dict with rollback result (success, rolled_back_to, error).
    """
    spec = ServiceSpec(name=service_name, image=service_name, version="", provider=provider, namespace=namespace)
    adapters = get_deployment_adapters(provider)
    result = adapters.cluster.rollback(spec)
    return {
        "success": result.success,
        "rolled_back_to": result.rolled_back_to,
        "error": result.error,
    }
