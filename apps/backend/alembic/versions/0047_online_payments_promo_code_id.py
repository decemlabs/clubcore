"""online_payments.promo_code_id nullable FK column (Phase 999.4 D-06/D-07).

Revision ID: 0047_online_payments_promo_code_id
Revises: 0046_promo_codes
Create Date: 2026-05-31 00:00:00.000000

Adds a nullable ``promo_code_id`` UUID column to ``online_payments`` so the
succeeded-webhook handler can read which promo code was applied at checkout and
record a ``promo_redemptions`` row (D-07).

Nullable — a payment without a promo leaves the column NULL. The FK uses
``ondelete=RESTRICT`` so promo codes cannot be hard-deleted while referencing
payments exist (soft-delete via ``deleted_at`` on promo_codes is the expected
lifecycle path).

Constraint naming follows NAMING_CONVENTION fk pattern:
  fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s
  → fk_online_payments_promo_code_id_promo_codes
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0047_online_payments_promo_code_id"
down_revision: str | None = "0046_promo_codes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "online_payments",
        sa.Column(
            "promo_code_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )
    op.create_foreign_key(
        op.f("fk_online_payments_promo_code_id_promo_codes"),
        "online_payments",
        "promo_codes",
        ["promo_code_id"],
        ["id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("fk_online_payments_promo_code_id_promo_codes"),
        "online_payments",
        type_="foreignkey",
    )
    op.drop_column("online_payments", "promo_code_id")
