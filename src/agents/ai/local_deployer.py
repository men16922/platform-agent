"""Pydantic AI deployer for the on-prem / local-LLM path.

Unlike the Strands deployer (AWS/Bedrock-native, see ``strands_deployer``), this
agent targets a **local MLX-LM server** exposing an OpenAI-compatible endpoint
(Qwen2.5/3-Coder). It has NO AWS or Strands dependency — the on-prem story runs
fully offline on the operator's own hardware.

Framework split:
    aws            -> Strands + Bedrock Claude   (strands_deployer)
    gcp            -> ADK + Vertex Gemini        (adk_deployer)
    azure          -> MSFT SDK + Azure OpenAI    (msft_deployer)
    onprem / local -> Pydantic AI + MLX Qwen     (this module)

MLX-LM does not always emit standard OpenAI ``tool_calls`` for Qwen (it may emit
``<function=...>`` markup), so this path talks to the ``mlx_qwen_tool_proxy``
normalizer, which honors the non-streaming request Pydantic AI's ``run_sync``
issues. Point ``ONPREM_LLM_ENDPOINT`` at the proxy (default ``:18081``), which in
turn fronts the raw MLX-LM server (default ``:8080``).

Usage:
    from src.agents.ai.local_deployer import create_local_deployer

    agent = create_local_deployer(provider="onprem")
    result = agent.run_sync("Deploy orders-api v1.4.2 to the local cluster")
    print(result.output)
"""

from __future__ import annotations

import os
from typing import Any

from pydantic_ai import Agent
from pydantic_ai.models import Model
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from src.agents.adapters.deployment import ServiceSpec, get_deployment_adapters


DEPLOYER_SYSTEM_PROMPT = """\
You are an on-premise Kubernetes **operations agent** running fully offline via a
local LLM. Answer questions and fulfill requests using the available tools —
deployment is one capability among several.

## Tools

**Investigate (read-only, use freely):**
- `list_pods`, `get_logs`, `describe_deployment`, `rollout_status`, `list_namespaces`

**Provision (infrastructure / IaC, mutating — only when explicitly asked):**
- `provision_cluster` (Terraform kind / Ansible k3s), `teardown_cluster`

**Deploy (mutating):**
- `build_image` -> `push_image` -> `deploy_to_cluster` -> `validate_deployment`

**Recover (mutating):**
- `rollback_deployment`

## How to work

- **Investigate before acting.** For a diagnostic or "why / what / show me"
  question, use the read-only tools and summarize findings — do NOT deploy or
  change anything unless explicitly asked.
- **For a "set up / provision a cluster" request**, use `provision_cluster`
  first; then deploy only if the user also asked to deploy.
- **For a deployment request**, follow build -> push -> deploy -> validate in
  order, passing the `image_uri` returned by push into the deploy step. If
  validation fails, roll back and report.
- Prefer the smallest set of tool calls that answers the request.
- Be concise. End with a clear summary of what you did and what you found.

## Safety

- You CANNOT delete namespaces, clusters, or infrastructure.
- Read-only tools are always safe; mutating tools change cluster state — only use
  them when the request calls for it.
"""


# --- Tools ---------------------------------------------------------------
# Plain functions (no framework decorator) so the local path stays free of any
# Strands import. Pydantic AI infers each tool schema from the type hints and
# the Google-style docstring. Logic mirrors src/agents/ai/tools/* but calls the
# provider-neutral deployment adapters directly.


def build_image(
    service_name: str,
    image: str,
    version: str,
    provider: str = "onprem",
    context_path: str = ".",
) -> dict:
    """Build a container image for a service.

    Args:
        service_name: Name of the service to build.
        image: Image name (without registry prefix).
        version: Image version/tag.
        provider: Deployment provider (onprem, aws, gcp, azure).
        context_path: Docker build context path.

    Returns:
        Dict with build result (success, image_tag, build_id, error).
    """
    spec = ServiceSpec(name=service_name, image=image, version=version, provider=provider)
    adapters = get_deployment_adapters(provider)
    result = adapters.build.build(spec, context_path=context_path)
    return {
        "success": result.success,
        "image_tag": result.image_tag,
        "build_id": result.build_id,
        "error": result.error,
    }


def push_image(image: str, version: str, provider: str = "onprem") -> dict:
    """Push a built container image to the provider's registry.

    Args:
        image: Image name (without registry prefix).
        version: Image version/tag.
        provider: Deployment provider (onprem, aws, gcp, azure).

    Returns:
        Dict with push result (success, image_uri, digest, error).
    """
    adapters = get_deployment_adapters(provider)
    result = adapters.registry.push(image, version)
    return {
        "success": result.success,
        "image_uri": result.image_uri,
        "digest": result.digest,
        "error": result.error,
    }


