"""Offline model/parameter sweep for the routing Model Router (cwc follow-up ⑦).

The Model Router today carries only fit *annotations* — "this model suits that
task" — with no measurement behind them. This runs a ``model × thinking × effort``
grid against the labeled routing dataset and records a cost/latency headline per
config (``cost_per_success``, ``seconds_per_success``), turning a static annotation
into an evidence-based pick.

**No real API call lives here.** The LLM backend is injected as a
``router_factory`` (config -> :data:`~src.agents.ai.eval_harness.ObservingRouter`)
plus a ``cost_per_call`` model, so the sweep runs fully offline — the unit suite
drives it with a deterministic mock backend. Wiring a live model behind an env flag,
and paying for the real spend, is a user-gated step: build a ``router_factory`` that
actually calls the model and pass it to :func:`run_sweep`.

The runner is **resumable**: hand back the points already computed (``done=``) and it
skips those configs, so a long paid sweep can stop and continue without re-spending.
It reuses the eval harness's self-consistency majority vote (``trials``) and grading
so the accuracy number here is the same one the scorecard reports.
"""

from __future__ import annotations

import math
import time
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any, Callable

from src.agents.ai.eval_harness import (
    ROUTING_EVAL_SET,
    EvalCase,
    Observation,
    ObservingRouter,
    _majority_observation,
)
from src.agents.ai.supervisor import AgentRole, RouteDecision, classify_request

# A plain role router — the deterministic classifier's shape, used as the live
# adapter's backstop.
Router = Callable[[str], RouteDecision]
# A router factory turns one sweep config into a router under test. In tests this
# is a deterministic mock; in a live run it is a closure that calls the model.
RouterFactory = Callable[["SweepConfig"], ObservingRouter]
# Cost of a single model call for a config, in USD. Injected so the sweep never
# hard-codes a price list that would drift.
CostModel = Callable[["SweepConfig"], float]


@dataclass(frozen=True)
class SweepConfig:
    """One point in the model/parameter grid."""

    model: str
    thinking: bool = False
    effort: str = "medium"

    def key(self) -> str:
        """Stable identity used for resume dedup and result keys."""
        return f"{self.model}|thinking={self.thinking}|effort={self.effort}"


