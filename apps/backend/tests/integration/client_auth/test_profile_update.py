"""PATCH /client/me email round-trip + duplicate-email 409 coverage (Phase 68 SC4).

Closes the SC4 verification gap: proves that PATCH /api/v1/client/me accepts a valid
email update, commits it to the database, and a subsequent GET /me returns the updated
value.  Also covers the 409 duplicate-email case (D-06).

Tests:
  1. test_patch_me_email_round_trip (SC4 / CAUTH-05 / D-04):
       Authenticate as linked_client → PATCH /me with a new email → assert 200 +
       response body reflects the new email → GET /me → assert email equals the
       patched value.  Proves DB persistence end-to-end.

  2. test_patch_me_duplicate_email_409 (D-06):
       Create a second alive client with a specific email → authenticate as
       linked_client → PATCH /me using the second client's email → assert 409
       with code 'email_unavailable' (non-enumerating, does not reveal owner) →
       GET /me → assert linked_client's email is still the original (unchanged).

Harness: SAVEPOINT rollback + ASGITransport async_client from root conftest.py.
Fixtures from tests/integration/client_auth/conftest.py.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import AsyncClient
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import User
from app.modules.clients.models import Client

# Re-use the OTP helper from the lifecycle tests to avoid duplication.
from tests.integration.client_auth.test_session_lifecycle import (
    _request_otp_and_get_raw_code,
)

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Helper: authenticate a client and return (access_token, csrf_token)
# ---------------------------------------------------------------------------


async def _authenticate_client(
    async_client: AsyncClient,
    db_session: AsyncSession,
    client: Client,
) -> tuple[str, str]:
    """Full OTP request → verify flow; returns (access_token, csrf_token) strings.

    Mirrors the authentication steps in test_full_session_lifecycle so the
    PATCH /me tests start from a valid authenticated session.
    """
    raw_code = await _request_otp_and_get_raw_code(async_client, db_session, client)

    verify = await async_client.post(
        "/api/v1/client/otp/verify",
        json={"phone": client.phone, "code": raw_code},
    )
    assert verify.status_code == 200, f"OTP verify failed: {verify.text}"

    set_cookies = verify.headers.get_list("set-cookie")

    access_hdr = next(c for c in set_cookies if c.startswith("cc_client_access="))
    csrf_hdr = next(c for c in set_cookies if c.startswith("clubcore_client_csrf="))

    access_token = access_hdr.split("=", 1)[1].split(";", 1)[0]
    csrf_token = csrf_hdr.split("=", 1)[1].split(";", 1)[0]

    return access_token, csrf_token


# ---------------------------------------------------------------------------
# Fixture: a second alive client used for the 409 duplicate-email test
# ---------------------------------------------------------------------------

_OTHER_PHONE = "+79990000042"
_OTHER_EMAIL = "other-alive-client@example.com"


@pytest_asyncio.fixture
async def other_alive_client(db_session: AsyncSession, seeded_staff: User) -> Client:
    """Second alive Client with a known email — used to trigger duplicate-email 409."""
    suffix = uuid4().hex[:6]
    client = Client(
        first_name="Other",
        last_name=f"Alive{suffix}",
        phone=_OTHER_PHONE,
        email=_OTHER_EMAIL,
        telegram_user_id=None,  # not needed — this client is only a DB record
        created_by_user_id=seeded_staff.id,
    )
    db_session.add(client)
    await db_session.commit()
    return client


# ---------------------------------------------------------------------------
# SC4 / CAUTH-05 / D-04: email round-trip
# ---------------------------------------------------------------------------


async def test_patch_me_email_round_trip(
    async_client: AsyncClient,
    db_session: AsyncSession,
    linked_client: Client,
    redis_clean: Redis,
) -> None:
    """SC4: PATCH /me → 200 with new email; GET /me → email equals patched value.

    This is the observable round-trip behavior described in ROADMAP success
    criterion 4 and CAUTH-05.  The test proves that:
      - update_client_me() commits the new email to the database.
      - A subsequent GET /me issues a fresh DB query and returns the updated value.
      - The PATCH response body itself already reflects the new email.

    CSRF discipline: PATCH /me requires the x-csrf-token header (T-68-25).
    """
    _ = redis_clean

    access_token, csrf_token = await _authenticate_client(async_client, db_session, linked_client)

    new_email = f"updated-{uuid4().hex[:8]}@example.com"

    # PATCH /me with a valid new email — requires both cookie + CSRF header.
    patch_resp = await async_client.patch(
        "/api/v1/client/me",
        json={"email": new_email},
        headers={
            "Cookie": f"cc_client_access={access_token}; clubcore_client_csrf={csrf_token}",
            "x-csrf-token": csrf_token,
        },
    )
    assert patch_resp.status_code == 200, (
        f"PATCH /me expected 200, got {patch_resp.status_code}: {patch_resp.text}"
    )

    patch_data = patch_resp.json()["data"]
    assert patch_data["email"] == new_email, (
        f"PATCH response should reflect new email immediately: {patch_data}"
    )
    assert patch_data["id"] == str(linked_client.id), f"PATCH response id mismatch: {patch_data}"

    # GET /me — fresh DB query via load_client_by_id.
    get_resp = await async_client.get(
        "/api/v1/client/me",
        headers={"Cookie": f"cc_client_access={access_token}"},
    )
    assert get_resp.status_code == 200, (
        f"GET /me after PATCH expected 200, got {get_resp.status_code}: {get_resp.text}"
    )

    get_data = get_resp.json()["data"]
    assert get_data["email"] == new_email, (
        f"GET /me after PATCH should return updated email.\n"
        f"  Expected: {new_email}\n"
        f"  Got:      {get_data['email']}"
    )


# ---------------------------------------------------------------------------
# D-06: duplicate-email 409 — generic, non-enumerating
# ---------------------------------------------------------------------------


async def test_patch_me_duplicate_email_409(
    async_client: AsyncClient,
    db_session: AsyncSession,
    linked_client: Client,
    other_alive_client: Client,
    redis_clean: Redis,
) -> None:
    """D-06: PATCH /me with an email held by another alive client → 409 email_unavailable.

    The 409 is non-enumerating: no indication of which account holds the address.
    After the 409, the authenticated client's email remains unchanged.

    Uses `other_alive_client` fixture (alive, email=_OTHER_EMAIL) as the collision target.
    """
    _ = redis_clean
    _ = other_alive_client  # ensure fixture is created in DB before the PATCH

    # Set a unique initial email on linked_client so we can verify it is unchanged later.
    original_email = f"original-{uuid4().hex[:8]}@example.com"
    linked_client.email = original_email
    await db_session.commit()

    access_token, csrf_token = await _authenticate_client(async_client, db_session, linked_client)

    # Attempt to claim the other client's email address.
    patch_resp = await async_client.patch(
        "/api/v1/client/me",
        json={"email": _OTHER_EMAIL},
        headers={
            "Cookie": f"cc_client_access={access_token}; clubcore_client_csrf={csrf_token}",
            "x-csrf-token": csrf_token,
        },
    )
    assert patch_resp.status_code == 409, (
        f"D-06: duplicate email should return 409, got {patch_resp.status_code}: {patch_resp.text}"
    )

    body = patch_resp.json()
    # ConflictError base class uses code="conflict"; the domain error string
    # is carried in the message field (e.g. ConflictError("email_unavailable")).
    assert body.get("code") == "conflict", (
        f"D-06: 409 body should have code='conflict' (ConflictError base): {body}"
    )
    assert body.get("message") == "email_unavailable", (
        f"D-06: 409 body should carry message='email_unavailable' (non-enumerating): {body}"
    )

    # Verify email is still the original value — the PATCH was a no-op.
    get_resp = await async_client.get(
        "/api/v1/client/me",
        headers={"Cookie": f"cc_client_access={access_token}"},
    )
    assert get_resp.status_code == 200, (
        f"GET /me after 409 expected 200, got {get_resp.status_code}: {get_resp.text}"
    )

    get_data = get_resp.json()["data"]
    assert get_data["email"] == original_email, (
        f"D-06: email must be unchanged after a failed 409 PATCH.\n"
        f"  Expected: {original_email}\n"
        f"  Got:      {get_data['email']}"
    )
