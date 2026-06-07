"""WS test convention for messaging module -- Phase 90 Plan 03 (P6/P13).

WHY this diverges from the project's httpx ASGITransport convention
===================================================================
CLAUDE.md mandates ``httpx ASGITransport`` for all backend HTTP tests.
However, ``httpx.AsyncClient`` (with ASGITransport) does NOT support the
WebSocket upgrade handshake -- calling ``async_client.get("ws://...")``
raises ``httpx.UnsupportedProtocol`` (Pitfall P13, PITFALLS.md lines 299-328).

The correct tool is Starlette's built-in ``TestClient.websocket_connect()``,
which uses ASGI directly (no real network) and does support the WS upgrade.
This is the FastAPI-recommended pattern per official docs and is the
ONLY way to test WS endpoints without spinning up a real network stack.

WS tests in this module are SYNCHRONOUS (sync pytest test functions that
call synchronous ``TestClient`` + ``WebSocketTestSession``).  The async
fixtures from the parent conftest (``app``, ``db_session``) are NOT used
in WS tests -- instead the WS conftest builds its own in-process stack with
a REAL Postgres + REAL Redis connection because:
  1. Redis pub/sub fan-out cannot be meaningfully mocked at the TestClient level.
  2. The SAVEPOINT-based async session from the parent conftest is async;
     mixing it with the sync TestClient loop would require complex threading.
  3. WS tests skip cleanly if Postgres/Redis are unreachable (same idiom as
     ``db_session`` in the parent conftest).

The ``ws_tc`` fixture yields a ``TestClient`` with the lifespan active so
``ws_tc.app.state.sessionmaker``, ``ws_tc.app.state.redis``, and
``ws_tc.app.state.engine`` are all bound -- exactly as in production and in
the async ``app`` fixture from tests/conftest.py but synchronous so it
works alongside TestClient.

Auth: WS tests authenticate by running the OTP flow synchronously against
the live app stack (using the TestClient's HTTP transport), then extracting
the ``cc_client_access`` cookie value and passing it to ``websocket_connect``
via the ``cookies`` parameter.

Convention (established here; all WS tests in this module follow this):

    from tests.messaging.conftest import auth_ws_client_sync, seed_ws_client

    def test_something(ws_tc):
        client = seed_ws_client(ws_tc, phone="+79991234567")
        cookie_val = auth_ws_client_sync(ws_tc, client)
        with ws_tc.websocket_connect(
            "/api/v1/client/ws/messages",
            cookies={"cc_client_access": cookie_val},
            headers={"origin": WS_ALLOWED_ORIGIN},
        ) as ws:
            data = ws.receive_json(timeout=3)

Important -- run async operations through ws_tc.portal.call(coro) not asyncio.run():
The TestClient manages an anyio BlockingPortal in a background thread.
All async work (DB seeding, Redis flush, OTP patching) MUST run through that same
portal so they share the same event loop and SQLAlchemy pool as the lifespan.
Using asyncio.run() creates a separate event loop which causes pool/connection leaks
and ResourceWarning failures at test teardown.
"""

from __future__ import annotations

import asyncio
import contextlib
import os
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from starlette.testclient import TestClient

from app.core.config import get_settings
from app.core.permissions import Role
from app.core.security import generate_otp_code, hash_password
from app.main import create_app

# ---------------------------------------------------------------------------
# Environment bootstrap -- mirrors tests/conftest.py so this module can run
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
# ws_tc fixture -- yields a TestClient with lifespan active
# ---------------------------------------------------------------------------


@pytest.fixture(scope="function")
def ws_tc() -> Generator[TestClient, None, None]:
    """Yield a Starlette TestClient with the ASGI lifespan active.

    The lifespan fires on TestClient.__enter__() and tears down on __exit__().
    Inside the context, ws_tc.app.state.sessionmaker, ws_tc.app.state.redis,
    and ws_tc.app.state.engine are all bound -- identical to the async ``app``
    fixture in tests/conftest.py but synchronous for TestClient WS usage.

    Skips cleanly if Postgres is unreachable.
    Convention: ALL WS tests use this fixture, not the async ``app`` fixture.

    CRITICAL: All async operations during a test (DB seeding, Redis flush, OTP
    patching) MUST use _portal_call(ws_tc, coro) so they run on the TestClient's
    event loop, NOT asyncio.run() which creates a separate loop and causes
    SQLAlchemy pool leaks at teardown.
    """
    _app = create_app()

    # Connectivity probe using asyncio.run() BEFORE the lifespan opens.
    # This is safe here because the probe creates its own throwaway engine
    # on a fresh loop -- no pool from the app is involved yet.
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
        asyncio.run(_probe())
    except Exception as exc:
        pytest.skip(
            f"DATABASE_URL not reachable; run `docker compose up postgres redis` first ({exc!r})"
        )

    # Enter the TestClient context which fires the lifespan on the portal thread.
    with TestClient(_app, raise_server_exceptions=True) as tc:
        yield tc


