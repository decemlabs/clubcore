"""Phase 44 RESET-01/02/04 password-reset + invitation-accept service.

Phase 41 INFRA-40 created this module as a 9-line placeholder so the
SVC001 commit-gate walker's target-file existence rule (D-41-28) was
satisfied early. Phase 44 fills the body — request/confirm/accept
services + ``_atomic_consume_token`` helper.

All four functions defined here MUST enforce the single-SQL atomic-consume
invariant on ``password_reset_tokens`` (D-41-04 / D-44-14 / D-44-19) at
the consume point, and service-owns-commit (D-03 / SVC001 walker scope
covers this file per D-41-28) at the transaction boundary.

Wave 1 ships this skeleton — 3 public service coroutine stubs + 1 private
atomic-consume helper, each with a locked signature and ``raise
NotImplementedError`` body. Wave 2 (plans 44-04 / 44-05 / 44-06) fills the
bodies without changing any signature.

Anti-oracle envelope (D-44-06 / D-44-15) and constant-time floor
(D-44-07) live in :func:`request_password_reset`'s body — see Wave 2.
"""

from __future__ import annotations

import asyncio
import hashlib
import secrets
import time
from datetime import UTC, datetime
from typing import Final, Literal
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

import structlog
from redis.asyncio import Redis
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import audit
from app.core.config import get_settings
from app.core.dependencies import get_email_dispatcher, get_user_session_invalidator
from app.core.exceptions import RateLimited
from app.core.models import User
from app.core.security import hash_password
from app.modules.auth import reset_rate_limit
from app.modules.auth.constants import PASSWORD_RESET_TOKEN_TTL
from app.modules.auth.exceptions import (
    InvalidOrExpiredTokenError,
    InvitationAlreadyAcceptedError,
    WeakPasswordError,
)
from app.modules.auth.password_reset_token_model import PasswordResetToken
from app.modules.auth.service import invalidate_all_families_for_user

# NOTE: `INVITATION_TOKEN_TTL` from `app.modules.users.constants` was originally
# listed in plan 44-03's required-imports block but importing it here BREAKS the
# locked import-linter contract "modules cannot import each other"
# (auth ↛ users). Phase 44's accept_invitation consumes an EXISTING
# pending-invitation row that Phase 43 already inserted with the 7-day TTL
# (D-44-20: this function NEVER INSERTs a users row, NEVER re-issues an
# invitation token). The constant is not actually needed at the accept-flow
# callsite. If a future plan adds an "auth-side replacement invitation token"
# path, it should either inline `timedelta(days=7)` locally or move the
# constant to `app.core` (architectural change — Rule 4). Deviation logged
# in 44-03-SUMMARY.md.

__all__ = [
    "accept_invitation",
    "confirm_password_reset",
    "request_password_reset",
]

# Tasks 3 + 4 of plan 44-04 land in subsequent commits; their symbol bindings
# stay imported at module scope per the auth/service.py precedent. This tuple
# anchors them so ruff F401 doesn't strip imports between commits. Removed in
# the final task once every symbol is referenced in an actual call site.
_TASK_3_4_PENDING: Final = (
    get_user_session_invalidator,
    hash_password,
    invalidate_all_families_for_user,
    InvalidOrExpiredTokenError,
    InvitationAlreadyAcceptedError,
    WeakPasswordError,
)

# D-44-11: ops events (rate-limit hits) emit via structlog, NOT audit_log,
# to preserve the anti-oracle public surface while keeping ops visibility.
_log: Final = structlog.get_logger("auth.password_reset_service")

# D-44-07 — 500ms wall-clock floor on every /password-reset/request response
# path (anti-oracle timing parity). Mirrors auth/service.py:_constant_time_floor.
_RESPONSE_FLOOR_SECONDS: Final[float] = 0.5

# Russian-locale datetime formatting (D-44-25 — `expires_at_human` Jinja var).
# Duplicated inline from users/service.py:80-115 because import-linter forbids
# auth ↛ users module imports. ~15-line helper, accepted per the "3-line shared
# util not worth packaging" carve-out documented in 44-CONTEXT § Reusable Assets.
_RU_MONTHS_GENITIVE: Final[tuple[str, ...]] = (
    "января",
    "февраля",
    "марта",
    "апреля",
    "мая",
    "июня",
    "июля",
    "августа",
    "сентября",
    "октября",
    "ноября",
    "декабря",
)

_MOSCOW_TZ: Final[ZoneInfo] = ZoneInfo("Europe/Moscow")


