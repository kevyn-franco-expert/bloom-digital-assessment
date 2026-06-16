"""Tests for the rate limiter."""
import pytest

from app.rate_limit import InMemoryRateLimiter


@pytest.mark.asyncio
async def test_in_memory_rate_limiter_allows_under_limit():
    limiter = InMemoryRateLimiter(limit=3, window_seconds=60.0)
    assert await limiter.is_allowed("student-a")
    assert await limiter.is_allowed("student-a")
    assert await limiter.is_allowed("student-a")


@pytest.mark.asyncio
async def test_in_memory_rate_limiter_blocks_over_limit():
    limiter = InMemoryRateLimiter(limit=2, window_seconds=60.0)
    assert await limiter.is_allowed("student-b")
    assert await limiter.is_allowed("student-b")
    assert not await limiter.is_allowed("student-b")


@pytest.mark.asyncio
async def test_in_memory_rate_limiter_resets():
    limiter = InMemoryRateLimiter(limit=1, window_seconds=60.0)
    assert await limiter.is_allowed("student-c")
    assert not await limiter.is_allowed("student-c")
    await limiter.reset()
    assert await limiter.is_allowed("student-c")
