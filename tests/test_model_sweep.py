"""Model/parameter sweep tests — offline, with a deterministic mock backend.

No real API call: the ``router_factory`` is injected, so these exercise the grid,
cost/latency headline math, ranking, and resume logic without any model spend.
"""

import math

import pytest

from src.agents.ai.eval_harness import (
    ROUTING_EVAL_SET,
    Observation,
    observing,
)
from src.agents.ai.model_sweep import (
    SweepConfig,
    SweepPoint,
    best,
    grid,
    live_router_factory,
    rank,
    run_sweep,
    scoreboard,
)
from src.agents.ai.supervisor import AgentRole, RouteDecision, classify_request

_DATASET = ROUTING_EVAL_SET
_N = len(_DATASET)


def _good_factory(latency=0.01):
    # A "good" model = the reference classifier, which grades 20/20 on the set.
    return lambda cfg: observing(classify_request, latency_s=latency)


def _always_deploy_factory(cfg):
    return lambda instruction: Observation(RouteDecision(AgentRole.DEPLOY, "stub"), 0.02)


def _fixed_cost(usd):
    return lambda cfg: usd


def test_sweep_config_key_is_stable_and_distinct():
    a = SweepConfig("opus", thinking=True, effort="high")
    assert a.key() == "opus|thinking=True|effort=high"
    assert SweepConfig("opus").key() != SweepConfig("haiku").key()


def test_grid_is_cartesian_product():
    g = grid(["a", "b"], thinking=[False, True], effort=["low", "high"])
    assert len(g) == 8
    assert SweepConfig("a", False, "low") in g
    assert SweepConfig("b", True, "high") in g


def test_run_sweep_measures_accuracy_cost_and_latency():
    pts = run_sweep(
        [SweepConfig("good")],
        _good_factory(latency=0.01),
        cost_per_call=_fixed_cost(0.001),
        dataset=_DATASET,
    )
    (p,) = pts
    assert p.successes == _N and p.pass_rate == 1.0
    assert p.total == _N
    assert p.cost_usd == pytest.approx(0.001 * _N)  # one call per case at trials=1
    assert p.seconds == pytest.approx(0.01 * _N)
    assert p.cost_per_success == pytest.approx(0.001)
    assert p.seconds_per_success == pytest.approx(0.01)


def test_run_sweep_counts_calls_per_trial():
    pts = run_sweep(
        [SweepConfig("good")],
        _good_factory(latency=0.0),
        cost_per_call=_fixed_cost(0.01),
        dataset=_DATASET,
        trials=3,
    )
    # 3 samples per case -> 3N calls -> 3N * price.
    assert pts[0].cost_usd == pytest.approx(0.01 * 3 * _N)


def test_cost_per_success_is_inf_when_nothing_succeeds():
    p = SweepPoint(SweepConfig("dud"), successes=0, total=_N, cost_usd=5.0, seconds=9.0, trials=1)
    assert math.isinf(p.cost_per_success)
    assert math.isinf(p.seconds_per_success)
    assert p.pass_rate == 0.0


def test_run_sweep_is_resumable_and_skips_done_configs():
    cached = SweepPoint(
        SweepConfig("cached"), successes=10, total=_N, cost_usd=1.0, seconds=5.0, trials=1
    )

    def exploding_factory(cfg):
        if cfg.key() == SweepConfig("cached").key():
            raise AssertionError("resume must not recompute a done config")
        return observing(classify_request, latency_s=0.0)

    pts = run_sweep(
        [SweepConfig("cached"), SweepConfig("good")],
        exploding_factory,
        cost_per_call=_fixed_cost(0.0),
        dataset=_DATASET,
        done=[cached],
    )
    assert len(pts) == 2
    assert pts[0] is cached  # prior points returned at the front, unchanged
    assert pts[1].config.model == "good" and pts[1].pass_rate == 1.0


def test_rank_orders_best_first_by_cost_then_accuracy():
    good = run_sweep([SweepConfig("good")], _good_factory(0.0), cost_per_call=_fixed_cost(0.001), dataset=_DATASET)
    bad = run_sweep([SweepConfig("bad")], _always_deploy_factory, cost_per_call=_fixed_cost(0.001), dataset=_DATASET)
    points = good + bad
    # good routes everything right -> lowest cost_per_success -> ranked first.
    assert rank(points, by="cost_per_success")[0].config.model == "good"
    assert rank(points, by="pass_rate")[0].config.model == "good"
    assert best(points).config.model == "good"


