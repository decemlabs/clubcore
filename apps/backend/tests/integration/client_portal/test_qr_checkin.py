"""Phase 70 CCHK-03 / criterion #5 — QR anti-replay, token-confusion, cross-client tests.

Proves all security properties of POST /api/v1/client/check-in:

  1. Expired replay (T-70-14): expired QR token → 401 token_expired.
  2. Same-day double check-in (T-70-15): duplicate collapses to 409 duplicate_checkin
     via uq_visits_client_id_gym_date (no jti store needed — D-70-07).
  3. Token confusion — both directions (T-70-16):
     a) Access token (aud='client', typ='access') at /check-in → 401 wrong_token_type.
     b) QR token (aud='qr', typ='qr_checkin') at an authenticated endpoint
        (GET /client/membership) → 401 (not a valid access token).
  4. Cross-client structural impossibility (T-70-17 / D-70-10):
     Client B's QR token presented at /check-in checks in client B, NOT client A.
     There is no body/path/query parameter that could target a different client.

Uses SAVEPOINT db_session + ASGITransport (no real network). Monkeypatches gym_hours
to always-open for happy-path branches. Same fixture harness as test_client_booking.py.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

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
from app.core.security import encode_client_token, encode_qr_token, generate_otp_code, hash_password
from app.modules.auth.models import OtpCode, User
from app.modules.clients.models import Client
from app.modules.memberships.models import Membership, MembershipPlan
from app.modules.visits.models import Visit

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
# Auth helper — mirrors test_idor_sweep.py:_auth_as_client verbatim
# ---------------------------------------------------------------------------


async def _auth_as_client(
    http_client: AsyncClient,
    db_session: AsyncSession,
    client: Client,
) -> str:
    """Request OTP → patch hash → verify → return cc_client_access token value.

    After this call http_client holds all session cookies. Returns the raw
    access token value for direct use in headers/cookies when needed.
    """
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

    set_cookies = verify.headers.get_list("set-cookie")
    access_cookie = next(
        (c for c in set_cookies if c.startswith("cc_client_access=")),
        None,
    )
    assert access_cookie is not None, "cc_client_access cookie missing from verify response"
    return access_cookie.split("=", 1)[1].split(";", 1)[0]


# ---------------------------------------------------------------------------
# DB seed helpers
# ---------------------------------------------------------------------------


async def _seed_staff(db_session: AsyncSession) -> User:
    user = User(
        email=f"qr-checkin-staff-{uuid4().hex[:6]}@example.com",
        password_hash=await hash_password("secure-test-password-123"),
        role=Role.RECEPTION,
        full_name="QR Checkin Test Staff",
    )
    db_session.add(user)
    await db_session.commit()
    return user


async def _seed_client(db_session: AsyncSession, staff: User, *, phone: str) -> Client:
    client = Client(
        first_name="QRCheck",
        last_name=f"Client-{uuid4().hex[:4]}",
        phone=phone,
        telegram_user_id=abs(hash(phone)) % (10**10),
        created_by_user_id=staff.id,
    )
    db_session.add(client)
    await db_session.commit()
    return client


async def _seed_active_membership(db_session: AsyncSession, client_id: UUID) -> Membership:
    """Seed an active membership far into the future (required for check-in anti-fraud)."""
    now = datetime.now(tz=UTC)
    plan = MembershipPlan(
        name=f"QR Check Plan {uuid4().hex[:4]}",
        duration_days=30,
        price_kopecks=100_000,
        freeze_days_limit=7,
        active=True,
    )
    db_session.add(plan)
    await db_session.flush()

    membership = Membership(
        client_id=client_id,
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


def _patch_gym_hours_always_open(monkeypatch: pytest.MonkeyPatch) -> None:
    """Monkeypatch gym hours to 00:00-23:59 so tests pass at any wall-clock time."""
    from datetime import time

    import app.modules.visits.service as svc_mod

    settings = get_settings()
    monkeypatch.setattr(settings, "gym_hours_start", time(0, 0))
    monkeypatch.setattr(settings, "gym_hours_end", time(23, 59))
    monkeypatch.setattr(svc_mod, "get_settings", lambda: settings)


# ---------------------------------------------------------------------------
# Test 1: Expired replay → 401 token_expired (T-70-14 / criterion #5)
# ---------------------------------------------------------------------------


async def test_expired_qr_token_rejected(
    http_client: AsyncClient,
    db_session: AsyncSession,
    app: FastAPI,
) -> None:
    """T-70-14: an expired QR token at /check-in → 401 token_expired.

    Mints a QR token with now= set 120s in the past (beyond the 60s TTL + 30s
    leeway). decode_qr_token raises InvalidAccessToken('token_expired') which
    _app_error_handler turns into 401.
    """
    await app.state.redis.flushdb()
    staff = await _seed_staff(db_session)
    client = await _seed_client(db_session, staff, phone="+79200000001")

    # Mint a token that expired: now = 120s ago > (TTL=60 + leeway=30)
    past = datetime.now(tz=UTC) - timedelta(seconds=120)
    expired_token = encode_qr_token(client.id, now=past)

    r = await http_client.post(
        "/api/v1/client/check-in",
        json={"token": expired_token},
    )
    assert r.status_code == 401, r.text
    body = r.json()
    # The HTTP response uses exc.code = "invalid_token" (InvalidAccessToken class default).
    # The specific error discriminator is in exc.message (passed as the first arg to the
    # constructor). This mirrors how unit tests check exc_info.value.message == "token_expired".
    assert body["code"] == "invalid_token", f"Expected 'invalid_token', got: {body['code']}"
    assert body["message"] == "token_expired", (
        f"Expected message 'token_expired', got: {body['message']}"
    )


# ---------------------------------------------------------------------------
# Test 2: Same-day double check-in → 409 duplicate_checkin (T-70-15)
# ---------------------------------------------------------------------------


async def test_same_day_double_checkin_collapses_to_duplicate(
    http_client: AsyncClient,
    db_session: AsyncSession,
    app: FastAPI,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """T-70-15: same-day second check-in collapses to 409 duplicate_checkin.

    uq_visits_client_id_gym_date UNIQUE fires on the second flush → DuplicateCheckinError
    ('duplicate_checkin'). No jti store needed (D-70-07) — the daily-UNIQUE is the guard.
    Uses SAVEPOINT harness (not real-commit) since partial-UNIQUE serialization is not
    needed here — the flush+SAVEPOINT rollback + second insert is sufficient.
    """
    await app.state.redis.flushdb()
    _patch_gym_hours_always_open(monkeypatch)

    staff = await _seed_staff(db_session)
    client = await _seed_client(db_session, staff, phone="+79200000002")
    client_id = client.id  # capture before any SAVEPOINT rollback expires the instance
    await _seed_active_membership(db_session, client_id)

    # Mint two valid QR tokens (different iat/exp) for the same client
    token1 = encode_qr_token(client_id)
    token2 = encode_qr_token(client_id)

    # First check-in → 200 success
    r1 = await http_client.post("/api/v1/client/check-in", json={"token": token1})
    assert r1.status_code == 200, r1.text
    assert r1.json()["data"]["channel"] == "client_qr"

    # Second check-in (same gym_date) → 409 duplicate_checkin
    r2 = await http_client.post("/api/v1/client/check-in", json={"token": token2})
    assert r2.status_code == 409, r2.text
    assert r2.json()["code"] == "duplicate_checkin"

    # DB: exactly one visit for this client today (SAVEPOINT harness — rollback to outer)
    visits = (
        await db_session.execute(select(Visit).where(Visit.client_id == client_id))
    ).scalars().all()
    assert len(visits) == 1
    assert visits[0].channel == "client_qr"


# ---------------------------------------------------------------------------
# Test 3a: Access token at /check-in → 401 wrong_token_type (T-70-16)
# ---------------------------------------------------------------------------


async def test_access_token_at_checkin_rejected(
    http_client: AsyncClient,
    db_session: AsyncSession,
    app: FastAPI,
) -> None:
    """T-70-16: an access token (aud='client', typ='access') at /check-in → 401.

    decode_qr_token asserts typ='qr_checkin'; finding typ='access' raises
    InvalidAccessToken('wrong_token_type').
    """
    await app.state.redis.flushdb()
    staff = await _seed_staff(db_session)
    client = await _seed_client(db_session, staff, phone="+79200000003")

    # Mint a client ACCESS token (not a QR token)
    access_token = encode_client_token(client.id)

    r = await http_client.post(
        "/api/v1/client/check-in",
        json={"token": access_token},
    )
    assert r.status_code == 401, r.text
    body = r.json()
    # HTTP response: code = "invalid_token" (InvalidAccessToken class default).
    # The specific discriminator is in message: decode_qr_token checks typ first,
    # so an access token (typ='access') raises wrong_token_type.
    assert body["code"] == "invalid_token", f"Expected 'invalid_token', got: {body['code']}"
    assert body["message"] in ("wrong_token_type", "wrong_audience"), (
        f"Expected wrong_token_type or wrong_audience, got: {body['message']}"
    )


# ---------------------------------------------------------------------------
# Test 3b: QR token at authenticated endpoint → 401 (T-70-16 reverse direction)
# ---------------------------------------------------------------------------


async def test_qr_token_at_authenticated_endpoint_rejected(
    http_client: AsyncClient,
    db_session: AsyncSession,
    app: FastAPI,
) -> None:
    """T-70-16: a QR token (aud='qr', typ='qr_checkin') does NOT pass require_client().

    GET /client/membership requires a client access token (aud='client', typ='access').
    A QR token has aud='qr' — decode_client_token raises wrong_audience → 401.
    This confirms the token types are non-interchangeable in BOTH directions.
    """
    await app.state.redis.flushdb()
    staff = await _seed_staff(db_session)
    client = await _seed_client(db_session, staff, phone="+79200000004")

    # Mint a QR token (NOT a client access token)
    qr_token = encode_qr_token(client.id)

    # Use a dedicated client with the QR token as the access cookie.
    # The ASGITransport is shared via http_client._transport.
    transport = http_client._transport
    async with AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as qr_client:
        # Set the QR token directly on the cookie jar for the specific domain
        qr_client.cookies.set("cc_client_access", qr_token)
        r = await qr_client.get("/api/v1/client/membership")

    assert r.status_code == 401, r.text
    body = r.json()
    # HTTP response: code = "invalid_token" (InvalidAccessToken class default).
    # decode_client_token: typ='qr_checkin' → wrong_token_type (type check before aud).
    assert body["code"] == "invalid_token", f"Expected 'invalid_token', got: {body['code']}"
    assert body["message"] in ("wrong_token_type", "wrong_audience"), (
        f"Expected wrong_token_type or wrong_audience, got: {body['message']}"
    )


# ---------------------------------------------------------------------------
# Test 4: Cross-client structural impossibility (T-70-17 / D-70-10)
# ---------------------------------------------------------------------------


async def test_cross_client_checkin_structurally_impossible(
    http_client: AsyncClient,
    db_session: AsyncSession,
    app: FastAPI,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """T-70-17 / criterion #5: client B's QR token checks in client B, not client A.

    client_id derives ONLY from the verified QR token's sub claim — there is no
    body/path/query parameter to target a different client. Presenting client B's
    token under client A's session still checks in client B (the token owner).

    After check-in, we verify the created Visit row belongs to client B (sub owner),
    not client A (the authenticated session holder).
    """
    await app.state.redis.flushdb()
    _patch_gym_hours_always_open(monkeypatch)

    staff = await _seed_staff(db_session)
    client_a = await _seed_client(db_session, staff, phone="+79200000005")
    client_b = await _seed_client(db_session, staff, phone="+79200000006")

    # Capture IDs before any SAVEPOINT rollback expires the ORM instances
    client_a_id = client_a.id
    client_b_id = client_b.id

    # Only client B has an active membership (so only client B can check in)
    await _seed_active_membership(db_session, client_b_id)

    # Authenticate as client A (session cookies on http_client are for A)
    await _auth_as_client(http_client, db_session, client_a)

    # Mint a QR token for client B (simulates B showing their QR code at the scanner)
    client_b_token = encode_qr_token(client_b_id)

    # Present client B's token (while authenticated as A via session cookies)
    # The endpoint MUST check in client B (the token's sub), not client A
    r = await http_client.post(
        "/api/v1/client/check-in",
        json={"token": client_b_token},
    )
    assert r.status_code == 200, r.text
    visit_data = r.json()["data"]
    assert visit_data["channel"] == "client_qr"

    # Verify the visit row belongs to client B (the token's sub), NOT client A
    visit_rows = (
        await db_session.execute(select(Visit).where(Visit.channel == "client_qr"))
    ).scalars().all()
    assert len(visit_rows) == 1, f"Expected exactly 1 QR visit, got {len(visit_rows)}"
    assert visit_rows[0].client_id == client_b_id, (
        f"Visit client_id={visit_rows[0].client_id} must be client B ({client_b_id}), "
        f"not client A ({client_a_id})"
    )
    # Structural proof: no body/path request parameter could have changed the target
    # The visit was created for B by token sub, not by any injectable client_id


async def test_no_request_parameter_can_override_checkin_target(
    http_client: AsyncClient,
    db_session: AsyncSession,
    app: FastAPI,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """D-70-10: injecting a client_id in the body has no effect on which client is checked in.

    ClientCheckInRequest has no client_id field; extra fields are silently ignored
    (ResponseData extra='ignore'). The visit is always created for the token's sub owner.
    This test confirms that even if a client_id is injected into the body, the check-in
    targets the token owner (client B), not the injected client A.
    """
    await app.state.redis.flushdb()
    _patch_gym_hours_always_open(monkeypatch)

    staff = await _seed_staff(db_session)
    client_a = await _seed_client(db_session, staff, phone="+79200000007")
    client_b = await _seed_client(db_session, staff, phone="+79200000008")

    # Capture IDs before any SAVEPOINT rollback expires the ORM instances
    client_a_id = client_a.id
    client_b_id = client_b.id

    await _seed_active_membership(db_session, client_b_id)

    # Mint a QR token for client B
    client_b_token = encode_qr_token(client_b_id)

    # Attempt to inject client A's ID alongside client B's token
    r = await http_client.post(
        "/api/v1/client/check-in",
        # client_id / clientId is an extra field — silently ignored by ResponseData
        json={"token": client_b_token, "clientId": str(client_a_id)},
    )
    assert r.status_code == 200, r.text

    # Visit must be for client B (token sub), not client A (injected field)
    visit_rows = (
        await db_session.execute(select(Visit).where(Visit.channel == "client_qr"))
    ).scalars().all()
    assert len(visit_rows) == 1
    assert visit_rows[0].client_id == client_b_id, (
        f"Injected clientId={client_a_id} must NOT override the token sub. "
        f"Visit belongs to {visit_rows[0].client_id}, expected client B ({client_b_id})"
    )
