"""Redis connection management."""
from __future__ import annotations

import redis.asyncio as aioredis

from app.core.config import get_settings

_redis: aioredis.Redis | None = None


async def connect_redis() -> None:
    global _redis
    settings = get_settings()
    _redis = aioredis.from_url(settings.redis_url, decode_responses=True, socket_connect_timeout=2)
    await _redis.ping()


async def close_redis() -> None:
    global _redis
    if _redis:
        await _redis.aclose()
        _redis = None


def get_redis() -> aioredis.Redis:
    if _redis is None:
        raise RuntimeError("Redis not initialised. Call connect_redis() first.")
    return _redis
