"""Phase 96 Plan 96-03 — Referral capture integration tests (REFER-03).

Proves:
  - Client B captures client A's code → 200, one referral_captures row
    (referrer=A, referee=B), one referral_captured audit row.
  - Second capture by B → 200 no-op, still exactly one capture row (first binding wins).
  - Self-referral (A captures A's own code) → 422 "self_referral_not_allowed".
  - Unknown code → 404 "referral_code_not_found".
  - Referee identity is from the principal (B's id), not from the body.

Harness: SAVEPOINT db_session + ASGITransport (no real network — CLAUDE.md).
Client auth: OTP flow via _auth_as_client helper.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit_models import AuditLog
from app.core.config import get_settings
from app.core.database import get_db
from app.core.permissions import Role
from app.core.redis import get_redis
from app.core.security import generate_otp_code, hash_password
from app.modules.auth.models import OtpCode, User
from app.modules.clients.models import Client

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
# Helpers
# ---------------------------------------------------------------------------


async def _seed_staff(db_session: AsyncSession, suffix: str = "") -> User:
    user = User(
        email=f"ref-cap-staff-{suffix or uuid4().hex[:8]}@example.com",
        password_hash=await hash_password("ref-cap-staff-pw-secure"),
        role=Role.RECEPTION,
        full_name="Referral Capture Test Staff",
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
        last_name="Клиент",
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


async def _get_code_for_client(
    http_client: AsyncClient,
    db_session: AsyncSession,
    client: Client,
) -> str:
    """Authenticate as client and GET /client/referral/code, return the code string."""
    await _auth_as_client(http_client, db_session, client)
    resp = await http_client.get("/api/v1/client/referral/code")
    assert resp.status_code == 200, f"GET code failed: {resp.text}"
    return str(resp.json()["data"]["code"])


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_capture_binds_referee_to_referrer(
    http_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Client B captures A's code → 200; referral_captures row has referrer=A, referee=B."""
    staff = await _seed_staff(db_session, "cap-bind")
    client_a = await _seed_client(db_session, staff, "+79201001001", "Алексей")
    client_b = await _seed_client(db_session, staff, "+79201001002", "Борис")
    await db_session.commit()

    # Get A's code
    code_a = await _get_code_for_client(http_client, db_session, client_a)

    # Authenticate as B and capture A's code
    transport = ASGITransport(app=http_client._transport.app)  # type: ignore[attr-defined]
    async with AsyncClient(transport=transport, base_url="http://testserver") as client_b_http:
        await _auth_as_client(client_b_http, db_session, client_b)
        capture_resp = await client_b_http.post(
            "/api/v1/client/referral/capture",
            json={"code": code_a},
        )
    assert capture_resp.status_code == 200, capture_resp.text

    # Verify a referral_captures row exists with referrer=A, referee=B
    row = (
        (
            await db_session.execute(
                text(
                    "SELECT referee_client_id, referrer_client_id "
                    "FROM referral_captures "
                    "WHERE referee_client_id = :referee"
                ),
                {"referee": str(client_b.id)},
            )
        )
        .mappings()
        .one_or_none()
    )
    assert row is not None, "Expected a referral_captures row for client B as referee"
    assert str(row["referrer_client_id"]) == str(client_a.id), (
        f"Expected referrer=A ({client_a.id}), got {row['referrer_client_id']}"
    )


