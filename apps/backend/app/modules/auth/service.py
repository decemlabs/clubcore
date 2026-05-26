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

import asyncio
import hashlib
import json
import time
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Final, Literal, cast
from uuid import UUID, uuid4

import structlog
from redis.asyncio import Redis
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import audit
from app.core.config import get_settings
from app.core.dependencies import get_email_dispatcher
from app.core.exceptions import InvalidAccessToken, InvalidPassword, InvalidSession
from app.core.pagination import PaginatedData
from app.core.security import (
    encode_access_token,
    generate_csrf_token,
    generate_otp_code,
    generate_refresh_token,
    hash_password,
    verify_password,
)
from app.modules.auth.models import OtpCode, RefreshToken, User
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

    # Phase 43 D-43-06 follow-up — explicit ``password_hash IS NOT NULL`` filter:
    # since Phase 43 migration 0030 dropped users.password_hash NOT NULL, the
    # ORM column is now ``Mapped[str | None]``. Pending_invitation users carry
    # ``password_hash=NULL`` and would otherwise leak to verify_password as a
    # None argument (Phase 12.1 lesson — verify by-types vs verify on-the-wire
    # MUST be aligned via SQL predicate, not Python branch). The IS NOT NULL
    # filter folds pending users into the same anti-oracle bucket as unknown
    # emails: both miss → sentinel-hash branch → InvalidPassword. The explicit
    # ``user.password_hash is not None`` Python re-check below carries the
    # invariant for mypy (which cannot follow SQL predicate narrowing).
    #
    # Phase 43 CR-03 (review) — D-43-20 added is_active + deleted_at predicates
    # to rotate_refresh but missed the LOGIN chokepoint. Without these filters,
    # a soft-deleted owner or deactivated operator can present their original
    # credentials and mint a fresh session, contradicting USERS-04/05 revoke
    # semantics. Mirror the rotate_refresh predicate set so deactivated /
    # soft-deleted users fall into the same anti-oracle bucket as unknown
    # emails — same audit shape (reason='invalid_credentials'), same timing.
    user = await session.scalar(
        select(User).where(
            User.email == email_lower,
            User.password_hash.is_not(None),
            User.is_active.is_(True),
            User.deleted_at.is_(None),
        )
    )
    target_hash: str
    if user is not None and user.password_hash is not None:
        target_hash = user.password_hash
    else:
        # Either no row (unknown email / pending_invitation filtered out) OR
        # — defence-in-depth — a row whose SQL-side IS NOT NULL filter raced
        # against a concurrent UPDATE...SET password_hash=NULL (Phase 12.1
        # by-types/on-the-wire alignment). Both paths fall to the sentinel
        # hash so wall-clock latency matches the success path (D-28).
        target_hash = await _get_sentinel_hash()

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
        select(RefreshToken).where(RefreshToken.token_hash == presented_hash).with_for_update()
    )

    if row is None:
        # Phase 43 D-43-20 — anti-oracle harmonisation. The truly-missing
        # refresh row and the deactivated-account branch below MUST surface
        # byte-identical 401 ``invalid_session`` bodies so the dashboard /
        # response cannot enumerate "token unknown" vs "account inactive".
        # Pre-Phase-43 this raised ``InvalidAccessToken("refresh_not_found")``
        # (code='invalid_token'); harmonised to ``InvalidSession`` so plan
        # 43-12's bounded-timing+identical-body test can assert parity across
        # (active, deactivated, deleted, missing) refresh-token cases.
        raise InvalidSession("invalid_session")

    # ---- Branch (A): ACTIVE — rotate ------------------------------------
    if row.revoked_at is None and row.replaced_by_id is None and row.expires_at > now:
        # Phase 43 D-43-20 — USERS-06 anti-oracle refresh chokepoint.
        # Single SELECT race-tight against parallel deactivate / soft-delete
        # (Pitfall 5 case 3). Predicate filtered IN the SQL — NOT a post-fetch
        # Python branch (which would race against UPDATE...SET is_active=false).
        user_loaded = await session.scalar(
            select(User).where(
                User.id == row.user_id,
                User.is_active.is_(True),
                User.deleted_at.is_(None),
            )
        )
        if user_loaded is None:
            # Anti-oracle: same 401 invalid_session response shape as the
            # truly-missing refresh-row branch above (D-20-9 lineage, D-43-20).
            # Audit emit is forensic-only — reason='account_inactive' lets
            # ops dashboards distinguish a deactivated/soft-deleted operator
            # from a generic invalid-session at the audit-log layer, while
            # the response body stays identical so the caller cannot enumerate.
            # emit → commit → raise ordering (Pitfall 2): commit BEFORE raise
            # so the audit row persists; otherwise InvalidSession propagation
            # would roll back the audit insert via the get_db dep cleanup.
            await audit.emit(
                session,
                "refresh_failed",
                actor_user_id=None,
                resource_type="session",
                resource_id=None,
                audit_correlation_id=None,
                # UUID → str at the JSONB boundary (same pattern as
                # invalidate_all_families_for_user line 1134 + the audit
                # convention in app/integrations/email/dispatcher.py). asyncpg's
                # default JSONB serializer raises TypeError on raw UUID — caught
                # by plan 43-12's anti-oracle integration test (Rule 1 fix).
                user_id=str(row.user_id),
                reason="account_inactive",
            )
            await session.commit()
            raise InvalidSession("invalid_session")

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
# Revoke all sessions — composable atomic UoW + thin commit wrapper.
# ---------------------------------------------------------------------------
#
# CR-04 (Phase 43 review) — splitting the implementation into a no-commit
# helper lets users/service.deactivate_user and soft_delete_user compose the
# revocation into their own atomic UoW. The thin wrapper preserves the
# previous "I am my own UoW" semantics for password_changed_revokes_sessions
# and the standalone /auth/logout-all endpoint.
#
# WR-04 (Phase 43 review) — family_count is now read from the DB UPDATE's
# RETURNING DISTINCT family_id set rather than Redis SMEMBERS, which can
# drift below DB truth (TTL expiry, flush, replica lag).
#
# WR-01 (Phase 43 review) — actor_user_id distinguishes the initiator from
# the target. ``user_id`` stays in ``resource_id`` (the entity being acted
# upon); ``actor_user_id`` is the audit row's ``actor_user_id`` column.


