"""Provisioning tools for the platform agent (① Provision role).

Mutating, infrastructure-level: stand up / tear down an on-prem Kubernetes
cluster via IaC (Terraform for kind, Ansible for k3s). Only invoke when the user
explicitly asks to provision or tear down a cluster.
"""

from __future__ import annotations

from src.agents.adapters.provisioning import ProvisionSpec, get_provisioning_adapter


def provision_cluster(cluster_name: str = "platform-agent", mode: str = "kind", provider: str = "onprem") -> dict:
    """Provision an on-prem Kubernetes cluster (infrastructure, IaC). MUTATING.

    Args:
        cluster_name: Name of the cluster to create.
        mode: "kind" (Terraform + Docker, no VM) or "k3s" (Ansible + VM/bare-metal).
        provider: Target environment (onprem).

    Returns:
        Dict with provisioning result (success, cluster, context, error).
    """
    adapter = get_provisioning_adapter(provider)
    result = adapter.provision_cluster(ProvisionSpec(cluster_name=cluster_name, provider=provider, mode=mode))
    return {
        "success": result.success,
        "cluster": result.cluster_name,
        "context": result.context,
        "error": result.error,
        "output": result.output[-2000:],
    }


def teardown_cluster(cluster_name: str = "platform-agent", mode: str = "kind", provider: str = "onprem") -> dict:
    """Tear down a provisioned on-prem cluster (infrastructure, IaC). MUTATING.

    Args:
        cluster_name: Name of the cluster to destroy.
        mode: "kind" (Terraform destroy) or "k3s".
        provider: Target environment (onprem).

    Returns:
        Dict with teardown result (success, error).
    """
    adapter = get_provisioning_adapter(provider)
    result = adapter.teardown_cluster(ProvisionSpec(cluster_name=cluster_name, provider=provider, mode=mode))
    return {"success": result.success, "cluster": result.cluster_name, "error": result.error, "output": result.output[-2000:]}


PROVISION_TOOLS = [provision_cluster, teardown_cluster]
