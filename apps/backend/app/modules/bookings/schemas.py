"""Bookings module request/response DTOs (Phase 38 BOOK-01..05 / BOOK-10).

Inputs inherit BackendSchemaBase (camelCase wire ↔ snake_case Python,
extra='forbid'). Responses inherit ResponseData.

Decision references — Phase 38 (38-CONTEXT.md / 38-PATTERNS.md):
- D-38-02 BookingCreateRequest requires pt_package_id (NOT NULL FK at the
  DB layer; every v1.5 booking is a PT-session reservation).
- BookingStatus mirrors `bookings.status` CHECK values from migration 0017
  (confirmed / cancelled / no_show / completed).

Cancel + list query schemas land in plan 38-03 — this module ships only the
shape needed for POST /api/v1/bookings (create) so plan 38-02 stays atomic.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from app.core.schemas import BackendSchemaBase, ResponseData

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
# Request schema (BOOK-02 create)
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


# ---------------------------------------------------------------------------
# Response schema (BOOK-02 create / Phase 38 plan 38-03 read)
# ---------------------------------------------------------------------------


class BookingResponse(ResponseData):
    """Outbound representation of a Booking (BOOK-02 / Phase 38 plan 38-03)."""

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
