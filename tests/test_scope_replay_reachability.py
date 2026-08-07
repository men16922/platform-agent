"""What bounds approval reuse, stated at the scope it is actually enforced.

History, because the shape repeats and the previous version of this file is part
of it:

  M13   a field is declared, written, and read by nobody
  D38   a mechanism is correct and no production code can reach it
  D39   a security exception is held open for a caller that does not exist
  D40   a probe exists to promote a substrate and cannot run on a candidate
  D41   a decision is posed with two options when the repo already uses a third
  결정 6 a replay guard whose state cannot outlive the check

``AttestedApproval.nonce`` was documented "One-time-use marker; the broker rejects
a replayed nonce". ``TokenBroker.mint`` did reject one — against ``self._spent``,
an instance attribute — while the only production caller built a fresh broker per
call. Measured through the production entry point on 2026-08-02: the same record
minted three scopes in a row. ``test_nonce_replay_is_refused`` had passed
throughout, because it held ONE broker and called ``mint`` twice; the test did not
merely miss the hole, it supplied the only condition under which the guard worked.

Real one-time-use was rejected as the fix, and not for effort: ``aws/executor.py``
resolves the scope for the same incident on both the runbook path and the action
path, and a retried Step Function does it again, so enforcing it would refuse
legitimate callers. 결정 6 answered with **option C — perishable, not single-use**:
``issued_at`` is covered by the signature and the broker refuses anything older
than its TTL.

That is a strictly weaker promise than one-time-use, and it is written down as one
(``docs/plans/2026-08-02-nonce-replay-scope.md``). What this file pins is the
boundary between the two, so neither drifts back into a claim:

  * inside the TTL, reuse still works — say it, do not imply otherwise;
  * outside it, and with no stamp at all, the broker refuses;
  * and reuse never crosses a tenant, in any of those cases.
"""

from __future__ import annotations

import hmac
import json
import os
import pathlib
import time
from hashlib import sha256
from types import SimpleNamespace

import pytest

from src.agents.platform.registry import load_registry
from src.agents.platform.scope import (
    APPROVAL_TTL_ENV,
    CREDENTIAL_DIR_ENV,
    DEFAULT_APPROVAL_TTL_SECONDS,
    SIGNING_KEY_ENV,
    AttestedApproval,
    ScopeError,
    TokenBroker,
    resolve_incident_scope,
    sign_approval,
)

KEY = "test-signing-key"


def _broker() -> TokenBroker:
    """Broker built directly, so a refusal's *reason* can be asserted.

    `resolve_incident_scope` swallows every ScopeError into None by design (it must
    never take down a path that has no tenant), which is why the production-path
    assertions above can only see "refused". Both are needed: the reason here, the
    reachability there.
    """
    return TokenBroker(
        registry=load_registry(),
        credential_dir=pathlib.Path(os.environ[CREDENTIAL_DIR_ENV]),
        signing_key=KEY,
    )


class _Log:
    """The production path takes a logger; nothing here asserts on it."""

    def info(self, *args, **kwargs) -> None: ...

    def warning(self, *args, **kwargs) -> None: ...


@pytest.fixture
def wired(tmp_path, monkeypatch):
    """Env exactly as `make scope-credentials` leaves it, with a real credential file."""
    creds = tmp_path / "credentials"
    creds.mkdir()
    (creds / "acme.kubeconfig").write_text("", encoding="utf-8")
    monkeypatch.setenv(CREDENTIAL_DIR_ENV, str(creds))
    monkeypatch.setenv(SIGNING_KEY_ENV, KEY)
    monkeypatch.delenv(APPROVAL_TTL_ENV, raising=False)
    return creds


def _incident(record: AttestedApproval, *, drop_issued_at: bool = False) -> SimpleNamespace:
    attested = {
        "approval_id": record.approval_id,
        "tenant": record.tenant,
        "env": record.env,
        "signature": record.signature,
        "nonce": record.nonce,
        "issued_at": record.issued_at,
    }
    if drop_issued_at:
        del attested["issued_at"]
    return SimpleNamespace(
        provider="onprem",
        tenant=record.tenant,
        source_metadata={"attested_approval": attested},
    )


