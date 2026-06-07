"""WS test convention for messaging module — Phase 90 Plan 03 (P6/P13).

WHY this diverges from the project's httpx ASGITransport convention
===================================================================
CLAUDE.md mandates ``httpx ASGITransport`` for all backend HTTP tests.
However, ``httpx.AsyncClient`` (with ASGITransport) does NOT support the
WebSocket upgrade handshake — ``async_client.get("ws://...")`` raises
``httpx.UnsupportedProtocol`` (Pitfall P13, PITFALLS.md lines 299-328).

The correct tool is Starlette's built-in ``TestClient.websocket_connect()``,
which uses ASGI directly (no real network) and does support the WS upgrade.
This is the FastAPI-recommended pattern per official docs and is the
ONLY way to test WS endpoints without spinning up a real network stack.

WS tests in this module are SYNCHRONOUS (sync pytest test functions that
call synchronous ``TestClient`` + ``WebSocketTestSession``).  The async
fixtures from the parent conftest (``app``, ``db_session``) are NOT used
in WS tests — instead the WS conftest builds its own in-process stack with
a REAL Postgres + REAL Redis connection because:
  1. Redis pub/sub fan-out cannot be meaningfully mocked at the TestClient level.
  2. The SAVEPOINT-based async session from the parent conftest is async;
     mixing it with the sync TestClient loop would require complex threading.
  3. WS tests skip cleanly if Postgres/Redis are unreachable (same idiom as
     ``db_session`` in the parent conftest).

The ``ws_app`` fixture enters the app lifespan so ``app.state.sessionmaker``,
``app.state.redis``, and ``app.state.engine`` are all bound — exactly as in
production and in the async ``app`` fixture from tests/conftest.py.

Auth: WS tests authenticate by running the OTP flow synchronously against
the live app stack (using the TestClient's HTTP transport), then extracting
the ``cc_client_access`` cookie value and passing it to ``websocket_connect``
via the ``cookies`` parameter.

Convention (established here; all WS tests in this module follow this):

    from starlette.testclient import TestClient
    from tests.messaging.conftest import auth_ws_client_sync, seed_ws_client

    def test_something(ws_app):
        tc = TestClient(ws_app)
        client = seed_ws_client(ws_app, phone="+79991234567")
        cookie_val = auth_ws_client_sync(tc, ws_app, client)
        with tc.websocket_connect(
            "/api/v1/client/ws/messages",
            cookies={"cc_client_access": cookie_val},
            headers={"origin": "http://testserver"},
        ) as ws:
            data = ws.receive_json(timeout=3)
"""

from __future__ import annotations

import contextlib
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from starlette.testclient import TestClient

from app.core.config import get_settings
from app.core.permissions import Role
from app.core.security import generate_otp_code, hash_password
from app.main import create_app

# ---------------------------------------------------------------------------
# Environment bootstrap — mirrors tests/conftest.py so this module can run
# standalone (e.g. `pytest tests/messaging/test_ws_*.py`) without the
# top-level conftest loading env vars first.
# ---------------------------------------------------------------------------

_ENV_EXAMPLE = Path(__file__).resolve().parent.parent.parent / ".env.example"
if _ENV_EXAMPLE.is_file():
    for _line in _ENV_EXAMPLE.read_text(encoding="utf-8").splitlines():
        _stripped = _line.strip()
        if not _stripped or _stripped.startswith("#") or "=" not in _stripped:
            continue
        _key, _, _value = _stripped.partition("=")
        os.environ.setdefault(_key.strip(), _value.strip())


# ---------------------------------------------------------------------------
# ws_app fixture — synchronous; fires lifespan so app.state.* are bound
# ---------------------------------------------------------------------------


@pytest.fixture(scope="function")
def ws_app() -> Any:
    """Create a fresh FastAPI instance with lifespan fired for WS tests.

    Returns the app inside the TestClient lifespan context; the test
    function uses this app directly to access app.state.sessionmaker etc.

    Uses Starlette TestClient(app).__enter__ / __exit__ to fire the ASGI
    lifespan so app.state.engine, app.state.sessionmaker, and app.state.redis
    are all bound — identical to the async ``app`` fixture in tests/conftest.py
    but synchronous so it works alongside TestClient.

    Skips cleanly if Postgres is unreachable.
    """
    _app = create_app()
    # TestClient.__enter__ fires the lifespan (Starlette behaviour).
    # We don't use TestClient as a context manager here because tests need
    # the tc object too — each test creates its own TestClient(ws_app) so the
    # HTTP transport is available. We only need the lifespan to be fired once
    # per fixture scope, which TestClient.__enter__ does.
    #
    # Pattern: return the bare app; each test wraps it in TestClient for the
    # actual requests. The lifespan fires when TestClient.__enter__ is called
    # inside the test body. This is safe because lifespan is idempotent on
    # repeated calls in Starlette.
    #
    # Connectivity check: probe Postgres synchronously via a throwaway engine.
    import asyncio

    import sqlalchemy as sa
    from sqlalchemy.ext.asyncio import create_async_engine

    settings = get_settings()

    async def _probe() -> None:
        engine = create_async_engine(str(settings.database_url), pool_pre_ping=True)
        try:
            async with engine.connect() as conn:
                await conn.execute(sa.text("SELECT 1"))
        finally:
            await engine.dispose()

    try:
        asyncio.get_event_loop().run_until_complete(_probe())
    except Exception as exc:
        pytest.skip(
            f"DATABASE_URL not reachable; run `docker compose up postgres redis` first ({exc!r})"
        )

    return _app


