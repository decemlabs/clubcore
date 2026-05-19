"""Audit payload schemas (INFRA-23 / Phase 30 / D-30-03).

Strict Pydantic-v2 BaseModel per audit event for the 17 new v1.4 events.
`audit.emit()` looks up `(event, resource_type)` in `AUDIT_PAYLOAD_SCHEMAS`
and calls `Schema.model_validate(payload_kwargs)` BEFORE structlog/DB writes.
Mirrors the D-09 hard-fail discipline of `AuditEventNotLockedError`:
unknown payload key OR missing required key → pydantic.ValidationError
(programmer error, not graceful degradation).

Scope (D-30-02): ONLY v1.4 events are locked. The 34 existing v1.1-v1.3
logical events remain free-form (back-compat); `audit.emit()` validates
payload only when `(event, resource_type)` is present in this registry.

Pydantic base-class divergence (rationale):
    Audit payloads are internal kwargs (snake_case Python identifiers),
    NOT camelCase wire DTOs. Therefore each schema inherits plain
    `pydantic.BaseModel` with `model_config = ConfigDict(extra="forbid")` —
    NOT `app.core.schemas.BackendSchemaBase` (which auto-aliases via
    `to_camel`). The `extra="forbid"` is the load-bearing invariant
    per D-30-01.

`payment_row_hash` (D-30-04): SHA-256 of canonical-JSON of the original
payment row, prefixed with `sha256:`. Canonicalization algorithm is
pencilled in for Phase 32 / Plan 03 (helper module `app.core.audit_hash`
exposes `payment_row_hash(row: dict) -> str` returning
`"sha256:<64-hex>"`). Field pattern constraint `^sha256:[0-9a-f]{64}$`
is locked here.

Architectural boundary: app.core.audit_payloads MUST NOT import from
app.modules.* (importlinter `core-not-depend-on-modules` contract).
"""

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Trainers lifecycle (Phase 31 TRN-07)
# ---------------------------------------------------------------------------


class TrainerCreatedPayload(BaseModel):
    """Payload schema for ("trainer_created", "trainer") — TRN-07."""

    model_config = ConfigDict(extra="forbid")

    trainer_id: UUID
    full_name: str
    phone: str | None


class TrainerUpdatedPayload(BaseModel):
    """Payload schema for ("trainer_updated", "trainer") — TRN-07."""

    model_config = ConfigDict(extra="forbid")

    trainer_id: UUID
    changed_fields: list[str]


class TrainerDeactivatedPayload(BaseModel):
    """Payload schema for ("trainer_deactivated", "trainer") — TRN-07."""

    model_config = ConfigDict(extra="forbid")

    trainer_id: UUID


class TrainerReactivatedPayload(BaseModel):
    """Payload schema for ("trainer_reactivated", "trainer") — TRN-07."""

    model_config = ConfigDict(extra="forbid")

    trainer_id: UUID


# ---------------------------------------------------------------------------
# Payments + refund + membership refund (Phase 32 PAY-10 / REF-07)
# ---------------------------------------------------------------------------


class PaymentRecordedPayload(BaseModel):
    """Payload schema for ("payment_recorded", "payment") — PAY-10.

    Verbatim per REQUIREMENTS.md §PAY-10:
        {payment_id, subject_kind, subject_id, amount_kopecks, method,
         received_by_user_id, payment_row_hash}.

    `payment_row_hash` (D-30-04): SHA-256 canonical-JSON of the payment row,
    prefixed `sha256:` — pattern `^sha256:[0-9a-f]{64}$`.
    """

    model_config = ConfigDict(extra="forbid")

    payment_id: UUID
    subject_kind: str = Field(pattern=r"^(membership|pt_package|refund)$")
    subject_id: UUID
    amount_kopecks: int
    method: str
    received_by_user_id: UUID
    # D-30-04: SHA-256 of canonical-JSON of the original payment row.
    payment_row_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class RefundIssuedPayload(BaseModel):
    """Payload schema for ("refund_issued", "payment") — REF-07.

    `amount_kopecks` is negative (refund row in append-only payments ledger).
    `payment_row_hash` (D-30-04): SHA-256 of canonical-JSON of the ORIGINAL
    payment row being refunded — forensic chain-of-custody.
    """

    model_config = ConfigDict(extra="forbid")

    payment_id: UUID
    refund_of_payment_id: UUID
    amount_kopecks: int
    subject_kind: str = Field(pattern=r"^(membership|pt_package)$")
    subject_id: UUID
    received_by_user_id: UUID
    reason: str
    # D-30-04: SHA-256 of canonical-JSON of the ORIGINAL refunded payment row.
    payment_row_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class MembershipRefundedPayload(BaseModel):
    """Payload schema for ("membership_refunded", "membership") — REF-07."""

    model_config = ConfigDict(extra="forbid")

    membership_id: UUID
    client_id: UUID
    refund_payment_id: UUID
    reason: str


