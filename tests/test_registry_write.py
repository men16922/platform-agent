"""
Guards for Phase 5's write half — attaching an add-on by PR.

The design and every tenant file's own header say the same thing: this flow may
only ever touch ``platform/tenants/<tenant>.yaml``, one file, the tenant's own.
That sentence has been in the repo since Phase 0 with nothing able to falsify it.
These are the falsifiers.

The invariants, in the order they matter:

  1. **One file, and it is the right one.** A tenant name is a filename, so a name
     that is not a plain slug must be refused *before* it becomes a path.
  2. **One key.** The edit is textual (to keep the comments, which are most of the
     value in these files) and therefore untrusted: the result is re-parsed and
     compared as data, and any change beyond the single add-on key is refused.
  3. **Attaching is not upgrading.** Silently turning "attach" into "bump the
     version" would get a PR approved for something it does not say.
  4. **The registry is the authority**, not the caller: unknown tenant, unknown
     env, uninstallable capability, or no backend for the substrate all refuse.
"""

from __future__ import annotations

import shutil

import pytest
import yaml

from src.agents.platform.registry_write import (
    _insert_addon as _INSERT_ADDON,
)
from src.agents.platform.registry_write import (
    RegistryWriteError,
    plan_addon_attachment,
    tenant_path,
)

REPO_TENANTS = "platform/tenants"


@pytest.fixture
def registry_root(tmp_path):
    """A real copy of the shipped registry — comments and all.

    A hand-written fixture would be a shape the real files never take, and the
    whole point of the textual edit is that it survives the real files.
    """
    root = tmp_path / "platform"
    shutil.copytree("platform", root)
    return root


class TestTheBlastRadiusIsOneFile:
    def test_a_traversing_tenant_name_never_becomes_a_path(self, registry_root):
        for name in ("../globex", "/etc/passwd", "acme/../globex", "..", ""):
            with pytest.raises(RegistryWriteError, match="plain registry name"):
                tenant_path(name, root=registry_root)

    def test_an_unknown_tenant_is_refused(self, registry_root):
        with pytest.raises(RegistryWriteError, match="no registry entry"):
            tenant_path("nosuchtenant", root=registry_root)

    def test_the_plan_names_exactly_one_path_and_it_is_the_tenants_own(self, registry_root):
        plan = plan_addon_attachment("acme", "prod", "logging", "7.1.0", root=registry_root)
        assert plan.path == (registry_root / "tenants" / "acme.yaml").resolve()

    def test_planning_writes_nothing(self, registry_root):
        before = (registry_root / "tenants" / "acme.yaml").read_text(encoding="utf-8")
        plan_addon_attachment("acme", "prod", "logging", "7.1.0", root=registry_root)
        assert (registry_root / "tenants" / "acme.yaml").read_text(encoding="utf-8") == before

    def test_no_other_tenant_file_appears_in_the_plan(self, registry_root):
        plan = plan_addon_attachment("acme", "prod", "logging", "7.1.0", root=registry_root)
        assert "globex" not in plan.diff()


class TestExactlyOneKeyChanges:
    def test_only_the_new_capability_is_added(self, registry_root):
        plan = plan_addon_attachment("acme", "prod", "logging", "7.1.0", root=registry_root)
        before = yaml.safe_load(plan.original)
        after = yaml.safe_load(plan.updated)

        assert after["environments"]["prod"]["addons"]["logging"] == "loki 7.1.0"
        del after["environments"]["prod"]["addons"]["logging"]
        assert after == before

    def test_the_sibling_environment_is_untouched(self, registry_root):
        """dev and prod deliberately run different add-on sets and versions."""
        plan = plan_addon_attachment("acme", "prod", "logging", "7.1.0", root=registry_root)
        before = yaml.safe_load(plan.original)["environments"]["dev"]
        after = yaml.safe_load(plan.updated)["environments"]["dev"]
        assert after == before

    def test_the_comments_survive(self, registry_root):
        """
        These files are mostly comments and the comments are the reasoning. A YAML
        round-trip would delete all of it while still producing a valid file — a
        PR that looks like a one-line change and is not.
        """
        plan = plan_addon_attachment("acme", "prod", "logging", "7.1.0", root=registry_root)
        original_comments = [ln for ln in plan.original.splitlines() if ln.strip().startswith("#")]
        updated_comments = [ln for ln in plan.updated.splitlines() if ln.strip().startswith("#")]
        assert original_comments == updated_comments
        assert len(original_comments) > 5, "fixture lost its comments; the guard proves nothing"

    def test_the_diff_is_a_single_added_line(self, registry_root):
        plan = plan_addon_attachment("acme", "prod", "logging", "7.1.0", root=registry_root)
        added = [ln for ln in plan.diff().splitlines() if ln.startswith("+") and not ln.startswith("+++")]
        removed = [ln for ln in plan.diff().splitlines() if ln.startswith("-") and not ln.startswith("---")]
        assert len(added) == 1 and not removed
        assert added[0].lstrip("+").strip() == "logging: loki 7.1.0"

    def test_the_result_still_loads_as_a_registry(self, registry_root):
        """The edit has to survive the real loader, not just yaml.safe_load."""
        from src.agents.platform.registry import load_registry

        plan = plan_addon_attachment("acme", "prod", "logging", "7.1.0", root=registry_root)
        plan.path.write_text(plan.updated, encoding="utf-8")
        env = load_registry(registry_root).environment("acme", "prod")
        # The loader splits "<chart> <version>" — it returns the version alone,
        # which is why the planner writes the pair rather than the version only.
        assert env.addon_version("logging") == "7.1.0"


