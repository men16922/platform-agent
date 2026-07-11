"""Provisioning adapters — cloud-neutral cluster/infra provisioning abstraction.

Mirrors the deployment adapters, but for the ① Provision role (Day-0/1 IaC):
stand up the platform (cluster + registry) before apps are deployed onto it.
Capability -> per-environment adapter. On-prem = Terraform (infra) + Ansible
(node config).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass
class ProvisionSpec:
    cluster_name: str = "platform-agent"
    provider: str = "onprem"
    # On-prem modes: "kind" (Terraform + Docker, no VM) | "k3s" (Ansible + VM).
    mode: str = "kind"
    registry_port: int = 5001
    approved: bool = False
    stack_name: str = "IncidentAgentStack"
    region: str | None = None


@dataclass
class ProvisionResult:
    success: bool
    cluster_name: str
    context: str | None = None
    output: str = ""
    error: str | None = None


class ProvisionAdapter(Protocol):
    def provision_cluster(self, spec: ProvisionSpec) -> ProvisionResult: ...

    def teardown_cluster(self, spec: ProvisionSpec) -> ProvisionResult: ...