# ---------------------------------------------------------------------------
# PT-package plans lifecycle (Phase 33 PT-03)
# ---------------------------------------------------------------------------


class PtPackagePlanCreatedPayload(BaseModel):
    """Payload schema for ("pt_package_plan_created", "pt_package_plan") — PT-03."""

    model_config = ConfigDict(extra="forbid")

    plan_id: UUID
    name: str
    session_count: int
    price_kopecks: int
    validity_days: int | None


class PtPackagePlanUpdatedPayload(BaseModel):
    """Payload schema for ("pt_package_plan_updated", "pt_package_plan") — PT-03."""

    model_config = ConfigDict(extra="forbid")

    plan_id: UUID
    changed_fields: list[str]


class PtPackagePlanArchivedPayload(BaseModel):
    """Payload schema for ("pt_package_plan_archived", "pt_package_plan") — PT-03."""

    model_config = ConfigDict(extra="forbid")

    plan_id: UUID


# ---------------------------------------------------------------------------
# PT-package instances lifecycle (Phase 33 PT-13)
# ---------------------------------------------------------------------------


class PtPackageSoldPayload(BaseModel):
    """Payload schema for ("pt_package_sold", "pt_package") — PT-13.

    Phase 33 D-33-15 additive extension (Plan 33-02): the Phase 32-landed
    7-key shape is extended to 10 keys by adding `plan_name_snapshot: str`,
    `start_date: date`, `end_date: date | None`. The `payment_id` forensic
    anchor is retained (Phase 32 PAY-05). LOCKED_AUDIT_EVENTS frozenset and
    AUDIT_PAYLOAD_SCHEMAS registry are untouched — only the per-event
    Pydantic model body grows. `end_date` is nullable because plans with
    `validity_days IS NULL` produce instances with `end_date IS NULL`
    (бессрочный package — D-33-14).
    """

    model_config = ConfigDict(extra="forbid")

    pt_package_id: UUID
    client_id: UUID
    plan_id: UUID
    plan_name_snapshot: str
    session_count_snapshot: int
    price_kopecks_snapshot: int
    validity_days_snapshot: int | None
    start_date: date
    end_date: date | None
    payment_id: UUID


class PtPackageCancelledPayload(BaseModel):
    """Payload schema for ("pt_package_cancelled", "pt_package") — PT-13.

    Phase 33 D-33-10 / Plan 33-03 additive extension: ``prior_status`` (one of
    ``'active'``, ``'exhausted'``, ``'expired'``) captures the source state
    before the cancellation transition for forensic chain inspection. Resolves
    the 33-PATTERNS.md:1112 mismatch flag — the original CONTEXT.md kwarg
    ``reason`` is now the schema field ``cancellation_reason`` AND the new
    ``prior_status`` field is added. LOCKED_AUDIT_EVENTS frozenset and
    AUDIT_PAYLOAD_SCHEMAS registry are untouched — only the per-event
    Pydantic model body grows (mirrors PtPackageSoldPayload additive
    extension pattern from Plan 33-02).
    """

    model_config = ConfigDict(extra="forbid")

    pt_package_id: UUID
    client_id: UUID
    cancellation_reason: str
    prior_status: str


class PtPackageRefundedPayload(BaseModel):
    """Payload schema for ("pt_package_refunded", "pt_package") — REF-07."""

    model_config = ConfigDict(extra="forbid")

    pt_package_id: UUID
    client_id: UUID
    refund_payment_id: UUID
    reason: str


