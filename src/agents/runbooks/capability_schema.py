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
                "on_failure": "abort"
            }
        ]
    }
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


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
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RunbookStep":
        return cls(
            name=data["name"],
            capability=data["capability"],
            description=data.get("description", ""),
            parameters=data.get("parameters", {}),
            condition=data.get("condition"),
            on_failure=data.get("on_failure", "abort"),
            timeout_sec=data.get("timeout_sec"),
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

    return problems


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
