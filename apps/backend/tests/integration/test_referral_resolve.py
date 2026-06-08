"""Phase 96 Plan 96-03 — Referral public resolver integration tests (REFER-02 backend).

Proves:
  - GET /api/v1/i/<known-code> (NO auth) → 200, valid:true, referrerFirstName is the
    referrer's first name, response has NO client_id and NO last name keys,
    welcomeBonusKopecks == 30000 (seeded config default).
  - GET /api/v1/i/UNKNOWN → 200 (NOT 404), valid:false, referrerFirstName is null.
  - The JSON keys are exactly {valid, referrerFirstName, welcomeBonusKopecks}.

Harness: SAVEPOINT db_session + ASGITransport (no real network — CLAUDE.md).
Client auth: OTP flow to mint the referral code for a known client.
The public resolve endpoint is unauthenticated — no cookie required.
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

pytestmark = pytest.mark.asyncio

_EXPECTED_WELCOME_BONUS_KOPECKS = 30_000  # 0068 seed default


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
    """ASGITransport client (no auth cookies — public endpoint tests)."""
    transport = ASGITransport(app=_overridden_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c


@pytest.fixture(autouse=True)
def stub_otp_sender(app: FastAPI, monkeypatch: pytest.MonkeyPatch) -> None:
    """Replace real OTP sender with no-op."""
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
        email=f"ref-resolve-staff-{suffix or uuid4().hex[:8]}@example.com",
        password_hash=await hash_password("ref-resolve-staff-pw-secure"),
        role=Role.RECEPTION,
        full_name="Referral Resolve Test Staff",
    )
    db_session.add(user)
    await db_session.flush()
    return user


async def _seed_client(
    db_session: AsyncSession,
    staff: User,
    phone: str,
    first_name: str = "Иван",
) -> Client:
    client = Client(
        first_name=first_name,
        last_name="Иванов",
        phone=phone,
        telegram_user_id=abs(hash(phone)) % (10**9),
        created_by_user_id=staff.id,
    )
    db_session.add(client)
    await db_session.flush()
    return client


async def _auth_and_get_code(
    overridden_app: FastAPI,
    db_session: AsyncSession,
    client: Client,
) -> str:
    """Authenticate as client and GET /client/referral/code; return the code."""
    transport = ASGITransport(app=overridden_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        req = await c.post("/api/v1/client/otp/request", json={"phone": client.phone})
        assert req.status_code == 202, f"OTP request failed: {req.text}"

        otp_row = await db_session.scalar(
            select(OtpCode).where(
                OtpCode.client_id == client.id,
                OtpCode.consumed_at.is_(None),
            )
        )
        assert otp_row is not None

        settings = get_settings()
        raw_code, code_hash = generate_otp_code()
        otp_row.code_hash = code_hash
        otp_row.expires_at = datetime.now(tz=UTC) + timedelta(
            seconds=settings.otp_code_ttl_seconds
        )
        await db_session.commit()

        verify = await c.post(
            "/api/v1/client/otp/verify",
            json={"phone": client.phone, "code": raw_code},
        )
        assert verify.status_code == 200

        resp = await c.get("/api/v1/client/referral/code")
        assert resp.status_code == 200, f"GET code failed: {resp.text}"
        return str(resp.json()["data"]["code"])


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_resolve_known_code_returns_valid_true(
    http_client: AsyncClient,
    _overridden_app: FastAPI,
    db_session: AsyncSession,
) -> None:
    """GET /api/v1/i/<known-code> → 200, valid:true, referrerFirstName is the referrer's first name."""  # noqa: E501
    staff = await _seed_staff(db_session, "resolve-known")
    referrer = await _seed_client(db_session, staff, "+79202001001", "Михаил")
    await db_session.commit()

    code = await _auth_and_get_code(_overridden_app, db_session, referrer)

    # Resolve without any auth (public endpoint)
    resp = await http_client.get(f"/api/v1/i/{code}")
    assert resp.status_code == 200, resp.text

    data = resp.json()["data"]
    assert data["valid"] is True, f"Expected valid:true for known code, got {data['valid']!r}"
    assert data["referrerFirstName"] == "Михаил", (
        f"Expected referrerFirstName='Михаил', got {data['referrerFirstName']!r}"
    )
    assert data["welcomeBonusKopecks"] == _EXPECTED_WELCOME_BONUS_KOPECKS, (
        f"Expected welcomeBonusKopecks={_EXPECTED_WELCOME_BONUS_KOPECKS}, "
        f"got {data['welcomeBonusKopecks']}"
    )


