"""
Capability-based runbook execution schema.

Extends the base runbook contract with declarative execution steps.
Each step declares a *capability* (cloud-neutral intent) that the runtime
resolves to a provider-specific action via the ExecutionAdapter.

A runbook with steps replaces the flat ``actions`` list. The executor walks
the steps in order, evaluating conditions and passing parameters.

Example runbook with steps:

    {
        "runbook_id": "eks-pod-oom",
        "capabilities": ["restart_workload", "scale_out"],
        "steps": [
            {
                "name": "restart_pod",
                "capability": "restart_workload",
                "description": "Restart the OOMKilled pod",
                "parameters": {"grace_period_sec": 30},
                "on_failure": "continue"
            },
            {
                "name": "scale_nodes",
                "capability": "scale_out",
                "description": "Scale out the node group if restart alone didn't recover",
                "condition": {"previous_step_failed": true},
                "parameters": {"increment": 1, "max_nodes": 10},
                "on_failure": "abort",
                "verify": {
                    "capability": "assert_workload_ready",
                    "parameters": {"timeout_sec": 120}
                }
            }
        ]
    }

``verify`` declares *how to prove the step actually helped* — dispatching an
action is not the same as recovering. Without it, "resolved" can only mean
"every action was dispatched" (see ``resolution_verdict`` below).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class StepVerification:
    """
    A post-execution check that proves a step's intended effect.

    Declared as a capability (cloud-neutral intent) so the execution adapter
    resolves it to a provider-specific read — the same indirection the action
    capabilities use. ``required=False`` makes the check advisory: it is still
    run and reported, but a failure does not by itself withhold resolution.
    """

    capability: str
    description: str = ""
    parameters: dict[str, Any] = field(default_factory=dict)
    required: bool = True

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"capability": self.capability}
        if self.description:
            result["description"] = self.description
        if self.parameters:
            result["parameters"] = self.parameters
        if not self.required:
            result["required"] = self.required
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StepVerification":
        return cls(
            capability=data["capability"],
            description=data.get("description", ""),
            parameters=data.get("parameters", {}),
            required=data.get("required", True),
        )


@dataclass
class RunbookStep:
    """A single execution step in a capability-based runbook."""

    name: str
    capability: str
    description: str = ""
    parameters: dict[str, Any] = field(default_factory=dict)
    condition: dict[str, Any] | None = None
    on_failure: str = "abort"  # "abort" | "continue" | "rollback"
    timeout_sec: int | None = None
    verify: StepVerification | None = None

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "name": self.name,
            "capability": self.capability,
        }
        if self.description:
            result["description"] = self.description
        if self.parameters:
            result["parameters"] = self.parameters
        if self.condition:
            result["condition"] = self.condition
        if self.on_failure != "abort":
            result["on_failure"] = self.on_failure
        if self.timeout_sec is not None:
            result["timeout_sec"] = self.timeout_sec
        if self.verify is not None:
            result["verify"] = self.verify.to_dict()
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RunbookStep":
        raw_verify = data.get("verify")
        return cls(
            name=data["name"],
            capability=data["capability"],
            description=data.get("description", ""),
            parameters=data.get("parameters", {}),
            condition=data.get("condition"),
            on_failure=data.get("on_failure", "abort"),
            timeout_sec=data.get("timeout_sec"),
            verify=StepVerification.from_dict(raw_verify) if isinstance(raw_verify, dict) else None,
        )


@dataclass
class CapabilityRunbook:
    """
    A cloud-neutral runbook with declarative execution steps.

    The runbook declares *what* should happen (capabilities + parameters).
    The execution adapter decides *how* (provider-specific actions).
    """

    runbook_id: str
    steps: list[RunbookStep]
    description: str = ""
    resource_types: list[str] = field(default_factory=list)
    rto_sec: int | None = None

    @property
    def capabilities(self) -> list[str]:
        """Derive capabilities from steps."""
        return list(dict.fromkeys(step.capability for step in self.steps))

    def to_dict(self) -> dict[str, Any]:
        return {
            "runbook_id": self.runbook_id,
            "description": self.description,
            "capabilities": self.capabilities,
            "resource_types": self.resource_types,
            "rto_sec": self.rto_sec,
            "steps": [step.to_dict() for step in self.steps],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CapabilityRunbook":
        steps = [RunbookStep.from_dict(s) for s in data.get("steps", [])]
        return cls(
            runbook_id=data["runbook_id"],
            steps=steps,
            description=data.get("description", ""),
            resource_types=data.get("resource_types", []),
            rto_sec=data.get("rto_sec"),
        )


def validate_capability_runbook(data: Any) -> list[str]:
    """
    Validate a capability-based runbook dict.

    Returns a list of problems. Empty list = valid.
    """
    problems: list[str] = []

    if not isinstance(data, dict):
        return [f"runbook must be a dict, got {type(data).__name__}"]

    if not isinstance(data.get("runbook_id"), str) or not data["runbook_id"].strip():
        problems.append("runbook_id must be a non-empty string")

    steps = data.get("steps")
    if not isinstance(steps, list) or len(steps) == 0:
        problems.append("steps must be a non-empty list")
        return problems

    seen_names: set[str] = set()
    for i, step in enumerate(steps):
        prefix = f"steps[{i}]"
        if not isinstance(step, dict):
            problems.append(f"{prefix} must be a dict")
            continue

        name = step.get("name")
        if not isinstance(name, str) or not name.strip():
            problems.append(f"{prefix}.name must be a non-empty string")
        elif name in seen_names:
            problems.append(f"{prefix}.name '{name}' is duplicated")
        else:
            seen_names.add(name)

        capability = step.get("capability")
        if not isinstance(capability, str) or not capability.strip():
            problems.append(f"{prefix}.capability must be a non-empty string")

        on_failure = step.get("on_failure", "abort")
        if on_failure not in ("abort", "continue", "rollback"):
            problems.append(f"{prefix}.on_failure must be 'abort', 'continue', or 'rollback'")

        timeout = step.get("timeout_sec")
        if timeout is not None and not isinstance(timeout, int):
            problems.append(f"{prefix}.timeout_sec must be an integer or null")

        verify = step.get("verify")
        if verify is not None:
            if not isinstance(verify, dict):
                problems.append(f"{prefix}.verify must be a dict or null")
            else:
                verify_capability = verify.get("capability")
                if not isinstance(verify_capability, str) or not verify_capability.strip():
                    problems.append(f"{prefix}.verify.capability must be a non-empty string")
                if not isinstance(verify.get("required", True), bool):
                    problems.append(f"{prefix}.verify.required must be a boolean")

    return problems


@dataclass
class VerificationResult:
    """Outcome of running one step's ``verify`` check."""

    step_name: str
    capability: str
    passed: bool
    required: bool = True
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "step_name": self.step_name,
            "capability": self.capability,
            "passed": self.passed,
        }
        if not self.required:
            result["required"] = self.required
        if self.detail:
            result["detail"] = self.detail
        return result


