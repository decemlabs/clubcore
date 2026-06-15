"""promo_codes: add nullable description column (Phase 113).

Revision ID: 0072_promo_codes_description
Revises: 0071_seed_settings
Create Date: 2026-06-15

Additive migration — one nullable String(500) column on the promo_codes table.
ADD COLUMN is metadata-only on Postgres 16 — negligible lock window.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0072_promo_codes_description"
down_revision: str | None = "0071_seed_settings"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "promo_codes",
        sa.Column("description", sa.String(500), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("promo_codes", "description")
