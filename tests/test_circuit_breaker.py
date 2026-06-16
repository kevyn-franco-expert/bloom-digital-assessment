"""Tests for the circuit breaker."""
import pytest

from app.circuit_breaker import CircuitBreaker, State
from app.exceptions import QuizGenerationError


@pytest.mark.asyncio
async def test_circuit_breaker_opens_after_failures():
    breaker = CircuitBreaker(failure_threshold=2, recovery_timeout_seconds=60.0)

    async def fail():
        raise QuizGenerationError("boom", retryable=True)

    with pytest.raises(QuizGenerationError):
        await breaker.call(fail())
    with pytest.raises(QuizGenerationError):
        await breaker.call(fail())

    # Circuit should now be OPEN.
    assert breaker.state == State.OPEN
    with pytest.raises(QuizGenerationError) as exc_info:
        await breaker.call(fail())
    assert "Circuit breaker is OPEN" in str(exc_info.value)


@pytest.mark.asyncio
async def test_circuit_breaker_closes_on_success():
    breaker = CircuitBreaker(failure_threshold=2, recovery_timeout_seconds=60.0)

    async def ok():
        return "success"

    result = await breaker.call(ok())
    assert result == "success"
    assert breaker.state == State.CLOSED
