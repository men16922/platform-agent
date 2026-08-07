"""
Scoped execution credentials — Phase 1a of the multi-tenant plan.

The privileged actor in this system is not a dashboard viewer; it is the ops
agent that runs remediation (`restart_workload` / `scale_out` / `rollback_release`).
So the first-class security invariant is **the credential is the boundary and the
label is a convenience**, and it has to be enforced by a code seam rather than by
prose.

Before this module the on-prem runner shelled out to `kubectl` against whatever
ambient kubeconfig context happened to be current — no `--kubeconfig`, no
`--context`. Blast radius was therefore whatever that context could reach, and a
routing bug failed **open**. Two pieces fix that:

``IncidentScope``
    An opaque, per-incident credential handle. The runner cannot execute without
    one, and it cannot enumerate other tenants' credentials because it never
    receives a directory of them — only the single handle for its own incident.

``TokenBroker``
    Mints those handles. Critically it does **not** trust a caller-supplied
    tenant string: the caller must present an *attested* approval record, and the
    broker issues a credential for the tenant named **inside that record**. This
    is what stops the broker from becoming the new concentration point — a
    compromised caller cannot ask for "tenant-B" any more than it can forge the
    signature.

Isolation tier decides what a credential is scoped *to* (see
``IsolationTier.credential_scope``): under the default soft tier several tenants
share one cluster by namespace, so the unit is the **tenant**, not the env — a
per-env kubeconfig would reach co-tenant namespaces on the same cluster.

**Reachability — read this before believing the gate does anything.**

Measured 2026-07-30: *nothing in production could open it.* No adapter wrote
``source_metadata["attested_approval"]``, ``sign_approval`` was called only from
tests, and neither broker environment variable was set by any stack, Makefile or
script. Every real incident resolved to ``None`` and every live remediation was
refused — fail-closed, which is safe, but it meant "blast radius = 1 tenant/env"
described a closed door rather than an enforced boundary. It stayed invisible
because ``ONPREM_EXECUTOR_LIVE`` defaults to false, so the gate was never reached.

2026-07-31 (결정 5, option A) added the missing half: :func:`attest_decision` is
called by the on-prem webhook on both the AUTO and the approval path, and
``make scope-credentials`` mints the per-tenant kubeconfigs and prints the two
variables. So the mechanism is now **reachable but opt-in** — with the variables
unset it still resolves to ``None`` and still refuses, byte for byte as before.

Which means the honest statement is: *scoping works when configured, and silently
does not when it is not.* ``scripts/probe_scope_reachability.py`` answers which of
those a given environment is in, and prints REFUSED when it is the second.
``tests/test_scope_producer_reachability.py`` holds the invariant that a producer
and the credentials must arrive together — it failed the moment
:func:`attest_decision` landed without the Makefile target, which is exactly the
trap it was written for. Options and trade-offs →
``docs/plans/2026-07-30-deploy-request-tenant-scoping.md``.
"""

from __future__ import annotations

import hmac
import json
import logging
import os
import time
from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path
from typing import Any

from src.agents.platform.registry import IsolationTier, Registry

# Where per-tenant kubeconfigs live. Each file is the credential for exactly one
# tenant (soft tier) or one env (vcluster/dedicated).
CREDENTIAL_DIR_ENV = "PLATFORM_CREDENTIAL_DIR"

# Shared secret used to attest approval records. Absent -> attestation cannot be
# verified, and the broker refuses to mint (fail-closed). This is the ONLY key
# anything signs with; see :data:`RETIRING_KEYS_ENV` for the verify-only set.
SIGNING_KEY_ENV = "PLATFORM_APPROVAL_SIGNING_KEY"

