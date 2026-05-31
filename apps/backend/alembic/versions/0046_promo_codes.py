"""promo_codes + promo_redemptions tables (Phase 999.4 D-04/D-07/D-08).

Revision ID: 0046_promo_codes
Revises: 0045_visits_channel_client_qr
Create Date: 2026-05-31 00:00:00.000000

Ships two tables:
- promo_codes: definition table with discount_type/value, usage caps,
  validity window, is_active, applicable_to; partial UNIQUE on upper(code)
  WHERE deleted_at IS NULL (uq_promo_codes_code_alive).
- promo_redemptions: append-only ledger keyed per online_payment;
  UNIQUE(online_payment_id) enforces one-redemption-per-payment (D-07).

Partial UNIQUE index name (uq_promo_codes_code_alive) is a LITERAL string —
NOT wrapped in op.f() — per 0034/0037 create_index precedent.
All FK and PK constraint names pass through op.f() (already-expanded names).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy import func, text
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0046_promo_codes"
down_revision: str | None = "0045_visits_channel_client_qr"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- promo_codes ---
    op.create_table(
        "promo_codes",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("discount_type", sa.String(16), nullable=False),
        sa.Column("discount_value", sa.BigInteger(), nullable=False),
        sa.Column("max_uses", sa.Integer(), nullable=True),
        sa.Column("per_client_limit", sa.Integer(), nullable=True),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column("applicable_to", sa.String(16), nullable=True),
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
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_promo_codes")),
        sa.CheckConstraint(
            "discount_type IN ('percentage', 'fixed')",
            name=op.f("ck_promo_codes_discount_type"),
        ),
        sa.CheckConstraint(
            "discount_value > 0",
            name=op.f("ck_promo_codes_discount_value_positive"),
        ),
    )
    # Partial UNIQUE: upper(code) WHERE deleted_at IS NULL
    # Literal index name (NOT via op.f()) — per 0034/0037 create_index precedent
    op.create_index(
        "uq_promo_codes_code_alive",
        "promo_codes",
        [text("upper(code)")],
        unique=True,
        postgresql_where=text("deleted_at IS NULL"),
    )

    # --- promo_redemptions ---
    op.create_table(
        "promo_redemptions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("promo_code_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("online_payment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("discount_kopecks", sa.BigInteger(), nullable=False),
        sa.Column(
            "redeemed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=func.now(),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_promo_redemptions")),
        sa.ForeignKeyConstraint(
            ["promo_code_id"],
            ["promo_codes.id"],
            name=op.f("fk_promo_redemptions_promo_code_id_promo_codes"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["client_id"],
            ["clients.id"],
            name=op.f("fk_promo_redemptions_client_id_clients"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["online_payment_id"],
            ["online_payments.id"],
            name=op.f("fk_promo_redemptions_online_payment_id_online_payments"),
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "discount_kopecks > 0",
            name=op.f("ck_promo_redemptions_discount_kopecks_positive"),
        ),
        sa.UniqueConstraint(
            "online_payment_id",
            name=op.f("uq_promo_redemptions_online_payment_id"),
        ),
    )


def downgrade() -> None:
    op.drop_index("uq_promo_codes_code_alive", table_name="promo_codes")
    op.drop_table("promo_redemptions")
    op.drop_table("promo_codes")
