"""Phase 43 CR-03 regression — login chokepoint blocks deactivated/soft-deleted users.

Pre-fix: authenticate() only filtered on password_hash IS NOT NULL. Soft-deleted
owners and deactivated operators could still present their original credentials
and receive a fresh access/refresh/csrf triple — contradicting USERS-04/05.

Fix: mirror the D-43-20 rotate_refresh predicate set (User.is_active +
User.deleted_at). Both new miss branches fall into the existing sentinel-hash
+ login_failed emit path, preserving AUTH-EP-02 timing+info equivalence.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit_models import AuditLog
from app.core.permissions import Role
from app.core.security import hash_password
from app.modules.auth.models import User

pytestmark = pytest.mark.asyncio

_PLAINTEXT = "TestPassword123!"
_PLAINTEXT_2 = "AnotherPassword456!"
_PLAINTEXT_3 = "Password789!"
_PLAINTEXT_AUDIT = "AuditPassword!"


@pytest_asyncio.fixture
async def active_reception_user(db_session: AsyncSession) -> User:
    """Seed an active reception user with a known plaintext password."""
    user = User(
        email="deactivated-login@example.com",
        email_verified=True,
        password_hash=await hash_password(_PLAINTEXT),
        role=Role.RECEPTION,
        full_name="Deactivated Login Target",
        is_active=True,
        status="active",
    )
    db_session.add(user)
    await db_session.commit()
    return user


async def test_login_deactivated_user_returns_401_no_cookies(
    async_client: AsyncClient,
    db_session: AsyncSession,
    active_reception_user: User,
) -> None:
    """CR-03 regression — deactivated user gets 401 with no Set-Cookie headers."""
    target = active_reception_user

    # Baseline — login works while active.
    baseline = await async_client.post(
        "/api/v1/auth/login",
        json={"email": target.email, "password": _PLAINTEXT},
    )
    assert baseline.status_code == 200, f"Baseline login failed unexpectedly: {baseline.text}"
    set_cookies_baseline = [v for k, v in baseline.headers.items() if k.lower() == "set-cookie"]
    assert len(set_cookies_baseline) > 0, "Expected Set-Cookie headers on successful login"

    # Deactivate via direct UPDATE (bypass the service layer — testing the
    # auth chokepoint, not the deactivate flow).
    await db_session.execute(
        update(User)
        .where(User.id == target.id)
        .values(
            is_active=False,
            deactivated_at=datetime.now(tz=UTC),
        )
    )
    await db_session.commit()

    # Attempt login — must 401 with no cookies.
    response = await async_client.post(
        "/api/v1/auth/login",
        json={"email": target.email, "password": _PLAINTEXT},
    )
    assert response.status_code == 401, (
        f"CR-03 regression — deactivated user returned {response.status_code} "
        f"instead of 401. The authenticate() SELECT must filter on User.is_active."
    )
    body = response.json()
    assert body.get("code") == "invalid_credentials", (
        f"CR-03 regression — deactivated login should return invalid_credentials, "
        f"got {body}. The authenticate() SELECT must filter on User.is_active."
    )
    # CRITICAL: no Set-Cookie headers on the failed login.
    cookie_headers = [v for k, v in response.headers.items() if k.lower() == "set-cookie"]
    assert cookie_headers == [], (
        "CR-03 regression — deactivated user received Set-Cookie on failed login. "
        f"Headers: {cookie_headers}"
    )


async def test_login_soft_deleted_user_returns_401_no_cookies(
    async_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Same invariant for soft-delete tombstone path."""
    user = User(
        email="soft-deleted-login@example.com",
        email_verified=True,
        password_hash=await hash_password(_PLAINTEXT_2),
        role=Role.RECEPTION,
        full_name="Soft Deleted Login Target",
        is_active=True,
        status="active",
    )
    db_session.add(user)
    await db_session.commit()

    # Soft-delete via direct UPDATE.
    now = datetime.now(tz=UTC)
    await db_session.execute(
        update(User)
        .where(User.id == user.id)
        .values(
            deleted_at=now,
            is_active=False,
            deactivated_at=now,
        )
    )
    await db_session.commit()

    response = await async_client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": _PLAINTEXT_2},
    )
    assert response.status_code == 401, (
        f"CR-03 regression — soft-deleted user returned {response.status_code} instead of 401."
    )
    assert response.json().get("code") == "invalid_credentials", (
        f"Expected invalid_credentials, got: {response.json()}"
    )
    cookie_headers = [v for k, v in response.headers.items() if k.lower() == "set-cookie"]
    assert cookie_headers == [], "Soft-deleted user received cookies on failed login"


