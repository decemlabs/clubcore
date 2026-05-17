"""Bookings module request/response DTOs (Phase 38 BOOK-01..10).

Inputs inherit BackendSchemaBase (camelCase wire ↔ snake_case Python,
extra='forbid'). Responses inherit ResponseData.

Decision references — Phase 38 (38-CONTEXT.md / 38-PATTERNS.md):
- D-38-02 BookingCreateRequest requires pt_package_id (NOT NULL FK at the
  DB layer; every v1.5 booking is a PT-session reservation).
- D-38-08 — NO snapshot columns on `bookings`. The detail-response payload
  built by GET /bookings/{id} (Phase 38 plan 38-03) carries a slot
  projection via the local `SlotSnapshot` class declared in this module.
  The class is declared HERE (NOT imported from `app.modules.schedule.schemas`)
  to preserve the `modules-independent` import-linter contract unambiguously
  AND to mirror the v1.4 pt_sessions precedent of inlining a brief
  projection of a sibling-module entity rather than cross-importing its
  schema module (see plan 38-03 §"Cross-module router mount — DECISION
  LOCKED" / checker fix).
- BookingStatus mirrors `bookings.status` CHECK values from migration 0017
  (confirmed / cancelled / no_show / completed).
- BOOK-07 default list window: now-30d → now+30d Europe/Moscow; defaults
  computed via Field(default_factory=...) so they evaluate PER REQUEST
  (mirrors the pattern used by other paginated endpoints; FastAPI accepts
  default_factory for non-query Pydantic models such as request bodies and
  for query params when wired via `Depends()` — see plan 38-03 §Task 1).
"""

from __future__ import annotations

from datetime import datetime, timedelta
from enum import StrEnum
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from pydantic import Field

from app.core.pagination import PageQuery
from app.core.schemas import BackendSchemaBase, ResponseData

# Business TZ pin (C-07 / D-38-12). List-window defaults are Moscow-relative.
MOSCOW_TZ = ZoneInfo("Europe/Moscow")


# ---------------------------------------------------------------------------
# Status enum — mirrors bookings.status CHECK values from migration 0017.
# ---------------------------------------------------------------------------


class BookingStatus(StrEnum):
    """Booking lifecycle status (Phase 37 BOOKING_STATUS_TRANSITIONS / C-04).

    Values byte-stable with migration 0017_bookings CHECK ck_bookings_status.
    The (confirmed → {cancelled, no_show, completed}) forward-only FSM is
    encoded in `app.modules.bookings.constants.BOOKING_STATUS_TRANSITIONS`
    (Phase 37 INFRA-30 / D-37-04).
    """

    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"
    COMPLETED = "completed"


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class BookingCreateRequest(BackendSchemaBase):
    """POST /api/v1/bookings body (Phase 38 BOOK-02 / D-38-02).

    Three fields required:
    - slot_id: target slot — must exist + status='active' (server checks).
    - client_id: client to book for — reception/owner can book any client
      (D-38-09 — gym-staff trust model; audit records actor_user_id).
    - pt_package_id: must reference an active package that the client owns;
      server cross-checks trainer_id match + validity window + remaining
      sessions before flipping the slot.

    `created_by_user_id` is server-set from `actor.id`; never accepted from
    request body (extra='forbid' rejects it structurally).
    `status` is server-set to 'confirmed' on INSERT.
    """

    slot_id: UUID
    client_id: UUID
    pt_package_id: UUID


class BookingCancelRequest(BackendSchemaBase):
    """POST /api/v1/bookings/{id}/cancel body (Phase 38 plan 38-03 / BOOK-06).

    `reason` is REQUIRED — 1..200 chars; downstream audit row stores this
    string verbatim via `BookingCancelledPayload.cancel_reason`.
    Mirrors `PtSessionCancelRequest` shape (B-12 precedent).
    """

    reason: str = Field(min_length=1, max_length=200)


# ---------------------------------------------------------------------------
# List query schemas (Phase 38 plan 38-03 / BOOK-07 / BOOK-08)
# ---------------------------------------------------------------------------


def _default_from_time() -> datetime:
    """Default lower bound of the booking-list window — now - 30d (Moscow).

    Computed PER REQUEST (BOOK-07 default). Bounded backward window prevents
    full-history dump from a single GET (T-38-03-05 mitigation).
    """
    return datetime.now(MOSCOW_TZ) - timedelta(days=30)