def _format_expires_ru(dt: datetime) -> str:
    """Render a Russian long-form datetime in Europe/Moscow with MSK suffix.

    Duplicated from ``app.modules.users.service._format_expires_ru`` because
    the import-linter contract forbids ``auth -> users``. WR-07 Phase 43 review.
    """
    local = dt.astimezone(_MOSCOW_TZ)
    return (
        f"{local.day} {_RU_MONTHS_GENITIVE[local.month - 1]} {local.year} "
        f"в {local.hour:02d}:{local.minute:02d} (МСК)"  # noqa: RUF001
    )


async def _floor_response_time(started: float) -> None:
    """500ms wall-clock floor for /password-reset/request anti-oracle (D-44-07).

    Awaited on EVERY return path of :func:`request_password_reset` so the
    HTTP latency distribution is identical across the 4 anti-oracle cases
    (active / deactivated / owner / nonexistent) AND the rate-limit-hit
    branch. ``time.perf_counter()`` is monotonic; ``asyncio.sleep(0)`` yields
    if elapsed already exceeds the floor.
    """
    elapsed = time.perf_counter() - started
    remaining = _RESPONSE_FLOOR_SECONDS - elapsed
    if remaining > 0:
        await asyncio.sleep(remaining)


async def _atomic_consume_token(
    session: AsyncSession,
    *,
    raw_token: str,
    purpose: Literal["password_reset", "invitation"],
) -> tuple[UUID, UUID, UUID | None] | None:
    """Single-SQL atomic consume on ``password_reset_tokens`` by ``token_hash``.

    Returns ``(token_id, user_id, audit_correlation_id)`` on success, or
    ``None`` when zero rows match (replay / expired / unknown — anti-oracle:
    all three collapse to ``None`` per D-44-14 / D-44-15 / D-44-19). NO
    commit here; caller commits as part of its UoW per D-03 / SVC001.

    SQL (D-44-14 verbatim; D-44-19 mirror with ``purpose='invitation'``)::

        UPDATE password_reset_tokens
           SET consumed_at = NOW()
         WHERE token_hash = :hash
           AND purpose = :purpose
           AND consumed_at IS NULL
           AND expires_at > NOW()
        RETURNING id, user_id, audit_correlation_id;

    The ``token_hash`` is ``hashlib.sha256(raw_token.encode()).hexdigest()``
    (Phase 43 ``_hash_token`` discipline, duplicated here per the
    "3-line shared util not worth packaging" carve-out in 44-CONTEXT
    § Reusable Assets).
    """
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    stmt = (
        update(PasswordResetToken)
        .where(
            PasswordResetToken.token_hash == token_hash,
            PasswordResetToken.purpose == purpose,
            PasswordResetToken.consumed_at.is_(None),
            PasswordResetToken.expires_at > func.now(),
        )
        .values(consumed_at=func.now())
        .returning(
            PasswordResetToken.id,
            PasswordResetToken.user_id,
            PasswordResetToken.audit_correlation_id,
        )
        .execution_options(synchronize_session=False)
    )
    result = await session.execute(stmt)
    row = result.first()
    if row is None:
        return None
    token_id, user_id, audit_corr_id = row
    return (token_id, user_id, audit_corr_id)


