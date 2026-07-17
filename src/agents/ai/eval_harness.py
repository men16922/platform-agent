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
from typing import Any, Callable

from src.agents.ai.supervisor import AgentRole, RouteDecision, classify_request

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
    "Judge",
    "JudgeVerdict",
    "ROUTING_EVAL_SET",
    "Router",
    "calibration_probe",
    "exact_match_judge",
    "grade",
    "llm_judge",
]
