"""audit_log report + pagination indexes (Phase 54 INFRA-43 / D-54-11).

Revision ID: 0040_audit_log_report_indexes
Revises: 0039_payment_notifications
Create Date: 2026-05-24 00:00:00.000000

Adds three read-side indexes on audit_log to support Phase 55/56 report
and audit-log read-API queries without table scans:

- ix_audit_log_created_at: composite (created_at DESC, id DESC) — covers
  the Phase 56 stable pagination ordering. DESC via sa.text() predicate
  (literal name, NOT op.f(); mirrors the 0034/0037 create_index precedent).

- ix_audit_log_action: single-column btree — covers filter queries by
  event kind (action).

- ix_audit_log_resource_type: single-column btree — covers filter queries
  by resource domain (resource_type).

Per D-10: ix_payments_received_at already exists (migration 0012) and is
NOT touched here.

ORM counterpart: app/core/audit_models.py AuditLog.__table_args__
(updated in the same Phase 54 Plan 54-02 task). Names are literal strings
in both places so alembic check round-trips clean (D-12).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy import text  # noqa: F401 — used via sa.text() alias below

from alembic import op

revision: str = "0040_audit_log_report_indexes"
down_revision: str | None = "0039_payment_notifications"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Composite (created_at DESC, id DESC) — stable pagination ordering.
    # Literal name + sa.text() predicates per the 0034/0037 create_index pattern.
    op.create_index(
        "ix_audit_log_created_at",
        "audit_log",
        [sa.text("created_at DESC"), sa.text("id DESC")],
    )
    # Single-column btree indexes for action and resource_type filter queries.
    op.create_index("ix_audit_log_action", "audit_log", ["action"])
    op.create_index("ix_audit_log_resource_type", "audit_log", ["resource_type"])


def downgrade() -> None:
    # Drop in reverse order of creation.
    op.drop_index("ix_audit_log_resource_type", table_name="audit_log")
    op.drop_index("ix_audit_log_action", table_name="audit_log")
    op.drop_index("ix_audit_log_created_at", table_name="audit_log")
