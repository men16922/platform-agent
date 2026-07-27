"""
Per-tenant rate limiting — the noisy-neighbour axis the quotas never covered.

Capsule's ResourceQuota bounds what a tenant can *hold* (cpu, memory, pods).
Nothing bounded what a tenant can *do*. On a shared control plane that is a real
gap: agent tool calls and model inference all funnel through single instances,
and one tenant looping a remediation can starve every other tenant without
exceeding a single Kubernetes quota. The GCP multi-tenant guide names this
directly — quota enforcement has to sit in front of the shared endpoint, not
inside the cluster the endpoint acts on.

Design choices worth stating, because each has a wrong-looking alternative:

**Limits come from the registry**, not from a new config file. The registry is
already the source of truth for what a tenant is allowed (isolation tier,
namespaces, quota), and a second place to declare tenant policy is a second
place for it to drift. An unset limit means *unlimited*, which is what every
tenant has today — this must be additive or it is an outage.

**Refuse, do not queue.** A queue converts one tenant's flood into everyone's
latency, which is the failure this exists to prevent, and it hides the flood.
A refusal is attributable and the caller can back off.

**Sliding window, not fixed buckets.** Fixed buckets let a caller spend the
whole budget in the last instant of one window and again in the first instant of
the next — a 2x burst at the boundary, arriving exactly when a retry storm
aligns everyone's clocks.

**The clock is injected.** Wall-clock in a limiter makes tests either slow or
flaky, and the interesting behaviour is entirely about time.
"""

from __future__ import annotations

import threading
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Any, Callable


class RateLimitExceeded(RuntimeError):
    """Raised when a tenant is over its declared budget for the window."""

    def __init__(self, tenant: str, limit: int, window_sec: float, action: str = ""):
        self.tenant = tenant
        self.limit = limit
        self.window_sec = window_sec
        subject = f" for {action!r}" if action else ""
        super().__init__(
            f"tenant {tenant!r} exceeded its budget{subject}: {limit} calls per "
            f"{window_sec:g}s. Refused rather than queued — queuing would turn one "
            f"tenant's flood into every tenant's latency."
        )


@dataclass
class TenantRateLimiter:
    """Sliding-window call budget, keyed by tenant.

    ``limits`` maps tenant name -> calls allowed per ``window_sec``. A tenant
    absent from the map is unlimited, so adding this to a running system changes
    nothing until a limit is actually declared.
    """

    limits: dict[str, int]
    window_sec: float = 60.0
    clock: Callable[[], float] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.clock is None:
            import time

            self.clock = time.monotonic
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        # Two agents sharing one gateway is the normal case, and a lost
        # increment is a tenant getting more than its budget.
        self._lock = threading.Lock()

    @classmethod
    def from_registry(cls, registry: Any, *, window_sec: float = 60.0,
                      clock: Callable[[], float] | None = None) -> "TenantRateLimiter":
        """Read declared budgets off the tenant registry.

        Tenants without ``quota.calls_per_min`` are simply absent from the map,
        which is how this stays additive.
        """
        limits: dict[str, int] = {}
        for name, tenant in (getattr(registry, "tenants", None) or {}).items():
            declared = getattr(getattr(tenant, "quota", None), "calls_per_min", None)
            if isinstance(declared, int) and declared > 0:
                limits[name] = declared
        kwargs: dict[str, Any] = {"limits": limits, "window_sec": window_sec}
        if clock is not None:
            kwargs["clock"] = clock
        return cls(**kwargs)

    def remaining(self, tenant: str) -> int | None:
        """Calls left in the current window, or None when unlimited."""
        limit = self.limits.get(tenant)
        if limit is None:
            return None
        with self._lock:
            return max(0, limit - len(self._prune(tenant)))

    def check(self, tenant: str, *, action: str = "") -> None:
        """Record one call for ``tenant``; raise if that puts it over budget.

        Records and checks under one lock: doing them separately lets two
        concurrent callers both observe room and both proceed.
        """
        limit = self.limits.get(tenant)
        if limit is None:
            return
        with self._lock:
            hits = self._prune(tenant)
            if len(hits) >= limit:
                raise RateLimitExceeded(tenant, limit, self.window_sec, action)
            hits.append(self.clock())

    def _prune(self, tenant: str) -> deque[float]:
        """Drop hits that have aged out. Caller holds the lock."""
        hits = self._hits[tenant]
        cutoff = self.clock() - self.window_sec
        while hits and hits[0] <= cutoff:
            hits.popleft()
        return hits
