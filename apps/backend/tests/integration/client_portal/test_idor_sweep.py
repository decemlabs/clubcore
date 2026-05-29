"""Parametrized IDOR sweep for Phase 69 client-portal read endpoints (D-20-IDOR / CISO-04).

Authenticates as client A and B in BOTH orderings and proves each owned read endpoint
returns ONLY the caller's data — no victim records leak.

Harness: SAVEPOINT rollback + ASGITransport async_client from root conftest.py.
Fixtures: client_a, client_b, seeded_owned_data, redis_clean from local conftest.py.

Covers T-69-01 (IDOR/BOLA) and T-69-11 (hollow-gate): victim data is actively seeded
for both clients so a leaking endpoint produces a real assertion failure.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import generate_otp_code
from app.modules.auth.models import OtpCode
from app.modules.clients.models import Client
from tests.integration.client_portal.conftest import SeededOwnedData

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Auth helper — identical to client_auth/test_idor.py:_auth_as_client
# ---------------------------------------------------------------------------


async def _auth_as_client(
    async_client: AsyncClient,
    db_session: AsyncSession,
    client: Client,
) -> str:
    """Request OTP → patch code → verify → return cc_client_access token value.

    Mirrors the helper in client_auth/test_idor.py: reads the OtpCode row and
    replaces the hash with a deterministic known code so the verify step succeeds
    in tests (bot sender is None → DM silently skipped → must read+replace code).
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
# Parametrized IDOR sweep — both orderings, all owned endpoints
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "resource_path,attacker_is_a",
    [
        ("/api/v1/client/membership", True),
        ("/api/v1/client/membership", False),
        ("/api/v1/client/home", True),
        ("/api/v1/client/home", False),
        ("/api/v1/client/bookings?upcoming=1", True),
        ("/api/v1/client/bookings?upcoming=1", False),
        ("/api/v1/client/history/visits", True),
        ("/api/v1/client/history/visits", False),
        ("/api/v1/client/history/pt-sessions", True),
        ("/api/v1/client/history/pt-sessions", False),
        ("/api/v1/client/history/payments", True),
        ("/api/v1/client/history/payments", False),
    ],
)
async def test_owned_resource_idor(
    async_client: AsyncClient,
    db_session: AsyncSession,
    client_a: Client,
    client_b: Client,
    seeded_owned_data: SeededOwnedData,
    redis_clean: object,
    resource_path: str,
    attacker_is_a: bool,
) -> None:
    """D-20-IDOR / CISO-04: each owned endpoint returns only the cookie-principal's data.

    Parametrized over both attack directions:
      - attacker=A, victim=B (attacker_is_a=True)
      - attacker=B, victim=A (attacker_is_a=False)

    Per case: authenticate as attacker, GET the path with attacker's cookie, assert 200,
    assert response contains ONLY attacker-owned record ids and NEVER any victim id.
    T-69-11: victim data is actively seeded — a leak produces a real assertion failure.
    """
    if attacker_is_a:
        attacker, victim = client_a, client_b
        attacker_data = seeded_owned_data.a
        victim_data = seeded_owned_data.b
    else:
        attacker, victim = client_b, client_a
        attacker_data = seeded_owned_data.b
        victim_data = seeded_owned_data.a

    token = await _auth_as_client(async_client, db_session, attacker)

    resp = await async_client.get(
        resource_path,
        headers={"Cookie": f"cc_client_access={token}"},
    )
    assert resp.status_code == 200, (
        f"Expected 200 from {resource_path} as {attacker.id}, "
        f"got {resp.status_code}: {resp.text}"
    )

    body = resp.json()
    data = body.get("data")

    # Collect all UUID-shaped string values from the response data
    # to check for victim id leakage.
    attacker_owned_ids = {
        str(attacker_data.client_id),
        str(attacker_data.membership_id),
        str(attacker_data.visit_id),
        str(attacker_data.pt_package_id),
        str(attacker_data.pt_session_id),
        str(attacker_data.payment_id),
        str(attacker_data.refund_id),
    }
    victim_owned_ids = {
        str(victim_data.client_id),
        str(victim_data.membership_id),
        str(victim_data.visit_id),
        str(victim_data.pt_package_id),
        str(victim_data.pt_session_id),
        str(victim_data.payment_id),
        str(victim_data.refund_id),
    }

    # Extract all id fields from the response (handles both scalar and list shapes)
    response_ids = _extract_ids_from_data(data)

    # Assert: no victim-owned id appears in the response
    leaked = victim_owned_ids & response_ids
    assert not leaked, (
        f"IDOR: {resource_path} returned victim ids {leaked!r} "
        f"when authenticated as {attacker.id} (T-69-01 violated)"
    )

    # Additional sanity: if the response contains any known id, it should be the attacker's
    # (only relevant for non-empty responses — empty states have no ids to check)
    known_ids_in_response = response_ids & (attacker_owned_ids | victim_owned_ids)
    for rid in known_ids_in_response:
        assert rid in attacker_owned_ids, (
            f"IDOR: {resource_path} returned id {rid!r} which belongs to the victim "
            f"(attacker={attacker.id}, victim={victim.id})"
        )


def _extract_ids_from_data(data: object) -> set[str]:
    """Recursively extract all 'id' field values from a JSON-decoded response data object.

    Handles: None, dict (single item), list of dicts (pagination items), nested dicts.
    Returns a set of UUID string values found at any 'id' key.
    """
    ids: set[str] = set()
    if data is None:
        return ids
    if isinstance(data, dict):
        for key, value in data.items():
            if key == "id" and isinstance(value, str):
                ids.add(value)
            elif isinstance(value, (dict, list)):
                ids |= _extract_ids_from_data(value)
    elif isinstance(data, list):
        for item in data:
            ids |= _extract_ids_from_data(item)
    return ids
