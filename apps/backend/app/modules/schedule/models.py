"""Schedule ORM models: TrainerAvailabilitySlot, RecurringSlotTemplate, TrainerTimeOff.

Phase 38 SLOT-01 — TrainerAvailabilitySlot (original model).
Phase 59 REC-01..04 — RecurringSlotTemplate + TrainerTimeOff + slot ALTER (0042).

Composition: Base + UUIDPkMixin + TimestampMixin.

NO SoftDeleteMixin (D-38-04) — decommission via status flip to 'cancelled'
per SLOT-02; cancelled slots stay for audit + booking history. Phase 38
schedule.service.cancel_slot performs the active→cancelled transition;
the booked→cancelled cascade lands in plan 38-03.

DB-level invariants (D-38-03 / D-38-04 / Pitfall 6):
- status IN ('active', 'booked', 'cancelled')
                         (CHECK ck_trainer_availability_slots_status)
- end_time > start_time  (CHECK ck_trainer_availability_slots_end_after_start)
- FK fk_trainer_availability_slots_trainer_id_trainers ON DELETE RESTRICT to
  trainers.id (trainers are soft-deleted via is_active, never hard-deleted)
- FK fk_trainer_availability_slots_created_by_user_id_users ON DELETE RESTRICT
  to users.id (forensic chain of who published the slot; NULLABLE since Phase
  59 / 0042 — cron-generated slots carry NULL author per D-59-05)
- Three btree indexes:
    ix_trainer_availability_slots_trainer_start_time
        (trainer_id, start_time) — full btree for trainer timeline scans.
    ix_trainer_availability_slots_active_start_time
        (status, start_time) WHERE status='active' — partial for SLOT-08
        discovery queries (active-only listing default; publish overlap
        candidate scan).
    uq_trainer_availability_slots_trainer_id_start_time
        UNIQUE (trainer_id, start_time) — Phase 59 D-59-05 / 0042: backs
        ON CONFLICT (trainer_id, start_time) DO NOTHING in the recurring-slot
        cron so repeat ticks are true no-ops (PITFALL 8).

Structurally satisfies the `SlotById` Protocol declared in
core/dependencies.py (matches on id, status, trainer_id, start_time,
end_time per D-37-06). No DTO conversion at the resolver boundary.
"""

from __future__ import annotations

from datetime import date, datetime, time
from typing import Any
from uuid import UUID as UUIDType  # noqa: N811

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    SmallInteger,
    String,
    Text,
    Time,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PgUUID  # noqa: N811
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin, UUIDPkMixin