class PtPackageExhaustedPayload(BaseModel):
    """Payload schema for ("pt_package_exhausted", "pt_package") — PT-13.

    Phase 33 D-33-15 additive extension (Plan 33-02): adds
    `exhausted_at: datetime` as schema bedrock for the Phase 34 callsite
    (PT-session decrement orchestrator emits this event when
    `sessions_remaining` reaches zero). Phase 33 itself does not emit this
    event — it is pre-registered for Phase 34 consumption (mirrors the
    Phase 30 INFRA-17 pre-registration pattern).
    """

    model_config = ConfigDict(extra="forbid")

    pt_package_id: UUID
    client_id: UUID
    exhausted_at: datetime


class PtPackageExpiredPayload(BaseModel):
    """Payload schema for ("pt_package_expired", "pt_package") — PT-13.

    `end_date` is the ISO date string (YYYY-MM-DD) on which the package
    became expired (snapshot from `pt_packages.end_date` at expiry). The
    pattern guard rejects empty / malformed strings at audit-emit time
    rather than letting them silently land in JSONB (WR-02 from Phase 33
    review — defence-in-depth alongside the cron's RuntimeError on a
    non-date row).
    """

    model_config = ConfigDict(extra="forbid")

    pt_package_id: UUID
    client_id: UUID
    end_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")


# ---------------------------------------------------------------------------
# PT-sessions lifecycle (Phase 34 PT-21)
# ---------------------------------------------------------------------------


class PtSessionRecordedPayload(BaseModel):
    """Payload schema for ("pt_session_recorded", "pt_session") — PT-21.

    `trainer_name_snapshot` (B-05) captures the trainer display name at
    recording time so historical UI integrity survives trainer rename /
    deactivation.
    `performed_at` is ISO-8601 datetime string with timezone offset.

    Phase 37 INFRA-25 / C-06 / D-37-05 additive extension: appends
    ``booking_id: UUID | None = None`` so the EXISTING `pt_session_recorded`
    event can also carry the parent-booking reference for v1.5 PT-session
    flows that originate from a confirmed booking. There is NO separate
    `booking_completed` event (C-06): completion is signalled by emitting
    `pt_session_recorded` with a non-None `booking_id`. Back-compat is
    preserved: every existing v1.4 emit callsite (notably
    ``app.modules.pt_sessions.service.record_pt_session``) continues to
    validate without modification because the field defaults to ``None``.
    LOCKED_AUDIT_EVENTS frozenset and AUDIT_PAYLOAD_SCHEMAS registry are
    untouched — only the per-event Pydantic model body grows (mirrors the
    Phase 33 D-33-15 PtPackageSoldPayload additive-extension precedent).
    """

    model_config = ConfigDict(extra="forbid")

    pt_session_id: UUID
    pt_package_id: UUID
    client_id: UUID
    trainer_id: UUID
    trainer_name_snapshot: str
    performed_at: str
    performed_by_user_id: UUID
    sessions_remaining_after: int
    # Phase 37 INFRA-25 / C-06 / D-37-05 — completion via existing event.
    booking_id: UUID | None = None


class PtSessionCancelledPayload(BaseModel):
    """Payload schema for ("pt_session_cancelled", "pt_session") — PT-21.

    `package_reactivated` flags whether the parent pt_package transitioned
    `exhausted → active` as part of the same UoW (PT-18 semantics).
    """

    model_config = ConfigDict(extra="forbid")

    pt_session_id: UUID
    pt_package_id: UUID
    client_id: UUID
    cancel_reason: str
    sessions_remaining_after: int
    package_reactivated: bool


# ---------------------------------------------------------------------------
# v1.5 (Phase 37 lock — emitted in Phase 38 per INFRA-25 / C-06)
# Schedule slot lifecycle payloads:
# ---------------------------------------------------------------------------


class SlotPublishedPayload(BaseModel):
    """Payload schema for ("slot_published", "schedule_slot") — Phase 38 SLOT-01.

    `start_time` / `end_time` are ISO-8601 datetime strings with timezone
    offset (Europe/Moscow per project i18n convention; serialiser uses
    `dt.isoformat()` at the emit callsite per P13).
    """

    model_config = ConfigDict(extra="forbid")

    slot_id: UUID
    trainer_id: UUID
    start_time: str
    end_time: str
    created_by_user_id: UUID


