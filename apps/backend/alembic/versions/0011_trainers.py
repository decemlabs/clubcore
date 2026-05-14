"""trainers

Revision ID: 0011_trainers
Revises: 0010_notifications
Create Date: 2026-05-14 00:00:00.000000

Phase 31 TRN-01 — trainers table.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy import text

from alembic import op

revision: str = "0011_trainers"
down_revision: str | None = "0010_notifications"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "trainers",
        sa.Column("full_name", sa.Text(), nullable=False),
        sa.Column("phone", sa.Text(), nullable=True),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
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
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_trainers")),
    )
    # D-31-03: partial unique on phone WHERE deleted_at IS NULL AND phone IS NOT NULL
    op.create_index(
        "uq_trainers_phone_alive",
        "trainers",
        ["phone"],
        unique=True,
        postgresql_where=text("deleted_at IS NULL AND phone IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_trainers_phone_alive", table_name="trainers")
    op.drop_table("trainers")
