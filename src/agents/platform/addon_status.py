"""
Normalized add-on status — **two orthogonal axes**, not one enum.

Why two axes (plan Critical#3): a single enum collapses "the cluster drifted from
git" and "the app is unhealthy" into one value, and drift is then unreportable.
The two mean different things and need different responses:

    Argo "Synced + Degraded"    -> {sync=synced,  health=degraded}  # app problem
    Argo "OutOfSync + Healthy"  -> {sync=drifted, health=healthy}   # DRIFT!

A managed backend (Amazon Managed Prometheus, Config Sync…) may have no sync
concept at all. That is `applicable=False` + `sync=NOT_APPLICABLE` — honestly
"this axis is meaningless here", never a fake "synced".
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class SyncState(str, Enum):
    """Does the cluster match the declared desired state?"""

    SYNCED = "synced"
    DRIFTED = "drifted"
    # Managed backends have no git-sync concept — see `applicable`.
    NOT_APPLICABLE = "n/a"
    UNKNOWN = "unknown"


class HealthState(str, Enum):
    """Is the thing actually working?"""

    HEALTHY = "healthy"
    PROGRESSING = "progressing"
    DEGRADED = "degraded"
    MISSING = "missing"
    # A dead push agent must surface as UNKNOWN, never silently freeze as healthy.
    UNKNOWN = "unknown"


@dataclass
class NormalizedAddonStatus:
    """Backend-neutral status for one (tenant, env, capability) triple."""

    tenant: str
    env: str
    capability: str
    backend: str
    sync_state: SyncState = SyncState.UNKNOWN
    health_state: HealthState = HealthState.UNKNOWN
    desired_version: str | None = None
    # False when the sync axis is meaningless for this backend (managed).
    applicable: bool = True
    # Raw backend payload, kept so a UI can show "why" without us modelling every
    # backend's vocabulary.
    native: dict[str, Any] = field(default_factory=dict)

    @property
    def is_drifted(self) -> bool:
        """Drift is a sync-axis fact and must not be inferred from health."""
        return self.sync_state is SyncState.DRIFTED

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "tenant": self.tenant,
            "env": self.env,
            "capability": self.capability,
            "backend": self.backend,
            "sync_state": self.sync_state.value,
            "health_state": self.health_state.value,
            "applicable": self.applicable,
        }
        if self.desired_version:
            result["desired_version"] = self.desired_version
        if self.native:
            result["native"] = self.native
        return result


_ARGO_HEALTH = {
    "Healthy": HealthState.HEALTHY,
    "Progressing": HealthState.PROGRESSING,
    "Degraded": HealthState.DEGRADED,
    "Missing": HealthState.MISSING,
    "Suspended": HealthState.PROGRESSING,
    "Unknown": HealthState.UNKNOWN,
}


def from_argocd(
    *,
    tenant: str,
    env: str,
    capability: str,
    sync_status: str,
    health_status: str,
    desired_version: str | None = None,
    backend: str = "argocd",
    native: dict[str, Any] | None = None,
) -> NormalizedAddonStatus:
    """
    Map an ArgoCD Application's two native fields onto our two axes.

    Argo already separates sync from health, so this is a rename — the value is
    that Flux and managed backends land in the same shape.
    """
    sync = {
        "Synced": SyncState.SYNCED,
        "OutOfSync": SyncState.DRIFTED,
    }.get(sync_status, SyncState.UNKNOWN)
    return NormalizedAddonStatus(
        tenant=tenant,
        env=env,
        capability=capability,
        backend=backend,
        sync_state=sync,
        health_state=_ARGO_HEALTH.get(health_status, HealthState.UNKNOWN),
        desired_version=desired_version,
        applicable=True,
        native=native or {"sync": sync_status, "health": health_status},
    )


def from_flux(
    *,
    tenant: str,
    env: str,
    capability: str,
    ready: bool | None,
    suspended: bool = False,
    desired_version: str | None = None,
    reason: str | None = None,
    backend: str = "flux",
    native: dict[str, Any] | None = None,
) -> NormalizedAddonStatus:
    """
    Map a Flux Kustomization/HelmRelease `Ready` condition onto both axes.

    Flux collapses the two axes into one condition, so this mapping is lossy by
    nature: Ready=False means "did not reconcile", which is a health failure and
    leaves sync genuinely UNKNOWN rather than DRIFTED. Claiming `drifted` here
    would invent information Flux never reported.
    """
    if suspended:
        return NormalizedAddonStatus(
            tenant=tenant, env=env, capability=capability, backend=backend,
            sync_state=SyncState.UNKNOWN, health_state=HealthState.PROGRESSING,
            desired_version=desired_version, applicable=True,
            native=native or {"suspended": True},
        )
    if ready is True:
        sync, health = SyncState.SYNCED, HealthState.HEALTHY
    elif ready is False:
        sync, health = SyncState.UNKNOWN, HealthState.DEGRADED
    else:
        sync, health = SyncState.UNKNOWN, HealthState.UNKNOWN
    return NormalizedAddonStatus(
        tenant=tenant,
        env=env,
        capability=capability,
        backend=backend,
        sync_state=sync,
        health_state=health,
        desired_version=desired_version,
        applicable=True,
        native=native or {"ready": ready, "reason": reason},
    )


def from_managed(
    *,
    tenant: str,
    env: str,
    capability: str,
    backend: str,
    healthy: bool | None = True,
    desired_version: str | None = None,
    native: dict[str, Any] | None = None,
) -> NormalizedAddonStatus:
    """
    Map a managed backend (no git-sync concept) onto the two axes.

    This is the `applicable=False` path the plan requires proving *before* any
    billable managed backend exists — a faked descriptor exercises the same code.
    """
    if healthy is True:
        health = HealthState.HEALTHY
    elif healthy is False:
        health = HealthState.DEGRADED
    else:
        health = HealthState.UNKNOWN
    return NormalizedAddonStatus(
        tenant=tenant,
        env=env,
        capability=capability,
        backend=backend,
        sync_state=SyncState.NOT_APPLICABLE,
        health_state=health,
        desired_version=desired_version,
        applicable=False,
        native=native or {"managed": True},
    )
