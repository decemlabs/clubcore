"""bookings

Revision ID: 0017_bookings
Revises: 0016_trainer_availability_slots
Create Date: 2026-05-17 17:30:00.000000

Phase 38 BOOK-01 — Booking instance (one row per PT-session reservation).

Notes:
- Partial UNIQUE on (slot_id) WHERE status='confirmed' is the race-safe
  one-confirmed-booking-per-slot invariant (BOOK-01 / C-02 / Pitfall 1).
  Installed via op.create_index(postgresql_where=...); the constraint name
  "uq_bookings_slot_confirmed" is literal-referenced by
  app/modules/bookings/service.py:_is_slot_confirmed_conflict (D-38-15
  mirror of pt_packages uq_pt_packages_active_per_client translation).
- TIMESTAMPTZ via sa.DateTime(timezone=True) for created_at / updated_at /
  cancelled_at / no_show_at / completed_at per Pitfall 6. Container TZ is
  UTC and Europe/Moscow business-day math lives in service code.
- pt_package_id is NOT NULL FK to pt_packages.id ON DELETE RESTRICT
  (D-38-02 — every booking references a live PT-package; nullable deferred
  to v1.7+ when non-PT bookings are scoped).
- slot_id is NOT NULL FK to trainer_availability_slots.id ON DELETE RESTRICT
  (cancelled slots stay for audit; never hard-deleted per D-38-04).
- client_id is NOT NULL FK to clients.id ON DELETE RESTRICT.
- created_by_user_id is NOT NULL FK to users.id ON DELETE RESTRICT
  (forensic chain of who created the booking).
- Status CHECK admits ('confirmed', 'cancelled', 'no_show', 'completed')
  per C-04 / Phase 37 BOOKING_STATUS_TRANSITIONS. Constraint name
  ck_bookings_status mirrors v1.4 pt_packages naming.
- NO snapshot columns (D-38-08) — joinedload(Booking.slot) +
  joinedload(Booking.pt_package) at the repository layer for display
  payloads (no hard-delete invariant per D-38-04 guarantees rows live).
- NO SoftDeleteMixin / deleted_at column — lifecycle is purely
  status-based (status flip to 'cancelled' is the decommission path).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy import text

from alembic import op

revision: str = "0017_bookings"
down_revision: str | None = "0016_trainer_availability_slots"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "bookings",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("slot_id", sa.UUID(), nullable=False),
        sa.Column("client_id", sa.UUID(), nullable=False),
        sa.Column("pt_package_id", sa.UUID(), nullable=False),
        sa.Column(
            "status",
            sa.String(length=16),
            server_default=sa.text("'confirmed'"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("created_by_user_id", sa.UUID(), nullable=False),
        sa.Column(
            "cancelled_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column("cancel_reason", sa.Text(), nullable=True),
        sa.Column(
            "no_show_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "completed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.CheckConstraint(
            "status IN ('confirmed', 'cancelled', 'no_show', 'completed')",
            name=op.f("ck_bookings_status"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_bookings")),
        sa.ForeignKeyConstraint(
            ["slot_id"],
            ["trainer_availability_slots.id"],
            name=op.f("fk_bookings_slot_id_trainer_availability_slots"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["client_id"],
            ["clients.id"],
            name=op.f("fk_bookings_client_id_clients"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["pt_package_id"],
            ["pt_packages.id"],
            name=op.f("fk_bookings_pt_package_id_pt_packages"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name=op.f("fk_bookings_created_by_user_id_users"),
            ondelete="RESTRICT",
        ),
    )
    # Partial UNIQUE — at most one confirmed booking per slot (BOOK-01 / C-02
    # / Pitfall 1). Constraint name literal-ref'd by
    # service.py:_is_slot_confirmed_conflict (D-38-15).
    op.create_index(
        "uq_bookings_slot_confirmed",
        "bookings",
        ["slot_id"],
        unique=True,
        postgresql_where=text("status = 'confirmed'"),
    )
    op.create_index(
        "ix_bookings_client_status",
        "bookings",
        ["client_id", "status"],
    )
    op.create_index(
        "ix_bookings_slot_status",
        "bookings",
        ["slot_id", "status"],
    )


def downgrade() -> None:
    op.drop_index("ix_bookings_slot_status", table_name="bookings")
    op.drop_index("ix_bookings_client_status", table_name="bookings")
    op.drop_index("uq_bookings_slot_confirmed", table_name="bookings")
    op.drop_table("bookings")
