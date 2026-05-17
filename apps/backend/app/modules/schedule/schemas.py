"""Schedule module request/response DTOs (Phase 38 SLOT-01..09).

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
"""

from __future__ import annotations

from datetime import datetime, timedelta
from enum import StrEnum
from uuid import UUID
from zoneinfo import ZoneInfo

from pydantic import Field

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
    """Outbound representation of a TrainerAvailabilitySlot (SLOT-02 / SLOT-08)."""

    id: UUID
    trainer_id: UUID
    start_time: datetime
    end_time: datetime
    status: SlotStatus
    created_at: datetime
    created_by_user_id: UUID
    cancelled_at: datetime | None
    cancel_reason: str | None


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