async def _revoke_all_sessions_no_commit(  # noqa: SVC001 caller-owns-txn
    session: AsyncSession,
    redis: Redis,
    user_id: UUID,
    *,
    actor_user_id: UUID | None,
) -> int:
    """Revoke every alive refresh-token family for user_id. NO session.commit().

    Composable UoW variant (CR-04). Returns the count of DISTINCT families
    revoked, sourced from the DB UPDATE's RETURNING set (WR-04 — DB-authoritative).

    The caller is responsible for the commit. The audit row is emitted here
    so it commits atomically with the bulk revocation UPDATE — Pitfall 2 emit
    ordering preserved.
    """
    # Best-effort Redis cleanup — bounded by the user's active families.
    # `smembers` is typed `Awaitable[set] | set` (sync/async shared stubs); cast.
    family_ids_raw = await cast(
        "Awaitable[set[str]]",
        redis.smembers(f"auth:user_sessions:{user_id}"),
    )
    if family_ids_raw:
        pipe = redis.pipeline()
        for fid in family_ids_raw:
            pipe.delete(f"auth:session:{user_id}:{fid}")
        pipe.delete(f"auth:user_sessions:{user_id}")
        await pipe.execute()

    # DB UPDATE with RETURNING distinct family_id — the DB-authoritative count.
    # WR-04: Redis SMEMBERS can drift below DB truth. The UPDATE applies to
    # every alive refresh_tokens row regardless of Redis state, so the
    # RETURNING set is the ground truth for "how many families were just killed".
    result = await session.execute(
        update(RefreshToken)
        .where(
            RefreshToken.user_id == user_id,
            RefreshToken.revoked_at.is_(None),
        )
        .values(revoked_at=datetime.now(tz=UTC))
        .returning(RefreshToken.family_id)
    )
    family_ids_revoked: set[UUID] = {row.family_id for row in result}
    family_count = len(family_ids_revoked)

    # Pitfall 2: emit BEFORE caller's commit so the audit row commits
    # atomically with the bulk revocation UPDATE (single UoW).
    # WR-01: actor_user_id is the initiator (owner), user_id is the target
    # (still surfaced via resource_id).
    await audit.emit(
        session,
        "session_revoked_all",
        actor_user_id=actor_user_id,
        resource_type="user",
        resource_id=user_id,
        family_count=family_count,
    )

    return family_count


