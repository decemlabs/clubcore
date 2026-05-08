"""Phase 24 / INFRA-16: extend memberships.status CHECK with 'frozen'.

Revision ID: 0007_status_taxonomy
Revises: 0006_visits
Create Date: 2026-05-08 00:00:00.000000

Postgres has no in-place CHECK alter; we DROP and re-CREATE the constraint
(D-24-02). Downgrade reverses to the v1.2 three-status form. ORM
`__table_args__` is updated in app/modules/memberships/models.py to mirror
this CHECK.

DDL only — no columns, no tables, no indexes (D-24-01).

Phase 24 ships the constraint extension; Phase 25 lands the freeze columns +
`membership_freeze_periods` table in `0008_freeze.py` (NOT `0007` as the
earlier milestone roadmap note suggested — see D-24-01).
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0007_status_taxonomy"
down_revision: str | None = "0006_visits"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE memberships DROP CONSTRAINT ck_memberships_status")
    op.execute(
        "ALTER TABLE memberships ADD CONSTRAINT ck_memberships_status "
        "CHECK (status IN ('active', 'expired', 'cancelled', 'frozen'))"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE memberships DROP CONSTRAINT ck_memberships_status")
    op.execute(
        "ALTER TABLE memberships ADD CONSTRAINT ck_memberships_status "
        "CHECK (status IN ('active', 'expired', 'cancelled'))"
    )
