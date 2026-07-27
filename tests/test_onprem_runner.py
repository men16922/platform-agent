"""On-Prem action runner — flag-gated real kubectl remediation."""

import pytest

from src.agents.operations.runners import onprem_runner


class _Log:
    """Minimal structlog-style stub that records the last event name."""

    def __init__(self):
        self.events: list[str] = []

    def _record(self, event, **_kw):
        self.events.append(event)

    info = _record
    error = _record
    warning = _record


PARAMS = {"Namespace": ["payments"], "WorkloadName": ["payments-api"], "ClusterName": ["prod"]}

# Live remediation now requires a per-incident scoped credential (Phase 1a); the
# ambient-kubeconfig path was removed. These tests exercise kubectl argv building,
# so they pass a scope with no namespace allowlist — the credential policy itself
# is covered in tests/test_incident_scope.py.
from src.agents.platform.scope import IncidentScope  # noqa: E402

SCOPE = IncidentScope(
    tenant="payments-tenant", env="prod",
    kubeconfig_path="/creds/payments-tenant.kubeconfig", approval_id="APR-TEST",
)


@pytest.fixture
def captured(monkeypatch):
    """Capture kubectl invocations instead of running them; return the calls list."""
    calls: list[list[str]] = []

    def fake(args, scope, timeout=60):
        calls.append(args)
        return 0, "deployment.apps/payments-api restarted", ""

    monkeypatch.setattr(onprem_runner, "_run_kubectl", fake)
    return calls


def test_log_only_by_default(captured, monkeypatch):
    monkeypatch.delenv("ONPREM_EXECUTOR_LIVE", raising=False)
    log = _Log()
    onprem_runner.run_onprem_action("ONPREM-RolloutRestartWorkload", PARAMS, log, SCOPE)
    assert captured == []  # no kubectl
    assert "onprem_runner.log_only" in log.events


def test_live_restart_runs_kubectl(captured, monkeypatch):
    monkeypatch.setenv("ONPREM_EXECUTOR_LIVE", "true")
    monkeypatch.delenv("TESTING", raising=False)
    onprem_runner.run_onprem_action("ONPREM-RolloutRestartWorkload", PARAMS, _Log(), SCOPE)
    assert captured == [["rollout", "restart", "deployment/payments-api", "-n", "payments"]]


def test_live_rollback_reads_ownership_then_runs_kubectl(captured, monkeypatch):
    """
    Since Phase 3② a rollback first asks who owns the workload — an unowned one
    proceeds. The read is part of the contract, not incidental: skipping it is
    how a rollback gets silently reverted by ArgoCD. Ownership refusal itself is
    covered in `test_reconciler_conflict.py`.
    """
    monkeypatch.setenv("ONPREM_EXECUTOR_LIVE", "true")
    monkeypatch.delenv("TESTING", raising=False)
    onprem_runner.run_onprem_action("ONPREM-ArgoRolloutRollback", PARAMS, _Log(), SCOPE)
    assert captured == [
        ["get", "deployment/payments-api", "-o", "json", "-n", "payments"],
        ["rollout", "undo", "deployment/payments-api", "-n", "payments"],
    ]


def test_live_unwired_action_is_log_only(captured, monkeypatch):
    monkeypatch.setenv("ONPREM_EXECUTOR_LIVE", "true")
    monkeypatch.delenv("TESTING", raising=False)
    log = _Log()
    onprem_runner.run_onprem_action("ONPREM-CleanupDiskSpace", PARAMS, log, SCOPE)
    assert captured == []
    assert "onprem_runner.live_unwired" in log.events


