"""
Guards for signing-key rotation — the second half of "custody & rotation".

The defect these were written against: **the approval signing key could not be
rotated at all.** The signer (`attest_decision`, on the approval path) and the
verifier (`TokenBroker`, in the executor) are separate processes reading the same
`PLATFORM_APPROVAL_SIGNING_KEY`, so swapping it is never atomic. Whichever side
rolled first produced records the other refused, and the refusal it produced was
`failed attestation` — indistinguishable from tampering. So rotating meant either
an outage or a false forgery alarm, which in practice means the key never rotates
and "rotation" stays a word in a doc.

What made this tractable is D42's TTL, not new cryptography. A record is usable
for `ttl_seconds`, so an old key only has to stay *accepted* until the records it
signed have expired — a bounded overlap rather than an indefinite one. Hence
`PLATFORM_APPROVAL_SIGNING_KEYS_RETIRING`: verify-only keys, never signing keys.

The invariants below are the ones that make that safe rather than merely possible:

  1. A retiring key still only *verifies*. Nothing signs with it.
  2. The TTL binds records signed by a retiring key exactly as it binds fresh
     ones — otherwise the overlap window would be unbounded again, which is the
     thing D42 closed.
  3. A retiring key does not widen authority: tenant binding, staleness and
     provenance are unchanged.
  4. Use of a retiring key is *observable*, because nothing can enforce the
     operator's step 3 (drop the old key). Silence is what makes it safe to drop.
"""

from __future__ import annotations

import logging

import pytest
import yaml

from src.agents.platform.registry import load_registry
from src.agents.platform.scope import (
    RETIRING_KEYS_ENV,
    SIGNING_KEY_ENV,
    AttestedApproval,
    ScopeError,
    TokenBroker,
    sign_approval,
)

OLD_KEY = "key-being-rotated-away"
NEW_KEY = "key-rotated-to"

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
def registry_and_creds(tmp_path):
    """Two tenants, because a rotation must not quietly widen the tenant boundary."""
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
    return load_registry(registry_root), credential_dir


def _broker(registry_and_creds, *, signing_key=NEW_KEY, retiring=()) -> TokenBroker:
    registry, credential_dir = registry_and_creds
    return TokenBroker(
        registry=registry,
        credential_dir=credential_dir,
        signing_key=signing_key,
        retiring_keys=tuple(retiring),
    )


class TestTheRotationIsPossibleAtAll:
    """Step 2 of the procedure: signing the new key while still accepting the old."""

    def test_without_an_overlap_the_old_key_is_refused(self, registry_and_creds):
        """
        This is the defect, stated. Not a bug in verification — it is correct — but
        it is why the key had never been rotated: every record already in flight at
        the moment of the swap dies here.
        """
        broker = _broker(registry_and_creds)  # no retiring keys: the old behaviour
        in_flight = sign_approval("APR-1", "acme", "dev", key=OLD_KEY)
        with pytest.raises(ScopeError, match="attestation"):
            broker.mint(in_flight)

    def test_a_retiring_key_lets_the_in_flight_record_land(self, registry_and_creds):
        broker = _broker(registry_and_creds, retiring=[OLD_KEY])
        scope = broker.mint(sign_approval("APR-1", "acme", "dev", key=OLD_KEY))
        assert scope.tenant == "acme"

    def test_the_new_key_works_at_the_same_time(self, registry_and_creds):
        """Both halves live at once, or the overlap is not an overlap."""
        broker = _broker(registry_and_creds, retiring=[OLD_KEY])
        assert broker.mint(sign_approval("APR-2", "acme", "dev", key=NEW_KEY)).tenant == "acme"

    def test_more_than_one_generation_can_be_accepted(self, registry_and_creds):
        older = "key-from-two-rotations-ago"
        broker = _broker(registry_and_creds, retiring=[OLD_KEY, older])
        for i, key in enumerate((OLD_KEY, older, NEW_KEY)):
            assert broker.mint(sign_approval(f"APR-{i}", "acme", "dev", key=key)).tenant == "acme"

    def test_a_key_that_was_never_issued_is_still_refused(self, registry_and_creds):
        """The set of accepted keys is a list, not "any key that looks plausible"."""
        broker = _broker(registry_and_creds, retiring=[OLD_KEY])
        with pytest.raises(ScopeError, match="attestation"):
            broker.mint(sign_approval("APR-1", "acme", "dev", key="never-issued"))


