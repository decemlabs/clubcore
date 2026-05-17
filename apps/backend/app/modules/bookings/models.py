"""Booking ORM model (Phase 38 BOOK-01).

Composition: Base + UUIDPkMixin + TimestampMixin.

NO SoftDeleteMixin (D-38-04 mirror) — decommission via status flip to
'cancelled'; cancelled bookings stay for audit + history. Phase 38
bookings.service.cancel_booking performs the confirmed→cancelled
transition (plan 38-03).

DB-level invariants (BOOK-01 / D-38-02 / D-38-15 / Pitfall 6):
- status IN ('confirmed', 'cancelled', 'no_show', 'completed')
                         (CHECK ck_bookings_status)
- pt_package_id is NOT NULL FK to pt_packages.id ON DELETE RESTRICT
                         (D-38-02: every booking references a live package)
- slot_id is NOT NULL FK to trainer_availability_slots.id ON DELETE RESTRICT
- client_id is NOT NULL FK to clients.id ON DELETE RESTRICT
- created_by_user_id is NOT NULL FK to users.id ON DELETE RESTRICT
- Partial UNIQUE uq_bookings_slot_confirmed on (slot_id) WHERE status='confirmed'
  — one confirmed booking per slot (BOOK-01 / C-02 / D-38-15; service
  catches IntegrityError via _is_slot_confirmed_conflict discriminator).

NO snapshot columns (D-38-08) — display payloads use joinedload(Booking.slot)
+ joinedload(Booking.pt_package) at the repository layer (Phase 38 plan
38-03 list/detail endpoints).
"""

from __future__ import annotations

from datetime import datetime
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
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, TimestampMixin, UUIDPkMixin


class Booking(Base, UUIDPkMixin, TimestampMixin):
    """PT-session booking (Phase 38 BOOK-01 / D-38-02)."""

    __tablename__ = "bookings"

    slot_id: Mapped[UUIDType] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey(
            "trainer_availability_slots.id",
            ondelete="RESTRICT",
            name="fk_bookings_slot_id_trainer_availability_slots",
        ),
        nullable=False,
    )
    client_id: Mapped[UUIDType] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey(
            "clients.id",
            ondelete="RESTRICT",
            name="fk_bookings_client_id_clients",
        ),
        nullable=False,
    )
    pt_package_id: Mapped[UUIDType] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey(
            "pt_packages.id",
            ondelete="RESTRICT",
            name="fk_bookings_pt_package_id_pt_packages",
        ),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(16),
        server_default=text("'confirmed'"),
        nullable=False,
    )
    created_by_user_id: Mapped[UUIDType] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey(
            "users.id",
            ondelete="RESTRICT",
            name="fk_bookings_created_by_user_id_users",
        ),
        nullable=False,
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    cancel_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    no_show_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    __table_args__ = (
        # NAMING_CONVENTION expands to ck_bookings_status (matches migration 0017
        # literal-string CHECK name so `alembic check` produces empty diff).
        CheckConstraint(
            "status IN ('confirmed', 'cancelled', 'no_show', 'completed')",
            name="status",
        ),
        # Partial UNIQUE — MUST match migration 0017 literal name letter-for-letter
        # (literal-ref'd by service.py:_is_slot_confirmed_conflict, D-38-15).
        Index(
            "uq_bookings_slot_confirmed",
            "slot_id",
            unique=True,
            postgresql_where=text("status = 'confirmed'"),
        ),
        Index("ix_bookings_client_status", "client_id", "status"),
        Index("ix_bookings_slot_status", "slot_id", "status"),
    )
