"""
Two-axis add-on status collection — **push**, from the spoke to the hub.

The direction is the whole design. The obvious build is a hub that polls every
cluster, and it fails the plan's top invariant on day one: to read N clusters the
hub must HOLD credentials for N clusters, which makes the control plane the single
place worth attacking and gives it exactly the cross-tenant reach Phase 1a spent
its effort removing. Here each cluster runs an agent that reads only itself and
pushes; the hub holds **zero spoke read credentials** and cannot initiate anything.

That inverts the trust problem rather than solving it, so two things follow:

**1. Identity is the key that verified the signature, never the body.**
A report says "I am acme/dev". Believing that field is the same mistake the release
gate made (D24) — a caller asserting its own identity. Instead the hub looks up the
signing key *for the claimed identity* and verifies against that one key: claiming
acme/dev requires acme/dev's key. A report is then rejected outright if it carries
rows for any other tenant/env, because a spoke agent's blast radius is one
tenant/env on the read path too.

**2. Silence must be loud.**
A push model's failure mode is a dead agent, and the default reading of "no new
data" is "nothing changed" — a frozen-healthy dashboard is the worst possible
output of a drift detector. Reports therefore expire: past ``stale_after``, every
axis reads UNKNOWN, which is a state the UI already has to render honestly.

The reader also reports declared-but-absent add-ons as MISSING instead of omitting
them. An add-on that vanished from the cluster would otherwise vanish from the
list, and a shorter list reads as "nothing wrong".
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import subprocess
from dataclasses import dataclass, field
from typing import Any

from src.agents.platform.addon_status import (
    HealthState,
    NormalizedAddonStatus,
    SyncState,
    from_managed,
)
from src.agents.platform.adapters.argocd import ArgoCDDeliveryAdapter
from src.agents.platform.registry import Registry, Tenant
from src.agents.platform.tenancy import TENANT_LABEL

#: How long a report stays believable without a refresh. Chosen against the push
#: cadence (a CronJob/loop pushing every minute), not against how long a human
#: would tolerate stale data: the point is to detect a dead agent, not to expire
#: data that is merely a little old.
DEFAULT_STALE_AFTER_SEC = 300

#: env var holding ``{"<tenant>/<env>": "<hmac key>"}``. Per-identity keys, so
#: "who signed this" is a fact rather than a claim.
PUSH_KEYS_ENV = "PLATFORM_PUSH_KEYS"


class UnauthenticatedReport(ValueError):
    """Signature missing, unknown identity, or rows outside the signer's scope."""


@dataclass
class StatusReport:
    """One spoke agent's view of one tenant/env at one moment."""

    tenant: str
    env: str
    cluster: str
    #: Spoke-side wall clock (epoch seconds). The hub records its own receive time
    #: separately and staleness is computed from THAT — a spoke with a wrong clock
    #: (or a replayed report) must not be able to look fresh.
    collected_at: float
    statuses: list[NormalizedAddonStatus] = field(default_factory=list)

    @property
    def identity(self) -> str:
        return f"{self.tenant}/{self.env}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "tenant": self.tenant,
            "env": self.env,
            "cluster": self.cluster,
            "collected_at": self.collected_at,
            "statuses": [s.to_dict() for s in self.statuses],
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> StatusReport:
        return cls(
            tenant=payload["tenant"],
            env=payload["env"],
            cluster=payload.get("cluster", ""),
            collected_at=float(payload.get("collected_at", 0.0)),
            statuses=[
                NormalizedAddonStatus(
                    tenant=row["tenant"],
                    env=row["env"],
                    capability=row["capability"],
                    backend=row.get("backend", ""),
                    sync_state=SyncState(row.get("sync_state", "unknown")),
                    health_state=HealthState(row.get("health_state", "unknown")),
                    desired_version=row.get("desired_version"),
                    applicable=bool(row.get("applicable", True)),
                    native=row.get("native") or {},
                )
                for row in payload.get("statuses", [])
            ],
        )


# --- spoke side ------------------------------------------------------------


def read_applications(namespace: str = "argocd", *, kubectl: Any = None) -> list[dict[str, Any]]:
    """Read ArgoCD Applications from THIS cluster.

    Runs in the spoke, against the spoke's own API server. `kubectl` is injectable
    so the mapping can be tested without a cluster; the default shells out.
    """
    runner = kubectl or _kubectl
    proc = runner("get", "applications.argoproj.io", "-n", namespace, "-o", "json")
    if proc.returncode != 0:
        # No ArgoCD, no permission, no cluster — all "we did not observe", which is
        # UNKNOWN downstream. Never an empty list, which would read as "all gone".
        return []
    try:
        return json.loads(proc.stdout).get("items", [])
    except (ValueError, AttributeError):
        return []


def _kubectl(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["kubectl", *args], capture_output=True, text=True, timeout=60)