#: Keys accepted for verification but **never used to sign**. Comma-separated.
#:
#: Without this the key cannot be rotated at all. The signer (:func:`attest_decision`,
#: on the approval path) and the verifier (:class:`TokenBroker`, in the executor) are
#: different processes, so swapping :data:`SIGNING_KEY_ENV` is never atomic. Records
#: signed by whichever side rolled first fail :meth:`TokenBroker.verify` and surface
#: as ``failed attestation`` — which reads as tampering, the exact misdiagnosis
#: :meth:`TokenBroker._signed_by_a_pre_ttl_version` exists to prevent for the other
#: rollout skew. Result: rotation means an outage or a false alarm, so in practice
#: the key never rotates.
#:
#: What makes this tractable is the TTL (결정 6 / D42). A record is usable for
#: :data:`DEFAULT_APPROVAL_TTL_SECONDS`, so the old key only has to stay accepted
#: until every record it signed has expired — the overlap is **bounded and short**,
#: not indefinite. The procedure this supports:
#:
#:   1. add the current key to ``RETIRING``, roll everything (accepts old + new)
#:   2. swap ``SIGNING_KEY`` to the new key, roll everything (signs new, accepts old)
#:   3. wait out the TTL, drop ``RETIRING``, roll everything (accepts new only)
#:
#: Step 3 is not optional and nothing here can enforce it: a listed key stays valid
#: for as long as it is listed. :meth:`TokenBroker.mint` logs every record that
#: verified under a retiring key so "is the rotation finished?" is answerable by
#: measurement rather than belief — when that line stops, step 3 is safe.
RETIRING_KEYS_ENV = "PLATFORM_APPROVAL_SIGNING_KEYS_RETIRING"

# How long an attested approval stays usable, in seconds. Widen it if a real
# dispatch path is slower than this; never widen it to "fix" a replay complaint.
APPROVAL_TTL_ENV = "PLATFORM_APPROVAL_TTL_SECONDS"

#: 15 minutes. Chosen from the shape of the path rather than picked round: the
#: attestation is minted at the instant authorization exists (AUTO = the Guardian
#: policy decision, APPROVE = the human resolving the parked approval — see
#: :func:`attest_decision`), and it is consumed by the executor in the same flow.
#: There is **no human wait inside that window by design**, so what has to fit is
#: machine time: dispatch, plus Step Functions retries, plus queue latency. 15
#: minutes is generous for that and still short enough that a leaked record is not
#: a standing credential.
DEFAULT_APPROVAL_TTL_SECONDS = 900

#: Tolerance for a signer whose clock runs ahead of the verifier's. Small on
#: purpose — a record stamped far in the future is either a broken clock or an
#: attempt to mint something that never expires, and both should be refused.
CLOCK_SKEW_TOLERANCE_SECONDS = 60

logger = logging.getLogger(__name__)


class ScopeError(RuntimeError):
    """Raised when a scoped credential cannot be established. Always fail-closed."""


def _parse_retiring_keys(raw: str, signing_key: str) -> tuple[str, ...]:
    """Parse :data:`RETIRING_KEYS_ENV`, refusing the shapes that fake a rotation.

    Refused on purpose:

    * the active key listed as retiring — the two halves of a rotation are "sign
      with new" and "still accept old", and a config where they are the same key
      has done neither while looking like it did both. Left to pass, step 2 of the
      procedure could be skipped forever and nothing would say so.
    * a duplicate — harmless to verification, but it means the operator is tracking
      more keys than they think, and this list is the only record of what is still
      accepted.

    An empty value is not an error: no rotation in flight is the steady state.
    """
    keys = tuple(part.strip() for part in raw.split(",") if part.strip())
    if signing_key in keys:
        raise ScopeError(
            f"{RETIRING_KEYS_ENV} lists the active {SIGNING_KEY_ENV} — that is not a "
            "rotation, it is the same key twice. Retire the key you are rotating AWAY "
            "from and sign with the new one"
        )
    if len(set(keys)) != len(keys):
        raise ScopeError(
            f"{RETIRING_KEYS_ENV} lists the same key more than once — refusing, because "
            "this list is the only record of which old keys are still accepted"
        )
    return keys


