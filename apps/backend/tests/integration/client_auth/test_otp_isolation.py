"""Two-principal isolation + anti-oracle byte-parity tests (Phase 68 Plan 06).

Tests:
  1. test_staff_token_rejected_by_client_endpoint (CISO-02):
     A staff `cc_access` token presented as `cc_client_access` to GET /api/v1/client/me
     must return 401. Isolation is structural: decode_client_token asserts aud="client",
     which staff tokens do not carry.

  2. test_client_token_rejected_by_staff_endpoint (CISO-02 reverse):
     A client `cc_client_access` token presented as `cc_access` to GET /api/v1/clients
     must return 401. The staff decode_access_token validates `role` against Role enum;
     client tokens carry aud="client" and no role, so decoding always fails.

  3. test_otp_request_anti_oracle (CAUTH-02, per-case 202 check):
     POST /api/v1/client/otp/request parametrized over 4 phone states returns 202 each.

  4. test_otp_request_anti_oracle_body_parity (CAUTH-02, byte-identical body check):
     All 4 phone states in a single test to assert byte-identical response body.

Harness: SAVEPOINT rollback + ASGITransport async_client from root conftest.py.
Fixtures: linked_client, unlinked_client, soft_deleted_client, redis_clean, seeded_staff
          come from tests/integration/client_auth/conftest.py (auto-discovered by pytest).

Note: httpx ≥0.27 raises DeprecationWarning for per-request cookies={}; use
      headers={"Cookie": "name=value"} to pass cookies without triggering the warning.
      Pytest filterwarnings=error treats all warnings as errors.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from httpx import AsyncClient
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.permissions import Role
from app.core.security import generate_otp_code, hash_password
from app.modules.auth.models import OtpCode, User
from app.modules.clients.models import Client

pytestmark = pytest.mark.asyncio

_STAFF_EMAIL = "staff-isolation-test@example.com"
_STAFF_PASSWORD = "isolation-test-pw-secure-12"  # noqa: S105 — test literal

# Phone string that has no Client row in DB — used for the unknown-phone case
_UNKNOWN_PHONE = "+79990000099"


@pytest_asyncio.fixture
async def seeded_staff_user(db_session: AsyncSession, redis_clean: Redis) -> User:
    """Seed a RECEPTION staff user for the isolation tests."""
    _ = redis_clean  # flush fixture ensures clean state
    user = User(
        email=_STAFF_EMAIL,
        password_hash=await hash_password(_STAFF_PASSWORD),
        role=Role.RECEPTION,
        full_name="Isolation Test Staff",
    )
    db_session.add(user)
    await db_session.commit()
    return user


async def _authenticate_client(
    async_client: AsyncClient,
    db_session: AsyncSession,
    client: Client,
) -> str:
    """Request OTP → patch code in OtpCode row → verify → return cc_client_access token value.

    Since the bot sender is None in tests (silently skipped), we read the OtpCode row
    written by request_client_otp and replace its code_hash with a known code so we
    can verify it (plan 68-06 notes: "read the persisted OtpCode row from db_session").
    """
    req = await async_client.post(
        "/api/v1/client/otp/request",
        json={"phone": client.phone},
    )
    assert req.status_code == 202, f"OTP request failed: {req.text}"

    # Read the OtpCode row and replace with known code
    otp_row = await db_session.scalar(
        select(OtpCode).where(
            OtpCode.client_id == client.id,
            OtpCode.consumed_at.is_(None),
        )
    )
    assert otp_row is not None, "OtpCode row not found after otp/request"

    settings = get_settings()
    raw_code, code_hash = generate_otp_code()
    otp_row.code_hash = code_hash
    otp_row.expires_at = datetime.now(tz=UTC) + timedelta(seconds=settings.otp_code_ttl_seconds)
    await db_session.commit()

    verify = await async_client.post(
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


async def test_staff_token_rejected_by_client_endpoint(
    async_client: AsyncClient,
    seeded_staff_user: User,
) -> None:
    """CISO-02: a staff cc_access token presented as cc_client_access → 401.

    Flow:
      1. Staff user logs in via /auth/login → gets cc_access cookie.
      2. Present the cc_access token value as cc_client_access to GET /api/v1/client/me.
      3. Assert 401 — decode_client_token rejects it (missing aud="client").
    """
    _ = seeded_staff_user  # ensure staff user is seeded before login
    login = await async_client.post(
        "/api/v1/auth/login",
        json={"email": _STAFF_EMAIL, "password": _STAFF_PASSWORD},
    )
    assert login.status_code == 200, f"Staff login failed: {login.text}"

    set_cookies = login.headers.get_list("set-cookie")
    access_cookie = next(
        (c for c in set_cookies if c.startswith("cc_access=")),
        None,
    )
    assert access_cookie is not None, "cc_access cookie not in staff login response"
    staff_token = access_cookie.split("=", 1)[1].split(";", 1)[0]

    # Present the staff token as cc_client_access — MUST be rejected.
    # Use Cookie header directly to avoid httpx per-request cookies deprecation warning.
    resp = await async_client.get(
        "/api/v1/client/me",
        headers={"Cookie": f"cc_client_access={staff_token}"},
    )
    assert resp.status_code == 401, (
        f"Expected 401 (staff token on client endpoint), got {resp.status_code}: {resp.text}"
    )


async def test_client_token_rejected_by_staff_endpoint(
    async_client: AsyncClient,
    db_session: AsyncSession,
    linked_client: Client,
    redis_clean: Redis,
) -> None:
    """CISO-02 reverse: a client cc_client_access token presented as cc_access → 401.

    Flow:
      1. Authenticate as the linked client → get cc_client_access cookie.
      2. Present that token value as cc_access to GET /api/v1/clients (staff endpoint).
      3. Assert 401 — decode_access_token rejects it (client token lacks role field).
    """
    _ = redis_clean  # flush fixture
    client_token = await _authenticate_client(async_client, db_session, linked_client)

    # Present the client token as cc_access to a staff-protected endpoint.
    # Use Cookie header directly to avoid httpx per-request cookies deprecation warning.
    resp = await async_client.get(
        "/api/v1/clients",
        headers={"Cookie": f"cc_access={client_token}"},
    )
    assert resp.status_code == 401, (
        f"Expected 401 (client token on staff endpoint), got {resp.status_code}: {resp.text}"
    )


@pytest.mark.parametrize(
    "phone_fixture",
    [
        "linked_phone",
        "unlinked_phone",
        "unknown_phone",
        "soft_deleted_phone",
    ],
)
async def test_otp_request_anti_oracle(
    async_client: AsyncClient,
    linked_client: Client,
    unlinked_client: Client,
    soft_deleted_client: Client,
    redis_clean: Redis,
    phone_fixture: str,
) -> None:
    """CAUTH-02: POST /api/v1/client/otp/request returns 202 for each of 4 phone states.

    Each parametrize case independently asserts status 202. The byte-parity assertion
    is in test_otp_request_anti_oracle_body_parity (all 4 cases in one test invocation).
    Redis is flushed per test via redis_clean so rate-limit keys don't interfere.
    """
    _ = redis_clean  # flush fixture
    phone_map = {
        "linked_phone": linked_client.phone,
        "unlinked_phone": unlinked_client.phone,
        "unknown_phone": _UNKNOWN_PHONE,
        "soft_deleted_phone": soft_deleted_client.phone,
    }
    phone = phone_map[phone_fixture]

    resp = await async_client.post(
        "/api/v1/client/otp/request",
        json={"phone": phone},
    )
    assert resp.status_code == 202, (
        f"Expected 202 for {phone_fixture} ({phone}), got {resp.status_code}: {resp.text}"
    )


async def test_otp_request_anti_oracle_body_parity(
    async_client: AsyncClient,
    linked_client: Client,
    unlinked_client: Client,
    soft_deleted_client: Client,
    redis_clean: Redis,
) -> None:
    """CAUTH-02: ALL 4 phone states MUST produce a byte-identical response body.

    Runs all 4 cases in a single test so bodies can be compared directly.
    This is the definitive anti-oracle byte-parity assertion (D-02).
    """
    _ = redis_clean  # flush fixture
    cases = [
        ("linked", linked_client.phone),
        ("unlinked", unlinked_client.phone),
        ("unknown", _UNKNOWN_PHONE),
        ("soft_deleted", soft_deleted_client.phone),
    ]

    results = []
    for name, phone in cases:
        resp = await async_client.post(
            "/api/v1/client/otp/request",
            json={"phone": phone},
        )
        results.append((name, resp.status_code, resp.content, resp.headers.get("content-type")))

    # All must be 202
    non_202 = [(name, sc) for name, sc, _, _ in results if sc != 202]
    assert not non_202, f"Non-202 status in anti-oracle sweep: {non_202}"

    # All bodies must be byte-identical (anti-oracle invariant D-02)
    bodies = {content for _, _, content, _ in results}
    assert len(bodies) == 1, (
        "Response body diverges across phone states — anti-oracle leak! "
        f"Per-case bodies: {[(name, body) for name, _, body, _ in results]}"
    )

    # All content-types must be identical
    ctypes = {ct for _, _, _, ct in results}
    assert len(ctypes) == 1, (
        f"Content-Type diverges across phone states: {[(name, ct) for name, _, _, ct in results]}"
    )
