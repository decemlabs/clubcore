"""Schedule module request/response DTOs (Phase 38 SLOT-01..09 + Phase 59 REC-01..04).

Inputs inherit BackendSchemaBase (camelCase wire ↔ snake_case Python,
extra='forbid'). Responses inherit ResponseData.

Decision references — Phase 38 (38-CONTEXT.md / 38-PATTERNS.md):
- D-38-03 SlotStatus values: active / booked / cancelled (NO 'available').
- D-38-05 SlotCreateRequest is THREE fields only: trainer_id, start_time,
  end_time — NO recurrence_rule (one-off slot per POST; bulk-publish and
  RRULE expansion deferred to v1.8).
- SLOT-08 default list window: now → now+14d Europe/Moscow; defaults computed
  via `Field(default_factory=...)` so they are evaluated PER REQUEST (not at
  module import time — testability + correct "now").

Phase 59 additions (REC-01..04):
- SlotResponse.created_by_user_id widened to UUID | None — cron-generated
  slots carry no human author (D-59-05 / 0042 nullable ALTER).
- RecurringSlotTemplateCreate / RecurringSlotTemplateResponse — CRUD DTOs for
  recurring availability patterns (REC-01).
- TimeOffCreate / TimeOffResponse — CRUD DTOs for trainer time-off blocks
  (REC-03).
- TimeOffConflictDetail — 409 payload when booked slots overlap a new time-off
  block (REC-03 / D-59-06).
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from enum import StrEnum
from uuid import UUID
from zoneinfo import ZoneInfo

from pydantic import Field, field_validator, model_validator

from app.core.pagination import PageQuery
from app.core.schemas import BackendSchemaBase, ResponseData

# Business TZ pin (C-07). All Moscow-relative defaults derive from here.
MOSCOW_TZ = ZoneInfo("Europe/Moscow")


# ---------------------------------------------------------------------------
# Status enum — mirrors trainer_availability_slots.status CHECK values (D-38-03).
# ---------------------------------------------------------------------------


class SlotStatus(StrEnum):
    """Slot lifecycle status (38-CONTEXT.md domain / D-38-03).

    Values byte-stable with migration 0016_trainer_availability_slots CHECK
    `ck_trainer_availability_slots_status`. NO 'available' — research
    ARCHITECTURE.md drafted it but REQUIREMENTS SLOT-01 overrode (D-38-03).
    """

    ACTIVE = "active"
    BOOKED = "booked"
    CANCELLED = "cancelled"


# ---------------------------------------------------------------------------
# Request schemas (SLOT-02 publish / SLOT-09 cancel)
# ---------------------------------------------------------------------------


class SlotCreateRequest(BackendSchemaBase):
    """POST /api/v1/trainer-slots body (SLOT-02 / D-38-05).

    Three fields only — NO recurrence_rule (D-38-05 — RRULE expansion is a
    v1.8 reports-milestone feature). `created_by_user_id` is server-set from
    `actor.id`; never accepted from request body (extra='forbid' rejects it
    structurally).
    """

    trainer_id: UUID
    start_time: datetime
    end_time: datetime


class SlotCancelRequest(BackendSchemaBase):
    """PATCH /api/v1/trainer-slots/{id}/cancel body (SLOT-09).

    `cancel_reason` is REQUIRED — 1..200 chars; downstream notification flow
    (Phase 39 CRON-01) reuses the same length bound for the audit payload
    `cancel_reason` field.
    """

    cancel_reason: str = Field(min_length=1, max_length=200)


# ---------------------------------------------------------------------------
# Response schema (SLOT-02 publish / SLOT-08 read / SLOT-09 cancel)
# ---------------------------------------------------------------------------


class SlotResponse(ResponseData):
    """Outbound representation of a TrainerAvailabilitySlot (SLOT-02 / SLOT-08).

    Phase 40 BLOCKER-2 extension: ``trainer_full_name`` is projected via JOIN
    on the trainers table at the repository layer (D-38-08 pattern preserved —
    no snapshot column on ``trainer_availability_slots``). The /book bot
    handler (Phase 40 D-40-07) consumes this field directly to label the
    InlineKeyboard buttons without a secondary lookup.

    Phase 59 D-59-05: ``created_by_user_id`` is now ``UUID | None`` — the 0042
    migration made the column nullable so the recurring-slot cron (Plan 05) can
    materialise slots with no human author.  The human publish_slot path
    continues to populate this field with the actor's UUID.
    """

    id: UUID
    trainer_id: UUID
    start_time: datetime
    end_time: datetime
    status: SlotStatus
    created_at: datetime
    created_by_user_id: UUID | None  # None for cron-generated recurring slots
    cancelled_at: datetime | None
    cancel_reason: str | None
    trainer_full_name: str  # Phase 40 D-40-07 / BLOCKER-2 — JOIN-projected


# ---------------------------------------------------------------------------
# List query (SLOT-08)
# ---------------------------------------------------------------------------


def resolve_default_from_time() -> datetime:
    """Default lower bound of the slot-list window — now (Europe/Moscow).

    Computed lazily by the repository when `from_time is None` (FastAPI query
    schema generation cannot synthesize a `datetime` default_factory for
    query params, so we keep the wire type Optional and resolve server-side).
    """
    return datetime.now(MOSCOW_TZ)


def resolve_default_to_time() -> datetime:
    """Default upper bound of the slot-list window — now + 14d (Europe/Moscow).

    Same lazy-resolution rationale as `resolve_default_from_time`. The 14-day
    forward window bounds enumeration so an unconstrained list cannot dump
    the full slot history (T-38-01-04 mitigation).
    """
    return datetime.now(MOSCOW_TZ) + timedelta(days=14)


class SlotListQuery(PageQuery):
    """GET /api/v1/trainer-slots query parameters (SLOT-08).

    `from_time` / `to_time` default to None on the wire; the repository
    layer resolves them to `now()` / `now() + 14d` (Europe/Moscow) at
    request time via `resolve_default_from_time` / `resolve_default_to_time`
    helpers exported above. This is the FastAPI-friendly equivalent of
    `Field(default_factory=...)` for datetime query params (the OpenAPI
    schema generator cannot synthesize a default datetime for query strings
    so we must keep the wire type Optional).
    """

    trainer_id: UUID | None = None
    from_time: datetime | None = Field(default=None)
    to_time: datetime | None = Field(default=None)
    status: SlotStatus = SlotStatus.ACTIVE


# ---------------------------------------------------------------------------
# Phase 59 — Recurring slot template DTOs (REC-01)
# ---------------------------------------------------------------------------


class RecurringSlotTemplateCreate(BackendSchemaBase):
    """POST /api/v1/recurring-slot-templates body (REC-01 / D-59-02).

    Mirrors the CHECK constraints from migration 0042 at the Pydantic layer
    (T-59-06 double gate — DTO validates before the DB CHECK fires):
    - day_of_week MUST be in [0, 6]  (0 = Mon, 6 = Sun ISO weekday).
    - end_time MUST be after start_time.
    - valid_until, when present, MUST be >= valid_from.
    """

    trainer_id: UUID
    # 0 = Monday … 6 = Sunday (ISO weekday)
    day_of_week: int = Field(ge=0, le=6)
    start_time: time
    end_time: time
    valid_from: date
    valid_until: date | None = None

    @model_validator(mode="after")
    def _end_after_start(self) -> RecurringSlotTemplateCreate:
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        return self

    @model_validator(mode="after")
    def _valid_window(self) -> RecurringSlotTemplateCreate:
        if self.valid_until is not None and self.valid_until < self.valid_from:
            raise ValueError("valid_until must be >= valid_from when set")
        return self


class RecurringSlotTemplateResponse(ResponseData):
    """Outbound representation of a RecurringSlotTemplate (REC-01 / REC-04)."""

    id: UUID
    trainer_id: UUID
    day_of_week: int
    start_time: time
    end_time: time
    valid_from: date
    valid_until: date | None
    is_active: bool
    created_at: datetime


# ---------------------------------------------------------------------------
# Phase 59 — Trainer time-off DTOs (REC-03)
# ---------------------------------------------------------------------------


class TimeOffCreate(BackendSchemaBase):
    """POST /api/v1/trainer-time-off body (REC-03 / D-59-06).

    Mirrors the CHECK constraint from migration 0042 at the Pydantic layer
    (T-59-07 double gate — DTO validates before the DB CHECK fires):
    - block_end MUST be after block_start.
    Both fields MUST be timezone-aware (TIMESTAMPTZ; always stored in UTC).
    """

    trainer_id: UUID
    block_start: datetime
    block_end: datetime
    reason: str | None = None

    @field_validator("block_start", "block_end", mode="after")
    @classmethod
    def _must_be_aware(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("block_start and block_end must be timezone-aware")
        return v

    @model_validator(mode="after")
    def _block_end_after_start(self) -> TimeOffCreate:
        if self.block_end <= self.block_start:
            raise ValueError("block_end must be after block_start")
        return self


class TimeOffResponse(ResponseData):
    """Outbound representation of a TrainerTimeOff block (REC-03 / REC-04)."""

    id: UUID
    trainer_id: UUID
    block_start: datetime
    block_end: datetime
    reason: str | None
    created_at: datetime


# ---------------------------------------------------------------------------
# Phase 59 — 409 conflict detail (REC-03 booked-slot guard / D-59-06)
# ---------------------------------------------------------------------------


class TimeOffConflictDetail(ResponseData):
    """Body of the 409 response when a time-off block overlaps booked slots.

    Lists the IDs of the conflicting trainer_availability_slots and the
    corresponding confirmed booking IDs so the owner can decide whether to
    proceed with ``?force=true`` (which cascades booking-FSM cancellation +
    client DM) or resolve the conflicts manually first.
    """

    conflicting_slot_ids: list[UUID]
    conflicting_booking_ids: list[UUID]
