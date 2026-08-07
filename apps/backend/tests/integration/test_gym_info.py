"""Phase 86 Plan 86-02 — Gym-info API integration tests (GYM-01/GYM-02).

Proves:
  - GET /api/v1/client/gym → 200, seeded baseline content (name, address, arrays)
  - PUT /api/v1/gym by owner → 200, updated field persisted; GET reflects change
  - PUT /api/v1/gym by reception → 403 (OWNER_ONLY EDIT/GYM enforced — GYM-02)
  - GET /api/v1/client/gym without client auth → 401 (require_client gate)
  - PUT /api/v1/gym with unknown key → 422 (GymInfoUpdateRequest extra='forbid')

Harness: SAVEPOINT db_session + ASGITransport async_client (no real network — CLAUDE.md).
Client auth: OTP flow via inline _auth_as_client helper (mirrors test_loyalty_read.py).
Staff auth: /api/v1/auth/login with seeded owner/reception (mirrors test_loyalty_grant.py).
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

_OWNER_EMAIL = "gym-info-owner@example.com"
_OWNER_PASSWORD = "gym-info-owner-pw-secure-123"  # noqa: S105
_RECEPTION_EMAIL = "gym-info-reception@example.com"
_RECEPTION_PASSWORD = "gym-info-reception-pw-secure-456"  # noqa: S105


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
    """ASGITransport client that persists cookies across requests (client-portal auth)."""
    transport = ASGITransport(app=_overridden_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c


@pytest_asyncio.fixture
async def http_client_owner(
    _overridden_app: FastAPI,
    seeded_owner: User,
) -> AsyncIterator[AsyncClient]:
    """ASGITransport client logged in as owner (depends on seeded_owner for ordering)."""
    transport = ASGITransport(app=_overridden_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        r = await c.post(
            "/api/v1/auth/login",
            json={"email": _OWNER_EMAIL, "password": _OWNER_PASSWORD},
        )
        assert r.status_code == 200, f"Owner login failed: {r.text}"
        yield c


@pytest_asyncio.fixture
async def http_client_reception(
    _overridden_app: FastAPI,
    seeded_reception: User,
) -> AsyncIterator[AsyncClient]:
    """ASGITransport client logged in as reception (depends on seeded_reception for ordering)."""
    transport = ASGITransport(app=_overridden_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        r = await c.post(
            "/api/v1/auth/login",
            json={"email": _RECEPTION_EMAIL, "password": _RECEPTION_PASSWORD},
        )
        assert r.status_code == 200, f"Reception login failed: {r.text}"
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


@pytest_asyncio.fixture
async def seeded_owner(db_session: AsyncSession) -> User:
    user = User(
        email=_OWNER_EMAIL,
        password_hash=await hash_password(_OWNER_PASSWORD),
        role=Role.OWNER,
        full_name="Gym Info Test Owner",
    )
    db_session.add(user)
    await db_session.commit()
    return user


@pytest_asyncio.fixture
async def seeded_reception(db_session: AsyncSession, seeded_owner: User) -> User:
    """Reception user (depends on seeded_owner to ensure commit ordering)."""
    user = User(
        email=_RECEPTION_EMAIL,
        password_hash=await hash_password(_RECEPTION_PASSWORD),
        role=Role.RECEPTION,
        full_name="Gym Info Test Reception",
    )
    db_session.add(user)
    await db_session.commit()
    return user


@pytest_asyncio.fixture
async def seeded_client(db_session: AsyncSession, seeded_owner: User) -> Client:
    """A client seeded for GET /client/gym tests."""
    client = Client(
        first_name="Клиент",
        last_name="ЗалТест",
        phone=f"+7916{uuid4().int % 10_000_000:07d}",
        telegram_user_id=abs(hash("gym-info-test-client")) % (10**9),
        created_by_user_id=seeded_owner.id,
    )
    db_session.add(client)
    await db_session.commit()
    return client


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _csrf_headers(client: AsyncClient) -> dict[str, str]:
    return {"X-CSRF-Token": client.cookies.get("clubcore_csrf", "")}


async def _auth_as_client(
    async_client: AsyncClient,
    db_session: AsyncSession,
    client: Client,
) -> str:
    """Request OTP → patch code → verify → return cc_client_access token value.

    Mirrors the helper in test_loyalty_read.py: reads the OtpCode row and replaces
    the hash with a deterministic known code so the verify step succeeds in tests.
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
    return verify.cookies.get("cc_client_access", "")


# ---------------------------------------------------------------------------
# Test: client read — seeded baseline content (GYM-01)
# ---------------------------------------------------------------------------


