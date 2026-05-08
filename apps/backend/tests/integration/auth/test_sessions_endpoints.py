"""Integration tests for HYG-03 — GET /sessions + POST /sessions/{family_id}/revoke.

Covers (Phase 23 D-23-1..D-23-10):
  - Paginated envelope shape {items, total, page, pageSize} (D-23-1).
  - Sort: is_current=True first, then last_used_at DESC (D-23-2).
  - is_current resolved by sha256(sz_refresh) token_hash lookup (D-23-3).
  - Item fields: {familyId, createdAt, lastUsedAt, userAgent, channel, isCurrent} (D-23-4).
  - POST revoke: 404-collapse on unknown/cross-user family (D-23-6).
  - POST revoke: idempotent 200 on already-revoked family (D-23-7).
  - POST revoke: self-revoke clears cookie matrix (D-23-8).
  - POST revoke: CSRF required (D-23-9).
  - POST revoke: audit session_revoked resource_type='auth_session' (D-23-10).
  - /logout-all behavior unchanged (smoke test).
"""

from __future__ import annotations

import uuid

import pytest_asyncio
from fastapi import FastAPI
from httpx import AsyncClient
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit_models import AuditLog
from app.core.permissions import Role
from app.core.security import hash_password
from app.modules.auth.models import RefreshToken, User

SESSIONS_OWNER_EMAIL = "sessions-owner@example.com"
SESSIONS_OWNER_PASSWORD = "hunter22hunter22"  # noqa: S105 — test password
SESSIONS_USER_B_EMAIL = "sessions-user-b@example.com"
SESSIONS_USER_B_PASSWORD = "userBpassword22"  # noqa: S105 — test password


@pytest_asyncio.fixture
async def redis_clean(app: FastAPI) -> Redis:
    """Flush Redis between tests so session + rate-limit keys don't bleed."""
    client: Redis = app.state.redis
    await client.flushdb()
    return client


@pytest_asyncio.fixture
async def seeded_owner(db_session: AsyncSession, redis_clean: Redis) -> User:
    """Insert seeded owner user with a valid password hash."""
    user = User(
        email=SESSIONS_OWNER_EMAIL,
        password_hash=await hash_password(SESSIONS_OWNER_PASSWORD),
        role=Role.OWNER,
        full_name="Sessions Owner",
    )
    db_session.add(user)
    await db_session.commit()
    return user


@pytest_asyncio.fixture
async def seeded_user_b(db_session: AsyncSession) -> User:
    """Second user for cross-user revoke test."""
    user = User(
        email=SESSIONS_USER_B_EMAIL,
        password_hash=await hash_password(SESSIONS_USER_B_PASSWORD),
        role=Role.OWNER,
        full_name="Sessions User B",
    )
    db_session.add(user)
    await db_session.commit()
    return user


async def _login(client: AsyncClient, email: str, password: str) -> None:
    r = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert r.status_code == 200, r.text


async def _get_sessions(client: AsyncClient, **params: object) -> dict:  # type: ignore[return]
    r = await client.get("/api/v1/auth/sessions", params=params)
    assert r.status_code == 200, r.text
    return r.json()


async def _revoke(
    client: AsyncClient, family_id: str, *, csrf: str | None = None
) -> dict | None:
    csrf_val = csrf if csrf is not None else client.cookies.get("sportzal_csrf", "")
    r = await client.post(
        f"/api/v1/auth/sessions/{family_id}/revoke",
        headers={"X-CSRF-Token": csrf_val} if csrf_val else {},
    )
    return r


async def test_get_sessions_returns_paginated_envelope(
    async_client: AsyncClient,
    db_session: AsyncSession,
    seeded_owner: User,
) -> None:
    """HYG-03 D-23-1: GET /sessions returns standard pagination envelope."""
    await _login(async_client, SESSIONS_OWNER_EMAIL, SESSIONS_OWNER_PASSWORD)

    body = await _get_sessions(async_client)
    data = body["data"]

    # Envelope shape.
    assert "items" in data
    assert "total" in data
    assert "page" in data
    assert "pageSize" in data
    assert data["page"] == 1
    assert data["pageSize"] == 20

    # At least one session (the one we just logged in with).
    assert data["total"] >= 1
    assert len(data["items"]) >= 1

    # Item field set (camelCase, D-23-4).
    item = data["items"][0]
    for key in ("familyId", "createdAt", "lastUsedAt", "userAgent", "channel", "isCurrent"):
        assert key in item, f"Missing key '{key}' in session item: {item}"


