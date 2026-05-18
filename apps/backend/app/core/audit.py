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

  ## v1.4 (Phase 30 lock — emitted in Phases 31/32/33/34 per INFRA-17 / D-30-02)
  - trainer_created/_updated/_deactivated/_reactivated  → 'trainer'
  - payment_recorded                                    → 'payment'
    {payment_id, subject_kind, subject_id, amount_kopecks, method,
     received_by_user_id, payment_row_hash}
  - refund_issued                                       → 'payment'
  - membership_refunded                                 → 'membership'
  - pt_package_plan_{created,updated,archived}          → 'pt_package_plan'
  - pt_package_{sold,cancelled,refunded,exhausted,expired} → 'pt_package'
  - pt_session_{recorded,cancelled}                     → 'pt_session'

Phase 30 also adds AUDIT_PAYLOAD_SCHEMAS registry (INFRA-23 / D-30-03) which
validates payload kwargs for the 17 new v1.4 events via Pydantic v2 with
`extra="forbid"`. Existing v1.1-v1.3 events keep free-form payload (D-30-02).
NOTE: the logical event count grows 34 → 51 (17 new); the actual frozenset
size grows 36 → 53 because v1.1 has two `session_revoked` variants (one for
`session`, one for `auth_session` per Phase 23 D-23-10).

  ## v1.5 (Phase 37 lock — emitted in Phase 38 per INFRA-24 / C-06)
  - slot_published                      {slot_id, trainer_id, start_time, end_time,
                                         created_by_user_id}                # 'schedule_slot'
  - slot_cancelled                      {slot_id, trainer_id, cancelled_by_user_id,
                                         cancel_reason, had_booking}        # 'schedule_slot'
  - booking_created                     {booking_id, slot_id, client_id,
                                         pt_package_id, created_by_user_id} # 'booking'
  - booking_cancelled                   {booking_id, slot_id,
                                         cancelled_by_user_id, cancel_reason} # 'booking'
  - booking_no_show                     {booking_id, slot_id, client_id,
                                         no_show_at}                        # 'booking' (ARQ)

Phase 37 also extends `PtSessionRecordedPayload` with an optional
`booking_id: UUID | None = None` field (C-06 / D-37-05): completion of a
booking is signalled by the EXISTING `pt_session_recorded` event carrying
the booking reference — there is no separate `booking_completed` event.
The frozenset size grows 53 → 58.

