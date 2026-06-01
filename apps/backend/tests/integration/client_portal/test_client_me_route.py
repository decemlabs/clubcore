"""ASGI-level route tests for GET + PATCH /api/v1/client/me (Phase 999.5 route consolidation).

REGRESSION GUARD for the route-collision-client-me bug:
  Two routers (client_auth + client_portal) both registered GET/PATCH /me under the
  shared /api/v1/client prefix. FastAPI matches the FIRST-registered route, so the
  client_auth /me pair (email-only PATCH, extra='forbid'; core-identity GET) shadowed
  the Phase 999.5 client_portal onboarding-profile handlers. Onboarding writes 422'd
  ("Extra inputs are not permitted") and the profile read lacked onboardingCompletedAt.

  The pre-existing tests missed this: test_client_me_service.py exercises the SERVICE
  layer directly (bypasses the ASGI route table). These tests go through the REAL route
  table via httpx ASGITransport (async_client fixture), so a future re-introduction of a
  shadowing /me route is caught.

What is asserted (the consolidated contract — client_portal now owns /me):
  1. PATCH /me with the full onboarding body
     {firstName, goal, heightCm, weightKg, onboardingCompleted} → 200, NOT 422.
  2. After PATCH, GET /me exposes the onboarding fields (goal/heightCm/weightKg/
     onboardingCompletedAt) in camelCase — proving the 999.5 GET handler is live.
  3. The receipt-email path still works: PATCH /me {email} → 200 and the email round-trips
     via GET /me (this is what the removed client_auth PATCH /me used to serve).

Harness: SAVEPOINT rollback + ASGITransport async_client from root conftest.py.
Auth: local helper (OTP flow) returning BOTH cc_client_access + clubcore_client_csrf —
PATCH /me is state-changing and requires the CSRF header (RBAC-04 / T-999.5-08).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import generate_otp_code
from app.modules.auth.models import OtpCode
from app.modules.clients.models import Client

pytestmark = pytest.mark.asyncio


async def _auth_as_client_with_csrf(
    async_client: AsyncClient,
    db_session: AsyncSession,
    client: Client,
) -> tuple[str, str]:
    """OTP request → patch code → verify → return (access_token, csrf_token).

    Mirrors test_idor_sweep._auth_as_client but also extracts the
    clubcore_client_csrf cookie so state-changing PATCH /me can present the
    x-csrf-token header (RBAC-04 double-submit).
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
    csrf_cookie = next(
        (c for c in set_cookies if c.startswith("clubcore_client_csrf=")),
        None,
    )
    assert access_cookie is not None, "cc_client_access cookie missing from verify response"
    assert csrf_cookie is not None, "clubcore_client_csrf cookie missing from verify response"
    access = access_cookie.split("=", 1)[1].split(";", 1)[0]
    csrf = csrf_cookie.split("=", 1)[1].split(";", 1)[0]
    return access, csrf


# ---------------------------------------------------------------------------
# 1 + 2: onboarding PATCH accepted (NOT 422) and GET exposes onboarding fields
# ---------------------------------------------------------------------------


async def test_patch_me_onboarding_body_accepted_through_route_table(
    async_client: AsyncClient,
    db_session: AsyncSession,
    client_a: Client,
    redis_clean: object,
) -> None:
    """PATCH /me with the full onboarding body → 200 (regression: used to 422).

    This is the exact body the PWA onboarding "finish" step sends. If a client_auth
    /me route ever shadows the client_portal handler again, ClientMePatchRequest
    (extra='forbid', email-only) would reject these fields with 422 — which is
    precisely the bug this test guards against.
    """
    _ = redis_clean
    access, csrf = await _auth_as_client_with_csrf(async_client, db_session, client_a)

    resp = await async_client.patch(
        "/api/v1/client/me",
        json={
            "firstName": "Андрей",
            "goal": "lose_weight",
            "heightCm": 180,
            "weightKg": 75,
            "onboardingCompleted": True,
        },
        headers={
            "Cookie": f"cc_client_access={access}; clubcore_client_csrf={csrf}",
            "x-csrf-token": csrf,
        },
    )
    assert resp.status_code == 200, (
        f"Onboarding PATCH /me should be accepted (200), got {resp.status_code}: {resp.text}\n"
        "A 422 'Extra inputs are not permitted' means the client_auth /me route is "
        "shadowing the Phase 999.5 client_portal handler again (route-collision regression)."
    )

    data = resp.json()["data"]
    assert data["firstName"] == "Андрей", data
    assert data["goal"] == "lose_weight", data
    assert data["heightCm"] == 180, data
    assert data["weightKg"] == 75, data
    assert data["onboardingCompletedAt"] is not None, (
        f"onboardingCompleted=True must stamp onboardingCompletedAt server-side (D-05): {data}"
    )


