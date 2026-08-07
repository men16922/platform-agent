"""
Guards for Phase 1a — scoped execution credentials.

The invariant under test: **the credential is the boundary, the label is a
convenience.** Concretely that means three things must be impossible:

  1. Running a live on-prem action with no scoped credential (the old ambient
     kubeconfig path — blast radius = whatever the current context could reach).
  2. Getting a credential for a tenant just by asking for it (the broker must
     go by the attested record, not the caller's string).
  3. Replaying one approval to mint a second credential.
"""

from __future__ import annotations

import pytest
import yaml

from src.agents.platform.registry import load_registry
from src.agents.platform.scope import (
    AttestedApproval,
    IncidentScope,
    ScopeError,
    TokenBroker,
    sign_approval,
)

KEY = "test-signing-key"

CATALOG = {
    "capabilities": {
        "observability": {"wave": 1, "backends": {"self_hosted": "kube-prometheus-stack"}},
        "logging": {"wave": 1, "backends": {"self_hosted": "loki"}},
    }
}


def _tenant_doc(prefix: str, isolation: str = "soft") -> dict:
    return {
        "isolation": isolation,
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
    """Two tenants sharing one cluster — a single-tenant fixture cannot falsify isolation."""
    registry_root = tmp_path / "platform"
    (registry_root / "tenants").mkdir(parents=True)
    (registry_root / "catalog.yaml").write_text(yaml.safe_dump(CATALOG), encoding="utf-8")
    for name in ("acme", "globex"):
        (registry_root / "tenants" / f"{name}.yaml").write_text(
            yaml.safe_dump(_tenant_doc(name)), encoding="utf-8"
        )

    credential_dir = tmp_path / "creds"
    credential_dir.mkdir()
    for name in ("acme", "globex"):
        (credential_dir / f"{name}.kubeconfig").write_text(f"# {name} kubeconfig", encoding="utf-8")

    return TokenBroker(
        registry=load_registry(registry_root),
        credential_dir=credential_dir,
        signing_key=KEY,
    )


class TestProvenanceBinding:
    """The broker must go by the attested record, never by what the caller claims."""

    def test_valid_record_mints_its_own_tenant(self, broker):
        record = sign_approval("APR-1", "acme", "dev", key=KEY)
        scope = broker.mint(record)
        assert scope.tenant == "acme"
        assert scope.kubeconfig_path.endswith("acme.kubeconfig")
        assert scope.approval_id == "APR-1"

    def test_forged_tenant_is_refused(self, broker):
        """Editing the tenant on a signed record must invalidate it."""
        genuine = sign_approval("APR-1", "acme", "dev", key=KEY)
        forged = AttestedApproval(
            approval_id=genuine.approval_id,
            tenant="globex",              # <- swapped
            env=genuine.env,
            signature=genuine.signature,  # <- kept
        )
        with pytest.raises(ScopeError, match="attestation"):
            broker.mint(forged)

    def test_unsigned_record_is_refused(self, broker):
        with pytest.raises(ScopeError, match="attestation"):
            broker.mint(AttestedApproval("APR-1", "acme", "dev", signature=""))

    def test_record_signed_with_another_key_is_refused(self, broker):
        with pytest.raises(ScopeError, match="attestation"):
            broker.mint(sign_approval("APR-1", "acme", "dev", key="other-key"))

    def test_caller_tenant_mismatch_is_refused_not_silently_honoured(self, broker):
        """
        A caller asking for tenant-B while holding tenant-A's approval must fail,
        not quietly receive tenant-A (which would hide a routing bug).
        """
        record = sign_approval("APR-1", "acme", "dev", key=KEY)
        with pytest.raises(ScopeError, match="refusing"):
            broker.mint(record, requested_tenant="globex")

    def test_matching_caller_tenant_is_fine(self, broker):
        record = sign_approval("APR-1", "acme", "dev", key=KEY)
        assert broker.mint(record, requested_tenant="acme").tenant == "acme"

    def test_nonce_replay_is_refused_within_one_broker_instance(self, broker):
        """Named for what it proves, after the old name turned out to be a claim.

        This was `test_nonce_replay_is_refused`, and it passed while production
        minted three scopes from one replayed record: `_spent` is instance state
        and `resolve_incident_scope` builds a broker per call, so the only place
        the guard ever fired was a test holding the instance still. Measured
        2026-08-02 → `tests/test_scope_replay_reachability.py`.
        """
        record = sign_approval("APR-1", "acme", "dev", nonce="n-1", key=KEY)
        assert broker.mint(record).tenant == "acme"
        with pytest.raises(ScopeError, match="replay"):
            broker.mint(record)

    def test_unknown_tenant_or_env_is_refused(self, broker):
        with pytest.raises(KeyError):
            broker.mint(sign_approval("APR-1", "nosuch", "dev", key=KEY))
        with pytest.raises(KeyError):
            broker.mint(sign_approval("APR-1", "acme", "nosuch", key=KEY))

    def test_missing_credential_file_fails_closed(self, broker):
        (broker.credential_dir / "acme.kubeconfig").unlink()
        with pytest.raises(ScopeError, match="fail-closed"):
            broker.mint(sign_approval("APR-1", "acme", "dev", key=KEY))

    def test_signing_without_a_key_is_refused(self, monkeypatch):
        monkeypatch.delenv("PLATFORM_APPROVAL_SIGNING_KEY", raising=False)
        with pytest.raises(ScopeError, match="signing key"):
            sign_approval("APR-1", "acme", "dev")

    def test_broker_from_env_refuses_without_configuration(self, broker, monkeypatch):
        """No credential dir must NOT mean "use whatever is ambient"."""
        monkeypatch.delenv("PLATFORM_CREDENTIAL_DIR", raising=False)
        monkeypatch.setenv("PLATFORM_APPROVAL_SIGNING_KEY", KEY)
        with pytest.raises(ScopeError, match="ambient"):
            TokenBroker.from_env(broker.registry)


class TestCredentialUnitFollowsTier:
    def test_soft_tier_credential_is_per_tenant(self, broker):
        """Under soft, a per-ENV credential would reach co-tenant namespaces."""
        assert broker.credential_path("acme", "dev").name == "acme.kubeconfig"

    def test_stronger_tiers_are_per_env(self, tmp_path):
        registry_root = tmp_path / "platform"
        (registry_root / "tenants").mkdir(parents=True)
        (registry_root / "catalog.yaml").write_text(yaml.safe_dump(CATALOG), encoding="utf-8")
        (registry_root / "tenants" / "acme.yaml").write_text(
            yaml.safe_dump(_tenant_doc("acme", isolation="dedicated")), encoding="utf-8"
        )
        b = TokenBroker(
            registry=load_registry(registry_root),
            credential_dir=tmp_path,
            signing_key=KEY,
        )
        assert b.credential_path("acme", "dev").name == "acme-dev.kubeconfig"


class TestScopeHandle:
    def test_kubectl_is_always_pinned_to_the_credential(self):
        scope = IncidentScope(tenant="acme", env="dev", kubeconfig_path="/creds/acme.kubeconfig")
        assert scope.kubectl_prefix() == ["--kubeconfig", "/creds/acme.kubeconfig"]

    def test_namespace_precheck_is_advisory_only(self, broker):
        scope = broker.mint(sign_approval("APR-1", "acme", "dev", key=KEY))
        assert scope.permits_namespace("acme-dev-observability") is True
        assert scope.permits_namespace("globex-dev-observability") is False
        # No declared namespaces => cannot pre-judge; RBAC remains the decider.
        open_scope = IncidentScope(tenant="acme", env="dev", kubeconfig_path="/x")
        assert open_scope.permits_namespace("anything") is True

    def test_redacted_logging_hides_the_path(self, broker):
        scope = broker.mint(sign_approval("APR-1", "acme", "dev", key=KEY))
        redacted = scope.redacted()
        assert redacted["kubeconfig"] == "acme.kubeconfig"
        assert "/" not in redacted["kubeconfig"]


class TestRunnerRefusesWithoutScope:
    """The ambient-kubeconfig path is gone; a live run without a scope must fail."""

    @staticmethod
    def _log():
        class _L:
            def __init__(self):
                self.events = []

            def info(self, event, **kw):
                self.events.append((event, kw))

            def warning(self, event, **kw):
                self.events.append((event, kw))

            def error(self, event, **kw):
                self.events.append((event, kw))

        return _L()

    def test_live_without_scope_raises(self, monkeypatch):
        from src.agents.operations.runners import onprem_runner

        monkeypatch.setenv("ONPREM_EXECUTOR_LIVE", "true")
        monkeypatch.delenv("TESTING", raising=False)
        log = self._log()
        with pytest.raises(RuntimeError, match="without a scoped credential"):
            onprem_runner.run_onprem_action(
                "ONPREM-RolloutRestartWorkload",
                {"Namespace": ["default"], "WorkloadName": ["api"]},
                log,
                None,
            )
        assert any(e == "onprem_runner.no_scope" for e, _ in log.events)

    def test_log_only_mode_still_works_without_scope(self, monkeypatch):
        """Log-only touches nothing, so it must not need a credential."""
        from src.agents.operations.runners import onprem_runner

        monkeypatch.setenv("ONPREM_EXECUTOR_LIVE", "false")
        log = self._log()
        onprem_runner.run_onprem_action("ONPREM-RolloutRestartWorkload", {}, log, None)
        assert any(e == "onprem_runner.log_only" for e, _ in log.events)

    def test_cross_tenant_namespace_is_refused_before_kubectl(self, monkeypatch, broker):
        """
        Defence in depth: RBAC would also refuse, but skipping here yields an
        attributable log line instead of an opaque Forbidden.
        """
        from src.agents.operations.runners import onprem_runner

        monkeypatch.setenv("ONPREM_EXECUTOR_LIVE", "true")
        monkeypatch.delenv("TESTING", raising=False)
        called = []
        monkeypatch.setattr(
            onprem_runner, "_run_kubectl", lambda *a, **k: called.append(a) or (0, "", "")
        )
        scope = broker.mint(sign_approval("APR-1", "acme", "dev", key=KEY))
        log = self._log()
        with pytest.raises(RuntimeError, match="outside the scope"):
            onprem_runner.run_onprem_action(
                "ONPREM-RolloutRestartWorkload",
                {"Namespace": ["globex-dev-observability"], "WorkloadName": ["api"]},
                log,
                scope,
            )
        assert not called, "kubectl must not run for an out-of-scope namespace"

    def test_in_scope_action_passes_the_credential_to_kubectl(self, monkeypatch, broker):
        from src.agents.operations.runners import onprem_runner

        monkeypatch.setenv("ONPREM_EXECUTOR_LIVE", "true")
        monkeypatch.delenv("TESTING", raising=False)
        seen: dict = {}

        def _fake(args, scope, timeout=60):
            seen["args"] = args
            seen["scope"] = scope
            return 0, "restarted", ""

        monkeypatch.setattr(onprem_runner, "_run_kubectl", _fake)
        scope = broker.mint(sign_approval("APR-1", "acme", "dev", key=KEY))
        onprem_runner.run_onprem_action(
            "ONPREM-RolloutRestartWorkload",
            {"Namespace": ["acme-dev-observability"], "WorkloadName": ["api"]},
            self._log(),
            scope,
        )
        assert seen["scope"].tenant == "acme"
        assert seen["scope"].kubectl_prefix()[0] == "--kubeconfig"


class TestIncidentCarriesTenancy:
    def test_normalized_incident_has_first_class_scope_fields(self):
        from src.agents.models import NormalizedIncident

        incident = NormalizedIncident(
            provider="onprem", service="api", resource_type="kubernetes-workload",
            resource_id="api-1", signal_type="reliability", tenant="acme", env="dev",
        )
        assert (incident.tenant, incident.env) == ("acme", "dev")

    def test_defaults_are_empty_so_legacy_incidents_fail_closed(self):
        from src.agents.models import NormalizedIncident

        incident = NormalizedIncident(
            provider="onprem", service="api", resource_type="kubernetes-workload",
            resource_id="api-1", signal_type="reliability",
        )
        assert incident.tenant == "" and incident.env == ""

    def test_onprem_adapter_lifts_tenant_env_from_alert_labels(self):
        from src.agents.adapters.signals.onprem import OnPremAlertmanagerSignalAdapter

        incident = OnPremAlertmanagerSignalAdapter().normalise({
            "status": "firing",
            "alerts": [{
                "labels": {"alertname": "X", "namespace": "acme-dev-observability",
                           "pod": "api-1", "tenant": "acme", "env": "dev"},
                "annotations": {"summary": "s"},
            }],
        })
        assert incident.tenant == "acme"
        assert incident.env == "dev"

    def test_missing_labels_leave_scope_empty(self):
        from src.agents.adapters.signals.onprem import OnPremAlertmanagerSignalAdapter

        incident = OnPremAlertmanagerSignalAdapter().normalise({
            "status": "firing",
            "alerts": [{"labels": {"alertname": "X", "pod": "api-1"}, "annotations": {}}],
        })
        assert incident.tenant == "" and incident.env == ""
