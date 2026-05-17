"""trainer_availability_slots

Revision ID: 0016_trainer_availability_slots
Revises: 0015_pt_sessions
Create Date: 2026-05-17 14:30:00.000000

Phase 38 SLOT-01 — Trainer availability slot table (one row per published 1:1
PT slot).

Notes:
- TIMESTAMPTZ (DateTime(timezone=True)) for start_time / end_time per Pitfall 6;
  container TZ is UTC and Europe/Moscow business-day math lives in service code.
- Status CHECK admits ('active', 'booked', 'cancelled') per D-38-03 (NOT
  'available'). Constraint name `ck_trainer_availability_slots_status` is
  literal-referenced by app/modules/schedule/service.py:_assert_can_transition
  via the SLOT_STATUS_TRANSITIONS constant.
- CHECK end_time > start_time guards against zero-or-negative duration slots
  at the DB layer (defence-in-depth alongside schema-layer validation).
- Two indexes (D-38-04 partial-for-active-discovery + full btree for trainer
  timeline scans). NO partial UNIQUE on this table — the partial UNIQUE for
  per-slot booking integrity lives on the `bookings` table in 0017.
- FK to trainers.id ON DELETE RESTRICT — trainers are soft-deleted via
  is_active, never hard-deleted; RESTRICT preserves audit-trail integrity.
- FK to users.id (created_by_user_id) ON DELETE RESTRICT — author of the
  publication is forensic-critical, never cascade-delete.
- NO SoftDeleteMixin / deleted_at column per D-38-04 — lifecycle is purely
  status-based (status flip to 'cancelled' is the decommission path).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy import text

from alembic import op

revision: str = "0016_trainer_availability_slots"
down_revision: str | None = "0015_pt_sessions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "trainer_availability_slots",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("trainer_id", sa.UUID(), nullable=False),
        sa.Column(
            "start_time",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "end_time",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=16),
            server_default=sa.text("'active'"),
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
        sa.CheckConstraint(
            "status IN ('active', 'booked', 'cancelled')",
            name=op.f("ck_trainer_availability_slots_status"),
        ),
        sa.CheckConstraint(
            "end_time > start_time",
            name=op.f("ck_trainer_availability_slots_end_after_start"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_trainer_availability_slots")),
        sa.ForeignKeyConstraint(
            ["trainer_id"],
            ["trainers.id"],
            name=op.f("fk_trainer_availability_slots_trainer_id_trainers"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name=op.f("fk_trainer_availability_slots_created_by_user_id_users"),
            ondelete="RESTRICT",
        ),
    )
    # Composite btree — trainer timeline scans (publish overlap-check, list-by-trainer).
    op.create_index(
        "ix_trainer_availability_slots_trainer_start_time",
        "trainer_availability_slots",
        ["trainer_id", "start_time"],
    )
    # Partial index — active-only discovery queries (SLOT-08 listing default,
    # publish-overlap candidate scan).
    op.create_index(
        "ix_trainer_availability_slots_active_start_time",
        "trainer_availability_slots",
        ["status", "start_time"],
        postgresql_where=text("status = 'active'"),
    )


def downgrade() -> None:
    op.drop_index(
        "ix_trainer_availability_slots_active_start_time",
        table_name="trainer_availability_slots",
    )
    op.drop_index(
        "ix_trainer_availability_slots_trainer_start_time",
        table_name="trainer_availability_slots",
    )
    op.drop_table("trainer_availability_slots")
