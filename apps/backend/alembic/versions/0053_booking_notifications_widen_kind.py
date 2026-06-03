"""widen booking_notifications.kind CHECK for 'rescheduled' kind (Phase 80 RESCH-02).

Revision ID: 0053_booking_notif_widen_kind_rescheduled
Revises: 0052_client_payment_methods
Create Date: 2026-06-03 00:00:00.000000

Phase 80 RESCH-02: adds 'rescheduled' (12 chars) to the existing 4-kind
CHECK predicate.  VARCHAR(32) is already wide enough — no column ALTER needed
(contrast 0032 which widened VARCHAR(16) → VARCHAR(32)).  Only the CHECK
constraint is dropped and recreated with the widened 5-kind predicate.

OPERATIONS
----------
1. DROP CONSTRAINT ``ck_booking_notifications_kind`` (Migration 0020 literal
   name via ``op.f()`` — naming convention expands to the same identifier).
2. CREATE CONSTRAINT (same literal name) with widened predicate:
   ``kind IN ('reminder_24h', 'confirmed', 'cancelled_by_client',
              'cancelled_by_owner', 'rescheduled')``.

Zero-row backfill — 'rescheduled' rows do not exist yet; all existing rows
carry one of the 4 pre-migration kinds which satisfy the widened CHECK.

DOWNGRADE
---------
Restores the CHECK to the 4-kind predicate (without 'rescheduled').
If any rows with kind='rescheduled' exist at downgrade time, the CHECK
creation will fail — that is the correct behaviour (disaster-recovery path).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0053_booking_notif_widen_kind_rescheduled"
down_revision: str | None = "0052_client_payment_methods"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Name MUST match Migration 0020's op.f()-derived constraint identifier
# letter-for-letter. The naming convention expands
# ``ck_%(table_name)s_%(constraint_name)s`` → ``ck_booking_notifications_kind``
# given the bare ``kind`` constraint_name from 0020.
_KIND_CHECK_NAME = "ck_booking_notifications_kind"

# Phase 80 widened predicate — 5 kinds (Phase 80 RESCH-02):
#   - reminder_24h         (Phase 39 D-39-13)
#   - confirmed            (Phase 45 NOTIFY-09)
#   - cancelled_by_client  (Phase 45 NOTIFY-09)
#   - cancelled_by_owner   (Phase 45 NOTIFY-09)
#   - rescheduled          (Phase 80 RESCH-02 — NEW)
_NEW_KIND_PREDICATE = (
    "kind IN ('reminder_24h', 'confirmed', 'cancelled_by_client',"
    " 'cancelled_by_owner', 'rescheduled')"
)
_OLD_KIND_PREDICATE = (
    "kind IN ('reminder_24h', 'confirmed', 'cancelled_by_client', 'cancelled_by_owner')"
)


def upgrade() -> None:
    # VARCHAR(32) is already wide enough — 'rescheduled' is 12 chars.
    # Include the alter_column call for symmetry with 0032's pattern and to
    # be explicit that the column width is intentionally unchanged.
    op.alter_column(
        "booking_notifications",
        "kind",
        type_=sa.String(length=32),
        existing_type=sa.String(length=32),
        existing_nullable=False,
    )

    # Drop + recreate the CHECK with widened predicate.
    # All constraint-name positions wrapped in op.f() so the project's
    # NAMING_CONVENTION does NOT double-prefix (mirrors 0032 lines 104/109).
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
    # Restore the narrower CHECK (without 'rescheduled').
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
