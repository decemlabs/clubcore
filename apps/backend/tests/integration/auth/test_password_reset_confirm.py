"""Integration tests for POST /api/v1/auth/password-reset/confirm (RESET-02).

D-44-14 (single-SQL atomic-consume) + D-44-15 (replay/expired/unknown → 410
identical body) + D-44-16 (atomic-consume → password rotate → revoke-all →
audit emit, in that order) + D-44-17 (weak-password gate runs BEFORE the
atomic-consume so the token stays valid for retry within TTL).

Phase 41 D-41-18 lineage — real Postgres via SAVEPOINT-per-test isolation
(``db_session`` fixture in ``tests/conftest.py``); each test seeds its own
user + token row.

Wire format note: ``PasswordResetConfirmBody`` declares ``new_password``
which serializes to ``newPassword`` via ``to_camel``. ``validate_by_name=True``
+ ``validate_by_alias=True`` (core.schemas:BackendSchemaBase) accept BOTH
forms on input; tests use the camelCase wire spelling per project convention.

AppError envelope shape (pinned for Wave 4 sibling tests):
  ``{"code": "<error_code>", "message": "<...>", "fields": <null | dict>}``
at top level (NOT nested under ``detail``). Source:
``app.core.exceptions._app_error_handler`` (apps/backend/app/core/exceptions.py:415-423).
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
import structlog
from fastapi import FastAPI
from httpx import AsyncClient
from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit_models import AuditLog
from app.core.permissions import Role
from app.core.security import hash_password
from app.modules.auth.models import User
from app.modules.auth.password_reset_token_model import PasswordResetToken

pytestmark = pytest.mark.asyncio


# AUTH-EP-05 login floor is >=12 chars. Old + new passwords both clear it so
# the happy-path test can exercise login-with-new-password end-to-end.
_OLD_PASSWORD = "old-pass-rotated-12345"  # noqa: S105 — test literal
_NEW_PASSWORD = "new-pass-rotated-67890"  # noqa: S105 — test literal
# Below the 8-char floor enforced by ``confirm_password_reset`` per D-44-17.
_WEAK_PASSWORD = "weak123"  # noqa: S105 — test literal (7 chars)


def _hash_token(raw: str) -> str:
    """Mirror service-layer ``hashlib.sha256(raw.encode()).hexdigest()`` discipline."""
    return hashlib.sha256(raw.encode()).hexdigest()


@pytest_asyncio.fixture
async def redis_clean(app: FastAPI) -> Redis:
    """Flush Redis between tests so prior rate-limit/session keys don't bleed."""
    client: Redis = app.state.redis
    await client.flushdb()
    return client


@pytest_asyncio.fixture
async def _refresh_password_reset_logger() -> None:
    """Force ``password_reset_service._log`` to re-resolve processors.

    Mirrors the auth.service logger-cache reset in
    ``tests/integration/auth/conftest.py``: ``structlog.configure(
    cache_logger_on_first_use=True)`` makes the lazy proxy cache a reference
    to the processor list active at first ``bind()``. Tests using
    ``structlog.testing.capture_logs()`` swap the *current* config's
    processor list — but the cached logger keeps pointing at the old list.
    Deleting ``__dict__['bind']`` forces re-resolution on the next call so
    ``capture_logs()`` sees the emissions.
    """
    from app.modules.auth import password_reset_service as service_mod

    if "bind" in service_mod._log.__dict__:
        del service_mod._log.__dict__["bind"]


@pytest_asyncio.fixture
async def seeded_user_with_token(
    db_session: AsyncSession,
    redis_clean: Redis,
) -> tuple[User, str, UUID]:
    """Seed one active user + one fresh ``password_reset_tokens`` row.

    Returns ``(user, raw_token, token_row_id)``. The raw token is held only
    in the test process; the DB stores ``sha256(raw)`` per the service-layer
    hashing discipline (password_reset_token_model.py:43-53).
    """
    _ = redis_clean  # fixture-graph dep — Redis must be clean before the request
    suffix = uuid4().hex[:8]
    pw_hash = await hash_password(_OLD_PASSWORD)
    user = User(
        email=f"reset-confirm+{suffix}@example.com",
        password_hash=pw_hash,
        role=Role.RECEPTION,
        full_name="Reset Confirm User",
        email_verified=True,
    )
    db_session.add(user)
    await db_session.commit()

    raw_token = f"test-raw-token-{uuid4().hex}"
    token_row = PasswordResetToken(
        user_id=user.id,
        token_hash=_hash_token(raw_token),
        purpose="password_reset",
        expires_at=datetime.now(UTC) + timedelta(hours=1),
        audit_correlation_id=uuid4(),
    )
    db_session.add(token_row)
    await db_session.commit()
    return user, raw_token, token_row.id