@dataclass(frozen=True)
class IncidentScope:
    """
    A single-incident credential handle.

    Deliberately narrow: it names one tenant/env and points at one kubeconfig.
    There is no method to list other tenants, because the executor holding this
    object must not be able to reach beyond the incident it was minted for.
    """

    tenant: str
    env: str
    kubeconfig_path: str
    #: Which record authorised this scope — carried for audit, never for authz.
    approval_id: str = ""
    #: Namespaces this credential is expected to reach (advisory; RBAC is truth).
    allowed_namespaces: tuple[str, ...] = ()

    def kubectl_prefix(self) -> list[str]:
        """Argv prefix pinning kubectl to this credential (never ambient)."""
        return ["--kubeconfig", self.kubeconfig_path]

    def permits_namespace(self, namespace: str) -> bool:
        """
        Advisory pre-check only.

        Returning True here does NOT grant anything: the real answer comes from
        the API server rejecting the call. This exists to skip an obviously
        cross-tenant action early with a clear log line, not to make a decision
        the RBAC layer wouldn't also make.
        """
        if not namespace or not self.allowed_namespaces:
            return True
        return namespace in self.allowed_namespaces

    def redacted(self) -> dict[str, Any]:
        """Loggable form — no token material, no path leakage beyond the filename."""
        return {
            "tenant": self.tenant,
            "env": self.env,
            "approval_id": self.approval_id,
            "kubeconfig": Path(self.kubeconfig_path).name,
        }


@dataclass(frozen=True)
class AttestedApproval:
    """
    An approval record carrying its own provenance.

    The signature covers the fields that decide blast radius (record id, tenant,
    env). A caller can hand this to the broker but cannot alter the tenant
    without invalidating it.
    """

    approval_id: str
    tenant: str
    env: str
    signature: str
    #: Replay marker. NOT one-time-use — the rejection in :meth:`TokenBroker.mint`
    #: is per broker INSTANCE and production builds a fresh broker on every call.
    #: What bounds reuse instead is :attr:`issued_at` plus the broker's TTL; see
    #: :data:`APPROVAL_TTL_ENV` and docs/plans/2026-08-02-nonce-replay-scope.md.
    nonce: str = ""
    #: Epoch seconds when the authorization happened. **Signed**, so it cannot be
    #: pushed forward without the key. Zero means "signed by a version that did not
    #: record it", which the broker refuses rather than treating as ageless.
    issued_at: int = 0

    def payload(self) -> str:
        """Canonical signed form — field order fixed so signatures are stable."""
        return json.dumps(
            {
                "approval_id": self.approval_id,
                "tenant": self.tenant,
                "env": self.env,
                "nonce": self.nonce,
                "issued_at": self.issued_at,
            },
            sort_keys=True,
            separators=(",", ":"),
        )


def sign_approval(
    approval_id: str,
    tenant: str,
    env: str,
    nonce: str = "",
    *,
    key: str | None = None,
    issued_at: int | None = None,
) -> AttestedApproval:
    """Produce an attested record, stamped with the moment the authorization existed.

    ``issued_at`` defaults to now and is covered by the signature. It is what makes
    the record perishable: reuse is bounded by age rather than by a spent-nonce set
    that no production lifetime survives (결정 6 / option C).
    """
    secret = key if key is not None else os.getenv(SIGNING_KEY_ENV, "")
    if not secret:
        raise ScopeError("cannot attest an approval without a signing key")
    stamp = int(time.time()) if issued_at is None else int(issued_at)
    unsigned = AttestedApproval(
        approval_id=approval_id, tenant=tenant, env=env, signature="", nonce=nonce, issued_at=stamp
    )
    digest = hmac.new(secret.encode(), unsigned.payload().encode(), sha256).hexdigest()
    return AttestedApproval(
        approval_id=approval_id, tenant=tenant, env=env, signature=digest, nonce=nonce, issued_at=stamp
    )