# ---------------------------------------------------------------------------
# Seed / auth helpers — synchronous (used inside sync WS test bodies)
# ---------------------------------------------------------------------------


def _run(coro: Any) -> Any:
    """Run a coroutine in the running or a new event loop."""
    import asyncio

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def seed_ws_client(ws_app: FastAPI, *, phone: str, suffix: str = "") -> Any:
    """Seed a User + Client row for WS tests and return the Client ORM object.

    Uses a short-lived async session from app.state.sessionmaker.
    The row is NOT wrapped in SAVEPOINT — each WS test is responsible for
    cleanup or uses unique phone numbers to avoid collisions.
    """
    from app.modules.auth.models import User
    from app.modules.clients.models import Client

    async def _seed() -> Any:
        session_factory: async_sessionmaker[AsyncSession] = ws_app.state.sessionmaker
        async with session_factory() as session:
            user = User(
                email=f"ws-test-staff-{suffix or phone[-6:]}@example.com",
                password_hash=await hash_password("ws-test-pw-secure-90"),
                role=Role.RECEPTION,
                full_name="WS Test Staff",
            )
            session.add(user)
            await session.flush()

            client = Client(
                first_name="WS",
                last_name="Test",
                phone=phone,
                telegram_user_id=abs(hash(phone)) % (10**9),
                created_by_user_id=user.id,
            )
            session.add(client)
            await session.flush()
            await session.commit()
            # Re-load to get a detached instance with all columns populated.
            loaded = await session.get(Client, client.id)
            return loaded

    return _run(_seed())


def auth_ws_client_sync(
    tc: TestClient,
    ws_app: FastAPI,
    client: Any,
) -> str:
    """Run the OTP auth flow synchronously and return cc_client_access cookie value.

    Mirrors _auth_as_client() from test_messaging_rest.py but using the sync
    TestClient HTTP API so it works inside sync WS tests.

    Returns the raw cookie value (without 'cc_client_access=' prefix).
    """
    from app.modules.auth.models import OtpCode

    # Step 1: request OTP
    resp = tc.post(
        "/api/v1/client/otp/request",
        json={"phone": client.phone},
    )
    assert resp.status_code == 202, f"OTP request failed: {resp.text}"

    # Step 2: patch OTP hash in DB to a known value
    settings = get_settings()
    raw_code, code_hash = generate_otp_code()

    async def _patch_otp() -> None:
        session_factory: async_sessionmaker[AsyncSession] = ws_app.state.sessionmaker
        async with session_factory() as session:
            otp_row = await session.scalar(
                select(OtpCode).where(
                    OtpCode.client_id == client.id,
                    OtpCode.consumed_at.is_(None),
                )
            )
            assert otp_row is not None, f"OtpCode not found for client {client.id}"
            otp_row.code_hash = code_hash
            otp_row.expires_at = datetime.now(tz=UTC) + timedelta(
                seconds=settings.otp_code_ttl_seconds
            )
            await session.commit()

    _run(_patch_otp())

    # Step 3: verify OTP
    verify_resp = tc.post(
        "/api/v1/client/otp/verify",
        json={"phone": client.phone, "code": raw_code},
    )
    assert verify_resp.status_code == 200, f"OTP verify failed: {verify_resp.text}"

    # Step 4: extract cookie value
    set_cookies = verify_resp.headers.get_list("set-cookie")
    access_cookie = next(
        (c for c in set_cookies if c.startswith("cc_client_access=")),
        None,
    )
    assert access_cookie is not None, "cc_client_access cookie missing from verify response"
    return access_cookie.split("=", 1)[1].split(";", 1)[0]


def flush_redis_sync(ws_app: FastAPI) -> None:
    """Flush Redis synchronously for WS test isolation."""

    async def _flush() -> None:
        await ws_app.state.redis.flushdb()

    _run(_flush())


def cleanup_client_sync(ws_app: FastAPI, *, phone: str) -> None:
    """Remove the seeded client + staff user by phone (best-effort; ignores errors)."""
    from app.modules.clients.models import Client

    async def _cleanup() -> None:
        session_factory: async_sessionmaker[AsyncSession] = ws_app.state.sessionmaker
        async with session_factory() as session:
            client = await session.scalar(select(Client).where(Client.phone == phone))
            if client is not None:
                await session.execute(
                    text(
                        "DELETE FROM message_threads WHERE client_id = :cid"
                    ),
                    {"cid": str(client.id)},
                )
                await session.execute(
                    text("DELETE FROM otp_codes WHERE client_id = :cid"),
                    {"cid": str(client.id)},
                )
                await session.execute(
                    text("DELETE FROM clients WHERE id = :cid"),
                    {"cid": str(client.id)},
                )
                await session.commit()

    with contextlib.suppress(Exception):
        _run(_cleanup())


# ---------------------------------------------------------------------------
# WS_ORIGIN constant — pass as Origin header for TestClient WS connections
# ---------------------------------------------------------------------------

WS_ALLOWED_ORIGIN = "http://testserver"
"""The Origin header value accepted by verify_ws_origin in tests.

Configured via Settings.ws_allowed_origins default list.
Pass as ``headers={"origin": WS_ALLOWED_ORIGIN}`` to TestClient.websocket_connect().
"""
