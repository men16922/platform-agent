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

import ast
import json
import os
import pathlib
from unittest import mock

import pytest

from src.agents.platform.reconciler import (
    ROLLBACK_ACTIONS,
    ReconcilerConflict,
    detect_reconciler,
    guard_rollback,
    is_rollback,
)
from src.agents.platform.scope import IncidentScope

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _adapter_rollback_actions() -> set[str]:
    """Every action the execution adapters map from capability `rollback_release`.

    Read from source because `_action_for`'s mapping is a local variable inside
    the function — there is nothing to import. Asking the adapters is the point:
    the previous version of this check kept its own list of clouds and left one
    out, so the set it validated against drifted from the set that exists.
    """
    found: set[str] = set()
    for path in sorted((ROOT / "src/agents/adapters/execution").glob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not isinstance(node, ast.Dict):
                continue
            for key, value in zip(node.keys, node.values):
                if not isinstance(key, ast.Tuple) or not key.elts:
                    continue
                capability = key.elts[0]
                if (
                    isinstance(capability, ast.Constant)
                    and capability.value == "rollback_release"
                    and isinstance(value, ast.Constant)
                    and isinstance(value.value, str)
                ):
                    found.add(value.value)
    return found


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

    def test_every_rollback_action_the_adapters_emit_is_registered(self):
        """
        A rollback action missing from this set is a silently-unguarded path.

        ⚠️ This replaces a hand-written enumeration that had the very bug it was
        written to catch. It iterated ``("ONPREM-", "GCP-", "AZURE-")`` — **AWS
        was not in the list of clouds** — so `AWS-RollbackEKSDeployment` and
        `AWS-RollbackLambdaAlias` sat unregistered while this test stayed green
        (measured 2026-08-16). It also asked `any(...)`, which one action per
        prefix satisfies even when a sibling of the same cloud is missing.

        So the expected set is now **derived from the execution adapters** rather
        than typed out here. `_action_for`'s mapping is a local inside the
        function, hence the AST read: importing it is not possible, and a second
        hand-written list is exactly what failed.
        """
        emitted = _adapter_rollback_actions()
        assert len(emitted) >= 7, f"the adapter sweep found only {sorted(emitted)}"
        missing = sorted(emitted - ROLLBACK_ACTIONS)
        assert not missing, (
            f"{missing} map from capability `rollback_release` in the execution "
            "adapters but are not in ROLLBACK_ACTIONS, so `is_rollback` calls them "
            "False and the reconciler-conflict guard lets them through."
        )

    def test_the_set_names_no_action_nobody_emits(self):
        """Reverse direction — a stale entry means the set describes a path that
        no longer exists, which is how a list stops being checkable."""
        stale = sorted(ROLLBACK_ACTIONS - _adapter_rollback_actions())
        assert not stale, f"ROLLBACK_ACTIONS lists actions no adapter emits: {stale}"


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


# ---------------------------------------------------------------------------
# 4. The refusal must be a property of the ACTION, not of one runner
# ---------------------------------------------------------------------------

class TestEveryRunnerThatCanRollBackAsks:
    """Measured 2026-08-18: `ROLLBACK_ACTIONS` named all four providers, and
    exactly one runner called `guard_rollback`.

    M31 fixed the *list* — the two AWS entries were missing — and the guard above
    (`test_every_rollback_action_the_adapters_emit_is_registered`) keeps the list
    honest. Nothing counted the **call sites**, so a rollback on GCP or Azure went
    straight to the patch. That is M18's sibling-set failure one level up: the
    siblings being counted were actions, when the set that mattered was runners.

    Two reasons for skipping were checked and neither survived:

      * "those runners have no manifest" — false. Both fetch the deployment
        immediately before mutating it (to read the container name) and drop
        `metadata`, which is where the ownership markers live. The check costs
        no extra API call.
      * "our registry only declares kind/k3s envs" — not a reason. `reconciler.py`
        reads ownership off the live object precisely because the registry says
        what *should* be managed, and the question is what *is*.

    Gaps must be declared with a reason, and a declared gap that stops being real
    fails here too — an allowlist that outlives its justification is how the
    previous version of this file drifted.
    """

    #: runner module -> why it does not call the guard. Empty = it must call it.
    JUSTIFIED_GAPS = {
        "azure_runner.py": (
            "Azure's executor does not dispatch to its runner at all — it logs and "
            "reports success without executing (open item, measured 2026-08-16). "
            "Wiring the refusal into a path that never runs would be a guard with "
            "no load on it; fix the dispatch first, then this entry must go."
        ),
    }

    def _runner_sources(self) -> dict[str, str]:
        d = ROOT / "src" / "agents" / "operations" / "runners"
        return {p.name: p.read_text(encoding="utf-8") for p in d.glob("*_runner.py")}

    @staticmethod
    def _calls_the_guard(src: str) -> bool:
        """A *call*, found by AST — not the substring.

        The first version of this asked `"guard_rollback" in src`, and deleting
        the call still passed because the import line survived. An unused import
        is precisely the shape a half-reverted fix leaves behind, so the check
        that was supposed to catch the revert was satisfied by its debris.
        """
        for node in ast.walk(ast.parse(src)):
            if isinstance(node, ast.Call):
                func = node.func
                name = getattr(func, "id", None) or getattr(func, "attr", None)
                if name == "guard_rollback":
                    return True
        return False

    def _runners_that_execute_a_rollback(self) -> dict[str, str]:
        return {
            name: src
            for name, src in self._runner_sources().items()
            if any(action in src for action in ROLLBACK_ACTIONS)
        }

    def test_the_sweep_found_the_runners(self):
        """Guards the guard: a glob that matches nothing passes vacuously."""
        found = self._runners_that_execute_a_rollback()
        assert len(found) >= 3, f"expected the known rollback-capable runners, got {sorted(found)}"

    def test_every_rollback_capable_runner_calls_the_guard(self):
        offenders = [
            name
            for name, src in self._runners_that_execute_a_rollback().items()
            if not self._calls_the_guard(src) and name not in self.JUSTIFIED_GAPS
        ]
        assert not offenders, (
            f"{offenders} can execute an action in ROLLBACK_ACTIONS without asking "
            "whether a reconciler owns the target. The rollback succeeds, the "
            "verifier can see it, and then it is silently reverted — with the "
            "incident recorded as remediated"
        )

    def test_a_justified_gap_that_closed_must_be_removed(self):
        stale = [
            name
            for name, src in self._runner_sources().items()
            if name in self.JUSTIFIED_GAPS and self._calls_the_guard(src)
        ]
        assert not stale, (
            f"{stale} now calls the guard but is still listed as a justified gap — "
            "an allowlist nobody prunes stops describing reality"
        )

    def test_aws_has_no_runner_module_and_that_is_why_it_is_absent(self):
        """AWS is not a silently-missed sibling; it has a different shape.

        `AWS-RollbackEKSDeployment` / `AWS-RollbackLambdaAlias` execute as SSM
        Automation documents dispatched from `aws/executor.py`, so there is no
        `aws_runner.py` for the sweep above to find. Recorded here so the absence
        reads as measured rather than overlooked — if an AWS runner ever appears,
        the sweep picks it up and the assertion above starts applying to it.
        """
        assert "aws_runner.py" not in self._runner_sources()
        aws_actions = {a for a in ROLLBACK_ACTIONS if a.startswith("AWS-")}
        assert aws_actions, "the AWS rollback actions vanished from the set"
        executor = (ROOT / "src/agents/operations/aws/executor.py").read_text(encoding="utf-8")
        assert "start_automation_execution" in executor


# ---------------------------------------------------------------------------
# 5. GCP: the refusal must land before the patch, on the real execution path
# ---------------------------------------------------------------------------

class TestGcpRunnerRefusesBeforeMutating:
    """Structural checks say the call exists; only this says it happens in time.

    The GKE rollback is a strategic-merge patch, and a patch that has already
    been sent cannot be un-sent — so `requests.patch` must never be reached when
    a reconciler owns the target. The manifest fed to the guard is the same one
    this walk was already fetching, which is the whole reason the check is free.
    """

    @staticmethod
    def _cluster_metadata():
        resp = mock.Mock()
        resp.status_code = 200
        resp.json.return_value = {
            "endpoint": "10.0.0.1",
            "masterAuth": {"clusterCaCertificate": "dGVzdC1jYS1jZXJ0"},
        }
        return resp

    @staticmethod
    def _deployment(manifest):
        resp = mock.Mock()
        resp.status_code = 200
        resp.json.return_value = manifest
        return resp

    PARAMS = {
        "ProjectId": ["gcp-proj-1"],
        "ClusterName": ["gke-cluster-1"],
        "WorkloadName": ["loki-gateway"],
        "Namespace": ["acme-dev-logging"],
        "RollbackVersion": ["registry.example/loki:1.2.3"],
    }

    def _run(self, manifest):
        from src.agents.operations.runners.gcp_runner import run_gcp_action

        with mock.patch(
            "src.agents.operations.runners.gcp_runner.get_gcp_access_token",
            return_value="fake-gcp-token",
        ), mock.patch("requests.get") as mock_get, mock.patch("requests.patch") as mock_patch:
            def _get(url, *a, **k):
                # Dispatch on URL rather than call order: the walk fetches cluster
                # metadata first and the deployment second, but pinning a fixed
                # sequence would make this test fail for an unrelated extra read.
                if "container.googleapis.com" in url:
                    return self._cluster_metadata()
                return self._deployment(manifest)

            mock_get.side_effect = _get
            patched = mock.Mock()
            patched.status_code = 200
            mock_patch.return_value = patched
            with mock.patch.dict(os.environ, {"GCP_MOCK": "false", "TESTING": "False"}):
                try:
                    run_gcp_action("GCP-RollbackGKEWorkload", self.PARAMS, _Log(), SCOPE)
                    raised = None
                except ReconcilerConflict as exc:
                    raised = exc
            return raised, mock_patch

    def test_the_patch_never_runs_when_argocd_owns_the_workload(self):
        manifest = dict(ARGOCD_MANAGED)
        manifest["spec"] = {"template": {"spec": {"containers": [{"name": "loki", "image": "x:1"}]}}}
        raised, mock_patch = self._run(manifest)
        assert raised is not None, "an ArgoCD-owned GKE workload was rolled back anyway"
        assert "would revert" in str(raised)
        mock_patch.assert_not_called()

    def test_an_unowned_workload_still_rolls_back(self):
        """The refusal must be narrow. Blocking every GKE rollback would trade a
        quiet wrong fix for a loud absent one, which is the same bad trade the
        onprem read already refuses to make."""
        manifest = {
            "metadata": {"name": "loki-gateway", "namespace": "acme-dev-logging"},
            "spec": {"template": {"spec": {"containers": [{"name": "loki", "image": "x:1"}]}}},
        }
        raised, mock_patch = self._run(manifest)
        assert raised is None, f"an unmanaged workload was refused: {raised}"
        mock_patch.assert_called_once()
