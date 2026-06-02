"""Seed FIT15 product promo code (Phase 75 Plan 02 — PROMO-01).

Revision ID: 0051_seed_fit15_promo
Revises: 0050_clients_notif_prefs
Create Date: 2026-06-02 00:00:00.000000

Data-only migration: seeds the FIT15 recommended-promo product code so the PWA
promo chip can validate it through the existing POST /client/promo/validate endpoint.

Design notes (D-07 / D-08 / D-09):
- D-07: FIT15 is a PRODUCT CODE (not demo data) — it lands on any clean DB
  including production. Contrast with FIT10/FIRST500 which live only in
  scripts/seed_demo_data.py (demo-data-only discipline).
- D-08: applicable_to=NULL means both membership and pt_package are eligible.
- D-09: FIT15 parameters — percentage type, discount_value=1500 (15% encoded as
  percent*100 = 1500), per_client_limit=1 (caps per-account abuse), max_uses=NULL
  (globally uncapped — recommended product code), valid_from/valid_until=NULL
  (no expiry window; a hardcoded date would silently expire), is_active=True.

Idempotency:
- INSERT ... ON CONFLICT DO NOTHING on the partial-unique index
  uq_promo_codes_code_alive (upper(code) WHERE deleted_at IS NULL).
- Re-running upgrade() is a verified no-op (T-75-05 mitigation).
- The explicit conflict target form is used to bind the partial index unambiguously:
  ON CONFLICT (upper(code)) WHERE deleted_at IS NULL DO NOTHING.

Downgrade soft-deletes rather than hard-deletes to preserve referential integrity
if any promo_redemptions rows reference the FIT15 row (RESTRICT FK).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0051_seed_fit15_promo"
down_revision: str | None = "0050_clients_notif_prefs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Insert FIT15 product code — idempotent via partial-unique index
    # uq_promo_codes_code_alive: upper(code) WHERE deleted_at IS NULL.
    # id and created_at/updated_at have server defaults (gen_random_uuid(), now()).
    op.execute(
        sa.text(
            "INSERT INTO promo_codes "
            "(code, discount_type, discount_value, per_client_limit, max_uses, "
            " valid_from, valid_until, is_active, applicable_to) "
            "VALUES ('FIT15', 'percentage', 1500, 1, NULL, NULL, NULL, TRUE, NULL) "
            "ON CONFLICT (upper(code)) WHERE deleted_at IS NULL DO NOTHING"
        )
    )


def downgrade() -> None:
    # Soft-delete rather than hard-delete to preserve referential integrity:
    # promo_redemptions.promo_code_id has RESTRICT FK → promo_codes.id.
    # Soft-deleting keeps the FK intact while making the code invisible to the
    # validate endpoint (which filters WHERE deleted_at IS NULL).
    op.execute(
        sa.text(
            "UPDATE promo_codes "
            "SET deleted_at = now() "
            "WHERE upper(code) = 'FIT15' AND deleted_at IS NULL"
        )
    )
