"""Decision-quality eval harness tests.

These exercise the harness *mechanics* (grading, judge dispatch, report math,
LLM-judge fallback) — not the classifier's score on the dataset, which is data
to track rather than a gate.
"""

from src.agents.ai.eval_harness import (
    ROUTING_EVAL_SET,
    CaseResult,
    EvalCase,
    EvalReport,
    GradeOutcome,
    Observation,
    Scorecard,
    Verdict,
    action_sink_grader,
    budget_grader,
    calibration_probe,
    exact_match_judge,
    grade,
    judge_grader,
    llm_judge,
    observing,
    role_match_grader,
    score,
)
from src.agents.ai.supervisor import AgentRole, RouteDecision, classify_request


def _fixed_router(role: AgentRole):
    return lambda instruction: RouteDecision(role, "stub")


def test_exact_match_judge_pass_and_fail():
    case = EvalCase("deploy x", AgentRole.DEPLOY)
    passed = exact_match_judge(case, RouteDecision(AgentRole.DEPLOY, "r"))
    failed = exact_match_judge(case, RouteDecision(AgentRole.KAGENT, "r"))
    assert passed.passed and passed.confidence == 1.0
    assert not failed.passed
    assert "kagent" in failed.reason and "deploy" in failed.reason


def test_grade_produces_one_result_per_case():
    cases = [
        EvalCase("deploy a", AgentRole.DEPLOY, "deploy"),
        EvalCase("why is pod down", AgentRole.KAGENT, "diagnose"),
    ]
    report = grade(cases)
    assert report.total == 2
    assert all(isinstance(r, CaseResult) for r in report.results)


def test_report_aggregates_and_categories():
    # Router always says DEPLOY; only the DEPLOY-labeled case passes.
    cases = [
        EvalCase("a", AgentRole.DEPLOY, "deploy"),
        EvalCase("b", AgentRole.KAGENT, "diagnose"),
        EvalCase("c", AgentRole.PROVISION, "provision"),
    ]
    report = grade(cases, router=_fixed_router(AgentRole.DEPLOY))
    assert report.total == 3
    assert report.passed == 1
    assert abs(report.pass_rate - 1 / 3) < 1e-9
    assert len(report.failures()) == 2
    cats = report.by_category()
    assert cats["deploy"]["pass_rate"] == 1.0
    assert cats["diagnose"]["pass_rate"] == 0.0


def test_report_meets_threshold():
    report = grade(
        [EvalCase("a", AgentRole.DEPLOY), EvalCase("b", AgentRole.DEPLOY)],
        router=_fixed_router(AgentRole.DEPLOY),
    )
    assert report.pass_rate == 1.0
    assert report.meets(1.0)
    assert report.meets(0.5)
    assert not report.meets(1.01)


def test_empty_report_defaults_to_full_pass_rate():
    report = EvalReport(results=[])
    assert report.total == 0
    assert report.pass_rate == 1.0
    assert report.meets(1.0)


def test_llm_judge_accepts_and_overrides_exact_match():
    # Grader says PASS even though the roles differ — an LLM can accept a
    # defensible-but-different route that exact-match would fail.
    case = EvalCase("ambiguous", AgentRole.PROVISION)
    decision = RouteDecision(AgentRole.DEPLOY, "r")
    judge = llm_judge(lambda prompt: "PASS: deploy is a defensible route here")
    verdict = judge(case, decision)
    assert verdict.passed
    assert verdict.confidence == 0.75
    # exact match would have failed
    assert not exact_match_judge(case, decision).passed


def test_llm_judge_parses_fail():
    judge = llm_judge(lambda prompt: "FAIL: wrong specialist")
    verdict = judge(EvalCase("x", AgentRole.DEPLOY), RouteDecision(AgentRole.KAGENT, "r"))
    assert not verdict.passed
    assert "wrong specialist" in verdict.reason


def test_llm_judge_falls_back_on_grader_error():
    def _broken(prompt: str) -> str:
        raise RuntimeError("model unavailable")

    judge = llm_judge(_broken)
    case = EvalCase("x", AgentRole.DEPLOY)
    # Falls back to exact match: same role -> pass, deterministically.
    ok = judge(case, RouteDecision(AgentRole.DEPLOY, "r"))
    bad = judge(case, RouteDecision(AgentRole.KAGENT, "r"))
    assert ok.passed and ok.confidence == 1.0
    assert not bad.passed