def collect(
    tenant: Tenant,
    env_name: str,
    applications: list[dict[str, Any]],
    *,
    observed: bool = True,
    scope_of: Any = None,
    is_managed: Any = None,
) -> list[NormalizedAddonStatus]:
    """Map observed Applications onto the two axes, one row per DECLARED add-on.

    Driven by the registry's declarations rather than by what the cluster happens
    to hold: an add-on that should exist and does not is the most important thing
    this function can report, and it can only be reported by something that knows
    what was supposed to be there.

    ``observed=False`` means we could not look at all (no ArgoCD, no permission).
    Every axis then reads UNKNOWN — distinct from MISSING, which is a real
    observation that the add-on is gone.

    ``scope_of`` (normally ``Registry.scope_of``) keeps cluster-scoped capabilities
    from being reported as the tenant's own. A shared operator is not something the
    tenant syncs, so per tenant its sync axis is meaningless — the same fact
    ``applicable=False`` already models for managed backends. Without this, every
    tenant on the cluster shows "logging MISSING, drifted" for one shared install
    that is running fine, and four tenants produce four false alarms about it.
    """
    env = tenant.environments.get(env_name)
    if env is None:
        return []

    by_capability: dict[str, dict[str, Any]] = {}
    shared_by_capability: dict[str, dict[str, Any]] = {}
    for application in applications:
        labels = (application.get("metadata") or {}).get("labels") or {}
        capability = labels.get("platform-agent.io/capability")
        if not capability:
            continue
        if labels.get(TENANT_LABEL) in (None, tenant.name):
            by_capability[capability] = application
        # An Application carrying a capability but no tenant label is the shared,
        # cluster-level installation of that capability.
        if TENANT_LABEL not in labels:
            shared_by_capability[capability] = application

    rows: list[NormalizedAddonStatus] = []
    for capability, declared in sorted(env.addons.items()):
        backend = declared.split()[0]
        version = env.addon_version(capability)
        application = by_capability.get(capability)

        if is_managed and is_managed(capability, backend):
            # A managed backend has no git-sync axis at all, and this collector —
            # which reads Kubernetes objects — cannot see it. Falling through would
            # report MISSING for a service that is running fine in the cloud
            # provider's console: the same false alarm the cluster-scoped case
            # produced, from a different direction.
            #
            # `healthy=None` rather than True: we have not observed anything.
            # Asserting health for a backend nobody queried is the fabrication the
            # two-axis model exists to prevent, and reading a green badge for an
            # unqueried service is worse than reading "unknown". A real health
            # signal needs the cloud API, which is Phase 4 (and billable).
            rows.append(from_managed(
                tenant=tenant.name,
                env=env_name,
                capability=capability,
                backend=backend,
                healthy=None,
                desired_version=version,
                native={"backend_kind": "managed", "substrate": env.substrate},
            ))
            continue

        if observed and scope_of and scope_of(capability) == "cluster":
            shared = shared_by_capability.get(capability)
            health = (
                ArgoCDDeliveryAdapter.normalise(
                    tenant.name, env_name, capability, shared
                ).health_state
                if shared is not None
                # Not MISSING: a cluster install this view cannot see through GitOps
                # (Terraform-owned, for instance) is unobserved, not absent. Claiming
                # a false outage for every tenant is as bad as hiding a real one.
                else HealthState.UNKNOWN
            )
            rows.append(NormalizedAddonStatus(
                tenant=tenant.name,
                env=env_name,
                capability=capability,
                backend=backend,
                sync_state=SyncState.NOT_APPLICABLE,
                health_state=health,
                desired_version=version,
                applicable=False,
                native={"scope": "cluster", "shared": shared is not None},
            ))
            continue

        if not observed:
            rows.append(NormalizedAddonStatus(
                tenant=tenant.name,
                env=env_name,
                capability=capability,
                backend=backend,
                sync_state=SyncState.UNKNOWN,
                health_state=HealthState.UNKNOWN,
                desired_version=version,
            ))
        elif application is None:
            rows.append(NormalizedAddonStatus(
                tenant=tenant.name,
                env=env_name,
                capability=capability,
                backend=backend,
                # Declared and absent. Not "unknown" — we looked, and it is not there.
                sync_state=SyncState.DRIFTED,
                health_state=HealthState.MISSING,
                desired_version=version,
            ))
        else:
            row = ArgoCDDeliveryAdapter.normalise(tenant.name, env_name, capability, application)
            row.backend = backend
            rows.append(row)
    return rows


def build_report(
    tenant: Tenant,
    env_name: str,
    applications: list[dict[str, Any]],
    *,
    now: float,
    observed: bool = True,
    scope_of: Any = None,
    is_managed: Any = None,
) -> StatusReport:
    env = tenant.environments[env_name]
    return StatusReport(
        tenant=tenant.name,
        env=env_name,
        cluster=env.cluster,
        collected_at=now,
        statuses=collect(
            tenant, env_name, applications,
            observed=observed, scope_of=scope_of, is_managed=is_managed,
        ),
    )


