"""Create gym_info singleton table (Phase 86 GYM-01).

Revision ID: 0058_gym_info
Revises: 0057_payment_notifications_widen_kind
Create Date: 2026-06-06

DDL-only migration: creates the gym_info table that holds the single gym-info
singleton row. The seed data is in the next migration (0059_seed_gym_info).

Columns:
- id: UUID PK (server default gen_random_uuid())
- name: Text NOT NULL — gym display name
- address: Text NOT NULL — physical address
- tagline/city/metro/phone/email: Text NULL — optional info fields
- hours/amenities/rules/social: JSONB NOT NULL DEFAULT '[]'::jsonb — list content
- created_at/updated_at: timestamptz NOT NULL DEFAULT now() — TimestampMixin mirrors
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0058_gym_info"
down_revision: str | None = "0057_payment_notifications_widen_kind"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "gym_info",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("address", sa.Text(), nullable=False),
        sa.Column("tagline", sa.Text(), nullable=True),
        sa.Column("city", sa.Text(), nullable=True),
        sa.Column("metro", sa.Text(), nullable=True),
        sa.Column("phone", sa.Text(), nullable=True),
        sa.Column("email", sa.Text(), nullable=True),
        sa.Column(
            "hours",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "amenities",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "rules",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "social",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
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
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("gym_info")
