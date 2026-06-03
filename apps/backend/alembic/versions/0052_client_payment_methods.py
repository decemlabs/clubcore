"""client_payment_methods table + save_payment_method column on online_payments (Phase 79).

Revision ID: 0052_client_payment_methods
Revises: 0051_seed_fit15_promo
Create Date: 2026-06-03 00:00:00.000000

Ships two DDL changes:
- client_payment_methods: new table with partial UNIQUE on client_id WHERE unlinked_at IS NULL
  (single active card per client, uq_client_payment_methods_client_id_alive).
- online_payments: adds save_payment_method boolean column (intent flag read by webhook step 8.5).

Partial UNIQUE index name (uq_client_payment_methods_client_id_alive) is a LITERAL string —
NOT wrapped in op.f() — per 0034/0037/0046 create_index precedent.
All FK and PK constraint names pass through op.f() (already-expanded names).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy import func, text
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0052_client_payment_methods"
down_revision: str | None = "0051_seed_fit15_promo"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- client_payment_methods ---
    op.create_table(
        "client_payment_methods",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("yookassa_method_id", sa.Text(), nullable=False),  # plaintext token
        sa.Column("last4", sa.Text(), nullable=False),
        sa.Column("brand", sa.Text(), nullable=False),
        sa.Column("expiry_month", sa.Integer(), nullable=True),
        sa.Column("expiry_year", sa.Integer(), nullable=True),
        sa.Column("autopay_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("consent_recorded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("unlinked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=func.now(),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_client_payment_methods")),
        sa.ForeignKeyConstraint(
            ["client_id"],
            ["clients.id"],
            name=op.f("fk_client_payment_methods_client_id_clients"),
            ondelete="RESTRICT",
        ),
    )
    # Partial UNIQUE: single active card per client (literal name, NOT via op.f())
    op.create_index(
        "uq_client_payment_methods_client_id_alive",
        "client_payment_methods",
        ["client_id"],
        unique=True,
        postgresql_where=text("unlinked_at IS NULL"),
    )

    # --- online_payments: add save_payment_method intent column ---
    # ADD COLUMN is metadata-only on Postgres 16 — negligible lock window.
    op.add_column(
        "online_payments",
        sa.Column(
            "save_payment_method",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    op.drop_column("online_payments", "save_payment_method")
    op.drop_index("uq_client_payment_methods_client_id_alive", table_name="client_payment_methods")
    op.drop_table("client_payment_methods")