@dataclass
class TokenBroker:
    """
    Mints per-incident scoped credentials from attested approval records.

    Not a credential vault: it verifies provenance and hands back the one handle
    the incident is entitled to. It never answers "give me tenant X's credential"
    on the strength of the caller saying so.
    """

    registry: Registry
    credential_dir: Path
    signing_key: str
    #: Seconds an attested record stays usable. See :data:`DEFAULT_APPROVAL_TTL_SECONDS`.
    ttl_seconds: int = DEFAULT_APPROVAL_TTL_SECONDS
    #: Keys accepted by :meth:`verify` but never used to sign. Empty is the normal
    #: steady state; non-empty means a rotation is mid-flight. See
    #: :data:`RETIRING_KEYS_ENV` for why an empty overlap makes rotation impossible.
    retiring_keys: tuple[str, ...] = ()
    #: Nonces spent **by this instance**. Kept, and deliberately NOT described as
    #: one-time-use, because measured 2026-08-02 it is not: the only production
    #: caller (:func:`resolve_incident_scope`) builds a broker per call, so this set
    #: starts empty every time — three replays of one record minted three scopes.
    #:
    #: It was not turned into real one-time-use because that would refuse a
    #: legitimate caller: ``aws/executor.py`` resolves the scope for the same
    #: incident on both the runbook path and the action path, and a retried Step
    #: Function does it again. What bounds reuse instead is :attr:`ttl_seconds`
    #: (결정 6, option C) — a weaker promise than one-time-use and one that is
    #: actually kept. Full reasoning: docs/plans/2026-08-02-nonce-replay-scope.md.
    _spent: set[str] = field(default_factory=set)

    @classmethod
    def from_env(cls, registry: Registry) -> "TokenBroker":
        credential_dir = os.getenv(CREDENTIAL_DIR_ENV, "")
        signing_key = os.getenv(SIGNING_KEY_ENV, "")
        if not credential_dir:
            raise ScopeError(f"{CREDENTIAL_DIR_ENV} is not set — refusing to fall back to ambient credentials")
        if not signing_key:
            raise ScopeError(f"{SIGNING_KEY_ENV} is not set — approval provenance cannot be verified")
        raw_ttl = os.getenv(APPROVAL_TTL_ENV, "").strip()
        try:
            ttl = int(raw_ttl) if raw_ttl else DEFAULT_APPROVAL_TTL_SECONDS
        except ValueError:
            raise ScopeError(
                f"{APPROVAL_TTL_ENV}={raw_ttl!r} is not an integer — refusing to guess a TTL"
            ) from None
        if ttl <= 0:
            raise ScopeError(
                f"{APPROVAL_TTL_ENV}={ttl} would disable expiry; there is no 'never expires' setting"
            )
        return cls(
            registry=registry,
            credential_dir=Path(credential_dir),
            signing_key=signing_key,
            ttl_seconds=ttl,
            retiring_keys=_parse_retiring_keys(os.getenv(RETIRING_KEYS_ENV, ""), signing_key),
        )

    def _legacy_payload(self, record: AttestedApproval) -> str:
        """The signed form used before ``issued_at`` existed.

        Kept **only to name the failure**, never to accept one. Measured while
        building the TTL: a record signed by a pre-TTL version does not reach the
        age check at all, because ``issued_at`` is inside the payload and its
        absence changes the digest — so it dies at :meth:`verify` reporting
        "failed attestation", which reads as tampering. During a rolling deploy
        that is the normal case, and sending an operator to hunt a forgery is the
        kind of misleading diagnostic this repo keeps paying for. This lets
        :meth:`mint` say what actually happened.
        """
        return json.dumps(
            {
                "approval_id": record.approval_id,
                "tenant": record.tenant,
                "env": record.env,
                "nonce": record.nonce,
            },
            sort_keys=True,
            separators=(",", ":"),
        )

    def _signed_by_a_pre_ttl_version(self, record: AttestedApproval) -> bool:
        """True when the signature is valid for the OLD payload shape. Never grants.

        Checks the retiring keys too. A rollout that changes the payload shape and a
        rotation that changes the key can overlap — and if they do, a record that is
        BOTH pre-TTL and old-key would fall through to "failed attestation" and be
        read as tampering, which is the one outcome this method exists to prevent.
        """
        if record.issued_at:
            return False
        payload = self._legacy_payload(record).encode()
        return any(
            hmac.compare_digest(
                hmac.new(key.encode(), payload, sha256).hexdigest(), record.signature
            )
            for key in self._accepted_keys()
        )

    def _accepted_keys(self) -> tuple[str, ...]:
        """Every key a signature may verify under: the active one, then retiring ones.

        Signing never consults this — :func:`sign_approval` reads
        :data:`SIGNING_KEY_ENV` alone, so a retiring key can only ever let an old
        record in, never mint a new one under a key that is on its way out.
        """
        return (self.signing_key, *self.retiring_keys)

    def _verifying_key_index(self, record: AttestedApproval) -> int | None:
        """Index into :meth:`_accepted_keys` of the key that verifies ``record``.

        Every candidate is compared even after a match, so the work does not depend
        on which key matched; the comparison itself is already constant-time. 0 is
        the active key — falsy, so callers must test ``is None``.
        """
        payload = record.payload().encode()
        matched: int | None = None
        for index, key in enumerate(self._accepted_keys()):
            expected = hmac.new(key.encode(), payload, sha256).hexdigest()
            if hmac.compare_digest(expected, record.signature) and matched is None:
                matched = index
        return matched

    def _refuse_if_stale(self, record: AttestedApproval) -> None:
        """Age check. The signature covers ``issued_at``, so this cannot be extended.

        Reached only by records that already verified, which means the zero case
        here is an *explicitly* unstamped signature (``sign_approval(..., issued_at=0)``)
        rather than version skew — skew is caught earlier and named in :meth:`mint`.
        Either way an approval whose age cannot be established is refused, the same
        reading this module takes everywhere: the caller gets no scope and the
        action is refused, which is the pre-D38 behaviour rather than a new outage.
        """
        if not record.issued_at:
            raise ScopeError(
                f"approval {record.approval_id!r} is signed with issued_at=0 — an "
                "approval whose age cannot be established is not one this broker will "
                "mint against"
            )
        now = int(time.time())
        age = now - record.issued_at
        if age > self.ttl_seconds:
            raise ScopeError(
                f"approval {record.approval_id!r} is {age}s old, past the "
                f"{self.ttl_seconds}s TTL — re-authorize rather than reusing it"
            )
        if age < -CLOCK_SKEW_TOLERANCE_SECONDS:
            raise ScopeError(
                f"approval {record.approval_id!r} is stamped {-age}s in the future — "
                "refusing (clock skew, or a record built to outlive its TTL)"
            )

    def verify(self, record: AttestedApproval) -> bool:
        """Constant-time signature check over the blast-radius fields.

        Accepts the active key or any retiring one. Which key matched is not part of
        this answer — :meth:`mint` asks :meth:`_verifying_key_index` for that, because
        the distinction is operational (is the rotation finished?) and not a
        difference in authority.
        """
        return self._verifying_key_index(record) is not None

    def credential_path(self, tenant: str, env: str) -> Path:
        """
        Filename for a scope's credential, keyed by the tier's credential unit.

        soft      -> <tenant>.kubeconfig   (one cluster shared by namespace)
        otherwise -> <tenant>-<env>.kubeconfig
        """
        tier = self.registry.tenant(tenant).isolation
        if tier is IsolationTier.SOFT:
            return self.credential_dir / f"{tenant}.kubeconfig"
        return self.credential_dir / f"{tenant}-{env}.kubeconfig"

    def mint(self, record: AttestedApproval, *, requested_tenant: str | None = None) -> IncidentScope:
        """
        Issue the scope for ``record``'s tenant — never for a caller-named tenant.

        ``requested_tenant`` exists only so a mismatch can be *detected and
        refused* rather than silently honoured; it is never used to select the
        credential.
        """
        verifying_key = self._verifying_key_index(record)
        if verifying_key is None:
            if self._signed_by_a_pre_ttl_version(record):
                # Still refused — only the diagnosis changes. Accepting it would
                # reopen unbounded reuse, which is the whole point of the TTL.
                raise ScopeError(
                    f"approval {record.approval_id!r} was signed before approval TTLs "
                    "existed (no issued_at in its payload) — refusing. This is version "
                    "skew during a rollout, not tampering; it clears once the signer "
                    "is on the same build"
                )
            raise ScopeError(f"approval {record.approval_id!r} failed attestation — refusing to mint")

        if verifying_key:  # 0 is the active key; anything else is on its way out
            # The only signal that says whether a rotation can be finished. Nothing
            # here can enforce step 3 (drop the retiring key) — but once this stops
            # appearing, every record signed by the old key has aged past the TTL and
            # dropping it is safe. Silence is the measurement.
            logger.warning(
                "scope.approval.verified_under_retiring_key",
                extra={
                    "approval_id": record.approval_id,
                    "tenant": record.tenant,
                    "retiring_key_index": verifying_key - 1,
                    "ttl_seconds": self.ttl_seconds,
                },
            )

        # After the signature, because an unsigned record's timestamp means nothing.
        self._refuse_if_stale(record)

        if requested_tenant is not None and requested_tenant != record.tenant:
            raise ScopeError(
                f"caller asked for tenant {requested_tenant!r} but approval "
                f"{record.approval_id!r} attests tenant {record.tenant!r} — refusing"
            )

        # Instance-local replay dedupe. NOT one-time-use — see `_spent`. It refuses a
        # tight loop inside one broker and nothing else, which is worth keeping and
        # not worth claiming.
        if record.nonce:
            if record.nonce in self._spent:
                raise ScopeError(f"approval {record.approval_id!r} nonce replayed — refusing to mint")
            self._spent.add(record.nonce)

        # The registry is the authority on whether this tenant/env even exists.
        environment = self.registry.environment(record.tenant, record.env)
        tenant = self.registry.tenant(record.tenant)

        path = self.credential_path(record.tenant, record.env)
        if not path.is_file():
            raise ScopeError(
                f"no credential for tenant={record.tenant} env={record.env} at {path.name} — "
                "fail-closed rather than falling back to ambient context"
            )

        namespaces = tuple(
            tenant.namespace_for(environment.name, capability) for capability in environment.addons
        )
        return IncidentScope(
            tenant=record.tenant,
            env=record.env,
            kubeconfig_path=str(path),
            approval_id=record.approval_id,
            allowed_namespaces=namespaces,
        )


