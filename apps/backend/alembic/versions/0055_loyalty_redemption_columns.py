"""loyalty_redemption_columns: redemption FK + idempotency index (Phase 83 REDM-01/REDM-02).

Revision ID: 0055_loyalty_redemption_columns
Revises: 0054_loyalty_ledger
Create Date: 2026-06-05 00:00:00.000000

Adds the schema contracts required for bonus redemption at checkout (Phase 83):

1. loyalty_ledger.online_payment_id — nullable UUID FK → online_payments.id (RESTRICT).
   Idempotency anchor for the webhook-locked redemption write (REDM-02).
   FK name: fk_loyalty_ledger_online_payment_id_online_payments.

2. Partial UNIQUE index uq_loyalty_ledger_online_payment_id on loyalty_ledger
   (online_payment_id) WHERE entry_type = 'redemption'.
   LITERAL index name (NOT op.f()) — mirrors uq_loyalty_ledger_welcome (0054)
   and uq_promo_redemptions_online_payment_id precedents.
   One redemption row per online_payment; DB-level double-spend guard (T-83-01).

3. online_payments.loyalty_redeem_kopecks — nullable BigInteger; server-computed
   redeem amount stored at checkout; NULL = no bonus applied (REDM-01).
   Server-written only; never client-writable (T-83-03).

Constraint naming:
  FK uses full literal name (NAMING_CONVENTION: fk_%(table)s_%(col)s_%(referred)s).
  Partial UNIQUE index uses LITERAL name per 0034/0037/0046/0054 create_index precedent.
  Plain PK/CK names go through op.f() (existing table — no new ones here).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy import text
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0055_loyalty_redemption_columns"
down_revision: str | None = "0054_loyalty_ledger"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Add nullable online_payment_id UUID FK column to loyalty_ledger
    op.add_column(
        "loyalty_ledger",
        sa.Column(
            "online_payment_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )
    op.create_foreign_key(
        "fk_loyalty_ledger_online_payment_id_online_payments",
        "loyalty_ledger",
        "online_payments",
        ["online_payment_id"],
        ["id"],
        ondelete="RESTRICT",
    )

    # 2. Partial UNIQUE index — literal name (NOT op.f()) — mirrors uq_loyalty_ledger_welcome.
    # One redemption row per online_payment_id; DB-level double-spend / replay guard (T-83-01).
    op.create_index(
        "uq_loyalty_ledger_online_payment_id",
        "loyalty_ledger",
        ["online_payment_id"],
        unique=True,
        postgresql_where=text("entry_type = 'redemption'"),
    )

    # 3. Add nullable loyalty_redeem_kopecks BigInteger to online_payments.
    # Server-computed at checkout; NULL = no bonus applied (REDM-01 / T-83-03).
    op.add_column(
        "online_payments",
        sa.Column(
            "loyalty_redeem_kopecks",
            sa.BigInteger(),
            nullable=True,
        ),
    )


def downgrade() -> None:
    # Reverse in inverse order of upgrade.
    op.drop_column("online_payments", "loyalty_redeem_kopecks")
    op.drop_index("uq_loyalty_ledger_online_payment_id", table_name="loyalty_ledger")
    op.drop_constraint(
        "fk_loyalty_ledger_online_payment_id_online_payments",
        "loyalty_ledger",
        type_="foreignkey",
    )
    op.drop_column("loyalty_ledger", "online_payment_id")
