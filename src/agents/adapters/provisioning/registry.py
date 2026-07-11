"""Provisioning adapter registry — resolve a per-environment provisioning adapter."""

from __future__ import annotations

from src.agents.adapters.provisioning.base import ProvisionAdapter
from src.agents.adapters.provisioning.onprem import OnPremProvisionAdapter


def get_provisioning_adapter(provider: str) -> ProvisionAdapter:
    if provider == "onprem":
        return OnPremProvisionAdapter()
    # AWS/GCP/Azure provisioning (Terraform / CDK / native) — roadmap.
    raise ValueError(f"provisioning not implemented for provider: {provider}")


def supported_provisioning_providers() -> list[str]:
    return ["onprem"]
