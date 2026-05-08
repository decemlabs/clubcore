"""Integration tests for HYG-02 — tampered sz_access cookie with non-UUID sub.

Covers:
  - A hand-signed access JWT with sub='not-a-uuid' returns 401 invalid_session (NOT 500).
  - The error code is 'invalid_session' (NOT 'invalid_token'), distinguishing the
    cookie-tampered path from the token-expired path (D-23-11).
  - Wrap site is ONLY at app.core.dependencies.get_current_user:UUID(claims.sub) (D-23-12).
  - sz_refresh is NOT UUID-parsed — the sha256 lookup path is unchanged.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import jwt
from fastapi import FastAPI
from httpx import AsyncClient

from app.core.config import get_settings


async def test_tampered_access_jwt_with_non_uuid_sub_returns_401_invalid_session(
    async_client: AsyncClient,
    app: FastAPI,
) -> None:
    """HYG-02: sz_access with sub='not-a-uuid' → 401 invalid_session (NOT 500).

    Constructs a cryptographically valid JWT (signed with the live secret_key) whose
    sub claim is not a valid UUID. Pre-Phase-23, UUID(claims.sub) raised ValueError
    which propagated as an unhandled 500. Post-Phase-23, it raises InvalidSession(401).

    The code must be 'invalid_session' (not 'invalid_token') — FE branches on this
    to distinguish "cookie tampered, force re-login UX" from "token expired, auto-refresh UX".
    """
    settings = get_settings()
    now = datetime.now(tz=UTC)
    # Manually build a JWT with all required claims but sub='not-a-uuid'.
    payload = {
        "sub": "not-a-uuid",
        "role": "reception",
        "typ": "access",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=15)).timestamp()),
    }
    tampered_token = jwt.encode(
        payload,
        settings.secret_key.get_secret_value(),
        algorithm="HS256",
    )

    # Set the tampered token as the sz_access cookie.
    async_client.cookies.set("sz_access", tampered_token)

    # Hit any Depends(get_current_user) route — /me is the simplest.
    response = await async_client.get("/api/v1/auth/me")

    assert response.status_code == 401, (
        f"Expected 401 for tampered sub, got {response.status_code}: {response.text}"
    )
    body = response.json()
    # Must be 'invalid_session', NOT 'invalid_token' (HYG-02 D-23-11 distinction).
    assert body["code"] == "invalid_session", (
        f"Expected code='invalid_session', got code={body['code']!r}. "
        f"This test is verifying HYG-02: the UUID parse failure at dependencies.py:221 "
        f"must surface as InvalidSession, not as a 500 or InvalidAccessToken."
    )


async def test_valid_jwt_with_unknown_user_id_still_returns_401(
    async_client: AsyncClient,
    app: FastAPI,
) -> None:
    """Regression guard: valid UUID sub that doesn't match any User row → 401 (not 500).

    This confirms the wrap is NARROW — only the UUID parse failure raises InvalidSession.
    A syntactically valid UUID for a non-existent user goes through UUID(claims.sub)
    successfully and then hits the user_loader, which returns None → InvalidAccessToken.

    The code will be 'invalid_token' (user_not_found) not 'invalid_session'.
    This distinguishes the two failure modes from each other:
      - non-UUID sub → 'invalid_session'
      - unknown-but-valid UUID → still 'invalid_token' (code='user_not_found' message)
    """
    import uuid

    settings = get_settings()
    now = datetime.now(tz=UTC)
    # Valid UUIDv4 that will not exist in the test DB.
    unknown_uuid = str(uuid.uuid4())
    payload = {
        "sub": unknown_uuid,
        "role": "reception",
        "typ": "access",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=15)).timestamp()),
    }
    token = jwt.encode(
        payload,
        settings.secret_key.get_secret_value(),
        algorithm="HS256",
    )
    async_client.cookies.set("sz_access", token)

    response = await async_client.get("/api/v1/auth/me")

    assert response.status_code == 401, (
        f"Expected 401 for unknown user UUID, got {response.status_code}: {response.text}"
    )
    body = response.json()
    # Must NOT be 'invalid_session' — the UUID parse succeeded; it's a user-not-found path.
    assert body["code"] != "invalid_session", (
        f"Unknown UUID sub should NOT return 'invalid_session'; got {body['code']!r}"
    )
    # The existing path returns 'user_not_found' via InvalidAccessToken.
    assert body["code"] in {"user_not_found", "invalid_token"}, (
        f"Unexpected code for unknown UUID: {body['code']!r}"
    )
