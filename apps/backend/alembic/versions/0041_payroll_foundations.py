"""trainer_comp_configs + trainer_payroll_accruals tables (Phase 58 PAY-01..03 / D-58-02..05).

Revision ID: 0041_payroll_foundations
Revises: 0040_audit_log_report_indexes
Create Date: 2026-05-25 00:00:00.000000

Phase 58 PAY-01..06 schema. Ships TWO tables + partial UNIQUE (excluding
clawback rows per D-58-03) in ONE migration (atomic per success-criterion #5).

Partial UNIQUE pattern mirrors Phase 32 uq_payments_refund_of_alive and
Phase 49 uq_online_payments_*_double_tap precedent.

ORM model is intentionally NOT added by this migration; Plan 58-04 owns
``app/modules/payroll/models.py``.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy import text
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0041_payroll_foundations"
down_revision: str | None = "0040_audit_log_report_indexes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── Table 1: trainer_comp_configs (INSERT-only versioned, D-58-02) ──────────
    # No UNIQUE(trainer_id): multiple rows per trainer are allowed — each INSERT
    # creates a new version. Resolver picks ORDER BY effective_from DESC LIMIT 1
    # WHERE effective_from <= :as_of_date. Created FIRST — accruals FK into it.
    op.create_table(
        "trainer_comp_configs",
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
                name=op.f("fk_trainer_comp_configs_trainer_id_trainers"),
            ),
            nullable=False,
        ),
        # Economics columns: both NULL is allowed at write time; both NULL at
        # accrual run time → 422 comp_config_missing (D-58-09 / D-58-02).
        sa.Column("commission_pct_bps", sa.Integer(), nullable=True),
        sa.Column("session_fee_kopecks", sa.Integer(), nullable=True),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "created_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "users.id",
                ondelete="RESTRICT",
                name=op.f("fk_trainer_comp_configs_created_by_user_id_users"),
            ),
            nullable=True,
        ),
        # D-58-04: bps cap 0..10000 (100%); NULL means "not set" (hybrid config)
        sa.CheckConstraint(
            "commission_pct_bps IS NULL"
            " OR (commission_pct_bps >= 0 AND commission_pct_bps <= 10000)",
            name=op.f("ck_trainer_comp_configs_commission_pct_bps_range"),
        ),
        # Non-negative session fee; NULL means "not set" (hybrid config)
        sa.CheckConstraint(
            "session_fee_kopecks IS NULL OR session_fee_kopecks >= 0",
            name=op.f("ck_trainer_comp_configs_session_fee_kopecks_nonneg"),
        ),
    )
    # Composite index — resolves latest effective config for a trainer efficiently
    op.create_index(
        "ix_trainer_comp_configs_trainer_effective",
        "trainer_comp_configs",
        ["trainer_id", text("effective_from DESC")],
    )

    # ── Table 2: trainer_payroll_accruals (append-only signed-amount, D-58-03) ──
    # Created SECOND because it FKs into trainer_comp_configs (comp_config_id_snapshot).
    # NO TimestampMixin — accrued_at is the single creation temporal column (mirrors
    # Payment append-only discipline: apps/backend/app/modules/payments/models.py:1-19).
    # The only allowed post-INSERT mutation is the single status='pending'→'paid'
    # transition (paid_at, paid_by_user_id, status columns). No UPDATE to any other
    # column. Clawback rows are INSERTs with negative accrual_kopecks (NOT UPDATE).
    op.create_table(
        "trainer_payroll_accruals",
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
                name=op.f("fk_trainer_payroll_accruals_trainer_id_trainers"),
            ),
            nullable=False,
        ),
        # Period bounds — inclusive [period_start, period_end] MSK dates (D-58-05)
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        # Snapshot columns — frozen at INSERT time; never recomputed (D-58-03 / D-58-04)
        sa.Column("sessions_count", sa.Integer(), nullable=False),
        sa.Column("revenue_kopecks", sa.Integer(), nullable=False),
        # NULL when config was session-fee-only; NULL when config was pct-only
        sa.Column("commission_pct_bps_snapshot", sa.Integer(), nullable=True),
        sa.Column("session_fee_kopecks_snapshot", sa.Integer(), nullable=True),
        sa.Column(
            "comp_config_id_snapshot",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "trainer_comp_configs.id",
                ondelete="RESTRICT",
                name=op.f("fk_trainer_payroll_accruals_comp_config_id_snapshot"),
            ),
            nullable=False,
        ),
        # Signed: positive for regular accruals; negative for clawback rows (D-58-03)
        # NO >= 0 CHECK — clawback rows intentionally carry negative amounts (T-58-08)
        sa.Column("accrual_kopecks", sa.Integer(), nullable=False),
        # Lifecycle: single-transition 'pending' → 'paid' (PAY-04 / D-58-08)
        sa.Column(
            "status",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column(
            "accrued_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "paid_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "users.id",
                ondelete="RESTRICT",
                name=op.f("fk_trainer_payroll_accruals_paid_by_user_id_users"),
            ),
            nullable=True,
        ),
        # Clawback self-FK — mirrors Payment.refund_of (payments/models.py:81-89)
        # NULL on regular accrual rows; NOT NULL on clawback rows (D-58-03 / PAY-06)
        sa.Column(
            "clawback_of_accrual_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "trainer_payroll_accruals.id",
                ondelete="RESTRICT",
                name=op.f("fk_trainer_payroll_accruals_clawback_of_accrual_id"),
            ),
            nullable=True,
        ),
        # FK to the refund payment row that triggered this clawback (PAY-06)
        sa.Column(
            "source_refund_payment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "payments.id",
                ondelete="RESTRICT",
                name=op.f("fk_trainer_payroll_accruals_source_refund_payment_id"),
            ),
            nullable=True,
        ),
        # Audit hash chain reference; SET NULL preserves accrual if audit row pruned
        sa.Column(
            "audit_log_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "audit_log.id",
                ondelete="SET NULL",
                name=op.f("fk_trainer_payroll_accruals_audit_log_id_audit_log"),
            ),
            nullable=True,
        ),
        # T-58-08: only two lifecycle states; clawback rows start as 'pending'
        sa.CheckConstraint(
            "status IN ('pending','paid')",
            name=op.f("ck_trainer_payroll_accruals_status"),
        ),
        # T-58-10: clawback FKs are both NULL (regular row) or both NOT NULL (clawback row)
        sa.CheckConstraint(
            "(clawback_of_accrual_id IS NULL AND source_refund_payment_id IS NULL)"
            " OR (clawback_of_accrual_id IS NOT NULL AND source_refund_payment_id IS NOT NULL)",
            name=op.f("ck_trainer_payroll_accruals_clawback_fks_paired"),
        ),
    )
    # Partial UNIQUE — covers only regular accrual rows (clawback_of_accrual_id IS NULL).
    # Mirrors uq_payments_refund_of_alive (payments/models.py:112-117) and the
    # Phase 49 double-tap guard pattern (0034_online_payments.py:139-156).
    # T-58-09: DB-wins-the-race idempotency: ON CONFLICT DO NOTHING targets this index.
    op.create_index(
        "uq_trainer_payroll_accruals_period_alive",
        "trainer_payroll_accruals",
        ["trainer_id", "period_start", "period_end"],
        unique=True,
        postgresql_where=text("clawback_of_accrual_id IS NULL"),
    )
    # PAY-05: list ordering index — accrued_at DESC per D-58-14
    op.create_index(
        "ix_trainer_payroll_accruals_trainer_accrued",
        "trainer_payroll_accruals",
        ["trainer_id", text("accrued_at DESC")],
    )
    # Pending-accrual queries — status + period_start DESC per D-58-14
    op.create_index(
        "ix_trainer_payroll_accruals_status_period",
        "trainer_payroll_accruals",
        ["status", text("period_start DESC")],
    )


def downgrade() -> None:
    # T-58-11: drop accruals FIRST (it FKs configs), then configs. FK-safe reverse order.
    # Drop indexes before dropping tables.
    op.drop_index(
        "ix_trainer_payroll_accruals_status_period",
        table_name="trainer_payroll_accruals",
    )
    op.drop_index(
        "ix_trainer_payroll_accruals_trainer_accrued",
        table_name="trainer_payroll_accruals",
    )
    op.drop_index(
        "uq_trainer_payroll_accruals_period_alive",
        table_name="trainer_payroll_accruals",
    )
    op.drop_table("trainer_payroll_accruals")
    op.drop_index(
        "ix_trainer_comp_configs_trainer_effective",
        table_name="trainer_comp_configs",
    )
    op.drop_table("trainer_comp_configs")
