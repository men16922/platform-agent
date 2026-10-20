"""A real local read-only run must survive reload without inventing a deploy."""
import json

import pytest

from src.agents.ai import deploy_recorder as rec


@pytest.mark.parametrize("ok", [True, False])
def test_readonly_run_records_activity_without_deployment(tmp_path, monkeypatch, ok):
    store = tmp_path / "activity.jsonl"
    monkeypatch.delenv("PLATFORM_ACTIVITY_TABLE", raising=False)
    monkeypatch.setenv("PLATFORM_ACTIVITY_FILE", str(store))
    steps = [{"tool": "list_pods", "args": {"namespace": "acme-dev-observability"},
              "result": {"ok": ok, "output": "No resources found" if ok else "Forbidden"}}]
    ids = rec.record_deploy(instruction="Read pods only", model="local-qwen", provider="onprem",
                            summary="No changes", steps=steps, ok=ok)
    rows = [json.loads(line) for line in store.read_text().splitlines()]
    assert [row["PK"] for row in rows] == ["ACTIVITY"]
    assert ids == {"activity_id": rows[0]["activity_id"]}
    assert "deployment_id" not in rows[0]
    assert rows[0]["status"] == ("success" if ok else "failed")
    assert rows[0]["tool_calls"] == ["list_pods"]
    assert json.loads(rows[0]["trace"])[0]["result"] == steps[0]["result"]
    assert rows[0]["cost_metrics"]["tool_calls_total"] == 1


def test_read_then_deploy_keeps_the_deployment_record(tmp_path, monkeypatch):
    store = tmp_path / "activity.jsonl"
    monkeypatch.delenv("PLATFORM_ACTIVITY_TABLE", raising=False)
    monkeypatch.setenv("PLATFORM_ACTIVITY_FILE", str(store))
    steps = [
        {"tool": "list_pods", "args": {"namespace": "acme-dev-observability"}, "result": {"ok": True}},
        {"tool": "deploy_service", "args": {"service_name": "orders-api", "version": "v1"}, "result": {"ok": True}},
    ]
    ids = rec.record_deploy(instruction="Inspect then deploy", model="local-qwen", provider="onprem",
                            summary="Deployed", steps=steps, ok=True)
    rows = [json.loads(line) for line in store.read_text().splitlines()]
    assert [row["PK"] for row in rows] == ["DEPLOY", "ACTIVITY"]
    assert rows[0]["service"] == "orders-api"
    assert ids["deployment_id"] == rows[1]["deployment_id"]
