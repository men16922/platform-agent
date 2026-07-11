"""Build container image tool for MS Agent Framework deployer (Azure)."""

from __future__ import annotations


from src.agents.adapters.deployment import ServiceSpec, get_deployment_adapters


def azure_build_image(
    service_name: str,
    image: str,
    version: str,
    context_path: str = ".",
) -> dict:
    """Build a container image using Azure Container Registry Tasks (az acr build).

    Args:
        service_name: Name of the service to build.
        image: Image name (without registry prefix).
        version: Image version/tag.
        context_path: Docker build context path.

    Returns:
        Dict with build result (success, image_tag, error).
    """
    spec = ServiceSpec(name=service_name, image=image, version=version, provider="azure")
    adapters = get_deployment_adapters("azure")
    result = adapters.build.build(spec, context_path=context_path)
    return {
        "success": result.success,
        "image_tag": result.image_tag,
        "build_id": result.build_id,
        "error": result.error,
    }
