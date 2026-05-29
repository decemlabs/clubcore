"""Parametrized IDOR sweep for GET /api/v1/client/me (Phase 68 Plan 06 — CISO-04).

Each authenticated client MUST only receive their own principal id from GET /me.
Cross-client reads are impossible by design: `require_client()` resolves the cookie
principal — there is no `client_id` URL param that could be manipulated.

Test: seed clients A and B; parametrize (attacker, victim) over both orderings;
authenticate as the attacker; GET /me; assert returned id == attacker.id AND != victim.id.

Harness: SAVEPOINT rollback + ASGITransport async_client from root conftest.py.
Fixtures from tests/integration/client_auth/conftest.py: seeded_staff, redis_clean.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import AsyncClient
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import generate_otp_code
from app.modules.auth.models import OtpCode, User
from app.modules.clients.models import Client

pytestmark = pytest.mark.asyncio


async def _auth_as_client(
    async_client: AsyncClient,
    db_session: AsyncSession,
    client: Client,
) -> str:
    """Request OTP → patch code → verify → return cc_client_access token value.

    Mirrors the helper in test_otp_isolation.py: reads the OtpCode row and replaces
    the hash with a deterministic known code so the verify step succeeds in tests
    (bot sender is None → DM is silently skipped → we must read+replace the code).
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


@pytest_asyncio.fixture
async def client_a(db_session: AsyncSession, seeded_staff: User) -> Client:
    """First linked client — party A in the IDOR parametrize sweep."""
    client = Client(
        first_name="IDOR",
        last_name=f"ClientA-{uuid4().hex[:6]}",
        phone="+79991110001",
        telegram_user_id=111_000_001,
        created_by_user_id=seeded_staff.id,
    )
    db_session.add(client)
    await db_session.commit()
    return client


@pytest_asyncio.fixture
async def client_b(db_session: AsyncSession, seeded_staff: User) -> Client:
    """Second linked client — party B in the IDOR parametrize sweep."""
    client = Client(
        first_name="IDOR",
        last_name=f"ClientB-{uuid4().hex[:6]}",
        phone="+79991110002",
        telegram_user_id=111_000_002,
        created_by_user_id=seeded_staff.id,
    )
    db_session.add(client)
    await db_session.commit()
    return client


@pytest.mark.parametrize("attacker_is_a", [True, False])
async def test_get_me_returns_only_own_id(
    async_client: AsyncClient,
    db_session: AsyncSession,
    client_a: Client,
    client_b: Client,
    redis_clean: Redis,
    attacker_is_a: bool,
) -> None:
    """CISO-04: GET /api/v1/client/me returns only the cookie principal's id.

    Parametrized over both attack directions:
      - attacker=A, victim=B (attacker_is_a=True)
      - attacker=B, victim=A (attacker_is_a=False)

    In both cases: returned data.id == attacker.id AND != victim.id.
    There is no cross-client read path — /me resolves from the access cookie only.
    """
    if attacker_is_a:
        attacker, victim = client_a, client_b
    else:
        attacker, victim = client_b, client_a

    # Authenticate as the attacker
    attacker_token = await _auth_as_client(async_client, db_session, attacker)

    # GET /me with the attacker's token.
    # Use Cookie header directly to avoid httpx per-request cookies deprecation warning.
    resp = await async_client.get(
        "/api/v1/client/me",
        headers={"Cookie": f"cc_client_access={attacker_token}"},
    )
    assert resp.status_code == 200, (
        f"Expected 200 from /me as {attacker.id}, got {resp.status_code}: {resp.text}"
    )

    data = resp.json()["data"]
    returned_id = data["id"]

    # The returned id MUST be the attacker's own id — never the victim's.
    assert returned_id == str(attacker.id), (
        f"IDOR: /me returned {returned_id!r} but expected attacker id {attacker.id!r}"
    )
    assert returned_id != str(victim.id), (
        f"IDOR: /me returned victim id {victim.id!r} — cross-client read exposed!"
    )
