"""0035 — fiscal_receipts table (Phase 50 FISCAL-01 / FISCAL-02 / D-50-30).

Creates the fiscal_receipts table holding 54-ФЗ receipt lifecycle rows.
``payment_id`` FK targets ``payments.id`` (NOT ``online_payments.id``)
because the fiscal obligation attaches to the committed ledger row, per
FEATURES.md SUMMARY line 104 and T-50-01-01 mitigation.

NAMING_CONVENTION: op.f() wrappers on PK / FK / CHECK / UNIQUE; mirrors
the 0034 byte-for-byte convention. Constraint name
``uq_fiscal_receipts_payment_id_kind`` is the cross-channel-discriminator
UNIQUE (one payment row may have at most one 'payment' receipt + one
'refund' receipt — D-50-30, FISCAL-02).

Downgrade order: drop the UNIQUE constraint BEFORE drop_table so
partial-state teardowns fail loudly rather than leave a phantom index
behind (T-50-01-05 mitigation).

ORM model lives at app/modules/fiscal_receipts/models.py (Plan 50-01 Task 1)
and uses BARE-suffix CHECK names so SA NAMING_CONVENTION expands to the
same literal Alembic 0035 wrote via ``op.f("ck_fiscal_receipts_*")``
(avoids the double-prefix bug fixed by Plan 49-01 deviation #2).

Revision ID: 0035_fiscal_receipts
Revises: 0034_online_payments
Create Date: 2026-05-22 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0035_fiscal_receipts"
down_revision: str | None = "0034_online_payments"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "fiscal_receipts",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("payment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("yookassa_receipt_id", sa.Text(), nullable=True),
        sa.Column("customer_email", sa.Text(), nullable=False),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("succeeded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("audit_correlation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_fiscal_receipts")),
        sa.ForeignKeyConstraint(
            ["payment_id"],
            ["payments.id"],
            name=op.f("fk_fiscal_receipts_payment_id_payments"),
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "kind IN ('payment', 'refund')",
            name=op.f("ck_fiscal_receipts_kind"),
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'sent', 'succeeded', 'failed')",
            name=op.f("ck_fiscal_receipts_status"),
        ),
        sa.UniqueConstraint(
            "payment_id",
            "kind",
            name=op.f("uq_fiscal_receipts_payment_id_kind"),
        ),
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("uq_fiscal_receipts_payment_id_kind"),
        "fiscal_receipts",
        type_="unique",
    )
    op.drop_table("fiscal_receipts")
