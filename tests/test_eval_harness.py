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
    exact_match_judge,
    grade,
    llm_judge,
)
from src.agents.ai.supervisor import AgentRole, RouteDecision


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