def _incident_of(decision_out: Any) -> Any:
    """The normalized incident nested inside a decision payload, or None.

    The executor reads ``decision.analyzer.detector.normalized_incident``; this
    walks the same path on the dict form the in-process pipeline passes around.
    One traversal rather than one per call site, because there is more than one
    gate (AUTO and approval) and the second one is always the one that forgets.
    """
    node = decision_out
    for key in ("analyzer", "detector", "normalized_incident"):
        if node is None:
            return None
        node = node.get(key) if isinstance(node, dict) else getattr(node, key, None)
    return node


def _field(incident: Any, name: str) -> str:
    value = incident.get(name) if isinstance(incident, dict) else getattr(incident, name, "")
    return str(value or "")


def attest_decision(decision_out: Any, *, approval_id: str, log: Any = None) -> bool:
    """Attach an attested authorization to a decision, so a scope can be minted for it.

    This is the producer the broker was written for and never had. Until now
    ``sign_approval`` was called only by tests, so ``resolve_incident_scope``
    returned ``None`` for every real incident and ``guard_scoped_action`` refused
    every live remediation — a gate that could not be opened
    (``docs/evidence/deploy-path-authorization.log``).

    Called at the two points where an action becomes *authorized*:

      AUTO      the Guardian policy decided this class of incident may execute
                without a human. The authorization is the policy decision, so the
                attestation is minted there.
      APPROVE   a human resolved the parked approval. The authorization did not
                exist until then, so neither does the attestation — signing at
                parking time would attest an action nobody had approved yet.

    **What the signature is worth, precisely.** It binds the tenant/env to the
    record, so a downstream caller cannot ask the broker for a different tenant
    than the one that was authorized — that is the property ``TokenBroker.mint``
    was built around. It is *not* a defence against code execution inside this
    process, which holds the signing key: an attacker there can sign anything. It
    buys attribution and it stops routing bugs and payload tampering from widening
    blast radius. Do not describe it as more than that anywhere.

    Best-effort on purpose. With no signing key configured this returns False and
    changes nothing, so the current default behaviour is bit-for-bit unchanged: no
    attestation, no scope, and the gate refuses exactly as it does today. Turning
    this into a hard failure would make an unconfigured deployment stop working at
    the moment it tried to remediate, which is worse than the fail-closed refusal
    it already gets.
    """
    incident = _incident_of(decision_out)
    if incident is None:
        return False

    tenant, env = _field(incident, "tenant"), _field(incident, "env")
    if not tenant or not env:
        # An unattributed incident cannot be authorized for anyone. The detector
        # already declines to invent these (signals/onprem.py), so absence here
        # means the alert carried no tenant — not that we failed to look.
        if log:
            log.info("scope.attest.skipped", reason="incident names no tenant/env")
        return False

    try:
        record = sign_approval(approval_id, tenant, env)
    except ScopeError as exc:
        if log:
            log.info("scope.attest.unavailable", error=str(exc))
        return False

    metadata = (
        incident.setdefault("source_metadata", {})
        if isinstance(incident, dict)
        else getattr(incident, "source_metadata", None)
    )
    if metadata is None:
        return False
    metadata["attested_approval"] = {
        "approval_id": record.approval_id,
        "tenant": record.tenant,
        "env": record.env,
        "signature": record.signature,
        "nonce": record.nonce,
        # Written AND read (resolve_incident_scope below). Persisting it without a
        # consumer would be M13 all over again — and worse here, because the broker
        # refuses a record whose stamp is missing, so a write-only field would fail
        # every mint instead of silently doing nothing.
        "issued_at": record.issued_at,
    }
    if log:
        log.info("scope.attest.signed", approval_id=approval_id, tenant=tenant, env=env)
    return True


