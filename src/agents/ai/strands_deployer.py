"""
Strands Deployer Agent — AI-driven autonomous deployment pipeline.

The agent receives a ServiceSpec (or natural language describing one) and
autonomously executes: Build → Push → Deploy → Validate → (Rollback if needed).

Usage:
    from src.agents.ai.strands_deployer import create_deployer_agent

    agent = create_deployer_agent(provider="onprem")
    result = agent("Deploy orders-api v1.4.2 to the on-prem cluster with 3 replicas")
"""

from __future__ import annotations

from typing import Any

from strands import Agent

from src.agents.ai.tools import ALL_DEPLOY_TOOLS


DEPLOYER_SYSTEM_PROMPT = """\
You are a Platform Deployment Agent. Your job is to autonomously deploy container services
to Kubernetes clusters using the available tools.

## Workflow

When asked to deploy a service, follow this exact sequence:

1. **Build** — Use `build_image` to build the container image from source.
2. **Push** — Use `push_image` to push the image to the registry.
3. **Deploy** — Use `deploy_to_cluster` to apply the deployment to the cluster.
4. **Validate** — Use `validate_deployment` to verify the deployment is healthy.
5. **Rollback** (only if needed) — If validation fails, use `rollback_deployment`.

## Rules

- Always follow the Build → Push → Deploy → Validate sequence.
- If any step fails, report the error clearly and stop (do NOT proceed to the next step).
- If validation fails after deploy, automatically rollback and report the failure.
- Never skip the validation step.
- Use the provider specified by the user (onprem, aws, gcp, azure). Default is "onprem".
- Report a clear summary at the end: what was deployed, where, and whether it succeeded.

## Available Providers

- `onprem` — On-premise Kubernetes cluster with private registry (via MCP Gateway)
- `aws` — EKS + ECR + CodeBuild
- `gcp` — GKE + Artifact Registry + Cloud Build
- `azure` — AKS + ACR + ACR Tasks

## Safety

- You CANNOT delete namespaces, clusters, or infrastructure.
- You can only deploy, validate, and rollback deployments.
- If unsure about any action, ask for confirmation rather than proceeding.
"""


def create_deployer_agent(
    provider: str = "onprem",
    model: str | None = None,
    **kwargs: Any,
) -> Agent:
    """Create a Strands deployer agent configured for the given provider.

    Args:
        provider: Target deployment provider (onprem, aws, gcp, azure).
        model: Model ID override. Defaults to Bedrock Claude if None.
        **kwargs: Additional Agent constructor arguments.

    Returns:
        Configured Strands Agent instance.
    """
    system_prompt = DEPLOYER_SYSTEM_PROMPT + f"\n\nCurrent provider: {provider}\n"

    agent_kwargs: dict[str, Any] = {
        "system_prompt": system_prompt,
        "tools": ALL_DEPLOY_TOOLS,
        **kwargs,
    }

    if model:
        agent_kwargs["model"] = model

    return Agent(**agent_kwargs)