async def test_resolve_known_code_no_pii_leakage(
    http_client: AsyncClient,
    _overridden_app: FastAPI,
    db_session: AsyncSession,
) -> None:
    """Known code response must have exactly {valid, referrerFirstName, welcomeBonusKopecks}."""
    staff = await _seed_staff(db_session, "resolve-pii")
    referrer = await _seed_client(db_session, staff, "+79202001002", "Сергей")
    await db_session.commit()

    code = await _auth_and_get_code(_overridden_app, db_session, referrer)

    resp = await http_client.get(f"/api/v1/i/{code}")
    assert resp.status_code == 200, resp.text

    data = resp.json()["data"]
    keys = set(data.keys())
    assert keys == {"valid", "referrerFirstName", "welcomeBonusKopecks"}, (
        f"Response data keys should be exactly {{valid, referrerFirstName, welcomeBonusKopecks}}, "
        f"got {keys!r}. Ensure no client_id, last_name, or other PII fields are exposed."
    )
    # Explicit no-PII assertions
    assert "clientId" not in data, "Response must not expose client_id (T-96-06)"
    assert "client_id" not in data, "Response must not expose client_id (T-96-06)"
    assert "lastName" not in data, "Response must not expose last name (T-96-06)"
    assert "last_name" not in data, "Response must not expose last name (T-96-06)"


async def test_resolve_unknown_code_returns_200_valid_false(
    http_client: AsyncClient,
) -> None:
    """GET /api/v1/i/UNKNOWN → 200 (NOT 404), valid:false, referrerFirstName:null."""
    resp = await http_client.get("/api/v1/i/UNKNWNXYZ")
    assert resp.status_code == 200, (
        f"Expected 200 for unknown code (anti-enumeration), got {resp.status_code}"
    )

    data = resp.json()["data"]
    assert data["valid"] is False, f"Expected valid:false for unknown code, got {data['valid']!r}"
    assert data["referrerFirstName"] is None, (
        f"Expected referrerFirstName:null for unknown code, got {data['referrerFirstName']!r}"
    )


async def test_resolve_unknown_code_exact_key_set(
    http_client: AsyncClient,
) -> None:
    """Unknown code response must have exactly {valid, referrerFirstName, welcomeBonusKopecks}."""
    resp = await http_client.get("/api/v1/i/NOTEXIST")
    assert resp.status_code == 200, resp.text

    data = resp.json()["data"]
    keys = set(data.keys())
    assert keys == {"valid", "referrerFirstName", "welcomeBonusKopecks"}, (
        f"Unknown code response keys must be exactly {{valid, referrerFirstName, "
        f"welcomeBonusKopecks}}, got {keys!r}"
    )


async def test_resolve_is_case_insensitive(
    http_client: AsyncClient,
    _overridden_app: FastAPI,
    db_session: AsyncSession,
) -> None:
    """Code resolve normalises input to upper-case (codes are stored upper-case)."""
    staff = await _seed_staff(db_session, "resolve-case")
    referrer = await _seed_client(db_session, staff, "+79202001003", "Анна")
    await db_session.commit()

    code = await _auth_and_get_code(_overridden_app, db_session, referrer)

    # Submit the code in lower-case
    resp = await http_client.get(f"/api/v1/i/{code.lower()}")
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["valid"] is True, (
        f"Expected valid:true when submitting lower-case code, got {data['valid']!r}"
    )
