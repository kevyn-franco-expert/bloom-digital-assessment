"""Sliding-window rate limiter with Redis primary and in-memory fallback.

Limits requests per student_id to protect the LLM backend from bursts.
"""
from __future__ import annotations

import asyncio
import time
from collections import defaultdict
from typing import Any

import redis.asyncio as aioredis
from fastapi import HTTPException, status

from app import dependencies as app_dependencies


class InMemoryRateLimiter:
    """Thread-safe in-memory sliding-window rate limiter."""

    def __init__(self, limit: int, window_seconds: float) -> None:
        self.limit = limit
        self.window = window_seconds
        self._store: dict[str, list[float]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def is_allowed(self, key: str) -> bool:
        now = time.monotonic()
        async with self._lock:
            window_start = now - self.window
            # Keep only timestamps inside the window.
            self._store[key] = [ts for ts in self._store[key] if ts > window_start]
            if len(self._store[key]) >= self.limit:
                return False
            self._store[key].append(now)
            return True

    async def reset(self) -> None:
        async with self._lock:
            self._store.clear()


class RedisRateLimiter:
    """Redis-backed sliding-window rate limiter using sorted sets."""

    def __init__(self, redis: aioredis.Redis, limit: int, window_seconds: float) -> None:
        self.redis = redis
        self.limit = limit
        self.window = window_seconds

    async def is_allowed(self, key: str) -> bool:
        now = time.time()
        window_start = now - self.window
        pipe = self.redis.pipeline()
        pipe.zremrangebyscore(key, 0, window_start)
        pipe.zcard(key)
        pipe.zadd(key, {str(now): now})
        pipe.expire(key, int(self.window) + 1)
        _, current_count, _, _ = await pipe.execute()
        return current_count < self.limit

    async def reset(self) -> None:
        # Best-effort clear of known keys is not practical without scanning.
        # Tests use the in-memory fallback instead.
        pass


class RateLimiter:
    """Facade that selects Redis when available, otherwise in-memory."""

    def __init__(
        self,
        redis: aioredis.Redis | None = None,
        limit: int = 10,
        window_seconds: float = 60.0,
    ) -> None:
        if redis is not None:
            self._backend: Any = RedisRateLimiter(redis, limit, window_seconds)
        else:
            self._backend = InMemoryRateLimiter(limit, window_seconds)

    async def is_allowed(self, key: str) -> bool:
        return await self._backend.is_allowed(key)

    async def reset(self) -> None:
        await self._backend.reset()


# Singleton used by the API. Tests can reset it via fixture.
_default_limiter: RateLimiter | None = None


def get_default_limiter(redis: aioredis.Redis | None = None) -> RateLimiter:
    global _default_limiter
    if _default_limiter is None:
        _default_limiter = RateLimiter(redis=redis, limit=10, window_seconds=60.0)
    return _default_limiter


async def check_rate_limit(student_id: str) -> None:
    """Reject requests that exceed the per-student rate limit."""
    redis = await app_dependencies._get_redis_client()
    limiter = get_default_limiter(redis)
    allowed = await limiter.is_allowed(f"rate_limit:student:{student_id}")
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Please wait before requesting another quiz.",
        )
