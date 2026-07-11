"""Provisioning adapter registry — resolve a per-environment provisioning adapter."""

from __future__ import annotations

from src.agents.adapters.provisioning.base import ProvisionAdapter
from src.agents.adapters.provisioning.onprem import OnPremProvisionAdapter
from src.agents.adapters.provisioning.aws import AwsProvisionAdapter


def get_provisioning_adapter(provider: str) -> ProvisionAdapter:
    if provider == "onprem":
        return OnPremProvisionAdapter()
    if provider == "aws":
        return AwsProvisionAdapter()
    raise ValueError(f"provisioning not implemented for provider: {provider}")


def supported_provisioning_providers() -> list[str]:
    return ["onprem", "aws"]
