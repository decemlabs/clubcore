"""Phase 39 / NOTIFY-05: booking-reminder idempotency table.

Revision ID: 0020_booking_notifications
Revises: 0019_pt_sessions_booking_id
Create Date: 2026-05-18 00:00:00.000000

Notes:
- The unique constraint `uq_booking_notifications_booking_kind` is the single
  source of truth for cron idempotency (Phase 39 D-39-13, mirror of Phase 27
  D-27-15). Helper code in `app/modules/bookings/service.py` (plan 39-04's
  `_send_booking_reminders`) catches IntegrityError on this constraint to skip
  race-duplicates between the cron tick and the one-shot operator runner.
- FK uses ON DELETE RESTRICT (D-39-13 — deviation from v1.3
  `membership_notifications` which used CASCADE). Bookings are never
  hard-deleted in v1.5 (Phase 38 D-38-04 — decommission via status flip to
  'cancelled'), so RESTRICT is the safer floor: if a future DBA-direct surgery
  ever attempts to hard-delete a booking that still has notification history,
  the FK blocks the delete instead of silently orphaning the row.
- CHECK `kind IN ('reminder_24h')` — single-element today (Phase 39 D-39-13).
  Future kinds (e.g. 12h, post-session feedback ping) extend the CHECK list
  via a follow-on migration; the constraint shape stays the same.
- NO `telegram_chat_id` snapshot column (Phase 39 D-39-03 — explicit deviation
  from v1.3 `membership_notifications`.telegram_chat_id BIGINT). The cron
  resolves `clients.telegram_user_id` at send time via JOIN, so the chat id is
  always current (a client who re-links between booking + reminder uses the new
  chat). Saving a column we never read avoids a future schema-debt cleanup.
- Downgrade DROPs the table — disaster recovery only.
- Alembic chain context: 0017_bookings -> 0018_pt_packages_trainer_id
  -> 0019_pt_sessions_booking_id -> 0020_booking_notifications (Phase 39).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0020_booking_notifications"
down_revision: str | None = "0019_pt_sessions_booking_id"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1) CREATE TABLE booking_notifications (Phase 39 NOTIFY-05).
    op.create_table(
        "booking_notifications",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("booking_id", sa.UUID(), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column(
            "sent_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_booking_notifications")),
        sa.ForeignKeyConstraint(
            ["booking_id"],
            ["bookings.id"],
            name=op.f("fk_booking_notifications_booking_id_bookings"),
            # D-39-13: RESTRICT (deviation from v1.3 CASCADE — bookings never
            # hard-delete per Phase 38 D-38-04; RESTRICT prevents silent
            # cascade on accidental DBA-direct surgery).
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "kind IN ('reminder_24h')",
            name=op.f("ck_booking_notifications_kind"),
        ),
    )

    # 2) UNIQUE constraint on (booking_id, kind) — idempotency single source of truth.
    #    Explicit literal name (NOT op.f()) — matches the ORM __table_args__
    #    entry in models.py letter-for-letter so `alembic check` stays clean.
    op.create_unique_constraint(
        "uq_booking_notifications_booking_kind",
        "booking_notifications",
        ["booking_id", "kind"],
    )

    # 3) Single-column index for forensic per-booking lookup.
    op.create_index(
        op.f("ix_booking_notifications_booking_id"),
        "booking_notifications",
        ["booking_id"],
    )


def downgrade() -> None:
    """Reverse upgrade in reverse order — disaster recovery only."""
    op.drop_index(
        op.f("ix_booking_notifications_booking_id"),
        table_name="booking_notifications",
    )
    op.drop_constraint(
        "uq_booking_notifications_booking_kind",
        "booking_notifications",
        type_="unique",
    )
    op.drop_table("booking_notifications")
