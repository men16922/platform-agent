"""Guards for the agent's two mutating platform tools.

These tools are reachable from one sentence typed into a dashboard chat, so the
tests are weighted toward what they must REFUSE. A happy path that applies
manifests is the easy half; the half that matters is that a wrong context, an
unknown tenant, an absent Capsule CRD or a cluster-singleton capability cannot
come back looking like success.

Nothing here touches a cluster: `cluster_io` is the seam, and it is faked.
"""

from __future__ import annotations

import pytest

from src.agents.ai import tenancy_tools as tt


@pytest.fixture()
def on_cluster(monkeypatch):
    """Put the tools on the cluster the registry declares for acme/dev."""
    monkeypatch.setattr(tt, "current_context", lambda: "kind-platform-agent")
    monkeypatch.setattr(tt, "capsule_crd_installed", lambda: True)
    applied: list[list[dict]] = []

    def fake_apply(objects, **kwargs):
        applied.append(objects)
        return {"ok": True, "applied": len(objects), "output": "", "warnings": [], "error": None}

    monkeypatch.setattr(tt, "apply_manifests", fake_apply)
    return applied


class TestContextGuard:
    """The blast-radius invariant, mechanised: write only where the registry says."""

    @pytest.mark.parametrize(
        "tool,kwargs",
        [
            (tt.setup_tenancy, {}),
            (tt.install_tenant_addons, {}),
        ],
    )
    def test_wrong_context_refuses_and_applies_nothing(self, monkeypatch, tool, kwargs):
        monkeypatch.setattr(tt, "current_context", lambda: "docker-desktop")
        called = []
        monkeypatch.setattr(tt, "apply_manifests", lambda o, **k: called.append(o))

        result = tool("acme", "dev", **kwargs)

        assert result["success"] is False
        assert "docker-desktop" in result["error"] and "kind-platform-agent" in result["error"]
        assert called == [], "refusal must happen before anything is applied"

    def test_no_cluster_at_all_is_not_a_context_mismatch(self, monkeypatch):
        """Distinct message: 'provision one first' is actionable, 'wrong context' is not."""
        monkeypatch.setattr(tt, "current_context", lambda: None)
        result = tt.setup_tenancy("acme", "dev")
        assert result["success"] is False
        assert "no reachable cluster" in result["error"]

    def test_unknown_tenant_names_the_known_ones(self, monkeypatch):
        monkeypatch.setattr(tt, "current_context", lambda: "kind-platform-agent")
        result = tt.setup_tenancy("nope", "dev")
        assert result["success"] is False
        assert "no tenant 'nope'" in result["error"]
        assert "acme" in result["error"]

    def test_unknown_env_names_the_known_ones(self, monkeypatch):
        monkeypatch.setattr(tt, "current_context", lambda: "kind-platform-agent")
        result = tt.setup_tenancy("acme", "staging")
        assert result["success"] is False
        assert "staging" in result["error"] and "dev" in result["error"]


