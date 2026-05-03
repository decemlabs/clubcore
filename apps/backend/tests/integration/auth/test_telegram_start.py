"""Integration tests for POST /api/v1/auth/telegram/start (Phase 7 AUTH-TG-01).

Asserts:
  - 200 with {deepLinkUrl, deepLinkToken} envelope
  - deepLinkUrl starts with https://t.me/ and carries ?start=<token>
  - deepLinkToken is a high-entropy URL-safe string (>=32 chars)
  - OtpCode row created with code_hash IS NULL (D-11 step 1 invariant)
"""

from __future__ import annotations

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit_models import AuditLog
from app.modules.auth.models import OtpCode


async def test_telegram_start_returns_deep_link_and_creates_otp_row(
    async_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """AUTH-TG-01: returns {deepLinkUrl, deepLinkToken} + OtpCode w/ code_hash IS NULL."""
    response = await async_client.post("/api/v1/auth/telegram/start")
    assert response.status_code == 200, response.text

    body = response.json()
    assert "data" in body
    deep_link_url = body["data"]["deepLinkUrl"]
    deep_link_token = body["data"]["deepLinkToken"]
    assert deep_link_url.startswith("https://t.me/")
    assert "?start=" in deep_link_url
    assert deep_link_token in deep_link_url
    # secrets.token_urlsafe(32) -> 43 chars; allow some slack but require entropy.
    assert len(deep_link_token) >= 32

    # OtpCode row created with code_hash IS NULL (D-11 step 1 invariant).
    rows = (await db_session.execute(select(OtpCode))).scalars().all()
    assert len(rows) >= 1
    matching = [r for r in rows if r.code_hash is None]
    assert len(matching) >= 1, "expected at least one OtpCode with code_hash IS NULL"


async def test_telegram_start_writes_deep_link_issued_audit_row(
    async_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """AUDIT-02 + D-04: /telegram/start writes telegram_deep_link_issued row
    with actor_user_id NULL (D-06 — no user identified yet)."""
    r = await async_client.post("/api/v1/auth/telegram/start")
    assert r.status_code == 200

    rows = (
        await db_session.scalars(
            select(AuditLog).where(AuditLog.action == "telegram_deep_link_issued")
        )
    ).all()
    assert len(rows) >= 1
    row = rows[-1]
    assert row.actor_user_id is None  # D-06 — actor-less
    assert row.resource_type == "otp"
