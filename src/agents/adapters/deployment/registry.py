"""
Deployment adapter factory — select provider-specific adapters by name.
"""

from __future__ import annotations

from src.agents.adapters.deployment.base import DeploymentAdapters


def get_deployment_adapters(provider: str) -> DeploymentAdapters:
    """Return a DeploymentAdapters bundle for the given provider."""
    if provider in ("onprem", "local"):
        from src.agents.adapters.deployment.onprem import (
            OnPremBuildAdapter,
            OnPremClusterAdapter,
            OnPremRegistryAdapter,
        )
        return DeploymentAdapters(
            provider="onprem",
            build=OnPremBuildAdapter(),
            registry=OnPremRegistryAdapter(),
            cluster=OnPremClusterAdapter(),
        )
    elif provider == "aws":
        from src.agents.adapters.deployment.aws import (
            AwsBuildAdapter,
            AwsClusterAdapter,
            AwsRegistryAdapter,
        )
        return DeploymentAdapters(
            provider="aws",
            build=AwsBuildAdapter(),
            registry=AwsRegistryAdapter(),
            cluster=AwsClusterAdapter(),
        )
    elif provider == "gcp":
        from src.agents.adapters.deployment.gcp import (
            GcpBuildAdapter,
            GcpClusterAdapter,
            GcpRegistryAdapter,
        )
        return DeploymentAdapters(
            provider="gcp",
            build=GcpBuildAdapter(),
            registry=GcpRegistryAdapter(),
            cluster=GcpClusterAdapter(),
        )
    elif provider == "azure":
        from src.agents.adapters.deployment.azure import (
            AzureBuildAdapter,
            AzureClusterAdapter,
            AzureRegistryAdapter,
        )
        return DeploymentAdapters(
            provider="azure",
            build=AzureBuildAdapter(),
            registry=AzureRegistryAdapter(),
            cluster=AzureClusterAdapter(),
        )
    else:
        raise ValueError(f"Unsupported deployment provider: {provider}. Supported: {supported_deployment_providers()}")


def supported_deployment_providers() -> list[str]:
    """Return list of supported deployment providers."""
    return ["onprem", "aws", "gcp", "azure"]