def resolve_incident_scope(normalized_incident: Any, log: Any) -> IncidentScope | None:
    """
    Mint the scope an incident is entitled to, or return None (fail-closed downstream).

    The credential is chosen by the **attested approval record** carried on the
    incident, never by a caller-supplied tenant string. Returning None is safe
    precisely because ``guard_scoped_action`` refuses to act on it — this function
    is allowed to be best-effort only because the gate downstream is not.

    Lives here rather than in one cloud's executor because there is more than one
    dispatch path into the runners (the AWS Step Functions executor and the GCP
    Cloud Workflows executor). When this logic sat in ``aws/executor.py`` the GCP
    path simply had no scope at all.

    Best-effort by design: tenancy resolution must never take down the AWS path,
    which has no tenant and never had this problem.
    """
    if normalized_incident is None or getattr(normalized_incident, "provider", None) == "aws":
        return None

    attested = (getattr(normalized_incident, "source_metadata", None) or {}).get("attested_approval")
    if not isinstance(attested, dict):
        log.info("executor.scope.absent", reason="no attested approval on the incident")
        return None

    try:
        from src.agents.platform.registry import load_registry

        broker = TokenBroker.from_env(load_registry())
        record = AttestedApproval(
            approval_id=attested.get("approval_id", ""),
            tenant=attested.get("tenant", ""),
            env=attested.get("env", ""),
            signature=attested.get("signature", ""),
            nonce=attested.get("nonce", ""),
            issued_at=int(attested.get("issued_at", 0) or 0),
        )
        # The incident's own tenant is passed only so a mismatch is REFUSED;
        # the broker never uses it to pick the credential.
        scope = broker.mint(record, requested_tenant=getattr(normalized_incident, "tenant", "") or None)
        log.info("executor.scope.minted", scope=scope.redacted())
        return scope
    except Exception as exc:
        log.warning("executor.scope.unavailable", error=str(exc))
        return None


