"""Deploy service to cluster tool for Strands deployer agent."""

from __future__ import annotations

from strands.tools import tool

from src.agents.adapters.deployment import ServiceSpec, get_deployment_adapters


@tool
def deploy_to_cluster(
    service_name: str,
    image: str,
    version: str,
    image_uri: str,
    provider: str = "local",
    replicas: int = 1,
    namespace: str = "default",
    health_path: str = "/healthz",
    ports: list[int] | None = None,
) -> dict:
    """Deploy a service to the target cluster.

    Args:
        service_name: Name of the service/deployment.
        image: Image name.
        version: Image version.
        image_uri: Full image URI (from push step).
        provider: Deployment provider (local, aws, gcp, azure).
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
        provider=provider,
        replicas=replicas,
        namespace=namespace,
        health_path=health_path,
        ports=ports or [8080],
    )
    adapters = get_deployment_adapters(provider)
    result = adapters.cluster.deploy(spec, image_uri)
    return {
        "status": result.status.value,
        "deployment_id": result.deployment_id,
        "namespace": result.namespace,
        "replicas_desired": result.replicas_desired,
        "endpoint": result.endpoint,
        "error": result.error,
    }