@dataclass(frozen=True)
class SweepPoint:
    """The measured result for one config over the dataset."""

    config: SweepConfig
    successes: int
    total: int
    cost_usd: float
    seconds: float
    trials: int

    @property
    def pass_rate(self) -> float:
        return self.successes / self.total if self.total else 1.0

    @property
    def cost_per_success(self) -> float:
        """USD spent per correct routing. ``inf`` when nothing was routed right —
        a config you cannot buy a success from at any price."""
        return self.cost_usd / self.successes if self.successes else math.inf

    @property
    def seconds_per_success(self) -> float:
        return self.seconds / self.successes if self.successes else math.inf

    def to_dict(self) -> dict[str, Any]:
        return {
            "config": {
                "model": self.config.model,
                "thinking": self.config.thinking,
                "effort": self.config.effort,
            },
            "successes": self.successes,
            "total": self.total,
            "cost_usd": round(self.cost_usd, 6),
            "seconds": round(self.seconds, 4),
            "trials": self.trials,
            "pass_rate": round(self.pass_rate, 4),
            "cost_per_success": self.cost_per_success,
            "seconds_per_success": self.seconds_per_success,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "SweepPoint":
        c = d["config"]
        return cls(
            config=SweepConfig(c["model"], c.get("thinking", False), c.get("effort", "medium")),
            successes=d["successes"],
            total=d["total"],
            cost_usd=d["cost_usd"],
            seconds=d["seconds"],
            trials=d.get("trials", 1),
        )


def grid(
    models: Sequence[str],
    *,
    thinking: Sequence[bool] = (False,),
    effort: Sequence[str] = ("medium",),
) -> list[SweepConfig]:
    """Cartesian product of the axes into a flat config list (stable order)."""
    return [
        SweepConfig(m, t, e)
        for m in models
        for t in thinking
        for e in effort
    ]


def run_sweep(
    configs: Iterable[SweepConfig],
    router_factory: RouterFactory,
    *,
    cost_per_call: CostModel,
    dataset: list[EvalCase] | None = None,
    trials: int = 1,
    done: Iterable[SweepPoint] = (),
) -> list[SweepPoint]:
    """Grade every config in ``configs`` over ``dataset`` and record its
    cost/latency headline.

    For each config not already present in ``done`` (matched by
    :meth:`SweepConfig.key`, so the runner is resumable), the config's router is
    built once and run over the dataset; routing accuracy is the majority vote over
    ``trials`` samples, cost is ``cost_per_call(config) * calls``, and latency is the
    summed observed ``latency_s``. Previously-computed points are returned unchanged
    at the front, so a caller can persist and re-feed results across runs.
    """
    cases = dataset if dataset is not None else ROUTING_EVAL_SET
    points: list[SweepPoint] = list(done)
    seen = {p.config.key() for p in points}

    for cfg in configs:
        if cfg.key() in seen:
            continue
        seen.add(cfg.key())
        router = router_factory(cfg)
        successes = 0
        seconds = 0.0
        calls = 0
        for case in cases:
            obs = _majority_observation(router, case.instruction, trials)
            calls += max(1, trials)
            seconds += obs.latency_s
            if obs.decision.role == case.expected_role:
                successes += 1
        points.append(
            SweepPoint(
                config=cfg,
                successes=successes,
                total=len(cases),
                cost_usd=cost_per_call(cfg) * calls,
                seconds=seconds,
                trials=trials,
            )
        )
    return points


# Ranking keys: lower is better for cost/latency-per-success; higher for accuracy.
_RANK_KEYS: dict[str, Callable[[SweepPoint], float]] = {
    "cost_per_success": lambda p: p.cost_per_success,
    "seconds_per_success": lambda p: p.seconds_per_success,
    "pass_rate": lambda p: -p.pass_rate,  # negate so ascending sort puts best first
}


def rank(points: list[SweepPoint], *, by: str = "cost_per_success") -> list[SweepPoint]:
    """Sort points best-first by ``by`` — one of ``cost_per_success``,
    ``seconds_per_success``, ``pass_rate``. Ties break on higher pass rate then
    lower cost, so the ranking is deterministic."""
    if by not in _RANK_KEYS:
        raise ValueError(f"unknown rank key '{by}'; choose from {sorted(_RANK_KEYS)}")
    primary = _RANK_KEYS[by]
    return sorted(points, key=lambda p: (primary(p), -p.pass_rate, p.cost_usd))


def best(points: list[SweepPoint], *, by: str = "cost_per_success") -> SweepPoint | None:
    """The single best point by ``by``, or ``None`` for an empty sweep."""
    ranked = rank(points, by=by)
    return ranked[0] if ranked else None


def scoreboard(points: list[SweepPoint], *, by: str = "cost_per_success") -> list[dict[str, Any]]:
    """A ranked, serialisable table (list of :meth:`SweepPoint.to_dict`) for
    logging or a dashboard."""
    return [p.to_dict() for p in rank(points, by=by)]


# --- live router factory (⑦ execution adapter) -------------------------------
# The scaffold above is backend-agnostic. This turns a real model call into a
# RouterFactory so the sweep can grade actual models — but the model call is still
# *injected*: `call_model(config, prompt) -> reply`. No credentials or network live
# here; a stub drives it offline in tests, a real client (with creds, and real
# spend) drives it live.

# A model call: given a config and a prompt, return the model's raw reply text.
ModelCall = Callable[["SweepConfig", str], str]


def _classify_prompt(instruction: str) -> str:
    # Mirrors the product routing semantics (classify_request / ROUTING_EVAL_SET):
    # teardown is delivery-lifecycle (teardown→deploy cascade), NOT provisioning,
    # and diagnostic verbs win over infrastructure nouns. The first live sweep
    # (2026-07-17) mis-stated teardown under provision and both adversarial misses
    # traced to exactly that line — keep this text aligned with the dataset notes.
    return (
        "Classify the request into exactly one specialist and reply with only that "
        "word: 'provision' (create new infrastructure or clusters), 'deploy' (ship, "
        "roll back, or tear down an app or cluster), or 'kagent' (read-only "
        "investigation — any request asking to investigate, diagnose, or explain "
        "why something failed, even when it mentions infrastructure).\n"
        f"Request: {instruction}\nSpecialist:"
    )


def _parse_role(reply: str) -> AgentRole | None:
    text = (reply or "").strip().lower()
    for role in AgentRole:
        if role.value in text:
            return role
    return None


def live_router_factory(call_model: ModelCall, *, backstop: Router | None = None) -> RouterFactory:
    """Build a :data:`RouterFactory` that classifies via a real model call.

    Each routing pass prompts ``call_model(config, prompt)`` for a role, parses it,
    and measures latency around the call. An unparseable/failed reply degrades to
    the deterministic ``backstop`` (default :func:`classify_request`) — the same
    reconciliation philosophy used elsewhere, so a flaky model never yields a null
    route. The model call is injected: pass a real client (with credentials) to run
    live and incur spend; a stub keeps it offline in tests.
    """
    fallback = backstop or classify_request

    def factory(config: "SweepConfig") -> ObservingRouter:
        def router(instruction: str) -> Observation:
            started = time.monotonic()
            try:
                reply = call_model(config, _classify_prompt(instruction))
            except Exception:
                reply = ""
            latency = time.monotonic() - started
            role = _parse_role(reply)
            decision = RouteDecision(role, "model") if role else fallback(instruction)
            return Observation(decision, latency_s=latency)

        return router

    return factory


__all__ = [
    "CostModel",
    "ModelCall",
    "RouterFactory",
    "SweepConfig",
    "SweepPoint",
    "best",
    "grid",
    "live_router_factory",
    "rank",
    "run_sweep",
    "scoreboard",
]