class TrainerAvailabilitySlot(Base, UUIDPkMixin, TimestampMixin):
    """Trainer 1:1 availability window (Phase 38 SLOT-01 / D-38-03)."""

    __tablename__ = "trainer_availability_slots"

    trainer_id: Mapped[UUIDType] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey(
            "trainers.id",
            ondelete="RESTRICT",
            name="fk_trainer_availability_slots_trainer_id_trainers",
        ),
        nullable=False,
    )
    start_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    end_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(16),
        server_default=text("'active'"),
        nullable=False,
    )
    # Phase 59 D-59-05 / 0042: NULLABLE since recurring-slot cron generates
    # slots with no human author. Mirrors 0021 bookings precedent.
    created_by_user_id: Mapped[UUIDType | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey(
            "users.id",
            ondelete="RESTRICT",
            name="fk_trainer_availability_slots_created_by_user_id_users",
        ),
        nullable=True,
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    cancel_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Phase 39 NOTIFY-03/04 — string-keyed cross-module relationship so the
    # `_dispatch_booking_dm` helper (in bookings.service) can render DMs with
    # `slot.trainer.full_name`. Same modules-independent discipline as
    # `Booking.slot` — no `from app.modules.trainers` import here; SA resolves
    # "Trainer" via the shared `Base.registry` at mapper-configuration time.
    trainer: Mapped[Any] = relationship(
        "Trainer",
        foreign_keys=[trainer_id],
        lazy="select",
        viewonly=True,
    )

    __table_args__ = (
        # Names match migration 0016 literal-string CHECK names so alembic
        # check produces empty diff. The NAMING_CONVENTION ck template would
        # expand to ck_trainer_availability_slots_<name>; we use the literal
        # tail here.
        CheckConstraint(
            "status IN ('active', 'booked', 'cancelled')",
            name="status",
        ),
        CheckConstraint(
            "end_time > start_time",
            name="end_after_start",
        ),
        Index(
            "ix_trainer_availability_slots_trainer_start_time",
            "trainer_id",
            "start_time",
        ),
        Index(
            "ix_trainer_availability_slots_active_start_time",
            "status",
            "start_time",
            postgresql_where=text("status = 'active'"),
        ),
        # Phase 59 D-59-05 / 0042: backs ON CONFLICT (trainer_id, start_time)
        # DO NOTHING in the recurring-slot cron (PITFALL 8 idempotency).
        Index(
            "uq_trainer_availability_slots_trainer_id_start_time",
            "trainer_id",
            "start_time",
            unique=True,
        ),
    )


class RecurringSlotTemplate(Base, UUIDPkMixin, TimestampMixin):
    """Recurring availability pattern for a trainer (Phase 59 REC-01 / D-59-02).

    Owner defines a weekly recurrence (day_of_week + start_time/end_time) with
    an optional validity window (valid_from…valid_until).  The ARQ cron
    materialises concrete TrainerAvailabilitySlot rows from active templates
    inside the rolling RECURRING_SLOT_HORIZON_DAYS window (D-59-04 / PITFALL 8).

    DB-level invariants (D-59-02 / 0042):
    - day_of_week IN [0..6]   (CHECK ck_recurring_slot_templates_day_of_week)
    - end_time > start_time   (CHECK ck_recurring_slot_templates_end_after_start)
    - valid_until IS NULL OR valid_until >= valid_from
                              (CHECK ck_recurring_slot_templates_valid_window)
    - UNIQUE (trainer_id, day_of_week, start_time, valid_from)
                              — REC-01 verbatim idempotency key
    - FK to trainers.id ON DELETE RESTRICT (trainer soft-deleted via is_active)
    """

    __tablename__ = "recurring_slot_templates"

    trainer_id: Mapped[UUIDType] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey(
            "trainers.id",
            ondelete="RESTRICT",
            name="fk_recurring_slot_templates_trainer_id_trainers",
        ),
        nullable=False,
    )
    # 0 = Monday … 6 = Sunday (ISO weekday convention)
    day_of_week: Mapped[int] = mapped_column(SmallInteger(), nullable=False)
    start_time: Mapped[time] = mapped_column(Time(), nullable=False)
    end_time: Mapped[time] = mapped_column(Time(), nullable=False)
    valid_from: Mapped[date] = mapped_column(Date(), nullable=False)
    # NULL = open-ended pattern (no expiry date)
    valid_until: Mapped[date | None] = mapped_column(Date(), nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean(),
        server_default=text("true"),
        nullable=False,
    )

    # String-keyed cross-module relationship (no import; SA resolves via Base.registry)
    trainer: Mapped[Any] = relationship(
        "Trainer",
        foreign_keys=[trainer_id],
        lazy="select",
        viewonly=True,
    )

    __table_args__ = (
        # Constraint name tails match 0042 migration op.f() names so alembic
        # check produces an empty diff (NAMING_CONVENTION expands these as
        # ck_%(table_name)s_%(constraint_name)s → full constraint name).
        CheckConstraint(
            "day_of_week >= 0 AND day_of_week <= 6",
            name="day_of_week",
        ),
        CheckConstraint(
            "end_time > start_time",
            name="end_after_start",
        ),
        CheckConstraint(
            "valid_until IS NULL OR valid_until >= valid_from",
            name="valid_window",
        ),
        # REC-01 verbatim UNIQUE
        Index(
            "uq_recurring_slot_templates_trainer_id",
            "trainer_id",
            "day_of_week",
            "start_time",
            "valid_from",
            unique=True,
        ),
    )


class TrainerTimeOff(Base, UUIDPkMixin, TimestampMixin):
    """Trainer time-off block (Phase 59 REC-03 / D-59-06).

    Owner creates a TIMESTAMPTZ block [block_start, block_end].  On creation
    the service (D-59-06): auto-cancels overlapping active slots; raises 409
    on booked overlaps unless ?force=true (which cascades booking-FSM
    cancellation + client DM via the existing cancel_slot machinery).

    DB-level invariants (D-59-06 / 0042):
    - block_end > block_start (CHECK ck_trainer_time_off_block_end_after_start)
    - FK to trainers.id ON DELETE RESTRICT
    - btree index on (trainer_id, block_start) for overlap queries (PITFALL 9)
    """

    __tablename__ = "trainer_time_off"

    trainer_id: Mapped[UUIDType] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey(
            "trainers.id",
            ondelete="RESTRICT",
            name="fk_trainer_time_off_trainer_id_trainers",
        ),
        nullable=False,
    )
    # Always stored in UTC (PITFALL 7 / D-59-05)
    block_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    block_end: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    reason: Mapped[str | None] = mapped_column(Text(), nullable=True)

    # String-keyed cross-module relationship (no import; SA resolves via Base.registry)
    trainer: Mapped[Any] = relationship(
        "Trainer",
        foreign_keys=[trainer_id],
        lazy="select",
        viewonly=True,
    )

    __table_args__ = (
        # Constraint name tail matches 0042 migration op.f() name so alembic
        # check produces an empty diff (NAMING_CONVENTION expands to full name).
        CheckConstraint(
            "block_end > block_start",
            name="block_end_after_start",
        ),
        # Backs overlap queries in the conflict service + the cron's per-trainer
        # pre-fetch (list_active_time_off_for_trainers: WHERE trainer_id IN (...)
        # AND block_end > now; Python-side overlap filter — PITFALL 9 inverse).
        Index(
            "ix_trainer_time_off_trainer_id",
            "trainer_id",
            "block_start",
        ),
    )
