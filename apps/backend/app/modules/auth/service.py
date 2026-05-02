"""Auth service — SQL+Redis seam (Phase 5).

Decisions implemented:
  D-09  — Redis session value JSON {family_id, last_seen_at, refresh_token_hash}
  D-10  — auth:user_sessions:{user_id} SET of family_ids for logout-all
  D-11  — Redis-first fast-path, Postgres authoritative for state changes
  D-13  — DB-led rotation chain via replaced_by_id + auth:rotate:{hash} 5s cache (Task 2b)
  D-14  — /auth/logout flow (revoke single family + clear cookies) (Task 2b)
  D-18  — rate-limit BEFORE password verify (AUTH-EP-03)
  D-20  — locked structlog event names (incl. password_changed_revokes_sessions)

The service NEVER bypasses the DB for state changes (revoke, rotate). Redis is a
follower: a flush degrades latency but does not lose correctness.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from redis.asyncio import Redis
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import emit
from app.core.config import get_settings
from app.core.exceptions import InvalidAccessToken, InvalidPassword
from app.core.security import (
    encode_access_token,
    generate_csrf_token,
    generate_refresh_token,
    hash_password,
    verify_password,
)
from app.modules.auth.models import RefreshToken, User
from app.modules.auth.rate_limit import bump_login_rate, check_login_rate


# ---------------------------------------------------------------------------
# Sentinel hash for timing-equivalent user-not-found path (Phase 4 D-28, AUTH-EP-02).
# Generated lazily on first call (avoid blocking the event loop at import time).
# ---------------------------------------------------------------------------

_SENTINEL_HASH: str | None = None


async def _get_sentinel_hash() -> str:
    """Return a fixed Argon2id hash of an unused random password.

    The hash is computed once per process. `verify_password` against it always
    raises InvalidPassword, but the wall-clock time matches a real verify —
    which is the AUTH-EP-02 timing-equivalence requirement.
    """
    global _SENTINEL_HASH
    if _SENTINEL_HASH is None:
        # Random secret; never sent over the wire, never persisted.
        _SENTINEL_HASH = await hash_password("__sentinel__never__matches__")
    return _SENTINEL_HASH


def _sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Loader — Phase 4 D-24 slot (registered in app.main.create_app per Plan 06)
# ---------------------------------------------------------------------------


async def load_user_by_id(session: AsyncSession, user_id: UUID) -> User | None:
    """Loader registered via register_user_loader() in create_app() (D-15).

    Returns None when no user with that id exists. The dependency at
    app.core.dependencies.get_current_user surfaces None as
    InvalidAccessToken('user_not_found').
    """
    return await session.get(User, user_id)


# ---------------------------------------------------------------------------
# Authenticate (login) — D-18 + AUTH-EP-02 timing equivalence
# ---------------------------------------------------------------------------


async def authenticate(
    session: AsyncSession,
    redis: Redis,
    email: str,
    password: str,
    *,
    ip: str | None = None,
) -> User:
    """Verify credentials, raise InvalidPassword on any failure.

    Timing-equivalence: even when the email is unknown, a real Argon2 verify
    runs against a sentinel hash so wall-clock latency matches the success
    path (Phase 4 D-28).

    Rate limit (D-18): the per-email counter is checked BEFORE the user
    lookup so the response code goes 429 → 401 → 200 without leaking which
    emails exist.
    """
    email_lower = email.lower()

    # 1. Rate limit BEFORE Argon2 (D-18). RateLimited is a 429 — propagate.
    await check_login_rate(redis, email_lower)

    user = await session.scalar(select(User).where(User.email == email_lower))
    target_hash = user.password_hash if user is not None else await _get_sentinel_hash()

    try:
        await verify_password(password, target_hash)
    except InvalidPassword:
        await bump_login_rate(redis, email_lower)
        emit(
            "login_failed",
            email=email_lower,
            reason="invalid_credentials",
            ip=ip,
        )
        raise

    if user is None:
        # Verify against sentinel succeeded only via implausible collision; treat
        # as failure (D-28). Bump rate + emit + raise.
        await bump_login_rate(redis, email_lower)
        emit(
            "login_failed",
            email=email_lower,
            reason="invalid_credentials",
            ip=ip,
        )
        raise InvalidPassword("invalid_credentials")

    emit("login_success", user_id=str(user.id), email=email_lower, ip=ip)
    return user


# ---------------------------------------------------------------------------
# Issue tokens — initial mint (called from /login)
# ---------------------------------------------------------------------------


async def issue_tokens(
    session: AsyncSession,
    redis: Redis,
    user: User,
) -> tuple[str, str, str]:
    """Mint a fresh (access, refresh, csrf) tuple and persist DB+Redis state.

    Returns:
        (access_jwt, raw_refresh_token, csrf_token) — caller writes cookies.

    Side effects:
        - INSERT new row into refresh_tokens with new family_id.
        - SET auth:session:{user_id}:{family_id} with EX=refresh_token_ttl_seconds.
        - SADD auth:user_sessions:{user_id} family_id; EXPIRE same TTL.
    """
    settings = get_settings()
    now = datetime.now(tz=UTC)
    family_id = uuid4()

    raw_refresh, refresh_hash = generate_refresh_token()
    access = encode_access_token(user.id, user.role, now=now)
    csrf = generate_csrf_token()

    rt = RefreshToken(
        user_id=user.id,
        family_id=family_id,
        token_hash=refresh_hash,
        expires_at=now + timedelta(seconds=settings.refresh_token_ttl_seconds),
    )
    session.add(rt)
    await session.commit()

    await _write_session_keys(
        redis,
        user_id=user.id,
        family_id=family_id,
        refresh_hash=refresh_hash,
        ttl=settings.refresh_token_ttl_seconds,
        now=now,
    )

    return access, raw_refresh, csrf


async def _write_session_keys(
    redis: Redis,
    *,
    user_id: UUID,
    family_id: UUID,
    refresh_hash: str,
    ttl: int,
    now: datetime,
) -> None:
    """Write D-09 session JSON + D-10 user_sessions SET membership."""
    session_value = json.dumps(
        {
            "family_id": str(family_id),
            "last_seen_at": now.isoformat(),
            "refresh_token_hash": refresh_hash,
        }
    )
    pipe = redis.pipeline()
    pipe.set(f"auth:session:{user_id}:{family_id}", session_value, ex=ttl)
    pipe.sadd(f"auth:user_sessions:{user_id}", str(family_id))
    pipe.expire(f"auth:user_sessions:{user_id}", ttl)
    await pipe.execute()


# ---------------------------------------------------------------------------
# Password-change wrapper — AUTH-LO-03 / D-20 call site
# ---------------------------------------------------------------------------
# The admin password-change endpoint itself is deferred (D-20). The wrapper
# exists NOW so whoever lands the admin endpoint can call it without inventing
# a new event name. It delegates to revoke_all_sessions (defined in Task 2b)
# and re-emits with the locked event name `password_changed_revokes_sessions`.


async def revoke_sessions_on_password_change(
    session: AsyncSession,
    redis: Redis,
    user_id: UUID,
) -> int:
    """Revoke every alive refresh-token family for the user after a password change.

    Locked call site for AUTH-LO-03 (D-20). NOT wired to any Phase 5 route — the
    admin password-change endpoint is deferred. The wrapper exists so the event
    name `password_changed_revokes_sessions` is already in source when the
    admin endpoint lands; Phase 8 audit-DB swap-in does not need a rename.

    Returns the family count (same as revoke_all_sessions).
    """
    family_count = await revoke_all_sessions(session, redis, user_id)
    emit(
        "password_changed_revokes_sessions",
        user_id=str(user_id),
        family_count=family_count,
    )
    return family_count
