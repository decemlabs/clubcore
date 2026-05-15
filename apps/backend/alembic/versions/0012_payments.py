"""payments

Revision ID: 0012_payments
Revises: 0011_trainers
Create Date: 2026-05-15 00:00:00.000000

Phase 32 PAY-01 + REF-01 — payments ledger table + memberships.cancellation_reason ALTER.

D-32-01..D-32-09 / B-01 — append-only ledger:
- 9-column payments table (subject_kind/subject_id/amount_kopecks signed/method/received_at/
  received_by_user_id/refund_of/audit_log_id/id).
- NO created_at, NO updated_at, NO deleted_at columns; received_at is the SINGLE temporal
  column (B-01 INFRA-22).
- CHECK ck_payments_amount_sign_matches_subject_kind enforces amount sign agrees with kind.
- CHECK ck_payments_subject_kind locks the enum to ('membership','pt_package','refund').
- Partial UNIQUE uq_payments_refund_of_alive ON (refund_of) WHERE refund_of IS NOT NULL —
  guarantees at most one refund per original sale.
- Three regular indexes: ix_payments_subject, ix_payments_received_by_user_id,
  ix_payments_received_at (DESC).

Also: ALTER TABLE memberships ADD COLUMN cancellation_reason TEXT NULL (REF-01 / D-32-07).
Coexists with the existing cancel_reason column (NOT renamed); legacy cancelled rows stay
NULL — no backfill. Plan 32-03 sets sentinel 'refunded' via refund_membership orchestrator.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy import text

from alembic import op

revision: str = "0012_payments"
down_revision: str | None = "0011_trainers"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "payments",
        sa.Column("subject_kind", sa.Text(), nullable=False),
        sa.Column("subject_id", sa.UUID(), nullable=False),
        sa.Column("amount_kopecks", sa.Integer(), nullable=False),
        sa.Column(
            "method",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'cash'"),
        ),
        sa.Column(
            "received_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("received_by_user_id", sa.UUID(), nullable=False),
        sa.Column("refund_of", sa.UUID(), nullable=True),
        sa.Column("audit_log_id", sa.UUID(), nullable=True),
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["received_by_user_id"],
            ["users.id"],
            ondelete="RESTRICT",
            name=op.f("fk_payments_received_by_user_id_users"),
        ),
        sa.ForeignKeyConstraint(
            ["refund_of"],
            ["payments.id"],
            ondelete="RESTRICT",
            name=op.f("fk_payments_refund_of_payments"),
        ),
        sa.ForeignKeyConstraint(
            ["audit_log_id"],
            ["audit_log.id"],
            ondelete="SET NULL",
            name=op.f("fk_payments_audit_log_id_audit_log"),
        ),
        sa.CheckConstraint(
            "(subject_kind = 'refund' AND amount_kopecks < 0) "
            "OR (subject_kind IN ('membership','pt_package') AND amount_kopecks > 0)",
            name=op.f("ck_payments_amount_sign_matches_subject_kind"),
        ),
        sa.CheckConstraint(
            "subject_kind IN ('membership','pt_package','refund')",
            name=op.f("ck_payments_subject_kind"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_payments")),
    )

    op.create_index(
        "ix_payments_subject",
        "payments",
        ["subject_kind", "subject_id"],
    )
    op.create_index(
        "ix_payments_received_by_user_id",
        "payments",
        ["received_by_user_id"],
    )
    # DESC ordering on received_at — operator listing is reverse-chronological.
    op.create_index(
        "ix_payments_received_at",
        "payments",
        [text("received_at DESC")],
    )
    # Partial UNIQUE — at most one refund row per original sale.
    op.create_index(
        "uq_payments_refund_of_alive",
        "payments",
        ["refund_of"],
        unique=True,
        postgresql_where=text("refund_of IS NOT NULL"),
    )

    # Phase 32 REF-01 / D-32-07 — sentinel 'refunded' lives here (set by refund_membership
    # orchestrator in Plan 32-03). NO CHECK constraint: legacy cancelled rows stay NULL.
    op.add_column(
        "memberships",
        sa.Column("cancellation_reason", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("memberships", "cancellation_reason")
    op.drop_index("uq_payments_refund_of_alive", table_name="payments")
    op.drop_index("ix_payments_received_at", table_name="payments")
    op.drop_index("ix_payments_received_by_user_id", table_name="payments")
    op.drop_index("ix_payments_subject", table_name="payments")
    op.drop_table("payments")
