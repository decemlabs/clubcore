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
from datetime import datetime, timedelta, timezone
from typing import Final, Literal
from uuid import UUID, uuid4

import structlog
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import audit
from app.core.config import get_settings
from app.core.dependencies import get_email_dispatcher, get_user_session_invalidator
from app.core.security import hash_password
from app.integrations.email.types import EmailEnvelope
from app.modules.auth import reset_rate_limit
from app.modules.auth.constants import PASSWORD_RESET_TOKEN_TTL
from app.modules.auth.email_templates import TEMPLATES
from app.modules.auth.exceptions import (
    InvalidOrExpiredTokenError,
    InvitationAlreadyAcceptedError,
    WeakPasswordError,
)
from app.modules.auth.password_reset_token_model import PasswordResetToken
from app.modules.auth.service import invalidate_all_families_for_user, issue_tokens

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

# Wave 2 will reference these in body — declared here so import-linter sees
# the wire shape compile cleanly and ruff doesn't strip them as unused at the
# skeleton stage.
__all__ = [
    "accept_invitation",
    "confirm_password_reset",
    "request_password_reset",
]

# D-44-11: ops events (rate-limit hits) emit via structlog, NOT audit_log,
# to preserve the anti-oracle public surface while keeping ops visibility.
_log: Final = structlog.get_logger("auth.password_reset_service")

# Re-export stdlib + symbol bindings the bodies will pick up (Wave 2). Keeping
# them at module scope avoids the ruff F401 "imported but unused" complaint
# on the skeleton commit. Each symbol below is a stable callsite Wave 2 uses.
_UNUSED_AT_SKELETON: Final = (
    asyncio,
    hashlib,
    secrets,
    time,
    datetime,
    timedelta,
    timezone,
    uuid4,
    audit,
    get_settings,
    get_email_dispatcher,
    get_user_session_invalidator,
    hash_password,
    EmailEnvelope,
    reset_rate_limit,
    PASSWORD_RESET_TOKEN_TTL,
    TEMPLATES,
    PasswordResetToken,
    invalidate_all_families_for_user,
    issue_tokens,
    InvalidOrExpiredTokenError,
    InvitationAlreadyAcceptedError,
    WeakPasswordError,
)


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
    raise NotImplementedError("Wave 2 plan 44-04 fills this body.")


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
    raise NotImplementedError("Wave 2 plan 44-04 fills this body.")


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