@pytest_asyncio.fixture
async def seeded_user_with_expired_token(
    db_session: AsyncSession,
    redis_clean: Redis,
) -> tuple[User, str, UUID]:
    """Seed one user + one ``password_reset_tokens`` row already past ``expires_at``.

    D-44-15 anti-oracle: the atomic-consume predicate ``expires_at > NOW()``
    filters this row out; the service raises ``InvalidOrExpiredTokenError``
    (410) with the SAME body as replay/unknown.
    """
    _ = redis_clean
    suffix = uuid4().hex[:8]
    pw_hash = await hash_password(_OLD_PASSWORD)
    user = User(
        email=f"reset-expired+{suffix}@example.com",
        password_hash=pw_hash,
        role=Role.RECEPTION,
        full_name="Reset Expired User",
        email_verified=True,
    )
    db_session.add(user)
    await db_session.commit()

    raw_token = f"test-expired-token-{uuid4().hex}"
    token_row = PasswordResetToken(
        user_id=user.id,
        token_hash=_hash_token(raw_token),
        purpose="password_reset",
        expires_at=datetime.now(UTC) - timedelta(minutes=1),
        audit_correlation_id=uuid4(),
    )
    db_session.add(token_row)
    await db_session.commit()
    return user, raw_token, token_row.id


async def test_confirm_happy_path_atomic_consume_password_rotate_sessions_revoke(
    async_client: AsyncClient,
    db_session: AsyncSession,
    seeded_user_with_token: tuple[User, str, UUID],
) -> None:
    """RESET-02 happy-path — atomic-consume + password rotate + revoke-all + audit.

    Asserts the full D-44-16 sequence end-to-end:
      1. Pre-reset login establishes >=1 refresh-token family.
      2. /password-reset/confirm returns 200 + ``envelope(None)``.
      3. ``password_reset_tokens.consumed_at IS NOT NULL`` — atomic-consume landed.
      4. ``users.password_hash`` changed — Argon2id rotation worked.
      5. Old refresh cookie now 401 on /auth/refresh — invalidator slot fired
         (D-43-26 Protocol wiring exercised end-to-end).
      6. New /auth/login with the new password succeeds — Argon2 rehash sane.
      7. Exactly one ``password_reset_completed`` audit row with
         ``sessions_revoked_count >= 1`` and ``token_id == <seeded row id>``.
    """
    user, raw_token, token_row_id = seeded_user_with_token

    # 1. Pre-reset login to establish a refresh-token family.
    login_pre = await async_client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": _OLD_PASSWORD},
    )
    assert login_pre.status_code == 200, login_pre.text
    pre_refresh = async_client.cookies.get("sz_refresh")
    assert pre_refresh is not None, "login should have set sz_refresh cookie"

    # Snapshot the original hash so we can assert rotation.
    original_hash = await db_session.scalar(select(User.password_hash).where(User.id == user.id))
    assert original_hash is not None

    # 2. /password-reset/confirm — happy path.
    r = await async_client.post(
        "/api/v1/auth/password-reset/confirm",
        json={"token": raw_token, "newPassword": _NEW_PASSWORD},
    )
    assert r.status_code == 200, r.text
    assert r.json() == {"data": None}

    # 3. ``consumed_at IS NOT NULL`` — atomic-consume landed.
    consumed_at = await db_session.scalar(
        select(PasswordResetToken.consumed_at).where(PasswordResetToken.id == token_row_id)
    )
    assert consumed_at is not None, "atomic-consume must mark consumed_at"

    # 4. ``password_hash`` rotated.
    rotated_hash = await db_session.scalar(select(User.password_hash).where(User.id == user.id))
    assert rotated_hash is not None
    assert rotated_hash != original_hash, "password_hash should differ after rotate"

    # 5. Old refresh cookie now 401 on /auth/refresh — sessions revoked.
    r_refresh = await async_client.post("/api/v1/auth/refresh")
    assert r_refresh.status_code == 401, r_refresh.text
    # Either anti-oracle output is valid (mirrors test_users_session_invalidation
    # acceptance: family-reuse vs invalid-session both satisfy "user cannot
    # mint fresh access tokens"). Cardinal guarantee: 401 after reset.
    assert r_refresh.json()["code"] in {"invalid_session", "invalid_token"}

    # 6. New login with the new password succeeds — Argon2 rehash sane.
    # Clear cookies first so the stale sz_refresh doesn't taint the login.
    async_client.cookies.clear()
    login_post = await async_client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": _NEW_PASSWORD},
    )
    assert login_post.status_code == 200, login_post.text

    # 7. Audit row — exactly one password_reset_completed for this token.
    rows = (
        await db_session.scalars(
            select(AuditLog).where(
                AuditLog.action == "password_reset_completed",
                AuditLog.resource_id == user.id,
            )
        )
    ).all()
    assert len(rows) == 1, f"expected 1 password_reset_completed row; got {len(rows)}"
    row = rows[0]
    assert row.payload["user_id"] == str(user.id)
    assert row.payload["token_id"] == str(token_row_id)
    assert row.payload["sessions_revoked_count"] >= 1, (
        f"sessions_revoked_count should be >=1 (user had 1 active family); "
        f"got {row.payload['sessions_revoked_count']}"
    )


