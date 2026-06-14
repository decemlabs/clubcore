"""Settings module Pydantic schemas (Phase 108 CFG-02/03/04).

Response schemas use ResponseData (camelCase wire via alias_generator=to_camel).
Request schemas use BackendSchemaBase (extra='forbid', camelCase inbound).

T-108-05: numeric bounds + extra='forbid' are the server-authoritative input
validation gate for settings PUT payloads.
"""

from __future__ import annotations

import re
from typing import Any

from pydantic import Field, field_validator

from app.core.schemas import BackendSchemaBase, ResponseData

_HH_MM_PATTERN = re.compile(r"^\d{2}:\d{2}$")

_VALID_SCHEDULE_STEPS = {15, 30, 60, 90}


# ---------------------------------------------------------------------------
# CFG-02: Working hours / breaks / closures
# ---------------------------------------------------------------------------


class WorkingHoursResponse(ResponseData):
    """GET /api/v1/settings/hours response payload (CFG-02).

    Wire: camelCase via alias_generator=to_camel on ResponseData base.
    model_validate from ORM (from_attributes=True inherited from ContractModel).

    schedule/breaks/closures are JSONB arrays — structural validation lives on
    the frontend (UI-SPEC); backend stores and returns arrays as-is.
    """

    schedule: list[Any] = Field(default_factory=list)
    breaks: list[Any] = Field(default_factory=list)
    closures: list[Any] = Field(default_factory=list)


class WorkingHoursUpdateRequest(BackendSchemaBase):
    """Owner-only partial upsert request body for working hours (CFG-02).

    extra='forbid' (inherited from BackendSchemaBase) rejects unknown keys.
    All fields optional — partial upsert via exclude_unset semantics in repository.
    Structural validation of schedule/breaks/closures arrays deferred to frontend
    (UI-SPEC); backend is a passthrough store for the JSONB arrays.
    """

    schedule: list[Any] | None = None
    breaks: list[Any] | None = None
    closures: list[Any] | None = None


# ---------------------------------------------------------------------------
# CFG-03: Booking rules
# ---------------------------------------------------------------------------


class BookingConfigResponse(ResponseData):
    """GET /api/v1/settings/booking response payload (CFG-03).

    Wire: camelCase via alias_generator=to_camel on ResponseData base.
    model_validate from ORM (from_attributes=True inherited from ContractModel).
    """

    schedule_step_minutes: int
    booking_ahead_days: int
    cutoff_minutes: int
    cancel_window_hours: int
    cancel_window_enabled: bool
    reschedule_same_day: bool
    no_show_penalty_kopecks: int
    no_show_penalty_enabled: bool
    group_limit: int
    waitlist_limit: int
    waitlist_auto_transfer: bool
    client_self_book: bool
    show_trainer_windows: bool


class BookingConfigUpdateRequest(BackendSchemaBase):
    """Owner-only partial upsert request body for booking rules (CFG-03).

    extra='forbid' (inherited from BackendSchemaBase) rejects unknown keys.
    All fields optional — partial upsert via exclude_unset semantics.

    T-108-05 numeric bounds:
      schedule_step_minutes: must be one of {15, 30, 60, 90} (schedule granularity enum).
      booking_ahead_days: 1..365 (at least 1 day, at most 1 year ahead).
      cutoff_minutes: 0..1440 (0 = no cutoff; 1440 = 24h same-day cutoff).
      cancel_window_hours: >= 1 (at least 1 hour notice to cancel).
      group_limit: >= 1 (group class must allow at least one participant).
      waitlist_limit: >= 0 (0 disables waitlist).
      no_show_penalty_kopecks: >= 0 (no negative penalties).
    """

    schedule_step_minutes: int | None = Field(default=None)
    booking_ahead_days: int | None = Field(default=None, ge=1, le=365)
    cutoff_minutes: int | None = Field(default=None, ge=0, le=1440)
    cancel_window_hours: int | None = Field(default=None, ge=1)
    cancel_window_enabled: bool | None = None
    reschedule_same_day: bool | None = None
    no_show_penalty_kopecks: int | None = Field(default=None, ge=0)
    no_show_penalty_enabled: bool | None = None
    group_limit: int | None = Field(default=None, ge=1)
    waitlist_limit: int | None = Field(default=None, ge=0)
    waitlist_auto_transfer: bool | None = None
    client_self_book: bool | None = None
    show_trainer_windows: bool | None = None

    @field_validator("schedule_step_minutes")
    @classmethod
    def validate_schedule_step(cls, v: int | None) -> int | None:
        """T-108-05: schedule_step_minutes must be one of {15, 30, 60, 90}."""
        if v is not None and v not in _VALID_SCHEDULE_STEPS:
            raise ValueError(
                f"schedule_step_minutes must be one of {sorted(_VALID_SCHEDULE_STEPS)}"
            )
        return v


# ---------------------------------------------------------------------------
# CFG-04: Notification preferences
# ---------------------------------------------------------------------------


class NotificationPrefsResponse(ResponseData):
    """GET /api/v1/settings/notifications response payload (CFG-04).

    Wire: camelCase via alias_generator=to_camel on ResponseData base.
    model_validate from ORM (from_attributes=True inherited from ContractModel).

    matrix is a JSONB object keyed by notification kind x channel — returned as-is.
    sender_signature is appended to outbound text channels (Telegram/email).
    quiet_hours_start / quiet_hours_end are "HH:MM" strings (Europe/Moscow).
    """

    matrix: dict[str, Any] = Field(default_factory=dict)
    sender_signature: str | None = None
    quiet_hours_start: str | None = None
    quiet_hours_end: str | None = None


class NotificationPrefsUpdateRequest(BackendSchemaBase):
    """Owner-only partial upsert request body for notification preferences (CFG-04).

    extra='forbid' (inherited from BackendSchemaBase) rejects unknown keys.
    All fields optional — partial upsert via exclude_unset semantics.

    T-108-05 bounds:
      sender_signature: max_length=11 (SMS/Telegram sender ID limit).
      quiet_hours_start / quiet_hours_end: "HH:MM" pattern (Europe/Moscow).
    """

    matrix: dict[str, Any] | None = None
    sender_signature: str | None = Field(default=None, max_length=11)
    quiet_hours_start: str | None = None
    quiet_hours_end: str | None = None

    @field_validator("quiet_hours_start", "quiet_hours_end")
    @classmethod
    def validate_hhmm(cls, v: str | None) -> str | None:
        """T-108-05: quiet_hours_* must be "HH:MM" format if provided."""
        if v is not None and not _HH_MM_PATTERN.match(v):
            raise ValueError("quiet_hours must be in HH:MM format")
        return v