async def test_get_me_exposes_onboarding_fields_through_route_table(
    async_client: AsyncClient,
    db_session: AsyncSession,
    client_a: Client,
    redis_clean: object,
) -> None:
    """GET /me exposes the Phase 999.5 onboarding fields in camelCase.

    Regression: when client_auth's GET /me shadowed this handler, the response
    lacked goal/heightCm/weightKg/onboardingCompletedAt, which permanently pinned
    the PWA HomeScreen onboarding-redirect gate (!me.onboardingCompletedAt) to true.
    """
    _ = redis_clean
    access, csrf = await _auth_as_client_with_csrf(async_client, db_session, client_a)

    # Seed onboarding values via PATCH first so GET has something to surface.
    await async_client.patch(
        "/api/v1/client/me",
        json={"goal": "tone", "heightCm": 170, "weightKg": 60, "onboardingCompleted": True},
        headers={
            "Cookie": f"cc_client_access={access}; clubcore_client_csrf={csrf}",
            "x-csrf-token": csrf,
        },
    )

    resp = await async_client.get(
        "/api/v1/client/me",
        headers={"Cookie": f"cc_client_access={access}"},
    )
    assert resp.status_code == 200, f"GET /me expected 200, got {resp.status_code}: {resp.text}"

    data = resp.json()["data"]
    # The 999.5 contract fields MUST be present (camelCase wire).
    for field in ("goal", "heightCm", "weightKg", "onboardingCompletedAt"):
        assert field in data, (
            f"GET /me missing '{field}' — client_portal handler not live "
            f"(route shadowing regression): {data}"
        )
    assert data["goal"] == "tone", data
    assert data["heightCm"] == 170, data
    assert data["weightKg"] == 60, data
    assert data["onboardingCompletedAt"] is not None, data
    # id is part of the consolidated contract (preserves the former client_auth PATCH /me
    # email round-trip caller that reads data.id).
    assert data["id"] == str(client_a.id), data


# ---------------------------------------------------------------------------
# 3: receipt-email gate path still works (the path client_auth used to serve)
# ---------------------------------------------------------------------------


async def test_patch_me_email_round_trip_through_route_table(
    async_client: AsyncClient,
    db_session: AsyncSession,
    client_a: Client,
    redis_clean: object,
) -> None:
    """PATCH /me {email} → 200 and the email round-trips via GET /me.

    This is the receipt-email gate path (54-ФЗ; checkout sends PATCH /me {email}).
    It MUST keep working after consolidating /me onto client_portal — that was a
    hard constraint of the fix.
    """
    _ = redis_clean
    access, csrf = await _auth_as_client_with_csrf(async_client, db_session, client_a)

    new_email = f"receipt-{uuid4().hex[:8]}@example.com"
    patch_resp = await async_client.patch(
        "/api/v1/client/me",
        json={"email": new_email},
        headers={
            "Cookie": f"cc_client_access={access}; clubcore_client_csrf={csrf}",
            "x-csrf-token": csrf,
        },
    )
    assert patch_resp.status_code == 200, (
        f"PATCH /me {{email}} should be 200, got {patch_resp.status_code}: {patch_resp.text}"
    )
    assert patch_resp.json()["data"]["email"] == new_email, patch_resp.json()

    get_resp = await async_client.get(
        "/api/v1/client/me",
        headers={"Cookie": f"cc_client_access={access}"},
    )
    assert get_resp.status_code == 200, get_resp.text
    assert get_resp.json()["data"]["email"] == new_email, (
        "Email did not round-trip via GET /me after PATCH"
    )
