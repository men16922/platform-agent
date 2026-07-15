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
    # activity links to its deployment detail
    assert activity["deployment_id"] == deploy["deployment_id"]


def test_record_route_activity_writes_trace_frames():
    table = _FakeTable()
    trace = [
        {"kind": "consensus", "role": "deploy", "agreement": 1.0, "votes": {"deploy": 5}, "fell_back": False},
        {"kind": "plan", "steps": [{"role": "deploy", "instruction": "deploy orders-api", "delegated": True}]},
    ]
    activity_id = rec.record_route_activity(
        instruction="Deploy orders-api and confirm healthy",
        trace=trace,
        tool_calls=["deploy"],
        status="success",
        table=table,
    )
    assert activity_id and activity_id.startswith("ROUTE-")
    assert len(table.items) == 1
    item = table.items[0]
    assert item["PK"] == "ACTIVITY"
    assert item["type"] == "route"
    assert item["tool_calls"] == ["deploy"]
    # The consensus + plan frames are serialized into the dashboard-rendered trace.
    assert '"kind": "consensus"' in item["trace"]
    assert '"kind": "plan"' in item["trace"]


def test_record_route_activity_disabled_is_noop(monkeypatch):
    monkeypatch.delenv("PLATFORM_ACTIVITY_TABLE", raising=False)
    monkeypatch.delenv("PLATFORM_ACTIVITY_FILE", raising=False)
    assert rec.record_route_activity(instruction="x", trace=[]) is None


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


def test_composite_run_splits_into_provision_and_deploy_rows():
    table = _FakeTable()
    steps = [
        {"tool": "provision_cluster", "args": {"cluster_name": "platform-agent", "mode": "kind"}, "result": {"success": True}},
        {"tool": "deploy_service", "args": {"service_name": "orders-api", "version": "v1.0.0"}, "result": {"error": None}},
    ]
    rec.record_deploy(
        instruction="Provision and deploy orders-api", model="local-qwen", provider="onprem",
        summary="ok", steps=steps, ok=True, table=table,
    )
    by_type = {r["type"]: r for r in rec.read_deploys(table)}
    assert set(by_type) == {"provision", "deploy"}
    assert by_type["provision"]["service"] == "platform-agent"
    assert by_type["deploy"]["service"] == "orders-api"
    assert by_type["deploy"]["cluster"] == "platform-agent"  # correlation key


def test_natural_language_teardown_cascades_to_deployments():
    table = _FakeTable()
    rec.record_deploy(
        instruction="Provision and deploy", model="local-qwen", provider="onprem", summary="ok",
        steps=[
            {"tool": "provision_cluster", "args": {"cluster_name": "platform-agent", "mode": "kind"}, "result": {"success": True}},
            {"tool": "deploy_service", "args": {"service_name": "orders-api", "version": "v1.0.0"}, "result": {"error": None}},
        ],
        ok=True, table=table,
    )
    # A natural-language "tear down the cluster" run routes through the teardown cascade.
    rec.record_deploy(
        instruction="Tear down the cluster", model="local-qwen", provider="onprem", summary="torn down",
        steps=[{"tool": "teardown_cluster", "args": {"cluster_name": "platform-agent", "mode": "kind"}, "result": {"success": True}}],
        ok=True, table=table,
    )
    by_type = {r["type"]: r for r in rec.read_deploys(table)}
    assert by_type["provision"]["status"] == "rolled-back"
    assert by_type["deploy"]["status"] == "rolled-back"  # app removed with its cluster
