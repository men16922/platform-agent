"""The producer the broker was written for and did not have.

`TokenBroker` was built around a careful idea: the caller presents an *attested*
record and the broker issues a credential for the tenant named **inside** it, so a
compromised caller cannot ask for someone else's tenant. Every test of that idea
minted its own record with `sign_approval`. Nothing in production ever did
(`docs/evidence/deploy-path-authorization.log`), so the idea was correct and inert.

`attest_decision` is the missing half. It is called at the two points where an
action becomes *authorized* — the Guardian policy deciding AUTO, and a human
resolving a parked approval — and it is what turns "the gate refuses everything"
into "the gate refuses what it should".

The tests below are grouped by the property each one protects:

  * it attaches a record the broker will actually accept (round-trip, not shape)
  * it changes NOTHING when unconfigured, so the current default is byte-identical
  * it refuses to attest an incident that names no tenant, rather than inventing one
  * both gates call it — derived, because the second gate is always the one missed

Deliberately NOT claimed anywhere: that this defends against code execution in this
process. The signing key lives here; an attacker who is already running here can
sign whatever they like. It binds the tenant to the record, which stops routing
bugs and payload tampering from widening blast radius, and it makes the action
attributable. That is the whole claim.
"""

import ast
import pathlib

import pytest

import yaml

from src.agents.platform.registry import load_registry
from src.agents.platform.scope import (
    AttestedApproval,
    ScopeError,
    TokenBroker,
    attest_decision,
)

REPO = pathlib.Path(__file__).resolve().parents[1]
WEBHOOK = REPO / "src" / "agents" / "ai" / "onprem_webhook_api.py"
KEY = "test-signing-key"


class _Incident(dict):
    """The normalized incident as the in-process pipeline passes it: a plain dict."""


def _decision(tenant="acme", env="dev", metadata=None):
    """The shape the executor reads: decision.analyzer.detector.normalized_incident."""
    incident = _Incident(
        provider="onprem",
        tenant=tenant,
        env=env,
        source_metadata=dict(metadata or {"alertname": "PodCrashLooping"}),
    )
    return {"analyzer": {"detector": {"normalized_incident": incident}}}, incident


CATALOG = {"capabilities": {"observability": {"wave": 1, "backends": {"self_hosted": "kps"}}}}


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
                "addons": {"observability": "kps 87.17.0"},
            }
        },
    }


@pytest.fixture
def broker(tmp_path):
    """Two tenants on one cluster — a single-tenant fixture cannot falsify isolation."""
    root = tmp_path / "platform"
    (root / "tenants").mkdir(parents=True)
    (root / "catalog.yaml").write_text(yaml.safe_dump(CATALOG), encoding="utf-8")
    creds = tmp_path / "creds"
    creds.mkdir()
    for name in ("acme", "globex"):
        (root / "tenants" / f"{name}.yaml").write_text(
            yaml.safe_dump(_tenant_doc(name)), encoding="utf-8"
        )
        (creds / f"{name}.kubeconfig").write_text(f"# {name}", encoding="utf-8")
    return TokenBroker(
        registry=load_registry(root), credential_dir=creds, signing_key=KEY
    )


@pytest.fixture
def signing_key(monkeypatch):
    monkeypatch.setenv("PLATFORM_APPROVAL_SIGNING_KEY", KEY)
    return KEY


class TestItAttachesARecordTheBrokerWillAccept:
    def test_the_attestation_lands_on_the_incident(self, signing_key):
        decision, incident = _decision()
        assert attest_decision(decision, approval_id="APR-1") is True

        record = incident["source_metadata"]["attested_approval"]
        assert record["tenant"] == "acme"
        assert record["env"] == "dev"
        assert record["approval_id"] == "APR-1"
        assert record["signature"]

    def test_the_broker_verifies_what_was_attached(self, signing_key, broker):
        """Round-trip, not shape.

        Asserting the dict has a `signature` key would pass on a signature computed
        over the wrong fields — and the fields are the entire point, because they are
        what binds the credential to a tenant.
        """
        decision, incident = _decision()
        attest_decision(decision, approval_id="APR-2")
        attached = incident["source_metadata"]["attested_approval"]

        scope = broker.mint(AttestedApproval(**attached))
        assert scope.tenant == "acme"
        assert scope.approval_id == "APR-2"

    def test_a_tampered_tenant_no_longer_verifies(self, signing_key, broker):
        """The property the whole design exists for."""
        decision, incident = _decision()
        attest_decision(decision, approval_id="APR-3")
        attached = dict(incident["source_metadata"]["attested_approval"])
        attached["tenant"] = "globex"

        with pytest.raises(ScopeError, match="attestation"):
            broker.mint(AttestedApproval(**attached))

    def test_it_does_not_disturb_the_metadata_already_there(self, signing_key):
        """`source_metadata` carries the alert's own provenance; the attestation is
        an addition to it, not a replacement of it."""
        decision, incident = _decision(metadata={"alertname": "X", "labels": {"a": "b"}})
        attest_decision(decision, approval_id="APR-4")
        assert incident["source_metadata"]["alertname"] == "X"
        assert incident["source_metadata"]["labels"] == {"a": "b"}


