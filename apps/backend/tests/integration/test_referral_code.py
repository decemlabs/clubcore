"""Phase 96 Plan 96-03 — Referral code mint integration tests (REFER-01).

Proves:
  - Client GET /api/v1/client/referral/code returns 200 with a non-empty code
    (8 chars, all in CROCKFORD_ALPHABET) and shareUrl ending in /i/<code>.
  - Second GET returns the SAME code (idempotent — first binding wins).
  - Exactly one referral_code_generated audit row per client (second call adds none).
  - Two distinct clients get distinct codes.
  - No-auth request → 401.

Harness: SAVEPOINT db_session + ASGITransport (no real network — CLAUDE.md).
Client auth: OTP flow via _auth_as_client helper (mirrors test_loyalty_read.py).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit_models import AuditLog
from app.core.config import get_settings
from app.core.database import get_db
from app.core.permissions import Role
from app.core.redis import get_redis
from app.core.security import generate_otp_code, hash_password
from app.modules.auth.models import OtpCode, User
from app.modules.clients.models import Client
from app.modules.referrals.service import CROCKFORD_ALPHABET

pytestmark = pytest.mark.asyncio

_CROCKFORD_SET = set(CROCKFORD_ALPHABET)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def _overridden_app(
    app: FastAPI,
    db_session: AsyncSession,
) -> AsyncIterator[FastAPI]:
    """Install dependency overrides so route handlers use the SAVEPOINT session."""

    async def _override_get_db() -> AsyncIterator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_redis] = lambda: app.state.redis
    try:
        yield app
    finally:
        app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def http_client(_overridden_app: FastAPI) -> AsyncIterator[AsyncClient]:
    """ASGITransport client that persists cookies across requests."""
    transport = ASGITransport(app=_overridden_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c


@pytest.fixture(autouse=True)
def stub_otp_sender(app: FastAPI, monkeypatch: pytest.MonkeyPatch) -> None:
    """Replace real OTP sender with no-op for all tests in this module."""
    _ = app
    from app.modules.client_auth import service as client_auth_service

    async def _noop(chat_id: int, code: str) -> None:
        pass

    monkeypatch.setattr(client_auth_service, "_client_otp_sender", _noop)


@pytest_asyncio.fixture(autouse=True)
async def flush_redis(app: FastAPI) -> None:
    """Flush Redis before each test."""
    await app.state.redis.flushdb()


# ---------------------------------------------------------------------------
# Auth + seed helpers
# ---------------------------------------------------------------------------


async def _seed_staff(db_session: AsyncSession, suffix: str = "") -> User:
    user = User(
        email=f"ref-code-staff-{suffix or uuid4().hex[:8]}@example.com",
        password_hash=await hash_password("ref-code-staff-pw-secure"),
        role=Role.RECEPTION,
        full_name="Referral Code Test Staff",
    )
    db_session.add(user)
    await db_session.flush()
    return user


async def _seed_client(
    db_session: AsyncSession,
    staff: User,
    phone: str,
    first_name: str = "Тест",
) -> Client:
    client = Client(
        first_name=first_name,
        last_name="Реферал",
        phone=phone,
        telegram_user_id=abs(hash(phone)) % (10**9),
        created_by_user_id=staff.id,
    )
    db_session.add(client)
    await db_session.flush()
    return client


async def _auth_as_client(
    async_client: AsyncClient,
    db_session: AsyncSession,
    client: Client,
) -> None:
    """Request OTP → patch code → verify (mirrors test_loyalty_read.py helper)."""
    req = await async_client.post(
        "/api/v1/client/otp/request",
        json={"phone": client.phone},
    )
    assert req.status_code == 202, f"OTP request failed for {client.phone}: {req.text}"

    otp_row = await db_session.scalar(
        select(OtpCode).where(
            OtpCode.client_id == client.id,
            OtpCode.consumed_at.is_(None),
        )
    )
    assert otp_row is not None, f"OtpCode row not found for client {client.id}"

    settings = get_settings()
    raw_code, code_hash = generate_otp_code()
    otp_row.code_hash = code_hash
    otp_row.expires_at = datetime.now(tz=UTC) + timedelta(seconds=settings.otp_code_ttl_seconds)
    await db_session.commit()

    verify = await async_client.post(
        "/api/v1/client/otp/verify",
        json={"phone": client.phone, "code": raw_code},
    )
    assert verify.status_code == 200, f"OTP verify failed for {client.phone}: {verify.text}"


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_get_referral_code_returns_valid_code(
    http_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Client GET /client/referral/code → 200, code is 8-char Crockford, shareUrl ends /i/<code>."""
    staff = await _seed_staff(db_session, "code-valid")
    client = await _seed_client(db_session, staff, "+79200001001")
    await db_session.commit()

    await _auth_as_client(http_client, db_session, client)

    resp = await http_client.get("/api/v1/client/referral/code")
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]

    code = data["code"]
    share_url = data["shareUrl"]

    assert len(code) == 8, f"Expected 8-char code, got {len(code)!r}: {code!r}"
    assert all(c in _CROCKFORD_SET for c in code), (
        f"Code contains characters outside CROCKFORD_ALPHABET: {code!r}"
    )
    assert share_url.endswith(f"/i/{code}"), (
        f"shareUrl should end with /i/{code}, got {share_url!r}"
    )


