"""
Guards for the add-on render path — the seam between the registry and a cluster.

The rule these encode: what this script prints must be applicable as printed. The
failures it exists to prevent all share a shape — the registry describes an add-on,
something needed to install it is missing, and the gap only surfaces two systems
away (an ArgoCD ComparisonError, a chart that will not template, a second
controller quietly fighting the first). None of those name the registry, so each
one cost a live run to find.

Exit codes are part of the contract, not diagnostics: the documented use is
`render_addons.py acme -e dev | kubectl apply -f -`, and an empty stream means
"nothing to do" and "everything here is shared" identically. Only the code
separates them.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
import yaml

from src.agents.platform.registry import Registry


REPO = Path(__file__).resolve().parents[1]


def _script():
    path = REPO / "scripts" / "render_addons.py"
    spec = importlib.util.spec_from_file_location("render_addons", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


render_addons = _script()


def _run(capsys, *argv) -> tuple[int, str, str]:
    import sys

    argv = ["render_addons.py", *argv]
    old, sys.argv = sys.argv, argv
    try:
        code = render_addons.main()
    finally:
        sys.argv = old
    captured = capsys.readouterr()
    return code, captured.out, captured.err


class TestRendersWhatCanBeInstalled:
    def test_namespace_scoped_addons_render_with_repo_chart_and_values(self, capsys):
        """All three inputs, from the registry alone.

        Historically each arrived in a different phase and the missing one was
        supplied by hand at a prompt, which meant what got installed was whatever
        the operator typed that night rather than what the registry declared.
        """
        code, out, _ = _run(capsys, "acme", "-e", "dev")
        assert code == 0

        docs = {d["metadata"]["name"]: d for d in yaml.safe_load_all(out) if d}
        assert set(docs) == {"acme-dev-logging", "acme-dev-tracing"}

        source = docs["acme-dev-logging"]["spec"]["source"]
        assert source["repoURL"] == "https://grafana.github.io/helm-charts"
        assert source["chart"] == "loki"
        assert source["targetRevision"] == "7.1.0"
        assert source["helm"]["valuesObject"]["deploymentMode"] == "SingleBinary"

    def test_destination_is_the_tenant_namespace(self, capsys):
        _, out, _ = _run(capsys, "acme", "-e", "dev")
        docs = {d["metadata"]["name"]: d for d in yaml.safe_load_all(out) if d}
        assert docs["acme-dev-tracing"]["spec"]["destination"]["namespace"] == "acme-dev-tracing"

    def test_check_mode_prints_no_manifests(self, capsys):
        code, out, err = _run(capsys, "acme", "-e", "dev", "--check")
        assert code == 0
        assert out.strip() == ""
        assert "2 manifest(s)" in err


class TestSharedCapabilitiesAreNamedNotDropped:
    """A cluster singleton must not be rendered per tenant — and must not vanish.

    Refusing to render it is the delivery contract's job and is already guarded.
    What is guarded here is the reporting: an omission with no explanation reads as
    "this tenant has no observability", which is the opposite of true.
    """

    def test_cluster_scoped_capabilities_are_not_rendered(self, capsys):
        _, out, _ = _run(capsys, "acme", "-e", "dev")
        names = {d["metadata"]["name"] for d in yaml.safe_load_all(out) if d}
        assert "acme-dev-observability" not in names
        assert "acme-dev-progressive" not in names

    def test_they_are_reported_by_name(self, capsys):
        _, _, err = _run(capsys, "acme", "-e", "dev")
        assert "SHARED, NOT PER-TENANT" in err
        assert "observability" in err and "progressive" in err

    def test_env_of_only_shared_capabilities_exits_nonzero(self, capsys):
        """globex/dev declares one capability and it is cluster-scoped.

        The stream is empty either way; a zero exit here would tell a pipeline
        that a tenant with nothing installed was fully provisioned.
        """
        code, out, err = _run(capsys, "globex", "-e", "dev")
        assert code == 1
        assert out.strip() == ""
        assert "every declared capability here is a shared cluster install" in err


class TestRefusesToGuess:
    @pytest.mark.parametrize(
        "argv", [("nosuchtenant", "-e", "dev"), ("acme", "-e", "nosuchenv")]
    )
    def test_unknown_tenant_or_env_is_exit_two(self, capsys, argv):
        code, out, _ = _run(capsys, *argv)
        assert code == 2
        assert out.strip() == ""

    def test_unknown_capability_filter_is_exit_two(self, capsys):
        """Silently rendering nothing would look like "that add-on is fine"."""
        code, _, err = _run(capsys, "acme", "-e", "dev", "--capability", "cache")
        assert code == 2
        assert "declares no capability cache" in err

    def test_capability_filter_narrows_output(self, capsys):
        code, out, _ = _run(capsys, "acme", "-e", "dev", "--capability", "logging")
        assert code == 0
        docs = [d for d in yaml.safe_load_all(out) if d]
        assert [d["metadata"]["name"] for d in docs] == ["acme-dev-logging"]


class TestInstallabilityIsCheckedBeforePrinting:
    def test_missing_repo_is_reported_and_not_printed(self, capsys, monkeypatch):
        """A chart with no repository renders an Application that can never sync.

        ArgoCD reports it as a ComparisonError on the Application — far from the
        catalog entry that caused it, and after it is already applied.
        """
        original = Registry.repo_for
        monkeypatch.setattr(
            Registry,
            "repo_for",
            lambda self, cap: "" if cap == "logging" else original(self, cap),
        )
        code, out, err = _run(capsys, "acme", "-e", "dev")
        assert code == 1
        assert "NOT INSTALLABLE: logging" in err
        names = {d["metadata"]["name"] for d in yaml.safe_load_all(out) if d}
        assert names == {"acme-dev-tracing"}

    def test_missing_values_is_reported(self, capsys, monkeypatch):
        original = Registry.values_for
        monkeypatch.setattr(
            Registry,
            "values_for",
            lambda self, cap, **kw: {} if cap == "tracing" else original(self, cap, **kw),
        )
        code, _, err = _run(capsys, "acme", "-e", "dev")
        assert code == 1
        assert "NOT INSTALLABLE: tracing" in err
