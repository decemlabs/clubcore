"""audit_log.actor_email_snapshot + ON DELETE SET NULL on actor_user_id FK (INFRA-39).

Revision ID: 0023_audit_actor_snapshot
Revises: 0022_users_soft_delete_unique
Create Date: 2026-05-18 18:05:00.000000

Phase 41 INFRA-39 / D-41-08-10 — multi-user audit traceability.
Adds a denormalised email snapshot to every audit row written via the
Phase 41 actor_context ContextVar boundary (Plan 07). The FK behaviour
flips from ON DELETE RESTRICT (0002_clients.py line 159) to ON DELETE
SET NULL so audit rows survive any future hard-delete of users with
`actor_email_snapshot` preserved.

Two steps:
  1. Add audit_log.actor_email_snapshot TEXT NULL.
  2. DROP + recreate the actor_user_id FK with ON DELETE SET NULL.

Population rule (D-41-10): callsite OR ContextVar (Plan 07). System emits
(cron jobs, anti-oracle unknown-email branch) emit with actor_user_id=NULL
and actor_email_snapshot=NULL. Snapshot is conditional on non-NULL
actor_user_id, matching INFRA-39 spec.

D-41-09: actor_email_snapshot is a column on audit_log, NOT a payload
field — keeps the 11 v1.6 payload Pydantic schemas (Plan 02) free of
cross-cutting actor noise.

No index on actor_email_snapshot — analytics queries scanning by
email-snapshot are out of scope for v1.6 (deferred).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0023_audit_actor_snapshot"
down_revision: str | None = "0022_users_soft_delete_unique"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Resolved from 0002_clients.py line 158 — op.f("fk_audit_log_actor_user_id_users").
_ACTOR_FK_NAME = "fk_audit_log_actor_user_id_users"


def upgrade() -> None:
    op.add_column(
        "audit_log",
        sa.Column("actor_email_snapshot", sa.Text(), nullable=True),
    )
    op.drop_constraint(_ACTOR_FK_NAME, "audit_log", type_="foreignkey")
    op.create_foreign_key(
        _ACTOR_FK_NAME,
        "audit_log",
        "users",
        ["actor_user_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(_ACTOR_FK_NAME, "audit_log", type_="foreignkey")
    # Restore the original ondelete from 0002_clients.py line 159: RESTRICT.
    op.create_foreign_key(
        _ACTOR_FK_NAME,
        "audit_log",
        "users",
        ["actor_user_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.drop_column("audit_log", "actor_email_snapshot")
