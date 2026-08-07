"""Settings singleton ORM models (Phase 108 CFG-02/03/04).

Three singletons follow the gym_info (D-31-08) pattern — one row each, seeded
by migration 0071_seed_settings with deterministic PKs. No SoftDeleteMixin
(singletons cannot be deleted). No created_by FK (owner-level reference data).

JSONB list/object columns carry server_default so the row is always valid even
if fields are omitted at insert time.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import Boolean, Integer, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, TimestampMixin, UUIDPkMixin


class BookingConfig(Base, UUIDPkMixin, TimestampMixin):
    """Booking rules singleton (CFG-03).

    One row only — seeded by migration 0071_seed_settings with deterministic PK
    00000000-0000-0000-0000-000000000003. Scalar typed columns so the booking
    service can read individual fields (not a JSONB blob).

    Money fields (no_show_penalty_kopecks) are integer kopecks per project convention.
    cancel_window_hours seeds from CANCEL_WINDOW_HOURS_RECEPTION = 24 (bookings/constants.py).
    """

    __tablename__ = "booking_config"

    # Scheduling granularity
    schedule_step_minutes: Mapped[int] = mapped_column(Integer, nullable=False, server_default="60")

    # Booking window
    booking_ahead_days: Mapped[int] = mapped_column(Integer, nullable=False, server_default="14")
    cutoff_minutes: Mapped[int] = mapped_column(Integer, nullable=False, server_default="60")

    # Cancellation policy
    cancel_window_hours: Mapped[int] = mapped_column(Integer, nullable=False, server_default="24")
    cancel_window_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )

    # Rescheduling policy
    reschedule_same_day: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )

    # No-show penalty (persisted; enforcement deferred per D-108 Context)
    no_show_penalty_kopecks: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    no_show_penalty_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )

    # Group class limits
    group_limit: Mapped[int] = mapped_column(Integer, nullable=False, server_default="20")
    waitlist_limit: Mapped[int] = mapped_column(Integer, nullable=False, server_default="10")
    waitlist_auto_transfer: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )

    # Self-booking flags
    client_self_book: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    show_trainer_windows: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )


class WorkingHoursConfig(Base, UUIDPkMixin, TimestampMixin):
    """Working hours / breaks / closures singleton (CFG-02).

    One row only — seeded by migration 0071_seed_settings with deterministic PK
    00000000-0000-0000-0000-000000000004.

    Three JSONB list columns mirror the GymInfo.hours pattern:
      schedule  — 7-day recurring schedule entries (Mon-Sun)
      breaks    — recurring break windows (empty by default)
      closures  — one-off holiday / closure date ranges (empty by default)
    """

    __tablename__ = "working_hours_config"

    # JSONB list columns — server_default '[]'::jsonb ensures a valid empty list
    schedule: Mapped[list[Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
    )
    breaks: Mapped[list[Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
    )
    closures: Mapped[list[Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
    )


class NotificationPrefsConfig(Base, UUIDPkMixin, TimestampMixin):
    """Club-wide notification preferences singleton (CFG-04).

    One row only — seeded by migration 0071_seed_settings with deterministic PK
    00000000-0000-0000-0000-000000000005.

    matrix — JSONB object keyed by notification kind × channel. Covers all 7 booking/
    payment/autopay notification kinds from notifications/models.py:
      booking_confirmed, booking_cancelled_by_client, booking_cancelled_by_owner,
      booking_rescheduled, payment_succeeded, autopay_charge_succeeded, autopay_charge_failed.

    NOTE: always-on (non-disablable) triggers — autopay_charge_failed and payment_failed
    (security-critical) bypass the matrix check. Enforcement is in the dispatcher (Plan 03),
    NOT at the model level.

    quiet_hours_start / quiet_hours_end — "HH:MM" Europe/Moscow time. Non-critical
    notifications are suppressed during the quiet window (no deferred/queued delivery per
    D-108 Context).

    sender_signature — appended to outbound text channels (Telegram/email); not used for
    in-app notifications.
    """  # noqa: RUF002

    __tablename__ = "notification_prefs_config"

    # JSONB matrix — server_default '{}'::jsonb ensures a valid empty object
    matrix: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )

    # Optional text channel sender attribution
    sender_signature: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Optional quiet-hours window (HH:MM strings, Europe/Moscow)
    quiet_hours_start: Mapped[str | None] = mapped_column(Text, nullable=True)
    quiet_hours_end: Mapped[str | None] = mapped_column(Text, nullable=True)
