"""Create message_threads table (Phase 90 MSG-01).

Revision ID: 0064_messaging_threads
Revises: 0063_seed_trainer_profiles
Create Date: 2026-06-07

DDL: message_threads table — one per client (1:1 enforced by UNIQUE(client_id)).
Columns mirror TimestampMixin (created_at/updated_at now() server_default)
+ UUIDPkMixin (id gen_random_uuid()).
UNIQUE(client_id) — one thread per client; ON CONFLICT target for get-or-create insert.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0064_messaging_threads"
down_revision: str | None = "0063_seed_trainer_profiles"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "message_threads",
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
        sa.Column(
            "last_message_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "client_unread_count",
            sa.Integer(),
            server_default=sa.text("0"),
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
            ondelete="RESTRICT",
            name="fk_message_threads_client_id_clients",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "client_id",
            name="uq_message_threads_client_id",
        ),
    )


def downgrade() -> None:
    op.drop_table("message_threads")
