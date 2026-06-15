"""Add message_threads.staff_last_read_at for staff-side unread watermark (Phase 116 MSG-01).

Revision ID: 0073
Revises: 0072
Create Date: 2026-06-15

Additive migration: nullable TIMESTAMPTZ column on message_threads.
NULL = never read by staff (correct initial state — all client messages are unread
for staff until the inbox is opened). No backfill needed; the staff-side unread count
is derived on read: COUNT(*) WHERE role='client' AND sent_at > staff_last_read_at
(or all client messages when staff_last_read_at IS NULL).

D-54-08 / Additive Migration Decision (116-PATTERNS): additive column only, no DROP
or ALTER of existing columns; downgrade removes the column cleanly.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0073_message_thread_staff_last_read_at"
down_revision = "0072_promo_codes_description"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "message_threads",
        sa.Column("staff_last_read_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("message_threads", "staff_last_read_at")
