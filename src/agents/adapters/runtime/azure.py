"""Azure agent-runtime hosting adapter — AI Foundry Agents, approval-gated.

Uses the ``azure-ai-projects`` SDK (``AIProjectClient.agents``). Mirrors the AWS
adapter's plan-first / apply-after-approval contract:

- unapproved ``host_agent`` runs a read-only preflight (``agents.list_agents``)
  — verifies the Foundry project endpoint + credentials; creates nothing
- ``approved=True`` runs the real ``agents.create_agent`` (needs a model
  deployment name in ``spec.extra['model']`` + optional instructions)
- ``teardown_agent`` requires explicit approval and deletes by agent id
  (resolved from the agent name when not supplied)

Config: ``AZURE_AI_PROJECT_ENDPOINT`` (Foundry project endpoint) or
``spec.extra['endpoint']``; credentials via ``DefaultAzureCredential`` (az login).
"""

from __future__ import annotations

import os

from src.agents.adapters.runtime.base import RuntimeResult, RuntimeSpec

_ENDPOINT_ENV = "AZURE_AI_PROJECT_ENDPOINT"


def _client(endpoint: str):
    from azure.ai.projects import AIProjectClient
    from azure.identity import DefaultAzureCredential

    return AIProjectClient(endpoint=endpoint, credential=DefaultAzureCredential())


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
                existing = list(client.agents.list_agents())
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
            created = client.agents.create_agent(
                model=model,
                name=spec.agent_name,
                instructions=spec.extra.get("instructions", ""),
            )
        except Exception as exc:
            return RuntimeResult(False, spec.agent_name, error=_err(exc))
        return RuntimeResult(
            success=True,
            agent_name=spec.agent_name,
            runtime_id=getattr(created, "id", None),
            status="DEPLOYED",
            output="foundry agent created",
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

        agent_id = spec.runtime_id or self._resolve(client, spec.agent_name)
        if not agent_id:
            return RuntimeResult(False, spec.agent_name, error=f"no agent found for name '{spec.agent_name}'")
        try:
            client.agents.delete_agent(agent_id)
        except Exception as exc:
            return RuntimeResult(False, spec.agent_name, runtime_id=agent_id, error=_err(exc))
        return RuntimeResult(
            success=True,
            agent_name=spec.agent_name,
            runtime_id=agent_id,
            status="DELETING",
            output="foundry agent delete requested",
        )

    def _resolve(self, client, agent_name: str) -> str:
        try:
            for a in client.agents.list_agents():
                if getattr(a, "name", None) == agent_name:
                    return getattr(a, "id", "") or ""
        except Exception:
            return ""
        return ""