class TestTheTextualEditIsNotTrusted:
    """
    Added after the falsification pass. Removing `_assert_only_change`'s equality
    check left every test above green: they all exercise the *happy* path, where
    the insertion happens to be correct, so the safety net was never load-bearing
    in any of them. A guard that only holds when nothing is wrong is not a guard —
    these make the edit go wrong on purpose.
    """

    def _plan_with_broken_insert(self, monkeypatch, registry_root, broken):
        from src.agents.platform import registry_write

        monkeypatch.setattr(registry_write, "_insert_addon", broken)
        return registry_write.plan_addon_attachment(
            "acme", "prod", "logging", "7.1.0", root=registry_root
        )

    def test_an_edit_that_lands_in_the_wrong_environment_is_refused(
        self, monkeypatch, registry_root
    ):
        """The failure mode a naive indentation walker actually has."""
        def wrong_block(text, env, capability, value):
            return text.replace(
                "    addons:\n      observability: kube-prometheus-stack 87.17.0\n      logging",
                f"    addons:\n      {capability}: {value}\n      observability: "
                "kube-prometheus-stack 87.17.0\n      logging",
                1,
            )

        with pytest.raises(RegistryWriteError, match="did not land"):
            self._plan_with_broken_insert(monkeypatch, registry_root, wrong_block)

    def test_an_edit_that_also_changes_something_else_is_refused(
        self, monkeypatch, registry_root
    ):
        """A correct insertion plus one stray change still fails the comparison."""
        # Captured before the patch: importing it inside the replacement would
        # resolve to the patched name and recurse forever.
        real_insert = _INSERT_ADDON

        def also_bumps_quota(text, env, capability, value):
            return real_insert(text, env, capability, value).replace(
                'cpu: "16"', 'cpu: "64"', 1
            )

        with pytest.raises(RegistryWriteError, match="more than the one add-on key"):
            self._plan_with_broken_insert(monkeypatch, registry_root, also_bumps_quota)

    def test_an_edit_that_corrupts_the_file_is_refused(self, monkeypatch, registry_root):
        with pytest.raises(Exception):
            self._plan_with_broken_insert(
                monkeypatch, registry_root, lambda t, e, c, v: t + "\n  : : broken\n"
            )


class TestAttachingIsNotUpgrading:
    def test_an_already_attached_capability_is_refused(self, registry_root):
        """acme/dev already declares logging. Bumping it is a different review."""
        with pytest.raises(RegistryWriteError, match="not upgrading"):
            plan_addon_attachment("acme", "dev", "logging", "9.9.9", root=registry_root)


class TestTheRegistryIsTheAuthority:
    def test_an_unknown_environment_is_refused(self, registry_root):
        with pytest.raises(Exception):
            plan_addon_attachment("acme", "staging", "logging", "7.1.0", root=registry_root)

    def test_a_capability_outside_the_catalog_is_refused(self, registry_root):
        with pytest.raises(Exception):
            plan_addon_attachment("acme", "prod", "not-a-capability", "1.0.0", root=registry_root)

    def test_the_backend_comes_from_the_substrate_not_the_caller(self, registry_root):
        """The caller names a capability and a version; the catalog picks the chart."""
        plan = plan_addon_attachment("acme", "prod", "logging", "7.1.0", root=registry_root)
        assert plan.backend == "loki"
        assert plan.backend in plan.updated
