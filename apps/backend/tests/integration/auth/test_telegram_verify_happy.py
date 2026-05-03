"""Integration test for POST /api/v1/auth/telegram/verify happy path.

Phase 7 AUTH-TG-02 + AUTH-TG-04 + AUTH-TG-06 -- end-to-end flow:

  /start -> direct telegram_service.bind_and_issue + commit_otp (simulating bot
  under same SAVEPOINT, D-15) -> /verify with raw_code -> 200 + sz_access /
  sz_refresh / sportzal_csrf cookies + structlog otp_consumed AND
  login_success(channel='telegram').

Per CONTEXT D-15/D-16: handler tests run direct service calls; no live ptb
event loop. The stub_telegram_sender fixture monkeypatches the sender so any
incidental DM call is a no-op recorder.
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
from app.core.security import hash_password
from app.modules.auth import telegram_service
from app.modules.auth.models import User
from tests.conftest import StubTelegramSender

OWNER_EMAIL = "tg-owner@example.com"
OWNER_PASSWORD = "hunter22hunter22"  # noqa: S105 -- test password literal (>=12 chars)
TG_USERNAME = "owner_tg"
TG_CHAT_ID = 1234567


@pytest_asyncio.fixture
async def redis_clean(app: FastAPI) -> Redis:
    """Flush Redis between tests so rate-limit + session keys don't bleed."""
    client: Redis = app.state.redis
    await client.flushdb()
    return client


@pytest_asyncio.fixture
async def seeded_owner_with_tg(
    db_session: AsyncSession,
    redis_clean: Redis,
) -> User:
    """Seeded owner with telegram_username pre-populated (mimics seed script D-03)."""
    user = User(
        email=OWNER_EMAIL,
        password_hash=await hash_password(OWNER_PASSWORD),
        role=Role.OWNER,
        full_name="TG Owner",
        telegram_username=TG_USERNAME,
    )
    db_session.add(user)
    await db_session.commit()
    return user


async def test_telegram_verify_happy_path(
    async_client: AsyncClient,
    db_session: AsyncSession,
    seeded_owner_with_tg: User,
    stub_telegram_sender: StubTelegramSender,
) -> None:
    """Full flow: /start -> bot bind+commit (direct call) -> /verify -> cookies + audit."""
    # Stub fixture is consumed implicitly: any sender call routed via the monkeypatch
    # becomes a no-op recorder. Mark it used for the type checker.
    _ = stub_telegram_sender

    # 1. /start -- get deep_link_token.
    r = await async_client.post("/api/v1/auth/telegram/start")
    assert r.status_code == 200
    deep_link_token = r.json()["data"]["deepLinkToken"]

    # 2. Simulate bot /start <token> handler under same SAVEPOINT (D-15: no live ptb).
    user, raw_code, otp_row = await telegram_service.bind_and_issue(
        db_session,
        deep_link_token,
        TG_CHAT_ID,
        TG_USERNAME,
    )
    # Sender returns ok=True by default (stub), so we directly call commit_otp.
    await telegram_service.commit_otp(db_session, otp_row, user, raw_code, TG_CHAT_ID)

    # 3. /verify with the raw code.
    with capture_logs() as caplog:
        verify = await async_client.post(
            "/api/v1/auth/telegram/verify",
            json={"deepLinkToken": deep_link_token, "code": raw_code},
        )
    assert verify.status_code == 200, verify.text

    # 4. Three cookies present (AUTH-TG-04 -- same shape as /login).
    set_cookies = verify.headers.get_list("set-cookie")
    joined = "\n".join(set_cookies)
    assert "sz_access=" in joined
    assert "sz_refresh=" in joined
    assert "sportzal_csrf=" in joined

    # 5. Response body shape mirrors /login.
    body = verify.json()
    assert body["data"]["user"]["fullName"] == "TG Owner"
    assert body["data"]["user"]["role"] == "owner"
    assert body["data"]["user"]["id"] == str(seeded_owner_with_tg.id)

    # 6. Audit events: otp_consumed (service) + login_success(channel='telegram') (router).
    events = [c.get("event") for c in caplog]
    assert "otp_consumed" in events, f"events={events}"
    assert "login_success" in events, f"events={events}"
    login_evt = next(c for c in caplog if c.get("event") == "login_success")
    assert login_evt.get("channel") == "telegram"

    # 7. Raw code never logged (T-07-38 mitigation).
    for entry in caplog:
        for value in entry.values():
            assert raw_code not in str(value), f"raw OTP code leaked in event: {entry}"

    # 8. AUDIT-02: otp_consumed audit_log row exists with the upserted user.id.
    rows = (
        await db_session.scalars(
            select(AuditLog).where(AuditLog.action == "otp_consumed")
        )
    ).all()
    assert len(rows) >= 1
    row = rows[-1]
    assert row.actor_user_id is not None  # bound user (D-04 row 9)
    assert row.resource_type == "otp"
