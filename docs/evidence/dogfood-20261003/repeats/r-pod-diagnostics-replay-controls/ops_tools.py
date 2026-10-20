"""Read-only cluster diagnostic tools for the on-prem ops agent.

Safe (read-only) kubectl wrappers so the agent can *investigate* before it acts:
list pods, fetch logs, describe, rollout status, list namespaces. All mutating
actions stay in the deploy tools (build/push/deploy/validate/rollback).

Read-only is not the same as harmless, and these share a process — and therefore a
credential — with the deploy tools. So they go through the same
``deploy_identity`` seam: pinning the deploy path while `get_logs` kept reading
whatever the ambient context could reach would be a boundary that looks closed from
the side you tested. (Someone else's pod logs are still someone else's data; that is
the same reasoning the unscoped MCP read path is a *named* carve-out rather than a
default — see 결정 2.)
"""

from __future__ import annotations

import subprocess
import json
import re
from datetime import datetime, timezone
from typing import Any

from src.agents.platform.deploy_identity import deploy_kubectl
from src.agents.ai.deployment_evidence import digest, pod_waiting_observations, summarize_deployment


def _kubectl(args: list[str], timeout: int = 30) -> dict[str, Any]:
    try:
        result = subprocess.run(deploy_kubectl(*args), capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError:
        return {"ok": False, "output": "", "error": "kubectl not found on PATH"}
    except subprocess.TimeoutExpired:
        return {"ok": False, "output": "", "error": f"kubectl timed out after {timeout}s"}
    ok = result.returncode == 0
    output = (result.stdout or result.stderr).strip()
    # Cap tightly: this output is fed back into the LLM context every turn, and
    # large kubectl dumps (describe/logs) balloon the prompt and slow prefill.
    return {
        "ok": ok,
        "output": output[:1500],
        "error": None if ok else (result.stderr.strip()[:600] or "non-zero exit"),
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
    result = _kubectl(["describe", f"deployment/{deployment}", "-n", namespace])
    if result["ok"]:
        result.update(_deployment_observations(deployment, namespace))
    return result


def _read_json(args: list[str], context: str) -> tuple[dict, str]:
    result = subprocess.run(deploy_kubectl("--context", context, *args, "-o", "json"),
                            capture_output=True, text=True, timeout=15)
    if result.returncode:
        raise ValueError(result.stderr.strip()[:600] or "Kubernetes observation failed")
    if len(result.stdout.encode()) > 1_000_000:
        raise ValueError("Kubernetes observation exceeds 1 MB; narrow the workload selector")
    data = json.loads(result.stdout)
    if not isinstance(data, dict):
        raise ValueError("Kubernetes observation must be a JSON object")
    return data, datetime.now(timezone.utc).isoformat()


def _selector(spec: dict) -> str:
    selector = spec.get("selector", {})
    parts = [f"{key}={value}" for key, value in sorted(selector.get("matchLabels", {}).items())]
    for expression in selector.get("matchExpressions", []):
        key, op, values = expression["key"], expression["operator"], expression.get("values", [])
        if op in {"In", "NotIn"} and values:
            parts.append(f"{key} {'in' if op == 'In' else 'notin'} ({','.join(values)})")
        elif op == "Exists":
            parts.append(key)
        elif op == "DoesNotExist":
            parts.append("!" + key)
        else:
            raise ValueError("Unsupported or incomplete deployment selector")
    if not parts:
        raise ValueError("Deployment selector is absent; namespace-wide collection refused")
    return ",".join(parts)


def deployment_evidence(deployment: str, namespace: str) -> dict:
    """Compatibility view of structured facts, without untrusted status prose."""
    return _deployment_observations(deployment, namespace)["evidence"]


def _deployment_observations(deployment: str, namespace: str) -> dict:
    """Acquire structured facts and separately quoted status through one read.

    No new credential, mutation, log interpretation or health endpoint is used.
    A second deployment read detects a changed UID/generation/resourceVersion;
    this does not claim a transaction across all Kubernetes resources.
    """
    unavailable = {"status": "not_established", "execution_authorized": False}
    try:
        if not re.fullmatch(r"[a-z0-9](?:[a-z0-9.-]{0,251}[a-z0-9])?", deployment):
            raise ValueError("Invalid deployment name")
        if not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", namespace):
            raise ValueError("Invalid namespace")
        start = datetime.now(timezone.utc)
        context_result = subprocess.run(deploy_kubectl("config", "current-context"),
                                        capture_output=True, text=True, timeout=5)
        context = context_result.stdout.strip()
        if context_result.returncode or not context or "\n" in context:
            raise ValueError("Deployment identity has no readable current context")
        before, at = _read_json(["get", f"deployment/{deployment}", "-n", namespace], context)
        related, related_at = _read_json(["get", "replicasets,pods", "-n", namespace,
                                         "-l", _selector(before.get("spec", {}))], context)
        after, _ = _read_json(["get", f"deployment/{deployment}", "-n", namespace], context)
        if any(before.get("metadata", {}).get(k) != after.get("metadata", {}).get(k)
               for k in ("uid", "generation", "resourceVersion")):
            raise ValueError("Deployment changed during observation; collect again before reviewing recovery")
        objects = related.get("items")
        if not isinstance(objects, list) or not all(isinstance(obj, dict) for obj in objects):
            raise ValueError("Related Kubernetes objects are not a list")
        sources = [{"source_id": "deployment", "sha256": digest(before), "observed_at": at},
                   {"source_id": "replicasets-pods", "sha256": digest(objects), "observed_at": related_at}]
        evidence = summarize_deployment(before, objects, context=context, namespace=namespace, name=deployment,
                                        sources=sources, as_of=datetime.now(timezone.utc), window_start=start)
        return {"evidence": evidence, "diagnostic_observations": pod_waiting_observations(evidence, objects)}
    except (ValueError, KeyError, TypeError, OSError, subprocess.TimeoutExpired) as exc:
        return {"evidence": {"recovery": unavailable, "error": str(exc)[:600],
                "limits": ["Structured observation unavailable; text output alone does not establish recovery eligibility."]},
                "diagnostic_observations": {"status": "unavailable", "trust": "untrusted_source_text", "records": [],
                                            "execution_authorized": False}}


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
