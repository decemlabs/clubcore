"""PT-sessions service — orchestration between router and repository (Phase 34).

PT-sessions are orthogonal to visits (PT-20 / Q3 default): recording does NOT
INSERT into visits; check-in does NOT INSERT into pt_sessions. Enforced by
ABSENCE — no service code in this file touches visits.

D-34-11a carve-out: `cancel_pt_session` (Plan 34-03) performs a reverse
transition `exhausted → active` on the parent pt_package via raw `text()` SQL
predicate-gated UPDATE in `pt_sessions.repository`. This bypass is NOT in the
global `PT_PACKAGE_STATUS_TRANSITIONS` FSM (Phase 33 D-33-04 is forward-only).
The locally-scoped invariant "we just freed one balance unit from an
exhausted package" makes the reverse flip safe under `WHERE status='exhausted'`.

D-34-04a: ALL cross-module SQL against `pt_packages` uses raw `text()` from
`pt_sessions.repository` (NEVER `from app.modules.pt_packages import ...`)
to keep the `modules-independent` importlinter contract clean.

Discipline invariants (Phase 30 walkers must remain green):
  - SVC001 caller-owns-txn (`tests/unit/test_service_commit_gate.py`):
    every public mutating orchestrator MUST end with `await session.commit()`.
  - audit.emit literal-string AST gate (INFRA-11 /
    `tests/unit/test_audit_taxonomy.py`): every `emit()` call uses literal
    strings for `event` and `resource_type`.
  - audit_payloads.py `extra='forbid'` validation (D-30-03): emit kwargs
    MUST match `PtSessionRecordedPayload` / `PtSessionCancelledPayload` /
    `PtPackageExhaustedPayload` schemas verbatim.

Plan 34-01 lands the module-level docstring + import surface + error class
hierarchy only. Public orchestrators are filled by 34-02 / 34-03:
  - 34-02: `record_pt_session` (PT-15 / PT-16 / PT-17).
  - 34-03: `cancel_pt_session` (PT-18), `get_pt_session` (PT-19),
    `list_sessions_by_pt_package` (PT-19).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core import audit
from app.core.dependencies import (
    CurrentUser,
    complete_booking_by_pt_session,
    resolve_trainer_by_id,
)
from app.core.exceptions import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    ValidationAppError,
)
from app.core.pagination import PaginatedData
from app.core.permissions import Role
from app.modules.pt_sessions import repository
from app.modules.pt_sessions.constants import (
    BACKDATING_WINDOW_DAYS_RECEPTION,
    CANCEL_WINDOW_HOURS_RECEPTION,
)
from app.modules.pt_sessions.schemas import (
    PtSessionCancelRequest,
    PtSessionCreateRequest,
    PtSessionListByPackageQuery,
    PtSessionResponse,
)

# ---------------------------------------------------------------------------
# Error classes (D-34-18 catalogue).
#
# Mirror pt_packages.service error-class hierarchy. Each class carries a
# stable `code` (translated by the global exception handler into the
# response envelope `{error.code}` field) and an HTTP `status_code`.
# ---------------------------------------------------------------------------


class PtSessionNotFoundError(NotFoundError):
    """Raised by cancel_pt_session / get_pt_session when the id does not exist."""

    code = "pt_session_not_found"
    status_code = 404


class PtPackageNotFoundError(NotFoundError):
    """Raised when fetch_pt_package_metadata returns None
    (record_pt_session / cancel_pt_session pre-mutation guard)."""

    code = "pt_package_not_found"
    status_code = 404


class PtPackageNotActiveError(ConflictError):
    """Raised when fetch_pt_package_metadata returns status != 'active'
    (record_pt_session pre-decrement guard; race-loser uses
    PtPackageExhaustedError instead)."""

    code = "pt_package_not_active"
    status_code = 409


class PtPackageExhaustedError(ConflictError):
    """Raised when atomic_decrement_pt_package returns None — i.e. the
    `sessions_remaining > 0 AND status='active'` predicate excluded the row
    (PT-16 / D-34-04a race-loser path)."""

    code = "pt_package_exhausted"
    status_code = 409


class TrainerNotFoundError(NotFoundError):
    """Raised by record_pt_session when the TrainerById Protocol slot
    resolves to None for `trainer_id`."""

    code = "trainer_not_found"
    status_code = 404


class TrainerInactiveError(ValidationAppError):
    """Raised by record_pt_session when the resolved trainer has
    `is_active=False`. 422 (semantic-validation) not 409 (state-conflict)
    per Phase 31 convention."""

    code = "trainer_inactive"
    status_code = 422


class PerformedAtInFutureError(ValidationAppError):
    """Raised by record_pt_session when `performed_at > datetime.now(UTC)`.
    Applies to BOTH roles (owner-unlimited is past-direction only —
    D-34-06). Distinct from `performed_at_out_of_window` for UI clarity."""

    code = "performed_at_in_future"
    status_code = 422


class PerformedAtOutOfWindowError(ValidationAppError):
    """Raised by record_pt_session when reception backdates more than
    BACKDATING_WINDOW_DAYS_RECEPTION (B-11 / D-34-06). Owner unlimited
    in the past direction."""

    code = "performed_at_out_of_window"
    status_code = 422


class PtSessionAlreadyCancelledError(ConflictError):
    """Raised by cancel_pt_session when `cancelled_at IS NOT NULL`
    already. Idempotency-Key replay returns the cached envelope first
    (D-34-10); this is the second-line guard for different keys against
    the same row."""

    code = "already_cancelled"
    status_code = 409


class CancelWindowExpiredError(ForbiddenError):
    """Raised by cancel_pt_session when reception attempts to cancel
    >CANCEL_WINDOW_HOURS_RECEPTION after `created_at` (B-12 / D-34-07).
    Owner is anytime. 403 not 409 — actor authorisation issue, not state
    conflict (mirrors OWNER_ONLY 403 mapping convention)."""

    code = "cancel_window_expired"
    status_code = 403


# Phase 38 PKG-04 / PKG-05 — booking validation error classes (mirror
# bookings/service.py shape; surface as 4xx via the global exception handler).


class BookingNotFoundError(NotFoundError):
    """Raised by record_pt_session when the supplied booking_id does not
    exist in the bookings table (Phase 38 PKG-04)."""

    code = "booking_not_found"
    status_code = 404


class BookingNotConfirmedError(ConflictError):
    """Raised by record_pt_session when the booking row's status is not
    'confirmed' (cancelled, completed, no_show). Defence-in-depth ahead of
    the predicate-gated UPDATE in bookings.service.complete_booking — the
    pre-check provides a clearer error code than the FSM 409 invalid_transition
    surface from complete_booking (Phase 38 PKG-05 / T-38-05-02)."""

    code = "booking_not_confirmed"
    status_code = 409


class BookingMismatchError(ConflictError):
    """Raised by record_pt_session when either
    booking.pt_package_id != request.pt_package_id OR
    slot.trainer_id != request.trainer_id (PKG-04 / T-38-05-03).
    Server-side mismatch — caller's booking_id does not match the package
    or trainer combination of the request. Surfaces as 409 (state-conflict)
    not 422 (semantic-validation) because the booking row exists and is
    confirmed; the conflict is cross-row, not field-shape."""

    code = "booking_mismatch"
    status_code = 409


# ---------------------------------------------------------------------------
# Public orchestrators (Plan 34-02: record_pt_session).
# ---------------------------------------------------------------------------


async def record_pt_session(
    session: AsyncSession,
    actor: CurrentUser,
    data: PtSessionCreateRequest,
) -> PtSessionResponse:
    """Record a PT-session (PT-15 / PT-16 / PT-17). Reception+owner.

    10-step orchestrator (mirrors ``pt_packages.create_pt_package`` recipe):

      1. Validate ``performed_at`` — both roles reject future-dated (422
         ``performed_at_in_future``); reception >7d back → 422
         ``performed_at_out_of_window`` (D-34-06 / B-11; owner unlimited).
      2. Resolve trainer via ``TrainerById`` Protocol slot (D-34-12a) —
         404 ``trainer_not_found`` / 422 ``trainer_inactive``. The
         resolved object exposes ``full_name`` for B-05 snapshot capture.
      3. Read pt_package metadata via raw text() SELECT
         (``fetch_pt_package_metadata``, D-34-13a) — 404
         ``pt_package_not_found`` / 409 ``pt_package_not_active``.
      4. Race-safe atomic decrement (``atomic_decrement_pt_package``,
         D-34-04a / PT-16) — ``None`` → 409 ``pt_package_exhausted``
         (race-loser path; the DB row-lock + predicate is sole arbiter).
      5. Insert pt_sessions row with
         ``trainer_name_snapshot=trainer.full_name`` (B-05) and
         ``client_id`` sourced from the parent package (NOT request body).
      6. ``session.flush()`` to surface FK / CHECK errors BEFORE audit emit.
      7. ``audit.emit('pt_session_recorded', ...)`` — payload matches
         ``PtSessionRecordedPayload`` (extra='forbid') verbatim;
         UUID/datetime cast to str/isoformat for JSONB serialisability.
      8. If ``new_remaining == 0`` →
         ``atomic_transition_to_exhausted`` + emit
         ``pt_package_exhausted`` ONCE (D-34-05 / PT-17).
      9. ``await session.commit()`` (SVC001 caller-owns-txn gate).
     10. Narrow ``refresh`` on the row + return ``PtSessionResponse``.
    """
    # Step 1 — performed_at window guards (D-34-06).
    now = datetime.now(UTC)
    delta = now - data.performed_at
    if delta.total_seconds() < 0:
        raise PerformedAtInFutureError("performed_at_in_future")
    if actor.role == Role.RECEPTION and delta > timedelta(
        days=BACKDATING_WINDOW_DAYS_RECEPTION,
    ):
        raise PerformedAtOutOfWindowError("performed_at_out_of_window")

    # Step 2 — Trainer via TrainerById Protocol slot (D-34-12a).
    trainer = await resolve_trainer_by_id(session, data.trainer_id)
    if trainer is None:
        raise TrainerNotFoundError("trainer_not_found")
    if not trainer.is_active:
        raise TrainerInactiveError("trainer_inactive")

    # Phase 38 PKG-04 — booking validation (D-38-11 / D-38-19 / Pitfall 12).
    # Lock order: booking → pt_package → pt_session insert. We MUST acquire
    # the booking row-lock BEFORE the pt_package SELECT FOR UPDATE
    # decrement below so all callers serialise on the same order — prevents
    # AB/BA deadlocks if the future Phase 39 no-show cron ever holds the
    # pt_package side of a lock (defensive: today the cron only touches
    # bookings, but ordering discipline future-proofs T-38-05-05).
    #
    # The FOR UPDATE clause on the booking row is the load-bearing piece
    # for D-38-19 / Pitfall 12: it blocks any concurrent UPDATE (notably
    # the Phase 39 no-show cron's batch UPDATE bookings SET status='no_show')
    # until this UoW commits. Postgres-only row-level lock; the cron's
    # competing UPDATE waits, sees status='completed' after our commit, and
    # the cron's WHERE status='confirmed' predicate filters us out.
    booking_meta: dict[str, Any] | None = None
    if data.booking_id is not None:
        booking_meta = await repository.fetch_booking_metadata_for_update(
            session,
            data.booking_id,
        )
        if booking_meta is None:
            raise BookingNotFoundError("booking_not_found")
        if booking_meta["status"] != "confirmed":
            raise BookingNotConfirmedError("booking_not_confirmed")
        if booking_meta["pt_package_id"] != data.pt_package_id:
            raise BookingMismatchError("booking_mismatch")
        slot_trainer_id = await repository.fetch_slot_trainer_id(
            session,
            booking_meta["slot_id"],
        )
        if slot_trainer_id != data.trainer_id:
            raise BookingMismatchError("booking_mismatch")

    # Step 3 — pt_package metadata (D-34-13a raw SQL — id-as-input).
    pkg = await repository.fetch_pt_package_metadata(session, data.pt_package_id)
    if pkg is None:
        raise PtPackageNotFoundError("pt_package_not_found")
    if pkg["status"] != "active":
        raise PtPackageNotActiveError("pt_package_not_active")

    # Step 4 — Race-safe decrement (PT-16 / D-34-04a). 0-row = 409 exhausted.
    new_remaining = await repository.atomic_decrement_pt_package(
        session,
        data.pt_package_id,
    )
    if new_remaining is None:
        raise PtPackageExhaustedError("pt_package_exhausted")

    # Steps 5 + 6 — Insert + flush (FK / CHECK surface before audit).
    # asyncpg returns UUID for UUID columns; defence-in-depth coerce in case a
    # different driver (or a test stub) returns a string. The narrow ternary
    # keeps the type-narrowing visible to mypy.
    client_id_raw = pkg["client_id"]
    client_id = (
        client_id_raw if isinstance(client_id_raw, UUID) else UUID(str(client_id_raw))
    )
    pt_session = await repository.insert_pt_session(
        session,
        pt_package_id=data.pt_package_id,
        trainer_id=data.trainer_id,
        client_id=client_id,
        performed_at=data.performed_at,
        performed_by_user_id=actor.id,
        trainer_name_snapshot=trainer.full_name,
        notes=data.notes,
        # Phase 38 PKG-04 — carries the parent-booking FK when this session
        # was delivered via the booking flow; NULL for walk-ins.
        booking_id=data.booking_id,
    )
    await session.flush()

    # Phase 38 PKG-05 — atomic booking completion via the Phase 37
    # register_booking_completer Protocol slot. The slot consumer
    # (bookings.service.complete_booking) issues a predicate-gated
    # UPDATE bookings SET status='completed' WHERE id=:bid AND status='confirmed'
    # inside this UoW (the booking row is already row-locked from
    # fetch_booking_metadata_for_update above). 0-row UPDATE inside
    # complete_booking surfaces as InvalidBookingTransitionError — defensive,
    # since we just SELECT FOR UPDATE'd and validated status='confirmed' in
    # the same UoW; the predicate gate is belt-and-braces against a future
    # caller that drops our pre-check.
    if data.booking_id is not None:
        await complete_booking_by_pt_session(session, data.booking_id)

    # Step 7 — Emit pt_session_recorded (LITERAL strings for INFRA-11 AST gate).
    # str() / isoformat() casts ensure JSONB serialisability (Phase 32-02
    # deviation #1 lesson).
    await audit.emit(
        session,
        "pt_session_recorded",
        actor_user_id=actor.id,
        resource_type="pt_session",
        resource_id=pt_session.id,
        pt_session_id=str(pt_session.id),
        pt_package_id=str(data.pt_package_id),
        client_id=str(client_id),
        trainer_id=str(data.trainer_id),
        trainer_name_snapshot=trainer.full_name,
        performed_at=data.performed_at.isoformat(),
        performed_by_user_id=str(actor.id),
        sessions_remaining_after=new_remaining,
        # Phase 38 D-37-05 / D-38-17 — booking completion is observable via
        # this event when booking_id is non-None (C-06 — no separate
        # booking_completed event). UUID stringified per Pitfall 13.
        booking_id=str(data.booking_id) if data.booking_id is not None else None,
    )

    # Step 8 — Conditional auto-exhausted transition (D-34-05 / PT-17).
    if new_remaining == 0:
        await repository.atomic_transition_to_exhausted(
            session,
            data.pt_package_id,
        )
        await audit.emit(
            session,
            "pt_package_exhausted",
            actor_user_id=actor.id,
            resource_type="pt_package",
            resource_id=data.pt_package_id,
            pt_package_id=str(data.pt_package_id),
            client_id=str(client_id),
            exhausted_at=datetime.now(UTC).isoformat(),
        )

    # Step 9 — Commit (SVC001 gate).
    await session.commit()

    # Step 10 — Narrow refresh (WR-04 lesson) + response.
    await session.refresh(pt_session, attribute_names=["created_at", "updated_at"])
    return PtSessionResponse.model_validate(pt_session, from_attributes=True)


# ---------------------------------------------------------------------------
# Public orchestrators (Plan 34-03: cancel + read paths).
# ---------------------------------------------------------------------------


async def cancel_pt_session(
    session: AsyncSession,
    actor: CurrentUser,
    pt_session_id: UUID,
    data: PtSessionCancelRequest,
) -> PtSessionResponse:
    """Cancel a recorded PT-session (PT-18 / D-34-07 / D-34-11a).

    10-step orchestrator (mirrors ``record_pt_session`` shape):

      1. Load the session row — 404 ``pt_session_not_found`` / 409
         ``already_cancelled``.
      2. Cancel-window gate (D-34-07 / B-12): reception is denied 403
         ``cancel_window_expired`` if ``now - pt_session.created_at >
         24h`` — the window is measured from `created_at` (recording
         time), NOT `performed_at` (training wall-clock) per D-34-07.
         Owner is anytime.
      3. Fetch parent pt_package metadata (forensic + reactivation
         decision). Defensive 404 ``pt_package_not_found`` — should be
         impossible due to FK RESTRICT, but guards against historical
         data drift.
      4. Mark session cancelled (sets ``cancelled_at`` + ``cancel_reason``
         on the loaded ORM instance).
      5. Atomic increment (D-34-04a raw text() — predicate-bounded by
         ``session_count_snapshot`` ceiling). 0-row return is a HARD
         CHECK invariant breach → RuntimeError → 500.
      6. Conditional reverse-transition (D-34-11a): if
         ``prior_status == 'exhausted'`` flip
         ``exhausted → active`` via predicate-gated raw text() UPDATE
         (NOT in PT_PACKAGE_STATUS_TRANSITIONS FSM — locally-scoped
         carve-out). When ``prior_status`` is ``cancelled`` or
         ``expired`` the balance is still incremented (data integrity)
         but status stays terminal; ``package_reactivated`` stays False.
      7. ``session.flush()`` to surface FK / CHECK errors BEFORE audit
         emit.
      8. ``audit.emit('pt_session_cancelled', ...)`` — payload matches
         ``PtSessionCancelledPayload`` (extra='forbid') verbatim;
         ``package_reactivated`` reflects actual rowcount truth (NOT
         intent — T-34-K mitigation).
      9. Narrow refresh on ``updated_at`` (WR-04 lesson).
     10. ``await session.commit()`` (SVC001 caller-owns-txn gate) +
         return ``PtSessionResponse``.
    """
    # Step 1 — Load + state guards.
    pt_session = await repository.get_pt_session(session, pt_session_id)
    if pt_session is None:
        raise PtSessionNotFoundError("pt_session_not_found")
    if pt_session.cancelled_at is not None:
        raise PtSessionAlreadyCancelledError("already_cancelled")

    # Step 2 — Cancel-window gate (D-34-07; B-12 from created_at, NOT performed_at).
    if actor.role == Role.RECEPTION:
        age = datetime.now(UTC) - pt_session.created_at
        if age > timedelta(hours=CANCEL_WINDOW_HOURS_RECEPTION):
            raise CancelWindowExpiredError("cancel_window_expired")

    # Step 3 — Fetch parent package metadata (forensic + reactivation decision).
    pkg = await repository.fetch_pt_package_metadata(
        session,
        pt_session.pt_package_id,
    )
    if pkg is None:
        raise PtPackageNotFoundError("pt_package_not_found")
    prior_status = pkg["status"]

    # Step 4 — Mark cancelled (in-place ORM setter; no flush/commit).
    await repository.mark_cancelled(
        session,
        pt_session,
        cancel_reason=data.cancel_reason,
    )

    # Step 5 — Atomic increment (D-34-04a; raw text() with ceiling predicate).
    new_remaining = await repository.atomic_increment_pt_package(
        session,
        pt_session.pt_package_id,
    )
    if new_remaining is None:
        raise RuntimeError(
            f"atomic_increment_pt_package returned 0 rows for "
            f"{pt_session.pt_package_id}; CHECK sessions_remaining <= "
            "session_count_snapshot invariant breached"
        )

    # Step 6 — Conditional reverse transition (D-34-11a).
    # When prior_status is 'cancelled' or 'expired' the balance is still
    # incremented above (data integrity / forensic correctness) but status
    # stays terminal — package_reactivated stays False (D-34-CONTEXT
    # §D-34-11 "What about cancelled / expired parent package?").
    package_reactivated = False
    if prior_status == "exhausted":
        flipped = await repository.atomic_transition_exhausted_to_active(
            session,
            pt_session.pt_package_id,
        )
        # Use rowcount truth, not intent (T-34-K): if a concurrent refund
        # flipped the package to 'cancelled' between Step 3 read and Step
        # 6 update, the predicate WHERE status='exhausted' silently no-ops
        # and the audit payload records the reality.
        package_reactivated = flipped

    # Step 7 — Flush (FK / CHECK surface before audit emit).
    await session.flush()

    # Step 8 — Emit pt_session_cancelled (LITERAL strings for INFRA-11 AST gate).
    # Payload matches PtSessionCancelledPayload (extra='forbid') verbatim;
    # str() casts on UUIDs for JSONB serialisability.
    await audit.emit(
        session,
        "pt_session_cancelled",
        actor_user_id=actor.id,
        resource_type="pt_session",
        resource_id=pt_session.id,
        pt_session_id=str(pt_session.id),
        pt_package_id=str(pt_session.pt_package_id),
        client_id=str(pt_session.client_id),
        cancel_reason=data.cancel_reason,
        sessions_remaining_after=new_remaining,
        package_reactivated=package_reactivated,
    )

    # Step 9 — Narrow refresh on updated_at (WR-04 lesson).
    await session.refresh(pt_session, attribute_names=["updated_at"])

    # Step 10 — Commit (SVC001 gate) + response.
    await session.commit()
    return PtSessionResponse.model_validate(pt_session, from_attributes=True)


async def get_pt_session(
    session: AsyncSession,
    pt_session_id: UUID,
) -> PtSessionResponse:
    """Read a single PT-session row (PT-19 / read tier).

    Pure read — does NOT commit. 404 ``pt_session_not_found`` if the id
    is unknown. Reception+owner permission is enforced at the router
    layer via ``require_permission(Action.VIEW, Resource.PT_SESSIONS)``.
    """
    pt_session = await repository.get_pt_session(session, pt_session_id)
    if pt_session is None:
        raise PtSessionNotFoundError("pt_session_not_found")
    return PtSessionResponse.model_validate(pt_session, from_attributes=True)


async def list_sessions_by_pt_package(
    session: AsyncSession,
    pt_package_id: UUID,
    query: PtSessionListByPackageQuery,
) -> PaginatedData[PtSessionResponse]:
    """Paginated PT-session history for a parent pt_package (PT-19 / D-34-08).

    Pure read — does NOT commit. Returns the standard
    ``{items, total, page, pageSize}`` envelope. Reception+owner
    permission is enforced at the router layer via
    ``require_permission(Action.VIEW, Resource.PT_SESSIONS)``.

    No 404 for unknown ``pt_package_id`` — returns ``items=[], total=0``
    per the pt_packages list precedent (existence check is out of scope
    for list endpoints).
    """
    page = await repository.list_by_pt_package_paginated(
        session,
        pt_package_id,
        query,
    )
    return PaginatedData.model_construct(
        items=[
            PtSessionResponse.model_validate(s, from_attributes=True)
            for s in page.items
        ],
        total=page.total,
        page=page.page,
        page_size=page.page_size,
    )