@dataclass
class ResolutionVerdict:
    """
    Why an incident is (or is not) considered resolved.

    ``dispatched`` is the pre-existing semantic ("every action ran"); ``verified``
    is the new evidence axis. Both are reported so a caller can tell an
    unverified dispatch apart from a proven recovery.
    """

    resolved: bool
    dispatched: bool
    verified: bool | None  # None = no verification was declared/attempted
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "resolved": self.resolved,
            "dispatched": self.dispatched,
            "verified": self.verified,
            "reason": self.reason,
        }


def resolution_verdict(
    executed: list[str],
    skipped: list[str],
    verifications: list[VerificationResult] | None = None,
    not_applicable: list[str] | None = None,
) -> ResolutionVerdict:
    """
    Decide whether an incident is resolved, using verification evidence when present.

    Backward compatible by construction: with no verifications the verdict is
    exactly the historical rule ``bool(executed) and not skipped`` and ``verified``
    is ``None`` (honestly "unknown", not "passed"). Only a *required* verification
    can withhold resolution — advisory checks are reported but never block.

    ``not_applicable`` carries steps whose ``condition`` was false — "we correctly
    chose not to do this", which is NOT "we tried and could not". Conflating the
    two is the same inversion log-only mode already taught us: it would make every
    runbook that uses conditions properly (scale out ONLY if the restart failed)
    report unresolved on its success path, which is the path that should look best.
    They are still reported as skipped for transparency; they just do not count
    against resolution.
    """
    blocking_skips = [s for s in skipped if s not in set(not_applicable or [])]
    dispatched = bool(executed) and not blocking_skips

    if not verifications:
        return ResolutionVerdict(
            resolved=dispatched,
            dispatched=dispatched,
            verified=None,
            reason="dispatched" if dispatched else "not all actions dispatched",
        )

    required_failures = [v for v in verifications if v.required and not v.passed]
    verified = not required_failures

    if not dispatched:
        reason = "not all actions dispatched"
    elif required_failures:
        names = ", ".join(v.step_name for v in required_failures)
        reason = f"verification failed: {names}"
    else:
        reason = "dispatched and verified"

    return ResolutionVerdict(
        resolved=dispatched and verified,
        dispatched=dispatched,
        verified=verified,
        reason=reason,
    )


def evaluate_condition(condition: dict[str, Any] | None, context: dict[str, Any]) -> bool:
    """
    Evaluate a step condition against execution context.

    Supported conditions:
        - {"previous_step_failed": true/false}
        - {"severity_in": ["P1", "P2"]}
        - {"provider": "aws"}

    Returns True if the step should execute. None condition = always execute.
    """
    if condition is None:
        return True

    if "previous_step_failed" in condition:
        expected = condition["previous_step_failed"]
        actual = context.get("previous_step_failed", False)
        if actual != expected:
            return False

    if "severity_in" in condition:
        allowed = condition["severity_in"]
        if context.get("severity") not in allowed:
            return False

    if "provider" in condition:
        if context.get("provider") != condition["provider"]:
            return False

    return True
