"""Create messages table (Phase 90 MSG-01).

Revision ID: 0065_messaging_messages
Revises: 0064_messaging_threads
Create Date: 2026-06-07

DDL: messages table — per-message rows under a thread.
role TEXT + CheckConstraint restricts to 'client'|'staff' (T-90-01 mitigate).
Index (thread_id, sent_at DESC) for efficient per-thread history pagination.
No attachment_id column — deferred to Phase 92 migration 0066 (ATT-01..03).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0065_messaging_messages"
down_revision: str | None = "0064_messaging_threads"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "messages",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "thread_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column(
            "sent_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "read_at",
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
            "role IN ('client','staff')",
            name="ck_messages_role",
        ),
        sa.ForeignKeyConstraint(
            ["thread_id"],
            ["message_threads.id"],
            ondelete="RESTRICT",
            name="fk_messages_thread_id_message_threads",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_messages_thread_sent",
        "messages",
        [sa.text("thread_id"), sa.text("sent_at DESC")],
    )


def downgrade() -> None:
    op.drop_index("ix_messages_thread_sent", table_name="messages")
    op.drop_table("messages")
