"""Simple in-memory circuit breaker for LLM provider failures."""
from __future__ import annotations

import asyncio
import time
from enum import Enum

from app.exceptions import QuizGenerationError


class State(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """Open after N consecutive failures; half-open after timeout."""

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout_seconds: float = 30.0,
        half_open_max_calls: int = 1,
    ) -> None:
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout_seconds
        self.half_open_max_calls = half_open_max_calls
        self._state = State.CLOSED
        self._failure_count = 0
        self._last_failure_time: float | None = None
        self._half_open_calls = 0
        self._lock = asyncio.Lock()

    @property
    def state(self) -> State:
        return self._state

    async def call(self, coro):
        """Execute coro if the circuit is closed, else raise."""
        await self._update_state()
        async with self._lock:
            if self._state == State.OPEN:
                raise QuizGenerationError(
                    "Circuit breaker is OPEN: LLM provider temporarily disabled.",
                    retryable=False,
                )
            if self._state == State.HALF_OPEN and self._half_open_calls >= self.half_open_max_calls:
                raise QuizGenerationError(
                    "Circuit breaker is HALF_OPEN and busy: try again shortly.",
                    retryable=False,
                )
            if self._state == State.HALF_OPEN:
                self._half_open_calls += 1

        try:
            result = await coro
            await self.record_success()
            return result
        except QuizGenerationError:
            await self.record_failure()
            raise

    async def record_success(self) -> None:
        async with self._lock:
            self._failure_count = 0
            self._last_failure_time = None
            self._half_open_calls = 0
            self._state = State.CLOSED

    async def record_failure(self) -> None:
        now = time.monotonic()
        async with self._lock:
            self._failure_count += 1
            self._last_failure_time = now
            if self._state == State.HALF_OPEN:
                self._state = State.OPEN
                self._half_open_calls = 0
            elif self._failure_count >= self.failure_threshold:
                self._state = State.OPEN

    async def _update_state(self) -> None:
        async with self._lock:
            if self._state != State.OPEN:
                return
            if self._last_failure_time is None:
                return
            if time.monotonic() - self._last_failure_time >= self.recovery_timeout:
                self._state = State.HALF_OPEN
                self._half_open_calls = 0

    async def reset(self) -> None:
        async with self._lock:
            self._state = State.CLOSED
            self._failure_count = 0
            self._last_failure_time = None
            self._half_open_calls = 0


# Singleton breaker for OpenAI calls.
_default_breaker: CircuitBreaker | None = None


def get_default_breaker() -> CircuitBreaker:
    global _default_breaker
    if _default_breaker is None:
        _default_breaker = CircuitBreaker()
    return _default_breaker
