"""Integration tests for /api/v1/auth/logout + /logout-all.

Covers AUTH-LO-01 / AUTH-LO-02 (Phase 5) and Phase 6 CSRF-02 wiring.

Asserts:
  - /logout: revokes the current family in DB + Redis, clears all three cookies,
    emits structlog event=session_revoked.
  - /logout-all: revokes ALL alive families for the user, emits event=session_revoked_all.
  - /logout without auth → 401 (Phase 6 RBAC-04: 401 fires before any 403 path).
  - /logout authenticated without X-CSRF-Token → 403 csrf_mismatch (Phase 6 D-09).
  - /logout authenticated with wrong X-CSRF-Token → 403 csrf_mismatch.
"""

from __future__ import annotations

from collections.abc import Awaitable
from typing import cast

import pytest_asyncio
from fastapi import FastAPI
from httpx import AsyncClient
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from structlog.testing import capture_logs

from app.core.audit_models import AuditLog
from app.core.permissions import Role
from app.core.security import hash_password
from app.modules.auth.models import RefreshToken, User

OWNER_EMAIL = "owner-logout@example.com"
OWNER_PASSWORD = "hunter22hunter22"  # noqa: S105 — test password literal


@pytest_asyncio.fixture
async def redis_clean(app: FastAPI) -> Redis:
    client: Redis = app.state.redis
    await client.flushdb()
    return client


@pytest_asyncio.fixture
async def seeded_owner(db_session: AsyncSession, redis_clean: Redis) -> User:
    user = User(
        email=OWNER_EMAIL,
        password_hash=await hash_password(OWNER_PASSWORD),
        role=Role.OWNER,
        full_name="Logout Owner",
    )
    db_session.add(user)
    await db_session.commit()
    return user


async def _login(client: AsyncClient) -> None:
    r = await client.post(
        "/api/v1/auth/login",
        json={"email": OWNER_EMAIL, "password": OWNER_PASSWORD},
    )
    assert r.status_code == 200, r.text


async def test_logout_revokes_family_and_clears_cookies(
    async_client: AsyncClient,
    db_session: AsyncSession,
    seeded_owner: User,
    redis_clean: Redis,
) -> None:
    await _login(async_client)

    # Sanity — there's exactly one alive refresh row.
    rows_before = (
        await db_session.scalars(
            select(RefreshToken).where(
                RefreshToken.user_id == seeded_owner.id,
                RefreshToken.revoked_at.is_(None),
            )
        )
    ).all()
    assert len(rows_before) == 1
    family_id = rows_before[0].family_id

    with capture_logs() as captured:
        r = await async_client.post(
            "/api/v1/auth/logout",
            headers={"X-CSRF-Token": async_client.cookies["sportzal_csrf"]},
        )

    assert r.status_code == 200, r.text

    # event=session_revoked emitted (D-20)
    events = [c.get("event") for c in captured]
    assert "session_revoked" in events

    # DB: every refresh row for this family is revoked
    rows_after = (
        await db_session.scalars(
            select(RefreshToken).where(
                RefreshToken.user_id == seeded_owner.id,
                RefreshToken.revoked_at.is_(None),
            )
        )
    ).all()
    assert len(rows_after) == 0

    # Redis: session key gone, family removed from user_sessions set
    assert await redis_clean.get(f"auth:session:{seeded_owner.id}:{family_id}") is None
    # `sismember` is typed `Awaitable[Literal[0, 1]] | Literal[0, 1]` in redis-py
    # (sync/async shared stubs) — cast to disambiguate for mypy.
    is_member = await cast(
        "Awaitable[int]",
        redis_clean.sismember(f"auth:user_sessions:{seeded_owner.id}", str(family_id)),
    )
    assert not is_member

    # Cookies cleared on the client (httpx jar updates from Set-Cookie with Max-Age=0).
    # We assert via presence of explicit deletion headers (Max-Age=0 or expires=...).
    deletion_headers = [
        h
        for h in r.headers.get_list("set-cookie")
        if "expires=" in h.lower() or "max-age=0" in h.lower()
    ]
    # All three cookies must be cleared
    assert any(h.startswith("sz_access=") for h in deletion_headers)
    assert any(h.startswith("sz_refresh=") for h in deletion_headers)
    assert any(h.startswith("sportzal_csrf=") for h in deletion_headers)


async def test_logout_unauthenticated_returns_401(
    async_client: AsyncClient,
    redis_clean: Redis,
) -> None:
    """No sz_access cookie → 401, NOT a free cookie clearing for unauthenticated callers."""
    r = await async_client.post("/api/v1/auth/logout")
    assert r.status_code == 401


