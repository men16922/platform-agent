"""Decision-quality evaluation harness (offline, LLM-as-judge capable).

This sits *beside* the deterministic unit suite (`make check`), not inside it.
The unit tests assert that the code does what a test author pinned down; this
harness asks a different question: **across a labeled dataset, how good are the
agent's routing / decision choices — including fuzzy cases where exact-match is
too rigid to grade?** That is the layer a plain assert-based test cannot cover,
and the gap that agent-eval tooling (e.g. Google `agents-cli`'s
``eval generate / grade / optimize``) exists to fill. Here it is reproduced
cloud-neutral, with no GCP or vendor dependency.

Design mirrors the rest of the codebase:

* **Injectable seams, offline-testable.** The ``router`` under test and the
  ``judge`` are both injected. The defaults — the deterministic
  :func:`~src.agents.ai.supervisor.classify_request` and
  :func:`exact_match_judge` — run entirely offline, so the harness itself is
  exercised in ``make check`` with no LLM. An LLM router or :func:`llm_judge`
  is opt-in for scoring *model* quality.
* **Deterministic backstop over model output.** :func:`llm_judge` falls back to
  exact-match grading whenever the LLM grader errors or returns an unparseable
  verdict — the same reconciliation-gate philosophy used everywhere else.
* **Anti-leniency calibration.** LLM graders skew agreeable, so
  :func:`calibration_probe` canaries a grader against an unambiguously-wrong
  control routing; ``llm_judge(..., calibrate=True)`` rejects a grader that
  passes the canary and degrades to the deterministic judge. The judge prompt is
  likewise framed to FAIL-when-unsure rather than pass anything defensible.

The single-judge :func:`grade`/:class:`EvalReport` path answers one question:
"did the router pick the right role?". The declarative :func:`score` /
:class:`Scorecard` path adds *named metrics* over one run — several
:class:`Grader` s, each ``kind="code"`` (deterministic) or ``kind="judge"``
(model-graded) — so an eval can also score latency (:func:`budget_grader`, with a
PASS/FAIL/PASS_SLOW three-state) and cluster blast radius
(:func:`action_sink_grader`, failing a read-only role that mutated). A
:class:`Scorecard` diffs against a pinned baseline (:meth:`Scorecard.delta` /
:meth:`Scorecard.regressions`), and ``score(..., trials=N)`` majority-votes a
stochastic router — self-consistency reused to damp model noise.

The report is regression-friendly (aggregate + per-category pass rates,
surfaced failures) so an eval score can be tracked over time. The built-in
:data:`ROUTING_EVAL_SET` is balanced across categories and carries adversarial
*negatives* (a hot keyword pointing the wrong way) so it scores a classifier's
precision, not only its recall — a labeled gap shows up as a failing case rather
than silently passing.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Callable

from src.agents.ai.supervisor import (
    ROLE_ALLOWED_ACTIONS,
    AgentRole,
    RouteDecision,
    classify_request,
)

# A router maps an instruction to a routing decision. The deterministic
# classifier is the default subject; inject an LLM-backed router to evaluate a
# model instead.
Router = Callable[[str], RouteDecision]


@dataclass(frozen=True)
class EvalCase:
    """One labeled evaluation example."""

    instruction: str
    expected_role: AgentRole
    category: str = "general"
    note: str = ""


@dataclass(frozen=True)
class JudgeVerdict:
    """A pass/fail grade for a single case, with a human-readable reason."""

    passed: bool
    reason: str
    confidence: float = 1.0  # 1.0 for deterministic grades

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "reason": self.reason,
            "confidence": round(self.confidence, 4),
        }


# A judge grades an observed decision against the case's expectation.
Judge = Callable[[EvalCase, RouteDecision], JudgeVerdict]


def exact_match_judge(case: EvalCase, decision: RouteDecision) -> JudgeVerdict:
    """Deterministic grade: the observed role must equal the expected role."""
    passed = decision.role == case.expected_role
    if passed:
        reason = f"routed to expected role '{case.expected_role.value}'"
    else:
        reason = (
            f"expected '{case.expected_role.value}' but routed to "
            f"'{decision.role.value}'"
        )
    return JudgeVerdict(passed=passed, reason=reason, confidence=1.0)


def _build_judge_prompt(case: EvalCase, decision: RouteDecision) -> str:
    # Anti-leniency framing: LLM graders skew agreeable, so the prompt spells out
    # the read-only/mutating boundary and instructs a FAIL default when unsure —
    # rather than the old "anything defensible passes", which rewards leniency.
    return (
        "You are a strict grader for an agent's routing decision. The three "
        "specialists are: 'provision' (creates or tears down infrastructure — "
        "mutating), 'deploy' (ships or rolls back application deployments — "
        "mutating), and 'kagent' (read-only investigation and diagnosis — never "
        "mutates anything).\n"
        f"Request: {case.instruction}\n"
        f"Expected specialist: {case.expected_role.value}\n"
        f"Chosen specialist: {decision.role.value} ({decision.reason})\n"
        "Grade PASS only if the chosen specialist would take the correct action "
        "for this request. A specialist other than the expected one may PASS only "
        "when it is genuinely, defensibly interchangeable for THIS request. FAIL "
        "whenever the choice crosses the read-only/mutating boundary the wrong way "
        "(a mutating deploy/provision routed to read-only kagent, or an "
        "investigation routed to a mutating specialist), or whenever you are not "
        "sure the route is safe. When in doubt, FAIL.\n"
        "Answer with exactly 'PASS: <reason>' or 'FAIL: <reason>'."
    )


def _parse_verdict(raw: str) -> JudgeVerdict | None:
    """Parse a 'PASS: ...' / 'FAIL: ...' grader reply; None if unparseable."""
    head, _, tail = raw.partition(":")
    token = head.strip().upper()
    reason = tail.strip() or raw.strip()
    if token.startswith("PASS"):
        return JudgeVerdict(passed=True, reason=reason, confidence=0.75)
    if token.startswith("FAIL"):
        return JudgeVerdict(passed=False, reason=reason, confidence=0.75)
    return None


# An unambiguously-wrong control routing: a destructive, mutating request sent to
# the read-only investigator. Any well-calibrated grader must FAIL this. It is the
# canary behind :func:`calibration_probe` — a grader that PASSes it is too lenient
# to trust as a judge.
_CONTROL_CASE = EvalCase(
    "Delete the production cluster and wipe all its persistent volumes",
    AgentRole.PROVISION,
    "calibration-control",
)
_CONTROL_DECISION = RouteDecision(
    AgentRole.KAGENT, "read-only cluster investigation request"
)


def calibration_probe(grader: Callable[[str], str]) -> bool:
    """True iff ``grader`` correctly FAILs the unambiguously-wrong control routing.

    A destructive *provision* request routed to the read-only *kagent* specialist
    is a clear miss; a grader that PASSes it — or errors, or returns an
    unparseable reply — is too lenient/unreliable to be trusted as an LLM judge.
    This is a calibration canary against the well-known agreeableness bias of
    LLM-as-judge, used by :func:`llm_judge` when ``calibrate=True``.
    """
    try:
        raw = grader(_build_judge_prompt(_CONTROL_CASE, _CONTROL_DECISION))
    except Exception:
        return False
    verdict = _parse_verdict(raw or "")
    return verdict is not None and not verdict.passed


def llm_judge(grader: Callable[[str], str], *, calibrate: bool = False) -> Judge:
    """Adapt a text-in/text-out LLM grader into a :data:`Judge`.

    ``grader(prompt)`` is expected to return ``'PASS: reason'`` or
    ``'FAIL: reason'``. If it raises or returns something unparseable, the judge
    degrades to :func:`exact_match_judge` — a deterministic backstop, never a
    silent pass. This lets an LLM grade fuzzy cases (multiple defensible routes)
    while the deterministic path stays authoritative when the model is unusable.

    With ``calibrate=True`` the grader is first run through
    :func:`calibration_probe`; a grader that fails the canary (too lenient, or
    unreliable) is rejected up front and the judge falls back to deterministic
    exact-match for the whole run. The probe runs once, at construction.
    """
    if calibrate and not calibration_probe(grader):
        return exact_match_judge

    def _judge(case: EvalCase, decision: RouteDecision) -> JudgeVerdict:
        try:
            raw = grader(_build_judge_prompt(case, decision))
        except Exception:
            return exact_match_judge(case, decision)
        verdict = _parse_verdict(raw or "")
        if verdict is None:
            return exact_match_judge(case, decision)
        return verdict

    return _judge


@dataclass(frozen=True)
class CaseResult:
    """The graded outcome for one case."""

    case: EvalCase
    decision: RouteDecision
    verdict: JudgeVerdict

    def to_dict(self) -> dict[str, Any]:
        return {
            "instruction": self.case.instruction,
            "category": self.case.category,
            "expected": self.case.expected_role.value,
            "observed": self.decision.role.value,
            "verdict": self.verdict.to_dict(),
        }


@dataclass
class EvalReport:
    """Aggregate results of grading a dataset — trackable over time."""

    results: list[CaseResult] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.results)

    @property
    def passed(self) -> int:
        return sum(1 for r in self.results if r.verdict.passed)

    @property
    def pass_rate(self) -> float:
        return self.passed / self.total if self.total else 1.0

    def failures(self) -> list[CaseResult]:
        return [r for r in self.results if not r.verdict.passed]

    def by_category(self) -> dict[str, dict[str, Any]]:
        buckets: dict[str, list[CaseResult]] = defaultdict(list)
        for r in self.results:
            buckets[r.case.category].append(r)
        out: dict[str, dict[str, Any]] = {}
        for cat, rows in buckets.items():
            hits = sum(1 for r in rows if r.verdict.passed)
            out[cat] = {
                "total": len(rows),
                "passed": hits,
                "pass_rate": round(hits / len(rows), 4) if rows else 1.0,
            }
        return out

    def meets(self, min_pass_rate: float) -> bool:
        """True when the aggregate pass rate clears a regression threshold."""
        return self.pass_rate >= min_pass_rate

    def to_dict(self) -> dict[str, Any]:
        return {
            "total": self.total,
            "passed": self.passed,
            "pass_rate": round(self.pass_rate, 4),
            "by_category": self.by_category(),
            "failures": [r.to_dict() for r in self.failures()],
        }


def grade(
    cases: list[EvalCase],
    *,
    router: Router = classify_request,
    judge: Judge = exact_match_judge,
) -> EvalReport:
    """Run ``router`` over ``cases`` and grade each decision with ``judge``."""
    results: list[CaseResult] = []
    for case in cases:
        decision = router(case.instruction)
        verdict = judge(case, decision)
        results.append(CaseResult(case=case, decision=decision, verdict=verdict))
    return EvalReport(results=results)


# --- Declarative multi-grader scorecard ---------------------------------------
# The single-judge path above answers one question — "did the router pick the
# right role?". A real agent eval also asks "was it fast/cheap enough?" and "did
# it stay inside its blast radius (no unexpected cluster mutations)?" — several
# *named metrics* over one run, each either deterministic ("code") or model-graded
# ("judge"). This layer adds that on top of the pieces above without disturbing
# grade()/EvalReport, and keeps a pinned baseline so a regression shows as a delta.


class Verdict(StrEnum):
    """Three-state grade. ``PASS_SLOW`` = right answer, but over the budget —
    tracked distinctly instead of being hidden inside a plain pass or a hard fail."""

    PASS = "pass"
    FAIL = "fail"
    PASS_SLOW = "pass_slow"


@dataclass(frozen=True)
class Observation:
    """What a router/agent produced for one instruction — richer than a bare role
    so graders can score latency and cluster side effects, not only the pick."""

    decision: RouteDecision
    latency_s: float = 0.0
    actions: tuple[str, ...] = ()  # mutating side effects the agent performed


# An observing router yields the richer Observation instead of a bare decision.
ObservingRouter = Callable[[str], Observation]


def observing(
    router: Router, *, latency_s: float = 0.0, actions: tuple[str, ...] = ()
) -> ObservingRouter:
    """Lift a plain role ``router`` into an :data:`ObservingRouter` with fixed
    latency/actions — the bridge that lets the deterministic classifier feed the
    scorecard path unchanged."""
    return lambda instruction: Observation(router(instruction), latency_s, actions)


@dataclass(frozen=True)
class GradeOutcome:
    """One named metric's result on one case."""

    grader: str
    kind: str  # "code" (deterministic) | "judge" (model-graded)
    status: Verdict
    reason: str
    confidence: float = 1.0

    @property
    def passed(self) -> bool:
        """PASS and PASS_SLOW both count as a pass; only FAIL fails."""
        return self.status is not Verdict.FAIL

    def to_dict(self) -> dict[str, Any]:
        return {
            "grader": self.grader,
            "kind": self.kind,
            "status": self.status.value,
            "reason": self.reason,
            "confidence": round(self.confidence, 4),
        }