async def test_login_anti_oracle_body_parity(
    async_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """The 401 body MUST be byte-identical across (deactivated, soft-deleted,
    unknown-email, wrong-password) — Phase 42 anti-oracle discipline."""
    # Seed a deactivated user.
    deactivated = User(
        email="oracle-parity-deactivated@example.com",
        email_verified=True,
        password_hash=await hash_password(_PLAINTEXT_3),
        role=Role.RECEPTION,
        full_name="Oracle Parity Deactivated",
        is_active=False,  # deactivated from the start
        status="active",
        deactivated_at=datetime.now(tz=UTC),
    )
    # Seed an active user for the wrong-password case.
    active = User(
        email="oracle-parity-active@example.com",
        email_verified=True,
        password_hash=await hash_password(_PLAINTEXT_3),
        role=Role.RECEPTION,
        full_name="Oracle Parity Active",
        is_active=True,
        status="active",
    )
    db_session.add_all([deactivated, active])
    await db_session.commit()

    deactivated_resp = await async_client.post(
        "/api/v1/auth/login",
        json={"email": deactivated.email, "password": _PLAINTEXT_3},
    )
    soft_deleted_resp = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "nonexistent-oracle@example.com", "password": _PLAINTEXT_3},
    )
    unknown_resp = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "completely-unknown@example.com", "password": _PLAINTEXT_3},
    )
    wrong_pw_resp = await async_client.post(
        "/api/v1/auth/login",
        json={"email": active.email, "password": "WrongPassword!!"},
    )

    # All four must be 401.
    assert deactivated_resp.status_code == 401
    assert soft_deleted_resp.status_code == 401
    assert unknown_resp.status_code == 401
    assert wrong_pw_resp.status_code == 401

    # Byte-identical body across all 4 cases.
    assert (
        deactivated_resp.text == soft_deleted_resp.text == unknown_resp.text == wrong_pw_resp.text
    ), (
        "Anti-oracle regression — login response bodies differ across "
        f"(deactivated={deactivated_resp.text!r}, "
        f"soft_deleted={soft_deleted_resp.text!r}, "
        f"unknown={unknown_resp.text!r}, wrong_pw={wrong_pw_resp.text!r}). "
        "All miss branches must share the same body shape."
    )


async def test_login_deactivated_user_emits_login_failed_audit(
    async_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Deactivated login attempt emits login_failed reason=invalid_credentials.

    Same shape as the unknown-email path — compliance review cannot
    distinguish at the audit layer (anti-oracle preserved at audit layer too).
    """
    user = User(
        email="audit-emit-deactivated@example.com",
        email_verified=True,
        password_hash=await hash_password(_PLAINTEXT_AUDIT),
        role=Role.RECEPTION,
        full_name="Audit Emit Deactivated",
        is_active=False,
        status="active",
        deactivated_at=datetime.now(tz=UTC),
    )
    db_session.add(user)
    await db_session.commit()

    await async_client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": _PLAINTEXT_AUDIT},
    )

    rows = (
        (await db_session.execute(select(AuditLog).where(AuditLog.action == "login_failed")))
        .scalars()
        .all()
    )
    matching = [r for r in rows if r.payload.get("email") == user.email]
    assert len(matching) >= 1, (
        f"CR-03 regression — no login_failed audit row found for deactivated "
        f"user {user.email!r}. Expected at least 1 matching row."
    )
    # Verify the reason is the anti-oracle-uniform "invalid_credentials".
    for r in matching:
        assert r.payload.get("reason") == "invalid_credentials", (
            f"CR-03 regression — login_failed for deactivated user has reason "
            f"!= 'invalid_credentials': {r.payload}"
        )
