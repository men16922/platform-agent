"""Read-only cluster diagnostic tools for the on-prem ops agent.

Safe (read-only) kubectl wrappers so the agent can *investigate* before it acts:
list pods, fetch logs, describe, rollout status, list namespaces. All mutating
actions stay in the deploy tools (build/push/deploy/validate/rollback). These run
against the ambient kubeconfig context (kind / on-prem cluster).
"""

from __future__ import annotations

import subprocess
from typing import Any


def _kubectl(args: list[str], timeout: int = 30) -> dict[str, Any]:
    try:
        result = subprocess.run(["kubectl", *args], capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError:
        return {"ok": False, "output": "", "error": "kubectl not found on PATH"}
    except subprocess.TimeoutExpired:
        return {"ok": False, "output": "", "error": f"kubectl timed out after {timeout}s"}
    ok = result.returncode == 0
    output = (result.stdout or result.stderr).strip()
    return {
        "ok": ok,
        "output": output[:8000],
        "error": None if ok else (result.stderr.strip()[:2000] or "non-zero exit"),
    }


def list_pods(namespace: str = "default") -> dict:
    """List pods in a namespace (read-only).

    Args:
        namespace: Kubernetes namespace.

    Returns:
        Dict with pod listing output.
    """
    return _kubectl(["get", "pods", "-n", namespace, "-o", "wide"])


def get_logs(deployment: str, namespace: str = "default", tail: int = 50) -> dict:
    """Fetch recent logs from a deployment's pods (read-only).

    Args:
        deployment: Deployment name.
        namespace: Kubernetes namespace.
        tail: Number of trailing log lines.

    Returns:
        Dict with log output.
    """
    return _kubectl(["logs", f"deployment/{deployment}", "-n", namespace, "--tail", str(tail)])


def describe_deployment(deployment: str, namespace: str = "default") -> dict:
    """Describe a deployment — replicas, conditions, recent events (read-only).

    Args:
        deployment: Deployment name.
        namespace: Kubernetes namespace.

    Returns:
        Dict with describe output.
    """
    return _kubectl(["describe", f"deployment/{deployment}", "-n", namespace])


def rollout_status(deployment: str, namespace: str = "default") -> dict:
    """Check rollout status of a deployment (read-only, short timeout).

    Args:
        deployment: Deployment name.
        namespace: Kubernetes namespace.

    Returns:
        Dict with rollout status output.
    """
    return _kubectl(
        ["rollout", "status", f"deployment/{deployment}", "-n", namespace, "--timeout", "10s"],
        timeout=15,
    )


def list_namespaces() -> dict:
    """List namespaces in the cluster (read-only).

    Returns:
        Dict with namespace listing output.
    """
    return _kubectl(["get", "namespaces"])


OPS_TOOLS = [list_pods, get_logs, describe_deployment, rollout_status, list_namespaces]
