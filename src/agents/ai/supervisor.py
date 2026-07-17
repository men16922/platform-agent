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
import uuid
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Callable, Protocol
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
    """Choose a specialist without invoking an LLM or executing any tool.

    Precedence, not first-substring-wins: an explicit *intent verb* beats an
    incidental keyword that shares the sentence. This resolves two over-triggers
    the eval harness surfaced — "Investigate why the terraform apply failed" is
    diagnosis (not provisioning, despite "terraform"), and "Deploy the
    observability stack" is delivery (not investigation, despite "observability").
    """
    text = instruction.lower()

    # 1. An explicit diagnostic verb/question is read-only investigation even when
    #    a provisioning noun (terraform, ansible) shares the sentence — the leading
    #    intent wins over the incidental keyword.
    if any(term in text for term in ("diagnose", "investigate", "troubleshoot", "debug", "why is", "why are", "why did")):
        return RouteDecision(AgentRole.KAGENT, "read-only cluster investigation request")

    # 2. Provisioning: explicit infra terms, or a cluster-creation verb applied to
    #    a named cluster ("create a GKE cluster", "spin up a kind cluster") where
    #    the literal "create cluster" bigram is split by the cluster's name.
    provision_terms = ("provision", "terraform", "ansible", "create cluster", "setup cluster", "set up cluster")
    creation_verbs = ("create", "spin up", "spin-up", "stand up", "stand-up", "bootstrap")
    if any(term in text for term in provision_terms) or (
        "cluster" in text and any(verb in text for verb in creation_verbs)
    ):
        return RouteDecision(AgentRole.PROVISION, "explicit infrastructure or cluster provisioning request")

    # 3. Weaker investigation *nouns* (a resource named without a diagnostic verb)
    #    still read as a look — unless a delivery verb leads, since deploying an
    #    observability/logging stack is delivery, not investigation. ("observability"
    #    was dropped as a standalone trigger: it names deploy and diagnose targets
    #    alike, so it was a poor routing signal.)
    delivery_verbs = ("deploy", "ship ", "install", "release", "roll out", "rollout", "promote")
    investigation_nouns = ("logs", "log ", "pods", "pod ", "namespace", "promql", "istio", "status")
    if not any(v in text for v in delivery_verbs) and any(n in text for n in investigation_nouns):
        return RouteDecision(AgentRole.KAGENT, "read-only cluster investigation request")

    return RouteDecision(AgentRole.DEPLOY, "delivery request or default operational handoff")


# The maximum length of untrusted instruction text forwarded across the A2A
# boundary. A specialist agent needs the request, not an unbounded payload: a huge
# or padded instruction is capped so it cannot exhaust the downstream agent or
# smuggle a wall of injected directives past a truncating log.
MAX_DELEGATED_INSTRUCTION = 4000


def sanitize_instruction(
    text: str, *, max_len: int = MAX_DELEGATED_INSTRUCTION
) -> tuple[str, list[str]]:
    """Bound and clean untrusted instruction text before it crosses the A2A boundary.

    The supervisor forwards a caller's natural-language request verbatim to a
    specialist agent; that text is untrusted. This strips C0/C1 control characters
    (except tab and newline) that could smuggle terminal escapes or protocol
    confusion downstream, and caps the length. It returns the cleaned text plus a
    list of applied-transform names for the audit trace — a clean, in-bounds input
    returns ``(text, [])`` unchanged, so normal requests are unaffected.

    This is a defensive bound, not a parser: it does not attempt to detect or
    neutralise prompt-injection *content* (that is the specialist server's job,
    via a fixed system prompt) — it only ensures what we forward is well-formed
    and bounded.
    """
    notes: list[str] = []
    cleaned = "".join(ch for ch in text if ch in "\t\n" or ord(ch) >= 0x20)
    if cleaned != text:
        notes.append("stripped_control_chars")
    if len(cleaned) > max_len:
        cleaned = cleaned[:max_len].rstrip() + " …[truncated]"
        notes.append("truncated")
    return cleaned, notes


Transport = Callable[[str, dict[str, Any]], dict[str, Any]]
CardFetcher = Callable[[str], dict[str, Any]]

ENDPOINT_ENV: dict[AgentRole, str] = {
    AgentRole.PROVISION: "PLATFORM_PROVISION_A2A_URL",
    AgentRole.DEPLOY: "PLATFORM_DEPLOY_A2A_URL",
    AgentRole.KAGENT: "PLATFORM_KAGENT_A2A_URL",
}


# Least-privilege blast radius per specialist role — the action verbs each role
# is permitted to perform. Forwarded as a `metadata.allowedActions` hint so a
# specialist knows its own bound, and single-sourced with the eval harness's
# `action_sink_grader` (which fails a role that acted outside this set). KAGENT is
# read-only: an empty set means "no mutation permitted".
ROLE_ALLOWED_ACTIONS: dict[AgentRole, frozenset[str]] = {
    AgentRole.PROVISION: frozenset({"provision", "teardown"}),
    AgentRole.DEPLOY: frozenset({"deploy", "rollback", "rollout_restart", "rollout_undo", "scale"}),
    AgentRole.KAGENT: frozenset(),
}