def test_rank_rejects_unknown_key():
    with pytest.raises(ValueError, match="unknown rank key"):
        rank([], by="nonsense")


def test_best_of_empty_sweep_is_none():
    assert best([]) is None


def test_sweep_point_dict_roundtrips():
    p = SweepPoint(SweepConfig("opus", True, "high"), successes=18, total=20, cost_usd=0.42, seconds=3.1, trials=2)
    restored = SweepPoint.from_dict(p.to_dict())
    assert restored.config == p.config
    assert restored.successes == 18 and restored.trials == 2
    assert restored.cost_usd == pytest.approx(0.42)


def test_scoreboard_is_ranked_serialisable_table():
    good = run_sweep([SweepConfig("good")], _good_factory(0.0), cost_per_call=_fixed_cost(0.001), dataset=_DATASET)
    bad = run_sweep([SweepConfig("bad")], _always_deploy_factory, cost_per_call=_fixed_cost(0.001), dataset=_DATASET)
    board = scoreboard(good + bad, by="cost_per_success")
    assert [row["config"]["model"] for row in board] == ["good", "bad"]
    assert board[0]["pass_rate"] == 1.0


# --- live router factory (⑦ execution adapter, offline with a mock model) ----


def test_live_router_factory_parses_model_reply_into_a_role():
    # A stub model that echoes a role word — no network, no spend.
    calls: list[str] = []

    def call_model(config, prompt):
        calls.append(config.model)
        return "kagent"  # the model's verdict

    router = live_router_factory(call_model)(SweepConfig("stub"))
    obs = router("Why is the pod down?")
    assert obs.decision.role is AgentRole.KAGENT
    assert calls == ["stub"]  # the model was actually consulted


def test_live_router_factory_backstops_on_unparseable_or_failed_reply():
    # Unparseable reply -> deterministic classify_request backstop, not a null route.
    router = live_router_factory(lambda cfg, prompt: "hmm not sure")(SweepConfig("m"))
    obs = router("Provision an EKS cluster with Terraform")
    assert obs.decision.role is AgentRole.PROVISION  # from the deterministic backstop

    # A raising model call also degrades to the backstop rather than erroring out.
    def boom(cfg, prompt):
        raise RuntimeError("api down")

    obs2 = live_router_factory(boom)(SweepConfig("m"))("Deploy orders-api to staging")
    assert obs2.decision.role is AgentRole.DEPLOY


def test_live_router_factory_feeds_run_sweep_end_to_end():
    # The live adapter drops straight into run_sweep with a mock model — proving the
    # execution path works offline; only real credentials + spend are missing.
    def perfect_model(config, prompt):
        # Recover the instruction from the prompt and defer to the reference
        # classifier, standing in for a competent model.
        instruction = prompt.split("Request:", 1)[1].rsplit("Specialist:", 1)[0].strip()
        return classify_request(instruction).role.value

    points = run_sweep(
        [SweepConfig("mock-llm")],
        live_router_factory(perfect_model),
        cost_per_call=_fixed_cost(0.0),
        dataset=_DATASET,
    )
    assert points[0].pass_rate == 1.0  # a competent model matches the labels


def test_classify_prompt_matches_product_routing_semantics():
    # Regression guard from the first LIVE sweep (2026-07-17): the prompt used to
    # describe teardown as provisioning, contradicting the teardown→deploy cascade
    # (see the ROUTING_EVAL_SET adversarial notes), and both live adversarial misses
    # traced to that line. The prompt must keep teardown under deploy and spell out
    # that diagnostic intent wins over infrastructure nouns.
    from src.agents.ai.model_sweep import _classify_prompt

    prompt = _classify_prompt("x")
    deploy_desc = prompt.split("'deploy'", 1)[1].split("'kagent'", 1)[0]
    provision_desc = prompt.split("'provision'", 1)[1].split("'deploy'", 1)[0]
    assert "tear down" in deploy_desc  # teardown is delivery-lifecycle, by design
    assert "tear down" not in provision_desc
    assert "investigate" in prompt.lower()  # diagnostic verbs called out for kagent