async def revoke_all_sessions(
    session: AsyncSession,
    redis: Redis,
    user_id: UUID,
) -> int:
    """Revoke every alive refresh-token family for the user. Owns its own commit.

    Public API preserved for callers that own their UoW boundary
    (``password_changed_revokes_sessions``, ``POST /auth/logout-all``).
    Internally delegates to ``_revoke_all_sessions_no_commit`` and adds a
    ``session.commit()``.

    Note on actor attribution: this entry point treats the user_id as BOTH
    the target AND the actor — appropriate for "/auth/logout-all" (the user
    is logging themselves out) and "password_changed_revokes_sessions" (the
    user just changed their own password). For initiator != target cases
    (owner deactivates reception), users/service uses the no-commit variant
    directly with the owner's id as ``actor_user_id``.
    """
    family_count = await _revoke_all_sessions_no_commit(
        session,
        redis,
        user_id,
        actor_user_id=user_id,
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


# ---------------------------------------------------------------------------
# Phase 42 — Unified OTP request entry points (D-42-22 / AUTH-EM-02 / AUTH-EM-03).
# ---------------------------------------------------------------------------

# Constant-time floor: matches the populated-branch median; test tolerance 100ms
# (plan 42-11 anti-oracle integration suite).
_EMAIL_OTP_FLOOR_MS: Final[int] = 200

# LOCKED placeholder for OtpCode.deep_link_token_hash on email-channel inserts.
# Rationale: apps/backend/app/modules/auth/models.py:109-113 declares the
# column ``nullable=False`` AND ``unique=True``. An empty-string ``""``
# placeholder collides on the SECOND email-channel insert via the unique
# constraint. The ``email-channel:`` prefix is non-overlapping with real
# deep-link sha256 hex hashes (which are exactly 64 lowercase-hex chars per
# ``telegram_service.py:_sha256_hex``); the placeholder is 78 chars and
# contains a colon, so a reader can grep
# ``deep_link_token_hash LIKE 'email-channel:%'`` to count email-channel rows.
_EMAIL_DEEP_LINK_PLACEHOLDER_PREFIX: Final[str] = "email-channel:"


async def _constant_time_floor(t_start: float) -> None:
    """Sleep just long enough to pad ``request_otp_email`` to the floor.

    Anti-oracle uniformity (D-42-22 / RESET-06 lineage): all branches
    (eligible / unknown-email / unverified / inactive / cooldown) converge
    on this floor so wall-clock duration cannot be used as an oracle for
    "did the email belong to a known verified user?".
    """
    elapsed_ms = (time.perf_counter() - t_start) * 1000
    remaining_ms = _EMAIL_OTP_FLOOR_MS - elapsed_ms
    if remaining_ms > 0:
        await asyncio.sleep(remaining_ms / 1000)


async def request_otp_email(
    session: AsyncSession,
    redis: Redis,
    email: str,
    *,
    ip: str | None = None,
) -> None:
    """POST /auth/otp/request {channel:'email'} entry (D-42-22 + AUTH-EM-02 + AUTH-EM-03).

    Anti-oracle invariant (D-42-22 / RESET-06 lineage / PITFALLS 1):
    user_unknown / email_verified=False / inactive ALL return None with
    bounded wall-clock matching the populated branch median (<=100ms
    tolerance per plan 42-11 anti-oracle integration suite).

    Per D-42-22:
      - TTL = 600s (10 min, Telegram x 2 per FEATURES SLO).
      - 60s resend cooldown enforced at otp_codes row level; cooldown-hit
        returns the same shape as success/silent-drop.
      - Second request for same (user_id, channel='email') invalidates the
        first via atomic UPDATE-to-consumed + INSERT-new in same UoW
        (RFC 6238 single-active per channel).
      - OtpCode.deep_link_token_hash uses LOCKED placeholder
        ``email-channel:{uuid4().hex}`` because the column is
        ``nullable=False + unique=True`` (verified-real-file).

    Per D-42-27 / INFRA-36: the ``get_email_dispatcher()(template_id=...)``
    callsite below is the FIRST real LOCKED_EMAIL_TEMPLATES consumer. The
    literal ``"EMAIL_OTP_LOGIN"`` is enforced by the Phase 41 AST gate at
    ``tests/unit/test_locked_email_templates_ast.py`` — do NOT replace
    with a module constant; the walker only accepts ``ast.Constant(str)``.

    ``redis`` and ``ip`` are accepted for signature parity with future
    request-rate enforcement (AUTH-EM-02 rate-limit clauses 5/15min IP +
    1/min email — wired in a downstream Wave-3 follow-up; the 60s row-level
    cooldown here is the in-Phase-42 mitigation).
    """
    t_start = time.perf_counter()
    email_lower = email.lower()
    audit_correlation_id = uuid4()  # D-42-35 chain seed
    now = datetime.now(tz=UTC)

    # Phase 43 CR-03 (review) — tighten the eligibility predicate set to use
    # explicit SQL filters. The previous code used a defensive getattr read for
    # is_active because the column was added mid-Phase; now that Phase 43 has landed
    # is_active on the User ORM, defensive Python reads are obsolete.
    # The deactivated / soft-deleted case is folded into the unknown-email
    # silent-drop bucket (anti-oracle: same wall-clock floor, same None return).
    user = await session.scalar(
        select(User).where(
            User.email == email_lower,
            User.is_active.is_(True),
            User.deleted_at.is_(None),
        )
    )

    # Three-way eligibility guard (D-42-22). All non-eligibility branches
    # (unknown-email / deactivated / soft-deleted / unverified-email) fall
    # through to the constant-time floor + None return — anti-oracle uniformity.
    # is_active and deleted_at are now filtered at the SQL layer (CR-03), so any
    # user object returned is by definition active+alive.
    is_eligible = user is not None and user.email_verified is True

    if is_eligible:
        assert user is not None  # narrowed by is_eligible
        # 60s cooldown silent-drop -- same response shape as success/silent.
        cooldown_row = await session.scalar(
            select(OtpCode)
            .where(
                OtpCode.user_id == user.id,
                OtpCode.channel == "email",
                OtpCode.consumed_at.is_(None),
            )
            .order_by(OtpCode.created_at.desc())
        )
        if cooldown_row is not None and cooldown_row.created_at > now - timedelta(seconds=60):
            await _constant_time_floor(t_start)
            return

        # Atomic single-active: consume prior + INSERT new in same UoW
        # (RFC 6238 / D-42-22). The partial UNIQUE
        # ``uq_otp_codes_user_channel_active`` (plan 42-03 / models.py:137-143)
        # is the DB-level floor; the app-level UPDATE+INSERT is the optimistic
        # happy path that flushes cleanly.
        await session.execute(
            update(OtpCode)
            .where(
                OtpCode.user_id == user.id,
                OtpCode.channel == "email",
                OtpCode.consumed_at.is_(None),
            )
            .values(consumed_at=now)
        )

        raw_code, code_hash = generate_otp_code()

        # LOCKED unique placeholder -- deep_link_token_hash is
        # nullable=False + unique=True. The ``email-channel:`` prefix is
        # non-overlapping with real deep-link sha256 hex (64 lowercase-hex
        # chars); this placeholder is 78 chars and contains a colon.
        placeholder_token_hash = f"{_EMAIL_DEEP_LINK_PLACEHOLDER_PREFIX}{uuid4().hex}"

        otp_row = OtpCode(
            user_id=user.id,
            channel="email",
            deep_link_token_hash=placeholder_token_hash,
            code_hash=code_hash,
            telegram_chat_id=None,
            expires_at=now + timedelta(seconds=600),  # D-42-22 -- 10 min TTL
            attempts=0,
            consumed_at=None,
        )
        session.add(otp_row)

        # Pitfall 2: audit.emit BEFORE commit (PATTERNS.md §A).
        # Piggyback on the existing ``otp_requested`` audit event per
        # D-42-35 -- no new event name; the channel='email' kwarg + the
        # audit_correlation_id correlate the row with the eventual
        # email_sent / email_send_failed row downstream.
        #
        # audit_correlation_id is stringified at the audit boundary because
        # AuditLog.payload is a JSONB column with no UUID-aware serializer
        # (the convention is mirrored in app.integrations.email.dispatcher
        # at the ARQ enqueue boundary — UUID → str at every JSON boundary).
        await audit.emit(
            session,
            "otp_requested",
            actor_user_id=user.id,
            resource_type="otp",
            audit_correlation_id=str(audit_correlation_id),
            channel="email",
        )
        await session.commit()

        # AST-gated callsite — first real LOCKED_EMAIL_TEMPLATES exercise
        # (D-42-27 / INFRA-36). template_id MUST be a literal string —
        # the walker only accepts ast.Constant(str).
        # Pass the lowercased input (not user.email's stored case) so
        # EmailSendLog.to_address is case-consistent with the
        # ix_email_send_log_to_addr_recorded forensic index (WR-03).
        await get_email_dispatcher()(
            template_id="EMAIL_OTP_LOGIN",
            to=email_lower,  # WR-03 -- lowercased boundary for forensic index consistency.
            audit_correlation_id=audit_correlation_id,
            otp_code=raw_code,
        )

    # Both branches converge on the constant-time floor.
    await _constant_time_floor(t_start)


async def request_otp_telegram(
    session: AsyncSession,
    redis: Redis,
    *,
    ip: str | None = None,
) -> None:
    """POST /auth/otp/request {channel:'telegram'} entry (D-42-22 backwards-compat).

    Thin facade that delegates to :func:`telegram_service.start_deep_link`
    to mint an OtpCode placeholder + emit ``telegram_deep_link_issued`` --
    the canonical Telegram OTP entry today. The returned
    ``(raw_token, hash)`` tuple is DISCARDED because the unified
    ``/auth/otp/request`` endpoint returns the anti-oracle envelope (
    ``data: null``), NOT a deep-link URL. Clients that need the deep-link
    continue to call POST ``/auth/telegram/start`` directly -- that route is
    untouched.

    ``redis`` and ``ip`` are accepted for signature parity with
    :func:`request_otp_email` so the router can call either branch with the
    same arg shape (D-42-22 anti-oracle uniformity).

    Per CR-02 fix: ``_constant_time_floor`` is now applied in a try/finally
    wrapper so the Telegram-default path matches the email path's
    anti-oracle latency distribution -- enforces the D-42-22 uniformity
    invariant across BOTH channels of /auth/otp/request.
    """
    t_start = time.perf_counter()
    # Local import keeps the top-of-file clean. ``telegram_service`` is a
    # sibling module already loaded by the router.
    from app.modules.auth import telegram_service

    # The returned (raw_token, hash) is intentionally discarded -- the
    # unified /otp/request route returns the anti-oracle envelope, not the
    # deep-link. Cross-arg references silence the unused-arg lint.
    _ = redis
    _ = ip
    try:
        _raw_token, _token_hash = await telegram_service.start_deep_link(session)
    finally:
        # Anti-oracle floor MUST run even on exception -- unprotected
        # exception propagation also leaks timing (CR-02).
        await _constant_time_floor(t_start)


# ---------------------------------------------------------------------------
# Phase 43 D-43-26/27 — UserSessionInvalidator Protocol implementation.
# ---------------------------------------------------------------------------
#
# Wraps revoke_all_sessions(session, redis, user_id) to match the Protocol
# signature declared in app/core/dependencies.py:UserSessionInvalidator. The
# Redis client is supplied via _redis_factory which app/main.py:create_app()
# sets at composition time (single-wire — NO worker registration per D-43-27).
#
# `reason` is logged via structlog but NOT placed in the audit emit — calling
# sites (users/service.py:deactivate_user, etc.) emit their own audit event
# carrying sessions_revoked_count per D-43-28.


_redis_factory: Callable[[], Redis] | None = None


def set_redis_factory(factory: Callable[[], Redis]) -> None:
    """Phase 43 D-43-26 composition-root injection of the Redis client factory.

    Called once from app/main.py:create_app(). Idempotent — last call wins.
    The factory is invoked lazily on each call to
    invalidate_all_families_for_user so it can read app.state.redis after
    the lifespan has populated it (the FastAPI lifespan sets app.state.redis
    AFTER create_app() returns, so the factory closes over the FastAPI app
    rather than over a Redis client directly).
    """
    global _redis_factory
    _redis_factory = factory


async def invalidate_all_families_for_user(
    session: AsyncSession,
    *,
    user_id: UUID,
    actor_user_id: UUID | None,
    reason: Literal["deactivated", "password_reset", "soft_deleted"],
) -> int:
    """Phase 41 D-41-25 UserSessionInvalidator Protocol implementation.

    Returns the number of refresh-token families revoked. Reason is logged
    (structlog) but is NOT in the audit emit — calling sites emit their own
    domain event (user_deactivated / password_reset_completed /
    user_soft_deleted) carrying sessions_revoked_count per D-43-28.

    CR-04 (Phase 43 review) — calls the no-commit variant so the caller
    (users/service.deactivate_user, soft_delete_user) owns the single
    transactional boundary. The pre-fix code's mid-flow commit broke the
    audit + mutation atomicity contract.

    WR-01 (Phase 43 review) — actor_user_id is plumbed into the
    session_revoked_all audit row as the actor, distinguishing the owner
    initiator from the target.
    """
    if _redis_factory is None:
        raise RuntimeError(
            "invalidate_all_families_for_user called before "
            "auth.service.set_redis_factory(...) was wired in create_app(). "
            "Phase 43 D-43-26 composition discipline."
        )
    redis = _redis_factory()
    _log.info(
        "user_session_invalidator.invoked",
        user_id=str(user_id),
        actor_user_id=str(actor_user_id) if actor_user_id else None,
        reason=reason,
    )
    return await _revoke_all_sessions_no_commit(
        session,
        redis,
        user_id,
        actor_user_id=actor_user_id,
    )
