"""Integration tests for PATCH /api/v1/auth/me (PROF-01).

Covers (Phase 109 Task 2):
  1. Happy path — full update (full_name + email) → 200, MeResponse echoes new values;
     GET /me confirms DB persistence.
  2. Partial update — PATCH with full_name only → 200, email unchanged.
  3. Email-taken — attempt to claim another user's email → 409 ConflictError with
     fields.email (NOT 500).  D-109-01-CONFLICT.
  4. Extra field rejected — PATCH {'theme': 'dark'} → 422 (extra=forbid on BackendSchemaBase).
  5. CSRF required — PATCH without X-CSRF-Token header → 403 csrf_mismatch.
  6. Auth required — PATCH with no session cookies → 401; assert 401 fires BEFORE 403
     when both auth+csrf are absent (RBAC-04 D-22).
  7. Audit row — profile_updated row written with no password/hash/raw-email leak.

Harness: SAVEPOINT rollback + ASGITransport async_client from root conftest.py.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import AsyncClient
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit_models import AuditLog
from app.core.permissions import Role
from app.core.security import hash_password
from app.modules.auth.models import User

pytestmark = pytest.mark.asyncio

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PROF_OWNER_EMAIL = "prof-update-owner@example.com"
PROF_OWNER_PASSWORD = "hunterprof22pw"  # noqa: S105 — test password

PROF_OTHER_EMAIL = "prof-other-user@example.com"
PROF_OTHER_PASSWORD = "otherprof22pw"  # noqa: S105 — test password


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def redis_clean(app: FastAPI) -> Redis:
    """Flush Redis between tests so session keys don't bleed."""
    client: Redis = app.state.redis
    await client.flushdb()
    return client


@pytest_asyncio.fixture
async def seeded_owner(db_session: AsyncSession, redis_clean: Redis) -> User:
    """Insert owner user with a valid password hash."""
    _ = redis_clean
    user = User(
        email=PROF_OWNER_EMAIL,
        password_hash=await hash_password(PROF_OWNER_PASSWORD),
        role=Role.OWNER,
        full_name="Profile Owner",
    )
    db_session.add(user)
    await db_session.commit()
    return user


@pytest_asyncio.fixture
async def seeded_other_user(db_session: AsyncSession) -> User:
    """Second user — used to trigger duplicate-email 409."""
    user = User(
        email=PROF_OTHER_EMAIL,
        password_hash=await hash_password(PROF_OTHER_PASSWORD),
        role=Role.OWNER,
        full_name="Other Prof User",
    )
    db_session.add(user)
    await db_session.commit()
    return user


async def _login(client: AsyncClient) -> None:
    r = await client.post(
        "/api/v1/auth/login",
        json={"email": PROF_OWNER_EMAIL, "password": PROF_OWNER_PASSWORD},
    )
    assert r.status_code == 200, r.text


# ---------------------------------------------------------------------------
# Test 1: happy path — full update (full_name + email), persistence confirmed
# ---------------------------------------------------------------------------


async def test_patch_me_happy_path_and_persistence(
    async_client: AsyncClient,
    db_session: AsyncSession,
    seeded_owner: User,
) -> None:
    """PROF-01 happy path: PATCH with fullName+email → 200 MeResponse echo;
    subsequent GET /me returns the updated values (DB persistence confirmed).
    """
    await _login(async_client)

    new_name = f"New Name {uuid4().hex[:6]}"
    new_email = f"newemail-{uuid4().hex[:8]}@example.com"

    r = await async_client.patch(
        "/api/v1/auth/me",
        json={"fullName": new_name, "email": new_email},
        headers={"X-CSRF-Token": async_client.cookies["clubcore_csrf"]},
    )
    assert r.status_code == 200, r.text

    data = r.json()["data"]
    assert data["fullName"] == new_name, f"PATCH response should echo new fullName: {data}"
    assert data["email"] == new_email, f"PATCH response should echo new email: {data}"
    assert data["id"] == str(seeded_owner.id)

    # Confirm persistence via GET /me.
    get_r = await async_client.get("/api/v1/auth/me")
    assert get_r.status_code == 200, get_r.text
    get_data = get_r.json()["data"]
    assert get_data["fullName"] == new_name, f"GET /me after PATCH: fullName mismatch: {get_data}"
    assert get_data["email"] == new_email, f"GET /me after PATCH: email mismatch: {get_data}"