async def test_confirm_replay_returns_410_with_identical_body(
    async_client: AsyncClient,
    db_session: AsyncSession,
    seeded_user_with_token: tuple[User, str, UUID],
) -> None:
    """RESET-02 replay — second POST with the same token returns 410 (D-44-15).

    Anti-oracle: replay / expired / unknown collapse to the SAME 410 body
    (verified across this test + ``test_confirm_expired_token_returns_410…``).
    """
    user, raw_token, _token_row_id = seeded_user_with_token

    # First POST — happy path; consumes the token.
    r1 = await async_client.post(
        "/api/v1/auth/password-reset/confirm",
        json={"token": raw_token, "newPassword": _NEW_PASSWORD},
    )
    assert r1.status_code == 200, r1.text

    # Second POST with same token — atomic-consume returns zero rows (consumed_at
    # IS NOT NULL filters it out) → InvalidOrExpiredTokenError → 410.
    r2 = await async_client.post(
        "/api/v1/auth/password-reset/confirm",
        json={"token": raw_token, "newPassword": _NEW_PASSWORD},
    )
    assert r2.status_code == 410, r2.text
    body = r2.json()
    assert body["code"] == "invalid_or_expired_token"
    assert body["fields"] is None
    assert "message" in body  # message exists; exact text is implementation detail

    # The first POST already emitted exactly one password_reset_completed row.
    # The replay 410 MUST NOT emit a second one (no atomic-consume happened).
    completed_count = await db_session.scalar(
        select(func.count(AuditLog.id)).where(
            AuditLog.action == "password_reset_completed",
            AuditLog.resource_id == user.id,
        )
    )
    assert completed_count == 1, (
        f"replay 410 should NOT emit a second audit row; got count={completed_count}"
    )


async def test_confirm_expired_token_returns_410_with_identical_body(
    async_client: AsyncClient,
    db_session: AsyncSession,
    seeded_user_with_expired_token: tuple[User, str, UUID],
) -> None:
    """RESET-02 expired token — ``expires_at < now()`` row returns 410 (D-44-15).

    Anti-oracle parity with the replay 410 (same code, same shape — caller
    cannot tell which precondition failed).
    """
    _user, raw_token, token_row_id = seeded_user_with_expired_token

    r = await async_client.post(
        "/api/v1/auth/password-reset/confirm",
        json={"token": raw_token, "newPassword": _NEW_PASSWORD},
    )
    assert r.status_code == 410, r.text
    body = r.json()
    assert body["code"] == "invalid_or_expired_token"
    assert body["fields"] is None

    # ``consumed_at IS NULL`` — the atomic-consume predicate filtered this row out;
    # no rotation, no revoke-all, no audit emit happened.
    consumed_at = await db_session.scalar(
        select(PasswordResetToken.consumed_at).where(PasswordResetToken.id == token_row_id)
    )
    assert consumed_at is None, (
        "expired-token 410 should NOT mark consumed_at — atomic-consume must "
        "have filtered the row out via the ``expires_at > NOW()`` predicate"
    )


async def test_confirm_weak_password_returns_422_token_stays_valid_for_retry(
    async_client: AsyncClient,
    db_session: AsyncSession,
    seeded_user_with_token: tuple[User, str, UUID],
) -> None:
    """RESET-02 weak password — 422 BEFORE atomic-consume so token stays valid (D-44-17).

    The 8-char floor is enforced in ``confirm_password_reset`` BEFORE the
    call to ``_atomic_consume_token``. Therefore:
      - First POST with a 7-char password → 422 ``weak_password``.
      - ``consumed_at`` STILL NULL (no atomic-consume happened).
      - Second POST with the SAME token + a valid password → 200 (retry works).
    """
    _user, raw_token, token_row_id = seeded_user_with_token

    # 1. Weak password (< 8 chars) → 422 weak_password.
    r_weak = await async_client.post(
        "/api/v1/auth/password-reset/confirm",
        json={"token": raw_token, "newPassword": _WEAK_PASSWORD},
    )
    assert r_weak.status_code == 422, r_weak.text
    body = r_weak.json()
    assert body["code"] == "weak_password"
    assert body["fields"] is None

    # 2. ``consumed_at IS NULL`` — token still valid for retry within TTL.
    consumed_at_after_weak = await db_session.scalar(
        select(PasswordResetToken.consumed_at).where(PasswordResetToken.id == token_row_id)
    )
    assert consumed_at_after_weak is None, (
        "weak-password 422 MUST NOT consume the token (D-44-17 — strength "
        "check runs BEFORE atomic-consume so user can retry within TTL)"
    )

    # 3. Re-POST with the SAME token + a valid password → 200.
    r_retry = await async_client.post(
        "/api/v1/auth/password-reset/confirm",
        json={"token": raw_token, "newPassword": _NEW_PASSWORD},
    )
    assert r_retry.status_code == 200, r_retry.text
    assert r_retry.json() == {"data": None}

    # Token now consumed.
    consumed_at_after_retry = await db_session.scalar(
        select(PasswordResetToken.consumed_at).where(PasswordResetToken.id == token_row_id)
    )
    assert consumed_at_after_retry is not None


# Touch the structlog import so static analysis sees the dep is intentional
# (the logger-cache reset fixture is referenced by name from other Wave 4
# tests; keeping the import here avoids a future "unused import" lint hit
# if the fixture is moved into the auth conftest).
_ = structlog
