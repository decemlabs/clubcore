"""Create in_app_notifications table (Phase 87 INBOX-01).

Revision ID: 0060_in_app_notifications
Revises: 0059_seed_gym_info
Create Date: 2026-06-06

DDL: in_app_notifications table for client inbox rows.
Columns mirror TimestampMixin (created_at/updated_at now() server_default)
+ UUIDPkMixin (id gen_random_uuid()).
UNIQUE(client_id, source_type, source_id, kind) — idempotent dedup guard (T-87-03).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0060_in_app_notifications"
down_revision: str | None = "0059_seed_gym_info"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_VALID_KINDS = (
    "booking_confirmed",
    "booking_cancelled_by_client",
    "booking_cancelled_by_owner",
    "booking_rescheduled",
    "payment_succeeded",
    "autopay_charge_succeeded",
    "autopay_charge_failed",
)
_KIND_CHECK = "kind IN (" + ", ".join(f"'{k}'" for k in _VALID_KINDS) + ")"


def upgrade() -> None:
    op.create_table(
        "in_app_notifications",
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
        sa.Column("source_type", sa.Text(), nullable=False),
        sa.Column(
            "source_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
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
            _KIND_CHECK,
            name="ck_in_app_notifications_kind",
        ),
        sa.ForeignKeyConstraint(
            ["client_id"],
            ["clients.id"],
            ondelete="RESTRICT",
            name="fk_in_app_notifications_client_id_clients",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "client_id",
            "source_type",
            "source_id",
            "kind",
            name="uq_in_app_notifications_client_source_kind",
        ),
    )
    op.create_index(
        "ix_in_app_notifications_client_id",
        "in_app_notifications",
        ["client_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_in_app_notifications_client_id", table_name="in_app_notifications")
    op.drop_table("in_app_notifications")