class SlotCancelledPayload(BaseModel):
    """Payload schema for ("slot_cancelled", "schedule_slot") — Phase 38 SLOT-07 / SLOT-09.

    `had_booking` (SLOT-09) discriminates whether a confirmed booking was
    attached to the slot at cancel time — drives downstream notification
    flow in Phase 39 (CRON-01 reminders) and forensic chain inspection.
    """

    model_config = ConfigDict(extra="forbid")

    slot_id: UUID
    trainer_id: UUID
    cancelled_by_user_id: UUID
    cancel_reason: str
    had_booking: bool


# ---------------------------------------------------------------------------
# v1.5 Booking lifecycle payloads:
# ---------------------------------------------------------------------------


class BookingCreatedPayload(BaseModel):
    """Payload schema for ("booking_created", "booking") — Phase 38 BOOK-02.

    `pt_package_id` is the decrement anchor: completion (via the existing
    `pt_session_recorded` event carrying `booking_id`) draws down sessions
    from this package. The (slot_id, client_id, pt_package_id) triple is
    the forensic chain for the booking.

    Phase 40 D-40-05 additive extension: ``actor_role`` Literal discriminates
    reception / owner (existing reception path) from telegram_bot (Phase 40
    self-service /book via Telegram). ``created_by_user_id`` becomes Optional
    because the bot path has no authenticated user — NULL means
    "self-service via bot, see ``actor_role`` for the discriminator".
    LOCKED_AUDIT_EVENTS frozenset and AUDIT_PAYLOAD_SCHEMAS registry are
    untouched (cardinality unchanged) — only this Pydantic model body grows
    (mirrors the additive pattern of ``PtPackageCancelledPayload`` in
    Phase 33 / ``PtSessionRecordedPayload`` in Phase 37).
    """

    model_config = ConfigDict(extra="forbid")

    booking_id: UUID
    slot_id: UUID
    client_id: UUID
    pt_package_id: UUID
    # Phase 40 D-40-05 — Optional for the bot self-service path (NULL =
    # actor_role='telegram_bot'); existing reception / owner emits continue
    # to populate this with the actor's UUID (stringified at the callsite
    # per Pitfall P13).
    created_by_user_id: UUID | None = None
    # Phase 40 D-40-05 — Literal discriminator. Default 'reception' preserves
    # the Phase 38 reception-path emit shape (which historically did not
    # carry actor_role); a Phase 40 callsite must pass actor_role explicitly
    # when emitting on behalf of the owner or the bot.
    actor_role: Literal["reception", "owner", "telegram_bot"] = "reception"


class BookingCancelledPayload(BaseModel):
    """Payload schema for ("booking_cancelled", "booking") — Phase 38 BOOK-06.

    `cancel_reason` captures operator-or-client intent; the 24h
    Europe/Moscow cancellation-window math lives in service code
    (Phase 38 plan, NOT this schema).
    """

    model_config = ConfigDict(extra="forbid")

    booking_id: UUID
    slot_id: UUID
    cancelled_by_user_id: UUID
    cancel_reason: str


class BookingNoShowPayload(BaseModel):
    """Payload schema for ("booking_no_show", "booking") — Phase 39 CRON-01.

    Emitted by the ARQ `mark_no_show_bookings` cron when a booking's slot
    has passed without a recorded `pt_session_recorded`. `no_show_at` is
    the ISO-8601 datetime string (with TZ offset) at which the cron
    classified the booking as no-show.
    """

    model_config = ConfigDict(extra="forbid")

    booking_id: UUID
    slot_id: UUID
    client_id: UUID
    no_show_at: str


