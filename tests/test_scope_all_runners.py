"""
Guards for Phase 3 — scoped credentials across *every* runner, not just on-prem.

Phase 1a proved the invariant ("the credential is the boundary") on the on-prem
path and left the other two clouds untouched. That is a partial guarantee that
reads like a whole one: a GKE or AKS remediation still executed on whatever the
routing put in ``params``, with no credential handle in the call at all.

What these tests pin down:

  1. Every cluster-touching runner refuses a live action with no scope.
  2. Every one of them refuses a namespace outside the scope *before* it reaches
     the network.
  3. The dispatch seam forwards the scope to **all** provider branches — and the
     last test fails if someone adds a fourth branch without doing so. That is
     the actual regression risk here; the first two would still pass while a new
     runner quietly executed unscoped.

Log-only/mock modes deliberately still work without a scope: they touch nothing,
so requiring a credential there would only teach people to fake one.
"""

from __future__ import annotations

import inspect
import re

import pytest
import yaml

from src.agents.platform.registry import load_registry
from src.agents.platform.scope import ScopeError, TokenBroker, sign_approval

KEY = "test-signing-key"

CATALOG = {
    "capabilities": {
        "observability": {"wave": 1, "backends": {"self_hosted": "kube-prometheus-stack"}},
    }
}


def _tenant_doc(prefix: str) -> dict:
    return {
        "isolation": "soft",
        "naming_prefix": prefix,
        "quota": {"cpu": "4", "memory": "8Gi", "pods": 50},
        "environments": {
            "dev": {
                "cluster": "kind-platform-agent",
                "substrate": "kind",
                "delivery": "argocd",
                "addons": {"observability": "kube-prometheus-stack 87.17.0"},
            }
        },
    }


@pytest.fixture
def broker(tmp_path):
    """Two tenants on one cluster — a single-tenant fixture cannot falsify isolation."""
    registry_root = tmp_path / "platform"
    (registry_root / "tenants").mkdir(parents=True)
    (registry_root / "catalog.yaml").write_text(yaml.safe_dump(CATALOG), encoding="utf-8")
    credential_dir = tmp_path / "creds"
    credential_dir.mkdir()
    for name in ("acme", "globex"):
        (registry_root / "tenants" / f"{name}.yaml").write_text(
            yaml.safe_dump(_tenant_doc(name)), encoding="utf-8"
        )
        (credential_dir / f"{name}.kubeconfig").write_text(f"# {name}", encoding="utf-8")

    return TokenBroker(
        registry=load_registry(registry_root),
        credential_dir=credential_dir,
        signing_key=KEY,
    )


class _Log:
    def __init__(self):
        self.events = []

    def info(self, event, **kw):
        self.events.append((event, kw))

    def warning(self, event, **kw):
        self.events.append((event, kw))

    def error(self, event, **kw):
        self.events.append((event, kw))


@pytest.fixture
def live(monkeypatch):
    """Take every runner out of mock mode — otherwise nothing reaches the gate."""
    monkeypatch.delenv("TESTING", raising=False)
    monkeypatch.setenv("GCP_MOCK", "false")
    monkeypatch.setenv("AZURE_MOCK", "false")
    monkeypatch.setenv("ONPREM_EXECUTOR_LIVE", "true")


# Each entry: (label, callable, in-scope namespace, an action name it accepts)
def _runners():
    from src.agents.operations.runners.azure_runner import run_azure_action
    from src.agents.operations.runners.gcp_runner import run_gcp_action
    from src.agents.operations.runners.onprem_runner import run_onprem_action

    return [
        ("gcp", run_gcp_action, "GCP-RolloutRestartGKEWorkload"),
        ("azure", run_azure_action, "AZURE-RolloutRestartAKSWorkload"),
        ("onprem", run_onprem_action, "ONPREM-RolloutRestartWorkload"),
    ]


