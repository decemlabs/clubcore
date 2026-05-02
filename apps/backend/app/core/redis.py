"""Redis client lifespan + per-request dependency (D-08).

Mirrors `app.core.database.db_lifespan` / `get_db`: a process-singleton client
bound to `app.state.redis` for the lifetime of the FastAPI app. Phase 5 sessions,
rate-limit, and refresh-rotation race window all read this single client.

`decode_responses=True` — Phase 5 service code deals in `str` not `bytes`. SET / GET / SADD /
SMEMBERS / pipeline operations expect text values throughout.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from redis.asyncio import Redis, from_url

from app.core.config import get_settings


@asynccontextmanager
async def redis_lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Open a Redis connection pool on startup, dispose on shutdown.

    Composes alongside `db_lifespan` via a `combined_lifespan` chain in `app.main`
    (D-08): both touch `app.state`, so they are wrapped in a single
    `@asynccontextmanager` that enters both contexts.
    """
    settings = get_settings()
    client: Redis = from_url(  # type: ignore[no-untyped-call]
        str(settings.redis_url),
        decode_responses=True,
        encoding="utf-8",
    )
    app.state.redis = client
    try:
        yield
    finally:
        await client.aclose()


def get_redis(request: Request) -> Redis:
    """Per-request Redis client — resolves to the singleton on app.state.redis."""
    client: Redis = request.app.state.redis
    return client
