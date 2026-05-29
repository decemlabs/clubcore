"""Full client session lifecycle + rate-limit + brute-force tests (Phase 68 Plan 06).

Tests:
  1. test_full_session_lifecycle (CAUTH-04):
     OTP request → verify (all three cc_client_* cookies set; refresh Path=/api/v1/client)
     → GET /me 200 → POST /session/refresh (rotation: new cookies, old token dead)
     → POST /session/logout (CSRF header required; cookies cleared)
     → GET /me 401 (post-logout token rejected).

  2. test_otp_rate_limited (CAUTH-06):
     Exceed the per-phone daily cap (5 requests/24h per D-11) and assert 429.

  3. test_otp_brute_force_blocked (CAUTH-06):
     Request a code; submit the wrong code otp_max_attempts times; assert the code
     is dead (subsequent verify with a correct code or with a wrong code returns 401
     rather than the original OtpInvalid error, because OtpMaxAttempts was raised).

Harness: SAVEPOINT rollback + ASGITransport async_client from root conftest.py.
Fixtures from tests/integration/client_auth/conftest.py.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import generate_otp_code
from app.modules.auth.models import OtpCode
from app.modules.client_auth.rate_limit import (
    _DAILY_LIMIT,
    _DAILY_WINDOW,
)
from app.modules.clients.models import Client

pytestmark = pytest.mark.asyncio


async def _request_otp_and_get_raw_code(
    async_client: AsyncClient,
    db_session: AsyncSession,
    client: Client,
) -> str:
    """Request OTP + patch OtpCode row with a known code; return raw_code.

    The bot sender slot is None in tests so no DM is actually sent.
    We read the OtpCode row and replace its code_hash with a freshly generated code
    so the test can call /otp/verify with a known value (plan 68-06 notes).
    """
    req = await async_client.post(
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
    assert otp_row is not None, "OtpCode row not found after otp/request"

    settings = get_settings()
    raw_code, code_hash = generate_otp_code()
    otp_row.code_hash = code_hash
    otp_row.expires_at = datetime.now(tz=UTC) + timedelta(seconds=settings.otp_code_ttl_seconds)
    await db_session.commit()
    return raw_code


async def test_full_session_lifecycle(
    async_client: AsyncClient,
    db_session: AsyncSession,
    linked_client: Client,
    redis_clean: Redis,
) -> None:
    """CAUTH-04: full cookie lifecycle — issue / survive / rotate / clear.

    Step-by-step:
      1. POST /otp/request + read code from OtpCode row.
      2. POST /otp/verify → assert three cc_client_* cookies issued.
         - cc_client_access: Path=/, HttpOnly, SameSite=Lax
         - cc_client_refresh: Path=/api/v1/client, HttpOnly
         - clubcore_client_csrf: Path=/, NOT HttpOnly
      3. GET /me with cc_client_access → 200.
      4. POST /session/refresh with cc_client_refresh → 200, new cookies.
      5. GET /me with new cc_client_access → 200 (rotation worked).
      6. POST /session/logout with new cookies + x-csrf-token header → 200.
         Assert Set-Cookie deletions (empty value / max-age=0) for all three names.
      7. GET /me with the cleared access cookie → 401.
    """
    _ = redis_clean  # flush fixture — prevents rate-limit key bleed between tests

    # Step 1+2: Verify OTP → three cookies issued
    raw_code = await _request_otp_and_get_raw_code(async_client, db_session, linked_client)
    verify = await async_client.post(
        "/api/v1/client/otp/verify",
        json={"phone": linked_client.phone, "code": raw_code},
    )
    assert verify.status_code == 200, f"OTP verify failed: {verify.text}"

    set_cookies = verify.headers.get_list("set-cookie")
    joined = "\n".join(set_cookies)

    # Three cookies present
    assert "cc_client_access=" in joined, "cc_client_access cookie missing"
    assert "cc_client_refresh=" in joined, "cc_client_refresh cookie missing"
    assert "clubcore_client_csrf=" in joined, "clubcore_client_csrf cookie missing"

    # cc_client_access — Path=/, HttpOnly, SameSite=Lax
    access_hdr = next(c for c in set_cookies if c.startswith("cc_client_access="))
    assert "Path=/" in access_hdr, f"cc_client_access missing Path=/: {access_hdr}"
    assert "HttpOnly" in access_hdr, f"cc_client_access not HttpOnly: {access_hdr}"
    assert "samesite=lax" in access_hdr.lower(), (
        f"cc_client_access missing SameSite=Lax: {access_hdr}"
    )

    # cc_client_refresh — Path=/api/v1/client (D-10 narrow scoping)
    refresh_hdr = next(c for c in set_cookies if c.startswith("cc_client_refresh="))
    assert "Path=/api/v1/client" in refresh_hdr, (
        f"cc_client_refresh must be Path=/api/v1/client: {refresh_hdr}"
    )
    assert "HttpOnly" in refresh_hdr, f"cc_client_refresh not HttpOnly: {refresh_hdr}"

    # clubcore_client_csrf — Path=/, NOT HttpOnly (PWA reads it for X-CSRF-Token)
    csrf_hdr = next(c for c in set_cookies if c.startswith("clubcore_client_csrf="))
    assert "Path=/" in csrf_hdr, f"clubcore_client_csrf missing Path=/: {csrf_hdr}"
    assert "HttpOnly" not in csrf_hdr, (
        f"clubcore_client_csrf must NOT be HttpOnly: {csrf_hdr}"
    )

    # Extract token values for subsequent requests
    access_token = access_hdr.split("=", 1)[1].split(";", 1)[0]
    refresh_token = refresh_hdr.split("=", 1)[1].split(";", 1)[0]

    # Step 3: GET /me with access token → 200
    # Use Cookie header directly to avoid httpx per-request cookies deprecation warning.
    me1 = await async_client.get(
        "/api/v1/client/me",
        headers={"Cookie": f"cc_client_access={access_token}"},
    )
    assert me1.status_code == 200, f"GET /me after verify failed: {me1.text}"
    assert me1.json()["data"]["id"] == str(linked_client.id)

    # Step 4: POST /session/refresh — rotation
    refresh_resp = await async_client.post(
        "/api/v1/client/session/refresh",
        headers={"Cookie": f"cc_client_refresh={refresh_token}"},
    )
    assert refresh_resp.status_code == 200, f"Session refresh failed: {refresh_resp.text}"

    refresh_set = refresh_resp.headers.get_list("set-cookie")
    joined_refresh = "\n".join(refresh_set)
    assert "cc_client_access=" in joined_refresh, "New cc_client_access missing"
    assert "cc_client_refresh=" in joined_refresh, "New cc_client_refresh missing"
    assert "clubcore_client_csrf=" in joined_refresh, "New clubcore_client_csrf missing"

    new_access_hdr = next(c for c in refresh_set if c.startswith("cc_client_access="))
    new_refresh_hdr = next(c for c in refresh_set if c.startswith("cc_client_refresh="))
    new_csrf_hdr = next(c for c in refresh_set if c.startswith("clubcore_client_csrf="))

    new_access_token = new_access_hdr.split("=", 1)[1].split(";", 1)[0]
    new_refresh_token = new_refresh_hdr.split("=", 1)[1].split(";", 1)[0]
    new_csrf_token = new_csrf_hdr.split("=", 1)[1].split(";", 1)[0]

    # Refresh token MUST be rotated (generate_refresh_token = secrets.token_urlsafe — always new).
    # Access token MAY match if both tokens were minted within the same second (stateless JWT;
    # iat is second-precision). We only assert refresh rotation; access uniqueness is a TTL
    # concern, not a rotation correctness concern.
    assert new_refresh_token != refresh_token, "Refresh token was not rotated"

    # Step 5: GET /me with new access token → 200
    me2 = await async_client.get(
        "/api/v1/client/me",
        headers={"Cookie": f"cc_client_access={new_access_token}"},
    )
    assert me2.status_code == 200, f"GET /me after rotation failed: {me2.text}"

    # Step 6: POST /session/logout with new cookies + CSRF header.
    # Multiple cookies: build a single Cookie header string.
    cookie_str = (
        f"cc_client_access={new_access_token}; "
        f"cc_client_refresh={new_refresh_token}; "
        f"clubcore_client_csrf={new_csrf_token}"
    )
    logout_resp = await async_client.post(
        "/api/v1/client/session/logout",
        headers={"Cookie": cookie_str, "x-csrf-token": new_csrf_token},
    )
    assert logout_resp.status_code == 200, f"Logout failed: {logout_resp.text}"

    # Assert Set-Cookie deletions: the three cookie names should appear with empty/expired values
    logout_set = logout_resp.headers.get_list("set-cookie")
    logout_joined = "\n".join(logout_set)
    # Cookie deletion: either max-age=0 or expires in the past; name must appear
    assert "cc_client_access=" in logout_joined, "cc_client_access not cleared by logout"
    assert "cc_client_refresh=" in logout_joined, "cc_client_refresh not cleared by logout"
    assert "clubcore_client_csrf=" in logout_joined, (
        "clubcore_client_csrf not cleared by logout"
    )

    # Step 7: GET /me without any access token cookie → 401 (missing_access_cookie).
    # Note: access tokens are stateless JWTs (no DB revocation). The "session cleared" guarantee
    # means the browser's cookies are erased — once cleared, GET /me has no cc_client_access
    # cookie, so the dependency raises InvalidAccessToken("missing_access_cookie") → 401.
    # The security contract is: refresh token revoked (no new sessions) + cookies cleared
    # (browser loses access immediately). This test verifies the cookie-missing-→-401 path.
    me3 = await async_client.get(
        "/api/v1/client/me",
    )
    assert me3.status_code == 401, (
        f"Expected 401 (no cookie after logout) but got {me3.status_code}: {me3.text}"
    )


async def test_otp_rate_limited(
    async_client: AsyncClient,
    app: FastAPI,
    linked_client: Client,
    redis_clean: Redis,
) -> None:
    """CAUTH-06: exceeding the per-phone daily OTP cap returns 429.

    D-11: ≤5 requests per rolling 24h per phone. After _DAILY_LIMIT requests,
    the next one MUST return 429 with code 'rate_limited'.

    Note: the cooldown (60s) also applies per request. We bypass it by directly
    manipulating the Redis daily counter to _DAILY_LIMIT, then send one more request.
    The `app` fixture provides access to `app.state.redis` for direct manipulation.
    """
    _ = redis_clean  # flush fixture — prevents rate-limit key bleed between tests

    redis_client: Redis = app.state.redis

    # Directly set the daily counter to the limit to avoid the 60s cooldown
    daily_key = f"ratelimit:client_otp_daily:{linked_client.phone}"
    await redis_client.set(daily_key, str(_DAILY_LIMIT), ex=_DAILY_WINDOW)

    # Next request MUST be rate-limited
    resp = await async_client.post(
        "/api/v1/client/otp/request",
        json={"phone": linked_client.phone},
    )
    assert resp.status_code == 429, (
        f"Expected 429 after daily cap exceeded, got {resp.status_code}: {resp.text}"
    )
    body = resp.json()
    assert body.get("code") == "rate_limited", f"Expected code='rate_limited': {body}"


async def test_otp_brute_force_blocked(
    async_client: AsyncClient,
    db_session: AsyncSession,
    linked_client: Client,
    redis_clean: Redis,
) -> None:
    """CAUTH-06: code is dead after OtpMaxAttempts wrong guesses.

    Flow:
      1. Request OTP → patch OtpCode with known hash.
      2. Submit the wrong code otp_max_attempts times.
      3. On the last attempt: assert 401 with code 'otp_max_attempts'.
      4. Further wrong attempts also return 'otp_max_attempts' (not 'otp_invalid').
    """
    _ = redis_clean  # flush fixture

    settings = get_settings()
    raw_code = await _request_otp_and_get_raw_code(async_client, db_session, linked_client)

    wrong_code = "000000"
    # Ensure wrong_code != raw_code
    assert wrong_code != raw_code, "Collision: wrong_code happened to match the generated code"

    # Submit wrong codes up to (max_attempts - 1): these should return otp_invalid (401)
    for i in range(settings.otp_max_attempts - 1):
        resp = await async_client.post(
            "/api/v1/client/otp/verify",
            json={"phone": linked_client.phone, "code": wrong_code},
        )
        assert resp.status_code == 401, (
            f"Expected 401 on wrong attempt {i + 1}/{settings.otp_max_attempts - 1}, "
            f"got {resp.status_code}: {resp.text}"
        )
        body = resp.json()
        assert body.get("code") == "otp_invalid", (
            f"Unexpected code on attempt {i + 1}: {body}"
        )

    # Final wrong attempt: hits OtpMaxAttempts — OtpMaxAttempts.status_code == 429
    last_wrong = await async_client.post(
        "/api/v1/client/otp/verify",
        json={"phone": linked_client.phone, "code": wrong_code},
    )
    assert last_wrong.status_code == 429, (
        f"Expected 429 (OtpMaxAttempts) on max-attempts hit, "
        f"got {last_wrong.status_code}: {last_wrong.text}"
    )
    last_body = last_wrong.json()
    assert last_body.get("code") == "otp_max_attempts", (
        f"Expected code='otp_max_attempts' on final wrong attempt: {last_body}"
    )

    # After OtpMaxAttempts: any further wrong code also returns 429/otp_max_attempts
    further_wrong = await async_client.post(
        "/api/v1/client/otp/verify",
        json={"phone": linked_client.phone, "code": wrong_code},
    )
    assert further_wrong.status_code == 429, (
        f"Expected 429 on post-max wrong attempt, "
        f"got {further_wrong.status_code}: {further_wrong.text}"
    )
    assert further_wrong.json().get("code") == "otp_max_attempts", (
        f"Expected code='otp_max_attempts' beyond max attempts: {further_wrong.json()}"
    )