# ---------------------------------------------------------------------------
# Test 2: partial update — full_name only, email unchanged
# ---------------------------------------------------------------------------


async def test_patch_me_partial_name_only(
    async_client: AsyncClient,
    db_session: AsyncSession,
    seeded_owner: User,
) -> None:
    """Partial PATCH with fullName only → 200; email remains as original."""
    original_email = seeded_owner.email

    await _login(async_client)

    new_name = f"Solo Name {uuid4().hex[:6]}"
    r = await async_client.patch(
        "/api/v1/auth/me",
        json={"fullName": new_name},
        headers={"X-CSRF-Token": async_client.cookies["clubcore_csrf"]},
    )
    assert r.status_code == 200, r.text

    data = r.json()["data"]
    assert data["fullName"] == new_name
    assert data["email"] == original_email, "Email must not change on fullName-only PATCH"


# ---------------------------------------------------------------------------
# Test 3: email-taken → 409 field error (D-109-01-CONFLICT), not 500
# ---------------------------------------------------------------------------


async def test_patch_me_email_taken_returns_409_with_field_error(
    async_client: AsyncClient,
    db_session: AsyncSession,
    seeded_owner: User,
    seeded_other_user: User,
) -> None:
    """PROF-01 D-109-01: duplicate email → 409 ConflictError with fields.email.

    seeded_other_user holds PROF_OTHER_EMAIL.  Attempting to move the owner's
    email to that address must return 409, NOT 500, and the error body must
    include fields.email so the FE can render an inline field error.
    """
    await _login(async_client)

    r = await async_client.patch(
        "/api/v1/auth/me",
        json={"email": PROF_OTHER_EMAIL},
        headers={"X-CSRF-Token": async_client.cookies["clubcore_csrf"]},
    )
    assert r.status_code == 409, (
        f"Duplicate email must return 409, got {r.status_code}: {r.text}"
    )

    body = r.json()
    assert body.get("code") == "conflict", f"Expected code='conflict', got: {body}"
    # fields.email must be present (inline field error for the FE).
    assert "fields" in body and "email" in body["fields"], (
        f"409 body must have fields.email for inline FE error: {body}"
    )

    # Owner's email must still be the original — the PATCH was rejected.
    get_r = await async_client.get("/api/v1/auth/me")
    assert get_r.status_code == 200
    assert get_r.json()["data"]["email"] == PROF_OWNER_EMAIL


# ---------------------------------------------------------------------------
# Test 4: extra field rejected (theme → 422, extra=forbid)
# ---------------------------------------------------------------------------


async def test_patch_me_extra_field_rejected_422(
    async_client: AsyncClient,
    seeded_owner: User,
) -> None:
    """PATCH with extra key 'theme' → 422 (BackendSchemaBase extra=forbid).

    Theme is client-only; no User.theme column exists.  This test is the
    contract canary: if extra fields were accidentally accepted, a later phase
    that rejects them would break.
    """
    await _login(async_client)

    r = await async_client.patch(
        "/api/v1/auth/me",
        json={"theme": "dark"},
        headers={"X-CSRF-Token": async_client.cookies["clubcore_csrf"]},
    )
    assert r.status_code == 422, (
        f"Extra field 'theme' must be rejected with 422, got {r.status_code}: {r.text}"
    )


# ---------------------------------------------------------------------------
# Test 5: CSRF required → 403 csrf_mismatch
# ---------------------------------------------------------------------------


async def test_patch_me_without_csrf_returns_403(
    async_client: AsyncClient,
    seeded_owner: User,
) -> None:
    """Authenticated PATCH /me without X-CSRF-Token header → 403 csrf_mismatch."""
    await _login(async_client)

    # Deliberately omit the X-CSRF-Token header.
    r = await async_client.patch(
        "/api/v1/auth/me",
        json={"fullName": "Ghost"},
    )
    assert r.status_code == 403, f"Expected 403, got {r.status_code}: {r.text}"
    assert r.json()["code"] == "csrf_mismatch"


# ---------------------------------------------------------------------------
# Test 6: auth required → 401 (and 401 before 403 when both are absent)
# ---------------------------------------------------------------------------


