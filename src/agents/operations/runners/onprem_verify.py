"""
On-Prem post-execution verification — "did the remediation actually help?"

`resolution_verdict` already models two axes (dispatched × verified), but until
now nothing filled the verified one: the executor knew every action had been
*sent* and inferred recovery from that. A restart that dispatches fine and leaves
the workload crash-looping was reported exactly like a real recovery.

These checks close that gap. Each is a **read-only** capability resolved to a
provider-specific query, mirroring how action capabilities resolve to
provider-specific actions — and each runs with the *same scoped credential* as
the action it verifies (Phase 1a), so verification cannot reach further than the
remediation it is checking.

Design rules:

* **A failed check is not an error.** It returns ``passed=False`` with a reason.
  Only a *required* check withholds resolution (see ``resolution_verdict``), and
  an unknown/unverifiable outcome must never read as success.
* **Bounded waits.** Every check has a timeout; a verification that hangs is a
  verification that has failed to answer.
* **No mutation.** These run after a change has been made, so anything that
  writes here would be an unreviewed second remediation.
"""

from __future__ import annotations

import json
import subprocess
from typing import TYPE_CHECKING, Any

from src.agents.runbooks.capability_schema import VerificationResult

if TYPE_CHECKING:
    from src.agents.platform.scope import IncidentScope

# Capability -> the action(s) whose effect it proves. Keyed by executor action so
# the flat action list the executor walks can be verified without the (still
# unwired) capability-step machinery.
VERIFY_FOR_ACTION: dict[str, str] = {
    "ONPREM-RolloutRestartWorkload": "assert_workload_ready",
    "ONPREM-ArgoRolloutRollback": "assert_workload_ready",
    "ONPREM-ScaleWorkload": "assert_replica_count",
    "ONPREM-DrainNode": "assert_node_unschedulable",
}

_DEFAULT_TIMEOUT_SEC = 90


