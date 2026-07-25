"""
Guards for the Terraform → GitOps handoff preflight.

The handoff is `terraform state rm` + adoption of an already-installed release.
Adoption must be a no-op; if the controller treats the objects as new it deletes
and recreates them, taking any PVC with them. So the checker's job is to refuse
until it can *prove* safety — and to not cry wolf, because a checker with false
positives gets ignored, which is worse than not having one.
"""

from __future__ import annotations

from src.agents.platform.handoff import (
    check_live_matches_rendered,
    diff_live_against_rendered,
    check_ownership,
    check_source_reachable,
    check_stateful,
    preflight,
    rollback_commands,
)


def _owned(kind: str, name: str, release="loki", namespace="monitoring", **extra):
    metadata = {
        "name": name,
        "labels": {"app.kubernetes.io/managed-by": "Helm"},
        "annotations": {
            "meta.helm.sh/release-name": release,
            "meta.helm.sh/release-namespace": namespace,
        },
    }
    metadata.update(extra)
    return {"kind": kind, "metadata": metadata}


class TestOwnership:
    def test_fully_owned_release_passes(self):
        finding = check_ownership(
            [_owned("Deployment", "loki"), _owned("Service", "loki")], "loki", "monitoring"
        )
        assert finding.passed is True

    def test_missing_managed_by_blocks(self):
        resource = _owned("Deployment", "loki")
        resource["metadata"]["labels"] = {}
        finding = check_ownership([resource], "loki", "monitoring")
        assert finding.passed is False and finding.blocking is True

    def test_wrong_release_name_blocks(self):
        finding = check_ownership([_owned("Deployment", "loki", release="other")], "loki", "monitoring")
        assert finding.passed is False
        assert "release-name" in finding.detail

    def test_wrong_release_namespace_blocks(self):
        finding = check_ownership(
            [_owned("Deployment", "loki", namespace="elsewhere")], "loki", "monitoring"
        )
        assert finding.passed is False
        assert "release-namespace" in finding.detail

    def test_controller_created_descendants_are_ignored(self):
        """
        Pods/ReplicaSets are created by their controller and inherit labels; they
        never carry Helm ownership. Judging them produced a false BLOCKED on a
        perfectly adoptable release.
        """
        pod = {
            "kind": "Pod",
            "metadata": {"name": "loki-0", "ownerReferences": [{"kind": "StatefulSet"}]},
        }
        finding = check_ownership([_owned("StatefulSet", "loki"), pod], "loki", "monitoring")
        assert finding.passed is True
        assert "all 1 resources" in finding.detail

    def test_empty_release_cannot_be_proven_safe(self):
        """Nothing to inspect is not the same as nothing wrong."""
        finding = check_ownership([], "loki", "monitoring")
        assert finding.passed is False and finding.blocking is True

    def test_only_descendants_also_cannot_be_proven(self):
        pod = {"kind": "Pod", "metadata": {"name": "x", "ownerReferences": [{"kind": "ReplicaSet"}]}}
        assert check_ownership([pod], "loki", "monitoring").passed is False


class TestStateful:
    def test_stateless_release_is_fine(self):
        finding = check_stateful([_owned("Deployment", "demo")], snapshot_taken=False)
        assert finding.passed is True

    def test_pvc_without_snapshot_blocks(self):
        finding = check_stateful(
            [_owned("PersistentVolumeClaim", "storage-loki-0")], snapshot_taken=False
        )
        assert finding.passed is False and finding.blocking is True
        assert "destroy data" in finding.detail

    def test_statefulset_without_snapshot_blocks(self):
        assert check_stateful([_owned("StatefulSet", "loki")], snapshot_taken=False).passed is False

    def test_snapshot_assertion_clears_it(self):
        finding = check_stateful([_owned("StatefulSet", "loki")], snapshot_taken=True)
        assert finding.passed is True
        assert "snapshot was asserted" in finding.detail


class TestSourceReachable:
    def test_up_to_date_remote_passes(self):
        assert check_source_reachable(0, True).passed is True

    def test_unpushed_commits_block(self):
        """
        The engine syncs the remote, not the working tree. Unpushed chart edits
        guarantee churn that is easily misread as an adoption failure.
        """
        finding = check_source_reachable(18, True)
        assert finding.passed is False
        assert "18 commit" in finding.detail

    def test_no_remote_blocks(self):
        finding = check_source_reachable(0, False)
        assert finding.passed is False
        assert "nothing to sync from" in finding.detail


