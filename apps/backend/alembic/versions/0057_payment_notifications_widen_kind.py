"""widen payment_notifications.kind CHECK for 'autopay_charge_succeeded' kind (Phase 84 APAY-04).

Revision ID: 0057_payment_notifications_widen_kind
Revises: 0056_autopay_charges
Create Date: 2026-06-05

Phase 84 APAY-04: adds 'autopay_charge_succeeded' to the existing 4-kind CHECK
predicate on ``payment_notifications.kind``.

The autopay success notification is dispatched via ``dispatch_payment_notification``
(the existing online-payments dispatcher) because the webhook creates an
``online_payments`` row on the ok path, allowing the claim to key on
``online_payment_id`` (D-52-10 pattern). The kind 'autopay_charge_succeeded' must
be accepted by the DB-level CHECK constraint for the claim INSERT to succeed.

OPERATIONS
----------
1. DROP CONSTRAINT ``ck_payment_notifications_kind`` (Migration 0039 name via
   raw DDL — D-84-01 discipline: locked tables use ``op.execute()`` to avoid
   NAMING_CONVENTION double-prefix on already-expanded constraint names).
2. CREATE CONSTRAINT (same literal name) with widened predicate:
   ``kind IN ('payment_succeeded', 'refund_succeeded', 'payment_canceled',
              'fiscal_failed', 'autopay_charge_succeeded')``.

Zero-row backfill — 'autopay_charge_succeeded' rows do not exist yet; all existing
rows carry one of the 4 pre-migration kinds which satisfy the widened CHECK.

DOWNGRADE
---------
Restores the CHECK to the 4-kind predicate (without 'autopay_charge_succeeded').
If any rows with kind='autopay_charge_succeeded' exist at downgrade time, the
CHECK creation will fail — that is the correct behaviour (disaster-recovery path).
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0057_payment_notifications_widen_kind"
down_revision: str | None = "0056_autopay_charges"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Literal constraint name — the DB stores it as-is from Migration 0039's op.f() call.
# D-84-01 discipline: use raw ALTER TABLE DDL to avoid NAMING_CONVENTION double-prefix
# (op.f() would double-expand an already-expanded constraint name).
_KIND_CHECK_NAME = "ck_payment_notifications_kind"

_NEW_KIND_PREDICATE = (
    "kind IN ('payment_succeeded', 'refund_succeeded', 'payment_canceled',"
    " 'fiscal_failed', 'autopay_charge_succeeded')"
)
_OLD_KIND_PREDICATE = (
    "kind IN ('payment_succeeded', 'refund_succeeded', 'payment_canceled', 'fiscal_failed')"
)


def upgrade() -> None:
    # D-84-01: raw DDL for locked tables — avoids NAMING_CONVENTION double-prefix.
    op.execute(f"ALTER TABLE payment_notifications DROP CONSTRAINT {_KIND_CHECK_NAME}")
    op.execute(
        f"ALTER TABLE payment_notifications ADD CONSTRAINT {_KIND_CHECK_NAME}"
        f" CHECK ({_NEW_KIND_PREDICATE})"
    )


def downgrade() -> None:
    # Restore the narrower CHECK (without 'autopay_charge_succeeded').
    op.execute(f"ALTER TABLE payment_notifications DROP CONSTRAINT {_KIND_CHECK_NAME}")
    op.execute(
        f"ALTER TABLE payment_notifications ADD CONSTRAINT {_KIND_CHECK_NAME}"
        f" CHECK ({_OLD_KIND_PREDICATE})"
    )