def deploy_to_cluster(
    service_name: str,
    image: str,
    version: str,
    image_uri: str,
    provider: str = "onprem",
    replicas: int = 1,
    namespace: str = "default",
    health_path: str = "/healthz",
    ports: list[int] | None = None,
) -> dict:
    """Deploy a service to the target cluster.

    Args:
        service_name: Name of the service/deployment.
        image: Image name.
        version: Image version.
        image_uri: Full image URI (from the push step).
        provider: Deployment provider (onprem, aws, gcp, azure).
        replicas: Number of replicas.
        namespace: Kubernetes namespace.
        health_path: Health check endpoint path.
        ports: Container ports (default [8080]).

    Returns:
        Dict with deploy result (status, deployment_id, endpoint, error).
    """
    spec = ServiceSpec(
        name=service_name,
        image=image,
        version=version,
        provider=provider,
        replicas=replicas,
        namespace=namespace,
        health_path=health_path,
        ports=ports or [8080],
    )
    adapters = get_deployment_adapters(provider)
    result = adapters.cluster.deploy(spec, image_uri)
    return {
        "status": result.status.value,
        "deployment_id": result.deployment_id,
        "namespace": result.namespace,
        "replicas_desired": result.replicas_desired,
        "endpoint": result.endpoint,
        "error": result.error,
    }


def validate_deployment(
    service_name: str,
    provider: str = "onprem",
    namespace: str = "default",
) -> dict:
    """Validate a deployed service by checking rollout status and readiness.

    Args:
        service_name: Name of the deployment to validate.
        provider: Deployment provider (onprem, aws, gcp, azure).
        namespace: Kubernetes namespace.

    Returns:
        Dict with validation result (healthy, checks_passed, checks_total, error).
    """
    spec = ServiceSpec(name=service_name, image=service_name, version="", provider=provider, namespace=namespace)
    adapters = get_deployment_adapters(provider)
    result = adapters.cluster.validate(spec)
    return {
        "healthy": result.healthy,
        "checks_passed": result.checks_passed,
        "checks_total": result.checks_total,
        "details": result.details,
        "error": result.error,
    }


def rollback_deployment(
    service_name: str,
    provider: str = "onprem",
    namespace: str = "default",
) -> dict:
    """Rollback a deployment to its previous version.

    Args:
        service_name: Name of the deployment to rollback.
        provider: Deployment provider (onprem, aws, gcp, azure).
        namespace: Kubernetes namespace.

    Returns:
        Dict with rollback result (success, rolled_back_to, error).
    """
    spec = ServiceSpec(name=service_name, image=service_name, version="", provider=provider, namespace=namespace)
    adapters = get_deployment_adapters(provider)
    result = adapters.cluster.rollback(spec)
    return {
        "success": result.success,
        "rolled_back_to": result.rolled_back_to,
        "error": result.error,
    }


LOCAL_DEPLOY_TOOLS = [build_image, push_image, deploy_to_cluster, validate_deployment, rollback_deployment]

# Full platform agent tool set = provision (IaC) + deploy/recover + read-only diagnostics.
from src.agents.ai.ops_tools import OPS_TOOLS  # noqa: E402
from src.agents.ai.provision_tools import PROVISION_TOOLS  # noqa: E402

ALL_OPS_TOOLS = PROVISION_TOOLS + LOCAL_DEPLOY_TOOLS + OPS_TOOLS


def create_local_deployer(
    provider: str = "onprem",
    model: Model | str | None = None,
    **kwargs: Any,
) -> Agent:
    """Create a Pydantic AI deployer agent for the local-LLM path.

    Args:
        provider: Target deployment provider (default "onprem").
        model: A Pydantic AI ``Model`` (or model-name string) override. If None,
            an ``OpenAIChatModel`` pointing at the local MLX proxy is built from
            the ``ONPREM_LLM_*`` environment variables. Pass a ``TestModel`` here
            to drive the agent without a live LLM.
        **kwargs: Additional ``Agent`` constructor arguments.

    Returns:
        Configured Pydantic AI ``Agent`` instance.
    """
    system_prompt = DEPLOYER_SYSTEM_PROMPT + f"\n\nCurrent provider: {provider}\n"

    if model is None:
        base_url = os.getenv("ONPREM_LLM_ENDPOINT", "http://localhost:18081/v1")
        model_id = os.getenv("ONPREM_LLM_MODEL", "mlx-community/Qwen2.5-Coder-32B-Instruct-8bit")
        api_key = os.getenv("ONPREM_LLM_API_KEY", "mlx-local")
        model = OpenAIChatModel(model_id, provider=OpenAIProvider(base_url=base_url, api_key=api_key))

    return Agent(model, system_prompt=system_prompt, tools=ALL_OPS_TOOLS, **kwargs)
