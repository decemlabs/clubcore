"""clients: goal enum, height_cm, weight_kg, onboarding_completed_at (Phase 999.5 D-06/D-07/D-08).

Revision ID: 0048_client_onboarding_fields
Revises: 0047_online_payments_promo_code_id
Create Date: 2026-05-31 00:00:00.000000

Additive migration — four nullable columns + CHECK constraint on goal.
All columns nullable, no backfill, no table rewrite (D-08).
ADD COLUMN is metadata-only on Postgres 16 — negligible lock window (T-999.5-02 accepted).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0048_client_onboarding_fields"
down_revision: str | None = "0047_online_payments_promo_code_id"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("clients", sa.Column("goal", sa.String(16), nullable=True))
    op.add_column("clients", sa.Column("height_cm", sa.SmallInteger(), nullable=True))
    op.add_column("clients", sa.Column("weight_kg", sa.SmallInteger(), nullable=True))
    op.add_column(
        "clients",
        sa.Column("onboarding_completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    # D-07: DB-level CHECK restricts goal to the 4 enum values (T-999.5-01 mitigated).
    op.create_check_constraint(
        op.f("ck_clients_goal"),
        "clients",
        "goal IN ('lose_weight', 'gain_mass', 'tone', 'maintain')",
    )


def downgrade() -> None:
    # Drop constraint before column (Postgres requirement for CHECK referencing column).
    op.drop_constraint(op.f("ck_clients_goal"), "clients", type_="check")
    op.drop_column("clients", "onboarding_completed_at")
    op.drop_column("clients", "weight_kg")
    op.drop_column("clients", "height_cm")
    op.drop_column("clients", "goal")
