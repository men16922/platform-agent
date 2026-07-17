"""Distilled memory tier tests — offline, deterministic (⑨ B-1)."""

from src.agents.ai.memory_tier import (
    DistilledMemory,
    MemoryStore,
    distill,
    scrub,
    signature,
)


def test_signature_is_stable_and_case_insensitive():
    a = signature("onprem", "orders-api", "deploy_to_cluster")
    b = signature("OnPrem", "Orders-API", "Deploy_To_Cluster")
    assert a == b and len(a) == 16
    # Different failed step -> different signature.
    assert signature("onprem", "orders-api", "validate") != a


def test_scrub_redacts_secrets_and_pii():
    text = "failed: password=hunter2 token: ghp_abcdefgh12345678 for ops@example.com Bearer xyz.tok"
    out = scrub(text)
    assert "hunter2" not in out
    assert "ghp_abcdefgh12345678" not in out
    assert "ops@example.com" not in out
    assert "xyz.tok" not in out
    assert "[redacted]" in out


def test_distill_clean_run_has_no_failure_fields():
    record = {"provider": "onprem", "service": "orders-api", "ok": True, "steps": []}
    m = distill(record)
    assert m.ok is True and m.failed_step == "" and m.symptom == ""
    assert m.signature == signature("onprem", "orders-api", "")


def test_distill_captures_first_failing_step_and_scrubs_symptom():
    record = {
        "provider": "aws",
        "service": "payments",
        "ok": False,
        "steps": [
            {"tool": "build_image", "ok": True},
            {"tool": "deploy_to_cluster", "ok": False, "error": "denied: token=sk-abcdefgh12345678"},
        ],
    }
    m = distill(record)
    assert m.ok is False and m.failed_step == "deploy_to_cluster"
    assert "sk-abcdefgh12345678" not in m.symptom and "[redacted]" in m.symptom
    assert m.signature == signature("aws", "payments", "deploy_to_cluster")


def test_distill_is_defensive_about_missing_fields():
    m = distill({})
    assert m.provider == "unknown" and m.service == "unknown"
    assert m.ok is False and m.failed_step == "unknown"


def test_store_consolidates_repeated_signature():
    store = MemoryStore()
    rec = {"provider": "onprem", "service": "orders-api", "ok": False,
           "steps": [{"tool": "validate", "ok": False, "error": "probe failed"}]}
    first = store.record(rec)
    assert first.seen == 1
    second = store.record(rec)
    assert second.seen == 2  # same signature -> consolidated, not duplicated
    assert len(store.all()) == 1


def test_store_recall_by_signature_and_by_fields():
    store = MemoryStore()
    store.record({"provider": "gcp", "service": "checkout", "ok": False,
                  "steps": [{"tool": "push_image", "ok": False, "error": "quota"}]})
    assert store.recall_for("gcp", "checkout", "push_image") is not None
    assert store.recall_for("gcp", "checkout", "validate") is None  # different signature
    assert store.recall("does-not-exist") is None


def test_store_dicts_roundtrip_preserves_consolidation():
    store = MemoryStore()
    rec = {"provider": "azure", "service": "web", "ok": False,
           "steps": [{"tool": "deploy_to_cluster", "ok": False, "error": "timeout"}]}
    store.record(rec)
    store.record(rec)
    restored = MemoryStore.from_dicts(store.to_dicts())
    (mem,) = restored.all()
    assert mem.seen == 2 and mem.failed_step == "deploy_to_cluster"
    assert isinstance(DistilledMemory.from_dict(mem.to_dict()), DistilledMemory)


def test_store_latest_symptom_wins_but_count_accumulates():
    store = MemoryStore()
    store.remember(DistilledMemory(signature("p", "s", "x"), "p", "s", False, "x", "old symptom"))
    merged = store.remember(DistilledMemory(signature("p", "s", "x"), "p", "s", False, "x", "new symptom"))
    assert merged.seen == 2 and merged.symptom == "new symptom"
