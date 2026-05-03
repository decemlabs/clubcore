"""Audit event emission (D-21 / Phase 8 D-03, D-04).

Phase 5 — pure structlog passthrough.
Phase 8 — structlog INFO + co-transactional DB INSERT into `audit_log` (AUDIT-01..03).

The function is `async` and takes the caller's `AsyncSession`. It NEVER calls
`session.commit()` or `session.flush()` — the caller owns the transaction
(D-03). The AuditLog row enrolls in whatever transaction `session` is part of
and commits or rolls back atomically with the caller's mutation.

Locked event names (do NOT invent new ones — Phase 8 contract):
  - login_success                       {user_id, email?, ip?, channel}
                                        # channel: 'email_password' | 'telegram' (Phase 7 D-14)
  - login_failed                        {email, reason, ip}
  - session_revoked                     {user_id, family_id}
  - session_revoked_all                 {user_id, family_count}
  - family_reuse_detected               {user_id, family_id, presented_token_hash_prefix}
  - password_changed_revokes_sessions   {user_id, family_count}
  - telegram_deep_link_issued           {deep_link_token_hash}                       # Phase 7 D-11
  - otp_issued                          {user_id, chat_id}                            # Phase 7 D-11
  - otp_consumed                        {user_id}                                     # Phase 7 D-14
  - telegram_unknown_start              {username, chat_id, deep_link_token_hash}     # Phase 7 D-04
  - telegram_dm_blocked                 {chat_id}                                     # Phase 7 D-11
  - telegram_dm_failed                  {chat_id, error}                              # Phase 7 D-11
  - telegram_replay_attempt             {deep_link_token_hash}                        # Phase 7 D-20
  - client_created                      {client_id, full_name, phone}                 # Phase 8 D-04
  - client_updated                      {client_id, changed_fields}                   # Phase 8 D-04
  - client_soft_deleted                 {client_id}                                   # Phase 8 D-04

Architectural boundary: app.core.audit MUST NOT import from app.modules.*
(importlinter `core-not-depend-on-modules` contract).
"""

from typing import Any
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit_models import AuditLog


async def emit(
    session: AsyncSession,
    event: str,
    *,
    actor_user_id: UUID | None,
    resource_type: str,
    resource_id: UUID | None = None,
    **payload: Any,
) -> None:
    """Emit an audit event: structlog INFO + co-transactional DB INSERT (D-04).

    The caller owns the surrounding transaction (D-03) — this function NEVER
    calls session.commit() or session.flush(). The AuditLog row is part of
    whatever transaction `session` is enrolled in; it commits or rolls back
    atomically with the caller's mutation.

    Args:
        session: AsyncSession in an active transaction.
        event: Locked event name (Phase 5 D-21, Phase 7 D-04, Phase 8 D-04).
        actor_user_id: User performing the action; None for actor-less events
            (login_failed, telegram_unknown_start, telegram_dm_*, etc.) per D-06.
        resource_type: Logical resource category — e.g. 'session', 'client',
            'otp', 'login_attempt', 'user'. Per D-04 mapping table.
        resource_id: UUID of the resource (D-07). None when the event has no
            UUID identifier (non-UUID identifiers go in payload).
        **payload: Arbitrary JSONB-serialisable kwargs. Per-event shape per D-08.

    Locked event names (UPDATED for Phase 8 — see D-04 mapping table):
        login_success, login_failed, session_revoked, session_revoked_all,
        family_reuse_detected, password_changed_revokes_sessions,
        telegram_deep_link_issued, otp_issued, otp_consumed,
        telegram_unknown_start, telegram_dm_blocked, telegram_dm_failed,
        telegram_replay_attempt, client_created, client_updated,
        client_soft_deleted.
    """
    structlog.get_logger("audit").info(event, **payload)
    session.add(
        AuditLog(
            action=event,
            actor_user_id=actor_user_id,
            resource_type=resource_type,
            resource_id=resource_id,
            payload=payload,
        )
    )