async def test_get_referral_code_is_idempotent(
    http_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Second GET /client/referral/code returns the SAME code as the first call."""
    staff = await _seed_staff(db_session, "code-idem")
    client = await _seed_client(db_session, staff, "+79200001002")
    await db_session.commit()

    await _auth_as_client(http_client, db_session, client)

    resp1 = await http_client.get("/api/v1/client/referral/code")
    assert resp1.status_code == 200, resp1.text
    code1 = resp1.json()["data"]["code"]

    resp2 = await http_client.get("/api/v1/client/referral/code")
    assert resp2.status_code == 200, resp2.text
    code2 = resp2.json()["data"]["code"]

    assert code1 == code2, (
        f"Idempotency failed: first call returned {code1!r}, second call returned {code2!r}"
    )


async def test_get_referral_code_single_audit_row_on_two_calls(
    http_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Two GETs produce exactly one referral_code_generated audit row (idempotent)."""
    staff = await _seed_staff(db_session, "code-audit")
    client = await _seed_client(db_session, staff, "+79200001003")
    await db_session.commit()

    await _auth_as_client(http_client, db_session, client)

    # First call — mints the code
    resp1 = await http_client.get("/api/v1/client/referral/code")
    assert resp1.status_code == 200, resp1.text

    # Second call — idempotent, no new audit row
    resp2 = await http_client.get("/api/v1/client/referral/code")
    assert resp2.status_code == 200, resp2.text

    # Count audit rows for this client
    audit_rows = (
        await db_session.scalars(
            select(AuditLog).where(
                AuditLog.action == "referral_code_generated",
                AuditLog.resource_type == "referral",
            )
        )
    ).all()
    client_audits = [a for a in audit_rows if a.payload.get("client_id") == str(client.id)]
    assert len(client_audits) == 1, (
        f"Expected exactly 1 referral_code_generated audit row, got {len(client_audits)}"
    )


async def test_two_distinct_clients_get_distinct_codes(
    http_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Two distinct clients get distinct referral codes."""
    staff = await _seed_staff(db_session, "code-distinct")
    client_a = await _seed_client(db_session, staff, "+79200001004")
    client_b = await _seed_client(db_session, staff, "+79200001005")
    await db_session.commit()

    # Authenticate and get code for client A
    await _auth_as_client(http_client, db_session, client_a)
    resp_a = await http_client.get("/api/v1/client/referral/code")
    assert resp_a.status_code == 200, resp_a.text
    code_a = resp_a.json()["data"]["code"]

    # Log out client A cookies by creating a new independent client session
    transport = ASGITransport(app=http_client._transport.app)  # type: ignore[attr-defined]
    async with AsyncClient(transport=transport, base_url="http://testserver") as client_b_http:
        await _auth_as_client(client_b_http, db_session, client_b)
        resp_b = await client_b_http.get("/api/v1/client/referral/code")
        assert resp_b.status_code == 200, resp_b.text
        code_b = resp_b.json()["data"]["code"]

    assert code_a != code_b, (
        f"Two distinct clients should not share a referral code, both got {code_a!r}"
    )


async def test_get_referral_code_no_auth_returns_401(
    http_client: AsyncClient,
) -> None:
    """No client auth → GET /client/referral/code returns 401."""
    resp = await http_client.get("/api/v1/client/referral/code")
    assert resp.status_code == 401, resp.text