# ---------------------------------------------------------------------------
# v1.6 (Phase 41 lock — INFRA-35; emitted in Phases 42/43/44/45)
#
# Per D-41-20: every new payload carries `audit_correlation_id: UUID | None`
# as the asynchronous event-correlation anchor — e.g. the synchronous
# `password_reset_requested` audit row and the eventual asynchronous
# `email_sent` audit row share the same UUID so the forensic chain is
# reconstructible from `audit_log` alone. `audit_correlation_id` is NOT
# auto-generated by `audit.emit()` (callers pass it explicitly to continue
# a chain; chain-starters pass `None`).
#
# Per D-41-09: `actor_email_snapshot` is a COLUMN on `audit_log`
# (migration 0023), NOT a payload field — it is set at the `audit.emit()`
# boundary from the ContextVar populated by the FastAPI auth dependency
# (D-41-08). NO new payload below carries `actor_email_snapshot`.
# ---------------------------------------------------------------------------


# Email transport (Phase 42 EMAIL-01 / EMAIL-04 / EMAIL-06):


class EmailSentPayload(BaseModel):
    """Payload schema for ("email_sent", "email_send_log") — Phase 42 EMAIL-01.

    Emitted by the ARQ `dispatch_email` task after the provider returns 2xx.
    `audit_correlation_id` links back to the triggering business audit row
    (e.g. the `password_reset_requested` row whose flow enqueued the email).
    `provider_message_id` is the provider's deliverability-tracking handle
    (None when the provider did not return one).
    """

    model_config = ConfigDict(extra="forbid")

    audit_correlation_id: UUID | None
    template_id: str
    to_email: str
    provider_message_id: str | None


class EmailSendFailedPayload(BaseModel):
    """Payload schema for ("email_send_failed", "email_send_log") — Phase 42 EMAIL-04 / EMAIL-06.

    Emitted by the ARQ `dispatch_email` task after exhausting retries OR when
    the circuit breaker is open. `reason` discriminates the failure class for
    Phase 45 ops dashboards / alerting; `provider_error_code` is the raw
    upstream code (None for `circuit_open`).
    """

    model_config = ConfigDict(extra="forbid")

    audit_correlation_id: UUID | None
    template_id: str
    to_email: str
    reason: Literal[
        "provider_5xx",
        "circuit_open",
        "invalid_recipient",
        "bounce",
        "complaint",
    ]
    provider_error_code: str | None


# Multi-user admin lifecycle (Phase 43 USERS-03..06):


class UserInvitedPayload(BaseModel):
    """Payload schema for ("user_invited", "user") — Phase 43 USERS-03.

    Emitted when the owner creates an invitation. `invited_role` is the
    Role string ('owner' | 'reception'); kept as `str` for forward-compat
    with future roles (D-41-20 — exact field shape left to implementor).
    `invitation_expires_at` is the UTC datetime at which the invitation
    becomes unusable (mirrors v1.1 `refresh_tokens.expires_at` discipline).

    `link_copied` (Phase 43 D-43-14): True when the owner used the
    ?include_invite_link=true escape-hatch query param at POST /users.
    URL itself is NOT in the payload (Pitfall 4 — anti-oracle for link bleed).
    """

    model_config = ConfigDict(extra="forbid")

    audit_correlation_id: UUID | None
    invited_user_id: UUID
    invited_email: str
    invited_role: str
    invitation_expires_at: datetime
    link_copied: bool  # Phase 43 D-43-14


class UserInvitationAcceptedPayload(BaseModel):
    """Payload schema for ("user_invitation_accepted", "user") — Phase 43 USERS-04.

    Emitted when the invitee completes the password-set flow via the
    invitation link. `invitation_token_id` is the atomic-consume token row
    (mirrors v1.1 refresh-token rotation discipline).
    """

    model_config = ConfigDict(extra="forbid")

    audit_correlation_id: UUID | None
    accepted_user_id: UUID
    invitation_token_id: UUID


class UserInvitationRevokedPayload(BaseModel):
    """Payload schema for ("user_invitation_revoked", "user") — Phase 43 USERS-05.

    Emitted when the owner manually revokes a pending invitation.
    `reason` is operator-supplied free text (None when not provided).
    """

    model_config = ConfigDict(extra="forbid")

    audit_correlation_id: UUID | None
    revoked_user_id: UUID
    invitation_token_id: UUID
    reason: str | None


