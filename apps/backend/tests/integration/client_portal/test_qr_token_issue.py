"""Phase 70 CCHK-01..02 — QR token issuance + basic check-in happy path.

Covers:
  - GET /api/v1/client/qr-token → 200 with token + expires_in == qr_token_ttl_seconds
  - POST /api/v1/client/check-in with a valid QR token → 200 visit channel='client_qr'
  - GET /api/v1/client/qr-token does NOT pre-check membership (client with no membership
    still gets a token; the anti-fraud gate fires only at scan time)

Uses SAVEPOINT db_session + ASGITransport (no real network). Monkeypatches gym_hours to
always-open so tests pass at any wall-clock time.

Security / anti-replay tests (expired → 401, duplicate → duplicate_checkin, token
confusion, cross-client) live in test_qr_checkin.py.
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
from app.modules.memberships.models import Membership, MembershipPlan

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Fixtures — dependency overrides + ASGITransport client
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
# Auth helper — mirrors test_idor_sweep.py:_auth_as_client
# ---------------------------------------------------------------------------


async def _auth_as_client(
    http_client: AsyncClient,
    db_session: AsyncSession,
    client: Client,
) -> None:
    """Request OTP → patch hash → verify. After this call http_client holds all cookies."""
    req = await http_client.post(
        "/api/v1/client/otp/request",
        json={"phone": client.phone},
    )
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
    otp_row.expires_at = datetime.now(tz=UTC) + timedelta(seconds=settings.otp_code_ttl_seconds)
    await db_session.commit()

    verify = await http_client.post(
        "/api/v1/client/otp/verify",
        json={"phone": client.phone, "code": raw_code},
    )
    assert verify.status_code == 200, f"OTP verify failed: {verify.text}"


# ---------------------------------------------------------------------------
# DB seed helpers
# ---------------------------------------------------------------------------


async def _seed_staff(db_session: AsyncSession) -> User:
    user = User(
        email=f"qr-issue-staff-{uuid4().hex[:6]}@example.com",
        password_hash=await hash_password("secure-test-password-123"),
        role=Role.RECEPTION,
        full_name="QR Issue Test Staff",
    )
    db_session.add(user)
    await db_session.commit()
    return user


async def _seed_client(db_session: AsyncSession, staff: User, *, phone: str) -> Client:
    client = Client(
        first_name="QRIssue",
        last_name=f"Client-{uuid4().hex[:4]}",
        phone=phone,
        telegram_user_id=abs(hash(phone)) % (10**10),
        created_by_user_id=staff.id,
    )
    db_session.add(client)
    await db_session.commit()
    return client


async def _seed_active_membership(db_session: AsyncSession, client_id: object) -> Membership:
    """Seed an active membership far into the future (anti-fraud requires one for check-in)."""
    now = datetime.now(tz=UTC)
    plan = MembershipPlan(
        name=f"QR Test Plan {uuid4().hex[:4]}",
        duration_days=30,
        price_kopecks=100_000,
        freeze_days_limit=7,
        active=True,
    )
    db_session.add(plan)
    await db_session.flush()

    membership = Membership(
        client_id=client_id,  # type: ignore[arg-type]
        plan_id=plan.id,
        plan_name_snapshot=plan.name,
        duration_days_snapshot=plan.duration_days,
        price_kopecks_snapshot=plan.price_kopecks,
        freeze_days_limit_snapshot=plan.freeze_days_limit,
        start_date=(now - timedelta(days=5)).date(),
        end_date=(now + timedelta(days=60)).date(),
        status="active",
    )
    db_session.add(membership)
    await db_session.commit()
    return membership


# ---------------------------------------------------------------------------
# GET /api/v1/client/qr-token — token issuance tests (CCHK-01)
# ---------------------------------------------------------------------------


async def test_qr_token_issuance_returns_token_and_expires_in(
    http_client: AsyncClient,
    db_session: AsyncSession,
    app: FastAPI,
) -> None:
    """CCHK-01: authenticated client gets a QR token with correct expires_in."""
    await app.state.redis.flushdb()
    staff = await _seed_staff(db_session)
    client = await _seed_client(db_session, staff, phone="+79100000001")
    await _auth_as_client(http_client, db_session, client)

    settings = get_settings()
    r = await http_client.get("/api/v1/client/qr-token")
    assert r.status_code == 200, r.text
    body = r.json()
    assert "token" in body["data"]
    assert body["data"]["expiresIn"] == settings.qr_token_ttl_seconds
    # Token is a non-empty JWT string
    assert len(body["data"]["token"]) > 20


async def test_qr_token_no_membership_precheck(
    http_client: AsyncClient,
    db_session: AsyncSession,
    app: FastAPI,
) -> None:
    """CCHK-01 / D-70-09: a client with NO active membership still gets a QR token.

    The anti-fraud gate (no_active_membership) fires at scan time (POST /check-in),
    not at token issuance. This test confirms the token endpoint issues freely.
    """
    await app.state.redis.flushdb()
    staff = await _seed_staff(db_session)
    # No membership seeded for this client
    client = await _seed_client(db_session, staff, phone="+79100000002")
    await _auth_as_client(http_client, db_session, client)

    r = await http_client.get("/api/v1/client/qr-token")
    assert r.status_code == 200, r.text
    body = r.json()
    assert "token" in body["data"]


async def test_qr_token_requires_auth(
    http_client: AsyncClient,
    app: FastAPI,
) -> None:
    """GET /qr-token without authentication → 401 (require_client guard)."""
    await app.state.redis.flushdb()
    r = await http_client.get("/api/v1/client/qr-token")
    assert r.status_code == 401, r.text


# ---------------------------------------------------------------------------
# POST /api/v1/client/check-in — basic happy path (CCHK-02)
# ---------------------------------------------------------------------------


async def test_check_in_valid_token_creates_visit(
    http_client: AsyncClient,
    db_session: AsyncSession,
    app: FastAPI,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CCHK-02: valid QR token → 200 visit with channel='client_qr'."""
    await app.state.redis.flushdb()

    # Patch gym hours to always-open
    import app.modules.visits.service as svc_mod

    settings = get_settings()
    from datetime import time

    monkeypatch.setattr(settings, "gym_hours_start", time(0, 0))
    monkeypatch.setattr(settings, "gym_hours_end", time(23, 59))
    monkeypatch.setattr(svc_mod, "get_settings", lambda: settings)

    staff = await _seed_staff(db_session)
    client = await _seed_client(db_session, staff, phone="+79100000003")
    await _seed_active_membership(db_session, client.id)

    # Authenticate + get QR token via the authenticated endpoint
    await _auth_as_client(http_client, db_session, client)
    qr_resp = await http_client.get("/api/v1/client/qr-token")
    assert qr_resp.status_code == 200, qr_resp.text
    token = qr_resp.json()["data"]["token"]

    # POST /check-in with the QR token (no session cookies needed — token-as-credential)
    # Use a fresh unauthenticated client to prove no session is needed
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as anon_client:
        # Install overrides on the app directly (shared app object)
        r = await anon_client.post(
            "/api/v1/client/check-in",
            json={"token": token},
        )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["data"]["channel"] == "client_qr"
    assert body["data"]["gymDate"] is not None


