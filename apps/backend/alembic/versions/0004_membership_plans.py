"""membership_plans

Revision ID: 0004_membership_plans
Revises: 0002_clients
Create Date: 2026-05-07 12:00:00.000000

Phase 16 / MEM-PLAN-01 — owner-only plan catalog SKU table.

Notes:
- Partial-unique on lower(name) WHERE deleted_at IS NULL is an EXPRESSION index;
  SQLAlchemy autogenerate cannot represent it. Installed via raw op.execute(...).
  Suppressed in alembic/env.py:_include_object to keep autogenerate clean.
- The constraint name "uq_membership_plans_name_alive" is referenced as a literal
  string by app/modules/memberships/service.py:_is_plan_name_conflict (D-02).
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0004_membership_plans"
down_revision: str | None = "0002_clients"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "membership_plans",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("duration_days", sa.Integer(), nullable=False),
        sa.Column("price_kopecks", sa.BigInteger(), nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
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
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "duration_days > 0",
            name=op.f("ck_membership_plans_duration_days_positive"),
        ),
        sa.CheckConstraint(
            "price_kopecks >= 0",
            name=op.f("ck_membership_plans_price_kopecks_nonneg"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_membership_plans")),
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_membership_plans_name_alive "
        "ON membership_plans (lower(name)) WHERE deleted_at IS NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_membership_plans_name_alive")
    op.drop_table("membership_plans")
