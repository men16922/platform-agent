from src.agents.ai import deploy_recorder as rec


class _FakeTable:
    def __init__(self):
        self.items = []

    def put_item(self, *, Item):
        self.items.append(Item)


_STEPS = [
    {"tool": "build_image", "args": {"service_name": "orders-api", "version": "v1.4.2"}, "result": {"error": None}},
    {"tool": "push_image", "args": {}, "result": {"error": None}},
    {"tool": "deploy_to_cluster", "args": {"service_name": "orders-api", "version": "v1.4.2"}, "result": {"error": None}},
    {"tool": "validate_deployment", "args": {}, "result": {"error": None}},
]


def test_record_deploy_writes_deploy_and_activity_rows():
    table = _FakeTable()
    ids = rec.record_deploy(
        instruction="Deploy orders-api v1.4.2 to the local cluster",
        model="local-qwen",
        provider="onprem",
        summary="done",
        steps=_STEPS,
        ok=True,
        table=table,
    )
    assert ids and ids["deployment_id"].startswith("DEP-")
    assert ids["activity_id"].startswith("ACT-")

    by_pk = {item["PK"]: item for item in table.items}
    assert set(by_pk) == {"DEPLOY", "ACTIVITY"}

    deploy = by_pk["DEPLOY"]
    assert deploy["service"] == "orders-api"
    assert deploy["version"] == "v1.4.2"
    assert deploy["provider"] == "onprem"
    assert deploy["status"] == "success"
    assert "Qwen" in deploy["agent"]
    assert deploy["SK"].endswith(deploy["deployment_id"])

    activity = by_pk["ACTIVITY"]
    assert activity["tool_calls"] == ["build_image", "push_image", "deploy_to_cluster", "validate_deployment"]
    assert activity["status"] == "success"


def test_record_deploy_failed_status():
    table = _FakeTable()
    rec.record_deploy(
        instruction="Deploy x",
        model="local-qwen",
        provider="onprem",
        summary="boom",
        steps=[{"tool": "build_image", "args": {"service_name": "x", "version": "1"}, "result": {"error": "boom"}}],
        ok=False,
        table=table,
    )
    assert all(item["status"] == "failed" for item in table.items)


def test_record_deploy_disabled_is_noop(monkeypatch):
    monkeypatch.delenv("PLATFORM_ACTIVITY_TABLE", raising=False)
    assert rec.record_deploy(
        instruction="x", model="local-qwen", provider="onprem", summary="", steps=_STEPS, ok=True
    ) is None
