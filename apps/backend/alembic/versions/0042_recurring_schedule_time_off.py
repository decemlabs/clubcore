"""recurring_slot_templates + trainer_time_off tables + slot ALTER (Phase 59 REC-01..04).

Revision ID: 0042_recurring_schedule_time_off
Revises: 0041_payroll_foundations
Create Date: 2026-05-25 00:00:00.000000

Phase 59 REC-01..04 schema. Ships TWO new tables + one ALTER on an existing
table in ONE migration (atomic; 0041 two-tables-one-revision precedent).

recurring_slot_templates  — REC-01 recurring availability patterns per trainer
                            (day_of_week, start_time, end_time, valid_from,
                            valid_until, is_active).  UNIQUE (trainer_id,
                            day_of_week, start_time, valid_from) is the
                            verbatim REC-01 idempotency key.

trainer_time_off          — REC-03 time-off blocks (block_start / block_end
                            TIMESTAMPTZ).  CHECK block_end > block_start.
                            btree index on (trainer_id, block_start) backs
                            overlap queries in the conflict service.

ALTER trainer_availability_slots
  (a) created_by_user_id → NULLABLE: cron-generated slots have no human author
      (D-59-05 / REC-02).
  (b) UNIQUE (trainer_id, start_time): backs ON CONFLICT (trainer_id, start_time)
      DO NOTHING in the recurring-slot cron (PITFALL 8 idempotency).

ORM models are added by Plan 59-03 (app/modules/schedule/models.py).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0042_recurring_schedule_time_off"
down_revision: str | None = "0041_payroll_foundations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── Table 1: recurring_slot_templates (REC-01) ───────────────────────────
    # Recurring availability patterns — owner defines a weekly recurrence per
    # trainer.  The ARQ cron (Plan 59-05) materialises concrete
    # trainer_availability_slots rows from these templates inside the rolling
    # RECURRING_SLOT_HORIZON_DAYS (default 56) window ahead.
    # UNIQUE (trainer_id, day_of_week, start_time, valid_from) is the REC-01
    # verbatim contract — prevents duplicate pattern rows for the same slot.
    op.create_table(
        "recurring_slot_templates",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "trainer_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "trainers.id",
                ondelete="RESTRICT",
                name=op.f("fk_recurring_slot_templates_trainer_id_trainers"),
            ),
            nullable=False,
        ),
        # 0 = Monday … 6 = Sunday (ISO weekday convention; CHECK enforces range)
        sa.Column("day_of_week", sa.SmallInteger(), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.Column("valid_from", sa.Date(), nullable=False),
        # NULL means "open-ended pattern" (no expiry date)
        sa.Column("valid_until", sa.Date(), nullable=True),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        # TimestampMixin equivalent (created_at / updated_at TIMESTAMPTZ)
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        # day_of_week must be in [0, 6] (Mon-Sun)
        sa.CheckConstraint(
            "day_of_week >= 0 AND day_of_week <= 6",
            name=op.f("ck_recurring_slot_templates_day_of_week"),
        ),
        # Slot window must be positive
        sa.CheckConstraint(
            "end_time > start_time",
            name=op.f("ck_recurring_slot_templates_end_after_start"),
        ),
        # valid_until must not precede valid_from when set
        sa.CheckConstraint(
            "valid_until IS NULL OR valid_until >= valid_from",
            name=op.f("ck_recurring_slot_templates_valid_window"),
        ),
    )
    # REC-01 verbatim UNIQUE — prevents duplicate recurring patterns for the
    # same trainer on the same weekday / time combination effective from the
    # same date (the fourth column disambiguates versioned replacements).
    op.create_index(
        op.f("uq_recurring_slot_templates_trainer_id"),
        "recurring_slot_templates",
        ["trainer_id", "day_of_week", "start_time", "valid_from"],
        unique=True,
    )

    # ── Table 2: trainer_time_off (REC-03) ───────────────────────────────────
    # Time-off blocks.  Creation triggers the conflict-guard service (D-59-06):
    # cancels overlapping active slots; raises 409 on booked overlaps (unless
    # ?force=true, which cascades booking-FSM cancellation + client DM).
    op.create_table(
        "trainer_time_off",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "trainer_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "trainers.id",
                ondelete="RESTRICT",
                name=op.f("fk_trainer_time_off_trainer_id_trainers"),
            ),
            nullable=False,
        ),
        # TIMESTAMPTZ — always stored in UTC (D-59-05 / PITFALL 7)
        sa.Column("block_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("block_end", sa.DateTime(timezone=True), nullable=False),
        # Human-readable note from the owner (e.g. "vacation", "sick leave")
        sa.Column("reason", sa.Text(), nullable=True),
        # TimestampMixin equivalent
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        # Block must span a positive duration (T-59-04 / D-59-06)
        sa.CheckConstraint(
            "block_end > block_start",
            name=op.f("ck_trainer_time_off_block_end_after_start"),
        ),
    )
    # Support efficient overlap queries in the time-off conflict service and the
    # cron NOT EXISTS predicate (PITFALL 9): trainer + block_start btree.
    op.create_index(
        op.f("ix_trainer_time_off_trainer_id"),
        "trainer_time_off",
        ["trainer_id", "block_start"],
    )

    # ── ALTER trainer_availability_slots (D-59-05 / REC-02) ──────────────────
    # (a) Make created_by_user_id nullable: cron-generated slots carry NULL
    #     for this column (no human author); mirrors 0021 bookings precedent.
    op.alter_column(
        "trainer_availability_slots",
        "created_by_user_id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=True,
        existing_nullable=False,
    )
    # (b) UNIQUE (trainer_id, start_time): backs ON CONFLICT (trainer_id,
    #     start_time) DO NOTHING in the recurring-slot cron so repeat ticks are
    #     true no-ops (PITFALL 8).  Named with "uq_" prefix per NAMING_CONVENTION.
    op.create_index(
        "uq_trainer_availability_slots_trainer_id_start_time",
        "trainer_availability_slots",
        ["trainer_id", "start_time"],
        unique=True,
    )


def downgrade() -> None:
    # Reverse order is the FK-safe teardown sequence:
    # 1. Undo the slot ALTER (unique index + nullable revert).
    # 2. Drop trainer_time_off (index then table).
    # 3. Drop recurring_slot_templates (unique index then table).

    # ── Undo ALTER trainer_availability_slots ────────────────────────────────
    op.drop_index(
        "uq_trainer_availability_slots_trainer_id_start_time",
        table_name="trainer_availability_slots",
    )
    # Downgrade guard mirrors 0021: fail loudly if cron-generated NULL rows
    # exist so the operator cannot silently violate the restored NOT NULL.
    conn = op.get_bind()
    null_count = conn.execute(
        sa.text(
            "SELECT COUNT(*) FROM trainer_availability_slots"
            " WHERE created_by_user_id IS NULL"
        )
    ).scalar_one()
    if null_count > 0:
        raise RuntimeError(
            "cannot downgrade: NULL created_by_user_id rows present in"
            f" trainer_availability_slots ({null_count} rows);"
            " operator must remove cron-generated slots first"
        )
    op.alter_column(
        "trainer_availability_slots",
        "created_by_user_id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=False,
        existing_nullable=True,
    )

    # ── Drop trainer_time_off ────────────────────────────────────────────────
    op.drop_index(
        op.f("ix_trainer_time_off_trainer_id"),
        table_name="trainer_time_off",
    )
    op.drop_table("trainer_time_off")

    # ── Drop recurring_slot_templates ────────────────────────────────────────
    op.drop_index(
        op.f("uq_recurring_slot_templates_trainer_id"),
        table_name="recurring_slot_templates",
    )
    op.drop_table("recurring_slot_templates")
