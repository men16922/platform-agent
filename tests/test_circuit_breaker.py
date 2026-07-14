import pytest

from src.agents.ai.circuit_breaker import CircuitBreaker, CircuitOpenError, State


class _Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


def _ok():
    return "ok"


def _boom():
    raise RuntimeError("dep down")


def test_closed_passes_through():
    cb = CircuitBreaker(failure_threshold=3)
    assert cb.call(_ok) == "ok"
    assert cb.state is State.CLOSED


def test_opens_after_threshold_failures():
    cb = CircuitBreaker(failure_threshold=3)
    for _ in range(3):
        with pytest.raises(RuntimeError):
            cb.call(_boom)
    assert cb.state is State.OPEN
    # now short-circuits without calling
    with pytest.raises(CircuitOpenError):
        cb.call(_ok)


def test_fallback_on_open_and_on_failure():
    cb = CircuitBreaker(failure_threshold=1)
    # first failure returns fallback and opens
    assert cb.call(_boom, fallback="fb") == "fb"
    assert cb.state is State.OPEN
    # open state also returns fallback (never calls fn)
    assert cb.call(_ok, fallback="fb") == "fb"


def test_half_open_after_timeout_then_closes_on_success():
    clock = _Clock()
    cb = CircuitBreaker(failure_threshold=2, reset_timeout=30.0, clock=clock)
    for _ in range(2):
        with pytest.raises(RuntimeError):
            cb.call(_boom)
    assert cb.state is State.OPEN
    clock.t = 31.0  # cooldown elapsed
    assert cb.state is State.HALF_OPEN
    assert cb.call(_ok) == "ok"  # probe succeeds
    assert cb.state is State.CLOSED


def test_half_open_failure_reopens():
    clock = _Clock()
    cb = CircuitBreaker(failure_threshold=1, reset_timeout=10.0, clock=clock)
    with pytest.raises(RuntimeError):
        cb.call(_boom)
    assert cb.state is State.OPEN
    clock.t = 11.0
    assert cb.state is State.HALF_OPEN
    with pytest.raises(RuntimeError):
        cb.call(_boom)  # probe fails
    assert cb.state is State.OPEN


def test_success_resets_failure_count():
    cb = CircuitBreaker(failure_threshold=3)
    with pytest.raises(RuntimeError):
        cb.call(_boom)
    cb.call(_ok)  # resets counter
    with pytest.raises(RuntimeError):
        cb.call(_boom)
    assert cb.state is State.CLOSED  # only 1 consecutive failure, not 3
