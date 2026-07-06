"""Push container image to ACR tool for MS Agent Framework deployer (Azure)."""

from __future__ import annotations

from src.agents.adapters.deployment import get_deployment_adapters


def azure_push_image(
    image: str,
    version: str,
) -> dict:
    """Push a built container image to Azure Container Registry.

    Args:
        image: Image name (without registry prefix).
        version: Image version/tag.

    Returns:
        Dict with push result (success, image_uri, error).
    """
    adapters = get_deployment_adapters("azure")
    result = adapters.registry.push(image, version)
    return {
        "success": result.success,
        "image_uri": result.image_uri,
        "digest": result.digest,
        "error": result.error,
    }
