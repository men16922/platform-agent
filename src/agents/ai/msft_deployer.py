"""
MS Agent Framework Deployer Agent — Microsoft Agent Framework-based deployment pipeline for Azure.

Uses Microsoft Agent Framework (unified Semantic Kernel + AutoGen) to create an LLM agent
that deploys container services to AKS via ACR Tasks + ACR + kubectl.

Usage:
    from src.agents.ai.msft_deployer import create_msft_deployer_agent

    agent = create_msft_deployer_agent()
    result = await agent.run("Deploy orders-api v1.4.2 to AKS with 3 replicas")
"""

from __future__ import annotations

from typing import Any

from agent_framework import tool
from agent_framework.azure import AzureOpenAIResponsesClient

from src.agents.ai.tools.azure_build import azure_build_image
from src.agents.ai.tools.azure_push import azure_push_image
from src.agents.ai.tools.azure_deploy import (
    azure_deploy_to_cluster,
    azure_rollback_deployment,
    azure_validate_deployment,
)


MSFT_DEPLOYER_INSTRUCTIONS = """\
You are an Azure Platform Deployment Agent. Your job is to autonomously deploy container services
to Azure Kubernetes Service (AKS) using the available tools.

## Workflow

When asked to deploy a service, follow this exact sequence:

1. **Build** — Use `azure_build_image` to build the container image via ACR Tasks.
2. **Push** — Use `azure_push_image` to push the image to Azure Container Registry.
3. **Deploy** — Use `azure_deploy_to_cluster` to apply the deployment to AKS.
4. **Validate** — Use `azure_validate_deployment` to verify the deployment is healthy.
5. **Rollback** (only if needed) — If validation fails, use `azure_rollback_deployment`.

## Rules

- Always follow the Build → Push → Deploy → Validate sequence.
- If any step fails, report the error clearly and stop (do NOT proceed to the next step).
- If validation fails after deploy, automatically rollback and report the failure.
- Never skip the validation step.
- Report a clear summary at the end: what was deployed, where, and whether it succeeded.

## Infrastructure

- Build: ACR Tasks (az acr build)
- Registry: Azure Container Registry (REGISTRY.azurecr.io)
- Cluster: Azure Kubernetes Service (kubectl apply)
- Region: Configured via AZURE_REGION env var (default: koreacentral)
- Resource Group: Configured via AZURE_RESOURCE_GROUP env var

## Safety

- You CANNOT delete namespaces, clusters, or infrastructure.
- You can only deploy, validate, and rollback deployments.
- If unsure about any action, ask for confirmation rather than proceeding.
"""


# Wrap plain functions with @tool decorator for MS Agent Framework
@tool(approval_mode="never_require")
def build_image_azure(
    service_name: str,
    image: str,
    version: str,
    context_path: str = ".",
) -> dict:
    """Build a container image using Azure Container Registry Tasks."""
    return azure_build_image(service_name, image, version, context_path)


@tool(approval_mode="never_require")
def push_image_azure(
    image: str,
    version: str,
) -> dict:
    """Push a built container image to Azure Container Registry."""
    return azure_push_image(image, version)


@tool(approval_mode="never_require")
def deploy_to_aks(
    service_name: str,
    image: str,
    version: str,
    image_uri: str,
    replicas: int = 1,
    namespace: str = "default",
    health_path: str = "/healthz",
) -> dict:
    """Deploy a service to Azure Kubernetes Service (AKS)."""
    return azure_deploy_to_cluster(
        service_name, image, version, image_uri, replicas, namespace, health_path
    )


@tool(approval_mode="never_require")
def validate_aks_deployment(
    service_name: str,
    namespace: str = "default",
) -> dict:
    """Validate a deployed service on AKS by checking rollout status."""
    return azure_validate_deployment(service_name, namespace)


@tool(approval_mode="always_require")
def rollback_aks_deployment(
    service_name: str,
    namespace: str = "default",
) -> dict:
    """Rollback a deployment on AKS to its previous version. Requires approval."""
    return azure_rollback_deployment(service_name, namespace)


# All Azure tools with @tool decorator applied
AZURE_DEPLOY_TOOLS = [
    build_image_azure,
    push_image_azure,
    deploy_to_aks,
    validate_aks_deployment,
    rollback_aks_deployment,
]


def create_msft_deployer_agent(
    endpoint: str | None = None,
    deployment_name: str | None = None,
    credential: Any | None = None,
    **kwargs: Any,
) -> Any:
    """Create a Microsoft Agent Framework deployer agent configured for Azure.

    Args:
        endpoint: Azure AI project endpoint. Falls back to AZURE_AI_PROJECT_ENDPOINT env var.
        deployment_name: Azure OpenAI deployment name. Falls back to AZURE_OPENAI_RESPONSES_DEPLOYMENT_NAME env var.
        credential: Azure credential. Defaults to AzureCliCredential.
        **kwargs: Additional agent constructor arguments.

    Returns:
        Configured MS Agent Framework Agent instance.
    """
    import os

    if credential is None:
        from azure.identity import AzureCliCredential
        credential = AzureCliCredential()

    endpoint = endpoint or os.environ.get("AZURE_AI_PROJECT_ENDPOINT", "")
    deployment_name = deployment_name or os.environ.get(
        "AZURE_OPENAI_RESPONSES_DEPLOYMENT_NAME", "gpt-5-4"
    )

    client = AzureOpenAIResponsesClient(
        project_endpoint=endpoint,
        deployment_name=deployment_name,
        credential=credential,
    )

    agent = client.as_agent(
        name="AzureDeployer",
        instructions=MSFT_DEPLOYER_INSTRUCTIONS,
        tools=AZURE_DEPLOY_TOOLS,
        **kwargs,
    )

    return agent