Architectural boundary: app.core.audit MUST NOT import from app.modules.*
(importlinter `core-not-depend-on-modules` contract).
"""

from typing import Any
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit_models import AuditLog
from app.core.audit_payloads import AUDIT_PAYLOAD_SCHEMAS


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
        # v1.4 (Phase 30 lock — emitted in Phases 31/32/33/34 per INFRA-17 / B-03 / D-30-02)
        # Trainers lifecycle (Phase 31 TRN-07):
        ("trainer_created", "trainer"),
        ("trainer_updated", "trainer"),
        ("trainer_deactivated", "trainer"),
        ("trainer_reactivated", "trainer"),
        # Payments + refund (Phase 32 PAY-10 / REF-07):
        ("payment_recorded", "payment"),
        ("refund_issued", "payment"),
        ("membership_refunded", "membership"),
        # PT-package plans (Phase 33 PT-03):
        ("pt_package_plan_created", "pt_package_plan"),
        ("pt_package_plan_updated", "pt_package_plan"),
        ("pt_package_plan_archived", "pt_package_plan"),
        # PT-package instances (Phase 33 PT-13):
        ("pt_package_sold", "pt_package"),
        ("pt_package_cancelled", "pt_package"),
        ("pt_package_refunded", "pt_package"),
        ("pt_package_exhausted", "pt_package"),
        ("pt_package_expired", "pt_package"),
        # PT-sessions (Phase 34 PT-21):
        ("pt_session_recorded", "pt_session"),
        ("pt_session_cancelled", "pt_session"),
        # v1.5 (Phase 37 lock — emitted in Phase 38 per INFRA-24 / C-06)
        # Schedule slot lifecycle (Phase 38 SLOT-01 / SLOT-07 / SLOT-09):
        ("slot_published", "schedule_slot"),
        ("slot_cancelled", "schedule_slot"),
        # Booking lifecycle (Phase 38 BOOK-02 / BOOK-06; Phase 39 CRON-01 for no_show):
        # NOTE: booking_completed is NOT a separate event per C-06 — completion is
        # carried by the existing ("pt_session_recorded", "pt_session") event with
        # an optional booking_id field on PtSessionRecordedPayload.
        ("booking_created", "booking"),
        ("booking_cancelled", "booking"),
        ("booking_no_show", "booking"),
        # v1.6 (Phase 41 lock — emitted in Phases 42/43/44/45 per INFRA-34 / D-41-19)
        # Email transport (Phase 42 EMAIL-01 / EMAIL-04 / EMAIL-06):
        # resource_type is the eventual `email_send_log` table — table itself
        # lands in Phase 42 (migration 0026); pair is pre-registered here per
        # INFRA-34 so the Phase 42 callsite ships green without AST-gate churn.
        ("email_sent", "email_send_log"),
        ("email_send_failed", "email_send_log"),
        # Multi-user admin lifecycle (Phase 43 USERS-03..05 + Phase 44 RESET-03 / RESET-05):
        ("user_invited", "user"),
        ("user_invitation_accepted", "user"),
        ("user_invitation_revoked", "user"),
        ("user_deactivated", "user"),
        ("user_reactivated", "user"),
        ("user_soft_deleted", "user"),
        # Password reset (Phase 44 RESET-01 / RESET-02):
        # `password_reset_requested` is emitted in BOTH known-email and
        # unknown-email branches per the anti-oracle contract (RESET-06);
        # unknown-email branch passes resource_id=None.
        ("password_reset_requested", "user"),
        ("password_reset_completed", "user"),
        # Payment receipt email (Phase 45 NOTIFY-12):
        ("payment_receipt_emailed", "payment"),
    }
)


LOCKED_EMAIL_TEMPLATES: frozenset[str] = frozenset(
    {
        # v1.6 (Phase 41 lock — INFRA-36 / D-41-12; templates landed in Phases 42/44/45)
        # Phase 42 — auth (AUTH-EM-03):
        "EMAIL_OTP_LOGIN",
        # Phase 44 — users + auth (RESET-03 / USERS-03):
        "USER_INVITATION_EMAIL",
        "PASSWORD_RESET_EMAIL",
        # Phase 45 — memberships expiring A/B (NOTIFY-08):
        "EMAIL_EXPIRING_7D_VARIANT_A",
        "EMAIL_EXPIRING_7D_VARIANT_B",
        "EMAIL_EXPIRING_3D_VARIANT_A",
        "EMAIL_EXPIRING_3D_VARIANT_B",
        "EMAIL_EXPIRING_1D_VARIANT_A",
        "EMAIL_EXPIRING_1D_VARIANT_B",
        # Phase 45 — booking lifecycle (NOTIFY-10):
        "EMAIL_BOOKING_CONFIRMED",
        "EMAIL_BOOKING_CANCELLED_BY_CLIENT",
        "EMAIL_BOOKING_CANCELLED_BY_OWNER",
        "EMAIL_BOOKING_REMINDER_24H",
        # Phase 45 — payment receipts (NOTIFY-12):
        "EMAIL_PAYMENT_RECEIPT_SALE",
        "EMAIL_PAYMENT_RECEIPT_REFUND",
    }
)
"""Locked email template identifiers (Phase 41 INFRA-36 / D-41-11 / D-41-12).

Mirrors LOCKED_AUDIT_EVENTS discipline: the runtime frozenset is the source
of truth; the AST gate at tests/unit/test_locked_email_templates_ast.py
asserts every get_email_dispatcher()(template_id=...) callsite passes a
literal name resolving to a member here. Templates physically live next
to their owning module per D-39-02 (e.g. auth/email_templates.py,
bookings/notifications.py); this frozenset only holds the identifiers.

Owner sign-off at VER-14 (Phase 46) enumerates these constant names — the
D-27-OWNER-COPY-LOCK / D-39-02 lineage.
"""


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
        pydantic.ValidationError: when `(event, resource_type)` is in
            AUDIT_PAYLOAD_SCHEMAS (the 17 v1.4 events) AND `payload`
            kwargs do not match the per-event Pydantic schema (extra
            keys, missing required keys, wrong types). Phase 30 D-30-03
            mirrors AuditEventNotLockedError hard-fail discipline — no
            graceful degradation, no DEBUG-only assert.
    """
    if (event, resource_type) not in LOCKED_AUDIT_EVENTS:
        raise AuditEventNotLockedError(
            f"audit.emit({event!r}, resource_type={resource_type!r}) "
            f"is not in LOCKED_AUDIT_EVENTS — extend the frozenset in "
            f"app.core.audit or fix the typo at the callsite."
        )
    # Phase 30 INFRA-23 / D-30-03: validate payload shape against locked schema
    # (only for the 17 v1.4 events; pre-v1.4 events keep free-form payload — D-30-02).
    # pydantic.ValidationError propagates unchanged (D-09 hard-fail discipline,
    # same shape as AuditEventNotLockedError above — no graceful degradation).
    schema = AUDIT_PAYLOAD_SCHEMAS.get((event, resource_type))
    if schema is not None:
        schema.model_validate(payload)
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