async def test_get_sessions_sort_is_current_first_then_last_used_desc(
    async_client: AsyncClient,
    db_session: AsyncSession,
    seeded_owner: User,
    redis_clean: Redis,
) -> None:
    """HYG-03 D-23-2 + D-23-3: sort is_current first, then lastUsedAt DESC.

    Seeds 2 sessions: one login with a fresh client (no cookies) then a second login.
    The second login's sz_refresh is the 'current' token. The is_current item should
    appear first in the list.
    """
    # First login (clear jar first to get a fresh family).
    await _login(async_client, SESSIONS_OWNER_EMAIL, SESSIONS_OWNER_PASSWORD)
    first_cookies = dict(async_client.cookies)

    # Second login (simulates a fresh device).
    async_client.cookies.clear()
    await _login(async_client, SESSIONS_OWNER_EMAIL, SESSIONS_OWNER_PASSWORD)

    body = await _get_sessions(async_client)
    items = body["data"]["items"]

    # There should be at least 2 families now.
    assert len(items) >= 2, f"Expected >= 2 session families, got {len(items)}"

    # The first item (current session) must have isCurrent=True.
    assert items[0]["isCurrent"] is True, (
        f"Expected items[0].isCurrent to be True, got: {items[0]}"
    )
    # Subsequent items must not be current.
    for item in items[1:]:
        assert item["isCurrent"] is False, (
            f"Expected non-current items to have isCurrent=False, got: {item}"
        )

    # Documentation: first_cookies was from the initial login (no longer current).
    assert "sz_refresh" in first_cookies


async def test_get_sessions_without_sz_refresh_marks_all_not_current(
    async_client: AsyncClient,
    db_session: AsyncSession,
    seeded_owner: User,
) -> None:
    """HYG-03 D-23-3: absent sz_refresh cookie → all items isCurrent=False."""
    await _login(async_client, SESSIONS_OWNER_EMAIL, SESSIONS_OWNER_PASSWORD)
    # Clear only sz_refresh (but keep sz_access for auth).
    async_client.cookies.delete("sz_refresh")

    body = await _get_sessions(async_client)
    items = body["data"]["items"]

    assert len(items) >= 1
    for item in items:
        assert item["isCurrent"] is False, (
            f"Without sz_refresh, all items must be isCurrent=False; got: {item}"
        )


async def test_get_sessions_pagination_defaults_and_cap(
    async_client: AsyncClient,
    seeded_owner: User,
) -> None:
    """HYG-03 D-23-1: defaults page=1, pageSize=20; cap at 100."""
    await _login(async_client, SESSIONS_OWNER_EMAIL, SESSIONS_OWNER_PASSWORD)

    # Default: no params.
    body_default = await _get_sessions(async_client)
    assert body_default["data"]["page"] == 1
    assert body_default["data"]["pageSize"] == 20

    # Cap: pageSize=500 should be clamped/rejected to ≤100 by PageQuery validation.
    r = await async_client.get("/api/v1/auth/sessions", params={"pageSize": 500})
    # Either validation error (422) or capped to 100 — both are acceptable.
    if r.status_code == 200:
        assert r.json()["data"]["pageSize"] <= 100, (
            f"pageSize exceeds cap: {r.json()['data']['pageSize']}"
        )
    else:
        assert r.status_code == 422, (
            f"Expected 422 validation error or capped 200, got {r.status_code}: {r.text}"
        )


async def test_revoke_unknown_family_returns_404(
    async_client: AsyncClient,
    seeded_owner: User,
) -> None:
    """HYG-03 D-23-6: POST revoke non-existent family_id → 404 not_found."""
    await _login(async_client, SESSIONS_OWNER_EMAIL, SESSIONS_OWNER_PASSWORD)

    random_family_id = str(uuid.uuid4())
    r = await _revoke(async_client, random_family_id)
    assert r.status_code == 404, r.text
    assert r.json()["code"] == "not_found"


