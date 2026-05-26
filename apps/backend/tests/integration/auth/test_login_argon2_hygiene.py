"""Integration tests for HYG-01 — Argon2 verify-error path hardening (Phase 23 D-23-15, D-23-16).

Covers:
  - Corrupted Argon2 hash → 401 invalid_credentials (NOT 500).
  - structlog WARNING event=login_verify_error with {reason, email_lower, ip} (D-23-13).
  - Audit row login_failed stays generic reason='invalid_credentials' (AUTH-EP-02 invariant).
  - D-23-14 negative: structlog WARNING MUST NOT carry password, hash bytes, user_id.
  - Rate-limit chokepoint BEFORE verify call: 6th attempt returns 429 (D-23-16).
"""

from __future__ import annotations

import pytest_asyncio
from fastapi import FastAPI
from httpx import AsyncClient
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from structlog.testing import capture_logs

from app.core.audit_models import AuditLog
from app.core.permissions import Role
from app.modules.auth.models import User

HYGIENE_EMAIL = "hygiene-owner@example.com"
CORRUPTED_HASH = "NOT_A_VALID_ARGON2_HASH"  # intentionally corrupted for HYG-01 test


@pytest_asyncio.fixture
async def redis_clean(app: FastAPI) -> Redis:
    """Flush Redis between tests so rate-limit keys don't bleed across tests."""
    client: Redis = app.state.redis
    await client.flushdb()
    return client


@pytest_asyncio.fixture
async def seeded_corrupted_user(db_session: AsyncSession, redis_clean: Redis) -> User:
    """Insert a user whose password_hash is intentionally corrupted (not a valid Argon2id hash).

    Bypasses hash_password() to simulate data corruption or a botched migration.
    """
    user = User(
        email=HYGIENE_EMAIL,
        password_hash=CORRUPTED_HASH,
        role=Role.OWNER,
        full_name="Hygiene Owner",
    )
    db_session.add(user)
    await db_session.commit()
    return user


async def test_login_with_corrupted_argon2_hash_returns_401_and_emits_warning(
    async_client: AsyncClient,
    db_session: AsyncSession,
    seeded_corrupted_user: User,
) -> None:
    """HYG-01 D-23-15: corrupted password_hash → 401 invalid_credentials + structlog WARNING.

    Pre-Phase-23 baseline: this path returned 500 (InvalidHashError bubbled to the default
    FastAPI handler). Post-Phase-23: wrapped by verify_password → InvalidPassword → 401.
    The structlog WARNING carries the distinguishing reason for ops triage.
    """
    with capture_logs() as captured:
        response = await async_client.post(
            "/api/v1/auth/login",
            json={"email": HYGIENE_EMAIL, "password": "hunter22hunter22"},
        )

    # HTTP layer: must be 401, not 500.
    assert response.status_code == 401, response.text
    body = response.json()
    assert body["code"] == "invalid_credentials"

    # structlog WARNING must be present.
    warning_entries = [c for c in captured if c.get("event") == "login_verify_error"]
    assert warning_entries, f"Expected login_verify_error in captured logs; got: {captured}"
    warn = warning_entries[-1]

    # Reason must be one of the three classified values.
    assert warn.get("reason") in {"invalid_hash", "verify_mismatch", "other"}, (
        f"Unexpected reason value: {warn.get('reason')!r}"
    )
    # email_lower must match the seeded email.
    assert warn.get("email_lower") == HYGIENE_EMAIL.lower()

    # D-23-14 negative-assert: WARNING MUST NOT carry raw password, hash, user_id, etc.
    for forbidden_key in ("password", "password_hash", "user_id", "telegram_chat_id", "headers"):
        assert forbidden_key not in warn, (
            f"Forbidden key '{forbidden_key}' found in login_verify_error log entry: {warn}"
        )

    # Audit DB: login_failed row written with generic reason='invalid_credentials'.
    # This is the Phase 5 AUTH-EP-02 timing/info equivalence invariant.
    rows = (
        await db_session.scalars(select(AuditLog).where(AuditLog.action == "login_failed"))
    ).all()
    assert rows, "Expected at least one login_failed audit row"
    row = rows[-1]
    assert row.actor_user_id is None, "login_failed audit row must have NULL actor (D-06)"
    assert row.resource_type == "login_attempt"
    assert row.payload["reason"] == "invalid_credentials", (
        "Audit row reason must stay generic (AUTH-EP-02 timing/info equivalence)"
    )
    # Audit row MUST NOT carry a distinguishing reason (e.g. 'invalid_hash').
    assert row.payload["reason"] != "invalid_hash"


async def test_login_rate_limit_chokepoints_before_verify_call(
    async_client: AsyncClient,
    db_session: AsyncSession,
    seeded_corrupted_user: User,
    redis_clean: Redis,
) -> None:
    """HYG-01 D-23-16: rate-limit (5/15min) fires BEFORE the Argon2 verify call.

    6th attempt against a corrupted-hash user returns 429 too_many_requests.
    This proves the rate-limit counter is incremented on the FAILED verify path
    and that check_login_rate is called BEFORE verify_password (Phase 5 AUTH-EP-02).
    """
    # 5 failed attempts — all should return 401 invalid_credentials.
    for attempt in range(5):
        r = await async_client.post(
            "/api/v1/auth/login",
            json={"email": HYGIENE_EMAIL, "password": "hunter22hunter22"},
        )
        assert r.status_code == 401, (
            f"Attempt {attempt + 1}: expected 401, got {r.status_code}: {r.text}"
        )
        assert r.json()["code"] == "invalid_credentials"

    # 6th attempt — rate-limit should fire BEFORE verify (D-23-16, Phase 5 D-18).
    r6 = await async_client.post(
        "/api/v1/auth/login",
        json={"email": HYGIENE_EMAIL, "password": "hunter22hunter22"},
    )
    assert r6.status_code == 429, f"Expected 429 on 6th attempt, got {r6.status_code}: {r6.text}"
    assert r6.json()["code"] == "rate_limited"
