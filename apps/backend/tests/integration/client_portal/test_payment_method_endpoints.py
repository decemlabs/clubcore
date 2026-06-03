"""Phase 79 Plan 79-04 — client payment-method endpoint behavior tests (PAYM-02/03/04).

Proves the endpoint contracts:
  - GET /client/payment-method: 200 + null when no card; 200 + display fields when card exists;
    response NEVER contains yookassa_method_id (token-absence assertion, T-79-13).
  - DELETE /client/payment-method: 204; subsequent GET → 200 + null; second DELETE → 204 no-op.
  - PATCH /client/payment-method/autopay:
    - enable + consent_acknowledged=True + active card → 200, autopayEnabled=True
    - enable + consent_acknowledged=False → 409 consent_required (ФЗ-376 gate, T-79-14)
    - enable + no card → 409 no_active_payment_method
    - disable → 200, autopay_enabled=False, consentRecordedAt unchanged (not cleared)

All endpoints IDOR-safe: client_id always from require_client() principal.
Token-absence: seeded yookassa_method_id string must not appear in any GET response body.

Harness: SAVEPOINT db_session + ASGITransport async_client.
Auth: OTP flow via _auth_as_client (cookies stored on http_client; CSRF from cookie jar).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.permissions import Role
from app.core.redis import get_redis
from app.core.security import hash_password
from app.modules.auth.models import User
from app.modules.clients.models import Client
from tests.integration.client_portal.test_idor_sweep import _auth_as_client

pytestmark = pytest.mark.asyncio

# ---------------------------------------------------------------------------
# Fixtures — dependency overrides + authed http_client
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


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------

_FAKE_TOKEN = "fake-pm-token-test-79-04-endpoint-a1b2c3d4"  # noqa: S105
_FAKE_LAST4 = "4444"
_FAKE_BRAND = "Visa"
_FAKE_EXPIRY_MONTH = 9
_FAKE_EXPIRY_YEAR = 2028


async def _seed_staff(db_session: AsyncSession) -> User:
    """Insert a staff user for client created_by_user_id FK."""
    user = User(
        email=f"pm-ep-staff-{uuid4().hex[:8]}@example.com",
        password_hash=await hash_password("secure-staff-pw-79-04"),
        role=Role.RECEPTION,
        full_name="PM Endpoint Test Staff",
    )
    db_session.add(user)
    await db_session.commit()
    return user


async def _seed_client(db_session: AsyncSession, staff: User, *, phone: str) -> Client:
    """Insert a client with the given phone."""
    client = Client(
        first_name="PMTest",
        last_name=f"Client-{uuid4().hex[:4]}",
        phone=phone,
        telegram_user_id=abs(hash(phone)) % (10**10),
        created_by_user_id=staff.id,
    )
    db_session.add(client)
    await db_session.commit()
    return client


async def _seed_active_card(
    db_session: AsyncSession,
    client_id: UUID,
    *,
    autopay_enabled: bool = False,
    consent_recorded_at: datetime | None = None,
    token: str = _FAKE_TOKEN,
) -> UUID:
    """Insert an active client_payment_methods row for the given client.

    Returns the row id for use in assertions.
    Uses raw SQL (D-54-08 discipline) to avoid ORM model import issues.
    """
    row_id = uuid4()
    await db_session.execute(
        text(
            "INSERT INTO client_payment_methods "
            "(id, client_id, yookassa_method_id, last4, brand, "
            " expiry_month, expiry_year, autopay_enabled, consent_recorded_at) "
            "VALUES (:id, :client_id, :token, :last4, :brand, "
            "        :expiry_month, :expiry_year, :autopay_enabled, :consent_recorded_at)"
        ),
        {
            "id": str(row_id),
            "client_id": str(client_id),
            "token": token,
            "last4": _FAKE_LAST4,
            "brand": _FAKE_BRAND,
            "expiry_month": _FAKE_EXPIRY_MONTH,
            "expiry_year": _FAKE_EXPIRY_YEAR,
            "autopay_enabled": autopay_enabled,
            "consent_recorded_at": consent_recorded_at,
        },
    )
    await db_session.commit()
    return row_id


# ---------------------------------------------------------------------------
# GET /client/payment-method — no card → 200 + null
# ---------------------------------------------------------------------------


async def test_get_payment_method_no_card_returns_null(
    http_client: AsyncClient,
    db_session: AsyncSession,
    app: FastAPI,
) -> None:
    """GET with no seeded card → 200 + data null (D-69-03 empty-state).

    T-79-13: response body must not contain the token.
    """
    await app.state.redis.flushdb()
    staff = await _seed_staff(db_session)
    client = await _seed_client(db_session, staff, phone="+79004440001")

    await _auth_as_client(http_client, db_session, client)

    r = await http_client.get("/api/v1/client/payment-method")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["data"] is None, f"Expected null, got: {body['data']}"

    # T-79-13: token must not appear in response body
    assert _FAKE_TOKEN not in r.text


async def test_get_payment_method_with_card_returns_display_fields(
    http_client: AsyncClient,
    db_session: AsyncSession,
    app: FastAPI,
) -> None:
    """GET with an active card → 200 + last4/brand/expiry/autopay/consent fields; no token."""
    await app.state.redis.flushdb()
    staff = await _seed_staff(db_session)
    client = await _seed_client(db_session, staff, phone="+79004440002")
    await _seed_active_card(db_session, client.id)

    await _auth_as_client(http_client, db_session, client)

    r = await http_client.get("/api/v1/client/payment-method")
    assert r.status_code == 200, r.text
    body = r.json()
    data = body["data"]

    assert data is not None, "Expected card data, got null"
    assert data["last4"] == _FAKE_LAST4
    assert data["brand"] == _FAKE_BRAND
    assert data["expiryMonth"] == _FAKE_EXPIRY_MONTH
    assert data["expiryYear"] == _FAKE_EXPIRY_YEAR
    assert data["autopayEnabled"] is False
    assert data["consentRecordedAt"] is None
    assert "id" in data

    # T-79-13: token (yookassa_method_id) must NEVER appear in response body
    assert _FAKE_TOKEN not in r.text, (
        "SECURITY: yookassa_method_id token leaked in GET response (T-79-13)"
    )
    # Belt-and-suspenders: ensure the key name itself is also absent
    assert "yookassaMethodId" not in r.text
    assert "yookassa_method_id" not in r.text


# ---------------------------------------------------------------------------
# DELETE /client/payment-method — 204 idempotent soft-delete (PAYM-03)
# ---------------------------------------------------------------------------


async def test_delete_payment_method_soft_deletes_and_returns_null(
    http_client: AsyncClient,
    db_session: AsyncSession,
    app: FastAPI,
) -> None:
    """DELETE on an existing card → 204; subsequent GET → 200 + null."""
    await app.state.redis.flushdb()
    staff = await _seed_staff(db_session)
    client = await _seed_client(db_session, staff, phone="+79004440003")
    await _seed_active_card(db_session, client.id)

    await _auth_as_client(http_client, db_session, client)
    csrf_token = http_client.cookies.get("clubcore_client_csrf") or ""

    r = await http_client.delete(
        "/api/v1/client/payment-method",
        headers={"X-CSRF-Token": csrf_token},
    )
    assert r.status_code == 204, r.text

    # Subsequent GET → 200 + null
    r2 = await http_client.get("/api/v1/client/payment-method")
    assert r2.status_code == 200, r2.text
    assert r2.json()["data"] is None, "Card should be null after delete"


async def test_delete_payment_method_idempotent_no_op(
    http_client: AsyncClient,
    db_session: AsyncSession,
    app: FastAPI,
) -> None:
    """DELETE idempotency: delete twice → 204 both times; GET → null after both."""
    await app.state.redis.flushdb()
    staff = await _seed_staff(db_session)
    client = await _seed_client(db_session, staff, phone="+79004440004")
    await _seed_active_card(db_session, client.id)

    await _auth_as_client(http_client, db_session, client)
    csrf_token = http_client.cookies.get("clubcore_client_csrf") or ""

    r1 = await http_client.delete(
        "/api/v1/client/payment-method",
        headers={"X-CSRF-Token": csrf_token},
    )
    assert r1.status_code == 204, r1.text

    # Second DELETE on an already-deleted card — must still be 204 (idempotent no-op)
    r2 = await http_client.delete(
        "/api/v1/client/payment-method",
        headers={"X-CSRF-Token": csrf_token},
    )
    assert r2.status_code == 204, f"Second DELETE expected 204, got {r2.status_code}: {r2.text}"

    # GET still null
    r3 = await http_client.get("/api/v1/client/payment-method")
    assert r3.status_code == 200
    assert r3.json()["data"] is None


# ---------------------------------------------------------------------------
# PATCH /client/payment-method/autopay — consent gate (PAYM-04 / ФЗ-376)
# ---------------------------------------------------------------------------


async def test_patch_autopay_enable_with_consent_succeeds(
    http_client: AsyncClient,
    db_session: AsyncSession,
    app: FastAPI,
) -> None:
    """PATCH enable with consent_acknowledged=True + active card → 200, autopayEnabled=True."""
    await app.state.redis.flushdb()
    staff = await _seed_staff(db_session)
    client = await _seed_client(db_session, staff, phone="+79004440005")
    await _seed_active_card(db_session, client.id)

    await _auth_as_client(http_client, db_session, client)
    csrf_token = http_client.cookies.get("clubcore_client_csrf") or ""

    r = await http_client.patch(
        "/api/v1/client/payment-method/autopay",
        json={"enabled": True, "consentAcknowledged": True},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["autopayEnabled"] is True
    assert data["consentRecordedAt"] is not None, "consent_recorded_at must be stamped on enable"

    # T-79-13: token still absent
    assert _FAKE_TOKEN not in r.text


async def test_patch_autopay_enable_without_consent_returns_409(
    http_client: AsyncClient,
    db_session: AsyncSession,
    app: FastAPI,
) -> None:
    """PATCH enable without consent → 409 consent_required (ФЗ-376 gate, T-79-14)."""
    await app.state.redis.flushdb()
    staff = await _seed_staff(db_session)
    client = await _seed_client(db_session, staff, phone="+79004440006")
    await _seed_active_card(db_session, client.id)

    await _auth_as_client(http_client, db_session, client)
    csrf_token = http_client.cookies.get("clubcore_client_csrf") or ""

    r = await http_client.patch(
        "/api/v1/client/payment-method/autopay",
        json={"enabled": True, "consentAcknowledged": False},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert r.status_code == 409, r.text
    body = r.json()
    # ConflictError: code="conflict", message=reason-string (consent_required)
    assert body.get("message") == "consent_required", (
        f"Expected consent_required 409, got: {r.text}"
    )

    # Autopay must remain false after failed enable attempt
    r2 = await http_client.get("/api/v1/client/payment-method")
    assert r2.json()["data"]["autopayEnabled"] is False


async def test_patch_autopay_enable_no_card_returns_409(
    http_client: AsyncClient,
    db_session: AsyncSession,
    app: FastAPI,
) -> None:
    """PATCH enable with no active card → 409 no_active_payment_method."""
    await app.state.redis.flushdb()
    staff = await _seed_staff(db_session)
    client = await _seed_client(db_session, staff, phone="+79004440007")
    # No card seeded

    await _auth_as_client(http_client, db_session, client)
    csrf_token = http_client.cookies.get("clubcore_client_csrf") or ""

    r = await http_client.patch(
        "/api/v1/client/payment-method/autopay",
        json={"enabled": True, "consentAcknowledged": True},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert r.status_code == 409, r.text
    body = r.json()
    # ConflictError: code="conflict", message=reason-string (no_active_payment_method)
    assert body.get("message") == "no_active_payment_method", (
        f"Expected no_active_payment_method in 409 body, got: {r.text}"
    )


async def test_patch_autopay_disable_ungated(
    http_client: AsyncClient,
    db_session: AsyncSession,
    app: FastAPI,
) -> None:
    """PATCH disable → 200, autopayEnabled=False; consentRecordedAt unchanged (not cleared)."""
    await app.state.redis.flushdb()
    staff = await _seed_staff(db_session)
    client = await _seed_client(db_session, staff, phone="+79004440008")
    consent_ts = datetime.now(tz=UTC)
    await _seed_active_card(
        db_session,
        client.id,
        autopay_enabled=True,
        consent_recorded_at=consent_ts,
    )

    await _auth_as_client(http_client, db_session, client)
    csrf_token = http_client.cookies.get("clubcore_client_csrf") or ""

    r = await http_client.patch(
        "/api/v1/client/payment-method/autopay",
        json={"enabled": False, "consentAcknowledged": False},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["autopayEnabled"] is False
    # consentRecordedAt must NOT be cleared when disabling autopay
    assert data["consentRecordedAt"] is not None, (
        "consentRecordedAt must be preserved (not cleared) when disabling autopay"
    )
