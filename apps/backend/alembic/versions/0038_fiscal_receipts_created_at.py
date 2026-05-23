"""0038 — fiscal_receipts.created_at column (Phase 51 plan 51-09 monitor cron prereq).

The monitor_stale_fiscal_receipts ARQ cron (Plan 51-09 / D-51-16) needs to
filter ``status='pending' AND created_at < now() - INTERVAL '90s'``. The 0035
table omitted ``created_at`` (the FSM tracks lifecycle via explicit
``sent_at`` / ``succeeded_at`` / ``failed_at`` columns), but the monitor cron
needs a wall-clock anchor for rows that have NOT yet transitioned out of
'pending' — sent_at IS NULL on those rows. Adding ``created_at`` with
``server_default=now()`` is the minimal-risk path: every existing row gets
NOW() at migration time (acceptable — no rows currently reach 'pending'
in any current flow, so backfill semantics are vacuous).

Rule 2 deviation rationale: this column is required for monitor cron
correctness. Without it, the cron has no way to bound rows by age and
either skips the time guard entirely (false positives during in-flight
dispatch) or relies on a side-channel like audit_log JOINs (complex,
performance-sensitive).

Revision ID: 0038_fiscal_receipts_created_at
Revises: 0037_online_refunds
Create Date: 2026-05-23 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0038_fiscal_receipts_created_at"
down_revision: str | None = "0037_online_refunds"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "fiscal_receipts",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )


def downgrade() -> None:
    op.drop_column("fiscal_receipts", "created_at")
