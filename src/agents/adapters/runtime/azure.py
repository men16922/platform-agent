"""Azure agent-runtime hosting adapter — AI Foundry Agents (v2), approval-gated.

Uses the ``azure-ai-projects`` v2 API (``AIProjectClient.agents``): agents are
named, versioned resources created from a declarative definition. Mirrors the AWS
adapter's plan-first / apply-after-approval contract:

- unapproved ``host_agent`` runs a read-only preflight (``agents.list``) —
  verifies the Foundry project endpoint + credentials; creates nothing
- ``approved=True`` runs the real ``agents.create_version`` with a
  ``PromptAgentDefinition`` (needs a model deployment name in
  ``spec.extra['model']`` + optional instructions)
- ``teardown_agent`` requires explicit approval and deletes the named agent

Auth: the Foundry data plane requires Entra ID (``DefaultAzureCredential`` via
``az login``) with a data-plane role (e.g. "Cognitive Services User") on the
account — subscription Owner alone is control-plane only. Config:
``AZURE_AI_PROJECT_ENDPOINT`` (project endpoint) or ``spec.extra['endpoint']``.
"""

from __future__ import annotations

import os

from src.agents.adapters.runtime.base import RuntimeResult, RuntimeSpec

_ENDPOINT_ENV = "AZURE_AI_PROJECT_ENDPOINT"


def _client(endpoint: str):
    from azure.ai.projects import AIProjectClient
    from azure.identity import DefaultAzureCredential

    return AIProjectClient(endpoint=endpoint, credential=DefaultAzureCredential())


def _prompt_definition(model: str, instructions: str):
    from azure.ai.projects.models import PromptAgentDefinition

    return PromptAgentDefinition(model=model, instructions=instructions or None)


def _err(exc: Exception) -> str:
    return f"{type(exc).__name__}: {exc}"[:400]


class FoundryRuntimeAdapter:
    def _endpoint(self, spec: RuntimeSpec) -> str:
        return spec.extra.get("endpoint") or os.getenv(_ENDPOINT_ENV, "")

    def host_agent(self, spec: RuntimeSpec) -> RuntimeResult:
        endpoint = self._endpoint(spec)
        if not endpoint:
            return RuntimeResult(False, spec.agent_name, error=f"{_ENDPOINT_ENV} (Foundry project endpoint) not set")
        try:
            client = _client(endpoint)
        except Exception as exc:
            return RuntimeResult(False, spec.agent_name, error=_err(exc))

        if not spec.approved:
            try:
                existing = list(client.agents.list())
            except Exception as exc:
                return RuntimeResult(False, spec.agent_name, error=_err(exc))
            names = [getattr(a, "name", None) for a in existing]
            return RuntimeResult(
                success=True,
                agent_name=spec.agent_name,
                status="PREFLIGHT",
                output=f"{len(names)} existing agent(s): {names}",
            )

        model = spec.extra.get("model")
        if not model:
            return RuntimeResult(False, spec.agent_name, error="extra['model'] (deployment name) required to host")
        try:
            definition = _prompt_definition(model, spec.extra.get("instructions", ""))
            created = client.agents.create_version(agent_name=spec.agent_name, definition=definition)
        except Exception as exc:
            return RuntimeResult(False, spec.agent_name, error=_err(exc))
        version = getattr(created, "version", None)
        return RuntimeResult(
            success=True,
            agent_name=spec.agent_name,
            runtime_id=getattr(created, "name", None) or spec.agent_name,
            status=f"v{version}" if version else "DEPLOYED",
            output="foundry agent version created",
        )

    def teardown_agent(self, spec: RuntimeSpec) -> RuntimeResult:
        if not spec.approved:
            return RuntimeResult(False, spec.agent_name, error="Foundry teardown requires explicit approved=True")
        endpoint = self._endpoint(spec)
        if not endpoint:
            return RuntimeResult(False, spec.agent_name, error=f"{_ENDPOINT_ENV} (Foundry project endpoint) not set")
        try:
            client = _client(endpoint)
        except Exception as exc:
            return RuntimeResult(False, spec.agent_name, error=_err(exc))

        # v2 agents are identified by name; delete removes the whole agent.
        name = spec.runtime_id or spec.agent_name
        try:
            client.agents.delete(name)
        except Exception as exc:
            return RuntimeResult(False, spec.agent_name, runtime_id=name, error=_err(exc))
        return RuntimeResult(
            success=True,
            agent_name=spec.agent_name,
            runtime_id=name,
            status="DELETING",
            output="foundry agent delete requested",
        )