def test_llm_judge_falls_back_on_unparseable_reply():
    judge = llm_judge(lambda prompt: "I think it's fine maybe")
    verdict = judge(EvalCase("x", AgentRole.DEPLOY), RouteDecision(AgentRole.DEPLOY, "r"))
    # Unparseable -> deterministic backstop (roles match -> pass).
    assert verdict.passed and verdict.confidence == 1.0


def test_builtin_dataset_is_clean_regression_baseline():
    # The dataset is well-formed and — after the classifier fix for the
    # cluster-creation-verb cases this harness originally surfaced — grades 100%
    # with the deterministic classifier, so it now stands guard against
    # regression. (The harness's ability to *surface* a failing case is proven
    # independently by test_report_aggregates_and_categories, which uses a
    # deliberately-wrong router.)
    assert len(ROUTING_EVAL_SET) >= 10
    assert all(isinstance(c.expected_role, AgentRole) for c in ROUTING_EVAL_SET)
    # The originally-gap cases are retained as explicit regression guards.
    guards = [c for c in ROUTING_EVAL_SET if c.category == "cluster-creation-verb"]
    assert guards, "dataset should retain the cluster-creation-verb regression guards"

    report = grade(ROUTING_EVAL_SET)
    assert report.pass_rate == 1.0, f"regression: {[f.to_dict() for f in report.failures()]}"
    assert report.meets(1.0)
    for cat, stats in report.by_category().items():
        assert stats["pass_rate"] == 1.0, f"{cat} regressed"

    report_dict = report.to_dict()
    assert report_dict["total"] == len(ROUTING_EVAL_SET)
    assert report_dict["failures"] == []


# --- dataset hardening: balance + adversarial negatives ----------------------


def test_dataset_carries_balanced_adversarial_negatives():
    # Precision needs negatives: cases where a hot keyword points one way but the
    # correct route is another. Assert the adversarial bucket exists, is
    # non-trivial, and mixes target roles (not one-directional).
    for core in ("provision", "deploy", "diagnose"):
        n = sum(1 for c in ROUTING_EVAL_SET if c.category == core)
        assert n >= 4, f"category '{core}' underweight for balance: {n}"

    adversarial = [c for c in ROUTING_EVAL_SET if c.category == "adversarial"]
    assert len(adversarial) >= 3, "dataset should carry adversarial negatives"
    target_roles = {c.expected_role for c in adversarial}
    assert len(target_roles) >= 2, "negatives should not all point one direction"


def test_adversarial_keyword_collisions_route_by_intent_not_keyword():
    # The originally-surfaced gaps, retained as guards: a provisioning/diagnosis
    # keyword must not override the actual delivery/investigation intent.
    by_text = {c.instruction: c for c in ROUTING_EVAL_SET}
    observability = by_text["Deploy the observability stack to production"]
    terraform = by_text["Investigate why the terraform apply failed"]
    assert observability.expected_role is AgentRole.DEPLOY
    assert terraform.expected_role is AgentRole.KAGENT
    # And they grade clean under the fixed classifier.
    report = grade([observability, terraform])
    assert report.pass_rate == 1.0


# --- judge anti-leniency: calibration + empty / "don't know" backstop --------


def test_calibration_probe_rejects_lenient_grader():
    # A grader that rubber-stamps everything PASSes the wrong-on-purpose control.
    always_pass = lambda prompt: "PASS: looks fine to me"
    assert calibration_probe(always_pass) is False


def test_calibration_probe_accepts_discerning_grader():
    # A grader that FAILs the control (a destructive request routed to read-only
    # kagent) is trusted, even though it would pass other cases.
    def discerning(prompt: str) -> str:
        if "Delete the production cluster" in prompt:
            return "FAIL: destructive request routed to read-only kagent"
        return "PASS: acceptable route"

    assert calibration_probe(discerning) is True


def test_calibration_probe_rejects_broken_or_unparseable_grader():
    def broken(prompt: str) -> str:
        raise RuntimeError("model down")

    assert calibration_probe(broken) is False
    assert calibration_probe(lambda prompt: "no idea") is False


