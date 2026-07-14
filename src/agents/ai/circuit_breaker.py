"""Circuit breaker for flaky external dependencies (ref AWSome AI Gateway resilience).

Wrap a call to an external dep (Slack, DynamoDB, a remote MCP). After
``failure_threshold`` consecutive failures the breaker OPENs and further calls
fail fast — returning a ``fallback`` if given, else raising ``CircuitOpenError``
— instead of hanging or cascading. After ``reset_timeout`` seconds it HALF-OPENs
to probe recovery; a success closes it, a failure re-opens it.

Pure Python; the clock is injectable so the state machine is deterministically
testable.
"""

from __future__ import annotations

import time
from enum import Enum
from typing import Any, Callable

_UNSET = object()


class State(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitOpenError(RuntimeError):
    """Raised when a call is short-circuited because the breaker is open."""


class CircuitBreaker:
    def __init__(
        self,
        *,
        failure_threshold: int = 3,
        reset_timeout: float = 30.0,
        name: str = "circuit",
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self.name = name
        self._clock = clock
        self._failures = 0
        self._state = State.CLOSED
        self._opened_at = 0.0

    @property
    def state(self) -> State:
        # Lazily transition OPEN → HALF_OPEN once the cooldown has elapsed.
        if self._state is State.OPEN and (self._clock() - self._opened_at) >= self.reset_timeout:
            self._state = State.HALF_OPEN
        return self._state

    def call(self, fn: Callable[..., Any], *args: Any, fallback: Any = _UNSET, **kwargs: Any) -> Any:
        if self.state is State.OPEN:
            if fallback is not _UNSET:
                return fallback
            raise CircuitOpenError(f"circuit '{self.name}' is open")
        try:
            result = fn(*args, **kwargs)
        except Exception:
            self._on_failure()
            if fallback is not _UNSET:
                return fallback
            raise
        self._on_success()
        return result

    def _on_success(self) -> None:
        self._failures = 0
        self._state = State.CLOSED

    def _on_failure(self) -> None:
        self._failures += 1
        if self._failures >= self.failure_threshold:
            self._state = State.OPEN
            self._opened_at = self._clock()
