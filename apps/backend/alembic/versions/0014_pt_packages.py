"""pt_packages

Revision ID: 0014_pt_packages
Revises: 0013_pt_package_plans
Create Date: 2026-05-15 12:30:00.000000

Phase 33 PT-04 / PT-05 — PT-package instance (one row per client purchase).

Notes:
- Partial UNIQUE on (client_id) WHERE status='active' is the active-per-client
  invariant (PT-05). Installed via op.create_index(postgresql_where=...);
  the constraint name "uq_pt_packages_active_per_client" is referenced as a
  literal string by app/modules/pt_packages/service.py:_is_active_pt_package_conflict
  (D-33-09 mirror of payments uq_payments_refund_of_alive translation).
- start_date and end_date are APPLICATION-COMPUTED (no DB-side
  Europe/Moscow server_default — D-33-03 stored-not-virtual choice).
  service.create_pt_package supplies both at INSERT time; end_date is NULL
  iff validity_days_snapshot is NULL (бессрочный package — D-33-14).
- Snapshot fields (plan_name_snapshot / session_count_snapshot /
  price_kopecks_snapshot / validity_days_snapshot) preserve historical
  readability after plan archive (D-33-02 / D-33-03).
- FK ON DELETE RESTRICT on both client_id and plan_id — never cascade-delete
  PT-package history.
- NO SoftDeleteMixin / deleted_at column — lifecycle is purely status-based
  per Phase 17 D-12 precedent (mirrors memberships table shape).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy import text

from alembic import op

revision: str = "0014_pt_packages"
down_revision: str | None = "0013_pt_package_plans"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "pt_packages",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("client_id", sa.UUID(), nullable=False),
        sa.Column("plan_id", sa.UUID(), nullable=False),
        sa.Column("plan_name_snapshot", sa.String(length=120), nullable=False),
        sa.Column("session_count_snapshot", sa.Integer(), nullable=False),
        sa.Column("price_kopecks_snapshot", sa.BigInteger(), nullable=False),
        sa.Column("validity_days_snapshot", sa.Integer(), nullable=True),
        sa.Column("sessions_remaining", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.String(length=16),
            server_default=sa.text("'active'"),
            nullable=False,
        ),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("cancellation_reason", sa.Text(), nullable=True),
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
            "status IN ('active', 'exhausted', 'expired', 'cancelled')",
            name=op.f("ck_pt_packages_status"),
        ),
        sa.CheckConstraint(
            "sessions_remaining >= 0 AND sessions_remaining <= session_count_snapshot",
            name=op.f("ck_pt_packages_sessions_remaining_bounded"),
        ),
        sa.CheckConstraint(
            "session_count_snapshot > 0",
            name=op.f("ck_pt_packages_session_count_snapshot_positive"),
        ),
        sa.CheckConstraint(
            "price_kopecks_snapshot > 0",
            name=op.f("ck_pt_packages_price_kopecks_snapshot_positive"),
        ),
        sa.CheckConstraint(
            "validity_days_snapshot IS NULL OR validity_days_snapshot > 0",
            name=op.f("ck_pt_packages_validity_days_snapshot_positive"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_pt_packages")),
        sa.ForeignKeyConstraint(
            ["client_id"],
            ["clients.id"],
            name=op.f("fk_pt_packages_client_id_clients"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["plan_id"],
            ["pt_package_plans.id"],
            # Literal-ref'd by service.py:_is_pt_package_plan_in_use_conflict
            # (defence-in-depth; pre-flight repository.has_instances_for_plan is
            # the primary gate per D-33-08).
            name=op.f("fk_pt_packages_plan_id_pt_package_plans"),
            ondelete="RESTRICT",
        ),
    )
    # Partial UNIQUE — at most one active PT-package per client (PT-05 / D-33-09).
    # Constraint name literal-ref'd by service.py:_is_active_pt_package_conflict.
    op.create_index(
        "uq_pt_packages_active_per_client",
        "pt_packages",
        ["client_id"],
        unique=True,
        postgresql_where=text("status = 'active'"),
    )
    op.create_index("ix_pt_packages_client_id", "pt_packages", ["client_id"])
    op.create_index("ix_pt_packages_status", "pt_packages", ["status"])
    op.create_index("ix_pt_packages_plan_id", "pt_packages", ["plan_id"])


def downgrade() -> None:
    op.drop_index("ix_pt_packages_plan_id", table_name="pt_packages")
    op.drop_index("ix_pt_packages_status", table_name="pt_packages")
    op.drop_index("ix_pt_packages_client_id", table_name="pt_packages")
    op.drop_index("uq_pt_packages_active_per_client", table_name="pt_packages")
    op.drop_table("pt_packages")
