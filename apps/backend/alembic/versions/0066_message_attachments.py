"""Create message_attachments table + messages.attachment_id (Phase 92 ATT-01..03).

Revision ID: 0066_message_attachments
Revises: 0065_messaging_messages
Create Date: 2026-06-07

DDL:
- message_attachments table: IDOR ownership via client_id NOT NULL (T-92-03 mitigate).
  thread_id FK to message_threads, client_id FK to clients; both RESTRICT.
  mime_type TEXT NOT NULL (validated server-side by magic-byte guard).
  object_key TEXT NOT NULL (server-generated UUID4-based path, P8 — no user filename).
  size_bytes INTEGER NOT NULL.
  created_at TIMESTAMPTZ server_default now() NOT NULL.

- messages.attachment_id: nullable UUID FK to message_attachments.id (RESTRICT).
  Added as nullable so existing message rows are unaffected.
  body stays NOT NULL; body OR attachment required is enforced at the service layer.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0066_message_attachments"
down_revision: str | None = "0065_messaging_messages"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # -------------------------------------------------------------------------
    # message_attachments: new table
    # -------------------------------------------------------------------------
    op.create_table(
        "message_attachments",
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
        sa.Column(
            "client_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("mime_type", sa.Text(), nullable=False),
        sa.Column("object_key", sa.Text(), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
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
            ["thread_id"],
            ["message_threads.id"],
            ondelete="RESTRICT",
            name="fk_message_attachments_thread_id_message_threads",
        ),
        sa.ForeignKeyConstraint(
            ["client_id"],
            ["clients.id"],
            ondelete="RESTRICT",
            name="fk_message_attachments_client_id_clients",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # -------------------------------------------------------------------------
    # messages.attachment_id: nullable FK column
    # -------------------------------------------------------------------------
    op.add_column(
        "messages",
        sa.Column(
            "attachment_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )
    op.create_foreign_key(
        "fk_messages_attachment_id_message_attachments",
        "messages",
        "message_attachments",
        ["attachment_id"],
        ["id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    # Drop messages.attachment_id FK + column first (child → parent order)
    op.drop_constraint(
        "fk_messages_attachment_id_message_attachments",
        "messages",
        type_="foreignkey",
    )
    op.drop_column("messages", "attachment_id")

    # Drop message_attachments table
    op.drop_table("message_attachments")
