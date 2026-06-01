"""fiscal_receipts: customer_phone + nullable customer_email + email-OR-phone CHECK.

Revision ID: 0049_fiscal_receipts_customer_phone
Revises: 0048_client_onboarding_fields
Create Date: 2026-06-01 00:00:00.000000

Phase 999.5 Plan 07 (gap-closure, Issue 2 / UAT test 12, PAY-03 / FISCAL-05).

Makes the fiscalization storage layer phone-aware so a «Чек не нужен»
phone-only payment (email NULL per D-10) can be persisted and fiscalized,
mirroring what Plan 03 did for create_payment.

Additive-then-restrictive, no backfill needed:
- ADD COLUMN customer_phone (nullable) — metadata-only on Postgres 16.
- ALTER customer_email → nullable=True (relaxing NOT NULL, never rewrites rows).
- ADD CHECK ck_fiscal_receipts_contact_present enforcing at least one of
  (customer_email, customer_phone) is non-NULL (T-999.5-G2-01 mitigation).

Downgrade safety: every existing fiscal_receipts row carries a non-null
customer_email today (the column shipped NOT NULL in 0035), so restoring the
NOT NULL on downgrade is safe for current data — no phone-only rows exist
until Plan 08 wires the webhook handler to persist them.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0049_fiscal_receipts_customer_phone"
down_revision: str | None = "0048_client_onboarding_fields"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "fiscal_receipts",
        sa.Column("customer_phone", sa.Text(), nullable=True),
    )
    op.alter_column(
        "fiscal_receipts",
        "customer_email",
        existing_type=sa.Text(),
        nullable=True,
    )
    # T-999.5-G2-01: a fiscal receipt must always carry a 54-ФЗ-deliverable
    # contact — at least one of email / phone present.
    op.create_check_constraint(
        op.f("ck_fiscal_receipts_contact_present"),
        "fiscal_receipts",
        "customer_email IS NOT NULL OR customer_phone IS NOT NULL",
    )


def downgrade() -> None:
    # Reverse order: drop CHECK before restoring NOT NULL / dropping column.
    op.drop_constraint(
        op.f("ck_fiscal_receipts_contact_present"),
        "fiscal_receipts",
        type_="check",
    )
    op.alter_column(
        "fiscal_receipts",
        "customer_email",
        existing_type=sa.Text(),
        nullable=False,
    )
    op.drop_column("fiscal_receipts", "customer_phone")