class TestUnconfiguredBehaviourIsUnchanged:
    """The compatibility claim, asserted rather than asserted-in-prose.

    With no signing key the whole feature must be a no-op: no attestation, no scope,
    and the gate refuses exactly as it did before. A hard failure here would make an
    unconfigured deployment break at the moment it tried to remediate, which is worse
    than the fail-closed refusal it already gets.
    """

    def test_no_key_means_no_attestation_and_no_mutation(self, monkeypatch):
        monkeypatch.delenv("PLATFORM_APPROVAL_SIGNING_KEY", raising=False)
        decision, incident = _decision()
        before = dict(incident["source_metadata"])

        assert attest_decision(decision, approval_id="APR-5") is False
        assert incident["source_metadata"] == before
        assert "attested_approval" not in incident["source_metadata"]

    def test_the_gate_still_refuses_afterwards(self, monkeypatch):
        from src.agents.platform.scope import guard_scoped_action

        monkeypatch.delenv("PLATFORM_APPROVAL_SIGNING_KEY", raising=False)
        decision, _ = _decision()
        attest_decision(decision, approval_id="APR-6")

        class _Log:
            def info(self, *a, **k): pass
            def warning(self, *a, **k): pass
            def error(self, *a, **k): pass

        with pytest.raises(ScopeError):
            guard_scoped_action(action="restart_workload", namespace="acme-dev-logging",
                                scope=None, log=_Log(), log_prefix="onprem_runner")


class TestItRefusesToInventAttribution:
    """An unattributed incident cannot be authorized for anyone.

    This is the D36/D37 rule at the security boundary: absence is a different fact
    from any particular tenant, and the one place it must never be filled in with a
    plausible default is the one that decides whose cluster gets touched.
    """

    @pytest.mark.parametrize("tenant,env", [("", "dev"), ("acme", ""), ("", "")])
    def test_a_missing_tenant_or_env_is_not_attested(self, signing_key, tenant, env):
        decision, incident = _decision(tenant=tenant, env=env)
        assert attest_decision(decision, approval_id="APR-7") is False
        assert "attested_approval" not in incident["source_metadata"]

    def test_a_decision_with_no_incident_is_not_attested(self, signing_key):
        assert attest_decision({"analyzer": {}}, approval_id="APR-8") is False
        assert attest_decision({}, approval_id="APR-9") is False
        assert attest_decision(None, approval_id="APR-10") is False


class TestBothGatesAttest:
    """Derived over the webhook, because the second gate is always the missed one.

    That is not a general worry — it is this repo's recorded history: the scope
    reached only the on-prem runner until Phase 3, the executor span covered only one
    of two paths, and `cost_metrics` was written by two of three writers. An
    enumerated check here would be written against whichever gate was in mind.
    """

    def _gate_functions(self):
        tree = ast.parse(WEBHOOK.read_text(encoding="utf-8"))
        return {
            node.name: node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef)
        }

    def _calls(self, node):
        return {
            n.func.id for n in ast.walk(node)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
        }

    def test_every_function_that_executes_also_attests(self):
        missing = []
        for name, node in self._gate_functions().items():
            calls = self._calls(node)
            if "execute_incident" in calls and "attest_decision" not in calls:
                missing.append(f"{name}()")
        assert not missing, (
            f"{missing} execute a remediation without attesting it first, so the "
            "executor cannot mint a scoped credential and the gate refuses — a path "
            "that silently cannot act is how this was missed the first time"
        )

    def test_at_least_two_gates_exist(self):
        """Guards the guard: if `execute_incident` were renamed, the check above would
        pass over an empty set and prove nothing."""
        executing = [
            name for name, node in self._gate_functions().items()
            if "execute_incident" in self._calls(node)
        ]
        assert len(executing) >= 2, (
            f"expected the AUTO and approval gates to both execute; found {executing}"
        )