def _kubectl(args: list[str], scope: "IncidentScope", timeout: int) -> tuple[int, str, str]:
    proc = subprocess.run(
        ["kubectl", *scope.kubectl_prefix(), *args],
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()


def _target(params: dict[str, list[str]]) -> tuple[str, str]:
    namespace = (params.get("Namespace") or [""])[0]
    workload = (params.get("WorkloadName") or [""])[0]
    return namespace, workload


def _assert_workload_ready(
    step_name: str, params: dict[str, list[str]], scope: "IncidentScope", timeout: int
) -> VerificationResult:
    """Wait for the rollout to converge — the actual proof a restart/rollback worked."""
    namespace, workload = _target(params)
    capability = "assert_workload_ready"
    if not workload:
        return VerificationResult(
            step_name=step_name, capability=capability, passed=False,
            detail="no workload name to verify",
        )
    args = ["rollout", "status", f"deployment/{workload}", f"--timeout={timeout}s"]
    if namespace:
        args += ["-n", namespace]
    try:
        code, out, err = _kubectl(args, scope, timeout + 30)
    except subprocess.TimeoutExpired:
        return VerificationResult(
            step_name=step_name, capability=capability, passed=False,
            detail=f"rollout did not converge within {timeout}s",
        )
    # `rollout status` streams progress lines; the LAST one is the conclusion.
    # Reporting the first would attach "waiting for..." to a passed check.
    conclusion = next((line for line in reversed((out or err).splitlines()) if line.strip()), "")
    return VerificationResult(
        step_name=step_name, capability=capability, passed=code == 0,
        detail=conclusion[:200],
    )


def _assert_replica_count(
    step_name: str, params: dict[str, list[str]], scope: "IncidentScope", timeout: int
) -> VerificationResult:
    """Read back readyReplicas — a scale that was accepted but never became ready is not a fix."""
    namespace, workload = _target(params)
    capability = "assert_replica_count"
    desired_raw = (params.get("DesiredReplicas") or [""])[0]
    try:
        desired = int(str(desired_raw).strip())
    except (TypeError, ValueError):
        return VerificationResult(
            step_name=step_name, capability=capability, passed=False,
            detail=f"no parseable DesiredReplicas ({desired_raw!r})",
        )
    args = ["get", f"deployment/{workload}", "-o", "json"]
    if namespace:
        args += ["-n", namespace]
    try:
        code, out, err = _kubectl(args, scope, timeout)
    except subprocess.TimeoutExpired:
        return VerificationResult(
            step_name=step_name, capability=capability, passed=False, detail="read timed out",
        )
    if code != 0:
        return VerificationResult(
            step_name=step_name, capability=capability, passed=False, detail=err[:200],
        )
    try:
        ready = int((json.loads(out).get("status") or {}).get("readyReplicas") or 0)
    except (ValueError, AttributeError):
        return VerificationResult(
            step_name=step_name, capability=capability, passed=False,
            detail="could not read status.readyReplicas",
        )
    return VerificationResult(
        step_name=step_name, capability=capability, passed=ready >= desired,
        detail=f"readyReplicas={ready} desired={desired}",
    )


def _assert_health_check_passing(
    step_name: str, params: dict[str, list[str]], scope: "IncidentScope", timeout: int
) -> VerificationResult:
    """The workload's own probes report healthy — the proof a health-check alarm wants.

    Distinct from ``assert_workload_ready`` on purpose. `rollout status` answers
    "did the new revision finish rolling out"; a workload can finish rolling out
    and still fail its readiness probe moments later, which is exactly the
    failure mode `health-check-failure` exists for. `Available` is the condition
    Kubernetes derives from readiness, so this asks the thing the alarm asked.

    Implemented because making that runbook selectable made this check
    reachable, and an unimplemented check is a *failed* check here (by design) —
    so shipping without it would have meant a runbook that silently cascades to
    rollback every time its first step actually worked.
    """
    namespace, workload = _target(params)
    capability = "assert_health_check_passing"
    if not workload:
        return VerificationResult(
            step_name=step_name, capability=capability, passed=False,
            detail="no workload name to verify",
        )
    # Read-only and bounded: `wait` polls the condition, it does not mutate.
    args = [
        "wait", f"deployment/{workload}",
        "--for=condition=Available", f"--timeout={timeout}s",
    ]
    if namespace:
        args += ["-n", namespace]
    try:
        code, out, err = _kubectl(args, scope, timeout + 30)
    except subprocess.TimeoutExpired:
        return VerificationResult(
            step_name=step_name, capability=capability, passed=False,
            detail=f"health checks did not pass within {timeout}s",
        )
    return VerificationResult(
        step_name=step_name, capability=capability, passed=code == 0,
        detail=(out or err)[:200] or "condition=Available",
    )


def _assert_node_unschedulable(
    step_name: str, params: dict[str, list[str]], scope: "IncidentScope", timeout: int
) -> VerificationResult:
    """A drain that left the node schedulable did not do what the runbook claimed."""
    capability = "assert_node_unschedulable"
    node = (params.get("NodeName") or [""])[0]
    if not node:
        return VerificationResult(
            step_name=step_name, capability=capability, passed=False, detail="no node name",
        )
    try:
        code, out, err = _kubectl(
            ["get", "node", node, "-o", "jsonpath={.spec.unschedulable}"], scope, timeout
        )
    except subprocess.TimeoutExpired:
        return VerificationResult(
            step_name=step_name, capability=capability, passed=False, detail="read timed out",
        )
    if code != 0:
        return VerificationResult(
            step_name=step_name, capability=capability, passed=False, detail=err[:200],
        )
    return VerificationResult(
        step_name=step_name, capability=capability, passed=out.strip() == "true",
        detail=f"spec.unschedulable={out.strip() or 'false'}",
    )


_CHECKS = {
    "assert_workload_ready": _assert_workload_ready,
    "assert_replica_count": _assert_replica_count,
    "assert_health_check_passing": _assert_health_check_passing,
    "assert_node_unschedulable": _assert_node_unschedulable,
}


def verify_onprem_action(
    action: str,
    params: dict[str, list[str]],
    log: Any,
    scope: "IncidentScope | None" = None,
    timeout_sec: int = _DEFAULT_TIMEOUT_SEC,
    capability: str | None = None,
    step_name: str | None = None,
) -> VerificationResult | None:
    """
    Verify one executed action's effect. ``None`` = nothing declared to verify.

    A missing scope yields a *failed* check rather than None: we ran a live action
    and then could not confirm it, which is precisely the state that must not be
    reported as resolved.

    ``capability`` lets a runbook step name its OWN check, which beats the
    action→capability table: the table is a global guess about what an action
    implies, while the step's ``verify`` is the author stating what would count
    as proof for this particular use of it. Unset falls back to the table, so
    every runbook that predates the step schema behaves exactly as before.
    """
    capability = capability or VERIFY_FOR_ACTION.get(action)
    if capability is None:
        return None
    if capability not in _CHECKS:
        # A declared check we cannot run is not a pass. Silently dropping it
        # would let a runbook claim verification it never had.
        log.warning("onprem_verify.unknown_capability", action=action, capability=capability)
        return VerificationResult(
            step_name=step_name or action, capability=capability, passed=False,
            detail=f"no check implemented for capability {capability!r}",
        )

    # Log-only mode changed nothing, so there is nothing to verify. Reporting a
    # failed check here would be worse than silence: it would turn "we chose not
    # to act" into "we acted and it did not work", flipping resolved to False for
    # every incident on the default (safe) configuration.
    from src.agents.operations.runners.onprem_runner import _is_live

    if not _is_live():
        log.info("onprem_verify.skipped_log_only", action=action, capability=capability)
        return None

    if scope is None:
        log.warning("onprem_verify.no_scope", action=action, capability=capability)
        return VerificationResult(
            step_name=action, capability=capability, passed=False,
            detail="no scoped credential to verify with",
        )

    result = _CHECKS[capability](action, params, scope, timeout_sec)
    log.info(
        "onprem_verify.done",
        action=action, capability=capability, passed=result.passed, detail=result.detail,
    )
    return result
