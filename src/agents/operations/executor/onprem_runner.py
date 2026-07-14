"""On-Prem Action Runner — real kubectl remediation for Day-2 incidents.

Mirrors ``gcp_runner`` / ``azure_runner`` for the on-prem provider. Execution is
**disabled by default**: unless ``ONPREM_EXECUTOR_LIVE=true`` (and not under
``TESTING``), the runner only logs the intended action — the same safe no-op the
executor shipped with. This keeps automated remediation from mutating a cluster
unless an operator explicitly opts in.

When live, only clearly-reversible actions are executed against the cluster the
current kubeconfig context points at:

    ONPREM-RolloutRestartWorkload -> kubectl rollout restart deployment/<w> -n <ns>
    ONPREM-ArgoRolloutRollback    -> kubectl rollout undo    deployment/<w> -n <ns>

Everything else (scale without a desired count, node drain, disk/volume ops, …)
stays log-only even when live — those need a desired-state/parameters the alert
doesn't carry, so they remain a human/roadmap decision.
"""

from __future__ import annotations

import os
import subprocess
from typing import Any

# Actions that are safe + reversible to run automatically when live.
_LIVE_KUBECTL: dict[str, list[str]] = {
    "ONPREM-RolloutRestartWorkload": ["rollout", "restart"],
    "ONPREM-ArgoRolloutRollback": ["rollout", "undo"],
}


def _is_live() -> bool:
    return os.getenv("ONPREM_EXECUTOR_LIVE", "false").lower() == "true" and os.getenv("TESTING") != "True"


def _run_kubectl(args: list[str], timeout: int = 60) -> tuple[int, str, str]:
    proc = subprocess.run(["kubectl", *args], capture_output=True, text=True, timeout=timeout)
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()


def run_onprem_action(action: str, params: dict[str, list[str]], log: Any) -> None:
    """Execute (or log-only) one on-prem remediation action.

    Raises on a failed live kubectl call so the executor marks the action skipped.
    """
    if not _is_live():
        log.info("onprem_runner.log_only", action=action, params=params)
        return

    verb = _LIVE_KUBECTL.get(action)
    if verb is None:
        # Live is on, but this action isn't wired for automatic execution.
        log.info("onprem_runner.live_unwired", action=action, params=params)
        return

    namespace = (params.get("Namespace") or [""])[0]
    workload = (params.get("WorkloadName") or [""])[0]
    if not workload:
        log.info("onprem_runner.live_missing_target", action=action, params=params)
        return

    args = [*verb, f"deployment/{workload}"]
    if namespace:
        args += ["-n", namespace]

    code, out, err = _run_kubectl(args)
    if code != 0:
        log.error("onprem_runner.kubectl_failed", action=action, args=args, stderr=err)
        raise RuntimeError(f"kubectl {' '.join(args)} failed ({code}): {err}")
    log.info("onprem_runner.kubectl_ok", action=action, args=args, stdout=out)
