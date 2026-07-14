from src.agents.ai.deploy_recorder import _cost_metrics, record_deploy


class _FakeTable:
    def __init__(self):
        self.items = []

    def put_item(self, Item):
        self.items.append(Item)


def test_cost_metrics_counts_tools_and_reasoning():
    trace = [
        {"kind": "reasoning", "text": "planning"},
        {"kind": "tool", "tool": "build_image"},
        {"kind": "tool", "tool": "push_image"},
        {"kind": "tool", "tool": "build_image"},
    ]
    m = _cost_metrics([], trace)
    assert m["tool_calls_total"] == 3
    assert m["tool_calls_by_name"] == {"build_image": 2, "push_image": 1}
    assert m["reasoning_steps"] == 1


def test_cost_metrics_sums_token_usage_mixed_key_styles():
    trace = [
        {"kind": "reasoning", "usage": {"input_tokens": 100, "output_tokens": 20}},
        {"kind": "tool", "tool": "deploy_to_cluster", "usage": {"prompt_tokens": 50, "completion_tokens": 10}},
    ]
    m = _cost_metrics([], trace)
    assert m["input_tokens"] == 150
    assert m["output_tokens"] == 30
    assert m["total_tokens"] == 180


def test_cost_metrics_zero_when_no_usage():
    m = _cost_metrics([{"tool": "build_image"}], None)
    assert m["total_tokens"] == 0
    assert m["tool_calls_total"] == 1


def test_record_deploy_attaches_cost_metrics():
    table = _FakeTable()
    record_deploy(
        instruction="deploy orders-api",
        model="local-qwen",
        provider="onprem",
        summary="ok",
        steps=[{"tool": "deploy_service", "args": {"service_name": "orders-api", "version": "v1"}}],
        ok=True,
        table=table,
    )
    activity = next(i for i in table.items if i["PK"] == "ACTIVITY")
    assert "cost_metrics" in activity
    assert activity["cost_metrics"]["tool_calls_by_name"] == {"deploy_service": 1}