class TestSetupTenancy:
    def test_applies_the_boundary_and_reports_the_axes(self, on_cluster):
        result = tt.setup_tenancy("acme", "dev")

        assert result["success"] is True
        assert result["namespaces"], "a soft-tier tenant must get namespaces"
        assert all(ns.startswith("acme-dev-") for ns in result["namespaces"])
        assert result["tier"] == "soft"
        assert result["credential_scope"] == "tenant"
        assert result["enforced"] == {"quota": True, "network": True}
        assert result["enforcement_gaps"] == []
        assert on_cluster and on_cluster[0], "manifests were handed to kubectl"

    def test_absent_capsule_crd_is_reported_in_the_note_not_just_a_flag(self, monkeypatch, on_cluster):
        """The failure this exists for: apply succeeds, quota silently does not.

        A boolean nobody reads is how "unbounded on a shared cluster" gets
        summarised as "tenant created". The gap has to be in the prose the model
        repeats, not only in a field it may ignore.
        """
        monkeypatch.setattr(tt, "capsule_crd_installed", lambda: False)

        result = tt.setup_tenancy("acme", "dev")

        assert result["enforced"]["quota"] is False
        assert any("NOT ENFORCED" in gap for gap in result["enforcement_gaps"])
        assert "QUOTA IS NOT ENFORCED" in result["note"]
        assert "unbounded" in result["note"]

    def test_unverifiable_capsule_is_not_reported_as_enforced(self, monkeypatch, on_cluster):
        monkeypatch.setattr(tt, "capsule_crd_installed", lambda: None)

        result = tt.setup_tenancy("acme", "dev")

        assert result["enforced"]["quota"] is False
        assert any("unconfirmed" in gap for gap in result["enforcement_gaps"])

    def test_unproven_substrate_reports_no_data_plane_isolation(self, monkeypatch, on_cluster):
        monkeypatch.setattr(tt, "network_policies_apply_to", lambda tenant, env: False)

        result = tt.setup_tenancy("acme", "dev")

        assert result["enforced"]["network"] is False
        assert "NO DATA-PLANE ISOLATION" in result["note"]


class TestInstallTenantAddons:
    def test_installs_the_namespace_scoped_addons(self, on_cluster):
        result = tt.install_tenant_addons("acme", "dev")

        assert result["success"] is True
        assert "logging" in result["installed"] and "tracing" in result["installed"]
        assert result["delivery"] == "argocd"
        assert result["applied"] > 0

    def test_cluster_singletons_are_named_not_dropped(self, on_cluster):
        """A silent omission reads as 'this tenant has no observability'."""
        result = tt.install_tenant_addons("acme", "dev")

        assert result["shared_not_per_tenant"], "shared capabilities must be listed"
        assert set(result["shared_not_per_tenant"]).isdisjoint(result["installed"])
        for capability in result["shared_not_per_tenant"]:
            assert capability in result["note"]

    def test_asking_for_a_cluster_singleton_alone_is_not_silent_success(self, on_cluster):
        """Nothing to apply and 'everything here is shared' must not look identical."""
        result = tt.install_tenant_addons("acme", "dev", capability="observability")

        assert result["success"] is False
        assert result["installed"] == []
        assert "observability" in result["shared_not_per_tenant"]
        assert "cluster-scoped" in result["note"]
        assert on_cluster == [], "nothing should have been applied"

    def test_undeclared_capability_is_an_error_with_the_declared_set(self, on_cluster):
        result = tt.install_tenant_addons("acme", "dev", capability="service-mesh")

        assert result["success"] is False
        assert "service-mesh" in result["error"]
        assert "logging" in result["error"]

    def test_uninstallable_addon_fails_loudly_with_the_reason(self, monkeypatch, on_cluster):
        """A missing repo surfaces three systems away as an ArgoCD ComparisonError."""
        monkeypatch.setattr(
            tt.Registry, "uninstallable_reason",
            lambda self, capability: "no self_hosted_repo in the catalog" if capability == "tracing" else None,
        )

        result = tt.install_tenant_addons("acme", "dev")

        assert result["success"] is False
        assert "tracing" in result["not_installable"]
        assert "tracing" not in result["installed"]
        assert "NOT INSTALLABLE" in result["note"]
        assert "logging" in result["installed"], "one broken add-on must not block the rest"