class UserDeactivatedPayload(BaseModel):
    """Payload schema for ("user_deactivated", "user") — Phase 43 USERS-06.

    Emitted when the owner deactivates a user account. `sessions_revoked_count`
    is the number of active session families killed as part of the same UoW
    (mirrors v1.1 password-change session-revoke discipline).
    """

    model_config = ConfigDict(extra="forbid")

    audit_correlation_id: UUID | None
    deactivated_user_id: UUID
    sessions_revoked_count: int


class UserReactivatedPayload(BaseModel):
    """Payload schema for ("user_reactivated", "user") — Phase 43 USERS-06."""

    model_config = ConfigDict(extra="forbid")

    audit_correlation_id: UUID | None
    reactivated_user_id: UUID


class UserSoftDeletedPayload(BaseModel):
    """Payload schema for ("user_soft_deleted", "user") — Phase 43 USERS-06.

    Mirrors `client_soft_deleted` discipline (Phase 8) — the row stays in
    place with a `deleted_at` column, and the partial-UNIQUE on
    `(email) WHERE deleted_at IS NULL` lets the email be reused later.
    """

    model_config = ConfigDict(extra="forbid")

    audit_correlation_id: UUID | None
    deleted_user_id: UUID


# Password reset (Phase 44 RESET-01 / RESET-02):


class PasswordResetRequestedPayload(BaseModel):
    """Payload schema for ("password_reset_requested", "user") — Phase 44 RESET-01.

    Emitted in BOTH branches of the anti-oracle reset request flow (RESET-06):

      * Known-email branch: `target_user_id` is the resolved user UUID.
      * Unknown-email branch (D-41-10 system-emit): `target_user_id=None`,
        `actor_user_id=None` at the emit boundary; `email_hint` (lowercased
        email) preserves the forensic chain even when no user resolves.

    The `audit_correlation_id` UUID is generated by the reset-request handler
    and propagated to the eventual `email_sent` / `email_send_failed` audit
    rows so the chain reconstructs from `audit_log` alone.
    """

    model_config = ConfigDict(extra="forbid")

    audit_correlation_id: UUID | None
    target_user_id: UUID | None
    email_hint: str | None


class PasswordResetCompletedPayload(BaseModel):
    """Payload schema for ("password_reset_completed", "user") — Phase 44 RESET-02.

    Emitted on successful atomic-consume of a password_reset_tokens row.
    `sessions_revoked_count` mirrors the USER-DEACTIVATED pattern — all
    active session families are killed as part of the same UoW
    (D-41-03 — `password_reset_tokens` mirrors v1.1 refresh_tokens
    discipline byte-for-byte).
    """

    model_config = ConfigDict(extra="forbid")

    audit_correlation_id: UUID | None
    user_id: UUID
    sessions_revoked_count: int
    token_id: UUID


# Payment receipt email (Phase 45 NOTIFY-12):


class PaymentReceiptEmailedPayload(BaseModel):
    """Payload schema for ("payment_receipt_emailed", "payment") — Phase 45 NOTIFY-12.

    Emitted when the receipt-email task is ENQUEUED for a payment row.
    The eventual `email_sent` / `email_send_failed` audit row shares the
    same `audit_correlation_id` for forensic chain reconstruction.
    `receipt_kind` discriminates sale vs refund receipts (drives the
    correct LOCKED_EMAIL_TEMPLATES choice at the dispatch callsite).
    """

    model_config = ConfigDict(extra="forbid")

    audit_correlation_id: UUID | None
    payment_id: UUID
    to_email: str
    receipt_kind: Literal["sale", "refund"]


# Refresh-token failure tracking (Phase 43 USERS-06 / D-43-20):


class RefreshFailedPayload(BaseModel):
    """Payload schema for ("refresh_failed", "session") — Phase 43 USERS-06 / D-43-20.

    Emitted from auth.service.rotate_refresh when a refresh attempt fails for
    a reason that warrants forensic tracking. `reason` discriminates the failure
    class. `account_inactive` (USERS-06) is the new entry that lets ops dashboards
    distinguish a deactivated/deleted operator from a stolen-token attempt
    (`family_reuse_detected` — handled by its own existing event).

    Anti-oracle: the HTTP response is identical across reasons (D-43-20). The
    audit emit is forensic-only — never leaks via the response.
    """

    model_config = ConfigDict(extra="forbid")

    audit_correlation_id: UUID | None
    user_id: UUID | None  # None when refresh-token did not resolve to any user
    reason: Literal[
        "account_inactive",
        "invalid_session",
        "expired",
        "revoked",
    ]