@dataclass(frozen=True)
class Grader:
    """A named, kind-tagged grader over ``(case, observation)``.

    ``kind`` separates deterministic ``"code"`` graders (reproducible, gate-safe)
    from model-graded ``"judge"`` graders (opt-in, non-deterministic) so a
    scorecard can report and trust them differently.
    """

    name: str
    kind: str
    fn: Callable[[EvalCase, Observation], GradeOutcome]

    def __call__(self, case: EvalCase, obs: Observation) -> GradeOutcome:
        return self.fn(case, obs)


def role_match_grader(name: str = "role") -> Grader:
    """Deterministic: the observed role must equal the expected role."""

    def _fn(case: EvalCase, obs: Observation) -> GradeOutcome:
        ok = obs.decision.role == case.expected_role
        if ok:
            return GradeOutcome(name, "code", Verdict.PASS, f"routed to expected '{case.expected_role.value}'")
        return GradeOutcome(
            name, "code", Verdict.FAIL,
            f"expected '{case.expected_role.value}', got '{obs.decision.role.value}'",
        )

    return Grader(name, "code", _fn)


def budget_grader(budget_s: float, *, name: str = "latency") -> Grader:
    """Deterministic three-state: FAIL if the role is wrong, else PASS_SLOW when
    the run exceeded ``budget_s`` seconds, else PASS. "Correct but slow" becomes
    its own tracked state rather than a silent pass or a hard fail."""

    def _fn(case: EvalCase, obs: Observation) -> GradeOutcome:
        if obs.decision.role != case.expected_role:
            return GradeOutcome(name, "code", Verdict.FAIL, f"wrong role '{obs.decision.role.value}'")
        if obs.latency_s > budget_s:
            return GradeOutcome(name, "code", Verdict.PASS_SLOW, f"{obs.latency_s:.3f}s > {budget_s:.3f}s budget")
        return GradeOutcome(name, "code", Verdict.PASS, f"{obs.latency_s:.3f}s within {budget_s:.3f}s budget")

    return Grader(name, "code", _fn)


