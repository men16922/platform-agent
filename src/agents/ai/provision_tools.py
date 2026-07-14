"""Provisioning tools for the platform agent (① Provision role).

Mutating, infrastructure-level: stand up / tear down an on-prem Kubernetes
cluster via IaC (Terraform for kind, Ansible for k3s). Only invoke when the user
explicitly asks to provision or tear down a cluster.
"""

import re

from src.agents.adapters.provisioning import ProvisionSpec, get_provisioning_adapter

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


def _clean_tail(output: str, limit: int) -> str:
    """Strip ANSI escapes / blank lines so tool results fed back to the LLM are
    clean text — small models get confused by raw terraform/ANSI noise and stop
    the tool loop instead of continuing to the next step."""
    text = _ANSI_RE.sub("", output or "")
    text = "\n".join(line.rstrip() for line in text.splitlines() if line.strip())
    return text[-limit:]


def provision_cluster(cluster_name: str = "platform-agent", mode: str = "kind", provider: str = "onprem") -> dict:
    """Provision a Kubernetes cluster (infrastructure, IaC). MUTATING for onprem.

    Args:
        cluster_name: Name of the cluster to create.
        mode: "kind" (Terraform + Docker, no VM) or "k3s" (Ansible + VM/bare-metal).
        provider: Target environment — "onprem" (default), "gcp" (GKE), or
            "azure" (AKS). For managed-cloud providers this runs a read-only
            PREFLIGHT only (verifies auth + project/resource-group); the real
            `clusters create` requires an approved spec and is not driven from
            here, so an agent tool call can never accidentally stand up billable
            cloud infrastructure.

    Returns:
        Dict with provisioning result (success, cluster, context, error).
    """
    adapter = get_provisioning_adapter(provider)
    result = adapter.provision_cluster(ProvisionSpec(cluster_name=cluster_name, provider=provider, mode=mode))
    out: dict = {
        "success": result.success,
        "cluster": result.cluster_name,
        "context": result.context,
        "error": result.error,
    }
    # On success feed a clean one-liner (not raw terraform output) so the agent
    # moves on to deploy; on failure include a cleaned tail for diagnosis.
    if result.success:
        out["note"] = f"cluster ready; kubeconfig context '{result.context}'"
    else:
        out["output"] = _clean_tail(result.output, 600)
    return out


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
    out: dict = {"success": result.success, "cluster": result.cluster_name, "error": result.error}
    if not result.success:
        out["output"] = _clean_tail(result.output, 600)
    return out


PROVISION_TOOLS = [provision_cluster, teardown_cluster]
