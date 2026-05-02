"""Pytest fixtures for the Phase A backend skeleton.

Per CONTEXT D-10/D-11:
- `app` builds a fresh FastAPI per test via `create_app()` (factory pattern, Phase 2 D-08).
- `LifespanManager` from `asgi-lifespan` forces FastAPI lifespan under
  `httpx.ASGITransport`. Without it, `app.state.sessionmaker` stays unset.
- `async_client` issues requests over `ASGITransport` (no real network — CLAUDE.md constraint).
- `db_session` is defined per TEST-01: SAVEPOINT-based per-test rollback (Phase 5 D-22).
  Service-level `session.commit()` calls become nested SAVEPOINTs that the outer
  rollback wipes on teardown — guarantees a clean DB across tests even when service
  bodies issue real commits.
"""
from __future__ import annotations

import os
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import pytest
import pytest_asyncio
from asgi_lifespan import LifespanManager
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.database import get_db
from app.core.redis import get_redis
from app.main import create_app

# Phase 2 D-15 Settings requires DATABASE_URL/REDIS_URL/SECRET_KEY from env or .env.
# CI / fresh checkouts run without `.env`; load `.env.example` defaults at import
# time so Settings() in `create_app()` does not fail before any test executes.
# This is a test-only fallback; production runs under `cp .env.example .env`
# (README D-09 quick-start) or container env vars (compose `env_file: .env`).
_ENV_EXAMPLE = Path(__file__).resolve().parent.parent / ".env.example"
if _ENV_EXAMPLE.is_file():
    for _line in _ENV_EXAMPLE.read_text(encoding="utf-8").splitlines():
        _stripped = _line.strip()
        if not _stripped or _stripped.startswith("#") or "=" not in _stripped:
            continue
        _key, _, _value = _stripped.partition("=")
        os.environ.setdefault(_key.strip(), _value.strip())


@pytest_asyncio.fixture
async def app() -> AsyncIterator[FastAPI]:
    """Per-test FastAPI instance with lifespan fired (engine + sessionmaker bound)."""
    _app = create_app()
    async with LifespanManager(_app):
        yield _app


@pytest_asyncio.fixture
async def db_session(app: FastAPI) -> AsyncIterator[AsyncSession]:
    """SAVEPOINT-based per-test rollback against a real Postgres (D-22, TEST-01).

    Pattern (SQLAlchemy 2.0 cookbook "Joining a session into an external
    transaction"):
      1. Open a connection from the engine.
      2. BEGIN an outer transaction on that connection.
      3. Bind an AsyncSession with join_transaction_mode='create_savepoint'
         so service-level session.commit() calls become nested SAVEPOINTs.
      4. Yield the session to the test.
      5. ROLLBACK the outer transaction on teardown — wipes every write
         the test made, even ones a service body claimed to commit.

    Skips cleanly if compose Postgres is unreachable (Phase 3 conftest idiom
    preserved).
    """
    engine = app.state.engine

    try:
        connection = await engine.connect()
    except Exception as exc:  # noqa: BLE001 — D-10: skip on any connectivity failure
        pytest.skip(
            f"DATABASE_URL not reachable; run "
            f"`docker compose up postgres` first ({exc!r})"
        )

    try:
        try:
            trans = await connection.begin()
        except Exception as exc:  # noqa: BLE001 — D-10: skip on any connectivity failure
            await connection.close()
            pytest.skip(
                f"DATABASE_URL not reachable; run "
                f"`docker compose up postgres` first ({exc!r})"
            )

        # Connectivity probe runs INSIDE the outer transaction so it does not
        # autobegin a competing transaction on the same connection.
        await connection.execute(text("select 1"))

        session_local = async_sessionmaker(
            bind=connection,
            expire_on_commit=False,
            class_=AsyncSession,
            join_transaction_mode="create_savepoint",
        )
        async with session_local() as session:
            try:
                yield session
            finally:
                await trans.rollback()
    finally:
        await connection.close()


@pytest_asyncio.fixture
async def async_client(
    app: FastAPI,
    db_session: AsyncSession,
) -> AsyncIterator[AsyncClient]:
    """httpx AsyncClient bound to the per-test app via ASGITransport (no real network).

    Installs FastAPI dependency overrides so that service code reached through
    the ASGI transport sees the SAVEPOINT-wrapped session (D-22) and the same
    Redis client `app.state.redis` the test fixtures flush. Without the
    override, get_db would yield a fresh session from app.state.sessionmaker —
    a different connection, so under Postgres READ COMMITTED isolation the
    seeded test data is invisible to the route handler.
    """

    async def _override_get_db() -> AsyncIterator[AsyncSession]:
        yield db_session

    def _override_get_redis() -> Any:
        # Mirrors app.core.redis.get_redis: returns the process-singleton
        # client bound on app.state.redis (no per-request connection).
        return app.state.redis

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_redis] = _override_get_redis

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client
    finally:
        app.dependency_overrides.clear()
