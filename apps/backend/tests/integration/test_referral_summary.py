"""Phase 98 Plan 98-01 — GET /api/v1/client/referral/summary integration tests (REFER-06).

Proves:
  - Empty: client with a code, zero captures → invitees == [], accruedKopecks == 0.
  - Pending: capture exists, no accrual row → status "pending", bonusKopecks 0.
  - Joined: capture + referral_accrual row → status "joined", bonusKopecks > 0,
    accruedKopecks reflects the SUM.
  - PII guard: each invitee's keys == {firstName, joinedAt, status, bonusKopecks};
    lastName absent; no referee client_id exposed.
  - shareUrl ends with /i/<code>.
  - No-auth → 401.
  - IDOR: client B's summary never contains client A's invitees.

Harness: SAVEPOINT db_session + ASGITransport (no real network — CLAUDE.md).
Client auth: OTP flow via _auth_as_client helper (mirrors test_referral_code.py).
Seed helpers for referral_captures + loyalty_ledger accrual rows mirror
test_referral_crediting.py.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.core.permissions import Role
from app.core.redis import get_redis
from app.core.security import generate_otp_code, hash_password
from app.modules.auth.models import OtpCode, User
from app.modules.clients.models import Client
from app.modules.referrals.models import ReferralCapture, ReferralCode

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Fixtures (verbatim from test_referral_code.py)
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
# Auth + seed helpers (verbatim from test_referral_code.py)
# ---------------------------------------------------------------------------


async def _seed_staff(db_session: AsyncSession, suffix: str = "") -> User:
    user = User(
        email=f"ref-sum-staff-{suffix or uuid4().hex[:8]}@example.com",
        password_hash=await hash_password("ref-sum-staff-pw-secure"),
        role=Role.RECEPTION,
        full_name="Referral Summary Test Staff",
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
    """Request OTP → patch code → verify (mirrors test_referral_code.py helper)."""
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
# Seed helpers for referral data (mirrors test_referral_crediting.py)
# ---------------------------------------------------------------------------


async def _seed_referral_code(
    db_session: AsyncSession,
    *,
    client_id: UUID,
) -> UUID:
    """Insert a referral_codes row for client_id. Returns the row id."""
    code_str = f"SUM{uuid4().hex[:8].upper()[:8]}"  # ensure exactly 8 chars
    rc = ReferralCode(client_id=client_id, code=code_str)
    db_session.add(rc)
    await db_session.flush()
    return rc.id


async def _seed_referral_capture(
    db_session: AsyncSession,
    *,
    referee_client_id: UUID,
    referrer_client_id: UUID,
    referral_code_id: UUID,
) -> UUID:
    """Insert a referral_captures row binding referee → referrer. Returns the row id."""
    capture = ReferralCapture(
        referee_client_id=referee_client_id,
        referrer_client_id=referrer_client_id,
        referral_code_id=referral_code_id,
    )
    db_session.add(capture)
    await db_session.flush()
    return capture.id


async def _seed_referral_accrual(
    db_session: AsyncSession,
    *,
    referrer_client_id: UUID,
    capture_id: UUID,
    amount_kopecks: int = 50_000,
) -> None:
    """Insert a referral_accrual loyalty_ledger row for the referrer."""
    await db_session.execute(
        text(
            "INSERT INTO loyalty_ledger "
            "(client_id, entry_type, amount_kopecks, referral_capture_id) "
            "VALUES (:cid, 'referral_accrual', :amount, :cap_id)"
        ),
        {
            "cid": str(referrer_client_id),
            "amount": amount_kopecks,
            "cap_id": str(capture_id),
        },
    )
    await db_session.flush()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_summary_empty_returns_empty_invitees_and_zero_accrued(
    http_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Client with a referral code but zero captures → invitees == [], accruedKopecks == 0."""
    staff = await _seed_staff(db_session, "empty")
    client = await _seed_client(db_session, staff, "+79200002001")
    await db_session.commit()

    await _auth_as_client(http_client, db_session, client)

    resp = await http_client.get("/api/v1/client/referral/summary")
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]

    assert data["invitees"] == [], f"Expected empty invitees, got {data['invitees']!r}"
    assert data["accruedKopecks"] == 0, (
        f"Expected 0 accruedKopecks, got {data['accruedKopecks']!r}"
    )
    assert "code" in data and len(data["code"]) > 0
    assert "shareUrl" in data


