"""GCP provisioning adapter — GKE cluster via gcloud, approval-gated.

Mirrors the AWS adapter's plan-first / apply-after-approval contract: without
approval we run a read-only preflight (`clusters list` — verifies auth + project
+ region reachability); the mutating `clusters create` runs only when
``approved=True``. Teardown (`clusters delete`) likewise requires explicit
approval — cluster deletion is hard to reverse.

Requires: gcloud CLI authenticated, ``GCP_PROJECT`` set (and optionally
``GCP_REGION``; falls back to the same default the deployment adapter uses).
"""

from __future__ import annotations

import os
import subprocess

from src.agents.adapters.provisioning.base import ProvisionResult, ProvisionSpec

_DEFAULT_REGION = "asia-northeast3"


def _run(cmd: list[str], timeout: int = 1800) -> tuple[int, str]:
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError as exc:
        return 127, str(exc)
    except subprocess.TimeoutExpired:
        return 124, f"timed out after {timeout}s"
    return result.returncode, ((result.stdout or "") + (result.stderr or "")).strip()


class GcpProvisionAdapter:
    def _project(self) -> str:
        return os.getenv("GCP_PROJECT", "")

    def _region(self, spec: ProvisionSpec) -> str:
        return spec.region or os.getenv("GCP_REGION", _DEFAULT_REGION)

    def provision_cluster(self, spec: ProvisionSpec) -> ProvisionResult:
        project = self._project()
        if not project:
            return ProvisionResult(False, spec.cluster_name, error="GCP_PROJECT not set")
        region = self._region(spec)
        if spec.approved:
            cmd = [
                "gcloud", "container", "clusters", "create", spec.cluster_name,
                "--project", project,
                "--region", region,
                "--num-nodes", str(spec.node_count),
                "--quiet",
            ]
        else:
            # Preflight: read-only auth/project/region check; no cluster is created.
            cmd = ["gcloud", "container", "clusters", "list", "--project", project, "--region", region]
        rc, output = _run(cmd)
        ok = rc == 0
        action = "create" if spec.approved else "preflight"
        return ProvisionResult(
            success=ok,
            cluster_name=spec.cluster_name,
            # gcloud writes this exact kubeconfig context on a successful create.
            context=f"gke_{project}_{region}_{spec.cluster_name}" if spec.approved and ok else region,
            output=output[-4000:],
            error=None if ok else f"gcloud clusters {action} failed",
        )

    def teardown_cluster(self, spec: ProvisionSpec) -> ProvisionResult:
        if not spec.approved:
            return ProvisionResult(False, spec.cluster_name, error="GCP teardown requires explicit approved=True")
        project = self._project()
        if not project:
            return ProvisionResult(False, spec.cluster_name, error="GCP_PROJECT not set")
        region = self._region(spec)
        cmd = [
            "gcloud", "container", "clusters", "delete", spec.cluster_name,
            "--project", project,
            "--region", region,
            "--quiet",
        ]
        rc, output = _run(cmd)
        ok = rc == 0
        return ProvisionResult(
            success=ok,
            cluster_name=spec.cluster_name,
            output=output[-4000:],
            error=None if ok else "gcloud clusters delete failed",
        )
