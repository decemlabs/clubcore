"""Audit event emission (D-21 / Phase 8 D-03, D-04 / Phase 15 INFRA-11).

Phase 5 — pure structlog passthrough.
Phase 8 — structlog INFO + co-transactional DB INSERT into `audit_log` (AUDIT-01..03).
Phase 15 — `LOCKED_AUDIT_EVENTS` frozenset is the runtime source of truth; `emit()`
raises `AuditEventNotLockedError` for any `(event, resource_type)` pair NOT in the set.
The static AST walker `tests/unit/test_audit_taxonomy.py` enforces the same invariant
at CI time (catches typos BEFORE runtime).

The function is `async` and takes the caller's `AsyncSession`. It NEVER calls
`session.commit()` or `session.flush()` — the caller owns the transaction
(D-03). The AuditLog row enrolls in whatever transaction `session` is part of
and commits or rolls back atomically with the caller's mutation.

Locked event names (do NOT invent new ones — Phase 8 contract; Phase 15 lifts to
`LOCKED_AUDIT_EVENTS` frozenset below — that is the runtime source of truth):

  ## v1.1 (Phase 5 / 6 / 7 / 8) — see LOCKED_AUDIT_EVENTS for the canonical pairs
  - login_success                       {user_id, email?, ip?, channel}     # 'session'
                                        # channel: 'email_password' | 'telegram' (Phase 7 D-14)
  - login_failed                        {email, reason, ip}                 # 'login_attempt'
  - session_revoked                     {user_id, family_id}                # 'session'
  - session_revoked_all                 {user_id, family_count}             # 'user' (per callsite)
  - family_reuse_detected               {user_id, family_id, hash_prefix}   # 'session'
  - password_changed_revokes_sessions   {user_id, family_count}             # 'user'
  - telegram_deep_link_issued           {deep_link_token_hash}              # 'otp' (Phase 7 D-11)
  - otp_issued                          {user_id, chat_id}                  # 'otp' (Phase 7 D-11)
  - otp_consumed                        {user_id}                           # 'otp' (Phase 7 D-14)
  - telegram_unknown_start              {username, chat_id, hash}           # 'otp' (per callsite)
  - telegram_dm_blocked                 {chat_id}                           # 'otp' (per callsite)
  - telegram_dm_failed                  {chat_id, error}                    # 'otp' (per callsite)
  - telegram_replay_attempt             {deep_link_token_hash}              # 'otp' (Phase 7 D-20)
  - rbac_forbidden                      {role, action, target_resource, path, ip}  # 'rbac'
  - csrf_mismatch                       {path, method, ip, has_cookie, has_header} # 'csrf'
  - client_created                      {client_id, full_name, phone}       # 'client' (Phase 8)
  - client_updated                      {client_id, changed_fields}         # 'client' (Phase 8)
  - client_soft_deleted                 {client_id}                         # 'client' (Phase 8)

  ## v1.2 (Phase 15 lock — emitted in Phases 16/17/19/20)
  - membership_plan_created             {plan_id, name, duration_days, price_kopecks}
  - membership_plan_updated             {plan_id, changed_fields}
  - membership_plan_archived            {plan_id}
  - membership_created                  {membership_id, client_id, plan_id, end_date}
  - membership_cancelled                {membership_id, client_id, reason?}
  - membership_expired                  {membership_id, client_id}                # ARQ daily
  - visit_created          {client_id, membership_id, channel}  [resource_id=visit.id]
  - visit_rejected_no_membership        {client_id, channel}
  - visit_rejected_duplicate            {client_id, gym_date, channel}
  - visit_rejected_outside_hours        {client_id, channel,
                                         current_local_time, gym_open, gym_close}

  ## v1.2 (Phase 20 — bot self check-in unknown-tg)
  - telegram_unknown_checkin            {chat_id, telegram_user_id_hash}
                                        # 'visit' (Phase 20 D-20-10)

  ## v1.3 (Phase 24 lock — emitted in Phases 25/26/27 per INFRA-15 / D-24-18)
  - membership_frozen                   {membership_id, client_id, freeze_days}
                                        # 'membership' (Phase 25 — freeze clock)
  - membership_unfrozen                 {membership_id, client_id, resumed_at}
                                        # 'membership' (Phase 25 — resume frozen)
  - membership_renewed                  {client_id, source_membership_id, source_plan_id,
                                         current_price_kopecks, start_date_strategy}
                                        # 'membership' (Phase 26 — operator-initiated renewal;
                                        # resource_id = new_membership.id; current_price_kopecks
                                        # captures plan price at renewal time, not source snapshot;
                                        # start_date_strategy literal is one of D-26-13 constants)
  - expiring_notification_sent_7d       {client_id, telegram_chat_id, kind, channel}
                                        # 'membership' (Phase 27 — 7-day reminder, ARQ;
                                        # resource_id = membership.id; kind="expiring_7d";
                                        # channel="telegram")
  - expiring_notification_sent_3d       {client_id, telegram_chat_id, kind, channel}
                                        # 'membership' (Phase 27 — 3-day reminder, ARQ;
                                        # resource_id = membership.id; kind="expiring_3d";
                                        # channel="telegram")
  - expiring_notification_sent_1d       {client_id, telegram_chat_id, kind, channel}
                                        # 'membership' (Phase 27 — 1-day reminder, ARQ;
                                        # resource_id = membership.id; kind="expiring_1d";
                                        # channel="telegram")

Architectural boundary: app.core.audit MUST NOT import from app.modules.*
(importlinter `core-not-depend-on-modules` contract).
"""

