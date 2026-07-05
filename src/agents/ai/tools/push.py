"""Push container image to registry tool for Strands deployer agent."""

from __future__ import annotations

from strands.tools import tool

from src.agents.adapters.deployment import get_deployment_adapters


@tool
def push_image(
    image: str,
    version: str,
    provider: str = "local",
) -> dict:
    """Push a built container image to the provider's registry.

    Args:
        image: Image name (without registry prefix).
        version: Image version/tag.
        provider: Deployment provider (local, aws, gcp, azure).

    Returns:
        Dict with push result (success, image_uri, error).
    """
    adapters = get_deployment_adapters(provider)
    result = adapters.registry.push(image, version)
    return {
        "success": result.success,
        "image_uri": result.image_uri,
        "digest": result.digest,
        "error": result.error,
    }