def _default_to_time() -> datetime:
    """Default upper bound of the booking-list window — now + 30d (Moscow).

    Computed PER REQUEST (BOOK-07 default). Bounded forward window completes
    the symmetric ±30d default window described by BOOK-07.
    """
    return datetime.now(MOSCOW_TZ) + timedelta(days=30)


class BookingListQuery(PageQuery):
    """GET /api/v1/bookings query parameters (BOOK-07).

    Filters:
      - `client_id` (optional) — narrow to one client.
      - `trainer_id` (optional) — narrow to one trainer via joinedload slot.
      - `from_time` / `to_time` — Moscow-relative ±30d default window
        applied at request time via `Field(default_factory=...)`.
      - `status` (optional) — filter by booking status; None = all statuses.

    Wire form: ?clientId=...&trainerId=...&fromTime=...&toTime=...&status=...
    """

    client_id: UUID | None = None
    trainer_id: UUID | None = None
    from_time: datetime = Field(default_factory=_default_from_time)
    to_time: datetime = Field(default_factory=_default_to_time)
    status: BookingStatus | None = None


class BookingsForClientListQuery(PageQuery):
    """GET /api/v1/clients/{client_id}/bookings query parameters (BOOK-08).

    Same filter set as BookingListQuery MINUS `client_id` (taken from the
    URL path). Default ±30d Moscow window mirrors BookingListQuery.
    """

    from_time: datetime = Field(default_factory=_default_from_time)
    to_time: datetime = Field(default_factory=_default_to_time)
    status: BookingStatus | None = None


# ---------------------------------------------------------------------------
# Response schemas (BOOK-02 create / BOOK-07/08 list / BOOK-09 detail)
# ---------------------------------------------------------------------------


class BookingResponse(ResponseData):
    """Outbound representation of a Booking (BOOK-02 / BOOK-07 / BOOK-08)."""

    id: UUID
    slot_id: UUID
    client_id: UUID
    pt_package_id: UUID
    status: BookingStatus
    created_at: datetime
    created_by_user_id: UUID
    cancelled_at: datetime | None
    cancel_reason: str | None
    no_show_at: datetime | None
    completed_at: datetime | None


class SlotSnapshot(BackendSchemaBase):
    """INLINE slot projection for BookingDetailResponse (Phase 38 plan 38-03).

    LOCAL class declared here — NOT imported from `app.modules.schedule.schemas`.

    Rationale (D-38-08 + plan 38-03 §Task 1 locked-decision per checker fix):
      - Preserves the `modules-independent` import-linter contract
        unambiguously. NO `from app.modules.schedule import ...` in this
        module — the bookings detail payload is built from a `joinedload(
        Booking.slot)` chain at the repository layer, then the slot
        attributes are projected into this 5-field BackendSchemaBase.
      - Mirrors the v1.4 pt_sessions precedent: `pt_sessions/schemas.py`
        inlines a brief projection of pt_packages rather than cross-importing
        `pt_packages/schemas.py`. The same discipline applies here.
      - D-38-08 governs DB design (no snapshot columns on the booking row);
        the schema-layer view of a slot for a read-payload is a separate
        concern — duplicating 5 fields here is cheap and decoupled.

    Fields match the SlotById Protocol surface (D-37-06) + the `status`
    string the GET-one endpoint surfaces for display.
    """

    id: UUID
    start_time: datetime
    end_time: datetime
    trainer_id: UUID
    status: str


class BookingDetailResponse(BookingResponse):
    """Outbound full-detail booking payload (Phase 38 plan 38-03 / BOOK-09).

    Extends `BookingResponse` with denormalized `slot` (via the LOCAL
    `SlotSnapshot` — no cross-module schema import) and a minimal
    `pt_package` dict snapshot (id, plan_name_snapshot, sessions_remaining,
    end_date). Kept dict-typed to avoid pulling the pt_packages schema
    surface into the bookings module — the read endpoint composes the dict
    inline from the joinedload chain at the service layer.

    Pitfall 19 — the repository must `joinedload(Booking.slot)` and
    `joinedload(Booking.pt_package)` for this read path so the GET /{id}
    handler emits ≤2 DB queries (test asserts).
    """

    slot: SlotSnapshot
    pt_package: dict[str, Any]
