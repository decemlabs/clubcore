"""loyalty_ledger append-only table (Phase 82 LOYL-03).

Revision ID: 0054_loyalty_ledger
Revises: 0053_booking_notif_widen_kind_rescheduled
Create Date: 2026-06-05 00:00:00.000000

Adds the append-only `loyalty_ledger` table:
- client_id RESTRICT FK → clients.id (one client many rows)
- entry_type CHECK IN ('welcome', 'owner_grant', 'redemption')
- amount_kopecks BigInteger SIGNED (positive=accrual, negative=redemption)
- category String(16) nullable (owner_grant rows only)
- reason String(255) nullable (owner_grant rows only)
- created_at TIMESTAMPTZ server_default=now()

Indexes:
- uq_loyalty_ledger_welcome: UNIQUE (client_id) WHERE entry_type='welcome'
  Literal index name (NOT via op.f()) — partial UNIQUE per 0034/0037/0046
  create_index precedent. Idempotency for welcome accrual (ACCR-01).
- ix_loyalty_ledger_client_id: plain index on client_id for balance/history fold.

All FK + PK constraint names pass through op.f() (already-expanded names).
CheckConstraint name=op.f() to produce ck_loyalty_ledger_entry_type.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy import func, text
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0054_loyalty_ledger"
down_revision: str | None = "0053_booking_notif_widen_kind_rescheduled"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "loyalty_ledger",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entry_type", sa.String(16), nullable=False),
        sa.Column("amount_kopecks", sa.BigInteger(), nullable=False),
        sa.Column("category", sa.String(16), nullable=True),
        sa.Column("reason", sa.String(255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=func.now(),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_loyalty_ledger")),
        sa.ForeignKeyConstraint(
            ["client_id"],
            ["clients.id"],
            name=op.f("fk_loyalty_ledger_client_id_clients"),
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "entry_type IN ('welcome', 'owner_grant', 'redemption')",
            name=op.f("ck_loyalty_ledger_entry_type"),
        ),
    )
    # Partial UNIQUE: one welcome row per client — LITERAL index name (NOT via op.f())
    # per 0034/0037/0046 create_index precedent. Idempotency for ACCR-01.
    op.create_index(
        "uq_loyalty_ledger_welcome",
        "loyalty_ledger",
        ["client_id"],
        unique=True,
        postgresql_where=text("entry_type = 'welcome'"),
    )
    # Plain index on client_id for balance/history fold performance (LOYL-03)
    op.create_index(
        op.f("ix_loyalty_ledger_client_id"),
        "loyalty_ledger",
        ["client_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("uq_loyalty_ledger_welcome", table_name="loyalty_ledger")
    op.drop_index(op.f("ix_loyalty_ledger_client_id"), table_name="loyalty_ledger")
    op.drop_table("loyalty_ledger")
