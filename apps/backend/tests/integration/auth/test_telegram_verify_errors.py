"""Integration tests for /api/v1/auth/telegram/verify error modes (Phase 7 AUTH-TG-06).

Covers ALL SIX failure modes from D-13:

  | scenario               | HTTP | code             | fields                    |
  |------------------------|------|------------------|---------------------------|
  | token_unknown          | 404  | token_unknown    | None                      |
  | bot_not_started        | 409  | bot_not_started  | {deepLinkUrl}             |
  | otp_expired            | 410  | otp_expired      | None                      |
  | otp_invalid (1..4)     | 401  | otp_invalid      | {attemptsRemaining: 4..1} |
  | otp_max_attempts (5)   | 429  | otp_max_attempts | None                      |
  | otp_consumed (replay)  | 409  | otp_consumed     | None                      |

Each test arranges the OtpCode state via direct telegram_service calls under
the SAVEPOINT-rolled db_session (Phase 5 D-22), then hits /verify and asserts
the AppError envelope shape.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest_asyncio
from fastapi import FastAPI
from httpx import AsyncClient
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import Role
from app.core.security import hash_password
from app.modules.auth import telegram_service
from app.modules.auth.models import OtpCode, User
from tests.conftest import StubTelegramSender

OWNER_EMAIL = "tg-errors@example.com"
OWNER_PASSWORD = "hunter22hunter22"  # noqa: S105 -- test password literal (>=12 chars)
TG_USERNAME = "tg_errors_user"
TG_CHAT_ID = 7654321


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def redis_clean(app: FastAPI) -> Redis:
    client: Redis = app.state.redis
    await client.flushdb()
    return client


@pytest_asyncio.fixture
async def seeded_owner_with_tg(
    db_session: AsyncSession,
    redis_clean: Redis,
) -> User:
    user = User(
        email=OWNER_EMAIL,
        password_hash=await hash_password(OWNER_PASSWORD),
        role=Role.OWNER,
        full_name="TG Errors Owner",
        telegram_username=TG_USERNAME,
    )
    db_session.add(user)
    await db_session.commit()
    return user


# ---------------------------------------------------------------------------
# Helpers -- drive the OtpCode row to the target state for each scenario.
# ---------------------------------------------------------------------------


async def _arrange_bot_not_started(db_session: AsyncSession) -> str:
    """Only /start was called -- code_hash IS NULL."""
    raw_token, _hash = await telegram_service.start_deep_link(db_session)
    return raw_token


async def _arrange_normal_otp(db_session: AsyncSession) -> tuple[str, str]:
    """/start + bot bind + commit_otp -- OtpCode ready to verify (code_hash set)."""
    raw_token, _hash = await telegram_service.start_deep_link(db_session)
    user_obj, raw_code, otp_row = await telegram_service.bind_and_issue(
        db_session,
        raw_token,
        TG_CHAT_ID,
        TG_USERNAME,
    )
    await telegram_service.commit_otp(db_session, otp_row, user_obj, raw_code, TG_CHAT_ID)
    return raw_token, raw_code


# ---------------------------------------------------------------------------
# Scenario 1: token_unknown (404)
# ---------------------------------------------------------------------------


async def test_verify_token_unknown_returns_404(
    async_client: AsyncClient,
    redis_clean: Redis,
) -> None:
    """Unknown deep_link_token -> 404 token_unknown."""
    _ = redis_clean
    response = await async_client.post(
        "/api/v1/auth/telegram/verify",
        json={"deepLinkToken": "x" * 43, "code": "123456"},
    )
    assert response.status_code == 404, response.text
    body = response.json()
    assert body["code"] == "token_unknown"


# ---------------------------------------------------------------------------
# Scenario 2: bot_not_started (409 + fields.deepLinkUrl)
# ---------------------------------------------------------------------------


async def test_verify_bot_not_started_carries_deep_link_url(
    async_client: AsyncClient,
    db_session: AsyncSession,
    redis_clean: Redis,
) -> None:
    """OtpCode found but code_hash IS NULL -> 409 bot_not_started + fields.deepLinkUrl."""
    _ = redis_clean
    raw_token = await _arrange_bot_not_started(db_session)
    response = await async_client.post(
        "/api/v1/auth/telegram/verify",
        json={"deepLinkToken": raw_token, "code": "000000"},
    )
    assert response.status_code == 409, response.text
    body = response.json()
    assert body["code"] == "bot_not_started"
    assert body["fields"] is not None
    assert "deepLinkUrl" in body["fields"]
    assert body["fields"]["deepLinkUrl"].startswith("https://t.me/")
    assert raw_token in body["fields"]["deepLinkUrl"]


# ---------------------------------------------------------------------------
# Scenario 3: otp_expired (410)
# ---------------------------------------------------------------------------


async def test_verify_otp_expired_returns_410(
    async_client: AsyncClient,
    db_session: AsyncSession,
    seeded_owner_with_tg: User,
    stub_telegram_sender: StubTelegramSender,
) -> None:
    """expires_at < now -> 410 otp_expired."""
    _ = seeded_owner_with_tg, stub_telegram_sender
    raw_token, _raw_code = await _arrange_normal_otp(db_session)
    # Force expiry -- directly mutate the OtpCode row.
    row = (await db_session.execute(select(OtpCode))).scalar_one()
    row.expires_at = datetime.now(tz=UTC) - timedelta(seconds=1)
    await db_session.commit()

    response = await async_client.post(
        "/api/v1/auth/telegram/verify",
        json={"deepLinkToken": raw_token, "code": "000000"},
    )
    assert response.status_code == 410, response.text
    assert response.json()["code"] == "otp_expired"


# ---------------------------------------------------------------------------
# Scenarios 4 + 5: otp_invalid (401 with attemptsRemaining 4..1) then otp_max_attempts (429)
# ---------------------------------------------------------------------------


async def test_verify_invalid_then_max_attempts(
    async_client: AsyncClient,
    db_session: AsyncSession,
    seeded_owner_with_tg: User,
    stub_telegram_sender: StubTelegramSender,
) -> None:
    """4 misses -> 401 otp_invalid; 5th miss -> 429 otp_max_attempts."""
    _ = seeded_owner_with_tg, stub_telegram_sender
    raw_token, raw_code = await _arrange_normal_otp(db_session)
    # Guarantee wrong_code != raw_code (paranoid fall-through).
    wrong_code = "999999" if raw_code != "999999" else "888888"

    # First 4 misses -> 401 otp_invalid with attemptsRemaining counting down.
    for expected_remaining in (4, 3, 2, 1):
        response = await async_client.post(
            "/api/v1/auth/telegram/verify",
            json={"deepLinkToken": raw_token, "code": wrong_code},
        )
        assert response.status_code == 401, (
            f"attempt remaining={expected_remaining}, body={response.text}"
        )
        body = response.json()
        assert body["code"] == "otp_invalid"
        assert body["fields"] is not None
        assert body["fields"]["attemptsRemaining"] == expected_remaining

    # 5th miss -> 429 otp_max_attempts.
    response = await async_client.post(
        "/api/v1/auth/telegram/verify",
        json={"deepLinkToken": raw_token, "code": wrong_code},
    )
    assert response.status_code == 429, response.text
    assert response.json()["code"] == "otp_max_attempts"


# ---------------------------------------------------------------------------
# Scenario 6: otp_consumed (409 -- replay)
# ---------------------------------------------------------------------------


async def test_verify_already_consumed_returns_409(
    async_client: AsyncClient,
    db_session: AsyncSession,
    seeded_owner_with_tg: User,
    stub_telegram_sender: StubTelegramSender,
) -> None:
    """Successful verify followed by replay of same code -> 409 otp_consumed (D-20)."""
    _ = seeded_owner_with_tg, stub_telegram_sender
    raw_token, raw_code = await _arrange_normal_otp(db_session)

    # First /verify -- success.
    r1 = await async_client.post(
        "/api/v1/auth/telegram/verify",
        json={"deepLinkToken": raw_token, "code": raw_code},
    )
    assert r1.status_code == 200, r1.text

    # Second /verify -- replay -> 409 otp_consumed.
    r2 = await async_client.post(
        "/api/v1/auth/telegram/verify",
        json={"deepLinkToken": raw_token, "code": raw_code},
    )
    assert r2.status_code == 409, r2.text
    assert r2.json()["code"] == "otp_consumed"
