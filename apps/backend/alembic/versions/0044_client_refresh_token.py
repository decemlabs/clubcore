"""Create client_refresh_tokens table (Phase 68 D-09).

Revision ID: 0044_client_refresh_token
Revises: 0043_client_auth_otp
Create Date: 2026-05-29 00:00:00.000000

New table, fully parallel to refresh_tokens — FK target is clients.id.
Redis namespace: auth:client:session:{client_id}:{family_id} (D-09).
Staff and client refresh storage never intersect (CISO-05 isolation).

Security:
  T-68-03 — token_hash UNIQUE prevents two families sharing a token hash.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0044_client_refresh_token"
down_revision: str | None = "0043_client_auth_otp"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "client_refresh_tokens",
        sa.Column("client_id", sa.UUID(), nullable=False),
        sa.Column("family_id", sa.UUID(), nullable=False),
        sa.Column("token_hash", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("replaced_by_id", sa.UUID(), nullable=True),
        sa.Column("replaced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["client_id"],
            ["clients.id"],
            name=op.f("fk_client_refresh_tokens_client_id_clients"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["replaced_by_id"],
            ["client_refresh_tokens.id"],
            name=op.f("fk_client_refresh_tokens_replaced_by_id_client_refresh_tokens"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_client_refresh_tokens")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_client_refresh_tokens_token_hash")),
    )
    op.create_index(
        "ix_client_refresh_tokens_client_id_family_id",
        "client_refresh_tokens",
        ["client_id", "family_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_client_refresh_tokens_client_id_family_id",
        table_name="client_refresh_tokens",
    )
    op.drop_table("client_refresh_tokens")
