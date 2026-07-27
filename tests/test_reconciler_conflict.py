"""
Guards for Phase 3② — rollback must not be silently undone by a reconciler.

The failure this prevents is not a crash. `kubectl rollout undo` returns 0, the
verifier can observe a healthy workload in the window before reconciliation, and
then ArgoCD puts the broken version back. Every record we keep says the incident
was remediated. So the tests below care about one thing above correctness of the
happy path: **the refusal must happen before the mutation**, because a rollback
that already ran cannot be un-recorded.
"""

from __future__ import annotations

import json

import pytest

from src.agents.platform.reconciler import (
    ROLLBACK_ACTIONS,
    ReconcilerConflict,
    detect_reconciler,
    guard_rollback,
    is_rollback,
)
from src.agents.platform.scope import IncidentScope

SCOPE = IncidentScope(
    tenant="acme", env="dev", kubeconfig_path="/dev/null", approval_id="APR-T"
)

ARGOCD_MANAGED = {
    "metadata": {
        "name": "loki-gateway",
        "namespace": "acme-dev-logging",
        # Exactly what the live cluster stamps under resourceTrackingMethod=annotation.
        "annotations": {
            "argocd.argoproj.io/tracking-id":
                "acme-dev-logging:apps/Deployment:acme-dev-logging/loki-gateway"
        },
    }
}

FLUX_MANAGED = {
    "metadata": {
        "name": "api", "namespace": "acme-dev-logging",
        "labels": {"kustomize.toolkit.fluxcd.io/name": "acme-dev"},
    }
}

UNMANAGED = {"metadata": {"name": "api", "namespace": "acme-dev-logging"}}


class _Log:
    def __init__(self):
        self.events = []

    def info(self, event, **kw):
        self.events.append((event, kw))

    warning = error = info


class TestOwnershipDetection:
    def test_argocd_tracking_annotation_is_the_marker(self):
        assert detect_reconciler(ARGOCD_MANAGED) == "argocd"

    def test_flux_kustomize_label_is_the_marker(self):
        assert detect_reconciler(FLUX_MANAGED) == "flux"

    def test_unmanaged_object_names_nobody(self):
        assert detect_reconciler(UNMANAGED) is None
        assert detect_reconciler(None) is None

    def test_helm_instance_label_alone_is_not_argocd(self):
        """
        `app.kubernetes.io/instance` is shared with plain Helm installs. Treating
        it as ArgoCD ownership would refuse rollbacks on workloads no reconciler
        touches — a guard that blocks real remediation gets switched off.
        """
        helm_only = {"metadata": {"name": "x", "namespace": "y",
                                  "labels": {"app.kubernetes.io/instance": "pa"}}}
        assert detect_reconciler(helm_only) is None


class TestRefusal:
    def test_rollback_on_managed_workload_is_refused(self):
        with pytest.raises(ReconcilerConflict, match="managed by argocd"):
            guard_rollback(action="ONPREM-ArgoRolloutRollback", manifest=ARGOCD_MANAGED,
                           log=_Log(), log_prefix="onprem_runner")

    def test_restart_and_scale_are_not_refused(self):
        """They converge to the desired spec the reconciler already holds."""
        for action in ("ONPREM-RolloutRestartWorkload", "ONPREM-ScaleWorkload"):
            assert not is_rollback(action)
            guard_rollback(action=action, manifest=ARGOCD_MANAGED,
                           log=_Log(), log_prefix="onprem_runner")

    def test_rollback_on_unmanaged_workload_proceeds(self):
        guard_rollback(action="ONPREM-ArgoRolloutRollback", manifest=UNMANAGED,
                       log=_Log(), log_prefix="onprem_runner")

    def test_aligned_desired_unblocks_and_says_so(self):
        log = _Log()
        guard_rollback(action="ONPREM-ArgoRolloutRollback", manifest=ARGOCD_MANAGED,
                       log=log, log_prefix="onprem_runner", desired_aligned=True)
        assert any(e.endswith("rollback_with_aligned_desired") for e, _ in log.events)

    def test_alignment_must_be_asserted_not_assumed(self):
        """
        The default is False on purpose: a caller that has not thought about
        self-heal gets the refusal, not the silent revert.
        """
        import inspect
        sig = inspect.signature(guard_rollback)
        assert sig.parameters["desired_aligned"].default is False

    def test_every_cloud_has_its_rollback_action_registered(self):
        """
        A rollback action missing from this set is a silently-unguarded path.
        Enumerated per cloud so adding a provider without registering its
        rollback fails here rather than in production.
        """
        for prefix in ("ONPREM-", "GCP-", "AZURE-"):
            assert any(a.startswith(prefix) for a in ROLLBACK_ACTIONS), prefix


class TestRunnerRefusesBeforeMutating:
    def test_undo_never_runs_when_argocd_owns_the_workload(self, monkeypatch):
        from src.agents.operations.runners import onprem_runner

        monkeypatch.setenv("ONPREM_EXECUTOR_LIVE", "true")
        monkeypatch.delenv("TESTING", raising=False)
        ran = []

        def fake_kubectl(args, scope, timeout=60):
            ran.append(args)
            if args[0] == "get":
                return 0, json.dumps(ARGOCD_MANAGED), ""
            return 0, "rolled back", ""

        monkeypatch.setattr(onprem_runner, "_run_kubectl", fake_kubectl)
        with pytest.raises(ReconcilerConflict):
            onprem_runner.run_onprem_action(
                "ONPREM-ArgoRolloutRollback",
                {"Namespace": ["acme-dev-logging"], "WorkloadName": ["loki-gateway"]},
                _Log(), SCOPE,
            )
        assert all(a[0] == "get" for a in ran), (
            f"only the ownership read may run before the refusal, got {ran}"
        )

    def test_unreadable_ownership_does_not_block_remediation(self, monkeypatch):
        """
        A kubectl hiccup must not turn into a blanket remediation outage — that
        trades a quiet wrong fix for a loud absent one. The refusal is the
        fail-closed part; this read is best-effort and says so in the log.
        """
        from src.agents.operations.runners import onprem_runner

        monkeypatch.setenv("ONPREM_EXECUTOR_LIVE", "true")
        monkeypatch.delenv("TESTING", raising=False)

        def fake_kubectl(args, scope, timeout=60):
            if args[0] == "get":
                return 1, "", "connection refused"
            return 0, "rolled back", ""

        monkeypatch.setattr(onprem_runner, "_run_kubectl", fake_kubectl)
        log = _Log()
        onprem_runner.run_onprem_action(
            "ONPREM-ArgoRolloutRollback",
            {"Namespace": ["acme-dev-logging"], "WorkloadName": ["api"]},
            log, SCOPE,
        )
        assert any(e == "onprem_runner.ownership_unreadable" for e, _ in log.events)