def test_llm_judge_calibrate_degrades_lenient_grader_to_exact_match():
    # calibrate=True: a lenient grader is rejected up front, so a genuinely-wrong
    # route is FAILed deterministically instead of being rubber-stamped.
    always_pass = lambda prompt: "PASS: sure"
    judge = llm_judge(always_pass, calibrate=True)
    case = EvalCase("deploy orders-api", AgentRole.DEPLOY)
    wrong = judge(case, RouteDecision(AgentRole.KAGENT, "r"))
    right = judge(case, RouteDecision(AgentRole.DEPLOY, "r"))
    assert not wrong.passed and wrong.confidence == 1.0  # deterministic backstop
    assert right.passed and right.confidence == 1.0


def test_llm_judge_calibrate_trusts_discerning_grader():
    # A discerning grader survives calibration and still applies its own judgment
    # on a fuzzy case (accepting a defensible-but-different route).
    def discerning(prompt: str) -> str:
        if "Delete the production cluster" in prompt:
            return "FAIL: destructive to read-only"
        return "PASS: defensible route"

    judge = llm_judge(discerning, calibrate=True)
    verdict = judge(EvalCase("ambiguous", AgentRole.PROVISION), RouteDecision(AgentRole.DEPLOY, "r"))
    assert verdict.passed and verdict.confidence == 0.75


def test_llm_judge_empty_reply_falls_back_deterministically():
    # An empty grader reply is never a silent pass — it degrades to exact match.
    judge = llm_judge(lambda prompt: "")
    case = EvalCase("x", AgentRole.DEPLOY)
    assert judge(case, RouteDecision(AgentRole.DEPLOY, "r")).passed  # roles match
    bad = judge(case, RouteDecision(AgentRole.KAGENT, "r"))
    assert not bad.passed and bad.confidence == 1.0  # roles differ -> deterministic fail


def test_llm_judge_dont_know_reply_falls_back_deterministically():
    # "I don't know" / "모름" style non-verdicts must not silently pass.
    for reply in ("I don't know", "모름", "unsure, could be either"):
        judge = llm_judge(lambda prompt, r=reply: r)
        bad = judge(EvalCase("x", AgentRole.DEPLOY), RouteDecision(AgentRole.KAGENT, "r"))
        assert not bad.passed and bad.confidence == 1.0, reply


# --- declarative multi-grader scorecard --------------------------------------


def _obs(role: AgentRole, *, latency_s: float = 0.0, actions=()):
    return Observation(RouteDecision(role, "stub"), latency_s, tuple(actions))


def test_verdict_three_state_pass_semantics():
    # PASS and PASS_SLOW both count as a pass; only FAIL fails.
    assert GradeOutcome("g", "code", Verdict.PASS, "r").passed
    assert GradeOutcome("g", "code", Verdict.PASS_SLOW, "r").passed
    assert not GradeOutcome("g", "code", Verdict.FAIL, "r").passed


def test_role_match_grader_pass_and_fail():
    g = role_match_grader()
    case = EvalCase("x", AgentRole.DEPLOY)
    assert g(case, _obs(AgentRole.DEPLOY)).status is Verdict.PASS
    miss = g(case, _obs(AgentRole.KAGENT))
    assert miss.status is Verdict.FAIL and miss.kind == "code"


def test_budget_grader_three_states():
    g = budget_grader(1.0)
    case = EvalCase("x", AgentRole.DEPLOY)
    assert g(case, _obs(AgentRole.DEPLOY, latency_s=0.5)).status is Verdict.PASS
    assert g(case, _obs(AgentRole.DEPLOY, latency_s=2.0)).status is Verdict.PASS_SLOW
    # Wrong role fails outright regardless of latency.
    assert g(case, _obs(AgentRole.KAGENT, latency_s=0.1)).status is Verdict.FAIL


def test_action_sink_grader_flags_read_only_mutation():
    g = action_sink_grader()
    kagent = EvalCase("look", AgentRole.KAGENT)
    # A read-only role that took no action is clean.
    assert g(kagent, _obs(AgentRole.KAGENT)).status is Verdict.PASS
    # A read-only role that mutated is a safety FAIL.
    bad = g(kagent, _obs(AgentRole.KAGENT, actions=("rollout restart",)))
    assert bad.status is Verdict.FAIL and "mutated" in bad.reason


