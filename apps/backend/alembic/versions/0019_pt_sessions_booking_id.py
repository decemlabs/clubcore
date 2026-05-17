"""pt_sessions.booking_id nullable FK to bookings(id)

Revision ID: 0019_pt_sessions_booking_id
Revises: 0018_pt_packages_trainer_id
Create Date: 2026-05-17 18:30:00.000000

Phase 38 PKG-04 / PKG-05 — link a recorded PT-session back to the booking
that originated it (C-03 decrement-at-delivery + Phase 37 register_booking_completer
Protocol slot consumer).

Notes:
- Nullable column: walk-in PT-sessions (no booking flow) keep booking_id = NULL.
  All pre-existing v1.4 rows get NULL on upgrade (no backfill required).
- ON DELETE RESTRICT — bookings are never hard-deleted (D-38-04 mirror); cancelled
  bookings keep their FK references for the forensic chain
  `booking_created → pt_session_recorded → pt_session_cancelled`. RESTRICT is the
  safer floor than SET NULL — if a future DBA-direct surgery attempts to delete a
  booking that still has a linked session, the FK blocks it instead of silently
  orphaning the chain.
- Single index `ix_pt_sessions_booking_id` supports the forensic lookup
  `WHERE booking_id = ?` (which session was delivered for THIS booking?).
- Constraint name `fk_pt_sessions_booking_id_bookings` mirrors the PT-14 naming
  pattern from migration 0015_pt_sessions; literal-referenced by
  `app/modules/pt_sessions/models.py:PtSession.booking_id` for clarity (no
  IntegrityError discriminator translates it — booking validation runs in
  service layer per D-38-19 SELECT FOR UPDATE pre-check).
- Alembic chain: 0017_bookings → 0018_pt_packages_trainer_id → 0019_pt_sessions_booking_id.
- 3-step upgrade template (same shape as 0009_renewal + 0018):
    1. add_column nullable
    2. create_foreign_key with explicit name
    3. create_index on the FK column
  Downgrade reverses order (drop_index → drop_constraint → drop_column).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0019_pt_sessions_booking_id"
down_revision: str | None = "0018_pt_packages_trainer_id"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1) Add nullable column. All existing pt_sessions rows get NULL (walk-ins).
    op.add_column(
        "pt_sessions",
        sa.Column("booking_id", sa.UUID(), nullable=True),
    )

    # 2) FK to bookings.id. ON DELETE RESTRICT — bookings are never hard-deleted
    #    (D-38-04). Protects the forensic chain from accidental DBA-direct surgery.
    op.create_foreign_key(
        op.f("fk_pt_sessions_booking_id_bookings"),
        "pt_sessions",
        "bookings",
        ["booking_id"],
        ["id"],
        ondelete="RESTRICT",
    )

    # 3) Index for forensic lookup `WHERE booking_id = ?`.
    op.create_index(
        op.f("ix_pt_sessions_booking_id"),
        "pt_sessions",
        ["booking_id"],
    )


def downgrade() -> None:
    """Reverse upgrade in reverse order — preserves row data, drops link only."""
    op.drop_index(
        op.f("ix_pt_sessions_booking_id"),
        table_name="pt_sessions",
    )
    op.drop_constraint(
        op.f("fk_pt_sessions_booking_id_bookings"),
        "pt_sessions",
        type_="foreignkey",
    )
    op.drop_column("pt_sessions", "booking_id")