async def request_password_reset(
    session: AsyncSession,
    redis: Redis,
    *,
    email: str,
    client_ip: str,
) -> None:
    """RESET-01 anti-oracle reset-link issuance.

    4-case identical envelope per D-44-06 (active / deactivated / owner /
    nonexistent — all return ``None`` to the caller; the router translates to
    HTTP 202 + ``envelope(None)``). 500ms constant-time floor per D-44-07
    via ``await asyncio.sleep(max(0.0, 0.5 - elapsed))`` immediately before
    returning. 3-key Redis rate-limit (per-IP, per-email-minute,
    per-email-hour) checked BEFORE the user lookup per D-44-10 / D-44-13;
    on hit, short-circuit to the 202 path with a structlog WARN per D-44-11
    (NO 429, NO audit-log row — only ops visibility).

    Audit emit ``password_reset_requested`` fires in BOTH the known-email
    and unknown-email branches per D-44-08; the email enqueue runs ONLY in
    the ``is_active=true AND deleted_at IS NULL`` branch per D-44-09.

    Service owns transaction — terminates with ``await session.commit()``
    so the SVC001 walker (D-41-28) sees a single mutating UoW closed in
    this module.
    """
    started = time.perf_counter()
    email_lower = email.strip().lower()
    audit_correlation_id = uuid4()

    # 3-key rate-limit check BEFORE user lookup (D-44-13). On hit: structlog
    # WARN + 500ms floor + return 202 envelope; NO audit emit, NO bump
    # (D-44-11 — idempotent re-check; the request that pushed the counter
    # past threshold already burned the bump quota).
    try:
        await reset_rate_limit.check_reset_rate_ip(redis, client_ip)
        await reset_rate_limit.check_reset_rate_email_minute(redis, email_lower)
        await reset_rate_limit.check_reset_rate_email_hour(redis, email_lower)
    except RateLimited:
        _log.warning(
            "password_reset.rate_limited",
            ip=client_ip,
            email_lower=email_lower,
            audit_correlation_id=str(audit_correlation_id),
        )
        await _floor_response_time(started)
        return

    # Bump all 3 counters UNCONDITIONALLY (anti-oracle parity — unknown email
    # floods also trip the limit; D-44-10).
    await reset_rate_limit.bump_reset_rate_ip(redis, client_ip)
    await reset_rate_limit.bump_reset_rate_email_minute(redis, email_lower)
    await reset_rate_limit.bump_reset_rate_email_hour(redis, email_lower)

    # User lookup — case-insensitive on lower(email), excluding soft-deleted.
    lookup_stmt = select(User).where(
        func.lower(User.email) == email_lower,
        User.deleted_at.is_(None),
    )
    result = await session.execute(lookup_stmt)
    user = result.scalar_one_or_none()

    if user is not None and user.is_active and user.deleted_at is None:
        # Branch A — known + active + non-deleted: issue token + audit + email.
        raw_token = secrets.token_urlsafe(32)

        # Pre-empt the (user_id, purpose) WHERE consumed_at IS NULL partial-
        # UNIQUE collision by marking any active prior token as consumed.
        await session.execute(
            update(PasswordResetToken)
            .where(
                PasswordResetToken.user_id == user.id,
                PasswordResetToken.purpose == "password_reset",
                PasswordResetToken.consumed_at.is_(None),
            )
            .values(consumed_at=func.now())
        )
        token_row = PasswordResetToken(
            user_id=user.id,
            token_hash=hashlib.sha256(raw_token.encode()).hexdigest(),
            purpose="password_reset",
            expires_at=datetime.now(UTC) + PASSWORD_RESET_TOKEN_TTL,
            audit_correlation_id=audit_correlation_id,
        )
        session.add(token_row)
        await session.flush()  # surface IntegrityError before audit/enqueue.

        await audit.emit(
            session,
            "password_reset_requested",
            actor_user_id=None,
            actor_email_snapshot=None,
            resource_type="user",
            resource_id=user.id,
            audit_correlation_id=str(audit_correlation_id),
            target_user_id=str(user.id),
            email_hint=email_lower,
        )

        # D-44-28 — raw token lives in URL fragment, never path/query (Referer
        # leak mitigation T-44-04-08).
        base = get_settings().frontend_base_url.rstrip("/")
        reset_url = f"{base}/auth/password-reset#token={raw_token}"
        expires_at_human = _format_expires_ru(token_row.expires_at)

        # Enqueue email PRE-COMMIT mirroring Phase 43 users/service.py:230-238.
        # Dispatcher renders subject/html/text from raw template_vars at
        # enqueue time (CR-01 lesson — passing pre-rendered subject/html/text
        # would be silently dropped by Jinja). Literal template_id required
        # by Phase 41 D-41-11 AST gate.
        await get_email_dispatcher()(
            template_id="PASSWORD_RESET_EMAIL",
            to=email_lower,
            audit_correlation_id=audit_correlation_id,
            reset_url=reset_url,
            expires_at_human=expires_at_human,
        )
    elif user is not None:
        # Branch B — known but deactivated or soft-deleted: emit audit only,
        # NO email enqueue (D-44-09). Audit row is forensic-only; HTTP
        # response is identical to Branch A.
        await audit.emit(
            session,
            "password_reset_requested",
            actor_user_id=None,
            actor_email_snapshot=None,
            resource_type="user",
            resource_id=user.id,
            audit_correlation_id=str(audit_correlation_id),
            target_user_id=str(user.id),
            email_hint=email_lower,
        )
    else:
        # Branch C — unknown email: emit audit with target_user_id=None,
        # email_hint=email_lower (D-44-08 dual-branch emit). Anti-oracle
        # parity with Branches A+B at the HTTP envelope layer.
        await audit.emit(
            session,
            "password_reset_requested",
            actor_user_id=None,
            actor_email_snapshot=None,
            resource_type="user",
            resource_id=None,
            audit_correlation_id=str(audit_correlation_id),
            target_user_id=None,
            email_hint=email_lower,
        )

    await session.commit()
    await _floor_response_time(started)


