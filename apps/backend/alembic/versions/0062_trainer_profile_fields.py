"""trainers: bio, specialization, photo_url columns (Phase 88 TRNR-01).

Revision ID: 0062_trainer_profile_fields
Revises: 0061_client_push_tokens
Create Date: 2026-06-06

Additive migration — three nullable Text columns.
All nullable, no backfill (separate data migration 0063).
ADD COLUMN is metadata-only on Postgres 16 — negligible lock window.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0062_trainer_profile_fields"
down_revision: str | None = "0061_client_push_tokens"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("trainers", sa.Column("bio", sa.Text(), nullable=True))
    op.add_column("trainers", sa.Column("specialization", sa.Text(), nullable=True))
    op.add_column("trainers", sa.Column("photo_url", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("trainers", "photo_url")
    op.drop_column("trainers", "specialization")
    op.drop_column("trainers", "bio")
