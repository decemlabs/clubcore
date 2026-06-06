"""Create client_push_tokens table (Phase 87 INBOX-02).

Revision ID: 0061_client_push_tokens
Revises: 0060_in_app_notifications
Create Date: 2026-06-06

DDL: client_push_tokens table for device/browser push-token registration.
Partial UNIQUE on (token) WHERE unregistered_at IS NULL enforces a global
one-alive-row-per-device-token guarantee — a physical device token is globally
unique so two clients must never hold alive rows for the same token
(privacy leak: dispatch fanout would reach the wrong client).
platform CheckConstraint restricts to web/android/ios (T-87-04).

CR-03 fix (in-place amendment — migration not yet deployed, single-dev project):
  Changed index from (client_id, token) to (token) alone so that registering
  an existing-alive token for a different client first unregisters/reassigns it.
  Repository.upsert_push_token keys the UPDATE on token (not client_id+token)
  to match this global uniqueness guarantee.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0061_client_push_tokens"
down_revision: str | None = "0060_in_app_notifications"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "client_push_tokens",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "client_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("token", sa.Text(), nullable=False),
        sa.Column("platform", sa.Text(), nullable=False),
        sa.Column(
            "unregistered_at",
            sa.DateTime(timezone=True),
            nullable=True,
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
        sa.CheckConstraint(
            "platform IN ('web', 'android', 'ios')",
            name="ck_client_push_tokens_platform",
        ),
        sa.ForeignKeyConstraint(
            ["client_id"],
            ["clients.id"],
            ondelete="RESTRICT",
            name="fk_client_push_tokens_client_id_clients",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    # Partial UNIQUE on (token) alone — device tokens are globally unique; enforcing
    # uniqueness per (client_id, token) would allow two clients to hold alive rows
    # for the same physical device token (privacy-leak fanout risk, CR-03).
    # Must use op.create_index (partial indexes are not expressible as
    # sa.UniqueConstraint inside create_table; mirrors migration 0052 pattern).
    op.create_index(
        "uq_client_push_tokens_token_alive",
        "client_push_tokens",
        ["token"],
        unique=True,
        postgresql_where=sa.text("unregistered_at IS NULL"),
    )
    op.create_index("ix_client_push_tokens_client_id", "client_push_tokens", ["client_id"])


def downgrade() -> None:
    op.drop_index("ix_client_push_tokens_client_id", table_name="client_push_tokens")
    op.drop_index(
        "uq_client_push_tokens_token_alive",
        table_name="client_push_tokens",
    )
    op.drop_table("client_push_tokens")
