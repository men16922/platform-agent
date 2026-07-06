"""Build container image tool for ADK deployer agent (GCP)."""

from __future__ import annotations

from src.agents.adapters.deployment import ServiceSpec, get_deployment_adapters


def gcp_build_image(
    service_name: str,
    image: str,
    version: str,
    context_path: str = ".",
) -> dict:
    """Build a container image using Google Cloud Build.

    Args:
        service_name: Name of the service to build.
        image: Image name (without registry prefix).
        version: Image version/tag.
        context_path: Docker build context path.

    Returns:
        Dict with build result (success, image_tag, error).
    """
    spec = ServiceSpec(name=service_name, image=image, version=version, provider="gcp")
    adapters = get_deployment_adapters("gcp")
    result = adapters.build.build(spec, context_path=context_path)
    return {
        "success": result.success,
        "image_tag": result.image_tag,
        "build_id": result.build_id,
        "error": result.error,
    }