async def test_summary_pending_invitee_status_and_zero_bonus(
    http_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Capture exists but no accrual row → status='pending', bonusKopecks=0."""
    staff = await _seed_staff(db_session, "pending")
    referrer = await _seed_client(db_session, staff, "+79200002002", first_name="Иван")
    referee = await _seed_client(db_session, staff, "+79200002003", first_name="Мария")
    await db_session.commit()

    # Seed code + capture (no accrual row yet — referee hasn't paid)
    code_id = await _seed_referral_code(db_session, client_id=referrer.id)
    await _seed_referral_capture(
        db_session,
        referee_client_id=referee.id,
        referrer_client_id=referrer.id,
        referral_code_id=code_id,
    )
    await db_session.commit()

    await _auth_as_client(http_client, db_session, referrer)

    resp = await http_client.get("/api/v1/client/referral/summary")
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]

    assert len(data["invitees"]) == 1, f"Expected 1 invitee, got {data['invitees']!r}"
    inv = data["invitees"][0]
    assert inv["status"] == "pending", f"Expected pending, got {inv['status']!r}"
    assert inv["bonusKopecks"] == 0, f"Expected 0 bonus, got {inv['bonusKopecks']!r}"
    assert data["accruedKopecks"] == 0


async def test_summary_joined_invitee_status_bonus_and_accrued_sum(
    http_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Capture + referral_accrual row → status='joined', bonusKopecks>0, accruedKopecks is SUM."""
    staff = await _seed_staff(db_session, "joined")
    referrer = await _seed_client(db_session, staff, "+79200002004", first_name="Петр")
    referee = await _seed_client(db_session, staff, "+79200002005", first_name="Анна")
    await db_session.commit()

    code_id = await _seed_referral_code(db_session, client_id=referrer.id)
    capture_id = await _seed_referral_capture(
        db_session,
        referee_client_id=referee.id,
        referrer_client_id=referrer.id,
        referral_code_id=code_id,
    )
    await _seed_referral_accrual(
        db_session,
        referrer_client_id=referrer.id,
        capture_id=capture_id,
        amount_kopecks=50_000,
    )
    await db_session.commit()

    await _auth_as_client(http_client, db_session, referrer)

    resp = await http_client.get("/api/v1/client/referral/summary")
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]

    assert len(data["invitees"]) == 1, f"Expected 1 invitee, got {data['invitees']!r}"
    inv = data["invitees"][0]
    assert inv["status"] == "joined", f"Expected joined, got {inv['status']!r}"
    assert inv["bonusKopecks"] == 50_000, (
        f"Expected bonusKopecks=50000, got {inv['bonusKopecks']!r}"
    )
    assert data["accruedKopecks"] == 50_000, (
        f"Expected accruedKopecks=50000, got {data['accruedKopecks']!r}"
    )


async def test_summary_invitee_keys_are_pii_minimal(
    http_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Each invitee wire keys == {firstName, joinedAt, status, bonusKopecks}; no lastName/id."""
    staff = await _seed_staff(db_session, "pii")
    referrer = await _seed_client(db_session, staff, "+79200002006")
    referee = await _seed_client(db_session, staff, "+79200002007", first_name="Олег")
    await db_session.commit()

    code_id = await _seed_referral_code(db_session, client_id=referrer.id)
    await _seed_referral_capture(
        db_session,
        referee_client_id=referee.id,
        referrer_client_id=referrer.id,
        referral_code_id=code_id,
    )
    await db_session.commit()

    await _auth_as_client(http_client, db_session, referrer)

    resp = await http_client.get("/api/v1/client/referral/summary")
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]

    assert len(data["invitees"]) >= 1
    for inv in data["invitees"]:
        assert set(inv.keys()) == {"firstName", "joinedAt", "status", "bonusKopecks"}, (
            f"Unexpected invitee keys: {set(inv.keys())!r}"
        )
        assert "lastName" not in inv, "lastName must not be exposed (PII-minimal)"
        assert "clientId" not in inv, "clientId must not be exposed (IDOR guard)"
        assert "refereeClientId" not in inv, "refereeClientId must not be exposed"
    # PII: firstName is present and is a string
    assert isinstance(data["invitees"][0]["firstName"], str)
    assert len(data["invitees"][0]["firstName"]) > 0


async def test_summary_share_url_ends_with_code(
    http_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """shareUrl must end with /i/<code>."""
    staff = await _seed_staff(db_session, "url")
    client = await _seed_client(db_session, staff, "+79200002008")
    await db_session.commit()

    await _auth_as_client(http_client, db_session, client)

    resp = await http_client.get("/api/v1/client/referral/summary")
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]

    assert data["shareUrl"].endswith(f"/i/{data['code']}"), (
        f"shareUrl {data['shareUrl']!r} does not end with /i/{data['code']!r}"
    )


async def test_summary_no_auth_returns_401(
    http_client: AsyncClient,
) -> None:
    """Unauthenticated request → GET /client/referral/summary returns 401."""
    resp = await http_client.get("/api/v1/client/referral/summary")
    assert resp.status_code == 401, resp.text


async def test_summary_idor_other_client_invitees_not_leaked(
    http_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Client B's summary must not contain client A's invitees."""
    staff = await _seed_staff(db_session, "idor")
    client_a = await _seed_client(db_session, staff, "+79200002009", first_name="Алиса")
    referee_of_a = await _seed_client(db_session, staff, "+79200002010", first_name="УникальноеИмя")
    client_b = await _seed_client(db_session, staff, "+79200002011", first_name="Борис")
    await db_session.commit()

    # Seed client A's referral code + capture for referee_of_a
    code_id_a = await _seed_referral_code(db_session, client_id=client_a.id)
    await _seed_referral_capture(
        db_session,
        referee_client_id=referee_of_a.id,
        referrer_client_id=client_a.id,
        referral_code_id=code_id_a,
    )
    await db_session.commit()

    # Authenticate as client B (fresh transport, separate session to avoid cookie collision)
    transport = ASGITransport(app=http_client._transport.app)  # type: ignore[attr-defined]
    async with AsyncClient(transport=transport, base_url="http://testserver") as client_b_http:
        await _auth_as_client(client_b_http, db_session, client_b)

        resp_b = await client_b_http.get("/api/v1/client/referral/summary")
        assert resp_b.status_code == 200, resp_b.text
        data_b = resp_b.json()["data"]

    # Client B has zero invitees — and specifically not client A's referee
    invitee_names = [inv["firstName"] for inv in data_b["invitees"]]
    assert "УникальноеИмя" not in invitee_names, (
        f"Client B must not see client A's referee. invitees: {data_b['invitees']!r}"
    )
    assert data_b["invitees"] == [], (
        f"Client B should have no invitees, got: {data_b['invitees']!r}"
    )
