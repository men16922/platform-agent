"""
ADK Deployer Agent — Google ADK-based autonomous deployment pipeline for GCP.

Uses Google Agent Development Kit (ADK) to create an LLM agent that deploys
container services to GKE via Cloud Build + Artifact Registry.

Authentication:
    Vertex AI backend (recommended): set GOOGLE_CLOUD_PROJECT + GOOGLE_CLOUD_LOCATION,
    then `gcloud auth application-default login`. No API key needed.

    API key backend: set GOOGLE_API_KEY (Google AI Studio).

Usage:
    from src.agents.ai.adk_deployer import create_adk_deployer_agent, root_agent

    # Programmatic usage
    agent = create_adk_deployer_agent()

    # ADK CLI usage (adk run / adk web): uses root_agent module-level export
"""

from __future__ import annotations

from typing import Any

from google.adk.agents import Agent as AdkAgent

from src.agents.ai.tools.gcp_build import gcp_build_image
from src.agents.ai.tools.gcp_push import gcp_push_image
from src.agents.ai.tools.gcp_deploy import (
    gcp_deploy_to_cluster,
    gcp_rollback_deployment,
    gcp_validate_deployment,
)


ADK_DEPLOYER_SYSTEM_PROMPT = """\
You are a GCP Platform Deployment Agent. Your job is to autonomously deploy container services
to Google Kubernetes Engine (GKE) using the available tools.

## Workflow

When asked to deploy a service, follow this exact sequence:

1. **Build** — Use `gcp_build_image` to build the container image via Cloud Build.
2. **Push** — Use `gcp_push_image` to push the image to Artifact Registry.
3. **Deploy** — Use `gcp_deploy_to_cluster` to apply the deployment to GKE.
4. **Validate** — Use `gcp_validate_deployment` to verify the deployment is healthy.
5. **Rollback** (only if needed) — If validation fails, use `gcp_rollback_deployment`.

## Rules

- Always follow the Build → Push → Deploy → Validate sequence.
- If any step fails, report the error clearly and stop (do NOT proceed to the next step).
- If validation fails after deploy, automatically rollback and report the failure.
- Never skip the validation step.
- Report a clear summary at the end: what was deployed, where, and whether it succeeded.

## Infrastructure

- Build: Google Cloud Build (gcloud builds submit)
- Registry: Google Artifact Registry (REGION-docker.pkg.dev)
- Cluster: Google Kubernetes Engine (kubectl apply)
- Region: Configured via GCP_REGION env var (default: asia-northeast3)
- Project: Configured via GCP_PROJECT env var

## Safety

- You CANNOT delete namespaces, clusters, or infrastructure.
- You can only deploy, validate, and rollback deployments.
- If unsure about any action, ask for confirmation rather than proceeding.
"""

# All GCP tools as plain functions (ADK uses plain functions, not decorators)
GCP_DEPLOY_TOOLS = [
    gcp_build_image,
    gcp_push_image,
    gcp_deploy_to_cluster,
    gcp_validate_deployment,
    gcp_rollback_deployment,
]


def create_adk_deployer_agent(
    model: str | None = None,
    **kwargs: Any,
) -> AdkAgent:
    """Create an ADK deployer agent configured for GCP.

    Args:
        model: Gemini model ID. Defaults to GEMINI_MODEL env var or gemini-2.5-flash.
        **kwargs: Additional AdkAgent constructor arguments.

    Returns:
        Configured ADK Agent instance.
    """
    import os
    if model is None:
        model = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash")
    return AdkAgent(
        model=model,
        name="gcp_deployer",
        description="Deploys container services to GKE via Cloud Build and Artifact Registry.",
        instruction=ADK_DEPLOYER_SYSTEM_PROMPT,
        tools=GCP_DEPLOY_TOOLS,
        **kwargs,
    )


# Module-level export for `adk run` / `adk web` CLI usage
root_agent = create_adk_deployer_agent()
