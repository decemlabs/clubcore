"""channel discriminator on membership_notifications + booking_notifications (NOTIFY-06).

Revision ID: 0024_notif_channel_discriminator
Revises: 0023_audit_actor_snapshot
Create Date: 2026-05-18 18:10:00.000000

Phase 41 INFRA-38 / NOTIFY-06 / D-41-15. Cross-channel idempotency
discriminator -- required BEFORE any NOTIFY-* phase per the v1.6 critical-
invariant ordering. Phase 45 reads this column when emitting email-channel
mirrors of expiring + booking-reminder + payment-receipt notifications.

For each of the two tables:
  1. ADD COLUMN channel TEXT NOT NULL DEFAULT 'telegram'
     CHECK (channel IN ('telegram','email'))
  2. DROP existing UNIQUE (existing-columns-pair)
  3. CREATE UNIQUE (existing-columns-pair, channel)

Zero-row backfill -- production data is reproducible by the next cron tick
(mirrors v1.3 NTF-05 / D-41-03 precedent). The DEFAULT 'telegram' assigns
every pre-v1.6 row to the Telegram channel without an explicit UPDATE.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0024_notif_channel_discriminator"
down_revision: str | None = "0023_audit_actor_snapshot"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Resolved from 0010_notifications.py line 86 / 0020_booking_notifications.py line 96.
_MEMBERSHIP_NOTIFS_OLD_UNIQUE = "uq_membership_notifications_membership_kind"
_BOOKING_NOTIFS_OLD_UNIQUE = "uq_booking_notifications_booking_kind"

_MEMBERSHIP_NOTIFS_NEW_UNIQUE = "uq_membership_notifications_membership_kind_channel"
_BOOKING_NOTIFS_NEW_UNIQUE = "uq_booking_notifications_booking_kind_channel"

# Resolved column pairs from source migrations.
_MEMBERSHIP_NOTIFS_COLS = ["membership_id", "kind"]
_BOOKING_NOTIFS_COLS = ["booking_id", "kind"]


def upgrade() -> None:
    # membership_notifications
    op.add_column(
        "membership_notifications",
        sa.Column(
            "channel",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'telegram'"),
        ),
    )
    op.create_check_constraint(
        # Pass the literal name through op.f() so the naming_convention
        # (`ck_%(table_name)s_%(constraint_name)s` in app/core/database.py:31)
        # does NOT re-prefix and double the table name. Mirrors the pattern
        # used in 0010_notifications.py line 78 for ck_membership_notifications_kind.
        op.f("ck_membership_notifications_channel"),
        "membership_notifications",
        "channel IN ('telegram','email')",
    )
    op.drop_constraint(
        _MEMBERSHIP_NOTIFS_OLD_UNIQUE,
        "membership_notifications",
        type_="unique",
    )
    op.create_unique_constraint(
        _MEMBERSHIP_NOTIFS_NEW_UNIQUE,
        "membership_notifications",
        [*_MEMBERSHIP_NOTIFS_COLS, "channel"],
    )

    # booking_notifications
    op.add_column(
        "booking_notifications",
        sa.Column(
            "channel",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'telegram'"),
        ),
    )
    op.create_check_constraint(
        op.f("ck_booking_notifications_channel"),
        "booking_notifications",
        "channel IN ('telegram','email')",
    )
    op.drop_constraint(
        _BOOKING_NOTIFS_OLD_UNIQUE,
        "booking_notifications",
        type_="unique",
    )
    op.create_unique_constraint(
        _BOOKING_NOTIFS_NEW_UNIQUE,
        "booking_notifications",
        [*_BOOKING_NOTIFS_COLS, "channel"],
    )


def downgrade() -> None:
    # booking_notifications
    op.drop_constraint(
        _BOOKING_NOTIFS_NEW_UNIQUE,
        "booking_notifications",
        type_="unique",
    )
    op.create_unique_constraint(
        _BOOKING_NOTIFS_OLD_UNIQUE,
        "booking_notifications",
        _BOOKING_NOTIFS_COLS,
    )
    op.drop_constraint(
        op.f("ck_booking_notifications_channel"),
        "booking_notifications",
        type_="check",
    )
    op.drop_column("booking_notifications", "channel")

    # membership_notifications
    op.drop_constraint(
        _MEMBERSHIP_NOTIFS_NEW_UNIQUE,
        "membership_notifications",
        type_="unique",
    )
    op.create_unique_constraint(
        _MEMBERSHIP_NOTIFS_OLD_UNIQUE,
        "membership_notifications",
        _MEMBERSHIP_NOTIFS_COLS,
    )
    op.drop_constraint(
        op.f("ck_membership_notifications_channel"),
        "membership_notifications",
        type_="check",
    )
    op.drop_column("membership_notifications", "channel")
