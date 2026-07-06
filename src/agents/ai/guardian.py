"""
Guardian Agent — Policy-as-Code deployment gatekeeper.

Evaluates deployment requests against YAML-defined policies to determine
whether a deployment should proceed (AUTO), require approval (APPROVE),
or be blocked (REJECT).

Usage:
    from src.agents.ai.guardian import create_guardian_agent, evaluate_deploy_request

    # Direct evaluation (no LLM needed)
    result = evaluate_deploy_request(environment="prod", action="deploy", replicas=3)

    # Agent-based evaluation (LLM reasons about edge cases)
    agent = create_guardian_agent()
    response = agent("Should I deploy orders-api v2.0 to production with 5 replicas?")
"""

from __future__ import annotations

from typing import Any

from strands import Agent
from strands.tools import tool

from src.agents.ai.policy_engine import Decision, DeployRequest, PolicyEngine, PolicyResult


# Singleton engine instance (loaded once)
_engine: PolicyEngine | None = None


def _get_engine() -> PolicyEngine:
    """Get or create the singleton policy engine."""
    global _engine
    if _engine is None:
        _engine = PolicyEngine.from_default()
    return _engine


@tool
def evaluate_policy(
    environment: str = "dev",
    action: str = "deploy",
    service_name: str = "",
    replicas: int = 1,
    provider: str = "local",
    namespace: str = "default",
    cross_region: bool = False,
    version: str = "",
) -> dict:
    """Evaluate a deployment request against the policy rules.

    Args:
        environment: Target environment (dev, staging, prod).
        action: Deployment action (deploy, rollback, delete, scale).
        service_name: Name of the service being deployed.
        replicas: Number of replicas requested.
        provider: Cloud provider (local, aws, gcp, azure).
        namespace: Kubernetes namespace.
        cross_region: Whether this is a cross-region deployment.
        version: Version being deployed.

    Returns:
        Dict with decision (APPROVE/AUTO/REJECT), reason, and matched rules.
    """
    request = DeployRequest(
        environment=environment,
        action=action,
        service_name=service_name,
        replicas=replicas,
        provider=provider,
        namespace=namespace,
        cross_region=cross_region,
        version=version,
    )

    engine = _get_engine()
    result = engine.evaluate(request)

    return {
        "decision": result.decision.value,
        "reason": result.reason,
        "matched_rules": [
            {"id": r.id, "description": r.description, "priority": r.priority}
            for r in result.matched_rules
        ],
        "request": {
            "environment": environment,
            "action": action,
            "service_name": service_name,
            "replicas": replicas,
            "provider": provider,
        },
    }


@tool
def list_policy_rules() -> dict:
    """List all active policy rules and their conditions.

    Returns:
        Dict with all rules, sorted by priority (highest first).
    """
    engine = _get_engine()
    rules = []
    for r in engine._rules:
        rules.append({
            "id": r.id,
            "description": r.description,
            "field": r.field,
            "operator": r.operator,
            "values": r.values,
            "decision": r.decision.value,
            "priority": r.priority,
        })
    return {"rules": rules, "default_decision": engine._default_decision.value}


GUARDIAN_TOOLS = [evaluate_policy, list_policy_rules]


GUARDIAN_SYSTEM_PROMPT = """\
You are a Guardian Agent — a deployment policy gatekeeper. Your job is to evaluate
deployment requests against the organization's policy rules and provide clear decisions.

## Your Role

When asked about a deployment, you MUST:
1. Use `evaluate_policy` to check the request against the rules.
2. Report the decision clearly: APPROVE, AUTO, or REJECT.
3. Explain WHY based on which rule matched.

## Decisions

- **AUTO** — Deployment can proceed without human intervention.
- **APPROVE** — Deployment requires human approval before proceeding.
- **REJECT** — Deployment is blocked and cannot proceed.

## Rules

- REJECT always wins, regardless of priority.
- Higher priority rules take precedence over lower ones.
- If no rules match, the default is AUTO.

## Safety

- You CANNOT override policy decisions.
- You CANNOT modify policy rules.
- You CAN explain why a request was blocked and suggest alternatives.
- When unsure, use `list_policy_rules` to show the active policies.

## Response Format

Always include:
1. The decision (APPROVE/AUTO/REJECT)
2. The rule that matched (ID + description)
3. If REJECT: suggest what the user can do differently
"""


def create_guardian_agent(
    model: str | None = None,
    **kwargs: Any,
) -> Agent:
    """Create a Guardian Agent for policy evaluation.

    Args:
        model: Model ID override. Defaults to Bedrock Claude if None.
        **kwargs: Additional Agent constructor arguments.

    Returns:
        Configured Strands Agent instance.
    """
    agent_kwargs: dict[str, Any] = {
        "system_prompt": GUARDIAN_SYSTEM_PROMPT,
        "tools": GUARDIAN_TOOLS,
        **kwargs,
    }

    if model:
        agent_kwargs["model"] = model

    return Agent(**agent_kwargs)


def evaluate_deploy_request(
    environment: str = "dev",
    action: str = "deploy",
    service_name: str = "",
    replicas: int = 1,
    provider: str = "local",
    namespace: str = "default",
    cross_region: bool = False,
    version: str = "",
) -> PolicyResult:
    """Direct policy evaluation without LLM (for programmatic use).

    Returns:
        PolicyResult with decision, matched rules, and reason.
    """
    request = DeployRequest(
        environment=environment,
        action=action,
        service_name=service_name,
        replicas=replicas,
        provider=provider,
        namespace=namespace,
        cross_region=cross_region,
        version=version,
    )
    return _get_engine().evaluate(request)
