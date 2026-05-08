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
from collections.abc import Awaitable
from datetime import UTC, datetime, timedelta
from typing import Literal, cast
from uuid import UUID, uuid4

import structlog
from redis.asyncio import Redis
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import audit
from app.core.config import get_settings
from app.core.exceptions import InvalidAccessToken, InvalidPassword
from app.core.pagination import PaginatedData
from app.core.security import (
    encode_access_token,
    generate_csrf_token,
    generate_refresh_token,
    hash_password,
    verify_password,
)
from app.modules.auth.models import RefreshToken, User
from app.modules.auth.rate_limit import bump_login_rate, check_login_rate
from app.modules.auth.schemas import ActiveSessionItem

_log = structlog.get_logger(__name__)

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


def _classify_verify_error(exc: InvalidPassword) -> str:
    """Map the argon2-cffi cause to an ops-triage reason string (HYG-01 D-23-13).

    Inspects exc.__cause__ (chained by verify_password with `raise ... from exc`).
    Returns: 'verify_mismatch' | 'invalid_hash' | 'other'.
    NEVER called with the raw cause itself — keeps the call site clean.
    """
    from argon2.exceptions import InvalidHashError, VerifyMismatchError

    cause = exc.__cause__
    if isinstance(cause, VerifyMismatchError):
        return "verify_mismatch"
    if isinstance(cause, InvalidHashError):
        return "invalid_hash"
    return "other"


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
    except InvalidPassword as exc:
        # HYG-01 D-23-13: TWO emits per failed verify path.
        # (1) Structlog WARNING (operator side) — carries the verify-error reason for
        #     ops triage (distinguishes wrong-password from corrupted-hash).
        #     D-23-14: NEVER carries raw password, hash bytes, user_id, or telegram_chat_id.
        _log.warning(
            "login_verify_error",
            reason=_classify_verify_error(exc),
            email_lower=email_lower,
            ip=ip,
        )
        # (2) Audit DB row (compliance side) — stays generic with reason='invalid_credentials'
        #     to preserve Phase 5 AUTH-EP-02 timing/info equivalence. Compliance reviewers
        #     cannot distinguish wrong-password from non-existent-email from corrupted-hash.
        await bump_login_rate(redis, email_lower)
        await audit.emit(
            session,
            "login_failed",
            actor_user_id=None,
            resource_type="login_attempt",
            email=email_lower,
            reason="invalid_credentials",
            ip=ip,
        )
        # Phase 24 DEBT-03 / SVC001: persist the login_failed audit row before
        # the get_db rollback would otherwise drop it (mirrors Phase 12.1 fix).
        await session.commit()
        raise

    if user is None:
        # Verify against sentinel succeeded only via implausible collision; treat
        # as failure (D-28). Bump rate + emit + raise.
        await bump_login_rate(redis, email_lower)
        await audit.emit(
            session,
            "login_failed",
            actor_user_id=None,
            resource_type="login_attempt",
            email=email_lower,
            reason="invalid_credentials",
            ip=ip,
        )
        # Phase 24 DEBT-03 / SVC001: persist failure audit row before raising.
        await session.commit()
        raise InvalidPassword("invalid_credentials")

    await audit.emit(
        session,
        "login_success",
        actor_user_id=user.id,
        resource_type="session",
        resource_id=None,
        email=email_lower,
        ip=ip,
        channel="email_password",
    )
    # Phase 24 DEBT-03 / SVC001: persist the login_success audit row co-transactionally.
    await session.commit()
    return user


# ---------------------------------------------------------------------------
# Issue tokens — initial mint (called from /login)
# ---------------------------------------------------------------------------


