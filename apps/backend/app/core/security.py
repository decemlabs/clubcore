"""Security primitives: JWT, Argon2id, token generators, cookie matrix (D-01..D-06, D-25..D-28).

Phase 4 ships pure cryptographic + cookie infrastructure. NO endpoints, NO DB calls, NO
auth flow logic — those land in Phase 5+. Every function here is consumed by Phase 5/7/8
services and dependencies.

Imports are layered stdlib → third-party → app-local per project convention.
"""

import asyncio
import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from fastapi import Response

from app.core.config import get_settings
from app.core.exceptions import InvalidAccessToken, InvalidPassword
from app.core.permissions import Role

# =========================================================================
# JWT (AUTH-01, D-01..D-06)
# =========================================================================


@dataclass(frozen=True, slots=True)
class AccessTokenClaims:
    """Decoded access-token claims (D-02).

    Phase 4 omits jti / iss / aud (D-02 — additive in future without breaking decode).
    """

    sub: str  # str(user_uuid)
    role: Role  # StrEnum value
    typ: str  # always "access" for tokens minted here
    iat: int  # UTC epoch seconds
    exp: int  # UTC epoch seconds


def encode_access_token(
    user_id: UUID,
    role: Role,
    *,
    now: datetime | None = None,
) -> str:
    """Mint a short-lived access JWT (HS256, settings.access_token_ttl_seconds = 900s).

    `now` is injectable for unit tests; production callers pass nothing.
    """
    settings = get_settings()
    issued = now or datetime.now(tz=UTC)
    expires = issued + timedelta(seconds=settings.access_token_ttl_seconds)
    payload = {
        "sub": str(user_id),
        "role": role.value,
        "typ": "access",
        "iat": int(issued.timestamp()),
        "exp": int(expires.timestamp()),
    }
    return jwt.encode(
        payload,
        settings.secret_key.get_secret_value(),
        algorithm="HS256",
    )