async def test_capture_emits_audit_row(
    http_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Capture → exactly one referral_captured audit row with correct payload fields."""
    staff = await _seed_staff(db_session, "cap-audit")
    client_a = await _seed_client(db_session, staff, "+79201001003")
    client_b = await _seed_client(db_session, staff, "+79201001004")
    await db_session.commit()

    code_a = await _get_code_for_client(http_client, db_session, client_a)

    transport = ASGITransport(app=http_client._transport.app)  # type: ignore[attr-defined]
    async with AsyncClient(transport=transport, base_url="http://testserver") as client_b_http:
        await _auth_as_client(client_b_http, db_session, client_b)
        await client_b_http.post("/api/v1/client/referral/capture", json={"code": code_a})

    audit_rows = (
        await db_session.scalars(
            select(AuditLog).where(
                AuditLog.action == "referral_captured",
                AuditLog.resource_type == "referral",
            )
        )
    ).all()
    b_audits = [a for a in audit_rows if a.payload.get("referee_client_id") == str(client_b.id)]
    assert len(b_audits) == 1, f"Expected 1 referral_captured audit row, got {len(b_audits)}"
    payload = b_audits[0].payload
    assert payload["referrer_client_id"] == str(client_a.id)
    assert "referral_capture_id" in payload
    assert "referral_code_id" in payload


async def test_capture_is_idempotent_second_call_no_op(
    http_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Second capture by same referee → 200 no-op, still exactly one capture row."""
    staff = await _seed_staff(db_session, "cap-idem")
    client_a = await _seed_client(db_session, staff, "+79201001005")
    client_b = await _seed_client(db_session, staff, "+79201001006")
    await db_session.commit()

    code_a = await _get_code_for_client(http_client, db_session, client_a)

    transport = ASGITransport(app=http_client._transport.app)  # type: ignore[attr-defined]
    async with AsyncClient(transport=transport, base_url="http://testserver") as client_b_http:
        await _auth_as_client(client_b_http, db_session, client_b)

        # First capture
        r1 = await client_b_http.post(
            "/api/v1/client/referral/capture",
            json={"code": code_a},
        )
        assert r1.status_code == 200, r1.text

        # Second capture — no-op
        r2 = await client_b_http.post(
            "/api/v1/client/referral/capture",
            json={"code": code_a},
        )
        assert r2.status_code == 200, r2.text

    # Exactly one capture row
    count_row = (
        (
            await db_session.execute(
                text(
                    "SELECT COUNT(*) AS cnt FROM referral_captures "
                    "WHERE referee_client_id = :referee"
                ),
                {"referee": str(client_b.id)},
            )
        )
        .mappings()
        .one()
    )
    assert int(count_row["cnt"]) == 1, (
        f"Expected exactly 1 capture row after two attempts, got {count_row['cnt']}"
    )


async def test_capture_self_referral_returns_422(
    http_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Client A captures their own code → 422 with code 'self_referral_not_allowed'."""
    staff = await _seed_staff(db_session, "cap-self")
    client_a = await _seed_client(db_session, staff, "+79201001007")
    await db_session.commit()

    code_a = await _get_code_for_client(http_client, db_session, client_a)

    # Same client tries to capture their own code
    resp = await http_client.post(
        "/api/v1/client/referral/capture",
        json={"code": code_a},
    )
    assert resp.status_code == 422, resp.text
    assert resp.json()["code"] == "self_referral_not_allowed", (
        f"Expected code 'self_referral_not_allowed', got {resp.json()['code']!r}"
    )


async def test_capture_unknown_code_returns_404(
    http_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Unknown code → 404 with code 'referral_code_not_found'."""
    staff = await _seed_staff(db_session, "cap-404")
    client_a = await _seed_client(db_session, staff, "+79201001008")
    await db_session.commit()

    await _auth_as_client(http_client, db_session, client_a)

    resp = await http_client.post(
        "/api/v1/client/referral/capture",
        json={"code": "ZZZZZZZZ"},  # unknown code
    )
    assert resp.status_code == 404, resp.text
    assert resp.json()["code"] == "referral_code_not_found", (
        f"Expected code 'referral_code_not_found', got {resp.json()['code']!r}"
    )


async def test_capture_referee_from_principal_not_body(
    http_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Referee identity is the authenticated principal (B), regardless of body content.

    The body carries only {code}. The DB row referee_client_id == client_b.id
    proves the principal is used, not any body field.
    """
    staff = await _seed_staff(db_session, "cap-idor")
    client_a = await _seed_client(db_session, staff, "+79201001009")
    client_b = await _seed_client(db_session, staff, "+79201001010")
    await db_session.commit()

    code_a = await _get_code_for_client(http_client, db_session, client_a)

    transport = ASGITransport(app=http_client._transport.app)  # type: ignore[attr-defined]
    async with AsyncClient(transport=transport, base_url="http://testserver") as client_b_http:
        await _auth_as_client(client_b_http, db_session, client_b)
        # Body only contains {code} — no id field is sent
        capture_resp = await client_b_http.post(
            "/api/v1/client/referral/capture",
            json={"code": code_a},
        )
    assert capture_resp.status_code == 200, capture_resp.text

    # Assert referee is B (the authenticated client)
    row = (
        (
            await db_session.execute(
                text(
                    "SELECT referee_client_id FROM referral_captures "
                    "WHERE referee_client_id = :referee"
                ),
                {"referee": str(client_b.id)},
            )
        )
        .mappings()
        .one_or_none()
    )
    assert row is not None, "Capture row should exist with B as referee"
    assert str(row["referee_client_id"]) == str(client_b.id), (
        f"referee_client_id should be B ({client_b.id}), got {row['referee_client_id']}"
    )
