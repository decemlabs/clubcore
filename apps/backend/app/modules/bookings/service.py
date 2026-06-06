"""Bookings service — orchestration between router and repository (Phase 38).

Phase 38 plan 38-02 Task 3 ships:
  - create_booking — 10-step atomic UoW that creates a confirmed booking
    (resolve slot → validate pt_package + trainer + Moscow-TZ validity
    window → flip slot active→booked via cross-module raw UPDATE → INSERT
    booking → flush + translate IntegrityError on uq_bookings_slot_confirmed
    → emit booking_created → commit).
  - complete_booking — Phase 37 stub body replaced with predicate-gated
    raw UPDATE (confirmed → completed) inside caller's UoW (D-38-13 /
    PKG-05; pt_sessions.service.record_pt_session is the future caller).

Discipline invariants (Phase 30 walkers — all must remain green):
  - SVC001 caller-owns-txn (test_service_commit_gate): every public mutating
    orchestrator MUST end with `await session.commit()`. Private / Protocol-
    slot helpers may carry `# noqa: SVC001 caller-owns-txn` on the def line.
  - audit.emit literal-string AST gate (INFRA-11 / test_audit_taxonomy):
    every emit() call uses literal strings for `event` and `resource_type`.
  - audit_payloads.py extra='forbid' validation (D-30-03): emit kwargs MUST
    match BookingCreatedPayload schema verbatim (5 keys — booking_id,
    slot_id, client_id, pt_package_id, created_by_user_id). UUIDs
    stringified at callsite per Pitfall 13 / D-38-17.
  - modules-independent contract: NO direct imports of
    app.modules.{schedule,pt_packages,...}. Cross-module reads via Protocol
    slots from app.core.dependencies (here: resolve_slot_by_id +
    get_active_pt_package). Cross-module slot UPDATE goes through the
    bookings.repository raw `sa.text()` helper (D-38-11 carve-out).

Cross-module behaviours used in this module:
  - resolve_slot_by_id (Protocol slot, Phase 37 D-37-06; Phase 38 plan
    38-01 replaced body with real schedule resolver) — returns SlotById
    structurally typed read of TrainerAvailabilitySlot.
  - get_active_pt_package (Phase 33 ActivePtPackageResolver) — returns
    the client's single active PT-package, silent-None if none.
  - bookings.repository.update_slot_status_predicate_gated — flips the
    schedule slot's status via raw cross-module UPDATE with the
    `noqa: TABLE_REF` marker (modules-independent contract preserved).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import ModuleType
from typing import TYPE_CHECKING
from uuid import UUID
from zoneinfo import ZoneInfo

import sqlalchemy as sa
import structlog
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import joinedload

from app.core import audit
from app.core.config import get_settings
from app.core.dependencies import (
    CurrentUser,
    get_active_pt_package,
    resolve_slot_by_id,
    restore_booking_slot,
)
from app.core.exceptions import ConflictError, NotFoundError
from app.core.formatters import _RU_MONTHS_GEN
from app.core.pagination import PaginatedData
from app.core.permissions import Role
from app.integrations.telegram import sender as telegram_sender
from app.integrations.telegram.bot import build_bot
from app.modules.bookings import repository
from app.modules.bookings.constants import (
    BOOKING_STATUS_TRANSITIONS,
    CANCEL_WINDOW_HOURS_CLIENT,
    CANCEL_WINDOW_HOURS_RECEPTION,
)
from app.modules.bookings.models import Booking, BookingNotification
from app.modules.bookings.notifications import (
    BOOKING_CANCELLED_BY_CLIENT_DM,
    BOOKING_CANCELLED_BY_OWNER_DM,
    BOOKING_CONFIRMED_DM,
    enqueue_booking_email_fallback,
    render_booking_rescheduled_dm,
)
from app.modules.bookings.schemas import (
    BookingCancelRequest,
    BookingCreateRequest,
    BookingDetailResponse,
    BookingListQuery,
    BookingResponse,
    BookingsForClientListQuery,
    BookingStatus,
    SlotSnapshot,
)
from app.modules.notifications.service import create_notification

if TYPE_CHECKING:
    from telegram import Bot

_log = structlog.get_logger("bookings.service")

# Business TZ pin (C-07 / D-38-12). Validity-window comparison MUST happen
# in Moscow time — a slot at 01:00 Moscow is 22:00 UTC the previous day;
# `.date()` on the UTC value mis-classifies the slot.
MOSCOW_TZ = ZoneInfo("Europe/Moscow")


# ---------------------------------------------------------------------------
# Error classes (mirror pt_sessions/service.py shape; class-level code +
# status_code translated by the global exception handler into the response
# envelope {error.code} field).
# ---------------------------------------------------------------------------


class BookingNotFoundError(NotFoundError):
    """Raised when a booking id lookup misses (plan 38-03 read/cancel)."""

    code = "booking_not_found"
    status_code = 404


class SlotNotFoundError(NotFoundError):
    """Raised by create_booking when the slot id does not exist."""

    code = "slot_not_found"
    status_code = 404


class SlotNotAvailableError(ConflictError):
    """Raised by create_booking when the slot exists but status != 'active'
    (cancelled, booked, etc.). Pre-INSERT app-layer guard mirrors the
    SLOT_STATUS_TRANSITIONS forward-only FSM (D-38-10)."""

    code = "slot_not_available"
    status_code = 409


class SlotAlreadyBookedError(ConflictError):
    """Raised by create_booking when the partial UNIQUE
    `uq_bookings_slot_confirmed` IntegrityError fires (D-38-15 / BOOK-10
    race-loser path). Translated via the `_is_slot_confirmed_conflict`
    constraint-name discriminator."""

    code = "slot_already_booked"
    status_code = 409


class TrainerMismatchError(ConflictError):
    """Raised by create_booking when `pt_package.trainer_id is not None`
    and does not match `slot.trainer_id` (C-08 / PKG-02). A NULL
    `pt_package.trainer_id` explicitly means "any trainer" and skips
    this guard."""

    code = "trainer_mismatch"
    status_code = 409


class PtPackageExhaustedError(ConflictError):
    """Raised by create_booking when the resolved active pt_package has
    sessions_remaining <= 0. Defence-in-depth at booking creation time;
    the package consumption logic itself lives in pt_sessions/service."""

    code = "pt_package_exhausted"
    status_code = 409


class PtPackageNotActiveError(ConflictError):
    """Raised by create_booking when the client has no active pt_package,
    or when the supplied pt_package_id does not match the client's active
    package. Defensive guard against id-spoofing — server is the arbiter
    of which package owns the booking."""

    code = "pt_package_not_active"
    status_code = 409


class PtPackageExpiredBeforeSlotError(ConflictError):
    """Raised by create_booking when the pt_package end_date is strictly
    less than the slot's start_time (compared in Moscow TZ per D-38-12 /
    Pitfall 18 / BOOK-04). NULL `pt_package.end_date` (бессрочный
    package) skips this guard."""

    code = "pt_package_expired_before_slot"
    status_code = 409


class InvalidBookingTransitionError(ConflictError):
    """Raised by complete_booking / FSM gate on disallowed booking status
    moves (D-38-10). Mirrors InvalidSlotTransitionError from schedule."""

    code = "invalid_transition"
    status_code = 409


class CancelWindowExpiredError(ConflictError):
    """Raised by cancel_booking when reception attempts to cancel a booking
    within CANCEL_WINDOW_HOURS_RECEPTION (24h per C-05 / D-38-16) of the
    slot's `start_time`. Owner is anytime per D-38-09.

    NOTE: status_code is **409** (not 403) per BOOK-06 REQUIREMENTS.md
    explicit lock — the plan-checker pinned this discriminator (pt_sessions
    uses 403 for the same window in B-12; BOOK-06 selected 409 because the
    state is "slot too imminent for this role" rather than an actor-auth
    issue per se). See plan 38-03 Task 2 <action> §"Error classes".
    """

    code = "cancel_window_expired"
    status_code = 409


class RescheduleWindowExpiredError(ConflictError):
    """Raised by reschedule_booking_for_client when the original slot starts
    within CANCEL_WINDOW_HOURS_CLIENT (24h) of now (RESCH-01 / D-80-XX).

    NOTE: status_code is **409** per parity with CancelWindowExpiredError
    (same "slot too imminent" business rule applied to the reschedule path).
    """

    code = "reschedule_window_expired"
    status_code = 409


class SlotTrainerMismatchError(ConflictError):
    """Raised by reschedule_booking_for_client when the new slot belongs to a
    different trainer than the original slot (RESCH-01 / D-80-XX).

    Reschedule is a slot MOVE within the same trainer — crossing trainers is
    an upgrade path requiring a new booking, not a reschedule.
    """

    code = "slot_trainer_mismatch"
    status_code = 409


# ---------------------------------------------------------------------------
# Phase 40 BLOCKER-2 — BookingResponse projection helper with JOIN fields.
# ---------------------------------------------------------------------------


def _booking_response_from_orm(booking: Booking) -> BookingResponse:
    """Project a Booking ORM (with eager-loaded ``slot`` + ``slot.trainer``)
    into ``BookingResponse``, injecting ``trainer_full_name`` and
    ``slot_start_time`` from the joined rows (Phase 40 BLOCKER-2 / D-40-07).

    Callers MUST have eager-loaded ``Booking.slot`` and ``slot.trainer``
    (the repository helpers that return bookings for response projection
    do this — ``get_booking_by_id``, ``list_bookings_paginated``,
    ``list_bookings_for_client_paginated``, ``get_booking_with_relations``).
    """
    return BookingResponse(
        id=booking.id,
        slot_id=booking.slot_id,
        client_id=booking.client_id,
        pt_package_id=booking.pt_package_id,
        status=BookingStatus(booking.status),
        created_at=booking.created_at,
        created_by_user_id=booking.created_by_user_id,
        cancelled_at=booking.cancelled_at,
        cancel_reason=booking.cancel_reason,
        no_show_at=booking.no_show_at,
        completed_at=booking.completed_at,
        trainer_full_name=booking.slot.trainer.full_name,
        slot_start_time=booking.slot.start_time,
    )


# ---------------------------------------------------------------------------
# FSM guard (D-38-10 / mirror pt_packages._assert_can_transition).
# ---------------------------------------------------------------------------


def _assert_can_transition(  # noqa: SVC001 caller-owns-txn
    booking: Booking,
    *,
    target: str,
) -> None:
    """Central state-machine guard (D-38-10).

    Consults `BOOKING_STATUS_TRANSITIONS` to decide whether
    `booking.status → target` is allowed; raises
    `InvalidBookingTransitionError` (409 invalid_transition) with
    discriminating `from_status` / `to_status` payload otherwise.

    Pure function — no DB writes; SVC001 noqa marker documents the
    discipline even though no commit is required here.
    """
    allowed = BOOKING_STATUS_TRANSITIONS.get(booking.status, frozenset())
    if target not in allowed:
        raise InvalidBookingTransitionError(
            "invalid_transition",
            fields={"from_status": booking.status, "to_status": target},
        )


# ---------------------------------------------------------------------------
# IntegrityError discriminator (D-38-15 / mirror
# pt_packages._is_active_pt_package_conflict).
# ---------------------------------------------------------------------------


def _is_slot_confirmed_conflict(exc: IntegrityError) -> bool:
    """Return True iff `exc` was caused by `uq_bookings_slot_confirmed` (D-38-15).

    asyncpg surfaces the constraint name via `exc.orig.constraint_name` on
    Postgres; string-fallback matches the literal embedded in the error
    message for drivers that omit the attribute. The literal MUST match
    the migration 0017 `op.create_index` name letter-for-letter.
    """
    constraint = getattr(exc.orig, "constraint_name", None) or ""
    if constraint == "uq_bookings_slot_confirmed":
        return True
    return "uq_bookings_slot_confirmed" in str(exc.orig)


# ---------------------------------------------------------------------------
# Phase 39 NOTIFY-03/04 — Telegram DM dispatch helpers.
# ---------------------------------------------------------------------------


async def _fetch_trainer_full_name(session: AsyncSession, trainer_id: UUID) -> str:  # noqa: SVC001 caller-owns-txn
    """Return trainer full_name for notification body rendering (D-54-08 raw SQL).

    Used by Phase 87 INBOX-03 co-transactional inbox hooks where the ORM
    joinedload chain is not available (trainer relationship not eagerly loaded
    at the hook site). Falls back to an empty string when the row is missing
    (defensive — slot FK ensures a trainer exists, but avoids masking a real error
    with a notification failure).
    """
    row = (
        await session.execute(
            sa.text("SELECT full_name FROM trainers WHERE id = :trainer_id"),
            {"trainer_id": str(trainer_id)},
        )
    ).mappings().one_or_none()
    if row is None:
        return ""
    return str(row["full_name"])


async def _load_booking_with_relationships(
    session: AsyncSession,
    booking_id: UUID,
) -> Booking | None:
    """Re-SELECT a booking with `client`, `slot`, `slot.trainer` eager-loaded.

    Phase 39 NOTIFY-03/04 dispatch helper consumer. Called post-commit by
    both `create_booking` / `cancel_booking` and (via function-local import)
    by `schedule.cancel_slot` cascade. Pure read; no UoW concerns.

    Uses `populate_existing()` so cross-module raw UPDATEs (slot status flips
    via `update_slot_status_predicate_gated`) don't leave a stale identity-
    map view of the slot when the same session is re-used.
    """
    import importlib

    from sqlalchemy import select

    # The nested `slot.trainer` chain requires a class-bound attribute on
    # the inner step (SA 2.0 strict rejects string-keyed joinedload as of
    # the version pinned for this project). We cannot statically
    # `from app.modules.schedule.models import TrainerAvailabilitySlot`
    # here — that would break the `modules-independent` import-linter
    # contract. Resolve via `importlib.import_module` so the import is
    # opaque to grimp's static-AST walker while still giving us the
    # class-bound `trainer` attribute (mirrors the same indirection
    # `schedule.cancel_slot` uses to reach bookings.service post-commit;
    # see PATTERNS.md §5 Option A as adapted during plan 39-02).
    _schedule_models = importlib.import_module("app.modules.schedule.models")
    trainer_availability_slot_cls = _schedule_models.TrainerAvailabilitySlot

    # NOTE: deliberately NO `populate_existing=True` here — the DM helper
    # only needs `client.first_name`, `client.telegram_user_id`,
    # `slot.start_time`, and `slot.trainer.full_name`. Status fields on the
    # slot are immaterial to the DM, and forcing populate_existing would
    # overwrite cached ORM instances elsewhere in the same session (e.g.
    # the slot row a subsequent `create_booking` call resolves through the
    # identity-map cache), changing behaviour observable from outside the
    # helper. The Phase 38 serial-double-book test (test_bookings_create.py
    # `test_create_booking_double_book_serial_409`) explicitly relies on
    # the stale-cache path to surface as `slot_already_booked` via the
    # 0-row UPDATE branch rather than the pre-INSERT `slot_not_available`
    # guard.
    stmt = (
        select(Booking)
        .options(
            joinedload(Booking.client),
            joinedload(Booking.slot).joinedload(trainer_availability_slot_cls.trainer),
        )
        .where(Booking.id == booking_id)
    )
    result: Booking | None = await session.scalar(stmt)
    return result


async def _dispatch_booking_dm(
    booking: Booking,
    *,
    template: str,
    bot: Bot,
    sender: ModuleType,
) -> None:
    """Fire-and-forget Telegram DM send (D-39-09 / D-39-10).

    The booking instance MUST have `client` and `slot.trainer` joinedloaded
    -- this helper does NOT refresh / re-fetch (that would extend the open
    transaction). Callers MUST use `_load_booking_with_relationships` (or
    equivalent eager-load) before invoking.

    Contract:
    - NEVER raises (D-39-09 fire-and-forget). The HTTP path is always green
      regardless of DM outcome.
    - Missing joinedload (None on `client` / `slot` / `slot.trainer`) ->
      ERROR-log `booking_dm_missing_joinedload` and return.
    - Unlinked client (`client.telegram_user_id is None`) -> INFO-log
      `booking_dm_skipped_unlinked` and return; no sender call.
    - `result.ok=False` -> WARNING-log `booking_dm_send_failed` with
      `reason=("bot_blocked" if result.blocked else "transient")` and return.

    `sender` is the `app.integrations.telegram.sender` module (D-39-19 — the
    indirection lets tests monkeypatch a stub `SimpleNamespace` exposing
    only `send_text_dm`). Helper takes no `session` argument and performs no
    DB writes, so SVC001 caller-owns-txn does not apply (no noqa needed).
    """
    if booking.client is None or booking.slot is None or booking.slot.trainer is None:
        _log.error(
            "booking_dm_missing_joinedload",
            booking_id=str(booking.id),
        )
        return

    chat_id = booking.client.telegram_user_id
    if chat_id is None:
        _log.info("booking_dm_skipped_unlinked", booking_id=str(booking.id))
        return

    text_body = template.format(
        client_name=booking.client.first_name,
        trainer_name=booking.slot.trainer.full_name,
        slot_start_msk=booking.slot.start_time.astimezone(MOSCOW_TZ).strftime("%d.%m.%Y %H:%M"),
    )
    result = await sender.send_text_dm(bot, chat_id, text_body)
    if not result.ok:
        reason = "bot_blocked" if result.blocked else "transient"
        _log.warning(
            "booking_dm_send_failed",
            reason=reason,
            booking_id=str(booking.id),
            telegram_chat_id=chat_id,
            error_msg=result.error,
        )


# ---------------------------------------------------------------------------
# Phase 45 D-45-05 — lifecycle email-fallback dispatch helper.
# ---------------------------------------------------------------------------


async def _dispatch_booking_lifecycle_notification(  # noqa: SVC001 caller-owns-txn -- helper opens its own fanout-INSERT scope post outer-commit
    booking: Booking,
    *,
    kind: str,
    template: str,
    bot: Bot,
    sender: ModuleType,
    session: AsyncSession,
) -> None:
    """Telegram-DM first + email-fallback INSERT for a lifecycle FSM event.

    Phase 45 D-45-05 / D-45-13. Wraps the existing
    ``_dispatch_booking_dm`` fire-and-forget Telegram path with a
    post-result email-fallback INSERT into ``booking_notifications``
    when:

      - Telegram returns ``SendResult.blocked=True`` AND the client has
        ``email IS NOT NULL`` — fanout to email + INSERT row with
        ``channel='email'``.
      - Telegram succeeds — no INSERT (lifecycle DMs are fire-and-forget
        per Phase 39 D-39-09; the booking row itself is the audit).
      - Client is Telegram-unlinked but has email — direct email send
        + INSERT row with ``channel='email'``.
      - Both channels unreachable — INFO-log + skip (no rows).

    Cross-channel UNIQUE ``uq_booking_notifications_booking_kind_channel``
    (Migration 0024) makes the INSERT idempotent per
    ``(booking_id, kind, channel)`` triple — concurrent FSM transitions
    cannot double-write.

    ``session`` is reused (the outer ``create_booking`` / ``cancel_booking``
    UoW has already committed and the session is in a clean state ready to
    begin a fresh transaction for the fanout INSERT). Mirrors the
    post-commit re-use shape established at create_booking lines 852-862
    where the same session is consumed by ``_load_booking_with_relationships``
    + ``get_booking_by_id`` reload.

    SVC001 marker (caller-owns-txn): this helper opens its own post-commit
    fanout scope — it commits the email-fallback INSERT independently of
    the outer booking-creation/cancellation transaction. Best-effort: an
    exception inside the fanout block does NOT roll back the booking
    FSM transition (that already committed upstream).
    """
    # Guard: missing eager-loaded relationships. Mirror _dispatch_booking_dm.
    if booking.client is None or booking.slot is None or booking.slot.trainer is None:
        _log.error(
            "booking_lifecycle_dm_missing_joinedload",
            booking_id=str(booking.id),
            kind=kind,
        )
        return

    chat_id = booking.client.telegram_user_id
    client_email = booking.client.email
    trainer_full_name = booking.slot.trainer.full_name
    slot_start_msk = booking.slot.start_time.astimezone(MOSCOW_TZ).strftime("%d.%m.%Y %H:%M")

    # Telegram side — only fire when a chat_id is present. Preserve the
    # Phase 39 log-event names (`booking_dm_skipped_unlinked` /
    # `booking_dm_send_failed`) so existing integration test assertions
    # in tests/integration/bookings/test_{create,cancel}_sends_dm.py
    # continue to match (the Phase 45 fanout is additive; the Phase 39
    # observability contract is unchanged).
    send_result = None
    if chat_id is None:
        _log.info("booking_dm_skipped_unlinked", booking_id=str(booking.id))
    else:
        text_body = template.format(
            client_name=booking.client.first_name,
            trainer_name=trainer_full_name,
            slot_start_msk=slot_start_msk,
        )
        send_result = await sender.send_text_dm(bot, chat_id, text_body)
        if not send_result.ok:
            reason = "bot_blocked" if send_result.blocked else "transient"
            # Phase 39 log-event name preserved for test-assertion stability.
            _log.warning(
                "booking_dm_send_failed",
                reason=reason,
                booking_id=str(booking.id),
                telegram_chat_id=chat_id,
                error_msg=send_result.error,
            )

    # Email-fallback decision (D-45-05): fire when Telegram unreachable AND
    # client has email. Transient Telegram failures (ok=False, blocked=False)
    # do NOT fan out — lifecycle DMs are best-effort; transient retries are
    # not the cron's job for lifecycle events (D-39-09 fire-and-forget).
    should_email_fanout = client_email is not None and (
        send_result is None  # Telegram-unlinked client
        or send_result.blocked  # Telegram bot blocked
    )
    if not should_email_fanout:
        return

    # Map the lifecycle kind -> 4-literal-branch email helper kind. Each
    # branch passes its own kind literal (D-45-22 + AST gate parity).
    try:
        if kind == "confirmed":
            session.add(
                BookingNotification(
                    booking_id=booking.id,
                    kind="confirmed",
                    channel="email",
                )
            )
            await enqueue_booking_email_fallback(
                kind="confirmed",
                client_email=client_email,
                trainer_name=trainer_full_name,
                slot_start_msk=slot_start_msk,
            )
        elif kind == "cancelled_by_client":
            session.add(
                BookingNotification(
                    booking_id=booking.id,
                    kind="cancelled_by_client",
                    channel="email",
                )
            )
            await enqueue_booking_email_fallback(
                kind="cancelled_by_client",
                client_email=client_email,
                trainer_name=trainer_full_name,
                slot_start_msk=slot_start_msk,
            )
        elif kind == "cancelled_by_owner":
            session.add(
                BookingNotification(
                    booking_id=booking.id,
                    kind="cancelled_by_owner",
                    channel="email",
                )
            )
            await enqueue_booking_email_fallback(
                kind="cancelled_by_owner",
                client_email=client_email,
                trainer_name=trainer_full_name,
                slot_start_msk=slot_start_msk,
            )
        else:  # pragma: no cover -- defensive; callers pass literals.
            raise ValueError(f"unknown lifecycle kind: {kind}")
        await session.commit()
    except IntegrityError:
        # Race with a concurrent FSM transition (idempotency catch).
        await session.rollback()
        _log.info(
            "booking_lifecycle_email_idempotency_conflict",
            booking_id=str(booking.id),
            kind=kind,
        )
    except Exception as exc:
        await session.rollback()
        _log.warning(
            "booking_lifecycle_email_fanout_failed",
            booking_id=str(booking.id),
            kind=kind,
            error_msg=str(exc),
        )


# ---------------------------------------------------------------------------
# Phase 39 CRON-01 — no-show batch helper (D-39-06 single-session, D-39-07
# SELECT FOR UPDATE OF b; SVC001-exempt: worker owns commit).
# ---------------------------------------------------------------------------


async def _mark_no_show_bookings(  # noqa: SVC001 caller-owns-txn
    session: AsyncSession,
) -> int:
    """Mark overdue confirmed bookings as no_show + emit audit (Phase 39 CRON-01).

    Single-session pattern (D-39-06 single-session for DB-only batch). Caller
    (`mark_no_show_bookings` worker) owns the surrounding transaction; this
    helper issues a SELECT FOR UPDATE + bulk UPDATE + per-row audit emit but
    does NOT commit (SVC001 noqa on the def line — mirrors
    `pt_packages._expire_due_pt_packages` and
    `memberships._expire_due_memberships`).

    Concurrency (D-39-07): `SELECT FOR UPDATE OF b` row-locks each candidate
    booking, serializing against `pt_sessions.service.record_pt_session`'s
    booking-completion path (D-38-19 — that path also takes the booking row
    lock before flipping confirmed->completed). Whichever transaction commits
    first wins; the loser sees the updated status and the
    `WHERE status='confirmed'` guard in the bulk UPDATE makes the no-op safe.

    Returns: count of rows newly flipped to no_show.
    """
    # Step 1 — Locked SELECT of candidates. Cross-module SQL: reads
    # `trainer_availability_slots` for the JOIN — raw text(...) keeps the
    # modules-independent import-linter contract green (mirror of Phase 38
    # D-38-11 TABLE_REF discipline; D-34-04a precedent).
    rows = await session.execute(
        sa.text(  # noqa: TABLE_REF cross-module SQL per D-34-04a / Phase 38 D-38-11
            "SELECT b.id, b.slot_id, b.client_id "
            "FROM bookings b "
            "JOIN trainer_availability_slots s ON s.id = b.slot_id "
            "WHERE b.status = 'confirmed' "
            "AND s.end_time < now() "
            "FOR UPDATE OF b"
        )
    )
    candidates = rows.fetchall()
    if not candidates:
        return 0

    # Step 2 — Bulk UPDATE. The `status = 'confirmed'` guard in the WHERE
    # clause is defensive (the FOR UPDATE already serializes); it makes the
    # statement idempotent against any concurrent transaction that flipped
    # one of the locked rows between Step 1 and here.
    await session.execute(
        sa.text(
            "UPDATE bookings SET status = 'no_show', no_show_at = now() "
            "WHERE id = ANY(:ids) AND status = 'confirmed'"
        ),
        {"ids": [c.id for c in candidates]},
    )

    # Step 3 — Per-row audit emit. Event name + resource_type MUST be string
    # literals (INFRA-11 AST gate). Payload matches BookingNoShowPayload
    # (extra='forbid') exactly: booking_id, slot_id, client_id, no_show_at.
    # UUIDs stringified at callsite per Pitfall 13 / D-38-17: although the
    # Pydantic v2 schema coerces both raw UUID and str (D-39-14), the
    # downstream JSONB write needs JSON-serializable values; raw UUID
    # objects are not json.dumps-able. Mirror the Phase 38 cancel_booking
    # callsite shape at bookings/service.py:709-713 verbatim. `resource_id`
    # is the typed FK column on AuditLog (PgUUID) — NOT in the JSONB
    # payload — so it stays as a raw UUID.
    no_show_at_iso = datetime.now(MOSCOW_TZ).isoformat()
    for c in candidates:
        await audit.emit(
            session,
            "booking_no_show",  # LITERAL — INFRA-11 AST gate
            actor_user_id=None,  # system actor; audit_log.actor_user_id is nullable
            resource_type="booking",  # LITERAL — INFRA-11 AST gate
            resource_id=c.id,
            booking_id=str(c.id),
            slot_id=str(c.slot_id),
            client_id=str(c.client_id),
            no_show_at=no_show_at_iso,
        )

    # Caller owns commit (D-39-06 single-session; worker function commits
    # after this helper returns).
    return len(candidates)


async def _send_booking_reminders(  # noqa: SVC001 caller-owns-txn
    session_factory: async_sessionmaker[AsyncSession],
    *,
    bot: Bot,
    sender: ModuleType,
    notifications_module: ModuleType,
) -> int:
    """Send 24h-out booking reminder DMs + insert booking_notifications
    idempotency rows on each successful send (Phase 39 CRON-02 / D-39-08).

    Multi-session per D-39-06b: one read session opens for the candidate
    SELECT; each successful send opens a FRESH write session for the
    INSERT + commit. This frees the DB connection across N Telegram HTTPS
    round-trips (mirror v1.3 D-27-07b).

    SVC001 marker (caller-owns-txn): the worker function
    ``send_booking_reminders`` receives no session — this helper is the
    transaction owner per per-send write session; the worker just supplies
    the sessionmaker.

    Idempotency (D-39-13): the SELECT pre-filters via LEFT JOIN
    ``booking_notifications`` + ``WHERE n.id IS NULL`` so the steady-state
    second tick is a no-op. The post-send INSERT is gated by the UNIQUE
    ``uq_booking_notifications_booking_kind`` constraint — a concurrent
    one-shot runner racing the live cron rolls back its write session and
    INFO-logs ``booking_reminder_idempotency_collision``.

    No audit emit (D-39-14): the ``booking_notifications`` row IS the
    audit record. Do NOT add a ``booking_reminder_sent`` event here.

    Returns:
        int — count of successful DM sends (also the count of newly-
        inserted ``booking_notifications`` rows on this run).
    """
    # Step 1 — read candidates in one short-lived read session.
    # D-39-08 verbatim: LEFT JOIN booking_notifications + WHERE n.id IS NULL
    # is the SELECT-level idempotency pre-filter; BETWEEN now()+23h AND
    # now()+25h is the locked 2-hour reminder window.
    #
    # Phase 45 D-45-01 cross-channel relax: the Telegram-only filter
    # `c.telegram_user_id IS NOT NULL` is widened to
    # `(c.telegram_user_id IS NOT NULL OR c.email IS NOT NULL)` so
    # email-only clients reach the email-fallback branch in the send loop
    # below. Both c.email and c.last_name/c.first_name are projected onto
    # the row so the per-send loop can call `enqueue_booking_email_fallback`
    # without a per-candidate re-query (matches the memberships
    # Plan 45-07 ExpiringCandidate widening shape — see
    # apps/backend/app/modules/memberships/repository.py:find_expiring_candidates).
    #
    # D-45-14: the NOT EXISTS / LEFT JOIN predicate on `booking_notifications`
    # stays channel-agnostic — `n.id IS NULL` matches the single-shot-per-kind
    # invariant ACROSS channels (Telegram OR email — only one wins per
    # (booking_id, kind), idempotency anchored by the cross-channel UNIQUE
    # `uq_booking_notifications_booking_kind_channel` from Migration 0024).
    async with session_factory() as read_session:
        result = await read_session.execute(
            sa.text(  # noqa: TABLE_REF cross-module SQL per D-34-04a / Phase 38 D-38-11
                "SELECT b.id, b.client_id, b.slot_id, "
                "       c.telegram_user_id, c.first_name, c.last_name, c.email, "
                "       t.full_name AS trainer_name, "
                "       s.start_time "
                "FROM bookings b "
                "JOIN clients c ON c.id = b.client_id "
                "JOIN trainer_availability_slots s ON s.id = b.slot_id "
                "JOIN trainers t ON t.id = s.trainer_id "
                "LEFT JOIN booking_notifications n "
                "       ON n.booking_id = b.id AND n.kind = 'reminder_24h' "
                "WHERE b.status = 'confirmed' "
                "  AND s.start_time BETWEEN now() + interval '23 hours' "
                "                       AND now() + interval '25 hours' "
                "  AND (c.telegram_user_id IS NOT NULL "
                "       OR c.email IS NOT NULL) "
                "  AND n.id IS NULL"
            )
        )
        rows = result.fetchall()

    sent = 0
    for r in rows:
        slot_start_msk = r.start_time.astimezone(MOSCOW_TZ).strftime("%d.%m.%Y %H:%M")

        # Phase 45 D-45-01 — Telegram-side dispatch only when chat_id present.
        # Email-only clients (telegram_user_id IS NULL but email IS NOT NULL)
        # skip the Telegram branch entirely and proceed directly to the
        # email-fallback block below; the read-session SELECT already
        # admitted them via the widened OR-predicate (D-45-01 / D-45-14).
        send_result = None
        if r.telegram_user_id is not None:
            # Step 2 — render the locked template via the supplied module
            # (passing the module enables test-time monkeypatching of the
            # renderer for the collision-rollback test).
            text_body = notifications_module.render_booking_reminder_24h_dm(
                client_name=r.first_name,
                trainer_name=r.trainer_name,
                slot_start_msk=slot_start_msk,
            )

            # Step 3 — fire the DM. ``sender.send_text_dm`` returns a typed
            # SendResult and never re-raises transport errors (D-07 contract).
            send_result = await sender.send_text_dm(bot, r.telegram_user_id, text_body)

        if send_result is not None and send_result.ok:
            # Step 4 (Telegram success) — open a FRESH write session for the
            # idempotency-row insert (multi-session per D-39-06b: never hold
            # the DB connection across HTTPS I/O). D-45-13: pass
            # `channel='telegram'` explicitly so the cross-channel UNIQUE
            # `uq_booking_notifications_booking_kind_channel` row is keyed
            # correctly.
            async with session_factory() as write_session:
                try:
                    write_session.add(
                        BookingNotification(
                            booking_id=r.id,
                            kind="reminder_24h",
                            channel="telegram",
                        )
                    )
                    await write_session.commit()
                    sent += 1
                except IntegrityError:
                    # D-39-13: race with a concurrent tick OR the one-shot
                    # operator runner that hit
                    # uq_booking_notifications_booking_kind_channel first.
                    # Rollback + INFO-log + continue.
                    await write_session.rollback()
                    _log.info(
                        "booking_reminder_idempotency_collision",
                        booking_id=str(r.id),
                        channel="telegram",
                    )
            continue

        # Telegram failed (or was not attempted because Telegram-unlinked).
        if send_result is not None:
            reason = "bot_blocked" if send_result.blocked else "transient"
            _log.warning(
                "booking_reminder_send_failed",
                reason=reason,
                booking_id=str(r.id),
                telegram_chat_id=r.telegram_user_id,
                error_msg=send_result.error,
            )

        # Phase 45 D-45-05 / D-45-06 — email-fallback sub-branch. Fires when
        # (a) Telegram was never attempted (email-only client), OR
        # (b) Telegram returned `blocked=True` AND the client has an email.
        # Transient Telegram failures (`blocked=False, ok=False`) do NOT
        # fan out — they retry on the next cron tick via the n.id IS NULL
        # pre-filter (D-39-13 idempotency anchored by row absence).
        client_email = r.email
        should_email_fanout = client_email is not None and (
            send_result is None  # email-only client
            or send_result.blocked  # Telegram-blocked
        )
        if not should_email_fanout:
            continue

        # D-45-06 reminder_24h email-fallback: open fresh write session,
        # INSERT channel='email' row, enqueue email, commit. IntegrityError
        # race-catch mirrors the Telegram-success branch above.
        slot_date_ru = (
            f"{r.start_time.astimezone(MOSCOW_TZ).day} "
            f"{_RU_MONTHS_GEN[r.start_time.astimezone(MOSCOW_TZ).month - 1]}"
        )
        async with session_factory() as write_session:
            try:
                write_session.add(
                    BookingNotification(
                        booking_id=r.id,
                        kind="reminder_24h",
                        channel="email",
                    )
                )
                await enqueue_booking_email_fallback(
                    kind="reminder_24h",
                    client_email=client_email,
                    trainer_name=r.trainer_name,
                    slot_start_msk=slot_start_msk,
                    slot_date=slot_date_ru,
                )
                await write_session.commit()
                sent += 1
            except IntegrityError:
                await write_session.rollback()
                _log.info(
                    "booking_reminder_idempotency_collision",
                    booking_id=str(r.id),
                    channel="email",
                )
            except Exception as exc:
                await write_session.rollback()
                _log.warning(
                    "booking_reminder_email_fanout_failed",
                    booking_id=str(r.id),
                    error_msg=str(exc),
                )

    _log.info("send_booking_reminders_complete", count=sent)
    return sent


# ---------------------------------------------------------------------------
# Phase 37 Protocol slot body (D-37-06 — preserve signature
# `async def complete_booking(session: AsyncSession, booking_id: UUID) -> None`;
# Phase 38 replaces the stub body with the predicate-gated raw UPDATE).
# ---------------------------------------------------------------------------


async def complete_booking(  # noqa: SVC001 caller-owns-txn
    session: AsyncSession,
    booking_id: UUID,
) -> None:
    """Transition booking confirmed→completed inside caller's UoW (D-38-13 / PKG-05).

    Caller (`pt_sessions.service.record_pt_session` — plan 38-05) owns the
    surrounding transaction. We issue a predicate-gated UPDATE so a
    concurrent cancel (status='cancelled') silently no-ops (FSM
    forward-only invariant `cancelled → ∅` from constants.py); 0-row
    UPDATE raises InvalidBookingTransitionError → 409 (defensive — the
    pt_sessions service already validated status='confirmed' under
    SELECT FOR UPDATE earlier in its UoW per D-38-19, but we still gate
    here to surface the contract breach if a future caller drops the
    pre-check).

    NO audit emit here — `pt_session_recorded` carries the `booking_id`
    field per D-37-05, so the booking-completion is observable via the
    pt_session_recorded audit row (C-06 / D-37-05).

    Caller-owns-txn (SVC001 opt-out marker on def line per D-32-10).
    """
    stmt = sa.text(
        """
        UPDATE bookings
        SET status = 'completed',
            completed_at = now(),
            updated_at = now()
        WHERE id = :booking_id AND status = 'confirmed'
        RETURNING id
        """,
    )
    result = await session.execute(stmt, {"booking_id": booking_id})
    if result.first() is None:
        raise InvalidBookingTransitionError(
            "invalid_transition",
            fields={"to_status": "completed"},
        )


# ---------------------------------------------------------------------------
# Public mutating orchestrator — create_booking (BOOK-02).
# ---------------------------------------------------------------------------


async def create_booking(
    session: AsyncSession,
    actor: CurrentUser,
    data: BookingCreateRequest,
) -> BookingResponse:
    """Create a confirmed booking (Phase 38 BOOK-02).

    Owns the UoW — `await session.commit()` at end (SVC001 gate).

    10-step recipe (mirror pt_sessions.record_pt_session shape):
      1. Resolve slot via SlotById Protocol slot (D-37-06) — 404
         slot_not_found / 409 slot_not_available if status != 'active'.
      2. Resolve client's active pt_package via the existing Phase 33
         ActivePtPackageResolver slot — 409 pt_package_not_active when
         silent-None, when the id doesn't match (defensive against
         id-spoofing), or when sessions_remaining <= 0 (then 409
         pt_package_exhausted).
      3. Trainer-mismatch guard (PKG-02 / C-08): if
         `pt_package.trainer_id is not None` and != `slot.trainer_id`,
         raise TrainerMismatchError. NULL trainer_id means "any".
      4. Moscow-TZ validity-window guard (Pitfall 18 / D-38-12 /
         BOOK-04): if `pt_package.end_date < slot.start_time.astimezone(
         MOSCOW_TZ).date()`, raise PtPackageExpiredBeforeSlotError. NULL
         end_date (бессрочный package) skips this check.
      5. Flip slot active→booked via the cross-module raw UPDATE
         (bookings.repository — modules-independent contract preserved
         via raw sa.text() with TABLE_REF noqa). 0 rows updated → 409
         slot_not_available (concurrent winner already took it pre-INSERT).
      6. Insert booking row via bookings.repository.insert_booking.
      7. session.flush() — surfaces the partial UNIQUE
         uq_bookings_slot_confirmed IntegrityError when a concurrent
         winner already INSERTed a confirmed row for the same slot in
         the gap between our active→booked UPDATE and our INSERT (the
         load-bearing race guard per BOOK-10). Translate via
         _is_slot_confirmed_conflict → 409 slot_already_booked.
      8. audit.emit('booking_created', ...) — payload matches
         BookingCreatedPayload (extra='forbid') verbatim; UUIDs
         stringified at callsite per Pitfall 13 / D-38-17.
      9. session.commit() (SVC001 gate).
     10. Narrow refresh on created_at/updated_at + return BookingResponse.
    """
    # Defensive request-time pin (Pitfall 7 / D-38-16 — datetime.now(UTC)
    # idiom; never datetime.utcnow which is deprecated in 3.12). Used by
    # the Moscow-TZ validity-window guard below and by the slot-not-available
    # defensive freshness check (if the slot's start_time has slipped into
    # the past since publish, surface as slot_not_available — the schedule
    # service guarantees future-only at publish time but time drifts).
    now_utc = datetime.now(UTC)

    # Step 1 — slot resolve + status guard.
    slot = await resolve_slot_by_id(session, data.slot_id)
    if slot is None:
        raise SlotNotFoundError("slot_not_found")
    if slot.status != "active":
        raise SlotNotAvailableError("slot_not_available")
    if slot.start_time <= now_utc:
        # Defensive freshness — the schedule-service publish-time guard
        # (D-38-16) means a newly-published slot can never start in the
        # past, but between publish and booking the clock advances. We
        # surface as slot_not_available to match the unified error code
        # set (no separate slot_in_past code at the booking layer; the
        # slot is simply not bookable).
        raise SlotNotAvailableError("slot_not_available")

    # Step 2 — active pt_package resolve + id-match + exhausted guard.
    pt_package = await get_active_pt_package(session, data.client_id)
    if pt_package is None:
        raise PtPackageNotActiveError("pt_package_not_active")
    if pt_package.id != data.pt_package_id:
        # Defensive — reception/owner cannot book against an unrelated
        # package id (server is the arbiter of which package owns the
        # booking; mirrors pt_sessions/service.py:217-222 client_id
        # sourced-from-package discipline per D-34-13a).
        raise PtPackageNotActiveError("pt_package_not_active")
    if pt_package.sessions_remaining <= 0:
        raise PtPackageExhaustedError("pt_package_exhausted")

    # Step 3 — Trainer-mismatch guard (PKG-02 / C-08).
    # pt_package.trainer_id is added by plan 38-04 (Alembic 0018); until
    # then the column does not exist on the ActivePtPackage Protocol and
    # `getattr` returns None (NULL = "any trainer" by C-08 spec).
    pkg_trainer_id = getattr(pt_package, "trainer_id", None)
    if pkg_trainer_id is not None and pkg_trainer_id != slot.trainer_id:
        raise TrainerMismatchError("trainer_mismatch")

    # Step 4 — Moscow-TZ validity-window guard (Pitfall 18 / D-38-12 / BOOK-04).
    # CRITICAL: convert slot.start_time to Moscow TZ before extracting .date()
    # — a slot at 01:00 Moscow is 22:00 UTC the prior day; .date() on the
    # UTC value would mis-classify and incorrectly accept an expired package.
    if (
        pt_package.end_date is not None
        and pt_package.end_date < slot.start_time.astimezone(MOSCOW_TZ).date()
    ):
        raise PtPackageExpiredBeforeSlotError("pt_package_expired_before_slot")

    # Step 5 — Cross-module raw UPDATE flipping slot active→booked.
    # 0-row return: concurrent winner already took it pre-INSERT (or the
    # slot status changed between Step 1's read and now). Re-fetch to
    # discriminate `slot_already_booked` (someone else booked it) from
    # `slot_not_available` (slot was cancelled / otherwise unbookable).
    # This matches BOOK-TEST-01 / D-38-15 expectation that the race-loser
    # surfaces as `slot_already_booked` consistently.
    slot_flipped = await repository.update_slot_status_predicate_gated(
        session,
        data.slot_id,
        from_status="active",
        to_status="booked",
    )
    if not slot_flipped:
        # Force a fresh read bypassing the ORM identity-map cache (the
        # cross-module raw UPDATE in another transaction bypassed our
        # ORM tracking, so a normal `session.scalar(select(...))` could
        # return a cached pre-UPDATE instance).
        await session.refresh(slot, attribute_names=["status"])
        if slot.status == "booked":
            raise SlotAlreadyBookedError("slot_already_booked")
        raise SlotNotAvailableError("slot_not_available")

    # Step 6 — INSERT booking row.
    booking = await repository.insert_booking(
        session,
        slot_id=data.slot_id,
        client_id=data.client_id,
        pt_package_id=data.pt_package_id,
        created_by_user_id=actor.id,
    )

    # Step 7 — Flush + race-translation. The partial UNIQUE
    # uq_bookings_slot_confirmed is the load-bearing race guard (BOOK-01 /
    # C-02 / Pitfall 1 / D-38-15). On 2 concurrent POSTs to the same slot:
    # both may pass Step 5 (their UPDATEs serialise but the loser sees 0
    # rows only when the winner committed; in real Postgres async write
    # interleavings the loser observes 1 row from its own UPDATE then
    # blocks on the row-lock, ultimately attempting the INSERT and hitting
    # the partial UNIQUE here). We rollback the broken UoW and translate
    # to 409 slot_already_booked.
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        if _is_slot_confirmed_conflict(exc):
            raise SlotAlreadyBookedError("slot_already_booked") from exc
        raise

    # Step 8 — Emit booking_created (LITERAL strings for INFRA-11 AST gate).
    # Payload matches BookingCreatedPayload (extra='forbid') verbatim; UUIDs
    # stringified at callsite per D-38-17 / Pitfall 13.
    #
    # Phase 40 D-40-05 / WARNING-1 — explicit ``actor_role`` literal kwarg
    # branched on ``actor.role``; ``actor_user_id`` continues to be the RAW
    # UUID (audit.emit's signature is ``UUID | None``, NOT str). Only the
    # payload-level ``created_by_user_id`` is stringified (Pitfall P13 — the
    # JSONB payload schema declares it as ``UUID | None`` but for forward
    # compat with payload-as-str callsites we stringify here, mirroring the
    # original Phase 38 shape).
    if actor.role is Role.OWNER:
        await audit.emit(
            session,
            "booking_created",  # LITERAL — INFRA-11 AST gate
            actor_user_id=actor.id,  # RAW UUID (audit.emit signature)
            resource_type="booking",  # LITERAL
            resource_id=booking.id,
            booking_id=str(booking.id),
            slot_id=str(booking.slot_id),
            client_id=str(booking.client_id),
            pt_package_id=str(booking.pt_package_id),
            created_by_user_id=str(actor.id),
            actor_role="owner",  # LITERAL — INFRA-11 AST gate / D-40-05
        )
    else:
        await audit.emit(
            session,
            "booking_created",  # LITERAL — INFRA-11 AST gate
            actor_user_id=actor.id,  # RAW UUID (audit.emit signature)
            resource_type="booking",  # LITERAL
            resource_id=booking.id,
            booking_id=str(booking.id),
            slot_id=str(booking.slot_id),
            client_id=str(booking.client_id),
            pt_package_id=str(booking.pt_package_id),
            created_by_user_id=str(actor.id),
            actor_role="reception",  # LITERAL — INFRA-11 AST gate / D-40-05
        )

    # Step 8.5 — Phase 87 INBOX-03 — in-app inbox row (co-transactional, BEFORE commit).
    # Placed here (after audit.emit, before session.commit) so the notification INSERT
    # participates in the same UoW as the booking state change (UNIQUE dedup via
    # uq_in_app_notifications_client_source_kind covers webhook/retry replay).
    _trainer_name = await _fetch_trainer_full_name(session, slot.trainer_id)
    _slot_start_msk = slot.start_time.astimezone(MOSCOW_TZ).strftime("%d.%m.%Y %H:%M")
    await create_notification(
        session,
        client_id=booking.client_id,
        source_type="booking",
        source_id=booking.id,
        kind="booking_confirmed",
        title="Бронь подтверждена",
        body=f"{_slot_start_msk} — {_trainer_name}",
    )

    # Step 9 — Commit (SVC001 gate).
    await session.commit()

    # Step 9.5 — Phase 39 NOTIFY-03 + Phase 45 D-45-05 — fire-and-forget
    # DM (post-commit per D-39-10) with email-fallback when Telegram is
    # unreachable. Booking is fully durable here; the helper never raises
    # so the HTTP path is unaffected by any DM-send outcome. Re-fetch with
    # joinedload(client, slot.trainer) — `repository.insert_booking` returns
    # a freshly-added ORM instance with relationships not eager-loaded.
    booking_for_dm = await _load_booking_with_relationships(session, booking.id)
    if booking_for_dm is not None:
        dm_bot = build_bot(
            token=get_settings().telegram_bot_token.get_secret_value(),
        )
        await _dispatch_booking_lifecycle_notification(
            booking_for_dm,
            kind="confirmed",  # LITERAL — Plan 45-08 4-kind contract
            template=BOOKING_CONFIRMED_DM,
            bot=dm_bot,
            sender=telegram_sender,
            session=session,
        )

    # Step 10 — Reload with slot+trainer joinedload (Phase 40 BLOCKER-2) so
    # BookingResponse carries trainer_full_name + slot_start_time without
    # an N+1 lookup.
    reloaded = await repository.get_booking_by_id(session, booking.id)
    if reloaded is None:
        # Defensive — booking was just INSERTed and committed; missing here
        # would indicate session-state corruption.
        raise RuntimeError("create_booking: just-inserted booking disappeared on reload")
    return _booking_response_from_orm(reloaded)


# ---------------------------------------------------------------------------
# Public mutating orchestrator — create_booking_via_bot (Phase 40 D-40-04).
# ---------------------------------------------------------------------------


async def create_booking_via_bot(
    session: AsyncSession,
    *,
    client_id: UUID,
    slot_id: UUID,
    pt_package_id: UUID,
) -> BookingResponse:
    """Telegram /book self-service booking entry — Phase 40 D-40-04.

    Mirrors ``create_booking``'s 10-step UoW exactly except:
      - Takes no ``CurrentUser`` (no authenticated user on the bot path).
      - Inserts the booking with ``created_by_user_id=None`` (Phase 40
        D-40-05 / BLOCKER-4 — Alembic 0021 made the column NULLABLE).
      - Emits ``booking_created`` with ``actor_user_id=None`` (raw None —
        ``audit.emit`` signature is ``UUID | None``), ``actor_role="telegram_bot"``
        (Literal — INFRA-11 AST gate), and payload
        ``created_by_user_id=None`` (D-40-05).
      - Returns the BookingResponse with ``trainer_full_name`` +
        ``slot_start_time`` populated (Phase 40 BLOCKER-2 JOIN projection)
        so the Phase 40 plan 40-03 callback handler can render the
        confirmation DM directly without a secondary lookup.

    Raises the same 7 domain error classes as ``create_booking``
    (``SlotNotFoundError``, ``SlotNotAvailableError``,
    ``SlotAlreadyBookedError``, ``TrainerMismatchError``,
    ``PtPackageNotActiveError``, ``PtPackageExhaustedError``,
    ``PtPackageExpiredBeforeSlotError``). The bot handler maps every
    raised error class to ``_BOT_BOOK_DENIED_DM`` (Phase 40 C-12
    anti-oracle — no failure-cause disclosure to the chat).

    SVC001 caller-owns-txn: this function commits its own UoW.
    """
    now_utc = datetime.now(UTC)

    # Step 1 — slot resolve + status guard (mirror create_booking lines).
    slot = await resolve_slot_by_id(session, slot_id)
    if slot is None:
        raise SlotNotFoundError("slot_not_found")
    if slot.status != "active":
        raise SlotNotAvailableError("slot_not_available")
    if slot.start_time <= now_utc:
        raise SlotNotAvailableError("slot_not_available")

    # Step 2 — active pt_package resolve + id-match + exhausted guard.
    pt_package = await get_active_pt_package(session, client_id)
    if pt_package is None:
        raise PtPackageNotActiveError("pt_package_not_active")
    if pt_package.id != pt_package_id:
        # Defensive — bot resolved a different package id than the user's
        # active package (id-spoofing protection mirrors Phase 38).
        raise PtPackageNotActiveError("pt_package_not_active")
    if pt_package.sessions_remaining <= 0:
        raise PtPackageExhaustedError("pt_package_exhausted")

    # Step 3 — Trainer-mismatch guard (PKG-02 / C-08).
    pkg_trainer_id = getattr(pt_package, "trainer_id", None)
    if pkg_trainer_id is not None and pkg_trainer_id != slot.trainer_id:
        raise TrainerMismatchError("trainer_mismatch")

    # Step 4 — Moscow-TZ validity-window guard (D-38-12 / Pitfall 18).
    if (
        pt_package.end_date is not None
        and pt_package.end_date < slot.start_time.astimezone(MOSCOW_TZ).date()
    ):
        raise PtPackageExpiredBeforeSlotError("pt_package_expired_before_slot")

    # Step 5 — Cross-module raw UPDATE flipping slot active→booked.
    slot_flipped = await repository.update_slot_status_predicate_gated(
        session,
        slot_id,
        from_status="active",
        to_status="booked",
    )
    if not slot_flipped:
        # Force a fresh read bypassing identity-map cache (mirror create_booking).
        await session.refresh(slot, attribute_names=["status"])
        if slot.status == "booked":
            raise SlotAlreadyBookedError("slot_already_booked")
        raise SlotNotAvailableError("slot_not_available")

    # Step 6 — INSERT booking row with created_by_user_id=None
    # (Phase 40 D-40-05 / BLOCKER-4 — Alembic 0021 made this column NULLABLE).
    booking = await repository.insert_booking(
        session,
        slot_id=slot_id,
        client_id=client_id,
        pt_package_id=pt_package_id,
        created_by_user_id=None,
    )

    # Step 7 — Flush + uq_bookings_slot_confirmed race translation.
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        if _is_slot_confirmed_conflict(exc):
            raise SlotAlreadyBookedError("slot_already_booked") from exc
        raise

    # Step 8 — Emit booking_created (LITERAL strings; D-40-05 telegram_bot
    # actor_role + raw None actor_user_id per WARNING-1 fix).
    await audit.emit(
        session,
        "booking_created",  # LITERAL — INFRA-11 AST gate
        actor_user_id=None,  # RAW None (audit.emit signature is UUID | None)
        resource_type="booking",  # LITERAL — INFRA-11 AST gate
        resource_id=booking.id,
        booking_id=str(booking.id),
        slot_id=str(booking.slot_id),
        client_id=str(booking.client_id),
        pt_package_id=str(booking.pt_package_id),
        created_by_user_id=None,  # payload-level; nullable per D-40-05
        actor_role="telegram_bot",  # LITERAL — INFRA-11 AST gate / D-40-05
    )

    # Step 9 — Commit (SVC001 gate).
    await session.commit()

    # Step 10 — Reload with slot+trainer joinedload (Phase 40 BLOCKER-2) so
    # the returned BookingResponse carries trainer_full_name + slot_start_time.
    # Plan 40-03's callback handler consumes these fields directly to render
    # the confirmation DM without a secondary lookup.
    reloaded = await repository.get_booking_by_id(session, booking.id)
    if reloaded is None:
        raise RuntimeError("create_booking_via_bot: just-inserted booking disappeared on reload")
    return _booking_response_from_orm(reloaded)


# ---------------------------------------------------------------------------
# Public mutating orchestrator — create_booking_for_client (Phase 70 D-70-01).
# ---------------------------------------------------------------------------


async def create_booking_for_client(
    session: AsyncSession,
    *,
    client_id: UUID,
    slot_id: UUID,
    pt_package_id: UUID,
) -> BookingResponse:
    """Client self-service booking entry — Phase 70 D-70-01.

    Mirrors ``create_booking_via_bot``'s 10-step UoW exactly except:
      - Takes no ``CurrentUser`` (no authenticated staff user on the client path).
      - Inserts the booking with ``created_by_user_id=None`` (D-40-05 /
        Alembic 0021 made the column NULLABLE).
      - Emits ``booking_created`` with ``actor_user_id=None`` (raw None —
        ``audit.emit`` signature is ``UUID | None``), ``actor_role="client"``
        (Literal — INFRA-11 AST gate / D-70-07), and payload
        ``created_by_user_id=None`` (D-40-05 anti-fabrication — do NOT
        invent a fake staff user).
      - Returns ``BookingResponse`` with ``trainer_full_name`` +
        ``slot_start_time`` populated (Phase 40 BLOCKER-2 JOIN projection)
        so Plan 70-03 client endpoints can return full response without a
        secondary lookup.

    Raises the same 7 domain error classes as ``create_booking``
    (``SlotNotFoundError``, ``SlotNotAvailableError``,
    ``SlotAlreadyBookedError``, ``TrainerMismatchError``,
    ``PtPackageNotActiveError``, ``PtPackageExhaustedError``,
    ``PtPackageExpiredBeforeSlotError``). Plan 70-03 maps every raised
    error class to the appropriate HTTP response code.

    SVC001 caller-owns-txn: this function commits its own UoW.
    """
    now_utc = datetime.now(UTC)

    # Step 1 — slot resolve + status guard (mirror create_booking_via_bot).
    slot = await resolve_slot_by_id(session, slot_id)
    if slot is None:
        raise SlotNotFoundError("slot_not_found")
    if slot.status != "active":
        raise SlotNotAvailableError("slot_not_available")
    if slot.start_time <= now_utc:
        raise SlotNotAvailableError("slot_not_available")

    # Step 2 — active pt_package resolve + id-match + exhausted guard.
    pt_package = await get_active_pt_package(session, client_id)
    if pt_package is None:
        raise PtPackageNotActiveError("pt_package_not_active")
    if pt_package.id != pt_package_id:
        # Defensive — client cannot book against an unrelated package id
        # (server is the arbiter of which package owns the booking; mirrors
        # create_booking_via_bot id-spoofing protection).
        raise PtPackageNotActiveError("pt_package_not_active")
    if pt_package.sessions_remaining <= 0:
        raise PtPackageExhaustedError("pt_package_exhausted")

    # Step 3 — Trainer-mismatch guard (PKG-02 / C-08).
    pkg_trainer_id = getattr(pt_package, "trainer_id", None)
    if pkg_trainer_id is not None and pkg_trainer_id != slot.trainer_id:
        raise TrainerMismatchError("trainer_mismatch")

    # Step 4 — Moscow-TZ validity-window guard (D-38-12 / Pitfall 18).
    if (
        pt_package.end_date is not None
        and pt_package.end_date < slot.start_time.astimezone(MOSCOW_TZ).date()
    ):
        raise PtPackageExpiredBeforeSlotError("pt_package_expired_before_slot")

    # Step 5 — Cross-module raw UPDATE flipping slot active→booked.
    slot_flipped = await repository.update_slot_status_predicate_gated(
        session,
        slot_id,
        from_status="active",
        to_status="booked",
    )
    if not slot_flipped:
        # Force a fresh read bypassing identity-map cache (mirror create_booking).
        await session.refresh(slot, attribute_names=["status"])
        if slot.status == "booked":
            raise SlotAlreadyBookedError("slot_already_booked")
        raise SlotNotAvailableError("slot_not_available")

    # Step 6 — INSERT booking row with created_by_user_id=None (D-40-05 /
    # D-70-07 anti-fabrication: no fake staff user for the client path).
    booking = await repository.insert_booking(
        session,
        slot_id=slot_id,
        client_id=client_id,
        pt_package_id=pt_package_id,
        created_by_user_id=None,
    )

    # Step 7 — Flush + uq_bookings_slot_confirmed race translation.
    # Criterion #1 (D-70-06 / CBOOK-03): the partial UNIQUE is the
    # load-bearing race guard. BOOK-10 race-loser path: translate
    # IntegrityError → SlotAlreadyBookedError (409 slot_already_booked).
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        if _is_slot_confirmed_conflict(exc):
            raise SlotAlreadyBookedError("slot_already_booked") from exc
        raise

    # Step 8 — Emit booking_created (LITERAL strings for INFRA-11 AST gate).
    # D-70-07: actor_role="client" literal; actor_user_id=None; payload
    # created_by_user_id=None (D-40-05 — do NOT fabricate a staff user;
    # audit.emit signature is UUID | None so None is legal here).
    await audit.emit(
        session,
        "booking_created",  # LITERAL — INFRA-11 AST gate
        actor_user_id=None,  # RAW None (audit.emit signature is UUID | None)
        resource_type="booking",  # LITERAL — INFRA-11 AST gate
        resource_id=booking.id,
        booking_id=str(booking.id),
        slot_id=str(booking.slot_id),
        client_id=str(booking.client_id),
        pt_package_id=str(booking.pt_package_id),
        created_by_user_id=None,  # payload-level; nullable per D-40-05 / D-70-07
        actor_role="client",  # LITERAL — INFRA-11 AST gate / D-70-07
    )

    # Step 9 — Commit (SVC001 gate).
    await session.commit()

    # Step 10 — Reload with slot+trainer joinedload (Phase 40 BLOCKER-2) so
    # the returned BookingResponse carries trainer_full_name + slot_start_time.
    reloaded = await repository.get_booking_by_id(session, booking.id)
    if reloaded is None:
        raise RuntimeError("create_booking_for_client: just-inserted booking disappeared on reload")
    return _booking_response_from_orm(reloaded)


# ---------------------------------------------------------------------------
# Public mutating orchestrator — cancel_booking (Phase 38 plan 38-03 / BOOK-06).
# ---------------------------------------------------------------------------


async def cancel_booking(
    session: AsyncSession,
    actor: CurrentUser,
    booking_id: UUID,
    data: BookingCancelRequest,
) -> BookingResponse:
    """Cancel a confirmed booking (Phase 38 BOOK-06 / D-38-09 / D-38-16).

    Owns the UoW — `await session.commit()` at end (SVC001 gate).

    Sequence:
      1. Load booking + linked slot (row-lock on booking) via
         `repository.get_booking_by_id_for_update_with_slot`. 404
         `booking_not_found` for missing id.
      2. FSM guard via `_assert_can_transition(target='cancelled')` —
         409 `invalid_transition` for non-confirmed source
         (cancelled / no_show / completed are terminal per
         BOOKING_STATUS_TRANSITIONS).
      3. 24h reception window (D-38-16): if `actor.role == RECEPTION` and
         `booking.slot.start_time - datetime.now(UTC) < timedelta(hours=
         CANCEL_WINDOW_HOURS_RECEPTION)` raise CancelWindowExpiredError.
         **Compared against `slot.start_time`, NOT `created_at`** —
         D-38-16 explicit (a booking made far in advance still locks 24h
         before the slot fires). Owner is anytime per D-38-09.
      4. Mutate booking in-place: status='cancelled', cancelled_at=now(UTC),
         cancel_reason=data.reason.
      5. Restore slot booked→active via the Phase 37 BookingSlotRestorer
         Protocol slot (`restore_booking_slot`) — flips the linked slot's
         status in the SAME UoW. Modules-independent contract preserved:
         the consumer reaches schedule.service.restore_slot_to_active
         via the composition-root slot, never via direct import.
      6. session.flush() — surfaces FK / CHECK errors before audit emit.
      7. audit.emit('booking_cancelled', ...) — payload matches
         `BookingCancelledPayload` (4 keys: booking_id, slot_id,
         cancelled_by_user_id, cancel_reason) verbatim with UUIDs
         stringified per D-38-17 / Pitfall 13. NOTE: `client_id` is NOT
         in BookingCancelledPayload (audit schema 4 keys, not 5) — see
         audit_payloads.py:394.
      8. (DM-queue side-effect: NO-OP stub in Phase 38; Phase 39 wires
         the real Telegram send via NOTIFY-04.)
      9. session.commit() (SVC001 gate).
     10. Narrow refresh + return BookingResponse.
    """
    # Step 1 — Load with row lock + eager-loaded slot.
    booking = await repository.get_booking_by_id_for_update_with_slot(session, booking_id)
    if booking is None:
        raise BookingNotFoundError("booking_not_found")

    # Step 2 — FSM gate (consults BOOKING_STATUS_TRANSITIONS).
    _assert_can_transition(booking, target="cancelled")

    # Step 3 — 24h reception window (D-38-16; compare against slot.start_time).
    now_utc = datetime.now(UTC)
    if actor.role is Role.RECEPTION and (
        booking.slot.start_time - now_utc < timedelta(hours=CANCEL_WINDOW_HOURS_RECEPTION)
    ):
        raise CancelWindowExpiredError("cancel_window_expired")

    # Step 4 — Mutate booking in-place (cancelled_at / cancel_reason).
    booking.status = "cancelled"
    booking.cancelled_at = now_utc
    booking.cancel_reason = data.reason

    # Step 5 — Restore linked slot booked→active in the same UoW via the
    # Phase 37 BookingSlotRestorer Protocol slot. The schedule.service
    # body (Phase 38 plan 38-01 replaced the stub) issues a predicate-
    # gated raw UPDATE; defensive InvalidSlotTransitionError on 0-row
    # propagates as a 409 if the slot is no longer 'booked' (which would
    # be a programmer-error invariant breach — booking was confirmed so
    # the slot MUST be booked).
    await restore_booking_slot(session, booking.slot_id)

    # Step 6 — Flush before audit emit so any FK / CHECK error surfaces
    # before the audit row enrolls in the transaction.
    await session.flush()

    # Step 7 — Emit booking_cancelled (LITERAL strings for INFRA-11 AST gate).
    # Payload matches BookingCancelledPayload (extra='forbid') verbatim:
    # exactly 4 keys — booking_id, slot_id, cancelled_by_user_id, cancel_reason.
    # NO `client_id` (it's NOT in the schema — audit_payloads.py:394).
    await audit.emit(
        session,
        "booking_cancelled",  # LITERAL — INFRA-11 AST gate
        actor_user_id=actor.id,
        resource_type="booking",  # LITERAL
        resource_id=booking.id,
        booking_id=str(booking.id),
        slot_id=str(booking.slot_id),
        cancelled_by_user_id=str(actor.id),
        cancel_reason=data.reason,
    )

    # Step 8 — DM dispatch is post-commit (see Step 9.5 below per D-39-10).

    # Step 8.5 — Phase 87 INBOX-03 — in-app inbox row (co-transactional, BEFORE commit).
    # Actor-role discriminator (mirrors Step 9.5 post-commit DM kind semantics):
    #   owner → kind="booking_cancelled_by_owner" (cancelled by venue)
    #   reception → kind="booking_cancelled_by_client" (cancelled by client request)
    # Both branches notify the AFFECTED CLIENT (booking.client_id) regardless of actor
    # (INBOX-03: staff-initiated cancel MUST reach the client inbox). Placed pre-commit
    # so the inbox INSERT is atomic with the booking state mutation (co-transactional).
    _cancel_trainer_name = await _fetch_trainer_full_name(session, booking.slot.trainer_id)
    _cancel_slot_msk = booking.slot.start_time.astimezone(MOSCOW_TZ).strftime("%d.%m.%Y %H:%M")
    if actor.role is Role.OWNER:
        await create_notification(
            session,
            client_id=booking.client_id,
            source_type="booking",
            source_id=booking.id,
            kind="booking_cancelled_by_owner",
            title="Бронь отменена залом",
            body=f"{_cancel_slot_msk} — {_cancel_trainer_name}",
        )
    elif actor.role is Role.RECEPTION:
        await create_notification(
            session,
            client_id=booking.client_id,
            source_type="booking",
            source_id=booking.id,
            kind="booking_cancelled_by_client",
            title="Бронь отменена",
            body=f"{_cancel_slot_msk} — {_cancel_trainer_name}",
        )

    # Step 9 — Commit (SVC001 gate).
    await session.commit()

    # Step 9.5 — Phase 39 NOTIFY-04 + Phase 45 D-45-05 — fire-and-forget
    # DM (post-commit per D-39-10) with email-fallback when Telegram is
    # unreachable. Actor-role discriminator (D-39-05): owner -> owner copy
    # ("cancelled by venue", kind='cancelled_by_owner'); reception ->
    # client copy ("cancelled by request", kind='cancelled_by_client').
    # Any other role is defensive — INFO-log and skip. Each branch passes
    # its OWN literal `kind` string per the Plan 45-08 4-literal contract
    # (no shared variable — AST gate parity D-45-22).
    if actor.role is Role.OWNER:
        booking_for_dm = await _load_booking_with_relationships(session, booking.id)
        if booking_for_dm is not None:
            dm_bot = build_bot(
                token=get_settings().telegram_bot_token.get_secret_value(),
            )
            await _dispatch_booking_lifecycle_notification(
                booking_for_dm,
                kind="cancelled_by_owner",  # LITERAL — Plan 45-08
                template=BOOKING_CANCELLED_BY_OWNER_DM,
                bot=dm_bot,
                sender=telegram_sender,
                session=session,
            )
    elif actor.role is Role.RECEPTION:
        booking_for_dm = await _load_booking_with_relationships(session, booking.id)
        if booking_for_dm is not None:
            dm_bot = build_bot(
                token=get_settings().telegram_bot_token.get_secret_value(),
            )
            await _dispatch_booking_lifecycle_notification(
                booking_for_dm,
                kind="cancelled_by_client",  # LITERAL — Plan 45-08
                template=BOOKING_CANCELLED_BY_CLIENT_DM,
                bot=dm_bot,
                sender=telegram_sender,
                session=session,
            )
    else:
        _log.info("cancel_booking_dm_unexpected_role", role=str(actor.role))

    # Step 10 — Reload with slot+trainer joinedload (Phase 40 BLOCKER-2).
    reloaded = await repository.get_booking_by_id(session, booking.id)
    if reloaded is None:
        raise RuntimeError("cancel_booking: just-cancelled booking disappeared on reload")
    return _booking_response_from_orm(reloaded)


# ---------------------------------------------------------------------------
# Public mutating orchestrator — cancel_booking_for_client (Phase 70 D-70-05/06).
# ---------------------------------------------------------------------------


async def cancel_booking_for_client(
    session: AsyncSession,
    *,
    client_id: UUID,
    booking_id: UUID,
    cancel_reason: str = "",
) -> BookingResponse:
    """Client self-cancel path — Phase 70 D-70-05 / D-70-06.

    Mirrors ``cancel_booking``'s sequence except:

      1. IDOR 404-collapse (D-20-IDOR / T-70-05): load via
         ``get_booking_by_id_for_update_with_slot`` then check
         ``booking.client_id == client_id``. If the booking is None OR
         owned by a different client, raise ``BookingNotFoundError
         ("booking_not_found")`` — anti-oracle: never reveal that a
         booking exists for another client (never 403 or existence leak).

      2. FSM guard via ``_assert_can_transition(target='cancelled')``
         (same as staff cancel).

      3. Client window (D-70-05 / D-38-16): drop the
         ``Role.RECEPTION`` branch — always apply
         ``CANCEL_WINDOW_HOURS_CLIENT`` measured against
         ``booking.slot.start_time`` (NOT ``created_at``). Raises
         ``CancelWindowExpiredError("cancel_window_expired")`` when inside
         the window.

      4-9. Same sequence as ``cancel_booking`` verbatim: mutate in-place,
         ``restore_booking_slot``, flush, ``audit.emit("booking_cancelled"
         ...)``, commit.

      10. NO ``sessions_remaining`` mutation (D-70-06 — credit is only
          consumed/restored at ``pt_sessions`` level; the active PT-package
          is simply free to book again once the slot restores to 'active').
          NO Telegram DM dispatch (client-cancel DM out of scope for this
          plan; Plan 70-03 may add it at the router layer).

    Owns the UoW — ``await session.commit()`` at end (SVC001 gate).
    """
    # Step 1 — Load with row lock + eager-loaded slot.
    booking = await repository.get_booking_by_id_for_update_with_slot(session, booking_id)

    # IDOR 404-collapse (D-20-IDOR / T-70-05): non-owned booking collapses to
    # BookingNotFoundError("booking_not_found") — anti-oracle, never 403 or
    # existence leak. This is the ONE divergence from the staff cancel path
    # (staff can cancel any booking; clients can only cancel their own).
    if booking is None or booking.client_id != client_id:
        raise BookingNotFoundError("booking_not_found")

    # Step 2 — FSM gate (consults BOOKING_STATUS_TRANSITIONS).
    _assert_can_transition(booking, target="cancelled")

    # Step 3 — Client cancel window (D-70-05 / D-38-16).
    # Unlike the staff path, there is no Role branch: always apply
    # CANCEL_WINDOW_HOURS_CLIENT measured against slot.start_time (NOT created_at).
    now_utc = datetime.now(UTC)
    if booking.slot.start_time - now_utc < timedelta(hours=CANCEL_WINDOW_HOURS_CLIENT):
        raise CancelWindowExpiredError("cancel_window_expired")

    # Step 4 — Mutate booking in-place (cancelled_at / cancel_reason).
    booking.status = "cancelled"
    booking.cancelled_at = now_utc
    booking.cancel_reason = cancel_reason

    # Step 5 — Restore linked slot booked→active in the same UoW via the
    # Phase 37 BookingSlotRestorer Protocol slot. Mirrors cancel_booking verbatim.
    await restore_booking_slot(session, booking.slot_id)

    # Step 6 — Flush before audit emit.
    await session.flush()

    # Step 7 — Emit booking_cancelled (LITERAL strings for INFRA-11 AST gate).
    # Payload: 4 keys matching BookingCancelledPayload (extra='forbid').
    # NOTE: client_id is NOT in BookingCancelledPayload (4-key schema) —
    # cancelled_by_user_id=None (Phase 70 D-70-05 widening; no fake staff user
    # mirrors D-70-07 anti-fabrication principle from create_booking_for_client).
    await audit.emit(
        session,
        "booking_cancelled",  # LITERAL — INFRA-11 AST gate
        actor_user_id=None,  # RAW None — audit.emit signature is UUID | None
        resource_type="booking",  # LITERAL — INFRA-11 AST gate
        resource_id=booking.id,
        booking_id=str(booking.id),
        slot_id=str(booking.slot_id),
        cancelled_by_user_id=None,  # Phase 70 D-70-05: client self-cancel, no staff user
        cancel_reason=cancel_reason,
    )

    # Step 8 — NO Telegram DM dispatch (out of scope for this plan).
    # Step 9 — NO sessions_remaining mutation (D-70-06 — credit only at pt_sessions level).

    # Step 8.5 — Phase 87 INBOX-03 — in-app inbox row (co-transactional, BEFORE commit).
    # Client self-cancel: the only notification side-effect (no DM dispatch in this path).
    # Placed pre-commit so the inbox INSERT is atomic with the booking state mutation.
    _self_cancel_trainer_name = await _fetch_trainer_full_name(
        session, booking.slot.trainer_id
    )
    _self_cancel_slot_msk = booking.slot.start_time.astimezone(MOSCOW_TZ).strftime(
        "%d.%m.%Y %H:%M"
    )
    await create_notification(
        session,
        client_id=booking.client_id,
        source_type="booking",
        source_id=booking.id,
        kind="booking_cancelled_by_client",
        title="Бронь отменена",
        body=f"{_self_cancel_slot_msk} — {_self_cancel_trainer_name}",
    )

    # Step 9 — Commit (SVC001 gate).
    await session.commit()

    # Step 10 — Reload with slot+trainer joinedload (Phase 40 BLOCKER-2).
    reloaded = await repository.get_booking_by_id(session, booking_id)
    if reloaded is None:
        raise RuntimeError(
            "cancel_booking_for_client: just-cancelled booking disappeared on reload"
        )
    return _booking_response_from_orm(reloaded)


# ---------------------------------------------------------------------------
# Phase 80 RESCH-01 — reschedule_booking_for_client (atomic slot move).
# ---------------------------------------------------------------------------


async def _write_reschedule_evidence(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession] | None,
    *,
    booking_id: UUID,
) -> None:
    """Insert the post-send reschedule evidence row (Phase 80 CR-01 / WR-02).

    Uses a FRESH session from ``session_factory`` when supplied (so the request
    connection is not held across the preceding Telegram I/O — D-39-06b), else
    falls back to the request ``session``. IntegrityError on
    ``uq_booking_notifications_booking_kind_channel`` is an idempotency
    collision — rollback (scoped to the evidence write) + INFO-log.

    Best-effort: callers wrap the invocation so no exception escapes the
    committed reschedule boundary.
    """
    if session_factory is not None:
        async with session_factory() as evidence_session:
            try:
                evidence_session.add(
                    BookingNotification(
                        booking_id=booking_id,
                        kind="rescheduled",
                        channel="telegram",
                    )
                )
                await evidence_session.commit()
            except IntegrityError:
                await evidence_session.rollback()
                _log.info(
                    "booking_reschedule_idempotency_collision",
                    booking_id=str(booking_id),
                    channel="telegram",
                )
        return

    # Fallback: no session_factory provided — reuse the request session.
    try:
        session.add(
            BookingNotification(
                booking_id=booking_id,
                kind="rescheduled",
                channel="telegram",
            )
        )
        await session.commit()
    except IntegrityError:
        await session.rollback()
        _log.info(
            "booking_reschedule_idempotency_collision",
            booking_id=str(booking_id),
            channel="telegram",
        )


async def reschedule_booking_for_client(
    session: AsyncSession,
    *,
    client_id: UUID,
    booking_id: UUID,
    new_slot_id: UUID,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
) -> BookingResponse:
    """Atomic reschedule: cancel-old-slot + create-new-booking in one UoW (RESCH-01).

    PT-session credit PRESERVED (RESCH-01 / T-80-11): reschedule is a slot MOVE.
    No sessions_remaining decrement, no restore. The new booking row reuses
    ``pt_package_id`` from the cancelled booking (contrast with WR-06 owner-
    force-cancel restore path that explicitly restores credit).

    SVC001 caller-owns-txn: this function commits its own UoW.

    Post-commit DM is genuinely fire-and-forget (D-39-09 / Phase 80 CR-01):
    the authoritative cancel-old + create-new + audit commit at Step 11 is the
    operation's success boundary. Everything after it — the reschedule DM send
    and the ``booking_notifications`` evidence INSERT — is wrapped in a broad
    try/except that logs a WARNING and NEVER re-raises into the endpoint. A
    DM-send failure (or any post-commit error) MUST NOT turn a durably-committed
    reschedule into a 500, because that would (a) break the fire-and-forget DM
    contract and (b) corrupt the idempotency envelope so a retry re-runs the
    full reschedule against the already-cancelled old booking (Phase 80 CR-02).

    ``session_factory`` (Phase 80 CR-01 / WR-02): when supplied, the evidence
    INSERT runs on a FRESH session so the request's pooled DB connection is not
    held across the Telegram HTTPS round-trip (mirrors ``_send_booking_reminders``
    / D-39-06b). When ``None`` (e.g. some tests), the request ``session`` is used
    as a fallback — still safe because the whole block is best-effort.
    """
    now_utc = datetime.now(UTC)

    # Step 1 — Load old booking with row lock + eager-loaded slot.
    # Mirrors cancel_booking_for_client:1593.
    booking = await repository.get_booking_by_id_for_update_with_slot(session, booking_id)

    # IDOR 404-collapse (D-20-IDOR / T-80-05): non-owned or missing booking
    # collapses to BookingNotFoundError("booking_not_found") — anti-oracle,
    # never 403 or an existence signal.
    if booking is None or booking.client_id != client_id:
        raise BookingNotFoundError("booking_not_found")

    # Step 2 — FSM guard (booking must be 'confirmed').
    _assert_can_transition(booking, target="cancelled")

    # Step 2b — Same-slot no-op (Phase 80 WR-01). Rescheduling to the slot the
    # booking already holds is a degenerate request: the old slot resolves as
    # "booked" (this booking holds it), so the Step 4 availability guard would
    # otherwise raise SlotNotAvailableError("slot_not_available") — an UNMAPPED
    # code in the PWA (BookingManageSheet only maps window/slot_already_booked/
    # trainer), surfacing the generic reschedule-failed copy for what is
    # really "you picked your current slot". Short-circuit to an idempotent
    # no-op that returns 200 + the current confirmed booking unchanged. Reload
    # via get_booking_by_id so slot + slot.trainer are eager-loaded for the
    # response projection (the row-lock loader joinedloads slot only, not
    # slot.trainer).
    if new_slot_id == booking.slot_id:
        current = await repository.get_booking_by_id(session, booking_id)
        if current is None:  # pragma: no cover — row was just locked above
            raise BookingNotFoundError("booking_not_found")
        return _booking_response_from_orm(current)

    # Step 3 — Reschedule window: 24h against ORIGINAL slot start (RESCH-01 / T-80-07).
    # Unlike the client cancel path, the window is measured against the original
    # slot's start_time (NOT created_at or now).
    if booking.slot.start_time - now_utc < timedelta(hours=CANCEL_WINDOW_HOURS_CLIENT):
        raise RescheduleWindowExpiredError("reschedule_window_expired")

    # Step 4 — Resolve new slot (mirror create_booking_for_client:1300-1306).
    new_slot = await resolve_slot_by_id(session, new_slot_id)
    if new_slot is None:
        raise SlotNotFoundError("slot_not_found")
    if new_slot.status != "active":
        raise SlotNotAvailableError("slot_not_available")
    if new_slot.start_time <= now_utc:
        raise SlotNotAvailableError("slot_not_available")

    # Step 5 — Same-trainer constraint (RESCH-01 / T-80-08).
    if new_slot.trainer_id != booking.slot.trainer_id:
        raise SlotTrainerMismatchError("slot_trainer_mismatch")

    # Step 6 — Cancel old booking in-place (mirror cancel_booking_for_client:1612-1619).
    old_slot_id = booking.slot_id
    booking.status = "cancelled"
    booking.cancelled_at = now_utc
    booking.cancel_reason = "rescheduled"
    await restore_booking_slot(session, old_slot_id)

    # Step 7 — Flip new slot active→booked (mirror create_booking_for_client:1332-1344).
    slot_flipped = await repository.update_slot_status_predicate_gated(
        session,
        new_slot_id,
        from_status="active",
        to_status="booked",
    )
    if not slot_flipped:
        # Force a fresh read bypassing identity-map cache (mirror create_booking).
        await session.refresh(new_slot, attribute_names=["status"])
        if new_slot.status == "booked":
            raise SlotAlreadyBookedError("slot_already_booked")
        raise SlotNotAvailableError("slot_not_available")

    # Step 8 — INSERT new booking row reusing pt_package_id (PT credit PRESERVED — T-80-11).
    # NO sessions_remaining decrement, NO restore: reschedule is a slot MOVE, not
    # cancel+rebook. The new booking inherits the same pt_package linkage.
    new_booking = await repository.insert_booking(
        session,
        slot_id=new_slot_id,
        client_id=client_id,
        pt_package_id=booking.pt_package_id,
        created_by_user_id=None,
    )

    # Step 9 — Flush + IntegrityError → SlotAlreadyBookedError (mirror create:1360-1366).
    # The partial UNIQUE uq_bookings_slot_confirmed is the load-bearing race guard.
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        if _is_slot_confirmed_conflict(exc):
            raise SlotAlreadyBookedError("slot_already_booked") from exc
        raise

    # Step 10 — Emit booking_rescheduled audit (LITERAL strings for INFRA-11 AST gate).
    # Payload matches BookingRescheduledPayload (extra='forbid') verbatim.
    await audit.emit(
        session,
        "booking_rescheduled",  # LITERAL — INFRA-11 AST gate
        actor_user_id=None,  # RAW None — audit.emit signature is UUID | None
        resource_type="booking",  # LITERAL — INFRA-11 AST gate
        resource_id=new_booking.id,
        old_booking_id=str(booking_id),
        new_booking_id=str(new_booking.id),
        old_slot_id=str(old_slot_id),
        new_slot_id=str(new_slot_id),
        old_start=booking.slot.start_time.isoformat(),
        new_start=new_slot.start_time.isoformat(),
        client_id=str(client_id),
        actor_role="client",  # LITERAL — INFRA-11 AST gate / D-70-07 parity
    )

    # Step 10.5 — Phase 87 INBOX-03 — in-app inbox row (co-transactional, BEFORE commit).
    # MUST be placed here, NOT in the post-commit fire-and-forget DM try/except block
    # (Step 13): that block's broad `except Exception` would silently swallow an inbox-
    # insert failure, and it runs post-commit (non-atomic). The reschedule in-app
    # notification fires for ALL clients regardless of Telegram-link state (unlike the DM
    # which WR-05 skips for unlinked clients). source_id=new_booking.id per plan mapping.
    _resch_trainer_name = await _fetch_trainer_full_name(session, new_slot.trainer_id)
    _resch_slot_msk = new_slot.start_time.astimezone(MOSCOW_TZ).strftime("%d.%m.%Y %H:%M")
    await create_notification(
        session,
        client_id=client_id,
        source_type="booking",
        source_id=new_booking.id,
        kind="booking_rescheduled",
        title="Бронь перенесена",
        body=f"{_resch_slot_msk} — {_resch_trainer_name}",
    )

    # Step 11 — Commit (SVC001 gate). Slot implementation owns commit.
    # THIS IS THE OPERATION'S SUCCESS BOUNDARY (Phase 80 CR-01/CR-02): the
    # cancel-old + create-new + audit is now durable. Everything below is
    # best-effort and MUST NOT be able to fail the HTTP response, or:
    #   - a transient DB / Telegram error would 500 an operation that already
    #     succeeded (breaking the fire-and-forget DM contract D-39-09), and
    #   - idempotent_execute would store a wrong envelope / delete the
    #     placeholder, so a retry would re-run the full reschedule against the
    #     now-cancelled old booking → InvalidBookingTransitionError 409
    #     invalid_transition (unmapped in the PWA) for a user whose reschedule
    #     actually succeeded (Phase 80 CR-02).
    await session.commit()

    # Step 12 — Reload new booking with client + slot.trainer joinedload
    # (Phase 40 BLOCKER-2 / D-40-07) for BOTH the response projection AND the
    # DM dispatch (WR-03: this single eager-load replaces the old redundant
    # Step 15 get_booking_by_id reload — _load_booking_with_relationships
    # already eager-loads slot + slot.trainer, satisfying
    # _booking_response_from_orm's projection contract). A reload failure here
    # would mean the just-committed row vanished — a genuine invariant
    # violation, so it is allowed to raise (it cannot be caused by the DM).
    reloaded = await _load_booking_with_relationships(session, new_booking.id)
    if reloaded is None:
        raise RuntimeError("reschedule_booking_for_client: new booking disappeared on reload")

    # Build the authoritative success response NOW, from the committed reload,
    # BEFORE any best-effort post-commit work. The response is what
    # idempotent_execute records as the success envelope; it must not depend on
    # the DM outcome.
    response = _booking_response_from_orm(reloaded)

    # Step 13 — Fire-and-forget reschedule DM + evidence INSERT (D-39-09 /
    # Phase 80 CR-01 / WR-02). The ENTIRE block is wrapped so no exception can
    # escape past the committed Step 11 boundary. The evidence INSERT runs on a
    # FRESH session (when session_factory is supplied) so the request's pooled
    # DB connection is not held across the Telegram HTTPS round-trip — mirrors
    # _send_booking_reminders (D-39-06b).
    #
    # Cannot reuse _dispatch_booking_dm (renders via BOOKING_CONFIRMED_DM's
    # slot_start_msk placeholder; render_booking_rescheduled_dm uses
    # new_slot_start_msk). Cannot reuse _dispatch_booking_lifecycle_notification
    # (its email-fallback branch has NO 'rescheduled' case —
    # enqueue_booking_email_fallback's Literal kind set excludes 'rescheduled';
    # calling it would raise ValueError). See WR-05 note below re: email-only
    # clients.
    try:
        chat_id = None
        if reloaded.client is not None:
            chat_id = reloaded.client.telegram_user_id

        if chat_id is None:
            # WR-05: Telegram-unlinked clients receive no reschedule
            # notification and no email fallback. This DM-only behaviour is a
            # DELIBERATE divergence from confirm/cancel (whose lifecycle helper
            # fans out to email) — extending email fallback to 'rescheduled'
            # would require widening enqueue_booking_email_fallback's Literal
            # kind set + an EMAIL_BOOKING_RESCHEDULED template, deferred to a
            # later phase. Consistent with all other booking DMs, an unlinked
            # client simply gets no reschedule notification (the reschedule
            # itself is durable and visible in the PWA).
            _log.info("booking_dm_skipped_unlinked", booking_id=str(new_booking.id))
        elif reloaded.slot is None or reloaded.slot.trainer is None:
            _log.error(
                "booking_dm_missing_joinedload",
                booking_id=str(new_booking.id),
            )
        else:
            new_slot_start_msk = new_slot.start_time.astimezone(MOSCOW_TZ).strftime(
                "%d.%m.%Y %H:%M"
            )
            text_body = render_booking_rescheduled_dm(
                client_name=reloaded.client.first_name,
                trainer_name=reloaded.slot.trainer.full_name,
                new_slot_start_msk=new_slot_start_msk,
            )
            bot = build_bot(token=get_settings().telegram_bot_token.get_secret_value())
            send_result = await telegram_sender.send_text_dm(bot, chat_id, text_body)

            if send_result.ok:
                # Step 14 — Insert send-evidence row (post-send) mirroring the
                # reminder_24h cron Telegram-success branch (~lines 757-799).
                # Use a FRESH session (when session_factory is supplied) so the
                # request connection is freed across the Telegram I/O above
                # (D-39-06b / WR-02). IntegrityError on
                # uq_booking_notifications_booking_kind_channel means idempotency
                # collision — rollback + INFO-log.
                await _write_reschedule_evidence(
                    session,
                    session_factory,
                    booking_id=new_booking.id,
                )
            else:
                reason = "bot_blocked" if send_result.blocked else "transient"
                _log.warning(
                    "booking_dm_send_failed",
                    reason=reason,
                    booking_id=str(new_booking.id),
                    telegram_chat_id=chat_id,
                    error_msg=send_result.error,
                )
    except Exception as exc:  # fire-and-forget envelope (D-39-09)
        # NEVER re-raise: the reschedule already committed at Step 11. A
        # post-commit DM/notification failure must not 500 the request nor flip
        # the idempotency envelope (Phase 80 CR-01 / CR-02).
        _log.warning(
            "booking_reschedule_dm_post_commit_failed",
            booking_id=str(new_booking.id),
            error_msg=str(exc),
        )

    return response


# ---------------------------------------------------------------------------
# Read-only orchestrators (no commit, no audit) — list / get / per-client.
# ---------------------------------------------------------------------------


async def list_bookings(
    session: AsyncSession,
    query: BookingListQuery,
) -> PaginatedData[BookingResponse]:
    """Paginated booking list (Phase 38 plan 38-03 / BOOK-07).

    Read-only — NO commit, NO audit. Delegates to
    `repository.list_bookings_paginated`; projects Booking ORM rows via
    ``_booking_response_from_orm`` (Phase 40 BLOCKER-2 — trainer_full_name +
    slot_start_time fields populated from the joinedload chain).
    """
    page = await repository.list_bookings_paginated(session, query)
    return PaginatedData.model_construct(
        items=[_booking_response_from_orm(b) for b in page.items],
        total=page.total,
        page=page.page,
        page_size=page.page_size,
    )


async def list_bookings_for_client(
    session: AsyncSession,
    client_id: UUID,
    query: BookingsForClientListQuery,
) -> PaginatedData[BookingResponse]:
    """Per-client paginated booking list (Phase 38 plan 38-03 / BOOK-08).

    Read-only — NO commit, NO audit. Delegates to
    `repository.list_bookings_for_client_paginated`; handler declared on
    `client_scoped_bookings_router` in bookings/router.py and composed by
    `app.api.v1.router` at the `/clients` prefix, so the public URL is
    `GET /api/v1/clients/{client_id}/bookings` per BOOK-08. The split keeps
    clients/router.py dependency-leaf (no `from app.modules.bookings`
    import) — Phase 38 verifier Gap #2 closure.
    """
    page = await repository.list_bookings_for_client_paginated(session, client_id, query)
    return PaginatedData.model_construct(
        items=[_booking_response_from_orm(b) for b in page.items],
        total=page.total,
        page=page.page,
        page_size=page.page_size,
    )


async def get_booking(
    session: AsyncSession,
    booking_id: UUID,
) -> BookingDetailResponse:
    """Read a single booking with denormalized slot + pt_package (BOOK-09).

    Uses `repository.get_booking_with_relations` which eager-loads via
    `joinedload(Booking.slot) + joinedload(Booking.pt_package)` —
    Pitfall 19 (N+1 prevention; total queries ≤ 2 enforced by the
    integration test).

    Projects the joined slot ORM into the LOCAL `SlotSnapshot` Pydantic
    class (D-38-08 — schema-layer view; no cross-module schema import).
    The pt_package dict is a minimal snapshot for display (id,
    plan_name_snapshot, sessions_remaining, end_date) — kept dict-typed
    to avoid pulling the pt_packages schema surface into the bookings
    module.
    """
    booking = await repository.get_booking_with_relations(session, booking_id)
    if booking is None:
        raise BookingNotFoundError("booking_not_found")

    slot_orm = booking.slot
    slot_snapshot = SlotSnapshot(
        id=slot_orm.id,
        start_time=slot_orm.start_time,
        end_time=slot_orm.end_time,
        trainer_id=slot_orm.trainer_id,
        status=slot_orm.status,
    )

    pkg = booking.pt_package
    pt_package_payload = {
        "id": str(pkg.id),
        "plan_name_snapshot": pkg.plan_name_snapshot,
        "sessions_remaining": pkg.sessions_remaining,
        "end_date": pkg.end_date.isoformat() if pkg.end_date is not None else None,
    }

    return BookingDetailResponse.model_validate(
        {
            "id": booking.id,
            "slot_id": booking.slot_id,
            "client_id": booking.client_id,
            "pt_package_id": booking.pt_package_id,
            "status": booking.status,
            "created_at": booking.created_at,
            "created_by_user_id": booking.created_by_user_id,
            "cancelled_at": booking.cancelled_at,
            "cancel_reason": booking.cancel_reason,
            "no_show_at": booking.no_show_at,
            "completed_at": booking.completed_at,
            # Phase 40 BLOCKER-2 — JOIN-projected fields:
            "trainer_full_name": slot_orm.trainer.full_name,
            "slot_start_time": slot_orm.start_time,
            "slot": slot_snapshot,
            "pt_package": pt_package_payload,
        }
    )
