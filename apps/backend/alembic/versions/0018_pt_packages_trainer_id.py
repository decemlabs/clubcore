"""pt_packages.trainer_id nullable FK column (Phase 38 PKG-01 / C-08).

Revision ID: 0018_pt_packages_trainer_id
Revises: 0017_bookings
Create Date: 2026-05-17 18:00:00.000000

# down_revision: "0017_bookings" — Wave-3 plan depending on 38-02's bookings
# table for chain order; refund-guard tests in Task 3 also seed rows into
# bookings via raw SQL (the production cross-module guard in
# pt_packages/service.refund_pt_package issues `SELECT count(*) FROM
# bookings WHERE pt_package_id=:pkg AND status='confirmed'` per D-38-11).

Notes:
- ADD COLUMN nullable=True — existing pt_packages rows have no trainer
  association (the optional trainer constraint is a v1.5 addition); backfill
  is NULL, not a value. Future rows MAY set it via POST /pt-packages.
- FK fk_pt_packages_trainer_id_trainers ON DELETE RESTRICT — trainers are
  soft-deleted via `is_active=false` (Phase 31 TRN-04), never hard-deleted,
  so RESTRICT is the safer floor than SET NULL. If a DBA ever hard-deletes
  a trainer row (out-of-band surgery), the FK blocks the delete — preserving
  the pt_package's audit trail integrity.
- Index ix_pt_packages_trainer_id — non-partial btree for forensic lookup
  `WHERE trainer_id = :id` and join-back from trainer cancellation flows
  (no autogenerate-suppression needed in alembic/env.py — full btree).
- Three-step upgrade (ADD COLUMN → create_foreign_key → create_index) mirrors
  0009_renewal.py:44-72 with the trainer_id rename + RESTRICT.
- Downgrade is lossless reverse: drop_index → drop_constraint(type_=foreignkey)
  → drop_column. Data loss occurs ONLY if non-NULL values exist; v1.5
  initial deployment has them all NULL.

Constraint name fk_pt_packages_trainer_id_trainers is NOT literal-ref'd by
service code (no IntegrityError discriminator translates this FK — invalid
trainer_id is caught at app layer via resolve_trainer_by_id Protocol slot
returning None → 404 trainer_not_found, never reaching the DB). Therefore
NO entry is added to alembic/env.py:_include_object.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0018_pt_packages_trainer_id"
down_revision: str | None = "0017_bookings"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1) Add nullable FK column. Existing rows have no trainer assoc — NULL is correct.
    op.add_column(
        "pt_packages",
        sa.Column(
            "trainer_id",
            sa.UUID(),
            nullable=True,
        ),
    )

    # 2) FK to trainers.id with ON DELETE RESTRICT (D-38-PATTERNS — trainers are
    #    soft-deleted via is_active; never hard-deleted. RESTRICT keeps the
    #    audit trail intact if surgery ever attempts to hard-delete a trainer.).
    op.create_foreign_key(
        op.f("fk_pt_packages_trainer_id_trainers"),
        "pt_packages",
        "trainers",
        ["trainer_id"],
        ["id"],
        ondelete="RESTRICT",
    )

    # 3) Index for forensic lookup `WHERE trainer_id = ?`. Non-partial btree.
    op.create_index(
        op.f("ix_pt_packages_trainer_id"),
        "pt_packages",
        ["trainer_id"],
    )


def downgrade() -> None:
    """Reverse upgrade in reverse order — preserves row data when trainer_id is NULL."""
    op.drop_index(
        op.f("ix_pt_packages_trainer_id"),
        table_name="pt_packages",
    )
    op.drop_constraint(
        op.f("fk_pt_packages_trainer_id_trainers"),
        "pt_packages",
        type_="foreignkey",
    )
    op.drop_column("pt_packages", "trainer_id")
