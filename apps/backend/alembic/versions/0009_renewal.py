"""Phase 26 / MEM-REN-01: membership renewal chain attribution.

Revision ID: 0009_renewal
Revises: 0008_freeze
Create Date: 2026-05-09 00:00:00.000000

Notes:
- `previous_membership_id` is a Postgres-native self-FK on `memberships.id`
  with ON DELETE SET NULL (D-26-05). Self-FK has no cycle issues; SET NULL
  preserves the renewal row's data if the source is hard-deleted (DBA-direct
  surgery — ORM path forbids hard-delete of memberships per Phase 17), losing
  only chain attribution. Audit-log payload `source_membership_id` retains
  forensic back-pointer (Phase 26 D-26-15).
- Non-partial index on `previous_membership_id` per D-26-02 step 3. A partial
  index `WHERE previous_membership_id IS NOT NULL` would shrink size at
  production scale (10K+ rows) but is deferred — pet-project cardinality
  makes the cost/benefit negligible (CONTEXT.md Risks/Watchpoints #2).
- Downgrade is **lossless for data** (renewal rows survive); only chain
  attribution disappears (D-26-03). Disaster-recovery only.
- Alembic chain context: 0007_status_taxonomy → 0008_freeze → 0009_renewal
  → 0010_notifications (Phase 27).
- Constraint name `fk_memberships_previous_membership_id_memberships` is NOT
  literal-ref'd by service code (no IntegrityError discriminator translates
  this FK — concurrent source-delete is a DBA-direct surgery edge case, not
  an operator-flow conflict). Therefore NO entry is added to
  `apps/backend/alembic/env.py:_include_object` (mirrors Phase 25 D-25-22 —
  only literal-ref'd constraint names go there).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0009_renewal"
down_revision: str | None = "0008_freeze"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1) Add nullable self-FK column. Existing rows have no source — NULL is correct.
    op.add_column(
        "memberships",
        sa.Column(
            "previous_membership_id",
            sa.UUID(),
            nullable=True,
        ),
    )

    # 2) Self-FK to memberships.id. ON DELETE SET NULL — orphans the renewal but
    #    keeps it queryable (audit trail integrity vs cascade-delete chain).
    op.create_foreign_key(
        op.f("fk_memberships_previous_membership_id_memberships"),
        "memberships",
        "memberships",
        ["previous_membership_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # 3) Index for forensic lookup `WHERE previous_membership_id = ?`. Non-partial
    #    per D-26-02 step 3 / CONTEXT.md Risks/Watchpoints #2; partial deferred.
    op.create_index(
        op.f("ix_memberships_previous_membership_id"),
        "memberships",
        ["previous_membership_id"],
    )


def downgrade() -> None:
    """Reverse upgrade in reverse order — preserves row data, drops chain attribution."""
    op.drop_index(
        op.f("ix_memberships_previous_membership_id"),
        table_name="memberships",
    )
    op.drop_constraint(
        op.f("fk_memberships_previous_membership_id_memberships"),
        "memberships",
        type_="foreignkey",
    )
    op.drop_column("memberships", "previous_membership_id")
