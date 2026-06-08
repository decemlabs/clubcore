"""referral_crediting_columns: referral_capture_id FK + partial UNIQUE + widened CHECK.

Phase 97 REFER-04.

Revision ID: 0069_referral_crediting_columns
Revises: 0068_seed_referral_config
Create Date: 2026-06-08

Adds the schema contracts required for referral bonus crediting (Phase 97 REFER-04):

1. loyalty_ledger.referral_capture_id — nullable UUID FK → referral_captures.id (RESTRICT).
   Idempotency anchor for the webhook-locked referral accrual write.
   FK name: fk_loyalty_ledger_referral_capture_id_referral_captures.
   NULL for all entry types except 'referral_accrual'.

2. Partial UNIQUE index uq_loyalty_ledger_referral_accrual on loyalty_ledger
   (referral_capture_id, client_id) WHERE entry_type = 'referral_accrual'.
   LITERAL index name (NOT op.f()) — mirrors uq_loyalty_ledger_welcome (0054) and
   uq_loyalty_ledger_online_payment_id (0055) precedents.
   Compound key allows one accrual row per side (referrer + referee) per capture;
   DB-level replay safety and one-per-referee guard (T-97-03).

3. Widen entry_type CHECK ck_loyalty_ledger_entry_type to include 'referral_accrual'.
   PostgreSQL requires DROP + CREATE (no ALTER CONSTRAINT). Named constraint drop uses
   the full expanded name produced by the NAMING_CONVENTION template (op.f() produced
   'ck_loyalty_ledger_entry_type' in migration 0054).

Constraint naming:
  FK uses full literal name (NAMING_CONVENTION: fk_%(table)s_%(col)s_%(referred)s).
  Partial UNIQUE index uses LITERAL name per 0034/0037/0046/0054/0055 create_index precedent.
  CHECK constraint uses full expanded name 'ck_loyalty_ledger_entry_type' for drop/create.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy import text
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0069_referral_crediting_columns"
down_revision: str | None = "0068_seed_referral_config"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Add nullable referral_capture_id UUID FK column to loyalty_ledger.
    op.add_column(
        "loyalty_ledger",
        sa.Column(
            "referral_capture_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )
    op.create_foreign_key(
        "fk_loyalty_ledger_referral_capture_id_referral_captures",
        "loyalty_ledger",
        "referral_captures",
        ["referral_capture_id"],
        ["id"],
        ondelete="RESTRICT",
    )

    # 2. Partial UNIQUE index — LITERAL name (NOT op.f()) — mirrors uq_loyalty_ledger_welcome.
    # Compound (referral_capture_id, client_id) allows one accrual per side per capture;
    # enforces webhook-replay safety and one-per-referee / no-second-purchase-bonus (T-97-03).
    op.create_index(
        "uq_loyalty_ledger_referral_accrual",
        "loyalty_ledger",
        ["referral_capture_id", "client_id"],
        unique=True,
        postgresql_where=text("entry_type = 'referral_accrual'"),
    )

    # 3. Widen entry_type CHECK to include 'referral_accrual'.
    # Must drop+recreate named constraint (no ALTER CONSTRAINT in Postgres).
    # Use raw op.execute() — op.drop_constraint/create_check_constraint would apply the
    # naming_convention template again, producing a double-prefixed name (D-07 gotcha).
    # Mirror migration 0007_status_taxonomy.py pattern.
    op.execute(
        "ALTER TABLE loyalty_ledger DROP CONSTRAINT ck_loyalty_ledger_entry_type"
    )
    op.execute(
        "ALTER TABLE loyalty_ledger ADD CONSTRAINT ck_loyalty_ledger_entry_type "
        "CHECK (entry_type IN ('welcome', 'owner_grant', 'redemption', 'referral_accrual'))"
    )


def downgrade() -> None:
    # Reverse in inverse order of upgrade.
    # 3. Restore the original 3-literal CHECK (drop new, recreate original).
    # Use raw op.execute() — mirrors the same naming_convention bypass as upgrade().
    op.execute(
        "ALTER TABLE loyalty_ledger DROP CONSTRAINT ck_loyalty_ledger_entry_type"
    )
    op.execute(
        "ALTER TABLE loyalty_ledger ADD CONSTRAINT ck_loyalty_ledger_entry_type "
        "CHECK (entry_type IN ('welcome', 'owner_grant', 'redemption'))"
    )

    # 2. Drop partial UNIQUE index.
    op.drop_index("uq_loyalty_ledger_referral_accrual", table_name="loyalty_ledger")

    # 1. Drop FK constraint, then drop column.
    op.drop_constraint(
        "fk_loyalty_ledger_referral_capture_id_referral_captures",
        "loyalty_ledger",
        type_="foreignkey",
    )
    op.drop_column("loyalty_ledger", "referral_capture_id")
