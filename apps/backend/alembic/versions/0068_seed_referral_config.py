"""Seed referral_config singleton baseline (Phase 96 REFER-07).

Revision ID: 0068_seed_referral_config
Revises: 0067_referral_tables
Create Date: 2026-06-08

Data-only migration: seeds the single referral_config row with the default
bonus amounts so fresh environments are functional with zero manual intervention.

Idempotency:
- INSERT ... ON CONFLICT (id) DO NOTHING — id is the PK.
- Re-running upgrade() is a verified no-op (T-96-02 mitigate).
- Conflict target is (id) because the singleton has a deterministic UUID PK.

Seed values:
  referrer_bonus_kopecks  = 50000  (500 ₽ for the client who shared the code)
  referee_welcome_kopecks = 30000  (300 ₽ welcome bonus for the new client)

Downgrade hard-deletes the row (no FK references to referral_config).

asyncpg driver sends all bind params as VARCHAR; explicit CAST(:id AS uuid) is
required (mirrors 0059_seed_gym_info pattern).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0068_seed_referral_config"
down_revision: str | None = "0067_referral_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Deterministic singleton PK — consistent across all environments.
# gym_info used ...001; referral_config uses ...002.
_SINGLETON_ID = "00000000-0000-0000-0000-000000000002"

# Default bonus amounts (kopecks = integer minor units, 1 kopeck = 0.01 ₽)
_REFERRER_BONUS_KOPECKS = 50_000  # 500 ₽ for the referrer
_REFEREE_WELCOME_KOPECKS = 30_000  # 300 ₽ welcome bonus for the new client


def upgrade() -> None:
    # Use CAST(:id AS uuid) syntax — asyncpg sends all bind params as VARCHAR;
    # explicit CAST is required for uuid columns (mirrors 0059_seed_gym_info).
    op.execute(
        sa.text(
            "INSERT INTO referral_config "
            "(id, referrer_bonus_kopecks, referee_welcome_kopecks) "
            "VALUES (CAST(:id AS uuid), :rb, :rw) "
            "ON CONFLICT (id) DO NOTHING"
        ).bindparams(
            id=_SINGLETON_ID,
            rb=_REFERRER_BONUS_KOPECKS,
            rw=_REFEREE_WELCOME_KOPECKS,
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text("DELETE FROM referral_config WHERE id = CAST(:id AS uuid)").bindparams(
            id=_SINGLETON_ID
        )
    )
