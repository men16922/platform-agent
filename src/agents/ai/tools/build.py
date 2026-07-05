"""Build container image tool for Strands deployer agent."""

from __future__ import annotations

from strands.tools import tool

from src.agents.adapters.deployment import ServiceSpec, get_deployment_adapters


@tool
def build_image(
    service_name: str,
    image: str,
    version: str,
    provider: str = "local",
    context_path: str = ".",
) -> dict:
    """Build a container image for a service.

    Args:
        service_name: Name of the service to build.
        image: Image name (without registry prefix).
        version: Image version/tag.
        provider: Deployment provider (local, aws, gcp, azure).
        context_path: Docker build context path.

    Returns:
        Dict with build result (success, image_tag, error).
    """
    spec = ServiceSpec(name=service_name, image=image, version=version, provider=provider)
    adapters = get_deployment_adapters(provider)
    result = adapters.build.build(spec, context_path=context_path)
    return {
        "success": result.success,
        "image_tag": result.image_tag,
        "build_id": result.build_id,
        "error": result.error,
    }