def guard_scoped_action(
    *,
    action: str,
    namespace: str,
    scope: IncidentScope | None,
    log: Any,
    log_prefix: str,
) -> IncidentScope:
    """
    The fail-closed gate every live remediation action must pass. Phase 3.

    This lived inside the on-prem runner through Phase 1a, which meant each new
    runner had to *remember* to re-derive it. That is the failure mode this repo
    has already paid for once (a capability rendered per-engine is a capability
    the third engine forgets), so the gate is one implementation and the runners
    call it — they do not restate it.

    Two refusals, in order:

    1. **No scope** — an unresolved credential means we do not know whose cluster
       this would touch, which is exactly when acting is least safe. Refuse
       rather than fall back to whatever ambient identity is lying around.
    2. **Out-of-scope namespace** — advisory, because the API server is the real
       authority. Refusing here turns an opaque ``Forbidden`` into an
       attributable log line naming the tenant and the namespace.

    ``log_prefix`` keeps each runner's event names intact (``<prefix>.no_scope``,
    ``<prefix>.out_of_scope``) so operators keep grepping what they already grep.

    Returns the scope so callers can use it as an assertion site rather than
    re-checking for ``None`` afterwards.
    """
    if scope is None:
        log.error(f"{log_prefix}.no_scope", action=action)
        raise ScopeError(
            f"refusing live action {action!r} without a scoped credential "
            "(ambient credential execution was removed in Phase 1a)"
        )

    if not scope.permits_namespace(namespace):
        log.warning(
            f"{log_prefix}.out_of_scope",
            action=action,
            namespace=namespace,
            scope=scope.redacted(),
        )
        raise ScopeError(
            f"namespace {namespace!r} is outside the scope of tenant {scope.tenant!r}"
        )

    return scope