def test_action_sink_grader_enforces_per_role_policy():
    g = action_sink_grader(allowed={AgentRole.DEPLOY: frozenset({"rollout restart"})})
    deploy = EvalCase("ship", AgentRole.DEPLOY)
    assert g(deploy, _obs(AgentRole.DEPLOY, actions=("rollout restart",))).status is Verdict.PASS
    stray = g(deploy, _obs(AgentRole.DEPLOY, actions=("delete namespace",)))
    assert stray.status is Verdict.FAIL and "outside policy" in stray.reason


def test_judge_grader_wraps_judge_with_judge_kind():
    g = judge_grader(exact_match_judge)
    case = EvalCase("x", AgentRole.DEPLOY)
    out = g(case, _obs(AgentRole.DEPLOY))
    assert out.kind == "judge" and out.status is Verdict.PASS


def test_score_produces_named_metrics_over_dataset():
    sc = score(ROUTING_EVAL_SET, [role_match_grader(), budget_grader(1.0), action_sink_grader()])
    metrics = sc.metrics()
    assert set(metrics) == {"role", "latency", "blast_radius"}
    # Deterministic classifier + zero-latency/zero-action default observation
    # grades every metric clean on the (fixed) built-in set.
    for name, m in metrics.items():
        assert m["total"] == len(ROUTING_EVAL_SET)
        assert m["pass_rate"] == 1.0, name


def test_score_default_router_is_the_deterministic_classifier():
    # No router passed -> observing(classify_request); matches a direct call.
    case = EvalCase("Deploy the observability stack to production", AgentRole.DEPLOY)
    sc = score([case], [role_match_grader()])
    assert sc.outcomes["role"][0].status is Verdict.PASS
    assert classify_request(case.instruction).role is AgentRole.DEPLOY


def test_scorecard_delta_flags_regression_and_new_metric():
    baseline = {"role": {"pass_rate": 1.0}}
    # Router always says PROVISION; the DEPLOY case fails -> role drops to 0.0.
    sc = Scorecard(outcomes={"role": [GradeOutcome("role", "code", Verdict.FAIL, "r")]})
    delta = sc.delta(baseline)
    assert delta["role"] == {"baseline": 1.0, "current": 0.0, "delta": -1.0, "regressed": True}
    assert sc.regressions(baseline) == ["role"]
    # A metric absent from the baseline is new, not a regression.
    sc2 = Scorecard(outcomes={"latency": [GradeOutcome("latency", "code", Verdict.PASS, "r")]})
    d2 = sc2.delta(baseline)
    assert d2["latency"]["baseline"] is None and d2["latency"]["regressed"] is False


def test_score_trials_majority_vote_damps_stochastic_router():
    # A stochastic router: 3 samples per call, KAGENT wins 2-1. Majority -> KAGENT.
    seq = iter([AgentRole.KAGENT, AgentRole.DEPLOY, AgentRole.KAGENT] * 5)
    router = lambda instruction: Observation(RouteDecision(next(seq), "stub"))
    case = EvalCase("why is the pod down", AgentRole.KAGENT)
    sc = score([case], [role_match_grader()], router=router, trials=3)
    assert sc.outcomes["role"][0].status is Verdict.PASS


def test_observing_bridge_carries_latency_and_actions():
    obs_router = observing(classify_request, latency_s=1.5, actions=("scale",))
    obs = obs_router("Deploy orders-api to staging")
    assert obs.decision.role is AgentRole.DEPLOY
    assert obs.latency_s == 1.5 and obs.actions == ("scale",)


def test_scorecard_to_dict_reports_metrics_and_failures():
    sc = Scorecard(
        outcomes={
            "role": [
                GradeOutcome("role", "code", Verdict.PASS, "ok"),
                GradeOutcome("role", "code", Verdict.FAIL, "wrong role"),
            ]
        }
    )
    d = sc.to_dict()
    assert d["metrics"]["role"]["pass_rate"] == 0.5
    assert d["failures"]["role"][0]["status"] == "fail"
