"""
Deployment adapters — multi-cloud container deployment abstraction.

Usage:
    from src.agents.adapters.deployment import get_deployment_adapters

    adapters = get_deployment_adapters("local")
    build_result = adapters.build.build(spec)
    push_result = adapters.registry.push(image, tag)
    deploy_result = adapters.cluster.deploy(spec, push_result.image_uri)
"""

from src.agents.adapters.deployment.base import (
    BuildAdapter,
    BuildResult,
    ClusterAdapter,
    DeploymentAdapters,
    DeployResult,
    DeployStatus,
    PushResult,
    RegistryAdapter,
    RollbackResult,
    ServiceSpec,
    ValidationResult,
)
from src.agents.adapters.deployment.registry import get_deployment_adapters, supported_deployment_providers

__all__ = [
    "BuildAdapter",
    "BuildResult",
    "ClusterAdapter",
    "DeploymentAdapters",
    "DeployResult",
    "DeployStatus",
    "PushResult",
    "RegistryAdapter",
    "RollbackResult",
    "ServiceSpec",
    "ValidationResult",
    "get_deployment_adapters",
    "supported_deployment_providers",
]
