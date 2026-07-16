"""Shared Kubernetes Deployment-over-REST verbs for the GCP/Azure runners.

Once a runner has resolved the API-server endpoint, a bearer token, and the
cluster CA file, the rollout-restart and scale flows hit the identical
``apps/v1`` Deployment endpoint with identical request bodies and status checks.
That behaviourally-identical part lives here.

What stays per-runner (because it genuinely differs by cloud): auth, endpoint/CA
discovery, failover, and rollback — GKE derives a fallback image while AKS
requires an explicit RollbackVersion, so rollback is intentionally not shared.

Note: this path is only reached in real cloud runs; the runners short-circuit to
mock mode under TESTING, so these verbs are verified by inspection, not by unit
tests. Keep them byte-for-byte faithful to the flow they replaced.
"""

from __future__ import annotations

import time
from typing import Any

import requests


def rollout_restart(
    *,
    base_url: str,
    headers: dict[str, str],
    ca_cert_path: str,
    workload: str,
    log: Any,
    log_prefix: str,
    timeout: int = 15,
) -> None:
    """Trigger a rollout restart via a strategic-merge patch on the pod template."""
    log.info(f"{log_prefix}.rollout_restart", workload=workload)
    patch_headers = {**headers, "Content-Type": "application/strategic-merge-patch+json"}
    patch_body = {
        "spec": {
            "template": {
                "metadata": {
                    "annotations": {
                        "kubectl.kubernetes.io/restartedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                    }
                }
            }
        }
    }
    resp = requests.patch(base_url, headers=patch_headers, json=patch_body, verify=ca_cert_path, timeout=timeout)
    if resp.status_code != 200:
        raise RuntimeError(f"K8s rollout restart failed (HTTP {resp.status_code}): {resp.text}")
    log.info(f"{log_prefix}.rollout_restart.success", workload=workload)


def scale_up(
    *,
    base_url: str,
    headers: dict[str, str],
    ca_cert_path: str,
    workload: str,
    log: Any,
    log_prefix: str,
    timeout: int = 15,
) -> int:
    """Scale the deployment up by one replica. Returns the new target replica count."""
    log.info(f"{log_prefix}.scale", workload=workload)
    resp = requests.get(base_url, headers=headers, verify=ca_cert_path, timeout=timeout)
    if resp.status_code != 200:
        raise RuntimeError(f"Failed to fetch deployment details: {resp.text}")

    deployment = resp.json()
    current_replicas = deployment.get("spec", {}).get("replicas", 1)
    target_replicas = current_replicas + 1
    log.info(f"{log_prefix}.scale.target", current=current_replicas, target=target_replicas)

    patch_headers = {**headers, "Content-Type": "application/merge-patch+json"}
    patch_body = {"spec": {"replicas": target_replicas}}

    resp = requests.patch(base_url, headers=patch_headers, json=patch_body, verify=ca_cert_path, timeout=timeout)
    if resp.status_code != 200:
        raise RuntimeError(f"K8s scale failed (HTTP {resp.status_code}): {resp.text}")
    log.info(f"{log_prefix}.scale.success", workload=workload, replicas=target_replicas)
    return target_replicas