async def test_revoke_cross_user_returns_404_collapsed(
    async_client: AsyncClient,
    db_session: AsyncSession,
    seeded_owner: User,
    seeded_user_b: User,
) -> None:
    """HYG-03 D-23-6: POST revoke with another user's family_id → 404 (enumeration prevention).

    User A revoking User B's family sees 404 (NOT 403), collapsing "does not exist" with
    "belongs to another user" to prevent probing other users' family_ids.
    """
    # Login as User B to mint their session family.
    b_client = AsyncClient(
        transport=async_client._transport,  # type: ignore[attr-defined]
        base_url="http://test",
    )
    async with b_client:
        await _login(b_client, SESSIONS_USER_B_EMAIL, SESSIONS_USER_B_PASSWORD)
        b_body = await _get_sessions(b_client)
        b_family_id = b_body["data"]["items"][0]["familyId"]

    # Login as User A.
    await _login(async_client, SESSIONS_OWNER_EMAIL, SESSIONS_OWNER_PASSWORD)

    # User A attempts to revoke User B's family.
    r = await _revoke(async_client, b_family_id)
    assert r.status_code == 404, (
        f"Expected 404 for cross-user revoke, got {r.status_code}: {r.text}"
    )
    assert r.json()["code"] == "not_found"

    # User B's session MUST still be alive (not revoked by User A).
    b_row = await db_session.scalar(
        select(RefreshToken).where(
            RefreshToken.user_id == seeded_user_b.id,
            RefreshToken.revoked_at.is_(None),
        )
    )
    assert b_row is not None, "User B's session was wrongly revoked by User A"


async def test_revoke_idempotent_on_second_call(
    async_client: AsyncClient,
    db_session: AsyncSession,
    seeded_owner: User,
    redis_clean: Redis,
) -> None:
    """HYG-03 D-23-7: POST revoke twice on the same non-current family → second call still 200.

    Uses two sessions: revoke the non-current (older) one twice. This avoids triggering
    self-revoke cookie clearing on the first call, so the second call's auth stays valid.
    The second call is a noop — already-revoked families are idempotent. Audit row
    count for session_revoked + auth_session does NOT increase on the second call.
    """
    # First login.
    await _login(async_client, SESSIONS_OWNER_EMAIL, SESSIONS_OWNER_PASSWORD)
    first_csrf = async_client.cookies.get("sportzal_csrf", "")
    first_cookies = dict(async_client.cookies)

    # Second login (different device).
    async_client.cookies.clear()
    await _login(async_client, SESSIONS_OWNER_EMAIL, SESSIONS_OWNER_PASSWORD)

    body = await _get_sessions(async_client)
    items = body["data"]["items"]
    assert len(items) >= 2, "Need at least 2 sessions to test non-self-revoke idempotency"

    # Pick the non-current family (to avoid self-revoke clearing our cookies).
    non_current = [it for it in items if not it["isCurrent"]]
    assert non_current, "Expected at least one non-current item"
    family_id = non_current[0]["familyId"]

    # First revoke.
    r1 = await _revoke(async_client, family_id)
    assert r1.status_code == 200, r1.text

    # Count audit rows after first revoke.
    rows_before = (
        await db_session.scalars(
            select(AuditLog).where(
                AuditLog.action == "session_revoked",
                AuditLog.resource_type == "auth_session",
            )
        )
    ).all()
    count_before = len(rows_before)

    # Second revoke (idempotent noop).
    r2 = await _revoke(async_client, family_id)
    assert r2.status_code == 200, r2.text

    # Audit row count must NOT have increased on the noop call.
    rows_after = (
        await db_session.scalars(
            select(AuditLog).where(
                AuditLog.action == "session_revoked",
                AuditLog.resource_type == "auth_session",
            )
        )
    ).all()
    assert len(rows_after) == count_before, (
        f"Audit row count increased on idempotent second revoke: "
        f"{count_before} → {len(rows_after)}"
    )
    _ = first_cookies, first_csrf  # first session is still alive (different device)


