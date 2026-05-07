"""memberships

Revision ID: 0005_memberships
Revises: 0004_membership_plans
Create Date: 2026-05-07 13:00:00.000000

Phase 17 / MEM-01 — membership instance table + composite resolver index.

Notes:
- Composite index (client_id, status, end_date DESC) installs DESC ordering on
  end_date via raw op.execute(); SQLAlchemy autogenerate cannot reliably
  represent the DESC qualifier inside a multi-column index. If autogenerate
  flags drift on this index, suppress via alembic/env.py:_include_object.
- The constraint name "fk_memberships_plan_id_membership_plans" is referenced
  as a literal string by app/modules/memberships/service.py:_is_plan_in_use_conflict
  (Phase 17 D-05). Renaming the FK requires updating the service helper.
- No soft-delete column — lifecycle is purely status-based (Phase 17 D-12 /
  CONTEXT.md domain line 12). Cancelled/expired rows keep an FK reference and
  block plan deletion (D-06).
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0005_memberships"
down_revision: str | None = "0004_membership_plans"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "memberships",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("client_id", sa.UUID(), nullable=False),
        sa.Column("plan_id", sa.UUID(), nullable=False),
        sa.Column("plan_name_snapshot", sa.String(length=120), nullable=False),
        sa.Column("duration_days_snapshot", sa.Integer(), nullable=False),
        sa.Column("price_kopecks_snapshot", sa.BigInteger(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column(
            "status",
            sa.String(length=16),
            server_default=sa.text("'active'"),
            nullable=False,
        ),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancel_reason", sa.Text(), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "activation_policy",
            sa.String(length=32),
            server_default=sa.text("'purchase_date'"),
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
        sa.CheckConstraint(
            "status IN ('active', 'expired', 'cancelled')",
            name=op.f("ck_memberships_status"),
        ),
        sa.CheckConstraint(
            "activation_policy = 'purchase_date'",
            name=op.f("ck_memberships_activation_policy"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_memberships")),
        sa.ForeignKeyConstraint(
            ["client_id"],
            ["clients.id"],
            name=op.f("fk_memberships_client_id_clients"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["plan_id"],
            ["membership_plans.id"],
            # NOTE: literal-ref'd by service.py:_is_plan_in_use_conflict (D-05).
            name=op.f("fk_memberships_plan_id_membership_plans"),
            ondelete="RESTRICT",
        ),
    )
    # Composite resolver index — DESC ordering on end_date requires raw SQL
    # because SQLAlchemy's Index() representation of DESC inside a multi-column
    # mixed index is not autogenerate-stable (CD-04 + D-20).
    op.execute(
        "CREATE INDEX ix_memberships_client_id_status_end_date "
        "ON memberships (client_id, status, end_date DESC)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_memberships_client_id_status_end_date")
    op.drop_table("memberships")
