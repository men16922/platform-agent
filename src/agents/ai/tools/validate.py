"""Validate deployment health tool for Strands deployer agent."""

from __future__ import annotations

from strands.tools import tool

from src.agents.adapters.deployment import ServiceSpec, get_deployment_adapters


@tool
def validate_deployment(
    service_name: str,
    provider: str = "local",
    namespace: str = "default",
) -> dict:
    """Validate a deployed service by checking rollout status and readiness.

    Args:
        service_name: Name of the deployment to validate.
        provider: Deployment provider (local, aws, gcp, azure).
        namespace: Kubernetes namespace.

    Returns:
        Dict with validation result (healthy, checks_passed, error).
    """
    spec = ServiceSpec(name=service_name, image=service_name, version="", provider=provider, namespace=namespace)
    adapters = get_deployment_adapters(provider)
    result = adapters.cluster.validate(spec)
    return {
        "healthy": result.healthy,
        "checks_passed": result.checks_passed,
        "checks_total": result.checks_total,
        "details": result.details,
        "error": result.error,
    }
