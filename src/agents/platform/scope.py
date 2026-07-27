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
"""

from __future__ import annotations

import hmac
import json
import os
from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path
from typing import Any

from src.agents.platform.registry import IsolationTier, Registry

# Where per-tenant kubeconfigs live. Each file is the credential for exactly one
# tenant (soft tier) or one env (vcluster/dedicated).
CREDENTIAL_DIR_ENV = "PLATFORM_CREDENTIAL_DIR"

# Shared secret used to attest approval records. Absent -> attestation cannot be
# verified, and the broker refuses to mint (fail-closed).
SIGNING_KEY_ENV = "PLATFORM_APPROVAL_SIGNING_KEY"


class ScopeError(RuntimeError):
    """Raised when a scoped credential cannot be established. Always fail-closed."""


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
    #: One-time-use marker; the broker rejects a replayed nonce.
    nonce: str = ""

    def payload(self) -> str:
        """Canonical signed form — field order fixed so signatures are stable."""
        return json.dumps(
            {
                "approval_id": self.approval_id,
                "tenant": self.tenant,
                "env": self.env,
                "nonce": self.nonce,
            },
            sort_keys=True,
            separators=(",", ":"),
        )


def sign_approval(approval_id: str, tenant: str, env: str, nonce: str = "", *, key: str | None = None) -> AttestedApproval:
    """Produce an attested record. Called by the pipeline when parking an approval."""
    secret = key if key is not None else os.getenv(SIGNING_KEY_ENV, "")
    if not secret:
        raise ScopeError("cannot attest an approval without a signing key")
    unsigned = AttestedApproval(approval_id=approval_id, tenant=tenant, env=env, signature="", nonce=nonce)
    digest = hmac.new(secret.encode(), unsigned.payload().encode(), sha256).hexdigest()
    return AttestedApproval(approval_id=approval_id, tenant=tenant, env=env, signature=digest, nonce=nonce)


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
    #: Nonces already spent — replaying an approval must not mint a second token.
    _spent: set[str] = field(default_factory=set)

    @classmethod
    def from_env(cls, registry: Registry) -> "TokenBroker":
        credential_dir = os.getenv(CREDENTIAL_DIR_ENV, "")
        signing_key = os.getenv(SIGNING_KEY_ENV, "")
        if not credential_dir:
            raise ScopeError(f"{CREDENTIAL_DIR_ENV} is not set — refusing to fall back to ambient credentials")
        if not signing_key:
            raise ScopeError(f"{SIGNING_KEY_ENV} is not set — approval provenance cannot be verified")
        return cls(registry=registry, credential_dir=Path(credential_dir), signing_key=signing_key)

    def verify(self, record: AttestedApproval) -> bool:
        """Constant-time signature check over the blast-radius fields."""
        expected = hmac.new(self.signing_key.encode(), record.payload().encode(), sha256).hexdigest()
        return hmac.compare_digest(expected, record.signature)

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
        if not self.verify(record):
            raise ScopeError(f"approval {record.approval_id!r} failed attestation — refusing to mint")

        if requested_tenant is not None and requested_tenant != record.tenant:
            raise ScopeError(
                f"caller asked for tenant {requested_tenant!r} but approval "
                f"{record.approval_id!r} attests tenant {record.tenant!r} — refusing"
            )

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
