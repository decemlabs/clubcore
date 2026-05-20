"""widen booking_notifications.kind CHECK + column for lifecycle email-fallback (NOTIFY-09).

Revision ID: 0032_booking_notif_widen_kind
Revises: 0031_payment_receipts
Create Date: 2026-05-20 12:30:00.000000

Phase 45 Plan 08 (Rule-4 deviation discovered at executor-time — see
``45-08-SUMMARY.md`` for the Plan-vs-Reality narrative). The original 45-08
plan assumed ``booking_notifications.kind`` already admitted the 4 lifecycle
kinds, but Migration 0020 (Phase 39 D-39-13) landed BOTH:

  - CHECK ``kind IN ('reminder_24h')`` — single-element predicate, and
  - column type ``VARCHAR(16)`` — sized for the original ``reminder_24h``
    literal (12 chars) only.

The Plan 45-08 service-layer fanout INSERTs rows with kind values up to
``cancelled_by_client`` (19 chars) and ``cancelled_by_owner`` (18 chars)
— both overflow the VARCHAR(16) before the CHECK even runs. So we widen
BOTH in this migration.

Phase 45 D-45-05 / D-45-13 makes ``booking_notifications`` cross-channel
(channel discriminator landed in 0024), and the Plan 45-08 service-layer
fanout INSERTs rows with ``kind`` ∈
``{'confirmed', 'cancelled_by_client', 'cancelled_by_owner', 'reminder_24h'}``
each guarded by the cross-channel UNIQUE
``uq_booking_notifications_booking_kind_channel`` (also from 0024).

OPERATIONS
----------
Two coupled changes (single migration, atomic upgrade):

  1. ALTER COLUMN ``kind`` TYPE VARCHAR(32) — 32 chars accommodates the
     longest current literal (``cancelled_by_client`` = 19 chars) with
     ample headroom for future kinds.
  2. DROP CONSTRAINT ``ck_booking_notifications_kind`` (Migration 0020
     literal name via ``op.f()`` — naming convention expands to the
     same identifier).
  3. CREATE CONSTRAINT (same literal name) with widened predicate:
     ``kind IN ('reminder_24h', 'confirmed', 'cancelled_by_client',
                'cancelled_by_owner')``.

Zero-row backfill — production rows pre-Phase-45 all carry
``kind = 'reminder_24h'`` which fits VARCHAR(32) and remains valid under
the widened CHECK (superset relation: every old row passes both new
constraints).

DOWNGRADE
---------
Reverses strictly: restore the CHECK to single-element + narrow the
column back to VARCHAR(16). If any rows with the new lifecycle kinds
exist at downgrade time, the CHECK creation will fail (and on a non-
empty table the column-narrow ALTER would too) — that is the correct
behaviour (the downgrade is a disaster-recovery path, not a routine
rollback after live cron writes).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

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
    # 1) Widen the column type FIRST (before the new CHECK lands) so the
    #    column + CHECK constraints are consistent at every point in time
    #    during the migration. ALTER COLUMN TYPE VARCHAR(16) -> VARCHAR(32)
    #    is a Postgres in-place metadata change for ASCII shrink/grow (no
    #    table rewrite); existing rows fit trivially.
    op.alter_column(
        "booking_notifications",
        "kind",
        type_=sa.String(length=32),
        existing_type=sa.String(length=16),
        existing_nullable=False,
    )

    # 2) Drop + recreate the CHECK with widened predicate. All four
    #    constraint-name positions wrapped in op.f() so the project's
    #    NAMING_CONVENTION does NOT double-prefix (mirrors 0024 lines 64+90+119).
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
    # 1) Restore the CHECK (narrower predicate) BEFORE narrowing the
    #    column so the predicate-CHECK + type combination is consistent
    #    at every point.
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

    # 2) Narrow the column back. Will fail if any rows carry kinds
    #    longer than 16 chars (the new CHECK above prevents that for
    #    well-behaved upgrades; the failure mode here is disaster
    #    recovery against a dirty schema, which is acceptable).
    op.alter_column(
        "booking_notifications",
        "kind",
        type_=sa.String(length=16),
        existing_type=sa.String(length=32),
        existing_nullable=False,
    )
