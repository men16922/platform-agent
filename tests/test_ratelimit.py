"""
Guards for per-tenant call budgets.

Capsule quotas bound what a tenant can *hold*. Nothing bounded what it can *do*,
so one tenant looping a remediation could starve every other tenant through the
shared control plane without exceeding a single Kubernetes quota.

The properties that matter here are all about *time* and *default*, and both are
easy to get subtly wrong:

  - unset limit must mean unlimited, or switching this on is an outage
  - the window must slide, or a caller gets 2x its budget at the boundary
  - one tenant's exhaustion must not touch another's budget
"""

from __future__ import annotations

import pytest

from src.agents.platform.ratelimit import RateLimitExceeded, TenantRateLimiter


class _Clock:
    """Injected time. A limiter tested against wall-clock is slow or flaky."""

    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


@pytest.fixture
def clock():
    return _Clock()


class TestDefaultIsUnlimited:
    def test_tenant_without_a_declared_limit_is_never_refused(self, clock):
        limiter = TenantRateLimiter(limits={}, window_sec=60, clock=clock)
        for _ in range(1000):
            limiter.check("acme")
        assert limiter.remaining("acme") is None, "None means unlimited, not zero"

    def test_registry_without_calls_per_min_declares_nothing(self):
        """Additive by construction: today's registry must produce an empty map."""
        from src.agents.platform.registry import load_registry

        limiter = TenantRateLimiter.from_registry(load_registry())
        assert limiter.limits == {}


class TestBudgetEnforcement:
    def test_calls_up_to_the_limit_pass_and_the_next_is_refused(self, clock):
        limiter = TenantRateLimiter(limits={"acme": 3}, window_sec=60, clock=clock)
        for _ in range(3):
            limiter.check("acme")
        assert limiter.remaining("acme") == 0
        with pytest.raises(RateLimitExceeded) as exc:
            limiter.check("acme", action="kubectl_get")
        assert "acme" in str(exc.value) and "kubectl_get" in str(exc.value)

    def test_a_refused_call_is_not_counted_against_the_budget(self, clock):
        """
        Otherwise a caller that keeps retrying can never recover: each refusal
        would push its own lockout further out, turning a burst into a permanent
        outage for that tenant — and retrying is exactly what a rate-limited
        client does.

        The clock advances *between* retries on purpose. An earlier version of
        this test retried at a frozen instant, so the refusals aged out together
        with the real call and it passed against a limiter that did count them —
        it asserted nothing. Verified by injecting that defect and watching this
        fail.
        """
        limiter = TenantRateLimiter(limits={"acme": 1}, window_sec=60, clock=clock)
        limiter.check("acme")  # the one real call, at t=0

        for _ in range(5):
            clock.advance(5)  # retries spread across the window
            with pytest.raises(RateLimitExceeded):
                limiter.check("acme")

        # t=+61: the real call has aged out. The refusals (t=+5..+25) have not,
        # so a limiter that recorded them would still be refusing here.
        clock.advance(36)
        limiter.check("acme")

    def test_one_tenant_exhausting_its_budget_does_not_touch_a_neighbour(self, clock):
        limiter = TenantRateLimiter(limits={"acme": 1, "globex": 1}, window_sec=60, clock=clock)
        limiter.check("acme")
        with pytest.raises(RateLimitExceeded):
            limiter.check("acme")
        limiter.check("globex")  # the whole point
        assert limiter.remaining("globex") == 0


class TestWindowSlides:
    def test_budget_recovers_gradually_not_all_at_once(self, clock):
        limiter = TenantRateLimiter(limits={"acme": 2}, window_sec=60, clock=clock)
        limiter.check("acme")
        clock.advance(30)
        limiter.check("acme")
        assert limiter.remaining("acme") == 0

        # 31s later the FIRST hit has aged out but the second has not.
        clock.advance(31)
        assert limiter.remaining("acme") == 1, "fixed buckets would restore both"
        limiter.check("acme")
        with pytest.raises(RateLimitExceeded):
            limiter.check("acme")

    def test_no_double_budget_at_the_window_boundary(self, clock):
        """
        The failure a fixed bucket has: spend the budget at the end of one
        window and again at the start of the next, for 2x in an instant —
        arriving exactly when a retry storm has aligned everyone's clocks.
        """
        limiter = TenantRateLimiter(limits={"2": 2}, window_sec=60, clock=clock)
        clock.advance(59)
        limiter.check("2")
        limiter.check("2")
        clock.advance(1.0)  # a fixed bucket would roll over here
        with pytest.raises(RateLimitExceeded):
            limiter.check("2")


class TestGatewayIntegration:
    def test_over_budget_tool_call_is_refused_before_the_boundary_check(self, monkeypatch):
        """
        Budget is checked before the namespace gate, so an over-budget tenant is
        refused whether or not the namespace would have been allowed — and a
        flooding caller does not get the boundary computed for it each time.
        """
        from src.agents.ai.gateway.mcp_server import MCPServer
        from src.agents.platform.scope import IncidentScope

        ran: list = []
        monkeypatch.setattr(
            "src.agents.ai.gateway.mcp_server.subprocess.run",
            lambda *a, **k: ran.append(a) or type("P", (), {"returncode": 0, "stdout": "{}", "stderr": ""})(),
        )
        scope = IncidentScope(
            tenant="acme", env="dev", kubeconfig_path="/tmp/k",
            allowed_namespaces=("acme-dev-logging",),
        )
        gw = MCPServer(scope=scope, rate_limiter=TenantRateLimiter(limits={"acme": 1}))
        args = {"resource": "pods", "namespace": "acme-dev-logging"}

        assert gw.call_tool("kubectl_get", args).success is True
        second = gw.call_tool("kubectl_get", args)
        assert second.success is False
        assert "exceeded its budget" in (second.error or "")
        assert len(ran) == 1, "the refused call must not reach kubectl"

    def test_no_limiter_means_no_change(self, monkeypatch):
        from src.agents.ai.gateway.mcp_server import MCPServer
        from src.agents.platform.scope import IncidentScope

        monkeypatch.setattr(
            "src.agents.ai.gateway.mcp_server.subprocess.run",
            lambda *a, **k: type("P", (), {"returncode": 0, "stdout": "{}", "stderr": ""})(),
        )
        gw = MCPServer(scope=IncidentScope(tenant="acme", env="dev", kubeconfig_path="/tmp/k"))
        for _ in range(20):
            assert gw.call_tool("kubectl_get", {"resource": "pods"}).success is True
