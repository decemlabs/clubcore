"""0036 — payments.received_by_user_id nullable (Phase 50 Plan 50-03 / Blocker #2).

Phase 32 declared ``payments.received_by_user_id`` as NOT NULL — every
ledger row was written by an in-person operator (the ``actor.id`` from
the request session). Phase 50 introduces the ЮKassa webhook flow
(Plan 50-04) which records ``method='online'`` payments WITHOUT a
``CurrentUser`` context (the webhook is anonymous; IP allowlist is the
only auth gate). The widened ``PaymentRecorder`` Protocol
(``app/core/dependencies.py``, Plan 50-03 Task 1) lets ``received_by_user_id``
default to ``None``; the underlying column must accept NULL or the INSERT
will fail with ``IntegrityError`` on the NOT NULL constraint.

The FK ``fk_payments_received_by_user_id_users`` and its ``ON DELETE RESTRICT``
clause are preserved — only the column nullability flips. The
``ix_payments_received_by_user_id`` btree is unaffected (Postgres allows
NULLs in btree indexes).

Round-trip: ``alembic upgrade head -> alembic downgrade -1 -> alembic upgrade head``
must succeed against a database where every existing row has a non-NULL
``received_by_user_id`` (the v1.4..v1.6 invariant). The downgrade flips
the column back to NOT NULL — if any NULL rows exist downgrade rightly
fails, surfacing the regression rather than silently masking it.

Revision ID: 0036_payments_received_by_user_id_nullable
Revises: 0035_fiscal_receipts
Create Date: 2026-05-22 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0036_payments_received_by_user_id_nullable"
down_revision: str | None = "0035_fiscal_receipts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "payments",
        "received_by_user_id",
        nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "payments",
        "received_by_user_id",
        nullable=False,
    )