# --- signing ---------------------------------------------------------------


def _canonical(payload: dict[str, Any]) -> bytes:
    """Byte-stable rendering of the payload.

    Signature verification compares bytes; if the hub re-serialises the parsed body
    with different key order it verifies a different message than the one signed.
    """
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sign(payload: dict[str, Any], key: str) -> str:
    return hmac.new(key.encode("utf-8"), _canonical(payload), hashlib.sha256).hexdigest()


def load_push_keys(env: dict[str, str] | None = None) -> dict[str, str]:
    raw = (env or os.environ).get(PUSH_KEYS_ENV, "").strip()
    if not raw:
        return {}
    try:
        keys = json.loads(raw)
    except ValueError:
        return {}
    return {str(k): str(v) for k, v in keys.items()} if isinstance(keys, dict) else {}


def verify(payload: dict[str, Any], signature: str, keys: dict[str, str]) -> StatusReport:
    """Authenticate a pushed report and confine it to the signer's own scope.

    Raises rather than returning a flag: a caller that forgets to check a boolean
    ingests unauthenticated data, and this is the seam where that would matter.
    """
    identity = f"{payload.get('tenant')}/{payload.get('env')}"
    key = keys.get(identity)
    if key is None:
        # Deliberately the same error as a bad signature: distinguishing "no such
        # tenant" from "wrong key" tells an attacker which tenants exist.
        raise UnauthenticatedReport("report rejected")
    if not signature or not hmac.compare_digest(sign(payload, key), signature):
        raise UnauthenticatedReport("report rejected")

    report = StatusReport.from_dict(payload)
    foreign = {
        f"{row.tenant}/{row.env}" for row in report.statuses
    } - {report.identity}
    if foreign:
        # A spoke agent's reach is one tenant/env on the READ path too. Without
        # this, acme's key could write globex's status — reporting is a write.
        raise UnauthenticatedReport(
            f"report signed by {report.identity} carries rows for {sorted(foreign)}"
        )
    return report


# --- hub side --------------------------------------------------------------


@dataclass
class StatusStore:
    """Latest report per tenant/env, with staleness applied on read.

    In-memory and last-writer-wins on purpose: this is a cache of a fact each spoke
    can always re-derive, so durability buys nothing a restart does not fix in one
    push interval. What it must never do is answer with data whose freshness it
    cannot vouch for.
    """

    stale_after_sec: float = DEFAULT_STALE_AFTER_SEC
    _reports: dict[str, tuple[StatusReport, float]] = field(default_factory=dict)

    def ingest(self, report: StatusReport, *, received_at: float) -> None:
        self._reports[report.identity] = (report, received_at)

    def is_stale(self, identity: str, *, now: float) -> bool:
        entry = self._reports.get(identity)
        if entry is None:
            return True
        return (now - entry[1]) > self.stale_after_sec

    def statuses(self, *, now: float) -> list[NormalizedAddonStatus]:
        """Every known status, with stale reports degraded to UNKNOWN.

        Degraded rather than dropped: a tenant/env disappearing from the list looks
        like it was decommissioned, while UNKNOWN says "we have stopped hearing
        from this cluster", which is the actual fact and the actionable one.
        """
        rows: list[NormalizedAddonStatus] = []
        for identity, (report, received_at) in sorted(self._reports.items()):
            stale = (now - received_at) > self.stale_after_sec
            for row in report.statuses:
                if not stale:
                    rows.append(row)
                    continue
                rows.append(NormalizedAddonStatus(
                    tenant=row.tenant,
                    env=row.env,
                    capability=row.capability,
                    backend=row.backend,
                    sync_state=SyncState.UNKNOWN,
                    health_state=HealthState.UNKNOWN,
                    desired_version=row.desired_version,
                    applicable=row.applicable,
                    native={"stale_sec": round(now - received_at, 1), **(row.native or {})},
                ))
        return rows

    def freshness(self, *, now: float) -> list[dict[str, Any]]:
        """Per-identity heartbeat, so "we stopped hearing from acme/dev" is visible
        even when that tenant has no add-ons to show."""
        return [
            {
                "identity": identity,
                "cluster": report.cluster,
                "age_sec": round(now - received_at, 1),
                "stale": (now - received_at) > self.stale_after_sec,
            }
            for identity, (report, received_at) in sorted(self._reports.items())
        ]

    def missing_identities(self, registry: Registry) -> list[str]:
        """Declared tenant/envs that have NEVER pushed.

        The hub cannot tell "no agent deployed" from "agent died before its first
        push", and both are the same actionable gap: a cluster nobody is watching.
        """
        declared = {
            f"{tenant.name}/{env}"
            for tenant in registry.tenants.values()
            for env in tenant.environments
        }
        return sorted(declared - set(self._reports))
