"""widen booking_notifications.kind CHECK for lifecycle email-fallback kinds (NOTIFY-09).

Revision ID: 0032_booking_notif_widen_kind
Revises: 0031_payment_receipts
Create Date: 2026-05-20 12:30:00.000000

Phase 45 Plan 08 (Rule-4 deviation discovered at executor-time — see
``45-08-SUMMARY.md`` for the Plan-vs-Reality narrative). The original 45-08
plan assumed ``booking_notifications.kind`` already admitted the 4 lifecycle
kinds, but Migration 0020 (Phase 39 D-39-13) landed the CHECK as
``kind IN ('reminder_24h')`` — single-element today, future kinds extend
the list via a follow-on migration.

Phase 45 D-45-05 / D-45-13 makes ``booking_notifications`` cross-channel
(channel discriminator landed in 0024), and the Plan 45-08 service-layer
fanout INSERTs rows with ``kind`` ∈
``{'confirmed', 'cancelled_by_client', 'cancelled_by_owner', 'reminder_24h'}``
each guarded by the cross-channel UNIQUE
``uq_booking_notifications_booking_kind_channel`` (also from 0024). The
existing CHECK rejects every kind except ``reminder_24h``, so we widen it
to the 4-kind set.

OPERATIONS
----------
Mirrors the drop-and-recreate-CHECK shape from
``0024_notification_channel_discriminator.py`` (which widened the same
table's UNIQUE):

  1. DROP CONSTRAINT ``ck_booking_notifications_kind`` (Migration 0020
     literal name via ``op.f()`` — naming convention expands to the
     same identifier).
  2. CREATE CONSTRAINT (same literal name) with widened predicate:
     ``kind IN ('reminder_24h', 'confirmed', 'cancelled_by_client',
                'cancelled_by_owner')``.

Zero-row backfill — production rows pre-Phase-45 all carry
``kind = 'reminder_24h'`` which remains valid under the widened CHECK
(superset relation: every old row passes the new predicate).

DOWNGRADE
---------
Reverses to the original single-element CHECK. If any rows with the new
lifecycle kinds exist at downgrade time, the CHECK creation will fail —
that is the correct behaviour (the downgrade is a disaster-recovery path,
not a routine rollback after live cron writes).
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0032_booking_notif_widen_kind"
down_revision: str | None = "0031_payment_receipts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Name MUST match Migration 0020's op.f()-derived constraint identifier
# letter-for-letter. The naming convention expands
# ``ck_%(table_name)s_%(constraint_name)s`` → ``ck_booking_notifications_kind``
# given the bare ``kind`` constraint_name from 0020.
_KIND_CHECK_NAME = "ck_booking_notifications_kind"

# Plan 45-08 widened predicate — 4 lifecycle kinds (D-45-05 / D-45-22):
#   - reminder_24h         (existing, Phase 39 D-39-13)
#   - confirmed            (Phase 45 NOTIFY-09 FSM transition hook)
#   - cancelled_by_client  (Phase 45 NOTIFY-09 FSM transition hook)
#   - cancelled_by_owner   (Phase 45 NOTIFY-09 FSM transition hook)
_NEW_KIND_PREDICATE = (
    "kind IN ('reminder_24h', 'confirmed', "
    "'cancelled_by_client', 'cancelled_by_owner')"
)
_OLD_KIND_PREDICATE = "kind IN ('reminder_24h')"


def upgrade() -> None:
    # All four constraint-name positions wrapped in op.f() so the project's
    # NAMING_CONVENTION (`ck_%(table_name)s_%(constraint_name)s`) does NOT
    # re-prefix and double-name the constraint. The original CHECK in
    # Migration 0020 was created via `op.f("ck_booking_notifications_kind")`,
    # so the on-disk constraint identifier is `ck_booking_notifications_kind`;
    # passing the same literal through op.f() is the canonical no-op that
    # preserves the literal name verbatim (mirrors 0024 lines 64 + 90 + 119).
    op.drop_constraint(
        op.f(_KIND_CHECK_NAME),
        "booking_notifications",
        type_="check",
    )
    op.create_check_constraint(
        op.f(_KIND_CHECK_NAME),
        "booking_notifications",
        _NEW_KIND_PREDICATE,
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f(_KIND_CHECK_NAME),
        "booking_notifications",
        type_="check",
    )
    op.create_check_constraint(
        op.f(_KIND_CHECK_NAME),
        "booking_notifications",
        _OLD_KIND_PREDICATE,
    )