from typing import Any
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit_models import AuditLog


class AuditEventNotLockedError(ValueError):
    """Raised by audit.emit() when (event, resource_type) ∉ LOCKED_AUDIT_EVENTS.

    Hard fail in dev AND prod (Phase 15 D-09): unknown audit pair = programmer
    error (stale callsite or unlocked taxonomy). NO graceful degradation, NO
    DEBUG-only assert. Tests catch this exception explicitly.
    """


LOCKED_AUDIT_EVENTS: frozenset[tuple[str, str]] = frozenset(
    {
        # v1.1 (Phase 5/6/7/8) — pairs verified against actual callsites in
        # apps/backend/app/**/*.py (NOT just the docstring; planner action item
        # per Phase 15 PATTERNS.md). Drift from the original docstring resolved
        # in favour of the runtime callsite (the actual emitter wins).
        ("login_success", "session"),
        ("login_failed", "login_attempt"),
        ("session_revoked", "session"),
        # Phase 23 D-23-10: per-family revoke endpoint uses 'auth_session' resource_type.
        # Distinct from ("session_revoked", "session") used by /logout flow.
        ("session_revoked", "auth_session"),
        # Drift fix: docstring claimed 'session' but auth/service.py:528 emits 'user'.
        ("session_revoked_all", "user"),
        ("family_reuse_detected", "session"),
        ("password_changed_revokes_sessions", "user"),
        ("telegram_deep_link_issued", "otp"),
        ("otp_issued", "otp"),
        ("otp_consumed", "otp"),
        # Drift fix: docstring claimed 'telegram' but handlers.py:116/160/171 emit 'otp'.
        ("telegram_unknown_start", "otp"),
        ("telegram_dm_blocked", "otp"),
        ("telegram_dm_failed", "otp"),
        ("telegram_replay_attempt", "otp"),
        # Phase 6 callsites (NOT in original docstring; lifted in Phase 15).
        # `rbac_forbidden` was previously emitted with `resource_type=resource.value`
        # (non-literal) — refactored to literal `'rbac'` in Phase 15 (target resource
        # moves to payload kwarg `target_resource`) so the AST literal-only gate
        # passes (Phase 15 D-11).
        ("rbac_forbidden", "rbac"),
        ("csrf_mismatch", "csrf"),
        ("client_created", "client"),
        ("client_updated", "client"),
        ("client_soft_deleted", "client"),
        # v1.2 (Phase 15 lock — emitted in Phases 16/17/19/20)
        ("membership_plan_created", "membership_plan"),
        ("membership_plan_updated", "membership_plan"),
        ("membership_plan_archived", "membership_plan"),
        ("membership_created", "membership"),
        ("membership_cancelled", "membership"),
        ("membership_expired", "membership"),
        ("visit_created", "visit"),
        ("visit_rejected_no_membership", "visit"),
        ("visit_rejected_duplicate", "visit"),
        ("visit_rejected_outside_hours", "visit"),
        # Phase 20 — bot self check-in: stranger /checkin lands here (D-20-10).
        ("telegram_unknown_checkin", "visit"),
        # v1.3 (Phase 24 lock — emitted in Phases 25/26/27)
        ("membership_frozen", "membership"),
        ("membership_unfrozen", "membership"),
        ("membership_renewed", "membership"),
        ("expiring_notification_sent_7d", "membership"),
        ("expiring_notification_sent_3d", "membership"),
        ("expiring_notification_sent_1d", "membership"),
    }
)


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

    Phase 15 INFRA-11: validates `(event, resource_type) ∈ LOCKED_AUDIT_EVENTS`
    BEFORE structlog/DB writes. Hard fail (D-09): raises
    `AuditEventNotLockedError` (a `ValueError` subclass) on any non-locked pair.

    Args:
        session: AsyncSession in an active transaction.
        event: Locked event name (Phase 5 D-21, Phase 7 D-04, Phase 8 D-04,
            Phase 15 INFRA-11). MUST be a literal str at every callsite (the
            AST gate `tests/unit/test_audit_taxonomy.py` enforces this).
        actor_user_id: User performing the action; None for actor-less events
            (login_failed, telegram_unknown_start, telegram_dm_*, etc.) per D-06.
        resource_type: Logical resource category — e.g. 'session', 'client',
            'otp', 'login_attempt', 'user', 'rbac', 'csrf', 'membership',
            'membership_plan', 'visit'. MUST be a literal str at every callsite.
        resource_id: UUID of the resource (D-07). None when the event has no
            UUID identifier (non-UUID identifiers go in payload).
        **payload: Arbitrary JSONB-serialisable kwargs. Per-event shape per D-08.

    Raises:
        AuditEventNotLockedError: when (event, resource_type) ∉ LOCKED_AUDIT_EVENTS
            (typo at the callsite or the taxonomy needs extending — fix one or
            the other; the AST gate also catches this at CI time).
    """
    if (event, resource_type) not in LOCKED_AUDIT_EVENTS:
        raise AuditEventNotLockedError(
            f"audit.emit({event!r}, resource_type={resource_type!r}) "
            f"is not in LOCKED_AUDIT_EVENTS — extend the frozenset in "
            f"app.core.audit or fix the typo at the callsite."
        )
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