def _portal_call(ws_tc: TestClient, coro: Any) -> Any:
    """Await a coroutine on the TestClient's anyio portal (same event loop as lifespan).

    portal.call() takes an async callable (not a coroutine instance), so we wrap
    the coroutine in a lambda that the portal can call and await.

    This is the ONLY safe way to run async code during a WS test -- avoids
    creating a separate event loop (asyncio.run()) which would cause SQLAlchemy
    pool connection leaks and ResourceWarning failures at test teardown.
    """
    assert ws_tc.portal is not None, (
        "_portal_call() called outside the ws_tc fixture context. "
        "Ensure ws_tc is used as a fixture (not constructed manually)."
    )

    # portal.call() expects a sync callable or an async callable.
    # A coroutine is already "awaitable" but not "callable".
    # We use portal.call with an async wrapper that awaits the coroutine.
    async def _awaiter() -> Any:
        return await coro

    return ws_tc.portal.call(_awaiter)


# ---------------------------------------------------------------------------
# Seed / auth helpers -- synchronous (used inside sync WS test bodies)
# ---------------------------------------------------------------------------


def seed_ws_client(ws_tc: TestClient, *, phone: str, suffix: str = "") -> Any:
    """Seed a User + Client row for WS tests and return the Client ORM object.

    Uses the TestClient's portal to run on the same event loop as the lifespan
    so SQLAlchemy pool connections are properly managed.
    """
    from app.modules.auth.models import User
    from app.modules.clients.models import Client

    session_factory: async_sessionmaker[AsyncSession] = ws_tc.app.state.sessionmaker

    async def _seed() -> Any:
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
            loaded = await session.get(Client, client.id)
            return loaded

    return _portal_call(ws_tc, _seed())


def auth_ws_client_sync(
    ws_tc: TestClient,
    client: Any,
) -> str:
    """Run the OTP auth flow synchronously and return cc_client_access cookie value.

    Uses the sync TestClient HTTP transport for OTP request/verify.
    Patches the OTP hash via the TestClient's portal (same event loop as lifespan).
    Returns the raw cookie value (without 'cc_client_access=' prefix and path suffix).
    """
    from app.modules.auth.models import OtpCode

    session_factory: async_sessionmaker[AsyncSession] = ws_tc.app.state.sessionmaker

    # Step 1: request OTP
    resp = ws_tc.post(
        "/api/v1/client/otp/request",
        json={"phone": client.phone},
    )
    assert resp.status_code == 202, f"OTP request failed: {resp.text}"

    # Step 2: patch OTP hash in DB using the portal (same loop as lifespan)
    settings = get_settings()
    raw_code, code_hash = generate_otp_code()

    async def _patch_otp() -> None:
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

    _portal_call(ws_tc, _patch_otp())

    # Step 3: verify OTP
    verify_resp = ws_tc.post(
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


def flush_redis_sync(ws_tc: TestClient) -> None:
    """Flush Redis synchronously for WS test isolation (runs on portal loop)."""

    async def _flush() -> None:
        await ws_tc.app.state.redis.flushdb()

    _portal_call(ws_tc, _flush())


def cleanup_client_sync(ws_tc: TestClient, *, phone: str) -> None:
    """Remove the seeded client, staff user, messages, and OTPs by phone (best-effort)."""
    from app.modules.clients.models import Client

    session_factory: async_sessionmaker[AsyncSession] = ws_tc.app.state.sessionmaker

    async def _cleanup() -> None:
        async with session_factory() as session:
            client = await session.scalar(select(Client).where(Client.phone == phone))
            if client is not None:
                await session.execute(
                    text(
                        "DELETE FROM messages WHERE thread_id IN "
                        "(SELECT id FROM message_threads WHERE client_id = :cid)"
                    ),
                    {"cid": str(client.id)},
                )
                await session.execute(
                    text("DELETE FROM message_threads WHERE client_id = :cid"),
                    {"cid": str(client.id)},
                )
                await session.execute(
                    text("DELETE FROM otp_codes WHERE client_id = :cid"),
                    {"cid": str(client.id)},
                )
                # Delete the staff user linked to this client (by email pattern)
                email_suffix = phone[-6:]
                await session.execute(
                    text(
                        "DELETE FROM users WHERE email LIKE :pattern"
                    ),
                    {"pattern": f"ws-test-staff-{email_suffix}%"},
                )
                await session.execute(
                    text("DELETE FROM clients WHERE id = :cid"),
                    {"cid": str(client.id)},
                )
                await session.commit()

    with contextlib.suppress(Exception):
        _portal_call(ws_tc, _cleanup())


# ---------------------------------------------------------------------------
# WS_ORIGIN constant -- pass as Origin header for TestClient WS connections
# ---------------------------------------------------------------------------

WS_ALLOWED_ORIGIN = "http://testserver"
"""The Origin header value accepted by verify_ws_origin in tests.

Configured via Settings.ws_allowed_origins default list.
Pass as ``headers={"origin": WS_ALLOWED_ORIGIN}`` to TestClient.websocket_connect().
"""