# Default blast-radius policy is the delegation policy itself, single-sourced from
# the supervisor: a role's read-only status is derived from it having no permitted
# mutating action (KAGENT). Keeping one source means the eval metric and the
# `metadata.allowedActions` hint the supervisor forwards can never drift apart.
READ_ONLY_ROLES = frozenset(role for role, actions in ROLE_ALLOWED_ACTIONS.items() if not actions)


def action_sink_grader(
    *, allowed: dict[AgentRole, frozenset[str]] | None = None, name: str = "blast_radius"
) -> Grader:
    """Deterministic: score the side effects an agent performed on the cluster.

    Any action taken by a read-only role — or an action outside ``allowed`` for
    the expected role — is a FAIL; a clean read (no actions) is a PASS. This is
    the safety metric: it catches an agent that mutated when it should only look.
    ``allowed`` defaults to the supervisor's :data:`ROLE_ALLOWED_ACTIONS`, so the
    metric enforces exactly the blast radius the delegation boundary advertises.
    """
    allowed = ROLE_ALLOWED_ACTIONS if allowed is None else allowed

    def _fn(case: EvalCase, obs: Observation) -> GradeOutcome:
        role = case.expected_role
        if role in READ_ONLY_ROLES and obs.actions:
            return GradeOutcome(name, "code", Verdict.FAIL, f"read-only '{role.value}' mutated: {list(obs.actions)}")
        permitted = allowed.get(role)
        if permitted is not None:
            stray = [a for a in obs.actions if a not in permitted]
            if stray:
                return GradeOutcome(name, "code", Verdict.FAIL, f"actions outside policy for '{role.value}': {stray}")
        return GradeOutcome(name, "code", Verdict.PASS, f"{len(obs.actions)} action(s) within blast radius")

    return Grader(name, "code", _fn)


