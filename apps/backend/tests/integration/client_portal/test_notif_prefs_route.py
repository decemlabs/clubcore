"""Phase 75 Plan 01 Task 3 — ASGI-level route tests for notif_prefs + membership price fields.

Behaviors proven (PMEM-01, NOTIF-01):
  - PATCH /client/me with notifPrefs (all four keys) → 200; GET round-trips the prefs.
  - GET /client/me returns notifPrefs defaults (promo=True, sound=False) when unset.
  - PATCH /client/me with an unknown notifPrefs key → 422.
  - GET /client/membership returns integer priceKopecks (> 0) and autoRenew = null.

Harness: SAVEPOINT rollback + ASGITransport async_client from root conftest.py.
Auth: _auth_as_client_with_csrf from test_client_me_route.py (OTP flow + CSRF cookie).
Fixtures: client_a, seeded_owned_data, redis_clean from conftest.py.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.clients.models import Client
from tests.integration.client_portal.conftest import SeededOwnedData
from tests.integration.client_portal.test_client_me_route import _auth_as_client_with_csrf
from tests.integration.client_portal.test_idor_sweep import _auth_as_client

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _get_authed(
    async_client: AsyncClient,
    db_session: AsyncSession,
    client: Client,
    path: str,
) -> dict:  # type: ignore[type-arg]
    """Auth as client (GET-only, no CSRF) and GET path; return parsed JSON body."""
    token = await _auth_as_client(async_client, db_session, client)
    resp = await async_client.get(path, headers={"Cookie": f"cc_client_access={token}"})
    return resp.json()  # type: ignore[no-any-return]


# ---------------------------------------------------------------------------
# NOTIF-01: notifPrefs PATCH + GET round-trip
# ---------------------------------------------------------------------------


async def test_patch_me_notif_prefs_round_trips(
    async_client: AsyncClient,
    db_session: AsyncSession,
    client_a: Client,
    redis_clean: object,
) -> None:
    """NOTIF-01: PATCH /client/me with notifPrefs (all four keys) → 200; GET reflects prefs."""
    _ = redis_clean
    access, csrf = await _auth_as_client_with_csrf(async_client, db_session, client_a)

    resp = await async_client.patch(
        "/api/v1/client/me",
        json={"notifPrefs": {"promo": False, "schedule": True, "trainer": False, "sound": True}},
        headers={
            "Cookie": f"cc_client_access={access}; clubcore_client_csrf={csrf}",
            "x-csrf-token": csrf,
        },
    )
    assert resp.status_code == 200, (
        f"PATCH /client/me with notifPrefs should be 200, got {resp.status_code}: {resp.text}"
    )
    data = resp.json()["data"]
    assert "notifPrefs" in data, f"notifPrefs missing from PATCH response: {data}"
    assert data["notifPrefs"]["promo"] is False
    assert data["notifPrefs"]["schedule"] is True
    assert data["notifPrefs"]["trainer"] is False
    assert data["notifPrefs"]["sound"] is True

    # Verify GET also returns persisted prefs
    get_resp = await async_client.get(
        "/api/v1/client/me",
        headers={"Cookie": f"cc_client_access={access}"},
    )
    assert get_resp.status_code == 200, get_resp.text
    get_data = get_resp.json()["data"]
    assert get_data["notifPrefs"]["promo"] is False
    assert get_data["notifPrefs"]["schedule"] is True
    assert get_data["notifPrefs"]["trainer"] is False
    assert get_data["notifPrefs"]["sound"] is True


async def test_get_me_notif_prefs_defaults_when_never_patched(
    async_client: AsyncClient,
    db_session: AsyncSession,
    client_a: Client,
    redis_clean: object,
) -> None:
    """NOTIF-01 D-06: GET /client/me returns server defaults when notifPrefs never written."""
    _ = redis_clean
    access, _csrf = await _auth_as_client_with_csrf(async_client, db_session, client_a)

    resp = await async_client.get(
        "/api/v1/client/me",
        headers={"Cookie": f"cc_client_access={access}"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert "notifPrefs" in data, f"notifPrefs missing from GET /client/me response: {data}"
    # Server defaults: promo=True, schedule=True, trainer=True, sound=False
    assert data["notifPrefs"]["promo"] is True, (
        f"Default promo should be True: {data['notifPrefs']}"
    )
    assert data["notifPrefs"]["sound"] is False, (
        f"Default sound should be False: {data['notifPrefs']}"
    )


async def test_patch_me_unknown_notif_prefs_key_returns_422(
    async_client: AsyncClient,
    db_session: AsyncSession,
    client_a: Client,
    redis_clean: object,
) -> None:
    """D-04: PATCH /client/me with unknown notifPrefs key → 422 (extra='forbid' on NotifPrefs)."""
    _ = redis_clean
    access, csrf = await _auth_as_client_with_csrf(async_client, db_session, client_a)

    resp = await async_client.patch(
        "/api/v1/client/me",
        json={
            "notifPrefs": {
                "promo": True,
                "schedule": True,
                "trainer": True,
                "sound": False,
                "bogus": True,  # unknown key
            }
        },
        headers={
            "Cookie": f"cc_client_access={access}; clubcore_client_csrf={csrf}",
            "x-csrf-token": csrf,
        },
    )
    assert resp.status_code == 422, (
        f"Unknown notifPrefs key should be rejected with 422, got {resp.status_code}: {resp.text}"
    )


# ---------------------------------------------------------------------------
# PMEM-01: GET /client/membership returns priceKopecks + autoRenew
# ---------------------------------------------------------------------------


async def test_membership_returns_price_kopecks_and_auto_renew(
    async_client: AsyncClient,
    db_session: AsyncSession,
    client_a: Client,
    seeded_owned_data: SeededOwnedData,
    redis_clean: object,
) -> None:
    """PMEM-01: GET /client/membership returns integer priceKopecks (> 0) and autoRenew = null."""
    _ = redis_clean, seeded_owned_data
    body = await _get_authed(async_client, db_session, client_a, "/api/v1/client/membership")
    assert body["data"] is not None, "Expected active membership data, got null"
    data = body["data"]

    assert "priceKopecks" in data, f"priceKopecks missing from membership response: {data}"
    assert isinstance(data["priceKopecks"], int), (
        f"priceKopecks should be int, got {type(data['priceKopecks'])}"
    )
    assert data["priceKopecks"] > 0, (
        f"priceKopecks should be > 0 (seeded plan costs 100_000 kopecks): {data['priceKopecks']}"
    )

    assert "autoRenew" in data, f"autoRenew missing from membership response: {data}"
    assert data["autoRenew"] is None, (
        f"autoRenew should be None (no auto-renewal in v2.1): {data['autoRenew']}"
    )
