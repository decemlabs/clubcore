"""pt_package_plans

Revision ID: 0013_pt_package_plans
Revises: 0012_payments
Create Date: 2026-05-15 12:00:00.000000

Phase 33 PT-01 — owner-only PT-package catalog SKU table.

Notes:
- Partial-unique on lower(name) WHERE deleted_at IS NULL is an EXPRESSION index;
  SQLAlchemy autogenerate cannot represent it. Installed via raw op.execute(...).
  Suppressed in alembic/env.py:_include_object to keep autogenerate clean.
- The constraint name "uq_pt_package_plans_name_alive" is referenced as a literal
  string by app/modules/pt_packages/service.py:_is_pt_package_plan_name_conflict
  (D-33-02 mirror of memberships D-02).
- Phase 33 D-33-02 column shape:
    id UUID PK gen_random_uuid()
    name TEXT NOT NULL
    session_count INT NOT NULL CHECK > 0 (immutable post-create — D-33-07)
    price_kopecks BIGINT NOT NULL CHECK > 0 (immutable post-create — D-33-07)
    validity_days INT NULL CHECK > 0 (NULL = no time-expiry; immutable post-create)
    deleted_at TIMESTAMPTZ NULL (soft-delete)
    created_at + updated_at TIMESTAMPTZ NOT NULL default now()
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0013_pt_package_plans"
down_revision: str | None = "0012_payments"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "pt_package_plans",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("session_count", sa.Integer(), nullable=False),
        sa.Column("price_kopecks", sa.BigInteger(), nullable=False),
        sa.Column("validity_days", sa.Integer(), nullable=True),
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
            "session_count > 0",
            name=op.f("ck_pt_package_plans_session_count_positive"),
        ),
        sa.CheckConstraint(
            "price_kopecks > 0",
            name=op.f("ck_pt_package_plans_price_kopecks_positive"),
        ),
        sa.CheckConstraint(
            "validity_days IS NULL OR validity_days > 0",
            name=op.f("ck_pt_package_plans_validity_days_positive"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_pt_package_plans")),
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_pt_package_plans_name_alive "
        "ON pt_package_plans (lower(name)) WHERE deleted_at IS NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_pt_package_plans_name_alive")
    op.drop_table("pt_package_plans")
