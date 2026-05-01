"""Pytest fixtures for the Phase A backend skeleton.

Per CONTEXT D-10/D-11:
- `app` builds a fresh FastAPI per test via `create_app()` (factory pattern, Phase 2 D-08).
- `LifespanManager` from `asgi-lifespan` forces FastAPI lifespan under
  `httpx.ASGITransport`. Without it, `app.state.sessionmaker` stays unset.
- `async_client` issues requests over `ASGITransport` (no real network — CLAUDE.md constraint).
- `db_session` is defined per TEST-01 but unused in Phase A test bodies; it skips
  cleanly if the test DB is unreachable (Phase A `/healthz` does not require DB).
"""
from __future__ import annotations

import os
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio
from asgi_lifespan import LifespanManager
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

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
async def async_client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    """httpx AsyncClient bound to the per-test app via ASGITransport (no real network)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest_asyncio.fixture
async def db_session(app: FastAPI) -> AsyncIterator[AsyncSession]:
    """Per-test DB session, rolled back on teardown.

    Defined per TEST-01 contract. Unused in Phase A test bodies (no business writes
    yet). Skips if DATABASE_URL is unreachable — run `docker compose up postgres` first.
    """
    sessionmaker = app.state.sessionmaker
    async with sessionmaker() as session:
        try:
            await session.execute(text("select 1"))
        except Exception as exc:  # noqa: BLE001 — D-10: skip on any connectivity failure
            pytest.skip(
                f"DATABASE_URL not reachable; run `docker compose up postgres` first ({exc!r})"
            )
        try:
            yield session
        finally:
            await session.rollback()