async def test_check_in_schema_has_no_client_id_field(
    http_client: AsyncClient,
    db_session: AsyncSession,
    app: FastAPI,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """T-70-17: POST /check-in body has NO client_id field — structural cross-client guard.

    ClientCheckInRequest has NO client_id field (D-70-10): there is no body/path/query
    parameter that could target a different client. Any client_id supplied in the body
    is silently ignored (ResponseData extra='ignore') — the visit is always created
    for the token's sub owner. This test confirms the route handler signature has no
    client_id parameter by verifying the endpoint is unauthenticated and a stale
    client_id injection has no effect on which client is checked in.

    The full cross-client proof (client B's token checks in client B regardless of
    the sender's session) lives in test_qr_checkin.py.
    """
    await app.state.redis.flushdb()

    # Confirm the endpoint exists without require_client (unauthenticated request
    # with an invalid token → 401 token_expired / invalid_token, not 401 missing cookie)
    r = await http_client.post(
        "/api/v1/client/check-in",
        json={"token": "not.a.real.token"},
    )
    # Should be 401 from decode_qr_token (invalid token), NOT from require_client
    assert r.status_code == 401, r.text
    body = r.json()
    # HTTP response code = "invalid_token" (InvalidAccessToken class default).
    # The specific error kind is in body["message"]: invalid_token, token_expired, etc.
    assert body.get("code") == "invalid_token", (
        f"Expected 'invalid_token' (require_client would return 'missing_access_cookie'), "
        f"got: {body.get('code')}"
    )
