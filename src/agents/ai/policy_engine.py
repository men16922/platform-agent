"""
Policy Engine — YAML-based policy parsing and evaluation for Guardian Agent.

Loads deploy policies from YAML files and evaluates deployment requests against
rules to produce a decision: APPROVE, AUTO, or REJECT.

Usage:
    from src.agents.ai.policy_engine import PolicyEngine, DeployRequest

    engine = PolicyEngine.from_default()
    request = DeployRequest(environment="prod", action="deploy", replicas=3)
    result = engine.evaluate(request)
    # result.decision == "APPROVE"
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import yaml


class Decision(str, Enum):
    """Policy evaluation decision."""

    APPROVE = "APPROVE"  # Requires human approval
    AUTO = "AUTO"  # Proceed automatically
    REJECT = "REJECT"  # Block the action


@dataclass
class DeployRequest:
    """A deployment request to be evaluated against policies."""

    environment: str = "dev"
    action: str = "deploy"
    service_name: str = ""
    replicas: int = 1
    provider: str = "onprem"
    namespace: str = "default"
    cross_region: bool = False
    version: str = ""
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class PolicyRule:
    """A single policy rule parsed from YAML."""

    id: str
    description: str
    field: str
    operator: str
    values: list[Any]
    decision: Decision
    priority: int = 0


@dataclass
class PolicyResult:
    """Result of policy evaluation."""

    decision: Decision
    matched_rules: list[PolicyRule]
    reason: str


class PolicyEngine:
    """Evaluates deployment requests against YAML-defined policies."""

    def __init__(self, rules: list[PolicyRule], default_decision: Decision = Decision.AUTO):
        self._rules = sorted(rules, key=lambda r: r.priority, reverse=True)
        self._default_decision = default_decision

    @classmethod
    def from_yaml(cls, path: str) -> PolicyEngine:
        """Load a policy engine from a YAML file."""
        with open(path) as f:
            data = yaml.safe_load(f)

        rules = []
        for rule_data in data.get("rules", []):
            condition = rule_data["condition"]
            rules.append(
                PolicyRule(
                    id=rule_data["id"],
                    description=rule_data.get("description", ""),
                    field=condition["field"],
                    operator=condition["operator"],
                    values=condition["values"],
                    decision=Decision(rule_data["decision"]),
                    priority=rule_data.get("priority", 0),
                )
            )

        default = Decision(data.get("default_decision", "AUTO"))
        return cls(rules=rules, default_decision=default)

    @classmethod
    def from_default(cls) -> PolicyEngine:
        """Load the default deploy-policy.yaml."""
        policy_path = os.path.join(
            os.path.dirname(__file__), "policies", "deploy-policy.yaml"
        )
        return cls.from_yaml(policy_path)

    def evaluate(self, request: DeployRequest) -> PolicyResult:
        """Evaluate a deployment request against all rules.

        Rules are evaluated in priority order (highest first).
        The first matching rule determines the decision.
        REJECT rules always win over APPROVE/AUTO at the same priority.

        Returns:
            PolicyResult with the final decision and reasoning.
        """
        matched = []

        for rule in self._rules:
            if self._matches(rule, request):
                matched.append(rule)

        if not matched:
            return PolicyResult(
                decision=self._default_decision,
                matched_rules=[],
                reason=f"No rules matched. Default: {self._default_decision.value}",
            )

        # REJECT at any priority wins over everything
        reject_rules = [r for r in matched if r.decision == Decision.REJECT]
        if reject_rules:
            top = reject_rules[0]
            return PolicyResult(
                decision=Decision.REJECT,
                matched_rules=reject_rules,
                reason=f"Blocked by rule '{top.id}': {top.description}",
            )

        # Among remaining, highest priority wins
        top = matched[0]
        return PolicyResult(
            decision=top.decision,
            matched_rules=matched,
            reason=f"Rule '{top.id}': {top.description}",
        )

    def _matches(self, rule: PolicyRule, request: DeployRequest) -> bool:
        """Check if a rule's condition matches the request."""
        value = self._get_field(rule.field, request)
        if value is None:
            return False

        op = rule.operator
        rule_values = rule.values

        if op == "in":
            return str(value).lower() in [str(v).lower() for v in rule_values]
        elif op == "equals":
            return value == rule_values[0] if rule_values else False
        elif op == "matches":
            # Check if action contains any of the keywords
            val_str = str(value).lower()
            return any(str(v).lower() in val_str for v in rule_values)
        elif op == "gt":
            try:
                return float(value) > float(rule_values[0])
            except (ValueError, TypeError):
                return False
        elif op == "lt":
            try:
                return float(value) < float(rule_values[0])
            except (ValueError, TypeError):
                return False
        elif op == "gte":
            try:
                return float(value) >= float(rule_values[0])
            except (ValueError, TypeError):
                return False
        elif op == "not_in":
            return str(value).lower() not in [str(v).lower() for v in rule_values]

        return False

    def _get_field(self, field_name: str, request: DeployRequest) -> Any:
        """Extract a field value from the request."""
        if hasattr(request, field_name):
            return getattr(request, field_name)
        return request.extra.get(field_name)