class TestARetiringKeyOnlyVerifies:
    """It is on its way out. It must not be able to mint anything new."""

    def test_signing_uses_the_active_key_not_a_retiring_one(self, monkeypatch):
        monkeypatch.setenv(SIGNING_KEY_ENV, NEW_KEY)
        monkeypatch.setenv(RETIRING_KEYS_ENV, OLD_KEY)

        produced = sign_approval("APR-1", "acme", "dev")

        assert produced.signature == sign_approval("APR-1", "acme", "dev", key=NEW_KEY,
                                                   issued_at=produced.issued_at).signature
        assert produced.signature != sign_approval("APR-1", "acme", "dev", key=OLD_KEY,
                                                   issued_at=produced.issued_at).signature

    def test_dropping_the_retiring_key_ends_the_overlap(self, registry_and_creds):
        """Step 3. The old key stops working the moment it stops being listed."""
        record = sign_approval("APR-1", "acme", "dev", key=OLD_KEY)
        assert _broker(registry_and_creds, retiring=[OLD_KEY]).mint(record).tenant == "acme"
        with pytest.raises(ScopeError, match="attestation"):
            _broker(registry_and_creds).mint(record)


class TestTheOverlapStaysBounded:
    """
    The whole argument for accepting an old key is that D42 makes the window
    finite. If the TTL did not apply to old-key records, the overlap would be
    unbounded and this feature would reopen exactly what 결정 6 closed.
    """

    def test_an_expired_record_is_refused_even_under_a_retiring_key(self, registry_and_creds):
        import time

        broker = _broker(registry_and_creds, retiring=[OLD_KEY])
        stale = sign_approval(
            "APR-1", "acme", "dev", key=OLD_KEY,
            issued_at=int(time.time()) - (broker.ttl_seconds + 60),
        )
        with pytest.raises(ScopeError, match="past the"):
            broker.mint(stale)

    def test_a_retiring_key_cannot_backdate_its_way_out_of_the_ttl(self, registry_and_creds):
        """`issued_at` is inside the payload under every key, not just the active one."""
        import time

        broker = _broker(registry_and_creds, retiring=[OLD_KEY])
        genuine = sign_approval(
            "APR-1", "acme", "dev", key=OLD_KEY,
            issued_at=int(time.time()) - (broker.ttl_seconds + 60),
        )
        refreshed = AttestedApproval(
            approval_id=genuine.approval_id,
            tenant=genuine.tenant,
            env=genuine.env,
            signature=genuine.signature,   # <- kept
            nonce=genuine.nonce,
            issued_at=int(time.time()),    # <- moved forward
        )
        with pytest.raises(ScopeError, match="attestation"):
            broker.mint(refreshed)


class TestARetiringKeyDoesNotWidenAuthority:
    def test_tenant_binding_holds_under_a_retiring_key(self, registry_and_creds):
        broker = _broker(registry_and_creds, retiring=[OLD_KEY])
        record = sign_approval("APR-1", "acme", "dev", key=OLD_KEY)
        with pytest.raises(ScopeError, match="refusing"):
            broker.mint(record, requested_tenant="globex")

    def test_a_forged_tenant_is_refused_under_a_retiring_key(self, registry_and_creds):
        broker = _broker(registry_and_creds, retiring=[OLD_KEY])
        genuine = sign_approval("APR-1", "acme", "dev", key=OLD_KEY)
        forged = AttestedApproval(
            approval_id=genuine.approval_id,
            tenant="globex",
            env=genuine.env,
            signature=genuine.signature,
            nonce=genuine.nonce,
            issued_at=genuine.issued_at,
        )
        with pytest.raises(ScopeError, match="attestation"):
            broker.mint(forged)