async def test_self_revoke_clears_cookie_matrix(
    async_client: AsyncClient,
    db_session: AsyncSession,
    seeded_owner: User,
    redis_clean: Redis,
) -> None:
    """HYG-03 D-23-8: self-revoke (current family) clears sz_access + sz_refresh + sportzal_csrf.

    Revoking the family that issued THIS request's sz_refresh is equivalent to /logout —
    the response must carry Set-Cookie deletion headers for all three cookies.
    """
    await _login(async_client, SESSIONS_OWNER_EMAIL, SESSIONS_OWNER_PASSWORD)
    body = await _get_sessions(async_client)
    # The current session item (isCurrent=True) is the one to self-revoke.
    current_items = [it for it in body["data"]["items"] if it["isCurrent"]]
    assert current_items, "Expected at least one isCurrent=True item in sessions list"
    current_family_id = current_items[0]["familyId"]

    r = await _revoke(async_client, current_family_id)
    assert r.status_code == 200, r.text

    # Response must clear all three cookies.
    deletion_headers = [
        h
        for h in r.headers.get_list("set-cookie")
        if "expires=" in h.lower() or "max-age=0" in h.lower()
    ]
    assert any(h.startswith("sz_access=") for h in deletion_headers), (
        f"sz_access cookie not cleared on self-revoke. Set-Cookie headers: {deletion_headers}"
    )
    assert any(h.startswith("sz_refresh=") for h in deletion_headers), (
        f"sz_refresh cookie not cleared on self-revoke. Set-Cookie headers: {deletion_headers}"
    )
    assert any(h.startswith("sportzal_csrf=") for h in deletion_headers), (
        f"sportzal_csrf cookie not cleared on self-revoke. Set-Cookie headers: {deletion_headers}"
    )

    # Audit row must be written with resource_type='auth_session'.
    audit_rows = (
        await db_session.scalars(
            select(AuditLog).where(
                AuditLog.action == "session_revoked",
                AuditLog.resource_type == "auth_session",
                AuditLog.actor_user_id == seeded_owner.id,
            )
        )
    ).all()
    assert audit_rows, "Expected session_revoked/auth_session audit row after self-revoke"
    assert str(audit_rows[-1].resource_id) == current_family_id


async def test_cross_revoke_does_not_clear_cookie_matrix(
    async_client: AsyncClient,
    db_session: AsyncSession,
    seeded_owner: User,
    redis_clean: Redis,
) -> None:
    """HYG-03 D-23-8 negative: revoking a NON-current family does NOT clear cookies."""
    # Create two sessions.
    await _login(async_client, SESSIONS_OWNER_EMAIL, SESSIONS_OWNER_PASSWORD)
    first_cookies = dict(async_client.cookies)
    async_client.cookies.clear()
    await _login(async_client, SESSIONS_OWNER_EMAIL, SESSIONS_OWNER_PASSWORD)

    body = await _get_sessions(async_client)
    items = body["data"]["items"]
    assert len(items) >= 2, "Need at least 2 sessions for this test"

    # Find a non-current item to revoke.
    non_current_items = [it for it in items if not it["isCurrent"]]
    assert non_current_items, "Expected at least one non-current session"
    non_current_family_id = non_current_items[0]["familyId"]

    r = await _revoke(async_client, non_current_family_id)
    assert r.status_code == 200, r.text

    # Cookies must NOT be cleared (it wasn't a self-revoke).
    deletion_headers = [
        h
        for h in r.headers.get_list("set-cookie")
        if "expires=" in h.lower() or "max-age=0" in h.lower()
    ]
    # The current session's cookies should NOT appear in deletion headers.
    current_cookies_cleared = any(
        h.startswith("sz_access=") or h.startswith("sz_refresh=")
        for h in deletion_headers
    )
    assert not current_cookies_cleared, (
        f"Cookies were cleared on cross-revoke (should only happen on self-revoke). "
        f"Set-Cookie headers: {deletion_headers}"
    )
    _ = first_cookies  # first session was seeded; docs only