class TestEveryRunnerFailsClosed:
    @pytest.mark.parametrize("label,run,action", _runners())
    def test_live_without_scope_is_refused(self, label, run, action, live):
        log = _Log()
        with pytest.raises(ScopeError, match="without a scoped credential"):
            run(action, {"Namespace": ["acme-dev-observability"], "WorkloadName": ["api"]}, log, None)
        assert any(e == f"{label}_runner.no_scope" for e, _ in log.events)

    @pytest.mark.parametrize("label,run,action", _runners())
    def test_cross_tenant_namespace_is_refused(self, label, run, action, live, broker):
        """
        The refusal must land before any network call. If it did not, the proof
        would be "the API server said no", which is a claim about someone else's
        configuration rather than about this code.
        """
        scope = broker.mint(sign_approval("APR-1", "acme", "dev", key=KEY))
        log = _Log()
        with pytest.raises(ScopeError, match="outside the scope"):
            run(
                action,
                {"Namespace": ["globex-dev-observability"], "WorkloadName": ["api"]},
                log,
                scope,
            )
        assert any(e == f"{label}_runner.out_of_scope" for e, _ in log.events)

    @pytest.mark.parametrize("label,run,action", _runners())
    def test_mock_mode_does_not_require_a_scope(self, label, run, action, monkeypatch):
        """Mock/log-only touches nothing — demanding a credential there teaches fakery."""
        monkeypatch.setenv("TESTING", "True")
        monkeypatch.setenv("ONPREM_EXECUTOR_LIVE", "false")
        log = _Log()
        run(action, {"Namespace": ["acme-dev-observability"]}, log, None)
        assert log.events, "mock mode should still record that it ran"


class TestDispatchSeamForwardsScope:
    """
    The regression that actually bites: a runner is correct, but the seam never
    hands it the scope. Phase 1a shipped exactly that state for gcp and azure.
    """

    def _seam(self):
        from src.agents.operations.aws import executor

        return executor

    @pytest.mark.parametrize("provider,module_path,func_name", [
        ("gcp", "src.agents.operations.runners.gcp_runner", "run_gcp_action"),
        ("azure", "src.agents.operations.runners.azure_runner", "run_azure_action"),
        ("onprem", "src.agents.operations.runners.onprem_runner", "run_onprem_action"),
    ])
    def test_scope_reaches_the_runner(self, provider, module_path, func_name, monkeypatch):
        import importlib

        module = importlib.import_module(module_path)
        seen = {}
        monkeypatch.setattr(
            module, func_name, lambda *a, **k: seen.update(args=a, kwargs=k)
        )

        sentinel = object()
        self._seam()._run_external_action(provider, "ACT", {"Namespace": ["ns"]}, _Log(), sentinel)

        forwarded = list(seen.get("args", ())) + list(seen.get("kwargs", {}).values())
        assert sentinel in forwarded, (
            f"{provider} branch dropped the incident scope — the runner would "
            "execute on routing correctness alone"
        )

    def test_every_provider_branch_is_covered_by_the_test_above(self):
        """
        Structural guard: enumerate the seam's provider branches from its source
        and fail if one is not exercised. Without this, adding a fourth cloud
        silently reintroduces the unscoped path and every other test stays green.
        """
        source = inspect.getsource(self._seam()._run_external_action)
        branches = set(re.findall(r'provider\s*==\s*"([a-z]+)"', source))
        covered = {"gcp", "azure", "onprem"}

        # Equality, not subset. A subset assertion also passes when the regex
        # finds *nothing* — which is what would happen if the seam were rewritten
        # as a dict dispatch. Then this guard would go quiet at the exact moment
        # its subject changed shape, which is the failure mode it exists to
        # prevent. If you do refactor the seam, update this to read the new form.
        assert branches == covered, (
            f"seam branches {sorted(branches)} != forwarding-tested {sorted(covered)}. "
            "Either a provider was added without a scope-forwarding test, or the "
            "dispatch shape changed and this guard can no longer see it."
        )