# ---------------------------------------------------------------------------
# Registry — single canonical (event, resource_type) → Pydantic schema map.
# Mirrors LOCKED_AUDIT_EVENTS tuple-key shape (`audit.py:102-157`) so the
# lookup in `audit.emit()` is a single `.get((event, resource_type))`.
# ---------------------------------------------------------------------------


AUDIT_PAYLOAD_SCHEMAS: dict[tuple[str, str], type[BaseModel]] = {
    # Trainers (Phase 31 TRN-07)
    ("trainer_created", "trainer"): TrainerCreatedPayload,
    ("trainer_updated", "trainer"): TrainerUpdatedPayload,
    ("trainer_deactivated", "trainer"): TrainerDeactivatedPayload,
    ("trainer_reactivated", "trainer"): TrainerReactivatedPayload,
    # Payments + refunds (Phase 32 PAY-10 / REF-07)
    ("payment_recorded", "payment"): PaymentRecordedPayload,
    ("refund_issued", "payment"): RefundIssuedPayload,
    ("membership_refunded", "membership"): MembershipRefundedPayload,
    # PT-package plans (Phase 33 PT-03)
    ("pt_package_plan_created", "pt_package_plan"): PtPackagePlanCreatedPayload,
    ("pt_package_plan_updated", "pt_package_plan"): PtPackagePlanUpdatedPayload,
    ("pt_package_plan_archived", "pt_package_plan"): PtPackagePlanArchivedPayload,
    # PT-package instances (Phase 33 PT-13)
    ("pt_package_sold", "pt_package"): PtPackageSoldPayload,
    ("pt_package_cancelled", "pt_package"): PtPackageCancelledPayload,
    ("pt_package_refunded", "pt_package"): PtPackageRefundedPayload,
    ("pt_package_exhausted", "pt_package"): PtPackageExhaustedPayload,
    ("pt_package_expired", "pt_package"): PtPackageExpiredPayload,
    # PT-sessions (Phase 34 PT-21)
    ("pt_session_recorded", "pt_session"): PtSessionRecordedPayload,
    ("pt_session_cancelled", "pt_session"): PtSessionCancelledPayload,
    # v1.5 (Phase 37 lock — emitted in Phase 38 per INFRA-25)
    ("slot_published", "schedule_slot"): SlotPublishedPayload,
    ("slot_cancelled", "schedule_slot"): SlotCancelledPayload,
    ("booking_created", "booking"): BookingCreatedPayload,
    ("booking_cancelled", "booking"): BookingCancelledPayload,
    ("booking_no_show", "booking"): BookingNoShowPayload,
    # v1.6 (Phase 41 lock — INFRA-35; emitted in Phases 42/43/44/45)
    # Email transport (Phase 42):
    ("email_sent", "email_send_log"): EmailSentPayload,
    ("email_send_failed", "email_send_log"): EmailSendFailedPayload,
    # Multi-user admin lifecycle (Phase 43):
    ("user_invited", "user"): UserInvitedPayload,
    ("user_invitation_accepted", "user"): UserInvitationAcceptedPayload,
    ("user_invitation_revoked", "user"): UserInvitationRevokedPayload,
    ("user_deactivated", "user"): UserDeactivatedPayload,
    ("user_reactivated", "user"): UserReactivatedPayload,
    ("user_soft_deleted", "user"): UserSoftDeletedPayload,
    # Password reset (Phase 44):
    ("password_reset_requested", "user"): PasswordResetRequestedPayload,
    ("password_reset_completed", "user"): PasswordResetCompletedPayload,
    # Refresh-token failure tracking (Phase 43 USERS-06 / D-43-20):
    ("refresh_failed", "session"): RefreshFailedPayload,
    # Payment receipt email (Phase 45):
    ("payment_receipt_emailed", "payment"): PaymentReceiptEmailedPayload,
}
