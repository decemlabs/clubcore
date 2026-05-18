"""bookings.created_by_user_id -> NULLABLE (Phase 40 D-40-05 / BLOCKER-4).

Revision ID: 0021_bookings_actor_nullable
Revises: 0020_booking_notifications
Create Date: 2026-05-18 00:00:00.000000

Relaxes the NOT NULL constraint on ``bookings.created_by_user_id`` to support
self-service Telegram /book where no authenticated user is the creator. A NULL
value distinguishes "self-service via bot, see ``audit_log.payload.actor_role``"
from reception/owner rows (which always carry the authenticated actor's UUID).

Downgrade is gated by an operational guard: it refuses to run while any row
with ``created_by_user_id IS NULL`` exists, so accidental revert cannot
silently violate the previous NOT NULL invariant. The operator must clean up
bot bookings first (delete or back-fill with a system user id).

Alembic chain context:
    0019_pt_sessions_booking_id -> 0020_booking_notifications -> 0021_*.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0021_bookings_actor_nullable"
down_revision: str | None = "0020_booking_notifications"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Relax bookings.created_by_user_id to NULLABLE (Phase 40 BLOCKER-4 fix)."""
    op.alter_column(
        "bookings",
        "created_by_user_id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=True,
        existing_nullable=False,
    )


def downgrade() -> None:
    """Restore NOT NULL — refuses to run if any row has NULL created_by_user_id.

    Operator guard: a bot booking lands with ``created_by_user_id=NULL``; if
    any such row exists, downgrading would either silently violate the
    restored NOT NULL constraint (catastrophic) or trigger a Postgres-side
    failure halfway through the migration (also bad). We surface the
    contract breach explicitly so the operator chooses cleanup vs. abort.
    """
    conn = op.get_bind()
    null_count = conn.execute(
        sa.text(
            "SELECT COUNT(*) FROM bookings WHERE created_by_user_id IS NULL"
        )
    ).scalar_one()
    if null_count > 0:
        raise RuntimeError(
            "cannot downgrade: NULL created_by_user_id rows present "
            f"({null_count} rows); operator must clean up bot bookings first"
        )
    op.alter_column(
        "bookings",
        "created_by_user_id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=False,
        existing_nullable=True,
    )
