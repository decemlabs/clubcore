"""Phase 82 Plan 82-02 — Loyalty client read endpoints integration tests (LOYL-01/LOYL-02).

Proves:
  - GET /api/v1/client/loyalty/balance returns balanceKopecks = SUM for the
    authenticated client only.
  - Client A cannot see Client B's balance/history (IDOR: A's principal returns
    only A's rows; balance excludes B's accruals — T-82-05).
  - GET /api/v1/client/loyalty/history returns {items,total,page,pageSize};
    items carry signed amountKopecks, type, createdAt; ordered DESC; pagination honored.
  - Empty ledger returns balanceKopecks=0 (not 404 — D-69-03).
  - No-auth requests return 401.

Harness: SAVEPOINT db_session + ASGITransport async_client (no real network).
Client auth: OTP flow via inline _auth_as_client helper.
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

from app.core.config import get_settings
from app.core.database import get_db
from app.core.permissions import Role
from app.core.redis import get_redis
from app.core.security import generate_otp_code, hash_password
from app.modules.auth.models import OtpCode, User
from app.modules.clients.models import Client
from app.modules.loyalty.service import accrue_welcome_bonus

pytestmark = pytest.mark.asyncio


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
# Auth helper for client OTP flow
# ---------------------------------------------------------------------------


async def _auth_as_client(
    async_client: AsyncClient,
    db_session: AsyncSession,
    client: Client,
) -> str:
    """Request OTP → patch code → verify → return cc_client_access token value.

    Mirrors the helper in client_portal/test_idor_sweep.py: reads the OtpCode
    row and replaces the hash with a deterministic known code so the verify
    step succeeds without a real Telegram DM.
    """
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

    set_cookies = verify.headers.get_list("set-cookie")
    access_cookie = next(
        (c for c in set_cookies if c.startswith("cc_client_access=")),
        None,
    )
    assert access_cookie is not None, "cc_client_access cookie missing from verify response"
    return access_cookie.split("=", 1)[1].split(";", 1)[0]


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------


async def _seed_staff(db_session: AsyncSession, suffix: str = "") -> User:
    user = User(
        email=f"loyalty-read-staff-{suffix or uuid4().hex[:8]}@example.com",
        password_hash=await hash_password("loyalty-read-staff-pw-secure"),
        role=Role.RECEPTION,
        full_name="Loyalty Read Test Staff",
    )
    db_session.add(user)
    await db_session.flush()
    return user


async def _seed_client(
    db_session: AsyncSession,
    staff: User,
    phone: str,
) -> Client:
    client = Client(
        first_name="Читатель",
        last_name="Бонусов",
        phone=phone,
        telegram_user_id=abs(hash(phone)) % (10**9),
        created_by_user_id=staff.id,
    )
    db_session.add(client)
    await db_session.flush()
    return client


# ---------------------------------------------------------------------------
# Behavior tests
# ---------------------------------------------------------------------------


async def test_balance_empty_ledger_returns_zero(
    http_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Empty loyalty ledger → GET balance returns 200 with balanceKopecks=0 (D-69-03)."""
    staff = await _seed_staff(db_session, "bal-empty")
    client = await _seed_client(db_session, staff, "+79160002201")
    await db_session.commit()

    await _auth_as_client(http_client, db_session, client)

    resp = await http_client.get("/api/v1/client/loyalty/balance")
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["balanceKopecks"] == 0


