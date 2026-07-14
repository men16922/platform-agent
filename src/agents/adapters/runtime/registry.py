"""Agent-runtime hosting registry — resolve a per-provider hosting adapter."""

from __future__ import annotations

from src.agents.adapters.runtime.aws import AgentCoreRuntimeAdapter
from src.agents.adapters.runtime.azure import FoundryRuntimeAdapter
from src.agents.adapters.runtime.base import RuntimeHostingAdapter
from src.agents.adapters.runtime.gcp import AgentEngineRuntimeAdapter


def get_runtime_adapter(provider: str) -> RuntimeHostingAdapter:
    if provider == "aws":
        return AgentCoreRuntimeAdapter()
    if provider == "gcp":
        return AgentEngineRuntimeAdapter()
    if provider == "azure":
        return FoundryRuntimeAdapter()
    raise ValueError(f"agent-runtime hosting not implemented for provider: {provider}")


def supported_runtime_providers() -> list[str]:
    return ["aws", "gcp", "azure"]