def decode_access_token(token: str) -> AccessTokenClaims:
    """Decode + validate an access JWT.

    Raises InvalidAccessToken (401) on:
      - expired signature → message "token_expired"
      - any other PyJWT failure (bad signature, malformed, missing claim) → "invalid_token"
      - wrong `typ` claim (e.g. a refresh token mistakenly handed in) → "wrong_token_type"
      - unknown role string (StrEnum coercion failure) → "unknown_role"
    """
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.secret_key.get_secret_value(),
            algorithms=["HS256"],
            leeway=settings.jwt_clock_leeway_seconds,
            options={"require": ["sub", "role", "typ", "iat", "exp"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise InvalidAccessToken("token_expired") from exc
    except jwt.InvalidTokenError as exc:
        # Parent class — covers DecodeError, MissingRequiredClaimError,
        # InvalidSignatureError, InvalidAlgorithmError, etc.
        raise InvalidAccessToken("invalid_token") from exc

    if payload.get("typ") != "access":
        raise InvalidAccessToken("wrong_token_type")
    try:
        role = Role(payload["role"])
    except ValueError as exc:
        raise InvalidAccessToken("unknown_role") from exc

    return AccessTokenClaims(
        sub=payload["sub"],
        role=role,
        typ=payload["typ"],
        iat=payload["iat"],
        exp=payload["exp"],
    )


# =========================================================================
# Argon2id (AUTH-02, D-27, D-28)
# =========================================================================

# Module-level hasher; library defaults align with OWASP 2026 (D-27):
# memory_cost=65536 KiB, time_cost=3, parallelism=4, hash_len=32, salt_len=16.
_ph = PasswordHasher()


async def hash_password(plain: str) -> str:
    """Return an Argon2id encoded hash. Wrapped in asyncio.to_thread (~50ms blocks loop)."""
    return await asyncio.to_thread(_ph.hash, plain)


async def verify_password(plain: str, encoded_hash: str) -> bool:
    """Return True on match. Raise InvalidPassword on mismatch / malformed hash.

    Phase 5 AUTH-EP-02 timing equivalence: callers always run verify_password (with a
    sentinel hash for user-not-found) so this exception fires regardless of whether the
    email exists. That sentinel-hash strategy lives in the Phase 5 login service, not here.
    """

    def _do() -> bool:
        try:
            _ph.verify(encoded_hash, plain)
            return True
        except VerifyMismatchError as exc:
            raise InvalidPassword("invalid_credentials") from exc
        except InvalidHashError as exc:
            # Stored hash malformed (data corruption / wrong column) — surface as auth fail
            raise InvalidPassword("invalid_credentials") from exc

    return await asyncio.to_thread(_do)


async def password_needs_rehash(encoded_hash: str) -> bool:
    """True iff the stored hash uses weaker params than current PasswordHasher defaults.

    Phase 5 login flow checks this after a successful verify and rehashes transparently
    when params bump. Phase 4 ships the helper; the rehash workflow lives in Phase 5.
    """
    return await asyncio.to_thread(_ph.check_needs_rehash, encoded_hash)


# =========================================================================
# Token generators (AUTH-03, CSRF-01, D-26)
# =========================================================================


def _sha256_hex(value: str) -> str:
    """Return the hex digest of SHA-256(value). 64 chars."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def generate_refresh_token() -> tuple[str, str]:
    """Return (raw_token, sha256_hex). Phase 5 stores ONLY the hash in DB.

    Raw is 43 base64url chars (32 bytes of entropy via secrets.token_urlsafe(32)).
    """
    raw = secrets.token_urlsafe(32)
    return raw, _sha256_hex(raw)


def generate_otp_code() -> tuple[str, str]:
    """Return (raw_6_digit_code, sha256_hex). Phase 7 sends raw to Telegram, stores hash.

    Uniform integer 0..999999 via secrets.randbelow(); zero-padded to 6 digits.
    """
    code = f"{secrets.randbelow(1_000_000):06d}"
    return code, _sha256_hex(code)


def generate_deep_link_token() -> str:
    """Return URL-safe 43-char token for Telegram /start <token> deep links (Phase 7)."""
    return secrets.token_urlsafe(32)


def generate_csrf_token() -> str:
    """Return 64-char hex (32 bytes) for the clubcore_csrf cookie (CSRF-01, D-26).

    Phase 5/7 regenerate on each successful login/refresh/OTP-verify so old values
    invalidate. Phase 6 verify_csrf dependency reads X-CSRF-Token header and compares.
    """
    return secrets.token_hex(32)


# =========================================================================
# Cookie matrix (AUTH-04, CSRF-01, D-25)
# =========================================================================


def issue_session_cookies(
    response: Response,
    *,
    access_token: str,
    refresh_token: str,
    csrf_token: str,
    secure: bool,
) -> None:
    """Set cc_access + cc_refresh + clubcore_csrf cookies with the locked attributes.

    Single function, not three setters — drift across emission sites (Phase 5 login vs
    refresh vs Phase 7 OTP-verify) is the real risk being mitigated (D-25).

    `secure` is env-driven via settings.cookie_secure; prod startup ASSERTS True
    (assertion lands in Phase 5 create_app per CONTEXT.md D-25).
    """
    settings = get_settings()

    # cc_access — covers all API paths
    response.set_cookie(
        key="cc_access",
        value=access_token,
        max_age=settings.access_token_ttl_seconds,
        path="/",
        httponly=True,
        secure=secure,
        samesite="lax",
    )

    # cc_refresh — narrow path; only sent to /api/v1/auth/* (smaller exposure)
    response.set_cookie(
        key="cc_refresh",
        value=refresh_token,
        max_age=settings.refresh_token_ttl_seconds,
        path="/api/v1/auth",
        httponly=True,
        secure=secure,
        samesite="lax",
    )

    # clubcore_csrf — non-httpOnly so frontend reads it for X-CSRF-Token header
    # (double-submit pattern). Verifier dependency lands in Phase 6 (CSRF-02).
    response.set_cookie(
        key="clubcore_csrf",
        value=csrf_token,
        max_age=settings.refresh_token_ttl_seconds,
        path="/",
        httponly=False,
        secure=secure,
        samesite="lax",
    )


def clear_session_cookies(response: Response, *, secure: bool) -> None:
    """Clear cc_access + cc_refresh + clubcore_csrf, mirroring issue_session_cookies (D-17).

    Browsers only delete a cookie when the deletion request matches the original
    Path / SameSite / Secure / HttpOnly tuple. Mismatched attributes produce a
    silent no-op delete that leaves stale cookies in the jar. This helper mirrors
    `issue_session_cookies` exactly so callers cannot drift across logout sites
    (Phase 5 /auth/logout, future Phase 5/7 admin password-change).

    `secure` MUST be passed from `settings.cookie_secure` for symmetry with the
    issuer (prod startup asserts `cookie_secure is True` per D-25).
    """
    # cc_access — Path=/ (matches issuer)
    response.delete_cookie(
        key="cc_access",
        path="/",
        httponly=True,
        secure=secure,
        samesite="lax",
    )
    # cc_refresh — Path=/api/v1/auth (matches issuer; browsers will not delete on Path=/)
    response.delete_cookie(
        key="cc_refresh",
        path="/api/v1/auth",
        httponly=True,
        secure=secure,
        samesite="lax",
    )
    # clubcore_csrf — Path=/, NOT httpOnly (matches issuer)
    response.delete_cookie(
        key="clubcore_csrf",
        path="/",
        httponly=False,
        secure=secure,
        samesite="lax",
    )


# =========================================================================
# Client JWT (D-07, D-08, CISO-01/CISO-05)
# =========================================================================


@dataclass(frozen=True, slots=True)
class ClientAccessTokenClaims:
    """Decoded client access-token claims (D-07).

    No `role` field — clients are not staff. `aud="client"` is the
    isolation discriminator. `require_client()` asserts aud; staff
    `decode_access_token` never validates aud (D-07 byte-parity).
    """

    sub: str  # str(client_uuid)
    aud: str  # always "client"
    typ: str  # always "access"
    iat: int  # UTC epoch seconds
    exp: int  # UTC epoch seconds


def encode_client_token(
    client_id: UUID,
    *,
    now: datetime | None = None,
) -> str:
    """Mint a short-lived client access JWT (HS256, settings.access_token_ttl_seconds).

    Mirrors `encode_access_token` but emits `aud="client"` and no `role` (D-07).
    `now` is injectable for unit tests; production callers pass nothing.
    """
    settings = get_settings()
    issued = now or datetime.now(tz=UTC)
    expires = issued + timedelta(seconds=settings.access_token_ttl_seconds)
    payload = {
        "sub": str(client_id),
        "aud": "client",
        "typ": "access",
        "iat": int(issued.timestamp()),
        "exp": int(expires.timestamp()),
    }
    return jwt.encode(
        payload,
        settings.secret_key.get_secret_value(),
        algorithm="HS256",
    )


def decode_client_token(token: str) -> ClientAccessTokenClaims:
    """Decode + validate a client access JWT.

    Mirrors `decode_access_token` but asserts `aud=="client"` (D-08) and
    never coerces a `role` claim. A staff token (no `aud`) will fail here
    because `require=["aud"]` makes PyJWT raise MissingRequiredClaimError
    → `InvalidAccessToken("invalid_token")`. A client token passed to
    `decode_access_token` will fail there because it lacks `role`.

    Raises InvalidAccessToken (401) on:
      - expired signature → message "token_expired"
      - any other PyJWT failure (bad sig, malformed, missing claim) → "invalid_token"
      - wrong `typ` claim → "wrong_token_type"
      - wrong `aud` claim (not "client") → "wrong_audience"
    """
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.secret_key.get_secret_value(),
            algorithms=["HS256"],
            leeway=settings.jwt_clock_leeway_seconds,
            # verify_aud=False: we require "aud" claim to be present via `require` but
            # validate its value manually below to emit the specific "wrong_audience" code
            # (PyJWT's InvalidAudienceError would surface as generic "invalid_token").
            options={"require": ["sub", "aud", "typ", "iat", "exp"], "verify_aud": False},
        )
    except jwt.ExpiredSignatureError as exc:
        raise InvalidAccessToken("token_expired") from exc
    except jwt.InvalidTokenError as exc:
        # Parent class — covers DecodeError, MissingRequiredClaimError (incl. missing aud),
        # InvalidSignatureError, InvalidAlgorithmError, etc.
        raise InvalidAccessToken("invalid_token") from exc

    if payload.get("typ") != "access":
        raise InvalidAccessToken("wrong_token_type")
    if payload.get("aud") != "client":
        raise InvalidAccessToken("wrong_audience")

    return ClientAccessTokenClaims(
        sub=payload["sub"],
        aud=payload["aud"],
        typ=payload["typ"],
        iat=payload["iat"],
        exp=payload["exp"],
    )


# =========================================================================
# QR self-check-in token (D-70-07 / D-70-08)
# =========================================================================


@dataclass(frozen=True, slots=True)
class QrTokenClaims:
    """Decoded QR check-in token claims (D-70-07).

    `aud="qr"` and `typ="qr_checkin"` are the isolation discriminators —
    structurally non-interchangeable with the client access token (`aud="client"`,
    `typ="access"`) and with staff tokens. A leaked QR token fails `require_client()`
    (wrong aud/typ); an access token is rejected at `decode_qr_token` (wrong typ).
    """

    sub: str  # str(client_uuid) — the ONLY client source for check-in (D-70-10)
    aud: str  # always "qr"
    typ: str  # always "qr_checkin"
    iat: int  # UTC epoch seconds
    exp: int  # UTC epoch seconds


def encode_qr_token(
    client_id: UUID,
    *,
    now: datetime | None = None,
) -> str:
    """Mint a short-lived QR self-check-in JWT (HS256, settings.qr_token_ttl_seconds ≈ 60s).

    Mirrors `encode_client_token` but emits `aud="qr"` and `typ="qr_checkin"` (D-70-08),
    making the token structurally distinct from access/refresh tokens.
    `now` is injectable for unit tests; production callers pass nothing.
    """
    settings = get_settings()
    issued = now or datetime.now(tz=UTC)
    expires = issued + timedelta(seconds=settings.qr_token_ttl_seconds)
    payload = {
        "sub": str(client_id),
        "aud": "qr",
        "typ": "qr_checkin",
        "iat": int(issued.timestamp()),
        "exp": int(expires.timestamp()),
    }
    return jwt.encode(
        payload,
        settings.secret_key.get_secret_value(),
        algorithm="HS256",
    )


def decode_qr_token(token: str) -> QrTokenClaims:
    """Decode + validate a QR check-in JWT.

    Mirrors `decode_client_token` but asserts `aud=="qr"` and `typ=="qr_checkin"`
    (D-70-08). A client access token passed here will fail with "wrong_token_type"
    (typ=="access"). A QR token passed to `decode_client_token` will fail there
    with "wrong_token_type" (typ!="access").

    Raises InvalidAccessToken (401) on:
      - expired signature → message "token_expired"
      - any other PyJWT failure (bad sig, malformed, missing claim) → "invalid_token"
      - wrong `typ` claim (not "qr_checkin") → "wrong_token_type"
      - wrong `aud` claim (not "qr") → "wrong_audience"
    """
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.secret_key.get_secret_value(),
            algorithms=["HS256"],
            leeway=settings.jwt_clock_leeway_seconds,
            # verify_aud=False: we require "aud" claim to be present via `require` but
            # validate its value manually below to emit the specific "wrong_audience" code
            # (mirrors decode_client_token discipline — D-70-08).
            options={"require": ["sub", "aud", "typ", "iat", "exp"], "verify_aud": False},
        )
    except jwt.ExpiredSignatureError as exc:
        raise InvalidAccessToken("token_expired") from exc
    except jwt.InvalidTokenError as exc:
        raise InvalidAccessToken("invalid_token") from exc

    if payload.get("typ") != "qr_checkin":
        raise InvalidAccessToken("wrong_token_type")
    if payload.get("aud") != "qr":
        raise InvalidAccessToken("wrong_audience")

    return QrTokenClaims(
        sub=payload["sub"],
        aud=payload["aud"],
        typ=payload["typ"],
        iat=payload["iat"],
        exp=payload["exp"],
    )


# =========================================================================
# Client cookie matrix (D-10, CISO-05)
# =========================================================================


def issue_client_session_cookies(
    response: Response,
    *,
    access_token: str,
    refresh_token: str,
    csrf_token: str,
    secure: bool,
) -> None:
    """Set cc_client_access + cc_client_refresh + clubcore_client_csrf cookies.

    Mirrors `issue_session_cookies` for the client principal (D-10). Key differences:
    - Cookie names use `cc_client_*` / `clubcore_client_csrf` to prevent collision
      with staff `cc_*` cookies on the same origin (CISO-05).
    - `cc_client_refresh` is Path-scoped to `/api/v1/client` (never sent on staff
      `/api/v1/auth` paths — T-68-07 mitigation).
    - `clubcore_client_csrf` is httponly=False so the PWA can read it for the
      double-submit pattern (mirrors staff `clubcore_csrf` treatment).
    """
    settings = get_settings()

    # cc_client_access — covers all API paths
    response.set_cookie(
        key="cc_client_access",
        value=access_token,
        max_age=settings.access_token_ttl_seconds,
        path="/",
        httponly=True,
        secure=secure,
        samesite="lax",
    )

    # cc_client_refresh — narrow path; only sent to /api/v1/client/* (D-10)
    response.set_cookie(
        key="cc_client_refresh",
        value=refresh_token,
        max_age=settings.refresh_token_ttl_seconds,
        path="/api/v1/client",
        httponly=True,
        secure=secure,
        samesite="lax",
    )

    # clubcore_client_csrf — non-httpOnly so PWA reads it for X-CSRF-Token header
    # (double-submit pattern; mirrors staff clubcore_csrf, T-68-09 accepted risk).
    response.set_cookie(
        key="clubcore_client_csrf",
        value=csrf_token,
        max_age=settings.refresh_token_ttl_seconds,
        path="/",
        httponly=False,
        secure=secure,
        samesite="lax",
    )


def clear_client_session_cookies(response: Response, *, secure: bool) -> None:
    """Clear cc_client_access + cc_client_refresh + clubcore_client_csrf.

    Mirrors `clear_session_cookies` attribute discipline: Path / HttpOnly /
    SameSite / Secure MUST match `issue_client_session_cookies` exactly or
    the browser silently ignores the deletion (T-68-08 mitigation, D-10).
    """
    # cc_client_access — Path=/ (matches issuer)
    response.delete_cookie(
        key="cc_client_access",
        path="/",
        httponly=True,
        secure=secure,
        samesite="lax",
    )
    # cc_client_refresh — Path=/api/v1/client (matches issuer)
    response.delete_cookie(
        key="cc_client_refresh",
        path="/api/v1/client",
        httponly=True,
        secure=secure,
        samesite="lax",
    )
    # clubcore_client_csrf — Path=/, NOT httpOnly (matches issuer)
    response.delete_cookie(
        key="clubcore_client_csrf",
        path="/",
        httponly=False,
        secure=secure,
        samesite="lax",
    )