def post_a2a_message(endpoint: str, body: dict[str, Any], *, timeout: float = 10.0) -> dict[str, Any]:
    """Send one A2A ``message:send`` request using only the standard library."""
    url = endpoint if body.get("jsonrpc") == "2.0" else f"{endpoint.rstrip('/')}/message:send"
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
    # Provisioning-specific terms only. Generic "cluster" is avoided here because
    # diagnostic/deploy skills also mention "Kubernetes cluster" in their text — a
    # diagnostic-only Agent Card must not be accepted as an infrastructure provisioner.
    AgentRole.PROVISION: ("provision", "terraform", "ansible", "infrastructure"),
    AgentRole.DEPLOY: ("deploy", "rollback", "validation", "delivery"),
    # Diagnostic-specific terms only. Generic "kubernetes"/"cluster" are avoided
    # here because deploy skills also carry those tags — a deploy-only Agent Card
    # must not be accepted as a read-only kagent diagnostic specialist.
    AgentRole.KAGENT: ("diagnostic", "troubleshoot", "observability", "investigat", "debug", "logs"),
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


class RoutingConfidence(Protocol):
    """Structural type for a self-consistency vote — satisfied by
    :class:`~src.agents.ai.orchestration.RouteConsensus` without importing it
    (which would be a cycle: orchestration already imports this module)."""

    decision: RouteDecision
    agreement: float


# An optional confidence router replaces the deterministic classifier with a voted
# decision carrying an agreement signal. Injected, so the default path stays
# LLM-free and offline.
ConfidenceRouter = Callable[[str], RoutingConfidence]


class Supervisor:
    """Route requests to registered provision, deploy, or kagent A2A agents."""

    def __init__(
        self,
        endpoints: dict[AgentRole, str] | None = None,
        *,
        transport: Transport = post_a2a_message,
        card_fetcher: CardFetcher = fetch_agent_card,
        confidence_router: ConfidenceRouter | None = None,
        min_agreement: float = 0.6,
    ):
        self._endpoints = endpoints or {}
        self._transport = transport
        self._card_fetcher = card_fetcher
        self._confidence_router = confidence_router
        self._min_agreement = min_agreement

    @classmethod
    def from_environment(
        cls,
        *,
        transport: Transport = post_a2a_message,
        card_fetcher: CardFetcher = fetch_agent_card,
        confidence_router: ConfidenceRouter | None = None,
        min_agreement: float = 0.6,
    ) -> "Supervisor":
        """Build the production registry from explicit operator-provided URLs."""
        endpoints = {
            role: endpoint
            for role, variable in ENDPOINT_ENV.items()
            if (endpoint := os.getenv(variable))
        }
        return cls(
            endpoints,
            transport=transport,
            card_fetcher=card_fetcher,
            confidence_router=confidence_router,
            min_agreement=min_agreement,
        )

    def handle(self, instruction: str, *, context_id: str | None = None) -> SupervisorOutcome:
        # Default path: deterministic, LLM-free. With a confidence router injected,
        # a low-agreement vote is *gated* (refused) rather than delegated on a
        # coin-flip — the same reconciliation philosophy used elsewhere.
        if self._confidence_router is not None:
            consensus = self._confidence_router(instruction)
            decision = consensus.decision
            trace: list[dict[str, Any]] = [
                {"kind": "route", "role": decision.role.value, "reason": decision.reason,
                 "agreement": round(consensus.agreement, 4)}
            ]
            if consensus.agreement < self._min_agreement:
                trace.append({"kind": "gated", "reason": "low_confidence",
                              "agreement": round(consensus.agreement, 4), "role": decision.role.value})
                return SupervisorOutcome(decision=decision, delegated=False, trace=trace)
        else:
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

        # The instruction is untrusted caller text; classification ran on the full
        # original, but what we forward across the A2A boundary is bounded/cleaned.
        safe_instruction, sanitize_notes = sanitize_instruction(instruction)
        if sanitize_notes:
            trace.append({"kind": "sanitize", "applied": sanitize_notes})

        message: dict[str, Any] = {
            # messageId is a required field on the A2A Message object; the
            # spec-compliant a2a SDK (e.g. kagent's server) rejects a
            # message/send whose params.message omits it (JSON-RPC -32602).
            "messageId": str(uuid.uuid4()),
            "role": "ROLE_USER",
            "parts": [{"text": safe_instruction}],
            "metadata": {
                "supervisorRole": decision.role.value,
                "matchedSkills": skills,
                # Least-privilege hint: the blast radius this role is allowed. A
                # read-only kagent carries an empty list.
                "allowedActions": sorted(ROLE_ALLOWED_ACTIONS[decision.role]),
                # Structured delegation descriptor: a single trusted object a
                # specialist can act on without parsing the free-text instruction.
                # The free-text `parts` stays for back-compat; params extraction is
                # a deliberate follow-up (see docs/plans/a2a-delegation-hardening.md).
                "task": {
                    "type": decision.role.value,
                    "origin": "supervisor",
                    "skills": skills,
                    "allowedActions": sorted(ROLE_ALLOWED_ACTIONS[decision.role]),
                },
            },
        }
        if context_id:
            message["contextId"] = context_id
        preferred_transport = str(card.get("preferredTransport", "HTTP+JSON")).upper()
        target = str(card.get("url") or endpoint)
        payload: dict[str, Any]
        if preferred_transport == "JSONRPC":
            message["role"] = "user"
            payload = {
                "jsonrpc": "2.0",
                "id": str(uuid.uuid4()),
                "method": "message/send",
                "params": {"message": message},
            }
        else:
            payload = {"message": message}
        try:
            response = self._transport(target, payload)
        except Exception as error:
            trace.append({"kind": "delegation", "status": "failed", "role": decision.role.value})
            return SupervisorOutcome(decision=decision, delegated=False, response={"error": str(error)}, trace=trace)

        trace.append({"kind": "delegation", "status": "sent", "role": decision.role.value})
        return SupervisorOutcome(decision=decision, delegated=True, response=response, trace=trace)
