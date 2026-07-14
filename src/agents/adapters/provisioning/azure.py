"""Azure provisioning adapter — AKS cluster via az, approval-gated.

Mirrors the AWS adapter's plan-first / apply-after-approval contract: without
approval we run a read-only preflight (`aks list` — verifies login + resource
group); the mutating `aks create` runs only when ``approved=True``. Teardown
(`aks delete`) likewise requires explicit approval — cluster deletion is hard to
reverse.

Requires: az CLI logged in, ``AZURE_RESOURCE_GROUP`` set (and optionally
``AZURE_REGION``; falls back to the same default the deployment adapter uses).
"""

from __future__ import annotations

import os
import subprocess

from src.agents.adapters.provisioning.base import ProvisionResult, ProvisionSpec

_DEFAULT_REGION = "koreacentral"


def _run(cmd: list[str], timeout: int = 1800) -> tuple[int, str]:
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError as exc:
        return 127, str(exc)
    except subprocess.TimeoutExpired:
        return 124, f"timed out after {timeout}s"
    return result.returncode, ((result.stdout or "") + (result.stderr or "")).strip()


class AzureProvisionAdapter:
    def _resource_group(self) -> str:
        return os.getenv("AZURE_RESOURCE_GROUP", "")

    def _region(self, spec: ProvisionSpec) -> str:
        return spec.region or os.getenv("AZURE_REGION", _DEFAULT_REGION)

    def provision_cluster(self, spec: ProvisionSpec) -> ProvisionResult:
        rg = self._resource_group()
        if not rg:
            return ProvisionResult(False, spec.cluster_name, error="AZURE_RESOURCE_GROUP not set")
        if spec.approved:
            cmd = [
                "az", "aks", "create",
                "--resource-group", rg,
                "--name", spec.cluster_name,
                "--location", self._region(spec),
                "--node-count", str(spec.node_count),
                "--generate-ssh-keys",
                "--yes",
            ]
            if spec.node_size:
                cmd += ["--node-vm-size", spec.node_size]
        else:
            # Preflight: read-only login/resource-group check; no cluster is created.
            cmd = ["az", "aks", "list", "--resource-group", rg, "--output", "table"]
        rc, output = _run(cmd)
        ok = rc == 0
        action = "create" if spec.approved else "preflight"
        return ProvisionResult(
            success=ok,
            cluster_name=spec.cluster_name,
            # AKS kubeconfig context defaults to the cluster name on `az aks get-credentials`.
            context=spec.cluster_name if spec.approved and ok else rg,
            output=output[-4000:],
            error=None if ok else f"az aks {action} failed",
        )

    def teardown_cluster(self, spec: ProvisionSpec) -> ProvisionResult:
        if not spec.approved:
            return ProvisionResult(False, spec.cluster_name, error="Azure teardown requires explicit approved=True")
        rg = self._resource_group()
        if not rg:
            return ProvisionResult(False, spec.cluster_name, error="AZURE_RESOURCE_GROUP not set")
        cmd = ["az", "aks", "delete", "--resource-group", rg, "--name", spec.cluster_name, "--yes"]
        rc, output = _run(cmd)
        ok = rc == 0
        return ProvisionResult(
            success=ok,
            cluster_name=spec.cluster_name,
            output=output[-4000:],
            error=None if ok else "az aks delete failed",
        )
