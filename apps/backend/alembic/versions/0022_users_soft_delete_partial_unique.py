"""users.deleted_at + partial-UNIQUE on lower(email) for soft-delete (INFRA-38).

Revision ID: 0022_users_soft_delete_unique
Revises: 0021_bookings_actor_nullable
Create Date: 2026-05-18 18:00:00.000000

Phase 41 INFRA-38 / D-41-15. Schema half of D-41-04/05/07 — enables Phase 43
USERS-05 (soft-delete) + RESET-04 (re-onboard same email after soft-delete).

Three steps:
  1. Add users.deleted_at TIMESTAMPTZ NULL (Pitfall 6: tz-aware).
  2. Drop the existing global UNIQUE constraint on users.email
     (uq_users_email, from 0001_auth.py — case-sensitive table-level).
  3. Create a PARTIAL UNIQUE expression-index on lower(email)
     WHERE deleted_at IS NULL. This upgrades the invariant to
     case-insensitive AND soft-delete-aware in one step.

The partial predicate-on-expression form follows v1.2/v1.5 precedent
(0008_freeze.py uq_membership_freeze_periods_active_per_membership;
0017_bookings.py uq_bookings_slot_confirmed). Postgres-only — alembic
SQLite path is N/A for this codebase (CI + prod both Postgres 16).

No index on deleted_at — the partial-UNIQUE predicate index already covers
every `WHERE deleted_at IS NULL` lookup (D-41 Claude's Discretion bullet).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy import text

from alembic import op

revision: str = "0022_users_soft_delete_unique"
down_revision: str | None = "0021_bookings_actor_nullable"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Resolved from 0001_auth.py line 50 — table-level UniqueConstraint("email", name="uq_users_email").
_EXISTING_EMAIL_UNIQUE_CONSTRAINT = "uq_users_email"
_NEW_EMAIL_PARTIAL_UNIQUE_INDEX = "uq_users_email_active"


def upgrade() -> None:
    # 1. Add deleted_at column (TIMESTAMPTZ, nullable — soft-delete marker).
    op.add_column(
        "users",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )

    # 2. Drop existing table-level UNIQUE on email (case-sensitive, from 0001_auth.py).
    op.drop_constraint(
        _EXISTING_EMAIL_UNIQUE_CONSTRAINT,
        "users",
        type_="unique",
    )

    # 3. Create partial UNIQUE on lower(email) — only enforce across non-deleted rows.
    #    This is an INDEX (not a constraint) because expression predicates require
    #    an index in Postgres. Mirrors 0008_freeze.py / 0017_bookings.py precedent.
    op.create_index(
        _NEW_EMAIL_PARTIAL_UNIQUE_INDEX,
        "users",
        [text("lower(email)")],
        unique=True,
        postgresql_where=text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    # Reverse-order: drop the partial index, restore the case-sensitive table-level
    # UniqueConstraint on email, then drop the soft-delete column.
    op.drop_index(_NEW_EMAIL_PARTIAL_UNIQUE_INDEX, table_name="users")
    op.create_unique_constraint(
        _EXISTING_EMAIL_UNIQUE_CONSTRAINT,
        "users",
        ["email"],
    )
    op.drop_column("users", "deleted_at")
