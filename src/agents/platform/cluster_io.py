"""The one place registry-rendered objects touch a cluster.

Everything else under ``src/agents/platform/`` is pure: it turns the registry into
manifests and never opens a socket. That separation is why the renderers are
testable offline, and it is worth keeping — so the two operations that genuinely
need a live cluster live here instead of leaking into the renderers, and the
callers that apply (``scripts/render_tenancy.py``, the agent's tenancy tools)
share one implementation of each.

Both functions distinguish three outcomes, not two. "The CRD is absent" and "we
could not ask" are different facts, and collapsing them is how a tenant ends up
reported as bounded on a cluster nobody checked.
"""

from __future__ import annotations

import subprocess
from typing import Any

import yaml

CAPSULE_CRD = "tenants.capsule.clastix.io"


def current_context() -> str | None:
    """Name of the active kubeconfig context, or None if it cannot be read."""
    try:
        proc = subprocess.run(
            ["kubectl", "config", "current-context"],
            capture_output=True, text=True, timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return proc.stdout.strip() or None if proc.returncode == 0 else None


def capsule_crd_installed() -> bool | None:
    """True/False, or None when we could not ask the cluster at all.

    The None case is not pedantry. Without the Capsule CRD, ``kubectl apply``
    creates a tenant's namespaces and RBAC, drops the quota object without
    erroring, and leaves the tenant unbounded on a shared cluster while every
    view still shows the declared quota. A caller that treats "unknown" as
    "installed" reproduces exactly that failure with more confidence.
    """
    try:
        proc = subprocess.run(
            ["kubectl", "get", "crd", CAPSULE_CRD],
            capture_output=True, text=True, timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return proc.returncode == 0


def apply_manifests(objects: list[dict[str, Any]], *, timeout: int = 300) -> dict[str, Any]:
    """`kubectl apply` a rendered manifest list, reporting what the server said.

    Args:
        objects: Rendered manifests, as the renderers return them.
        timeout: Seconds to wait. Add-on Applications are cheap to create; the
            default is generous because a cold API server on kind is not.

    Returns:
        Dict with ``ok``, ``applied`` (server-confirmed object count), ``output``,
        ``warnings`` and ``error``. ``applied`` counts lines kubectl acknowledged
        rather than objects sent, so a partial apply cannot report the number we
        hoped for.

        ``warnings`` is separate from ``error`` because kubectl writes both to
        stderr, and the callers upstream treat any non-empty ``error`` as a failed
        step. A live run proved that: applying a tenant emits two Capsule
        deprecation warnings, which turned a wholly successful chain into
        ``ok: False`` — the dashboard would have recorded a working run as failed.
        The warnings are kept rather than dropped; they are how a deprecation is
        noticed before it becomes the other kind of failure (silently unread).
    """
    if not objects:
        return {"ok": False, "applied": 0, "output": "", "warnings": [], "error": "nothing to apply"}
    stream = yaml.safe_dump_all(objects, sort_keys=False)
    try:
        proc = subprocess.run(
            ["kubectl", "apply", "-f", "-"],
            input=stream, capture_output=True, text=True, timeout=timeout,
        )
    except OSError:
        return {"ok": False, "applied": 0, "output": "", "warnings": [], "error": "kubectl not found on PATH"}
    except subprocess.TimeoutExpired:
        return {
            "ok": False, "applied": 0, "output": "", "warnings": [],
            "error": f"kubectl apply timed out after {timeout}s",
        }
    acknowledged = [ln for ln in proc.stdout.splitlines() if " " in ln.strip()]
    warnings, errors = [], []
    for line in proc.stderr.splitlines():
        (warnings if line.startswith("Warning:") else errors).append(line.strip())
    return {
        "ok": proc.returncode == 0,
        "applied": len(acknowledged),
        "output": proc.stdout.strip()[-800:],
        "warnings": warnings,
        "error": "\n".join(e for e in errors if e)[-800:] or None,
    }