class TestTheConfigCannotFakeARotation:
    def test_listing_the_active_key_as_retiring_is_refused(self, monkeypatch, registry_and_creds):
        """
        Both halves of a rotation are no-ops in this config, and it looks like both
        were done. Left to pass, step 2 could be skipped forever with nothing saying so.
        """
        registry, credential_dir = registry_and_creds
        monkeypatch.setenv("PLATFORM_CREDENTIAL_DIR", str(credential_dir))
        monkeypatch.setenv(SIGNING_KEY_ENV, NEW_KEY)
        monkeypatch.setenv(RETIRING_KEYS_ENV, f"{OLD_KEY},{NEW_KEY}")
        with pytest.raises(ScopeError, match="same key twice"):
            TokenBroker.from_env(registry)

    def test_a_duplicate_retiring_key_is_refused(self, monkeypatch, registry_and_creds):
        registry, credential_dir = registry_and_creds
        monkeypatch.setenv("PLATFORM_CREDENTIAL_DIR", str(credential_dir))
        monkeypatch.setenv(SIGNING_KEY_ENV, NEW_KEY)
        monkeypatch.setenv(RETIRING_KEYS_ENV, f"{OLD_KEY},{OLD_KEY}")
        with pytest.raises(ScopeError, match="more than once"):
            TokenBroker.from_env(registry)

    def test_no_rotation_in_flight_is_the_normal_state(self, monkeypatch, registry_and_creds):
        """Unset must stay a valid, quiet configuration — not a warning to tune out."""
        registry, credential_dir = registry_and_creds
        monkeypatch.setenv("PLATFORM_CREDENTIAL_DIR", str(credential_dir))
        monkeypatch.setenv(SIGNING_KEY_ENV, NEW_KEY)
        monkeypatch.delenv(RETIRING_KEYS_ENV, raising=False)
        assert TokenBroker.from_env(registry).retiring_keys == ()

    def test_whitespace_and_empty_entries_do_not_become_keys(self, monkeypatch, registry_and_creds):
        """An empty string is not a key; accepting one would accept `key=""` records."""
        registry, credential_dir = registry_and_creds
        monkeypatch.setenv("PLATFORM_CREDENTIAL_DIR", str(credential_dir))
        monkeypatch.setenv(SIGNING_KEY_ENV, NEW_KEY)
        monkeypatch.setenv(RETIRING_KEYS_ENV, f" {OLD_KEY} , ,")
        assert TokenBroker.from_env(registry).retiring_keys == (OLD_KEY,)


class TestFinishingTheRotationIsMeasurable:
    """
    Nothing in this module can enforce step 3 — a listed key is valid for as long as
    it is listed. What it can do is make "has the old key stopped being used?"
    answerable by measurement instead of belief.
    """

    def test_a_record_verified_under_a_retiring_key_says_so(self, caplog, registry_and_creds):
        broker = _broker(registry_and_creds, retiring=[OLD_KEY])
        with caplog.at_level(logging.WARNING):
            broker.mint(sign_approval("APR-1", "acme", "dev", key=OLD_KEY))
        assert "verified_under_retiring_key" in caplog.text

    def test_the_active_key_is_silent(self, caplog, registry_and_creds):
        """Otherwise the signal fires constantly and stops meaning anything."""
        broker = _broker(registry_and_creds, retiring=[OLD_KEY])
        with caplog.at_level(logging.WARNING):
            broker.mint(sign_approval("APR-2", "acme", "dev", key=NEW_KEY))
        assert "verified_under_retiring_key" not in caplog.text


class TestRotationAndRolloutSkewCanOverlap:
    def test_a_pre_ttl_record_signed_by_a_retiring_key_is_named_as_skew(self, registry_and_creds):
        """
        Still refused — only the diagnosis changes. If this fell through to "failed
        attestation" an operator would hunt a forgery during a routine rotation,
        which is the misdiagnosis `_signed_by_a_pre_ttl_version` exists to prevent.
        """
        import hmac
        from hashlib import sha256

        broker = _broker(registry_and_creds, retiring=[OLD_KEY])
        unsigned = AttestedApproval(
            approval_id="APR-1", tenant="acme", env="dev", signature="", nonce="", issued_at=0
        )
        # The old payload shape, taken from the producer rather than restated here.
        legacy = AttestedApproval(
            approval_id="APR-1",
            tenant="acme",
            env="dev",
            signature=hmac.new(
                OLD_KEY.encode(), broker._legacy_payload(unsigned).encode(), sha256
            ).hexdigest(),
            nonce="",
            issued_at=0,
        )
        with pytest.raises(ScopeError, match="before approval TTLs"):
            broker.mint(legacy)