async def test_client_get_gym_info_returns_seeded_baseline(
    http_client: AsyncClient,
    db_session: AsyncSession,
    seeded_client: Client,
) -> None:
    """Authenticated client GETs /api/v1/client/gym → 200, seeded baseline content.

    Proves seed is read from DB (not static data/gym.js): name, address, non-empty
    hours/amenities/rules arrays all reflect the 0059_seed_gym_info migration values.
    Wire format: camelCase (ResponseData alias_generator=to_camel).
    """
    await _auth_as_client(http_client, db_session, seeded_client)

    resp = await http_client.get("/api/v1/client/gym")
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]

    assert data["name"] == "Мой зал · Тверская"
    assert data["address"] == "Тверская, 18, 3 этаж"
    assert isinstance(data["hours"], list) and len(data["hours"]) > 0, (
        "hours should be a non-empty list from seed"
    )
    assert isinstance(data["amenities"], list) and len(data["amenities"]) > 0, (
        "amenities should be a non-empty list from seed"
    )
    assert isinstance(data["rules"], list) and len(data["rules"]) > 0, (
        "rules should be a non-empty list from seed"
    )


# ---------------------------------------------------------------------------
# Test: owner write-then-read (GYM-02 + read-after-write persistence)
# ---------------------------------------------------------------------------


async def test_owner_put_gym_info_updates_and_persists(
    http_client_owner: AsyncClient,
    http_client: AsyncClient,
    db_session: AsyncSession,
    seeded_client: Client,
) -> None:
    """Owner PUTs /api/v1/gym → 200; subsequent client GET reflects updated tagline.

    Proves read-after-write persistence: the owner write commits to the DB and the
    client read returns the updated value (not a stale cached or pre-seeded value).
    """
    new_tagline = "Новый слоган теста"

    put_resp = await http_client_owner.put(
        "/api/v1/gym",
        json={"tagline": new_tagline},
        headers=_csrf_headers(http_client_owner),
    )
    assert put_resp.status_code == 200, put_resp.text
    put_data = put_resp.json()["data"]
    assert put_data["tagline"] == new_tagline, (
        f"PUT response should reflect updated tagline, got: {put_data['tagline']!r}"
    )

    # Read-after-write: client GET must now return the updated tagline.
    await _auth_as_client(http_client, db_session, seeded_client)
    get_resp = await http_client.get("/api/v1/client/gym")
    assert get_resp.status_code == 200, get_resp.text
    get_data = get_resp.json()["data"]
    assert get_data["tagline"] == new_tagline, (
        f"Read-after-write failed: GET returned tagline={get_data['tagline']!r}, "
        f"expected {new_tagline!r}"
    )


# ---------------------------------------------------------------------------
# Test: reception 403 (GYM-02 RBAC-04 enforcement)
# ---------------------------------------------------------------------------


async def test_reception_put_gym_info_forbidden(
    http_client_reception: AsyncClient,
) -> None:
    """Reception PUT /api/v1/gym → 403 (OWNER_ONLY (EDIT, GYM) enforced — T-86-04).

    RBAC-04 ordering: require_permission fires before verify_csrf so reception
    fails at 403 even when a valid CSRF token is provided.
    """
    r = await http_client_reception.put(
        "/api/v1/gym",
        json={"tagline": "Не должен пройти"},  # noqa: RUF001
        headers=_csrf_headers(http_client_reception),
    )
    assert r.status_code == 403, r.text


# ---------------------------------------------------------------------------
# Test: anonymous/unauthenticated rejection (T-86-05)
# ---------------------------------------------------------------------------


async def test_anonymous_get_gym_info_rejected(
    http_client: AsyncClient,
) -> None:
    """No client auth → GET /api/v1/client/gym returns non-200 auth-rejection (T-86-05).

    require_client() gate enforces that only authenticated clients can read gym info.
    Expected: 401 (unauthenticated) from the client-auth dependency chain.
    """
    resp = await http_client.get("/api/v1/client/gym")
    assert resp.status_code != 200, (
        f"Unauthenticated request should be rejected, got status {resp.status_code}"
    )
    assert resp.status_code in (401, 403), (
        f"Expected 401 or 403 for unauthenticated request, got {resp.status_code}"
    )


# ---------------------------------------------------------------------------
# Test: unknown key → 422 (T-86-07 extra='forbid')
# ---------------------------------------------------------------------------


async def test_owner_put_gym_info_rejects_unknown_key(
    http_client_owner: AsyncClient,
) -> None:
    """Owner PUT with unknown JSON key → 422 (GymInfoUpdateRequest extra='forbid' — T-86-07).

    BackendSchemaBase (base class of GymInfoUpdateRequest) has extra='forbid' which
    causes Pydantic v2 to reject unknown fields with a 422 validation error.
    """
    r = await http_client_owner.put(
        "/api/v1/gym",
        json={"unknownField": "неизвестное поле"},
        headers=_csrf_headers(http_client_owner),
    )
    assert r.status_code == 422, r.text