class TestKubectlWarningsAreNotErrors:
    """Found live, not in review: a working chain reported itself failed.

    Applying a tenant used to emit two Capsule deprecation warnings on stderr.
    Everything upstream reads a non-empty ``error`` as a failed step
    (``model_router._step_failed`` is ``bool(result.get("error"))``), so the whole
    run came back ``ok: False`` with every step successful — the dashboard would
    have recorded a working setup as a failure, and the demo would have filmed it.

    The behaviour under test outlives its example. ``kubectl`` writes warnings to
    stderr from many sources, and any one of them would re-create the bug.
    """

    #: HISTORICAL, and labelled as such rather than quietly refreshed. This is the
    #: exact stderr the live cluster produced when the bug was found; both fields
    #: have since been migrated away (`additionalMetadataList` on 2026-07-28,
    #: `render_limit_ranges` on 2026-08-02) and applying a tenant now writes
    #: **nothing** to stderr — measured, `docs/evidence/capsule-limitranges-direct.log`.
    #: Kept because it is a real observed input and the two-warning case is the one
    #: that broke; the guard against these particular fields returning lives in
    #: `test_tenancy.py`, where it can assert the renderer instead of a string.
    CAPSULE_WARNINGS = (
        "Warning: The field `limitRanges` is deprecated and will be removed in a future release.\n"
        "Warning: The field `additionalMetadata` is deprecated and will be removed in a future release."
    )

    def _apply_with_stderr(self, stderr: str, returncode: int = 0):
        from src.agents.platform import cluster_io

        class FakeProc:
            def __init__(self):
                self.stdout = "namespace/acme-dev-logging configured\n"
                self.stderr = stderr
                self.returncode = returncode

        return cluster_io, FakeProc

    def test_warning_only_stderr_leaves_error_none(self, monkeypatch):
        cluster_io, FakeProc = self._apply_with_stderr(self.CAPSULE_WARNINGS)
        monkeypatch.setattr(cluster_io.subprocess, "run", lambda *a, **k: FakeProc())

        result = cluster_io.apply_manifests([{"kind": "Namespace"}])

        assert result["ok"] is True
        assert result["error"] is None, "a deprecation warning is not a failure"
        assert len(result["warnings"]) == 2, "and it must not be swallowed either"

    def test_real_stderr_still_reports_an_error(self, monkeypatch):
        cluster_io, FakeProc = self._apply_with_stderr(
            "Warning: deprecated field\nerror: unable to recognize \"STDIN\": no matches for kind \"Tenant\"",
            returncode=1,
        )
        monkeypatch.setattr(cluster_io.subprocess, "run", lambda *a, **k: FakeProc())

        result = cluster_io.apply_manifests([{"kind": "Tenant"}])

        assert result["ok"] is False
        assert "no matches for kind" in result["error"]
        assert result["warnings"] == ["Warning: deprecated field"]

    def test_the_tool_does_not_report_a_failed_step_on_warnings(self, monkeypatch):
        """The property that actually broke: end to end, through the tool."""
        from src.agents.ai.model_router import _step_failed

        monkeypatch.setattr(tt, "current_context", lambda: "kind-platform-agent")
        monkeypatch.setattr(tt, "capsule_crd_installed", lambda: True)
        monkeypatch.setattr(
            tt, "apply_manifests",
            lambda objects, **k: {
                "ok": True, "applied": len(objects), "output": "",
                "warnings": self.CAPSULE_WARNINGS.splitlines(), "error": None,
            },
        )

        result = tt.setup_tenancy("acme", "dev")

        assert result["success"] is True
        assert not _step_failed(result), "warnings must not make the run look failed"
        assert result["warnings"], "and they are still reported"


class TestChainIsReachableFromTheAgent:
    """연계 — the tools exist for the agent, not only for a unit test."""

    def test_both_tools_are_registered_for_dispatch(self):
        from src.agents.ai import local_deployer as ld

        names = {t.__name__ for t in ld.ALL_OPS_TOOLS}
        assert {"setup_tenancy", "install_tenant_addons"} <= names

    def test_prompt_states_the_order_and_its_reason(self):
        """The order is a real dependency, so the model has to be told, not hoped at."""
        from src.agents.ai.local_deployer import DEPLOYER_SYSTEM_PROMPT as prompt

        assert "setup_tenancy` -> `install_tenant_addons" in prompt
        assert "provision_cluster" in prompt
        # And why: add-ons are objects inside the tenant's namespaces.
        assert "namespaces" in prompt
        # Applied-is-not-enforced has to survive into the summary the user reads.
        assert "enforcement_gaps" in prompt
