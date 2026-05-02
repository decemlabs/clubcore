"""Unit tests for app.core.security — JWT, Argon2, token generators, cookie matrix (D-29)."""

from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
import pytest
from fastapi import Response

from app.core.exceptions import InvalidAccessToken, InvalidPassword
from app.core.permissions import Role
from app.core.security import (
    AccessTokenClaims,
    decode_access_token,
    encode_access_token,
    generate_csrf_token,
    generate_deep_link_token,
    generate_otp_code,
    generate_refresh_token,
    hash_password,
    issue_session_cookies,
    password_needs_rehash,
    verify_password,
)

# ---- JWT (AUTH-01) ----


def test_jwt_encode_decode_round_trip() -> None:
    uid = uuid4()
    token = encode_access_token(uid, Role.OWNER)
    claims = decode_access_token(token)
    assert isinstance(claims, AccessTokenClaims)
    assert claims.sub == str(uid)
    assert claims.role is Role.OWNER
    assert claims.typ == "access"
    assert claims.exp - claims.iat == 900  # 15-min access TTL


def test_jwt_decode_rejects_garbage() -> None:
    with pytest.raises(InvalidAccessToken) as exc_info:
        decode_access_token("not.a.jwt")
    assert exc_info.value.message == "invalid_token"


def test_jwt_decode_rejects_foreign_secret() -> None:
    # Key must be >= 32 bytes to avoid InsecureKeyLengthWarning (treated as error by pytest)
    bad = jwt.encode(
        {
            "sub": "x",
            "role": "owner",
            "typ": "access",
            "iat": int(time.time()),
            "exp": int(time.time()) + 60,
        },
        "wrong-secret-key-that-is-32-bytes!!",
        algorithm="HS256",
    )
    with pytest.raises(InvalidAccessToken) as exc_info:
        decode_access_token(bad)
    assert exc_info.value.message == "invalid_token"


def test_jwt_decode_rejects_expired_token() -> None:
    # Mint a token whose exp is in the past, beyond the 30s leeway window.
    past = datetime.now(tz=UTC) - timedelta(seconds=3600)
    token = encode_access_token(uuid4(), Role.OWNER, now=past)
    with pytest.raises(InvalidAccessToken) as exc_info:
        decode_access_token(token)
    assert exc_info.value.message == "token_expired"


def test_jwt_decode_rejects_wrong_typ() -> None:
    # Manually mint a token with typ != "access" using the real secret.
    from app.core.config import get_settings

    secret = get_settings().secret_key.get_secret_value()
    token = jwt.encode(
        {
            "sub": str(uuid4()),
            "role": "owner",
            "typ": "refresh",
            "iat": int(time.time()),
            "exp": int(time.time()) + 60,
        },
        secret,
        algorithm="HS256",
    )
    with pytest.raises(InvalidAccessToken) as exc_info:
        decode_access_token(token)
    assert exc_info.value.message == "wrong_token_type"


def test_jwt_decode_rejects_unknown_role() -> None:
    from app.core.config import get_settings

    secret = get_settings().secret_key.get_secret_value()
    token = jwt.encode(
        {
            "sub": str(uuid4()),
            "role": "superadmin",
            "typ": "access",
            "iat": int(time.time()),
            "exp": int(time.time()) + 60,
        },
        secret,
        algorithm="HS256",
    )
    with pytest.raises(InvalidAccessToken) as exc_info:
        decode_access_token(token)
    assert exc_info.value.message == "unknown_role"


# ---- Argon2 (AUTH-02) ----


async def test_argon2_hash_starts_with_argon2id_prefix() -> None:
    h = await hash_password("correct horse battery staple")
    assert h.startswith("$argon2id$")


async def test_argon2_verify_round_trip() -> None:
    h = await hash_password("correct horse battery staple")
    assert await verify_password("correct horse battery staple", h) is True


async def test_argon2_verify_wrong_password_raises() -> None:
    h = await hash_password("right")
    with pytest.raises(InvalidPassword) as exc_info:
        await verify_password("wrong", h)
    assert exc_info.value.message == "invalid_credentials"


async def test_argon2_password_needs_rehash_false_for_default_params() -> None:
    h = await hash_password("any")
    assert await password_needs_rehash(h) is False


# ---- Token generators (AUTH-03, CSRF-01) ----


def test_generate_refresh_token_returns_43_char_raw_and_64_char_sha256() -> None:
    raw, sh = generate_refresh_token()
    assert len(raw) == 43
    assert len(sh) == 64
    assert all(c in "0123456789abcdef" for c in sh)


def test_generate_otp_code_returns_6_digit_code_and_64_char_sha256() -> None:
    code, sh = generate_otp_code()
    assert len(code) == 6
    assert code.isdigit()
    assert len(sh) == 64


def test_generate_deep_link_token_is_43_chars_url_safe() -> None:
    tok = generate_deep_link_token()
    assert len(tok) == 43
    assert all(c.isalnum() or c in "-_" for c in tok)


def test_generate_csrf_token_is_64_char_hex() -> None:
    tok = generate_csrf_token()
    assert len(tok) == 64
    assert all(c in "0123456789abcdef" for c in tok)


def test_generators_produce_distinct_outputs_per_call() -> None:
    # Smoke: secrets.* should never produce the same value twice in succession.
    assert generate_csrf_token() != generate_csrf_token()
    assert generate_deep_link_token() != generate_deep_link_token()


# ---- Cookie matrix (AUTH-04, CSRF-01) ----


def test_issue_session_cookies_sets_three_cookies_with_locked_attributes() -> None:
    r = Response()
    issue_session_cookies(
        r,
        access_token="A",  # noqa: S106
        refresh_token="R",  # noqa: S106
        csrf_token="C",  # noqa: S106
        secure=False,
    )
    headers = r.headers.getlist("set-cookie")
    assert len(headers) == 3, headers

    sz_access = next(h for h in headers if h.startswith("sz_access="))
    sz_refresh = next(h for h in headers if h.startswith("sz_refresh="))
    csrf = next(h for h in headers if h.startswith("sportzal_csrf="))

    # sz_access: Path=/, Max-Age=900, HttpOnly, SameSite=lax
    assert "Path=/" in sz_access and "Path=/api" not in sz_access
    assert "HttpOnly" in sz_access
    assert "samesite=lax" in sz_access.lower()
    assert "Max-Age=900" in sz_access

    # sz_refresh: Path=/api/v1/auth, Max-Age=2592000, HttpOnly, SameSite=lax
    assert "Path=/api/v1/auth" in sz_refresh
    assert "HttpOnly" in sz_refresh
    assert "Max-Age=2592000" in sz_refresh

    # sportzal_csrf: Path=/, NOT HttpOnly, SameSite=lax
    assert "Path=/" in csrf
    assert "HttpOnly" not in csrf  # MUST be readable by frontend JS

    # secure=False → none of the three carry "Secure"
    assert "Secure" not in sz_access
    assert "Secure" not in sz_refresh
    assert "Secure" not in csrf


def test_issue_session_cookies_secure_true_emits_secure_attribute() -> None:
    r = Response()
    issue_session_cookies(
        r,
        access_token="A",  # noqa: S106
        refresh_token="R",  # noqa: S106
        csrf_token="C",  # noqa: S106
        secure=True,
    )
    for h in r.headers.getlist("set-cookie"):
        assert "Secure" in h, h