def test_reuse_inside_the_ttl_still_works(wired):
    """The honest limit of option C, asserted rather than left to be discovered.

    `aws/executor.py` depends on this: it resolves the scope for one incident on
    both the runbook path and the action path. A test that demanded refusal here
    would be demanding the behaviour that was deliberately not built.
    """
    record = sign_approval("APR-1", "acme", "dev", nonce="n-1", key=KEY)
    incident = _incident(record)

    minted = [resolve_incident_scope(incident, _Log()) for _ in range(3)]

    assert all(scope is not None for scope in minted), (
        "a fresh attestation was refused inside its TTL — the executor's two "
        "resolutions of one incident would now fail"
    )
    assert {scope.tenant for scope in minted} == {"acme"}


def test_reuse_past_the_ttl_is_refused(wired):
    """The promise that IS kept: a record stops working once it is old enough."""
    stale = int(time.time()) - (DEFAULT_APPROVAL_TTL_SECONDS + 60)
    record = sign_approval("APR-2", "acme", "dev", nonce="n-2", key=KEY, issued_at=stale)

    assert resolve_incident_scope(_incident(record), _Log()) is None, (
        "an expired approval minted a scope — the TTL is the only thing bounding "
        "reuse, so this failing means reuse is unbounded again"
    )


def test_the_stamp_cannot_be_pushed_forward_without_the_key(wired):
    """`issued_at` is inside the signed payload, so extending it invalidates it."""
    record = sign_approval(
        "APR-3", "acme", "dev", nonce="n-3", key=KEY,
        issued_at=int(time.time()) - (DEFAULT_APPROVAL_TTL_SECONDS + 60),
    )
    forged = AttestedApproval(
        approval_id=record.approval_id,
        tenant=record.tenant,
        env=record.env,
        signature=record.signature,
        nonce=record.nonce,
        issued_at=int(time.time()),  # freshened, signature left alone
    )

    assert resolve_incident_scope(_incident(forged), _Log()) is None


def test_a_record_with_no_stamp_is_refused_rather_than_treated_as_ageless(wired):
    """An explicitly unstamped signature is refused by the AGE check.

    Distinguished from the version-skew case below on purpose: the first draft of
    this file asserted only "returns None" and would have passed even though the
    two refusals come from different mechanisms — which is how a branch ends up
    unreachable while its test stays green.
    """
    record = sign_approval("APR-4", "acme", "dev", nonce="n-4", key=KEY, issued_at=0)
    broker = _broker()

    with pytest.raises(ScopeError, match="issued_at=0"):
        broker.mint(record)
    assert resolve_incident_scope(_incident(record), _Log()) is None


def test_a_pre_ttl_signature_is_refused_and_named_as_skew_not_tampering(wired):
    """Rolling deploys hit this, and the message must not send anyone hunting a forgery.

    Measured while building the TTL: `issued_at` is inside the signed payload, so a
    record signed by the old version fails `verify()` before the age check ever
    runs. Left alone it reported "failed attestation" — true, and misleading.
    """
    legacy_payload = json.dumps(
        {"approval_id": "APR-7", "tenant": "acme", "env": "dev", "nonce": "n-7"},
        sort_keys=True,
        separators=(",", ":"),
    )
    record = AttestedApproval(
        approval_id="APR-7",
        tenant="acme",
        env="dev",
        signature=hmac.new(KEY.encode(), legacy_payload.encode(), sha256).hexdigest(),
        nonce="n-7",
        issued_at=0,
    )

    with pytest.raises(ScopeError, match="signed before approval TTLs existed"):
        _broker().mint(record)
    assert resolve_incident_scope(_incident(record), _Log()) is None, (
        "naming the failure must never turn into accepting it"
    )


def test_the_ttl_is_configurable_and_has_no_off_switch(wired, monkeypatch):
    """Operators can widen it for a genuinely slower path; they cannot disable it."""
    monkeypatch.setenv(APPROVAL_TTL_ENV, "5")
    old = sign_approval(
        "APR-5", "acme", "dev", key=KEY, issued_at=int(time.time()) - 60
    )
    assert resolve_incident_scope(_incident(old), _Log()) is None, "a 5s TTL did not apply"

    monkeypatch.setenv(APPROVAL_TTL_ENV, "0")
    fresh = sign_approval("APR-6", "acme", "dev", key=KEY)
    assert resolve_incident_scope(_incident(fresh), _Log()) is None, (
        "TTL=0 must be refused as a configuration error, not honoured as 'never expires'"
    )
