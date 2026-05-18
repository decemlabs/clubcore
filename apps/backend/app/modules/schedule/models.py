"""TrainerAvailabilitySlot ORM model (Phase 38 SLOT-01).

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
  to users.id (forensic chain of who published the slot)
- Two btree indexes:
    ix_trainer_availability_slots_trainer_start_time
        (trainer_id, start_time) — full btree for trainer timeline scans.
    ix_trainer_availability_slots_active_start_time
        (status, start_time) WHERE status='active' — partial for SLOT-08
        discovery queries (active-only listing default; publish overlap
        candidate scan).

Structurally satisfies the `SlotById` Protocol declared in
core/dependencies.py (matches on id, status, trainer_id, start_time,
end_time per D-37-06). No DTO conversion at the resolver boundary.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID as UUIDType  # noqa: N811

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
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
    created_by_user_id: Mapped[UUIDType] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey(
            "users.id",
            ondelete="RESTRICT",
            name="fk_trainer_availability_slots_created_by_user_id_users",
        ),
        nullable=False,
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
    )