async def confirm_password_reset(
    session: AsyncSession,
    *,
    raw_token: str,
    new_password: str,
) -> None:
    """RESET-02 atomic-consume + password rotate + revoke-all + audit.

    Per D-44-16 the body sequences:

    1. Weak-password predicate (currently ``len(new_password) >= 8`` per
       D-44-17). Failure → raise :class:`WeakPasswordError` (422) BEFORE
       the atomic-consume so the token stays valid for retry within TTL.
    2. ``_atomic_consume_token(session, raw_token=…, purpose="password_reset")``.
       ``None`` return → raise :class:`InvalidOrExpiredTokenError` (410)
       — replay / expired / unknown collapse to the same wire shape per
       D-44-15.
    3. ``users.password_hash = await hash_password(new_password)``
       (Argon2id via :func:`app.core.security.hash_password`).
    4. ``await invalidate_all_families_for_user(session, user_id=resolved,
       actor_user_id=resolved, reason="password_reset")`` — self-reset, so
       actor == target per the D-44-CONTEXT clarification of D-43-26
       Protocol wiring.
    5. ``audit.emit("password_reset_completed", …)`` with flat kwargs per
       the Phase 42 CR-01 discipline (``user_id``, ``sessions_revoked_count``,
       ``token_id``, ``audit_correlation_id`` — :class:`PasswordResetCompletedPayload`
       shape at audit_payloads.py:630-645).
    6. ``await session.commit()`` — service owns the single UoW.

    Returns ``None``. The router translates to HTTP 200 ``envelope(None)``;
    NO new login cookies are issued per D-44-16 step 5 (user must
    re-authenticate via ``/auth/login`` with the new password).
    """
    raise NotImplementedError("Wave 2 plan 44-04 fills this body.")


async def accept_invitation(
    session: AsyncSession,
    *,
    raw_token: str,
    new_password: str,
    full_name: str | None,
) -> tuple[UUID, str, str, str]:
    """RESET-04 invitation-accept atomic-consume + UPDATE-only password set.

    Returns ``(user_id, email, role, full_name)`` for the caller to issue
    session cookies via :func:`app.modules.auth.service.issue_tokens` +
    :func:`app.core.security.issue_session_cookies` (the Phase 5 helpers
    that ``/auth/login`` already uses; D-44-21).

    Per D-44-18 / D-44-19 / D-44-20 / D-44-22 / D-44-23 the body sequences:

    1. Weak-password predicate (same check as ``confirm_password_reset`` —
       D-44-17). Failure → :class:`WeakPasswordError` (422) BEFORE the
       atomic-consume.
    2. ``_atomic_consume_token(session, raw_token=…, purpose="invitation")``.
       ``None`` return → :class:`InvalidOrExpiredTokenError` (410).
    3. Single-SQL UPDATE-only user-row mutation per D-44-20::

           UPDATE users
              SET password_hash = :argon2_hash,
                  status = 'active',
                  email_verified = TRUE,
                  full_name = COALESCE(NULLIF(:new_full_name, ''), full_name)
            WHERE id = :user_id
              AND status = 'pending_invitation'
              AND is_active = TRUE
              AND deleted_at IS NULL
           RETURNING id, email, role, full_name;

       0 rows ⇒ raise :class:`InvitationAlreadyAcceptedError` (409) — the
       target user was concurrently revoked / soft-deleted between the
       token-consume and the user-row UPDATE (millisecond-scale race per
       D-44-20).
    4. ``audit.emit("user_invitation_accepted",
       audit_correlation_id=<from token row>, accepted_user_id=<user_id>,
       invitation_token_id=<token_id>)`` per :class:`UserInvitationAcceptedPayload`.
    5. ``await session.commit()`` — service owns the single UoW.

    D-44-20 invariant: this function NEVER INSERTs a ``users`` row — the
    ``status='pending_invitation'`` row already exists (Phase 43
    ``create_user`` 4-branch idempotent INSERT pre-satisfies the
    soft-deleted-email replay invariant at create-user time per
    D-43-13 / D-41-07). Phase 44's accept-flow operates on the post-state.
    """
    raise NotImplementedError("Wave 2 plan 44-04 fills this body.")