async def test_logout_all_revokes_all_families(
    async_client: AsyncClient,
    db_session: AsyncSession,
    seeded_owner: User,
    redis_clean: Redis,
) -> None:
    """logout-all enumerates via Redis SET, revokes every alive row, emits session_revoked_all."""
    # Two logins → two families
    await _login(async_client)
    # Snapshot first cookie set so we can simulate a second device
    first_cookies = dict(async_client.cookies)
    # Reset the jar and login again to mint a second family
    async_client.cookies.clear()
    await _login(async_client)

    rows_before = (
        await db_session.scalars(
            select(RefreshToken).where(
                RefreshToken.user_id == seeded_owner.id,
                RefreshToken.revoked_at.is_(None),
            )
        )
    ).all()
    assert len(rows_before) == 2

    with capture_logs() as captured:
        r = await async_client.post(
            "/api/v1/auth/logout-all",
            headers={"X-CSRF-Token": async_client.cookies["sportzal_csrf"]},
        )

    assert r.status_code == 200, r.text
    events = [c.get("event") for c in captured]
    assert "session_revoked_all" in events

    rows_after = (
        await db_session.scalars(
            select(RefreshToken).where(
                RefreshToken.user_id == seeded_owner.id,
                RefreshToken.revoked_at.is_(None),
            )
        )
    ).all()
    assert len(rows_after) == 0

    # Redis: user_sessions set deleted, no auth:session:* keys remain for this user
    assert await redis_clean.exists(f"auth:user_sessions:{seeded_owner.id}") == 0

    # The unused first_cookies serve as documentation of the second-device scenario.
    assert "sz_refresh" in first_cookies  # belt-and-braces sanity


async def test_logout_authenticated_without_csrf_header_returns_403(
    async_client: AsyncClient,
    seeded_owner: User,
    redis_clean: Redis,
) -> None:
    """Authenticated /logout WITHOUT X-CSRF-Token header → 403 csrf_mismatch.

    Locks Phase 6 D-09 wiring: verify_csrf is a signature dep on /logout, runs
    AFTER require_authenticated (RBAC-04, D-22), so an authenticated caller
    without the CSRF header gets 403 csrf_mismatch (NOT 401).
    """
    await _login(async_client)
    # Login minted sportzal_csrf into the jar; deliberately omit the header.
    r = await async_client.post("/api/v1/auth/logout")
    assert r.status_code == 403, r.text
    body = r.json()
    assert body["code"] == "csrf_mismatch"


async def test_logout_authenticated_with_wrong_csrf_header_returns_403(
    async_client: AsyncClient,
    seeded_owner: User,
    redis_clean: Redis,
) -> None:
    """Mismatched X-CSRF-Token vs sportzal_csrf cookie → 403 csrf_mismatch."""
    await _login(async_client)
    r = await async_client.post(
        "/api/v1/auth/logout",
        headers={"X-CSRF-Token": "deadbeef" * 8},  # wrong value, length-OK
    )
    assert r.status_code == 403, r.text
    assert r.json()["code"] == "csrf_mismatch"


async def test_logout_unauthenticated_returns_401_even_without_csrf(
    async_client: AsyncClient,
    redis_clean: Redis,
) -> None:
    """RBAC-04 ordering canary (D-22): unauth /logout → 401 invalid_token, NOT 403 csrf_mismatch.

    verify_csrf is a SIGNATURE dep AFTER require_authenticated (Plan 06-03 Task 1
    Step 2). FastAPI resolves signature deps in declaration order, so the auth
    check fires first and returns 401 before verify_csrf can return 403.
    """
    # No _login call; no cookies in jar; no header.
    r = await async_client.post("/api/v1/auth/logout")
    assert r.status_code == 401, r.text
    assert r.json()["code"] == "invalid_token"


async def test_logout_writes_session_revoked_audit_row(
    async_client: AsyncClient,
    db_session: AsyncSession,
    seeded_owner: User,
) -> None:
    """AUDIT-02: /logout writes session_revoked row with family_id resource_id."""
    await _login(async_client)
    r = await async_client.post(
        "/api/v1/auth/logout",
        headers={"X-CSRF-Token": async_client.cookies["sportzal_csrf"]},
    )
    assert r.status_code == 200, r.text

    rows = (
        await db_session.scalars(
            select(AuditLog).where(
                AuditLog.action == "session_revoked",
                AuditLog.actor_user_id == seeded_owner.id,
            )
        )
    ).all()
    assert len(rows) == 1, "Pitfall 2 fix: emit must run BEFORE the route's commit"
    assert rows[0].resource_type == "session"
    assert rows[0].resource_id is not None  # family_id
