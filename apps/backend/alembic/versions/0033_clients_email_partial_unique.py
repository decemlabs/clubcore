"""clients.email partial UNIQUE on lower(email) for case-insensitive uniqueness (INFRA-41).

Revision ID: 0033_clients_email_partial_unique
Revises: 0032_booking_notif_widen_kind
Create Date: 2026-05-21 00:00:00.000000

Phase 47 INFRA-41 / D-47-03 / D-47-04 / D-47-05. The ``clients.email`` column
ALREADY exists since Alembic 0002 (v1.1) — this migration does NOT add the
column and does NOT narrow Text to a fixed-width character type per D-47-03.
It adds ONLY a partial UNIQUE index on ``(lower(email))`` with predicate
``WHERE email IS NOT NULL AND deleted_at IS NULL`` per D-47-04.

Pre-flight duplicate check (D-47-05): the migration aborts with a
``RuntimeError`` listing offending ``lower(email)`` values if any
case-insensitive duplicate already exists among live rows. Single-gym
pet-project scale makes duplicates unlikely; fail-fast is safer than
silent dedup. No silent dedup, no soft-delete, no automatic backfill —
the operator resolves manually (soft-delete, merge, or correct typos)
and re-runs the migration.

Mirrors ``0022_users_soft_delete_partial_unique.py`` partial-UNIQUE pattern +
the operator-guard pre-flight pattern from
``0021_bookings_created_by_user_id_nullable.py:56-66``.

Down-revision pin (deviation note): the Phase 47 plan / PATTERNS template
documents ``down_revision = "0032_booking_notifications_widen_kind"`` (matching
the migration's *filename*), but the actual ``revision`` identifier inside
that file is ``"0032_booking_notif_widen_kind"`` (16-char internal id, distinct
from the 32-char filename). Pinning to the actual revision id per Task 1
step 1 instruction ("if a newer/different revision is the actual HEAD, pin
down_revision to the actual HEAD and document the deviation").
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy import text

from alembic import op

revision: str = "0033_clients_email_partial_unique"
down_revision: str | None = "0032_booking_notif_widen_kind"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NEW_EMAIL_PARTIAL_UNIQUE_INDEX = "ix_clients_email_lower_unique"


def upgrade() -> None:
    # Pre-flight duplicate check (D-47-05): abort before any DDL if a
    # case-insensitive duplicate already exists among LIVE rows.
    conn = op.get_bind()
    duplicates = conn.execute(
        sa.text(
            "SELECT lower(email) AS email_lc, COUNT(*) AS n "
            "FROM clients "
            "WHERE email IS NOT NULL AND deleted_at IS NULL "
            "GROUP BY lower(email) HAVING COUNT(*) > 1"
        )
    ).fetchall()
    if duplicates:
        offenders = ", ".join(f"{row.email_lc!r} ({row.n}x)" for row in duplicates)
        raise RuntimeError(
            "cannot apply 0033 — duplicate clients.email (case-insensitive) "
            f"rows present: {offenders}. Operator must dedup manually "
            "(soft-delete, merge, or correct typos) and re-run the migration."
        )

    # Create partial UNIQUE on lower(email) — only enforce across live rows
    # with a non-NULL email. Mirrors 0022_users_soft_delete_partial_unique.py.
    op.create_index(
        _NEW_EMAIL_PARTIAL_UNIQUE_INDEX,
        "clients",
        [text("lower(email)")],
        unique=True,
        postgresql_where=text("email IS NOT NULL AND deleted_at IS NULL"),
    )


def downgrade() -> None:
    # Reverse: drop the partial index only. The clients.email column is left
    # untouched (it pre-dates this migration — see Alembic 0002).
    op.drop_index(_NEW_EMAIL_PARTIAL_UNIQUE_INDEX, table_name="clients")
