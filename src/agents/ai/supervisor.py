"""Supervisor routing for the platform's specialist A2A agents.

The deployment pipeline remains responsible for executing a deployment. This
module sits above it: it classifies a natural-language request and delegates it
to a registered specialist through the A2A HTTP binding. Keeping the delegation
boundary explicit prevents the supervisor from silently performing mutating
provision or deployment work itself.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Callable
from urllib import request


class AgentRole(StrEnum):
    """Specialist roles exposed through the A2A boundary."""

    PROVISION = "provision"
    DEPLOY = "deploy"
    KAGENT = "kagent"


@dataclass(frozen=True)
class RouteDecision:
    """A deterministic supervisor decision, suitable for an audit trace."""

    role: AgentRole
    reason: str


@dataclass
class SupervisorOutcome:
    """Result of classifying and optionally delegating one user request."""

    decision: RouteDecision
    delegated: bool
    response: dict[str, Any] | None = None
    trace: list[dict[str, Any]] = field(default_factory=list)


def classify_request(instruction: str) -> RouteDecision:
    """Choose a specialist without invoking an LLM or executing any tool."""
    text = instruction.lower()
    if any(term in text for term in ("provision", "terraform", "ansible", "create cluster", "setup cluster", "set up cluster")):
        return RouteDecision(AgentRole.PROVISION, "explicit infrastructure or cluster provisioning request")
    if any(term in text for term in ("diagnose", "investigate", "debug", "logs", "log ", "pods", "pod ", "namespace", "promql", "istio", "observability", "why is", "why are", "status")):
        return RouteDecision(AgentRole.KAGENT, "read-only cluster investigation request")
    return RouteDecision(AgentRole.DEPLOY, "delivery request or default operational handoff")


Transport = Callable[[str, dict[str, Any]], dict[str, Any]]
CardFetcher = Callable[[str], dict[str, Any]]

ENDPOINT_ENV: dict[AgentRole, str] = {
    AgentRole.PROVISION: "PLATFORM_PROVISION_A2A_URL",
    AgentRole.DEPLOY: "PLATFORM_DEPLOY_A2A_URL",
    AgentRole.KAGENT: "PLATFORM_KAGENT_A2A_URL",
}


def post_a2a_message(endpoint: str, body: dict[str, Any], *, timeout: float = 10.0) -> dict[str, Any]:
    """Send one A2A ``message:send`` request using only the standard library."""
    url = f"{endpoint.rstrip('/')}/message:send"
    payload = json.dumps(body).encode("utf-8")
    http_request = request.Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
    with request.urlopen(http_request, timeout=timeout) as response:  # noqa: S310 - endpoint is operator configuration
        return json.loads(response.read().decode("utf-8"))


def fetch_agent_card(endpoint: str, *, timeout: float = 10.0) -> dict[str, Any]:
    """Discover an A2A agent card from its standard well-known endpoint."""
    url = f"{endpoint.rstrip('/')}/.well-known/agent-card.json"
    with request.urlopen(url, timeout=timeout) as response:  # noqa: S310 - endpoint is operator configuration
        card = json.loads(response.read().decode("utf-8"))
    if not isinstance(card, dict) or not isinstance(card.get("name"), str) or not isinstance(card.get("skills"), list):
        raise ValueError("invalid Agent Card: expected name and skills")
    return card


ROLE_SKILL_TERMS: dict[AgentRole, tuple[str, ...]] = {
    AgentRole.PROVISION: ("provision", "terraform", "ansible", "cluster"),
    AgentRole.DEPLOY: ("deploy", "rollback", "validation", "delivery"),
    AgentRole.KAGENT: ("diagnostic", "troubleshoot", "observability", "kubernetes", "cluster"),
}


def matching_skills(card: dict[str, Any], role: AgentRole) -> list[str]:
    """Return skill IDs whose declared capability can serve ``role``."""
    terms = ROLE_SKILL_TERMS[role]
    matches: list[str] = []
    for skill in card.get("skills", []):
        if not isinstance(skill, dict) or not isinstance(skill.get("id"), str):
            continue
        searchable = " ".join(
            str(value)
            for value in (skill.get("id"), skill.get("name"), skill.get("description"), *(skill.get("tags") or []))
        ).lower()
        if any(term in searchable for term in terms):
            matches.append(skill["id"])
    return matches


class Supervisor:
    """Route requests to registered provision, deploy, or kagent A2A agents."""

    def __init__(
        self,
        endpoints: dict[AgentRole, str] | None = None,
        *,
        transport: Transport = post_a2a_message,
        card_fetcher: CardFetcher = fetch_agent_card,
    ):
        self._endpoints = endpoints or {}
        self._transport = transport
        self._card_fetcher = card_fetcher

    @classmethod
    def from_environment(
        cls, *, transport: Transport = post_a2a_message, card_fetcher: CardFetcher = fetch_agent_card
    ) -> "Supervisor":
        """Build the production registry from explicit operator-provided URLs."""
        endpoints = {
            role: endpoint
            for role, variable in ENDPOINT_ENV.items()
            if (endpoint := os.getenv(variable))
        }
        return cls(endpoints, transport=transport, card_fetcher=card_fetcher)

    def handle(self, instruction: str, *, context_id: str | None = None) -> SupervisorOutcome:
        decision = classify_request(instruction)
        trace = [{"kind": "route", "role": decision.role.value, "reason": decision.reason}]
        endpoint = self._endpoints.get(decision.role)
        if not endpoint:
            trace.append({"kind": "delegation", "status": "not_configured", "role": decision.role.value})
            return SupervisorOutcome(decision=decision, delegated=False, trace=trace)

        try:
            card = self._card_fetcher(endpoint)
            skills = matching_skills(card, decision.role)
        except Exception as error:
            trace.append({"kind": "discovery", "status": "failed", "role": decision.role.value})
            return SupervisorOutcome(decision=decision, delegated=False, response={"error": str(error)}, trace=trace)
        if not skills:
            trace.append({"kind": "discovery", "status": "capability_mismatch", "role": decision.role.value})
            return SupervisorOutcome(
                decision=decision,
                delegated=False,
                response={"error": f"Agent Card has no {decision.role} skill", "agent": card.get("name")},
                trace=trace,
            )
        trace.append({"kind": "discovery", "status": "matched", "agent": card["name"], "skills": skills})

        message: dict[str, Any] = {
            "role": "ROLE_USER",
            "parts": [{"text": instruction}],
            "metadata": {"supervisorRole": decision.role.value, "matchedSkills": skills},
        }
        if context_id:
            message["contextId"] = context_id
        try:
            response = self._transport(endpoint, {"message": message})
        except Exception as error:
            trace.append({"kind": "delegation", "status": "failed", "role": decision.role.value})
            return SupervisorOutcome(decision=decision, delegated=False, response={"error": str(error)}, trace=trace)

        trace.append({"kind": "delegation", "status": "sent", "role": decision.role.value})
        return SupervisorOutcome(decision=decision, delegated=True, response=response, trace=trace)