async def test_balance_returns_sum_after_welcome_accrual(
    http_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """After welcome accrual → GET balance returns balanceKopecks = 50000."""
    staff = await _seed_staff(db_session, "bal-sum")
    client = await _seed_client(db_session, staff, "+79160002202")
    await db_session.flush()
    await accrue_welcome_bonus(db_session, client_id=client.id)
    await db_session.commit()

    await _auth_as_client(http_client, db_session, client)

    resp = await http_client.get("/api/v1/client/loyalty/balance")
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["balanceKopecks"] == 50_000


async def test_balance_no_auth_returns_401(
    http_client: AsyncClient,
) -> None:
    """No auth → GET balance returns 401."""
    resp = await http_client.get("/api/v1/client/loyalty/balance")
    assert resp.status_code == 401


async def test_history_empty_ledger(
    http_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Empty ledger → GET history returns {items:[],total:0,page:1,pageSize:20}."""
    staff = await _seed_staff(db_session, "hist-empty")
    client = await _seed_client(db_session, staff, "+79160002203")
    await db_session.commit()

    await _auth_as_client(http_client, db_session, client)

    resp = await http_client.get("/api/v1/client/loyalty/history")
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["items"] == []
    assert data["total"] == 0
    assert data["page"] == 1
    assert data["pageSize"] == 20


async def test_history_after_welcome_has_signed_amount(
    http_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Welcome accrual → history item has type='welcome', amountKopecks=50000 (signed positive)."""
    staff = await _seed_staff(db_session, "hist-welcome")
    client = await _seed_client(db_session, staff, "+79160002204")
    await db_session.flush()
    await accrue_welcome_bonus(db_session, client_id=client.id)
    await db_session.commit()

    await _auth_as_client(http_client, db_session, client)

    resp = await http_client.get("/api/v1/client/loyalty/history")
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["total"] == 1
    assert len(data["items"]) == 1
    item = data["items"][0]
    assert item["type"] == "welcome"
    assert item["amountKopecks"] == 50_000
    assert "id" in item
    assert "createdAt" in item


async def test_history_no_auth_returns_401(
    http_client: AsyncClient,
) -> None:
    """No auth → GET history returns 401."""
    resp = await http_client.get("/api/v1/client/loyalty/history")
    assert resp.status_code == 401


async def test_history_pagination_honored(
    http_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """pagination: pageSize=1 returns exactly 1 item, total reflects all rows."""
    staff = await _seed_staff(db_session, "hist-page")
    client = await _seed_client(db_session, staff, "+79160002205")
    await db_session.flush()
    # Seed 2 accruals: welcome + a direct second insert (different entry_type to bypass UNIQUE).
    await accrue_welcome_bonus(db_session, client_id=client.id)
    # Insert a second row directly (owner_grant, no conflict guard).
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    from app.modules.loyalty.models import LoyaltyLedger

    await db_session.execute(
        pg_insert(LoyaltyLedger).values(
            client_id=client.id,
            entry_type="owner_grant",
            amount_kopecks=10_000,
            category="manual",
            reason="pagination test",
        )
    )
    await db_session.commit()

    await _auth_as_client(http_client, db_session, client)

    resp = await http_client.get("/api/v1/client/loyalty/history?pageSize=1")
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["total"] == 2
    assert len(data["items"]) == 1
    assert data["pageSize"] == 1
    assert data["page"] == 1


# ---------------------------------------------------------------------------
# IDOR tests — T-82-05
# ---------------------------------------------------------------------------


async def test_idor_balance_client_a_does_not_see_client_b_accrual(
    http_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """IDOR: client A's balance endpoint excludes client B's welcome accrual."""
    staff = await _seed_staff(db_session, "idor-bal")
    client_a = await _seed_client(db_session, staff, "+79160002210")
    client_b = await _seed_client(db_session, staff, "+79160002211")
    await db_session.flush()
    # Only client_b gets the welcome bonus.
    await accrue_welcome_bonus(db_session, client_id=client_b.id)
    await db_session.commit()

    # Authenticate as client_a.
    await _auth_as_client(http_client, db_session, client_a)

    resp = await http_client.get("/api/v1/client/loyalty/balance")
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["balanceKopecks"] == 0, (
        f"IDOR: client A saw client B's accrual: balanceKopecks={data['balanceKopecks']}"
    )


async def test_idor_history_client_a_does_not_see_client_b_rows(
    http_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """IDOR: client A's history endpoint excludes client B's ledger rows."""
    staff = await _seed_staff(db_session, "idor-hist")
    client_a = await _seed_client(db_session, staff, "+79160002212")
    client_b = await _seed_client(db_session, staff, "+79160002213")
    await db_session.flush()
    # Only client_b gets the welcome bonus.
    await accrue_welcome_bonus(db_session, client_id=client_b.id)
    await db_session.commit()

    # Authenticate as client_a.
    await _auth_as_client(http_client, db_session, client_a)

    resp = await http_client.get("/api/v1/client/loyalty/history")
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["total"] == 0, f"IDOR: client A saw client B's rows: total={data['total']}"
    assert data["items"] == [], "IDOR: client A received items from client B's ledger"


async def test_idor_balance_client_b_sees_only_own_rows(
    http_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """IDOR reverse: client B's balance only reflects client B's accruals."""
    staff = await _seed_staff(db_session, "idor-rev")
    client_a = await _seed_client(db_session, staff, "+79160002214")
    client_b = await _seed_client(db_session, staff, "+79160002215")
    await db_session.flush()
    # Only client_a gets the welcome bonus.
    await accrue_welcome_bonus(db_session, client_id=client_a.id)
    await db_session.commit()

    # Authenticate as client_b.
    await _auth_as_client(http_client, db_session, client_b)

    resp = await http_client.get("/api/v1/client/loyalty/balance")
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["balanceKopecks"] == 0, (
        f"IDOR (reverse): client B saw client A's accrual: balanceKopecks={data['balanceKopecks']}"
    )
