from src.agents.ai.reconciliation import apply_gate, reconcile
from src.agents.models import (
    AlarmContext,
    AnalyzerOutput,
    DetectorOutput,
    RemediationMode,
    Severity,
)


def _detector(state="ALARM", reason="pods OOMKilled in orders namespace", metrics=None, logs=None):
    return DetectorOutput(
        alarm=AlarmContext(
            alarm_name="orders-api-oom",
            alarm_arn="arn:x",
            state=state,
            reason=reason,
            metric_name="MemoryUtilization",
            namespace="orders",
            dimensions={"deployment": "orders-api"},
        ),
        related_metrics=metrics if metrics is not None else {"MemoryUtilization": 98.0},
        log_insights_results=logs if logs is not None else [{"@message": "orders-api container OOMKilled restarting"}],
    )


def _analyzer(detector, root_cause="orders-api memory utilization saturated, OOMKilled restarts", severity=Severity.P1, confidence=0.9):
    return AnalyzerOutput(detector=detector, root_cause=root_cause, severity=severity, confidence=confidence)


def test_grounded_p1_stays_auto():
    det = _detector()
    ana = _analyzer(det)
    res = reconcile(det, ana)
    assert res.grounded is True
    assert res.mode_override is None
    assert apply_gate(RemediationMode.AUTO, res) == RemediationMode.AUTO


def test_alarm_not_firing_downgrades():
    det = _detector(state="OK")
    ana = _analyzer(det)
    res = reconcile(det, ana)
    assert res.grounded is False
    assert any("not a firing state" in i for i in res.issues)
    assert apply_gate(RemediationMode.AUTO, res) == RemediationMode.APPROVE


def test_no_evidence_downgrades():
    det = _detector(reason="", metrics={}, logs=[])
    ana = _analyzer(det)
    res = reconcile(det, ana)
    assert res.grounded is False
    assert any("no supporting evidence" in i for i in res.issues)


def test_p1_low_confidence_downgrades():
    det = _detector()
    ana = _analyzer(det, confidence=0.2)
    res = reconcile(det, ana)
    assert res.grounded is False
    assert any("low confidence" in i for i in res.issues)
    assert apply_gate(RemediationMode.AUTO, res) == RemediationMode.APPROVE


def test_hallucinated_root_cause_downgrades():
    det = _detector()  # evidence is all about orders-api memory/OOM
    # root cause invents an unrelated payment DB story — no overlap with evidence
    ana = _analyzer(det, root_cause="payment gateway database deadlock exhausted connection pool replication")
    res = reconcile(det, ana)
    assert res.grounded is False
    assert res.grounding_ratio < 0.3
    assert any("grounding" in i for i in res.issues)


def test_thin_evidence_skips_grounding_check():
    # normalized-only signal (no logs/metrics) with a non-overlapping heuristic
    # root_cause — the vocabulary check is skipped, so this stays grounded on the
    # strength of firing state + confidence (avoids false-positive on on-prem).
    det = _detector(metrics={}, logs=[])
    ana = _analyzer(det, root_cause="heuristic: pod crash loop (OOM)")
    res = reconcile(det, ana)
    assert res.grounded is True
    assert apply_gate(RemediationMode.AUTO, res) == RemediationMode.AUTO


def test_apply_gate_never_upgrades_approve():
    det = _detector(state="OK")
    ana = _analyzer(det)
    res = reconcile(det, ana)  # ungrounded, override=APPROVE
    # a decision already at APPROVE/MANUAL is never escalated to AUTO
    assert apply_gate(RemediationMode.APPROVE, res) == RemediationMode.APPROVE
    assert apply_gate(RemediationMode.MANUAL, res) == RemediationMode.MANUAL


def test_grounded_result_leaves_mode_untouched():
    det = _detector()
    ana = _analyzer(det)
    res = reconcile(det, ana)
    for mode in (RemediationMode.AUTO, RemediationMode.APPROVE, RemediationMode.MANUAL):
        assert apply_gate(mode, res) == mode


def test_to_dict_shape():
    det = _detector(state="OK")
    res = reconcile(det, _analyzer(det))
    d = res.to_dict()
    assert set(d) == {"grounded", "issues", "mode_override", "grounding_ratio"}
    assert d["mode_override"] == "APPROVE"