async def issue_tokens(
    session: AsyncSession,
    redis: Redis,
    user: User,
    *,
    user_agent: str | None = None,
    channel: str = "email_password",
) -> tuple[str, str, str]:
    """Mint a fresh (access, refresh, csrf) tuple and persist DB+Redis state.

    Returns:
        (access_jwt, raw_refresh_token, csrf_token) — caller writes cookies.

    Side effects:
        - INSERT new row into refresh_tokens with new family_id.
        - SET auth:session:{user_id}:{family_id} with EX=refresh_token_ttl_seconds.
        - SADD auth:user_sessions:{user_id} family_id; EXPIRE same TTL.

    CD-01 (Phase 23): user_agent + channel written to Redis session JSON.
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
        user_agent=user_agent,
        channel=channel,
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
    user_agent: str | None = None,
    channel: str = "email_password",
) -> None:
    """Write D-09 session JSON + D-10 user_sessions SET membership.

    CD-01 (Phase 23): extends session JSON with user_agent + channel.
    Pre-Phase-23 sessions will not have these fields; callers that read the
    JSON fall back to None / 'email_password' respectively.
    """
    session_value = json.dumps(
        {
            "family_id": str(family_id),
            "last_seen_at": now.isoformat(),
            "refresh_token_hash": refresh_hash,
            "user_agent": user_agent,
            "channel": channel,
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
    await audit.emit(
        session,
        "password_changed_revokes_sessions",
        actor_user_id=user_id,
        resource_type="user",
        resource_id=user_id,
        family_count=family_count,
    )
    await session.commit()
    return family_count


# ---------------------------------------------------------------------------
# Rotate refresh — D-13 (THE Phase 5 hot path)
# ---------------------------------------------------------------------------


async def rotate_refresh(
    session: AsyncSession,
    redis: Redis,
    presented_token: str,
) -> tuple[str, str, str]:
    """Rotate a refresh token; return new (access, refresh, csrf).

    Three explicit branches per D-13:

      (A) ACTIVE — `revoked_at IS NULL AND replaced_by_id IS NULL AND not expired`:
          Mint new pair, INSERT new row, UPDATE old (replaced_by_id, replaced_at).
          Cache the new pair at `auth:rotate:{old_hash}` for refresh_reuse_window_seconds.

      (B) REPLACED-WITHIN-WINDOW — `replaced_by_id IS NOT NULL AND replaced_at > now - W`:
          Look up `auth:rotate:{old_hash}`. If hit, return the cached pair (idempotent
          same-pair return for the second of two parallel callers). Cache miss falls
          through to (C).

      (C) REUSE/REVOKED — anything else:
          UPDATE refresh_tokens SET revoked_at = now WHERE user_id+family_id alive.
          DEL auth:session:{user_id}:{family_id}.
          await audit.emit(session, 'family_reuse_detected', ...) before tx exits.
          Raise InvalidAccessToken('family_reuse_detected').

    SELECT ... FOR UPDATE acquires a row lock so two parallel rotators serialize on
    the DB (Postgres is the source of truth — D-11). Redis cache is an optimization
    on top of the DB chain, not the gate.
    """
    settings = get_settings()
    presented_hash = _sha256_hex(presented_token)
    now = datetime.now(tz=UTC)
    window = timedelta(seconds=settings.refresh_reuse_window_seconds)

    # Phase 24 DEBT-03 / SVC001: rely on AsyncSession autobegin (triggered by the
    # SELECT ... FOR UPDATE below) and explicit `await session.commit()` at the
    # end of each mutating branch — same pattern as `revoke_session` (see lines
    # 497-503). Replaces the previous `async with session.begin():` block; the
    # walker requires a literal `session.commit()` token in every public write
    # path, which the context-manager auto-commit shape did not provide.
    row = await session.scalar(
        select(RefreshToken)
        .where(RefreshToken.token_hash == presented_hash)
        .with_for_update()
    )

    if row is None:
        raise InvalidAccessToken("refresh_not_found")

    # ---- Branch (A): ACTIVE — rotate ------------------------------------
    if (
        row.revoked_at is None
        and row.replaced_by_id is None
        and row.expires_at > now
    ):
        user_loaded = await session.get(User, row.user_id)
        if user_loaded is None:
            raise InvalidAccessToken("user_not_found")

        raw_refresh, refresh_hash = generate_refresh_token()
        access = encode_access_token(user_loaded.id, user_loaded.role, now=now)
        csrf = generate_csrf_token()

        new_row = RefreshToken(
            user_id=row.user_id,
            family_id=row.family_id,
            token_hash=refresh_hash,
            expires_at=now + timedelta(seconds=settings.refresh_token_ttl_seconds),
        )
        session.add(new_row)
        await session.flush()
        row.replaced_by_id = new_row.id
        row.replaced_at = now
        # Phase 24 DEBT-03 / SVC001: commit the rotation atomically before
        # touching Redis; DB is the source of truth (D-11).
        await session.commit()

        # Race-window cache — NX so a concurrent caller cannot overwrite the pair.
        await redis.set(
            f"auth:rotate:{presented_hash}",
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

        # CD-01 (Phase 23): preserve user_agent + channel from prior session JSON.
        # If Redis miss (e.g. TTL expired between rotate calls), fall back to
        # None / 'email_password' so pre-Phase-23 sessions degrade gracefully.
        prior_ua: str | None = None
        prior_channel: str = "email_password"
        prior_raw = await redis.get(f"auth:session:{row.user_id}:{row.family_id}")
        if prior_raw is not None:
            try:
                prior = json.loads(prior_raw)
                prior_ua = prior.get("user_agent")
                prior_channel = prior.get("channel", "email_password")
            except (json.JSONDecodeError, AttributeError):
                pass

        await _write_session_keys(
            redis,
            user_id=row.user_id,
            family_id=row.family_id,
            refresh_hash=refresh_hash,
            ttl=settings.refresh_token_ttl_seconds,
            now=now,
            user_agent=prior_ua,
            channel=prior_channel,
        )
        return access, raw_refresh, csrf

    # ---- Branch (B): REPLACED-WITHIN-WINDOW — same-pair return -----------
    if (
        row.replaced_by_id is not None
        and row.replaced_at is not None
        and row.replaced_at > now - window
    ):
        cached = await redis.get(f"auth:rotate:{presented_hash}")
        if cached is not None:
            payload = json.loads(cached)
            return (
                payload["access_token"],
                payload["refresh_token"],
                payload["csrf_token"],
            )
        # Cache miss: window expired between caller and us. Fall through to (C).

    # ---- Branch (C): REUSE/REVOKED — family revocation -------------------
    await session.execute(
        update(RefreshToken)
        .where(
            RefreshToken.user_id == row.user_id,
            RefreshToken.family_id == row.family_id,
            RefreshToken.revoked_at.is_(None),
        )
        .values(revoked_at=now)
    )
    # Pitfall 2: emit BEFORE commit so the audit row commits atomically with
    # the family revocation UPDATE (same shape as revoke_session / revoke_family).
    await audit.emit(
        session,
        "family_reuse_detected",
        actor_user_id=row.user_id,
        resource_type="session",
        resource_id=row.family_id,
        presented_token_hash_prefix=presented_hash[:8],
    )
    # Phase 24 DEBT-03 / SVC001: explicit commit replaces the previous
    # context-manager auto-commit on `async with session.begin():` exit.
    await session.commit()

    # Outside the DB tx: clean Redis (best-effort; DB already holds truth).
    # `srem` is typed as `Awaitable[int] | int` (redis-py shares stubs across
    # sync/async clients); cast to disambiguate for mypy.
    await redis.delete(f"auth:session:{row.user_id}:{row.family_id}")
    await cast(
        "Awaitable[int]",
        redis.srem(f"auth:user_sessions:{row.user_id}", str(row.family_id)),
    )

    raise InvalidAccessToken("family_reuse_detected")


# ---------------------------------------------------------------------------
# Revoke session (single family) — /auth/logout (D-14)
# ---------------------------------------------------------------------------


async def revoke_session(
    session: AsyncSession,
    redis: Redis,
    presented_token: str,
) -> None:
    """Revoke the family the presented refresh token belongs to (D-14).

    Idempotent: if the token doesn't exist (already-revoked / unknown), the
    DB UPDATE is a no-op and Redis DEL is a no-op. The route handler always
    clears cookies regardless.

    IMPLEMENTATION NOTE — single transaction context:
    The SELECT (to derive user_id + family_id from token_hash) and the UPDATE
    live in ONE `async with session.begin():` block. A previous draft did the
    SELECT outside the block and then opened `session.begin()` for the UPDATE —
    this raises InvalidRequestError because AsyncSession autobegins on the
    first statement, and the explicit begin() then collides with the autobegun
    transaction. Keep both statements inside the same begin().
    """
    presented_hash = _sha256_hex(presented_token)
    now = datetime.now(tz=UTC)

    # The route's `get_current_user` dependency may already have issued a SELECT
    # on this session, autobegining a transaction. Calling `session.begin()` on
    # an already-begun session raises InvalidRequestError. Rely on the autobegun
    # transaction (or trigger one via the SELECT below) and `session.commit()`
    # explicitly at the end. Equivalent semantics to `async with session.begin()`
    # for our purposes: select + update + commit; rollback on raise (callers
    # propagate; the get_db dep cleans up via `async with sessionmaker()`).
    row = await session.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == presented_hash)
    )
    if row is None:
        # Idempotent: unknown token, nothing to revoke. Exit the tx clean.
        return

    user_id = row.user_id
    family_id = row.family_id

    await session.execute(
        update(RefreshToken)
        .where(
            RefreshToken.user_id == user_id,
            RefreshToken.family_id == family_id,
            RefreshToken.revoked_at.is_(None),
        )
        .values(revoked_at=now)
    )
    # Pitfall 2: emit BEFORE commit so the audit row commits atomically with
    # the revocation UPDATE.
    await audit.emit(
        session,
        "session_revoked",
        actor_user_id=user_id,
        resource_type="session",
        resource_id=family_id,
    )
    await session.commit()

    # Outside the tx: clean Redis (DB is authoritative; Redis follows).
    pipe = redis.pipeline()
    pipe.delete(f"auth:session:{user_id}:{family_id}")
    pipe.srem(f"auth:user_sessions:{user_id}", str(family_id))
    await pipe.execute()


# ---------------------------------------------------------------------------
# Revoke all sessions — /auth/logout-all (D-10, AUTH-LO-02, AUTH-LO-03)
# ---------------------------------------------------------------------------


async def revoke_all_sessions(
    session: AsyncSession,
    redis: Redis,
    user_id: UUID,
) -> int:
    """Revoke every alive refresh-token family for the user. Return family count.

    Enumerates via SMEMBERS auth:user_sessions:{user_id} (no SCAN — bounded by
    the user's active families, typically 1-3). Postgres is authoritative:
    the UPDATE always runs even if Redis SET is empty (e.g. after a flush).
    """
    # `smembers` is typed `Awaitable[set] | set` (sync/async shared stubs); cast.
    family_ids_raw = await cast(
        "Awaitable[set[str]]",
        redis.smembers(f"auth:user_sessions:{user_id}"),
    )
    family_count = len(family_ids_raw)

    if family_count > 0:
        pipe = redis.pipeline()
        for fid in family_ids_raw:
            pipe.delete(f"auth:session:{user_id}:{fid}")
        pipe.delete(f"auth:user_sessions:{user_id}")
        await pipe.execute()

    # See revoke_session for the rationale: rely on autobegin + explicit commit
    # so this works whether or not the route's dep chain (get_current_user) has
    # already issued a query that started a transaction on this session.
    await session.execute(
        update(RefreshToken)
        .where(
            RefreshToken.user_id == user_id,
            RefreshToken.revoked_at.is_(None),
        )
        .values(revoked_at=datetime.now(tz=UTC))
    )
    # Pitfall 2: emit BEFORE commit so the audit row commits atomically with
    # the bulk revocation UPDATE.
    await audit.emit(
        session,
        "session_revoked_all",
        actor_user_id=user_id,
        resource_type="user",
        resource_id=user_id,
        family_count=family_count,
    )
    await session.commit()

    return family_count


# ---------------------------------------------------------------------------
# list_user_sessions — GET /auth/sessions (Phase 23 HYG-03, D-23-1..D-23-4)
# ---------------------------------------------------------------------------


async def list_user_sessions(
    session: AsyncSession,
    redis: Redis,
    *,
    user_id: UUID,
    page: int,
    page_size: int,
    presented_refresh_token: str | None,
) -> PaginatedData[ActiveSessionItem]:
    """Return the user's active session families as a paginated envelope (D-23-1..D-23-4).

    Sort: is_current=True first, then last_used_at DESC.
    is_current resolved by sha256(presented_refresh_token) → RefreshToken.token_hash lookup.
    Metadata (user_agent, channel) read from Redis; falls back to None/'email_password'
    on cache miss (CD-01 trade-off for pre-Phase-23 sessions).

    Caller-owns-txn: no session.commit() — read-only path.
    """
    now = datetime.now(tz=UTC)

    # Resolve is_current: sha256(sz_refresh) → token_hash → family_id (D-23-3).
    current_family_id: UUID | None = None
    if presented_refresh_token is not None:
        presented_hash = _sha256_hex(presented_refresh_token)
        current_row = await session.scalar(
            select(RefreshToken).where(RefreshToken.token_hash == presented_hash)
        )
        if current_row is not None:
            current_family_id = current_row.family_id

    # Fetch all alive rows for this user (revoked_at IS NULL AND expires_at > now).
    all_rows = (
        await session.scalars(
            select(RefreshToken).where(
                RefreshToken.user_id == user_id,
                RefreshToken.revoked_at.is_(None),
                RefreshToken.expires_at > now,
            )
        )
    ).all()

    # Aggregate by family_id: earliest created_at per family.
    family_map: dict[UUID, datetime] = {}
    for row in all_rows:
        fid = row.family_id
        if fid not in family_map or row.created_at < family_map[fid]:
            family_map[fid] = row.created_at

    # Build items with Redis metadata.
    items: list[ActiveSessionItem] = []
    for fid, created_at in family_map.items():
        raw = await redis.get(f"auth:session:{user_id}:{fid}")
        last_used_at = created_at  # fallback when Redis miss (CD-01)
        ua: str | None = None
        channel: str = "email_password"
        if raw is not None:
            try:
                data = json.loads(raw)
                last_seen_str = data.get("last_seen_at")
                if last_seen_str:
                    last_used_at = datetime.fromisoformat(last_seen_str)
                ua = data.get("user_agent")
                channel = data.get("channel") or "email_password"
            except (json.JSONDecodeError, ValueError):
                pass

        items.append(
            ActiveSessionItem(
                family_id=fid,
                created_at=created_at,
                last_used_at=last_used_at,
                user_agent=ua,
                channel=channel,
                is_current=(fid == current_family_id),
            )
        )

    # Sort: is_current=True first, then last_used_at DESC (D-23-2).
    items.sort(key=lambda it: (not it.is_current, -it.last_used_at.timestamp()))

    total = len(items)
    offset = (page - 1) * page_size
    page_items = items[offset : offset + page_size]

    return PaginatedData[ActiveSessionItem](
        items=page_items,
        total=total,
        page=page,
        page_size=page_size,
    )


# ---------------------------------------------------------------------------
# revoke_family — POST /auth/sessions/{family_id}/revoke (Phase 23 HYG-03, D-23-5..D-23-10)
# ---------------------------------------------------------------------------


async def revoke_family(
    session: AsyncSession,
    redis: Redis,
    *,
    user_id: UUID,
    family_id: UUID,
) -> Literal["revoked", "noop", "not_found"]:
    """Revoke a single session family by family_id (D-23-5..D-23-10).

    Returns:
      'revoked'    — family existed and was alive; revoked + audit emitted.
      'noop'       — family existed but all rows already revoked (idempotent D-23-7).
      'not_found'  — family does not exist OR belongs to another user (404-collapse D-23-6).

    Self-commit: issues session.commit() so the audit row and UPDATE commit atomically,
    same pattern as revoke_session (Pitfall 2).
    """
    now = datetime.now(tz=UTC)

    # Fetch all rows for this family+user (cross-user safety — D-23-6).
    rows = (
        await session.scalars(
            select(RefreshToken).where(
                RefreshToken.family_id == family_id,
                RefreshToken.user_id == user_id,
            )
        )
    ).all()

    if not rows:
        # 404-collapse: covers both "family does not exist" AND "belongs to another user".
        return "not_found"

    # Check if all rows are already revoked.
    alive_rows = [r for r in rows if r.revoked_at is None]
    if not alive_rows:
        # Idempotent noop — all rows already revoked (D-23-7). No audit emit.
        return "noop"

    # Revoke all alive rows in this family.
    await session.execute(
        update(RefreshToken)
        .where(
            RefreshToken.user_id == user_id,
            RefreshToken.family_id == family_id,
            RefreshToken.revoked_at.is_(None),
        )
        .values(revoked_at=now)
    )
    # Pitfall 2: emit BEFORE commit so the audit row commits atomically with the UPDATE.
    await audit.emit(
        session,
        "session_revoked",
        actor_user_id=user_id,
        resource_type="auth_session",
        resource_id=family_id,
    )
    await session.commit()

    # Outside the tx: clean Redis (DB is authoritative; Redis follows).
    pipe = redis.pipeline()
    pipe.delete(f"auth:session:{user_id}:{family_id}")
    pipe.srem(f"auth:user_sessions:{user_id}", str(family_id))
    await pipe.execute()

    return "revoked"
