"""Phase 25 / MEM-FRZ-01..03: membership freeze schema foundation.

Revision ID: 0008_freeze
Revises: 0007_status_taxonomy
Create Date: 2026-05-08 00:00:00.000000

Notes:
- The partial unique index `uq_membership_freeze_periods_active_per_membership`
  is installed via raw `op.execute()` because expression-where unique indexes
  are not autogenerate-stable (mirrors the `uq_membership_plans_name_alive`
  pattern in 0004_membership_plans.py). Suppressed in alembic/env.py:_include_object
  to keep `alembic check` clean (D-25-05).
- The constraint name literal `uq_membership_freeze_periods_active_per_membership`
  is referenced by `app/modules/memberships/service.py:_is_already_frozen_conflict`
  in Phase 25's service plan. Renaming requires updating that helper (D-25-22).
- Backfill semantics for `memberships.freeze_days_limit_snapshot` use
  `COALESCE(plan.freeze_days_limit, 14)`: archived-plan rows lock to 14 by
  snapshot semantics. New sales snapshot at sale time (Phase 25 service plan).
- Downgrade is DATA-LOSSY: dropping `freeze_days_limit_snapshot` discards the
  per-membership snapshot which cannot be re-derived after the plan column is
  also dropped. Disaster-recovery only (D-25-03).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0008_freeze"
down_revision: str | None = "0007_status_taxonomy"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1) membership_plans.freeze_days_limit — add NOT NULL with DEFAULT 14
    #    (backfills existing rows), then drop default so future inserts must
    #    provide an explicit value (mirror duration_days immutability pattern).
    op.add_column(
        "membership_plans",
        sa.Column(
            "freeze_days_limit",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("14"),
        ),
    )
    op.alter_column("membership_plans", "freeze_days_limit", server_default=None)
    op.create_check_constraint(
        op.f("ck_membership_plans_freeze_days_limit_positive"),
        "membership_plans",
        "freeze_days_limit > 0",
    )

    # 2) memberships.freeze_days_limit_snapshot — nullable, then backfill, then SET NOT NULL.
    op.add_column(
        "memberships",
        sa.Column("freeze_days_limit_snapshot", sa.Integer(), nullable=True),
    )

    # 3) Backfill: COALESCE(plan.freeze_days_limit, 14) — archived plans → 14.
    op.execute(
        "UPDATE memberships m SET freeze_days_limit_snapshot = "
        "COALESCE((SELECT freeze_days_limit FROM membership_plans WHERE id = m.plan_id), 14)"
    )

    # 4) SET NOT NULL on memberships.freeze_days_limit_snapshot.
    op.alter_column("memberships", "freeze_days_limit_snapshot", nullable=False)

    # 5) CREATE TABLE membership_freeze_periods.
    op.create_table(
        "membership_freeze_periods",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("membership_id", sa.UUID(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_by", sa.UUID(), nullable=False),
        sa.Column("ended_by", sa.UUID(), nullable=True),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_membership_freeze_periods")),
        sa.ForeignKeyConstraint(
            ["membership_id"],
            ["memberships.id"],
            name=op.f("fk_membership_freeze_periods_membership_id_memberships"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["started_by"],
            ["users.id"],
            name=op.f("fk_membership_freeze_periods_started_by_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["ended_by"],
            ["users.id"],
            name=op.f("fk_membership_freeze_periods_ended_by_users"),
            ondelete="SET NULL",
        ),
    )

    # 6) Partial unique index — single open period per membership.
    #    Literal-ref'd by service.py:_is_already_frozen_conflict (D-25-22).
    op.execute(
        "CREATE UNIQUE INDEX uq_membership_freeze_periods_active_per_membership "
        "ON membership_freeze_periods (membership_id) WHERE ended_at IS NULL"
    )


def downgrade() -> None:
    """Reverse upgrade in reverse order — DATA-LOSSY (D-25-03).

    Snapshots stored in `memberships.freeze_days_limit_snapshot` cannot be
    re-derived after the column is dropped (the source plan rows may have
    been edited, archived, or deleted in the interim). Downgrade is for
    disaster recovery only.
    """
    op.execute("DROP INDEX IF EXISTS uq_membership_freeze_periods_active_per_membership")
    op.drop_table("membership_freeze_periods")
    op.drop_column("memberships", "freeze_days_limit_snapshot")
    op.drop_constraint(
        op.f("ck_membership_plans_freeze_days_limit_positive"),
        "membership_plans",
        type_="check",
    )
    op.drop_column("membership_plans", "freeze_days_limit")
