from src.agents.provisioning.cost_estimator import (
    BUDGET_HARD_BLOCK,
    BUDGET_OK,
    BUDGET_SOFT_WARNING,
    BUDGET_THROTTLE,
    evaluate_budget,
    gate_provision_cost,
)


def test_no_budget_is_ok_and_never_blocks():
    g = evaluate_budget(1000.0, 0.0)
    assert g.level == BUDGET_OK
    assert g.allowed is True and g.require_approval is False


def test_under_warn_is_ok():
    g = evaluate_budget(50.0, 100.0)  # 50%
    assert g.level == BUDGET_OK
    assert g.allowed is True


def test_soft_warning_band():
    g = evaluate_budget(85.0, 100.0)  # 85% >= warn 0.8
    assert g.level == BUDGET_SOFT_WARNING
    assert g.allowed is True and g.require_approval is False


def test_throttle_requires_approval():
    g = evaluate_budget(120.0, 100.0)  # 120% >= throttle 1.0
    assert g.level == BUDGET_THROTTLE
    assert g.allowed is True and g.require_approval is True


def test_hard_block_over_cap():
    g = evaluate_budget(200.0, 100.0)  # 200% >= block 1.5
    assert g.level == BUDGET_HARD_BLOCK
    assert g.allowed is False


def test_budget_from_env(monkeypatch):
    monkeypatch.setenv("PLATFORM_MONTHLY_BUDGET_USD", "100")
    g = evaluate_budget(180.0)  # 180% -> HARD_BLOCK
    assert g.level == BUDGET_HARD_BLOCK
    assert g.budget_usd == 100.0


def test_custom_ratios():
    # tighten the block cap to 1.1x
    g = evaluate_budget(120.0, 100.0, block_ratio=1.1)
    assert g.level == BUDGET_HARD_BLOCK


def test_gate_provision_cost_combines_estimate_and_gate():
    out = gate_provision_cost(
        {"platform": "eks", "desired_count": 2, "cpu": 512, "memory": 1024},
        budget_usd=10.0,  # tiny budget -> should block
    )
    assert "estimate" in out and "budget_gate" in out
    assert out["budget_gate"]["level"] == BUDGET_HARD_BLOCK
    assert out["budget_gate"]["allowed"] is False


def test_to_dict_shape():
    d = evaluate_budget(120.0, 100.0).to_dict()
    assert set(d) == {"level", "allowed", "require_approval", "reason", "estimate_usd", "budget_usd", "ratio"}
