"""Agents-as-tools orchestration with self-consistency routing.

This module sits *above* :class:`~src.agents.ai.supervisor.Supervisor` and reuses
it for the actual A2A delegation — it never mutates state itself, preserving the
delegation boundary documented in ``supervisor.py``. It adds two capabilities on
top of the single-shot deterministic router:

1. **Self-consistency routing** — the routing decision is sampled ``N`` times and
   majority-voted. When agreement is weak, it falls back to the deterministic
   :func:`~src.agents.ai.supervisor.classify_request`. This mirrors the
   reconciliation-gate philosophy (``reconciliation.py``): a deterministic
   backstop wins over an unsupported / self-inconsistent model call.

2. **Agents-as-tools orchestration** — a compound instruction ("provision a
   cluster *then* deploy orders-api") is decomposed into an ordered plan of
   specialist steps, each delegated through the existing ``Supervisor.handle``.
   The specialists become tools the orchestrator chains, sharing one A2A
   ``contextId`` across steps.

Both are non-breaking: the default ``sampler`` and ``planner`` are the
deterministic classifier and a single-step plan, so with defaults the outcome is
identical to calling ``Supervisor.handle`` directly (``agreement == 1.0``, never
falls back, one step).
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Callable

from src.agents.ai.supervisor import (
    AgentRole,
    RouteDecision,
    Supervisor,
    SupervisorOutcome,
    classify_request,
)

# A classifier maps an instruction to a single routing decision. ``classify_request``
# is the deterministic backstop; an injected LLM-backed classifier (which may
# disagree with itself across calls) is what makes self-consistency meaningful.
Classifier = Callable[[str], RouteDecision]


@dataclass(frozen=True)
class RouteConsensus:
    """Outcome of a self-consistency vote over a routing decision."""

    decision: RouteDecision
    agreement: float
    votes: dict[str, int]
    samples: int
    fell_back: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "role": self.decision.role.value,
            "reason": self.decision.reason,
            "agreement": round(self.agreement, 4),
            "votes": self.votes,
            "samples": self.samples,
            "fell_back": self.fell_back,
        }

    def trace_frame(self) -> dict[str, Any]:
        return {"kind": "consensus", **self.to_dict()}


def route_with_self_consistency(
    instruction: str,
    *,
    sampler: Classifier = classify_request,
    fallback: Classifier = classify_request,
    samples: int = 5,
    min_agreement: float = 0.6,
) -> RouteConsensus:
    """Vote on a routing decision, falling back to a deterministic classifier.

    ``sampler`` is called ``samples`` times and the plurality role wins. When the
    winning share (``agreement``) is below ``min_agreement`` — the samples
    disagree too much to trust — the decision is replaced by ``fallback``
    (deterministic) and ``fell_back`` is set. With the default sampler every call
    returns the same role, so ``agreement`` is always ``1.0`` and the fallback
    never triggers: behavior is identical to the single-shot classifier.
    """
    if samples < 1:
        raise ValueError("samples must be >= 1")

    sampled = [sampler(instruction) for _ in range(samples)]
    votes = Counter(decision.role for decision in sampled)
    winner_role, winner_count = votes.most_common(1)[0]
    agreement = winner_count / samples

    if agreement >= min_agreement:
        # Preserve a real reason string by reusing the first sample that voted
        # for the winning role, rather than synthesizing one.
        decision = next(d for d in sampled if d.role == winner_role)
        fell_back = False
    else:
        decision = fallback(instruction)
        fell_back = True

    return RouteConsensus(
        decision=decision,
        agreement=agreement,
        votes={role.value: count for role, count in votes.items()},
        samples=samples,
        fell_back=fell_back,
    )


@dataclass(frozen=True)
class PlanStep:
    """One specialist step in an orchestration plan."""

    decision: RouteDecision
    instruction: str


# A planner decomposes a (possibly compound) instruction into an ordered list of
# specialist steps, given the consensus decision for the primary route.
Planner = Callable[[str, RouteDecision], "list[PlanStep]"]


def single_step_planner(instruction: str, primary: RouteDecision) -> list[PlanStep]:
    """Default planner: one step routed by the consensus decision.

    Behavior-preserving — the whole instruction is delegated to the single
    consensus-selected specialist, exactly as ``Supervisor.handle`` does today.
    """
    return [PlanStep(primary, instruction)]


@dataclass
class OrchestratorOutcome:
    """Result of orchestrating one request across one or more specialists.

    Duck-types :class:`SupervisorOutcome` (``decision`` / ``delegated`` /
    ``response`` / ``trace``) so existing gateway formatting and artifact code can
    consume it unchanged.
    """

    consensus: RouteConsensus
    steps: list[SupervisorOutcome]
    delegated: bool
    response: dict[str, Any] | None = None
    trace: list[dict[str, Any]] = field(default_factory=list)

    @property
    def decision(self) -> RouteDecision:
        """The primary (consensus) routing decision."""
        return self.consensus.decision


class Orchestrator:
    """Route with self-consistency, then chain specialist delegations as tools."""

    def __init__(
        self,
        supervisor: Supervisor,
        *,
        sampler: Classifier = classify_request,
        fallback: Classifier = classify_request,
        planner: Planner = single_step_planner,
        samples: int = 5,
        min_agreement: float = 0.6,
    ):
        self._supervisor = supervisor
        self._sampler = sampler
        self._fallback = fallback
        self._planner = planner
        self._samples = samples
        self._min_agreement = min_agreement

    @classmethod
    def from_environment(
        cls,
        *,
        sampler: Classifier = classify_request,
        fallback: Classifier = classify_request,
        planner: Planner = single_step_planner,
        samples: int = 5,
        min_agreement: float = 0.6,
    ) -> "Orchestrator":
        """Build an orchestrator over a supervisor wired from operator env vars."""
        return cls(
            Supervisor.from_environment(),
            sampler=sampler,
            fallback=fallback,
            planner=planner,
            samples=samples,
            min_agreement=min_agreement,
        )

    def handle(self, instruction: str, *, context_id: str | None = None) -> OrchestratorOutcome:
        consensus = route_with_self_consistency(
            instruction,
            sampler=self._sampler,
            fallback=self._fallback,
            samples=self._samples,
            min_agreement=self._min_agreement,
        )
        trace: list[dict[str, Any]] = [consensus.trace_frame()]

        steps = self._planner(instruction, consensus.decision)
        step_outcomes: list[SupervisorOutcome] = []
        plan_steps_trace: list[dict[str, Any]] = []
        for step in steps:
            # Each specialist is "a tool": reuse Supervisor.handle verbatim for
            # discovery, capability-match, A2A transport and messageId handling.
            outcome = self._supervisor.handle(step.instruction, context_id=context_id)
            step_outcomes.append(outcome)
            plan_steps_trace.append(
                {
                    "role": step.decision.role.value,
                    "instruction": step.instruction,
                    "delegated": outcome.delegated,
                    "trace": outcome.trace,
                }
            )
            # Short-circuit the chain the moment a step fails to delegate, so a
            # broken provision step never triggers a dependent deploy step.
            if not outcome.delegated:
                break

        trace.append({"kind": "plan", "steps": plan_steps_trace})

        # The plan is "delegated" only if every planned step actually delegated.
        delegated = bool(step_outcomes) and len(step_outcomes) == len(steps) and all(
            o.delegated for o in step_outcomes
        )
        response = step_outcomes[-1].response if step_outcomes else None

        return OrchestratorOutcome(
            consensus=consensus,
            steps=step_outcomes,
            delegated=delegated,
            response=response,
            trace=trace,
        )


__all__ = [
    "AgentRole",
    "Classifier",
    "Orchestrator",
    "OrchestratorOutcome",
    "PlanStep",
    "Planner",
    "RouteConsensus",
    "route_with_self_consistency",
    "single_step_planner",
]