def test_live_drain_runs_polite_kubectl(captured, monkeypatch):
    # Polite drain: --ignore-daemonsets + bounded timeout, but NO --force and NO
    # --delete-emptydir-data, so PDBs are honored and data-risky pods block it.
    monkeypatch.setenv("ONPREM_EXECUTOR_LIVE", "true")
    monkeypatch.delenv("TESTING", raising=False)
    params = {"ClusterName": ["prod"], "NodeName": ["worker-3"]}
    onprem_runner.run_onprem_action("ONPREM-DrainNode", params, _Log(), SCOPE)
    assert captured == [["drain", "worker-3", "--ignore-daemonsets", "--timeout=90s"]]
    args = captured[0]
    assert "--force" not in args and "--delete-emptydir-data" not in args


def test_live_drain_missing_node_is_log_only(captured, monkeypatch):
    monkeypatch.setenv("ONPREM_EXECUTOR_LIVE", "true")
    monkeypatch.delenv("TESTING", raising=False)
    log = _Log()
    onprem_runner.run_onprem_action("ONPREM-DrainNode", {"ClusterName": ["prod"]}, log, SCOPE)
    assert captured == []
    assert "onprem_runner.live_missing_target" in log.events


def test_live_scale_runs_kubectl(captured, monkeypatch):
    monkeypatch.setenv("ONPREM_EXECUTOR_LIVE", "true")
    monkeypatch.delenv("TESTING", raising=False)
    params = {**PARAMS, "DesiredReplicas": ["5"]}
    onprem_runner.run_onprem_action("ONPREM-ScaleWorkload", params, _Log(), SCOPE)
    assert captured == [["scale", "deployment/payments-api", "--replicas=5", "-n", "payments"]]


def test_live_scale_missing_replicas_is_log_only(captured, monkeypatch):
    # Scale without a target count can't be inferred safely -> stay log-only.
    monkeypatch.setenv("ONPREM_EXECUTOR_LIVE", "true")
    monkeypatch.delenv("TESTING", raising=False)
    log = _Log()
    onprem_runner.run_onprem_action("ONPREM-ScaleWorkload", PARAMS, log, SCOPE)
    assert captured == []
    assert "onprem_runner.live_missing_target" in log.events


def test_live_scale_to_zero_is_log_only(captured, monkeypatch):
    # Scale-to-zero is a shutdown, not a reversible remediation -> needs a human.
    monkeypatch.setenv("ONPREM_EXECUTOR_LIVE", "true")
    monkeypatch.delenv("TESTING", raising=False)
    log = _Log()
    onprem_runner.run_onprem_action("ONPREM-ScaleWorkload", {**PARAMS, "DesiredReplicas": ["0"]}, log, SCOPE)
    assert captured == []
    assert "onprem_runner.live_missing_target" in log.events


def test_live_missing_workload_is_log_only(captured, monkeypatch):
    monkeypatch.setenv("ONPREM_EXECUTOR_LIVE", "true")
    monkeypatch.delenv("TESTING", raising=False)
    log = _Log()
    onprem_runner.run_onprem_action("ONPREM-RolloutRestartWorkload", {"Namespace": ["payments"]}, log, SCOPE)
    assert captured == []
    assert "onprem_runner.live_missing_target" in log.events


def test_testing_env_forces_log_only(captured, monkeypatch):
    # Even with the live flag, TESTING=True keeps it a no-op (gate safety).
    monkeypatch.setenv("ONPREM_EXECUTOR_LIVE", "true")
    monkeypatch.setenv("TESTING", "True")
    onprem_runner.run_onprem_action("ONPREM-RolloutRestartWorkload", PARAMS, _Log(), SCOPE)
    assert captured == []


def test_live_kubectl_failure_raises(monkeypatch):
    monkeypatch.setenv("ONPREM_EXECUTOR_LIVE", "true")
    monkeypatch.delenv("TESTING", raising=False)
    monkeypatch.setattr(onprem_runner, "_run_kubectl", lambda args, scope, timeout=60: (1, "", "not found"))
    with pytest.raises(RuntimeError, match="kubectl"):
        onprem_runner.run_onprem_action("ONPREM-RolloutRestartWorkload", PARAMS, _Log(), SCOPE)
