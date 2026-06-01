"""Client auth service — OTP request/verify, session rotation, profile update (Phase 68).

Decisions implemented:
  D-01  — phone-first OTP delivery: Client.telegram_user_id DM (via bot sender slot)
  D-02  — silent no-op anti-oracle for unknown/unlinked/soft-deleted phones
  D-04  — PATCH /client/me accepts email only
  D-06  — 409 email_unavailable on duplicate email (generic, non-enumerating)
  D-09  — separate client refresh stack (ClientRefreshToken + auth:client:* Redis)
  D-11  — rate-limit-before-lookup ordering (CAUTH-02 timing-equivalence)

Security-critical invariants (do NOT regress):
  CAUTH-02: rate-limit checks run BEFORE Client lookup; _constant_time_floor covers ALL paths.
  CAUTH-04: rotate_client_refresh branch (C) revokes the whole family on token reuse.
  CISO-05:  Redis keys are auth:client:* ONLY — never auth:session:* / auth:user_sessions:*.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import time
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Final, cast
from uuid import UUID, uuid4

import structlog
from redis.asyncio import Redis
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import audit
from app.core.config import get_settings
from app.core.exceptions import InvalidAccessToken, InvalidSession
from app.core.security import (
    encode_client_token,
    generate_csrf_token,
    generate_otp_code,
    generate_refresh_token,
)
from app.modules.auth.exceptions import OtpInvalid, OtpMaxAttempts
from app.modules.auth.models import OtpCode
from app.modules.client_auth.models import ClientRefreshToken
from app.modules.client_auth.rate_limit import (
    bump_client_ip_rate,
    bump_client_otp_daily,
    check_client_ip_rate,
    check_client_otp_cooldown,
    check_client_otp_daily,
    record_client_otp_sent,
)
from app.modules.clients.models import Client

_log = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Composition-root OTP sender slot (D-01 / Phase 68)
#
# The HTTP server process does not run the bot long-poll loop.  A bare
# `telegram.Bot` can still send DMs via the Bot API — `build_bot(token=...)`
# constructs one.  The slot is populated by `app.main.create_app()` (Phase 68
# plan 05); until then it is `None` and `request_client_otp` silently skips
# the DM (test / no-token-configured mode).
# ---------------------------------------------------------------------------

# ClientOtpSender: async (chat_id: int, code: str) -> None
ClientOtpSender = Callable[[int, str], Awaitable[None]]

_client_otp_sender: ClientOtpSender | None = None


def register_client_otp_sender(sender: ClientOtpSender) -> None:
    """Composition-root setter — called once by app.main.create_app (Phase 68 plan 05)."""
    global _client_otp_sender
    _client_otp_sender = sender


# ---------------------------------------------------------------------------
# Anti-oracle constant-time floor (CAUTH-02 / D-42-22 lineage)
# ---------------------------------------------------------------------------

_CLIENT_OTP_FLOOR_MS: Final[float] = 200.0


async def _constant_time_floor(t_start: float) -> None:
    """Sleep just long enough to pad request_client_otp to the floor.

    Anti-oracle uniformity (D-02): all branches (eligible / unknown-phone /
    unlinked / rate-limited) converge on this floor so wall-clock duration
    cannot be used as an oracle for "did the phone belong to a linked client?".
    Applied via try/finally so exceptions (RateLimited, DB errors) also hit
    the floor.
    """
    elapsed_ms = (time.perf_counter() - t_start) * 1000
    remaining_ms = _CLIENT_OTP_FLOOR_MS - elapsed_ms
    if remaining_ms > 0:
        await asyncio.sleep(remaining_ms / 1000)


# ---------------------------------------------------------------------------
# SHA-256 helper (local copy — mirrors service.py pattern)
# ---------------------------------------------------------------------------


def _sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Redis session key helpers (D-09 — auth:client:* namespace only)
# ---------------------------------------------------------------------------


async def _write_client_session_keys(
    redis: Redis,
    *,
    client_id: UUID,
    family_id: UUID,
    refresh_hash: str,
    ttl: int,
    now: datetime,
) -> None:
    """Write auth:client:session + auth:client:user_sessions keys.

    Mirrors _write_session_keys (auth/service.py L293-323) but namespaced
    auth:client:* to ensure CISO-05 staff/client storage separation.
    """
    session_value = json.dumps(
        {
            "family_id": str(family_id),
            "last_seen_at": now.isoformat(),
            "refresh_token_hash": refresh_hash,
        }
    )
    pipe = redis.pipeline()
    pipe.set(f"auth:client:session:{client_id}:{family_id}", session_value, ex=ttl)
    pipe.sadd(f"auth:client:user_sessions:{client_id}", str(family_id))
    pipe.expire(f"auth:client:user_sessions:{client_id}", ttl)
    await pipe.execute()


# ---------------------------------------------------------------------------
# OTP placeholder prefix — mirrors _EMAIL_DEEP_LINK_PLACEHOLDER_PREFIX pattern
# ---------------------------------------------------------------------------

_CLIENT_OTP_TOKEN_PREFIX: Final[str] = "client-otp:"  # noqa: S105 — not a password, prefix for OtpCode.deep_link_token_hash uniqueness


# ---------------------------------------------------------------------------
# request_client_otp — CAUTH-01/02/06/D-01/D-02/D-11
# ---------------------------------------------------------------------------


async def request_client_otp(
    session: AsyncSession,
    redis: Redis,
    phone: str,
    *,
    ip: str | None = None,
) -> None:
    """POST /client/otp/request entry.

    Anti-oracle invariant (D-02 / CAUTH-02):
    unknown-phone / unlinked / soft-deleted all return None with a floor-padded
    wall-clock matching the success branch — byte-identical response shape.

    Rate-limit check BEFORE subject lookup (D-11): latency does not vary by
    whether the phone is known.

    _constant_time_floor covers ALL paths including RateLimited exceptions
    (try/finally).
    """
    t_start = time.perf_counter()
    try:
        # Rate-limit checks BEFORE any DB lookup (D-11 / CAUTH-02).
        await check_client_ip_rate(redis, ip)
        await check_client_otp_cooldown(redis, phone)
        await check_client_otp_daily(redis, phone)

        client = await session.scalar(
            select(Client).where(
                Client.phone == phone,
                Client.deleted_at.is_(None),
            )
        )

        # D-02: silent no-op for unknown / unlinked phones — byte-identical to success.
        if client is None or client.telegram_user_id is None:
            return

        now = datetime.now(tz=UTC)

        # Atomic single-active: consume prior active client OTP.
        # (mirrors request_otp_email / RFC 6238 single-active per principal)
        await session.execute(
            update(OtpCode)
            .where(
                OtpCode.client_id == client.id,
                OtpCode.consumed_at.is_(None),
            )
            .values(consumed_at=now)
        )

        raw_code, code_hash = generate_otp_code()
        # deep_link_token_hash is nullable=False + unique=True; use a
        # client-otp: prefixed placeholder (non-overlapping with real sha256 hashes).
        placeholder_token_hash = f"{_CLIENT_OTP_TOKEN_PREFIX}{uuid4().hex}"

        settings = get_settings()
        # Dev-only: pin the client OTP to a constant so local UAT can sign in
        # without reading the backend log. WR-06: gated on BOTH ENVIRONMENT=dev
        # AND the explicit dev_otp_pin_enabled opt-in (default False) so a misset
        # ENVIRONMENT alone cannot turn this into an auth bypass. Settings also
        # fails fast at startup if the flag is True outside dev. staging/prod keep
        # the random secrets.randbelow() code from generate_otp_code().
        if settings.environment == "dev" and settings.dev_otp_pin_enabled:
            raw_code = "111111"
            code_hash = _sha256_hex(raw_code)

        otp_row = OtpCode(
            client_id=client.id,
            user_id=None,
            channel="telegram",
            deep_link_token_hash=placeholder_token_hash,
            code_hash=code_hash,
            telegram_chat_id=client.telegram_user_id,
            expires_at=now + timedelta(seconds=settings.otp_code_ttl_seconds),
            attempts=0,
            consumed_at=None,
        )
        session.add(otp_row)

        # Pitfall 2: audit.emit BEFORE commit so the audit row commits atomically.
        await audit.emit(
            session,
            "client_otp_requested",
            actor_user_id=None,
            resource_type="otp",
            client_id=str(client.id),
            channel="telegram",
        )
        await session.commit()

        # Bump rate-limit counters AFTER the DB commit succeeds.
        await record_client_otp_sent(redis, phone)
        await bump_client_otp_daily(redis, phone)
        await bump_client_ip_rate(redis, ip)

        # D-01: send OTP DM via composition-root bot sender.
        # Slot is None in test / unconfigured mode — skip silently.
        if _client_otp_sender is not None:
            await _client_otp_sender(client.telegram_user_id, raw_code)

    finally:
        # Anti-oracle floor MUST run on ALL paths including exceptions (CAUTH-02).
        await _constant_time_floor(t_start)


# ---------------------------------------------------------------------------
# verify_client_otp — CAUTH-01/06/D-09
# ---------------------------------------------------------------------------


async def verify_client_otp(
    session: AsyncSession,
    redis: Redis,
    phone: str,
    code: str,
) -> tuple[str, str, str]:
    """Verify a client OTP; return (access_token, raw_refresh_token, csrf_token).

    Consume/attempts logic is implemented INLINE against OtpCode.client_id.
    Do NOT call telegram_service.consume() — it requires a raw_deep_link_token
    not used in the client auth flow (D-01).

    Brute-force protection: OtpCode.attempts incremented on mismatch;
    OtpMaxAttempts raised when >= settings.otp_max_attempts (CAUTH-06).

    Anti-oracle (CR-02 / CAUTH-02): ALL rejection paths — unknown phone,
    no active OTP, expired OTP, wrong code, consumed OTP — raise
    InvalidAccessToken("invalid_session") → HTTP 401 with an identical body.
    OtpExpired (HTTP 410) is deliberately NOT used here: a distinct status code
    would reveal that a recent OTP was issued for the phone (phone enumeration).

    Constant-time floor (WR-02): _constant_time_floor wraps the entire function
    body via try/finally so the one-query (unknown phone) and two-query (known
    phone) paths converge to the same wall-clock duration, closing the timing
    oracle that mirrors the request_client_otp anti-oracle discipline.
    """
    t_start = time.perf_counter()
    try:
        settings = get_settings()
        now = datetime.now(tz=UTC)

        # Look up the alive linked client.
        client = await session.scalar(
            select(Client).where(
                Client.phone == phone,
                Client.deleted_at.is_(None),
            )
        )
        if client is None or client.telegram_user_id is None:
            raise InvalidAccessToken("invalid_session")

        # Look up the active (unconsumed) OTP for this client.
        otp_row = await session.scalar(
            select(OtpCode).where(
                OtpCode.client_id == client.id,
                OtpCode.channel == "telegram",
                OtpCode.consumed_at.is_(None),
            )
        )
        if otp_row is None:
            raise InvalidAccessToken("invalid_session")
        # CR-02: use the same 401 for expired OTP — 410 leaks "phone had a recent OTP".
        if otp_row.expires_at < now:
            raise InvalidAccessToken("invalid_session")

        # Inline consume/attempts logic (CAUTH-06 brute-force protection).
        # WR-03: a correct code after OtpMaxAttempts wrong guesses is intentionally
        # still accepted — this mirrors app/modules/auth/telegram_service.py:consume()
        # (staff flow) and avoids a lock-out DoS where an attacker burns the attempt
        # counter on a victim's phone. The OtpMaxAttempts signal is informational:
        # it tells the UI to prompt a fresh OTP request, but the correct code remains
        # valid until the OTP row expires or is consumed.
        presented_hash = _sha256_hex(code)
        if presented_hash != otp_row.code_hash:
            # Inc + commit BEFORE raise so an attacker dropping the response
            # cannot rewind the counter.
            otp_row.attempts += 1
            await session.commit()
            if otp_row.attempts >= settings.otp_max_attempts:
                raise OtpMaxAttempts("otp_max_attempts")
            remaining = settings.otp_max_attempts - otp_row.attempts
            raise OtpInvalid("otp_invalid", fields={"attemptsRemaining": remaining})

        # Success — stamp consumed_at.
        otp_row.consumed_at = now

        # Mint a new session family.
        family_id = uuid4()
        raw_refresh, refresh_hash = generate_refresh_token()
        access = encode_client_token(client.id, now=now)
        csrf = generate_csrf_token()

        new_token_row = ClientRefreshToken(
            client_id=client.id,
            family_id=family_id,
            token_hash=refresh_hash,
            expires_at=now + timedelta(seconds=settings.refresh_token_ttl_seconds),
        )
        session.add(new_token_row)

        # Pitfall 2: audit.emit BEFORE commit so the audit row commits atomically.
        await audit.emit(
            session,
            "client_otp_consumed",
            actor_user_id=None,
            resource_type="otp",
            client_id=str(client.id),
            channel="telegram",
        )
        await session.commit()

        # Write Redis session keys in auth:client:* namespace (CISO-05).
        await _write_client_session_keys(
            redis,
            client_id=client.id,
            family_id=family_id,
            refresh_hash=refresh_hash,
            ttl=settings.refresh_token_ttl_seconds,
            now=now,
        )

        return access, raw_refresh, csrf
    finally:
        # Anti-oracle floor MUST run on ALL paths including exceptions (CAUTH-02 / WR-02).
        await _constant_time_floor(t_start)


# ---------------------------------------------------------------------------
# rotate_client_refresh — CAUTH-04/D-09 (3-branch rotation)
# ---------------------------------------------------------------------------


async def rotate_client_refresh(
    session: AsyncSession,
    redis: Redis,
    presented_token: str,
) -> tuple[str, str, str]:
    """Rotate a client refresh token; return new (access, refresh, csrf).

    Three explicit branches per D-09 (mirrors rotate_refresh in auth/service.py):

      (A) ACTIVE — revoked_at IS NULL AND replaced_by_id IS NULL AND not expired:
          Mint new pair, INSERT new row, UPDATE old (replaced_by_id, replaced_at).
          Cache new pair at auth:client:rotate:{old_hash} for reuse window.

      (B) REPLACED-WITHIN-WINDOW — replaced_by_id IS NOT NULL AND replaced_at > now - W:
          Look up auth:client:rotate:{old_hash}. If cache hit, return cached pair
          (idempotent same-pair return for double-submit). Cache miss falls to (C).

      (C) REUSE/REVOKED — anything else:
          Revoke whole family (UPDATE all rows with that client_id + family_id).
          Emit client_family_reuse_detected audit event.
          Raise InvalidSession.

    SELECT ... FOR UPDATE serializes concurrent rotators on the DB row.
    Redis cache is an optimisation; DB is the source of truth (D-09).
    """
    settings = get_settings()
    presented_hash = _sha256_hex(presented_token)
    now = datetime.now(tz=UTC)
    window = timedelta(seconds=settings.refresh_reuse_window_seconds)

    row = await session.scalar(
        select(ClientRefreshToken)
        .where(ClientRefreshToken.token_hash == presented_hash)
        .with_for_update()
    )

    if row is None:
        raise InvalidSession("invalid_session")

    # ---- Branch (A): ACTIVE — rotate ------------------------------------
    if row.revoked_at is None and row.replaced_by_id is None and row.expires_at > now:
        # Verify the owning client is still alive.
        client_alive = await session.scalar(
            select(Client).where(
                Client.id == row.client_id,
                Client.deleted_at.is_(None),
            )
        )
        if client_alive is None:
            await audit.emit(
                session,
                "client_refresh_failed",
                actor_user_id=None,
                resource_type="session",
                resource_id=None,
                client_id=str(row.client_id),
                reason="client_inactive",
            )
            await session.commit()
            raise InvalidSession("invalid_session")

        raw_refresh, refresh_hash = generate_refresh_token()
        access = encode_client_token(row.client_id, now=now)
        csrf = generate_csrf_token()

        new_row = ClientRefreshToken(
            client_id=row.client_id,
            family_id=row.family_id,
            token_hash=refresh_hash,
            expires_at=now + timedelta(seconds=settings.refresh_token_ttl_seconds),
        )
        session.add(new_row)
        await session.flush()
        row.replaced_by_id = new_row.id
        row.replaced_at = now
        await session.commit()

        # Race-window cache — NX so a concurrent caller cannot overwrite the pair.
        await redis.set(
            f"auth:client:rotate:{presented_hash}",
            json.dumps(
                {
                    "access_token": access,
                    "refresh_token": raw_refresh,
                    "csrf_token": csrf,
                }
            ),
            ex=settings.refresh_reuse_window_seconds,
            nx=True,
        )

        await _write_client_session_keys(
            redis,
            client_id=row.client_id,
            family_id=row.family_id,
            refresh_hash=refresh_hash,
            ttl=settings.refresh_token_ttl_seconds,
            now=now,
        )
        return access, raw_refresh, csrf

    # ---- Branch (B): REPLACED-WITHIN-WINDOW — idempotent same-pair return --
    if (
        row.replaced_by_id is not None
        and row.replaced_at is not None
        and row.replaced_at > now - window
    ):
        cached = await redis.get(f"auth:client:rotate:{presented_hash}")
        if cached is not None:
            payload = json.loads(cached)
            return (
                payload["access_token"],
                payload["refresh_token"],
                payload["csrf_token"],
            )
        # Cache miss: window expired between callers. Fall through to (C).

    # ---- Branch (C): REUSE/REVOKED — family revocation --------------------
    await session.execute(
        update(ClientRefreshToken)
        .where(
            ClientRefreshToken.client_id == row.client_id,
            ClientRefreshToken.family_id == row.family_id,
            ClientRefreshToken.revoked_at.is_(None),
        )
        .values(revoked_at=now)
    )
    # Pitfall 2: emit BEFORE commit so audit row commits atomically with revocation.
    await audit.emit(
        session,
        "client_family_reuse_detected",
        actor_user_id=None,
        resource_type="session",
        resource_id=row.family_id,
        client_id=str(row.client_id),
        presented_token_hash_prefix=presented_hash[:8],
    )
    await session.commit()

    # Outside the DB tx: clean Redis (best-effort; DB already holds truth).
    # `srem` is typed as `Awaitable[int] | int` (redis-py shares stubs across
    # sync/async clients); cast to disambiguate for mypy.
    await redis.delete(f"auth:client:session:{row.client_id}:{row.family_id}")
    await cast(
        "Awaitable[int]",
        redis.srem(
            f"auth:client:user_sessions:{row.client_id}",
            str(row.family_id),
        ),
    )

    raise InvalidSession("invalid_session")


# ---------------------------------------------------------------------------
# revoke_client_session — /client/session/logout (D-09)
# ---------------------------------------------------------------------------


async def revoke_client_session(
    session: AsyncSession,
    redis: Redis,
    presented_token: str,
) -> None:
    """Revoke the family the presented refresh token belongs to.

    Idempotent: if the token doesn't exist (already revoked / unknown), the
    DB UPDATE is a no-op and Redis DEL is a no-op.
    """
    presented_hash = _sha256_hex(presented_token)
    now = datetime.now(tz=UTC)

    row = await session.scalar(
        select(ClientRefreshToken).where(
            ClientRefreshToken.token_hash == presented_hash
        )
    )
    if row is None:
        return

    client_id = row.client_id
    family_id = row.family_id

    await session.execute(
        update(ClientRefreshToken)
        .where(
            ClientRefreshToken.client_id == client_id,
            ClientRefreshToken.family_id == family_id,
            ClientRefreshToken.revoked_at.is_(None),
        )
        .values(revoked_at=now)
    )
    # Pitfall 2: emit BEFORE commit.
    await audit.emit(
        session,
        "client_session_revoked",
        actor_user_id=None,
        resource_type="session",
        resource_id=family_id,
        client_id=str(client_id),
    )
    await session.commit()

    # Outside the tx: clean Redis.
    pipe = redis.pipeline()
    pipe.delete(f"auth:client:session:{client_id}:{family_id}")
    pipe.srem(f"auth:client:user_sessions:{client_id}", str(family_id))
    await pipe.execute()