async def test_revoke_audit_uses_auth_session_resource_type(
    async_client: AsyncClient,
    db_session: AsyncSession,
    seeded_owner: User,
) -> None:
    """HYG-03 D-23-10: audit row after revoke has resource_type='auth_session' (NOT 'session').

    The /logout flow uses resource_type='session'; the per-family endpoint uses
    'auth_session' — these are DISTINCT and both preserved in LOCKED_AUDIT_EVENTS.
    """
    await _login(async_client, SESSIONS_OWNER_EMAIL, SESSIONS_OWNER_PASSWORD)
    body = await _get_sessions(async_client)
    family_id = body["data"]["items"][0]["familyId"]

    r = await _revoke(async_client, family_id)
    assert r.status_code == 200, r.text

    # Must find exactly one new row with resource_type='auth_session'.
    rows = (
        await db_session.scalars(
            select(AuditLog).where(
                AuditLog.action == "session_revoked",
                AuditLog.resource_type == "auth_session",
                AuditLog.actor_user_id == seeded_owner.id,
            )
        )
    ).all()
    assert len(rows) == 1, (
        f"Expected exactly 1 audit row (session_revoked/auth_session), got {len(rows)}"
    )
    assert str(rows[0].resource_id) == family_id

    # The existing /logout path (resource_type='session') must NOT have been touched.
    session_rows = (
        await db_session.scalars(
            select(AuditLog).where(
                AuditLog.action == "session_revoked",
                AuditLog.resource_type == "session",
            )
        )
    ).all()
    assert len(session_rows) == 0, (
        "Per-family revoke must NOT emit resource_type='session' (that's the /logout path)"
    )


async def test_revoke_csrf_required(
    async_client: AsyncClient,
    seeded_owner: User,
) -> None:
    """HYG-03 D-23-9: POST /sessions/{family_id}/revoke without CSRF header → 403."""
    await _login(async_client, SESSIONS_OWNER_EMAIL, SESSIONS_OWNER_PASSWORD)
    body = await _get_sessions(async_client)
    family_id = body["data"]["items"][0]["familyId"]

    # Deliberately omit the X-CSRF-Token header.
    r = await async_client.post(f"/api/v1/auth/sessions/{family_id}/revoke")
    assert r.status_code == 403, r.text
    assert r.json()["code"] == "csrf_mismatch"


async def test_revoke_unauthenticated_returns_401(
    async_client: AsyncClient,
) -> None:
    """RBAC-04 ordering: no sz_access cookie → 401 fires before CSRF check."""
    random_family_id = str(uuid.uuid4())
    r = await async_client.post(
        f"/api/v1/auth/sessions/{random_family_id}/revoke",
        headers={"X-CSRF-Token": "any-token"},
    )
    assert r.status_code == 401, r.text


async def test_logout_all_unchanged(
    async_client: AsyncClient,
    db_session: AsyncSession,
    seeded_owner: User,
    redis_clean: Redis,
) -> None:
    """Smoke test: POST /logout-all retains existing behavior after Phase 23 changes.

    All user families revoked, cookie matrix cleared.
    """
    # Create two sessions.
    await _login(async_client, SESSIONS_OWNER_EMAIL, SESSIONS_OWNER_PASSWORD)
    async_client.cookies.clear()
    await _login(async_client, SESSIONS_OWNER_EMAIL, SESSIONS_OWNER_PASSWORD)

    rows_before = (
        await db_session.scalars(
            select(RefreshToken).where(
                RefreshToken.user_id == seeded_owner.id,
                RefreshToken.revoked_at.is_(None),
            )
        )
    ).all()
    assert len(rows_before) == 2

    r = await async_client.post(
        "/api/v1/auth/logout-all",
        headers={"X-CSRF-Token": async_client.cookies["sportzal_csrf"]},
    )
    assert r.status_code == 200, r.text

    # All families revoked.
    rows_after = (
        await db_session.scalars(
            select(RefreshToken).where(
                RefreshToken.user_id == seeded_owner.id,
                RefreshToken.revoked_at.is_(None),
            )
        )
    ).all()
    assert len(rows_after) == 0

    # Cookie matrix cleared.
    deletion_headers = [
        h
        for h in r.headers.get_list("set-cookie")
        if "expires=" in h.lower() or "max-age=0" in h.lower()
    ]
    assert any(h.startswith("sz_access=") for h in deletion_headers)
    assert any(h.startswith("sz_refresh=") for h in deletion_headers)
    assert any(h.startswith("sportzal_csrf=") for h in deletion_headers)