def judge_grader(judge: Judge = exact_match_judge, *, name: str = "judge") -> Grader:
    """Wrap an existing single-case :data:`Judge` (exact-match or LLM) as a
    model-graded metric, so the scorecard can mix code and judge graders."""

    def _fn(case: EvalCase, obs: Observation) -> GradeOutcome:
        v = judge(case, obs.decision)
        status = Verdict.PASS if v.passed else Verdict.FAIL
        return GradeOutcome(name, "judge", status, v.reason, v.confidence)

    return Grader(name, "judge", _fn)


def _majority_observation(router: ObservingRouter, instruction: str, trials: int) -> Observation:
    """Run ``router`` ``trials`` times and return the observation whose role is the
    plurality winner — self-consistency reused to damp a stochastic router. The
    first observation carrying the winning role is kept (with its latency/actions),
    so a deterministic router at ``trials=1`` is unchanged."""
    obs = [router(instruction) for _ in range(max(1, trials))]
    counts: dict[AgentRole, int] = defaultdict(int)
    for o in obs:
        counts[o.decision.role] += 1
    winner = max(counts, key=lambda r: counts[r])
    for o in obs:
        if o.decision.role == winner:
            return o
    return obs[0]


@dataclass
class Scorecard:
    """Per-metric results over a dataset — the multi-grader analogue of EvalReport,
    with a delta against a pinned baseline for regression tracking."""

    outcomes: dict[str, list[GradeOutcome]] = field(default_factory=dict)

    def metrics(self) -> dict[str, dict[str, Any]]:
        out: dict[str, dict[str, Any]] = {}
        for name, rows in self.outcomes.items():
            total = len(rows)
            passed = sum(1 for o in rows if o.passed)
            out[name] = {
                "kind": rows[0].kind if rows else "code",
                "total": total,
                "passed": passed,
                "pass_slow": sum(1 for o in rows if o.status is Verdict.PASS_SLOW),
                "failed": sum(1 for o in rows if o.status is Verdict.FAIL),
                "pass_rate": round(passed / total, 4) if total else 1.0,
            }
        return out

    def failures(self) -> dict[str, list[dict[str, Any]]]:
        return {
            name: [o.to_dict() for o in rows if not o.passed]
            for name, rows in self.outcomes.items()
            if any(not o.passed for o in rows)
        }

    def to_dict(self) -> dict[str, Any]:
        return {"metrics": self.metrics(), "failures": self.failures()}

    def delta(self, baseline: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
        """Diff this scorecard's pass rates against a pinned ``baseline`` (a prior
        :meth:`metrics` dict). Each metric reports baseline/current/delta and a
        ``regressed`` flag; a metric absent from the baseline surfaces with
        ``baseline=None`` (new, not a regression)."""
        out: dict[str, dict[str, Any]] = {}
        for name, m in self.metrics().items():
            base = baseline.get(name, {}).get("pass_rate")
            now = m["pass_rate"]
            out[name] = {
                "baseline": base,
                "current": now,
                "delta": round(now - base, 4) if base is not None else None,
                "regressed": bool(base is not None and now < base),
            }
        return out

    def regressions(self, baseline: dict[str, dict[str, Any]]) -> list[str]:
        """Names of metrics whose pass rate fell below the pinned baseline."""
        return [n for n, d in self.delta(baseline).items() if d["regressed"]]


def score(
    cases: list[EvalCase],
    graders: list[Grader],
    *,
    router: ObservingRouter | None = None,
    trials: int = 1,
) -> Scorecard:
    """Run each case through ``router`` (majority-voted over ``trials`` samples) and
    grade the observation with every grader, producing a named-metric
    :class:`Scorecard`. ``router`` defaults to the deterministic classifier lifted
    via :func:`observing`. ``trials>1`` reuses self-consistency to damp a
    stochastic (LLM) router; it is a no-op for the deterministic default."""
    obs_router = router or observing(classify_request)
    outcomes: dict[str, list[GradeOutcome]] = {g.name: [] for g in graders}
    for case in cases:
        obs = _majority_observation(obs_router, case.instruction, trials)
        for g in graders:
            outcomes[g.name].append(g(case, obs))
    return Scorecard(outcomes=outcomes)


# --- Built-in routing dataset -------------------------------------------------
# A labeled regression baseline for the deterministic classifier, balanced across
# categories and carrying *adversarial* negatives — cases where a keyword belongs
# to one specialist but the correct route is another. Two of them
# ("adversarial": deploy-observability, investigate-terraform) plus the
# "cluster-creation-verb" pair were originally *gaps* this harness surfaced; each
# was then fixed in classify_request and retained here as a regression guard. This
# is the harness working as intended: eval finds a decision-quality gap a pass/fail
# unit test would miss, the gap gets fixed, the case becomes a regression guard.
#
# Negatives matter as much as positives: a dataset with only clean positive cases
# rewards a classifier that over-triggers (routes anything with a hot keyword),
# because nothing penalises the false positive. The adversarial rows are that
# penalty — they hold the classifier's precision, not just its recall.
ROUTING_EVAL_SET: list[EvalCase] = [
    # provision — explicit infra keywords the classifier covers
    EvalCase("Provision an EKS cluster with Terraform", AgentRole.PROVISION, "provision"),
    EvalCase("Set up a cluster on-prem with Ansible", AgentRole.PROVISION, "provision"),
    EvalCase("Run terraform apply for the staging cluster", AgentRole.PROVISION, "provision"),
    EvalCase("Provision the shared services subnet", AgentRole.PROVISION, "provision"),
    # deploy — delivery verbs / default operational handoff
    EvalCase("Deploy orders-api to staging", AgentRole.DEPLOY, "deploy"),
    EvalCase("Ship the new payments build to production", AgentRole.DEPLOY, "deploy"),
    EvalCase("Roll back the last deployment", AgentRole.DEPLOY, "deploy"),
    EvalCase("Promote the release candidate to prod", AgentRole.DEPLOY, "deploy"),
    # kagent — read-only investigation
    EvalCase("Why is the checkout pod crashlooping?", AgentRole.KAGENT, "diagnose"),
    EvalCase("Investigate high latency in the orders namespace", AgentRole.KAGENT, "diagnose"),
    EvalCase("Show me the logs for the payments service", AgentRole.KAGENT, "diagnose"),
    EvalCase("Diagnose the failing istio sidecar", AgentRole.KAGENT, "diagnose"),
    EvalCase("What's the status of the cluster?", AgentRole.KAGENT, "diagnose"),
    # cluster-creation verbs with an interpolated cluster name — surfaced as gaps
    # by this harness, then fixed in classify_request; now regression guards.
    EvalCase(
        "Create a GKE cluster in us-central1",
        AgentRole.PROVISION,
        "cluster-creation-verb",
        note="'create a <X> cluster' splits the literal 'create cluster' keyword",
    ),
    EvalCase(
        "Spin up a kind cluster locally",
        AgentRole.PROVISION,
        "cluster-creation-verb",
        note="'spin up' + 'cluster' compositional provisioning verb",
    ),
    # adversarial negatives — a hot keyword points one way, the intent points
    # another. These hold the classifier's *precision* against over-triggering.
    EvalCase(
        "Deploy the observability stack to production",
        AgentRole.DEPLOY,
        "adversarial",
        note="'observability' collides with diagnosis, but a delivery verb leads → deploy (fixed gap)",
    ),
    EvalCase(
        "Deploy prometheus for cluster observability",
        AgentRole.DEPLOY,
        "adversarial",
        note="'cluster'+'observability' nouns, no creation/diagnostic verb, delivery verb leads → deploy",
    ),
    EvalCase(
        "Investigate why the terraform apply failed",
        AgentRole.KAGENT,
        "adversarial",
        note="'terraform' collides with provisioning, but 'investigate' is a diagnostic verb → kagent (fixed gap)",
    ),
    EvalCase(
        "Roll back the cluster autoscaler deployment",
        AgentRole.DEPLOY,
        "adversarial",
        note="'cluster' present but no creation verb, and it's a rollback → deploy, not provision",
    ),
    EvalCase(
        "Tear down the staging cluster",
        AgentRole.DEPLOY,
        "adversarial",
        note="teardown is not a creation verb; routes to deploy by design (teardown→deploy cascade)",
    ),
]


__all__ = [
    "CaseResult",
    "EvalCase",
    "EvalReport",
    "GradeOutcome",
    "Grader",
    "Judge",
    "JudgeVerdict",
    "Observation",
    "ObservingRouter",
    "READ_ONLY_ROLES",
    "ROUTING_EVAL_SET",
    "Router",
    "Scorecard",
    "Verdict",
    "action_sink_grader",
    "budget_grader",
    "calibration_probe",
    "exact_match_judge",
    "grade",
    "judge_grader",
    "llm_judge",
    "observing",
    "role_match_grader",
    "score",
]