class TestVerdict:
    def _run(self, **overrides):
        kwargs = {
            "release": "demo",
            "namespace": "argo-rollouts",
            "revision": 3,
            "resources": [_owned("Deployment", "demo", release="demo", namespace="argo-rollouts")],
            "commits_ahead": 0,
            "remote_configured": True,
            "snapshot_taken": False,
        }
        kwargs.update(overrides)
        return preflight(**kwargs)

    def test_clean_release_is_safe(self):
        assert self._run().safe is True

    def test_any_blocking_failure_makes_it_unsafe(self):
        assert self._run(commits_ahead=1).safe is False

    def test_unknown_revision_blocks_because_no_churn_becomes_unverifiable(self):
        result = self._run(revision=None)
        # The baseline finding is advisory, but a missing revision means the
        # no-churn claim could never be checked afterwards.
        assert any(f.check == "revision-baseline" and not f.passed for f in result.findings)

    def test_blockers_are_reported_individually(self):
        result = self._run(commits_ahead=5, resources=[])
        assert {f.check for f in result.blockers} == {"ownership-metadata", "source-reachable"}

    def test_serialisation_carries_the_verdict_and_baseline(self):
        payload = self._run().to_dict()
        assert payload["safe"] is True
        assert payload["revision_before"] == 3
        # baseline, ownership, stateful, source-reachable, live-matches-rendered
        assert len(payload["findings"]) == 5


class TestRollback:
    def test_import_command_restores_single_ownership(self):
        commands = rollback_commands("helm_release.loki", "loki", "monitoring")
        assert "terraform import helm_release.loki monitoring/loki" in commands[0]

    def test_revision_check_is_included(self):
        """Partial adoption leaves dual ownership, which drifts silently."""
        commands = rollback_commands("helm_release.loki", "loki", "monitoring")
        assert any("helm history" in c for c in commands)


class TestLiveMatchesRendered:
    """The check added after the first real handoff churned anyway.

    Every other check passed, the preflight said SAFE TO PROCEED, and adoption
    still rolled a canary — because the live Rollout had silently lost its
    container `ports` and `resources.requests`, so re-asserting git was a real
    change. Cause: `kubectl patch --type=merge` on a container list is a JSON
    merge patch, which REPLACES arrays wholesale; a patch carrying only
    name+image drops every other field of that container.

    Non-blocking on purpose: adoption re-asserts the manifest either way. The
    damage is that unexpected churn reads as "the handoff broke it".
    """

    def test_the_exact_drift_that_caused_the_churn(self):
        rendered = {
            "kind": "Rollout",
            "spec": {"template": {"spec": {"containers": [
                {"name": "demo", "image": "demo:blue",
                 "ports": [{"name": "http", "containerPort": 8080}],
                 "resources": {"requests": {"cpu": "5m", "memory": "16Mi"}}},
            ]}}},
        }
        # What `--type=merge` left behind.
        live = {
            "kind": "Rollout",
            "spec": {"template": {"spec": {"containers": [
                {"name": "demo", "image": "demo:blue", "resources": {}},
            ]}}},
        }
        differences = diff_live_against_rendered(rendered, live)
        assert any("ports" in d for d in differences), differences
        assert any("resources" in d for d in differences), differences

    def test_identical_objects_report_no_drift(self):
        obj = {"kind": "Service", "spec": {"ports": [{"port": 80}]}}
        assert diff_live_against_rendered(obj, dict(obj)) == []

    def test_server_side_defaults_are_not_drift(self):
        """Live carries clusterIP/status the manifest never declared — one-directional."""
        rendered = {"kind": "Service", "spec": {"ports": [{"port": 80}]}}
        live = {
            "kind": "Service",
            "spec": {"ports": [{"port": 80}], "clusterIP": "10.96.0.1", "type": "ClusterIP"},
            "status": {"loadBalancer": {}},
        }
        assert diff_live_against_rendered(rendered, live) == []

    def test_adoption_annotations_are_not_drift(self):
        """The engine stamps its own tracking id — flagging it would cry wolf every handoff."""
        rendered = {"metadata": {"annotations": {
            "argocd.argoproj.io/tracking-id": "x", "keep": "me"}}}
        live = {"metadata": {"annotations": {"keep": "me"}}}
        assert diff_live_against_rendered(rendered, live) == []

    def test_list_length_change_is_reported(self):
        rendered = {"spec": {"containers": [{"name": "a"}, {"name": "sidecar"}]}}
        live = {"spec": {"containers": [{"name": "a"}]}}
        assert any("length" in d for d in diff_live_against_rendered(rendered, live))

    def test_finding_is_a_warning_not_a_blocker(self):
        finding = check_live_matches_rendered(["Rollout/demo spec.x (missing)"])
        assert finding.passed is False
        assert finding.blocking is False, "drift means 'expect churn', not 'stop'"
        assert "WILL churn" in finding.detail

    def test_clean_finding_says_it_should_be_a_no_op(self):
        finding = check_live_matches_rendered([])
        assert finding.passed is True
        assert "no-op" in finding.detail

    def test_long_drift_lists_are_truncated_with_a_count(self):
        """A wall of field paths is the same as no report."""
        finding = check_live_matches_rendered([f"f{i}" for i in range(20)])
        assert "+14 more" in finding.detail

    def test_drift_alone_does_not_block_the_verdict(self):
        result = preflight(
            release="demo", namespace="ns", revision=3,
            resources=[_owned("Rollout", "demo", release="demo", namespace="ns")],
            commits_ahead=0, drift=["Rollout/demo spec.x (missing)"],
        )
        assert result.safe is True, "drift is a warning; the handoff is still safe to run"
        assert any(f.check == "live-matches-rendered" and not f.passed for f in result.findings)
