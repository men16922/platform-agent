"""Deploy service to AKS tool for MS Agent Framework deployer (Azure)."""

from __future__ import annotations

from src.agents.adapters.deployment import ServiceSpec, get_deployment_adapters


def azure_deploy_to_cluster(
    service_name: str,
    image: str,
    version: str,
    image_uri: str,
    replicas: int = 1,
    namespace: str = "default",
    health_path: str = "/healthz",
    ports: list[int] | None = None,
) -> dict:
    """Deploy a service to Azure Kubernetes Service (AKS).

    Args:
        service_name: Name of the service/deployment.
        image: Image name.
        version: Image version.
        image_uri: Full image URI (from push step).
        replicas: Number of replicas.
        namespace: Kubernetes namespace.
        health_path: Health check endpoint path.
        ports: Container ports (default [8080]).

    Returns:
        Dict with deploy result (status, deployment_id, error).
    """
    spec = ServiceSpec(
        name=service_name,
        image=image,
        version=version,
        provider="azure",
        replicas=replicas,
        namespace=namespace,
        health_path=health_path,
        ports=ports or [8080],
    )
    adapters = get_deployment_adapters("azure")
    result = adapters.cluster.deploy(spec, image_uri)
    return {
        "status": result.status.value,
        "deployment_id": result.deployment_id,
        "namespace": result.namespace,
        "replicas_desired": result.replicas_desired,
        "endpoint": result.endpoint,
        "error": result.error,
    }


def azure_validate_deployment(
    service_name: str,
    namespace: str = "default",
) -> dict:
    """Validate a deployed service on AKS by checking rollout status.

    Args:
        service_name: Name of the deployment to validate.
        namespace: Kubernetes namespace.

    Returns:
        Dict with validation result (healthy, checks_passed, error).
    """
    spec = ServiceSpec(name=service_name, image=service_name, version="", provider="azure", namespace=namespace)
    adapters = get_deployment_adapters("azure")
    result = adapters.cluster.validate(spec)
    return {
        "healthy": result.healthy,
        "checks_passed": result.checks_passed,
        "checks_total": result.checks_total,
        "details": result.details,
        "error": result.error,
    }


def azure_rollback_deployment(
    service_name: str,
    namespace: str = "default",
) -> dict:
    """Rollback a deployment on AKS to its previous version.

    Args:
        service_name: Name of the deployment to rollback.
        namespace: Kubernetes namespace.

    Returns:
        Dict with rollback result (success, rolled_back_to, error).
    """
    spec = ServiceSpec(name=service_name, image=service_name, version="", provider="azure", namespace=namespace)
    adapters = get_deployment_adapters("azure")
    result = adapters.cluster.rollback(spec)
    return {
        "success": result.success,
        "rolled_back_to": result.rolled_back_to,
        "error": result.error,
    }
