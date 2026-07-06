"""Push container image to Artifact Registry tool for ADK deployer agent (GCP)."""

from __future__ import annotations

from src.agents.adapters.deployment import get_deployment_adapters


def gcp_push_image(
    image: str,
    version: str,
) -> dict:
    """Push a built container image to Google Artifact Registry.

    Args:
        image: Image name (without registry prefix).
        version: Image version/tag.

    Returns:
        Dict with push result (success, image_uri, error).
    """
    adapters = get_deployment_adapters("gcp")
    result = adapters.registry.push(image, version)
    return {
        "success": result.success,
        "image_uri": result.image_uri,
        "digest": result.digest,
        "error": result.error,
    }