async def test_patch_me_without_auth_returns_401(
    async_client: AsyncClient,
) -> None:
    """No session cookies → 401 (RBAC-04: auth dep fires before csrf dep)."""
    # No _login — empty cookie jar.
    r = await async_client.patch(
        "/api/v1/auth/me",
        json={"fullName": "Ghost"},
    )
    assert r.status_code == 401, f"Expected 401, got {r.status_code}: {r.text}"
    # When both auth and CSRF are absent, the auth dep fires FIRST → 401, not 403.
    assert r.json()["code"] == "invalid_token"


# ---------------------------------------------------------------------------
# Test 7: audit row written with no sensitive leak
# ---------------------------------------------------------------------------


async def test_patch_me_writes_profile_updated_audit_row(
    async_client: AsyncClient,
    db_session: AsyncSession,
    seeded_owner: User,
) -> None:
    """PATCH /me writes a 'profile_updated' AuditLog row (Pitfall 2 fix).

    Payload must contain changed_fields markers but NO password, hash, or
    raw email values (T-109-01 information-disclosure mitigated).
    """
    await _login(async_client)

    new_name = f"Audit Check {uuid4().hex[:6]}"
    r = await async_client.patch(
        "/api/v1/auth/me",
        json={"fullName": new_name},
        headers={"X-CSRF-Token": async_client.cookies["clubcore_csrf"]},
    )
    assert r.status_code == 200, r.text

    rows = (
        await db_session.scalars(
            select(AuditLog).where(
                AuditLog.action == "profile_updated",
                AuditLog.actor_user_id == seeded_owner.id,
            )
        )
    ).all()
    assert len(rows) >= 1, "Pitfall 2: profile_updated audit row must be committed atomically"

    row = rows[0]
    assert row.resource_type == "user"
    assert row.resource_id == seeded_owner.id

    # Payload must carry changed_fields markers but no raw secrets.
    payload = row.payload
    assert "changed_fields" in payload, f"Audit payload must have changed_fields: {payload}"
    assert "full_name" in payload["changed_fields"], (
        f"'full_name' must appear in changed_fields: {payload}"
    )
    # No raw values — password/hash/email must NOT be in the payload.
    payload_str = str(payload)
    assert "password" not in payload_str.lower(), f"Audit payload leaks 'password': {payload}"
    assert new_name not in payload_str, f"Audit payload leaks raw fullName value: {payload}"


# ---------------------------------------------------------------------------
# Test 8: mixed-case email update — stored lowercased, login still works (CR-01)
# ---------------------------------------------------------------------------


async def test_patch_me_mixed_case_email_stored_lowercase_login_succeeds(
    async_client: AsyncClient,
    db_session: AsyncSession,
    seeded_owner: User,
) -> None:
    """CR-01: PATCH email with mixed-case address → stored as lowercase;
    subsequent login with the lowercased email succeeds (no self-lockout).

    authenticate() always lowercases the submitted email before the SQL lookup,
    so update_profile must store the canonical lowercase form to match.
    """
    await _login(async_client)

    # Mixed-case address — the local part has uppercase letters.
    mixed_case_email = f"MixedCase-{uuid4().hex[:6]}@Example.COM"
    expected_stored = mixed_case_email.lower()

    r = await async_client.patch(
        "/api/v1/auth/me",
        json={"email": mixed_case_email},
        headers={"X-CSRF-Token": async_client.cookies["clubcore_csrf"]},
    )
    assert r.status_code == 200, r.text

    # The response must echo the stored (lowercased) value.
    data = r.json()["data"]
    assert data["email"] == expected_stored, (
        f"PATCH response must echo lowercased email, got: {data['email']!r}"
    )

    # DB value must be lowercase.
    await db_session.refresh(seeded_owner)
    assert seeded_owner.email == expected_stored, (
        f"DB User.email must be stored lowercase, got: {seeded_owner.email!r}"
    )

    # Login with the lowercased email must succeed (no self-lockout).
    login_r = await async_client.post(
        "/api/v1/auth/login",
        json={"email": expected_stored, "password": PROF_OWNER_PASSWORD},
    )
    assert login_r.status_code == 200, (
        f"Login with lowercased email must succeed after mixed-case PATCH: {login_r.text}"
    )
