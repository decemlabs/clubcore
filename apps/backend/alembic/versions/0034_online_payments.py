"""online_payments table + 4 indexes (Phase 49 PAY-01 / PAY-02 / D-49-05).

Revision ID: 0034_online_payments
Revises: 0033_clients_email_partial_unique
Create Date: 2026-05-22 00:00:00.000000

Phase 49 PAY-01/PAY-02 schema. Ships table + 2 full UNIQUEs + 2 partial
UNIQUE double-tap guards in ONE migration (atomic per success-criterion #5).

Partial UNIQUE indexes mirror the Phase 16/30 pattern of one constraint
per subject_kind (membership vs pt_package) instead of a polymorphic
single index. WHERE predicate ``status != 'canceled' AND <fk> IS NOT NULL``
allows retry after explicit cancellation (PITFALLS Pitfall 3).

The per-day partition expression is
``(initiated_at AT TIME ZONE 'Europe/Moscow')::date`` — NOT
``DATE(initiated_at)``. Postgres rejects ``DATE(timestamptz)`` in index
expressions because it is not IMMUTABLE (the result depends on the session
``TimeZone`` parameter); ``AT TIME ZONE`` with a literal timezone name
is IMMUTABLE and mirrors the Phase 6 ``visits.gym_date`` GENERATED column
(0006_visits.py:58).

The FK target ``pt_package_plans`` is the verified table name (singular
``package``, plural ``plans``) — confirmed against
``app/modules/pt_packages/models.py:64``.

ORM model is intentionally NOT added by this migration; Plan 49-02 owns
``app/modules/online_payments/models.py``.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy import text
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0034_online_payments"
down_revision: str | None = "0033_clients_email_partial_unique"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "online_payments",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "client_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "clients.id",
                ondelete="RESTRICT",
                name=op.f("fk_online_payments_client_id_clients"),
            ),
            nullable=False,
        ),
        sa.Column(
            "membership_plan_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "membership_plans.id",
                ondelete="RESTRICT",
                name=op.f("fk_online_payments_membership_plan_id_membership_plans"),
            ),
            nullable=True,
        ),
        sa.Column(
            "pt_package_plan_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "pt_package_plans.id",
                ondelete="RESTRICT",
                name=op.f("fk_online_payments_pt_package_plan_id_pt_package_plans"),
            ),
            nullable=True,
        ),
        sa.Column("yookassa_payment_id", sa.Text(), nullable=False),
        sa.Column("idempotency_key", sa.Text(), nullable=False),
        sa.Column("amount_kopecks", sa.Integer(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("confirmation_url", sa.Text(), nullable=True),
        sa.Column("confirmation_type", sa.Text(), nullable=False),
        sa.Column(
            "initiated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("succeeded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("canceled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "users.id",
                ondelete="SET NULL",
                name=op.f("fk_online_payments_created_by_user_id_users"),
            ),
            nullable=True,
        ),
        sa.Column("audit_correlation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.CheckConstraint(
            "amount_kopecks > 0",
            name=op.f("ck_online_payments_amount_kopecks_positive"),
        ),
        sa.CheckConstraint(
            "status IN ('pending','succeeded','canceled')",
            name=op.f("ck_online_payments_status"),
        ),
        sa.CheckConstraint(
            "confirmation_type IN ('redirect','qr')",
            name=op.f("ck_online_payments_confirmation_type"),
        ),
        sa.CheckConstraint(
            "(membership_plan_id IS NOT NULL) <> (pt_package_plan_id IS NOT NULL)",
            name=op.f("ck_online_payments_exactly_one_subject_fk"),
        ),
        sa.UniqueConstraint(
            "yookassa_payment_id",
            name=op.f("uq_online_payments_yookassa_payment_id"),
        ),
        sa.UniqueConstraint(
            "idempotency_key",
            name=op.f("uq_online_payments_idempotency_key"),
        ),
    )
    # IMMUTABLE per-day partition expression — see module docstring.
    _msk_date = sa.text("((initiated_at AT TIME ZONE 'Europe/Moscow')::date)")
    op.create_index(
        "uq_online_payments_membership_double_tap",
        "online_payments",
        ["client_id", "membership_plan_id", _msk_date],
        unique=True,
        postgresql_where=text(
            "status != 'canceled' AND membership_plan_id IS NOT NULL"
        ),
    )
    op.create_index(
        "uq_online_payments_pt_package_double_tap",
        "online_payments",
        ["client_id", "pt_package_plan_id", _msk_date],
        unique=True,
        postgresql_where=text(
            "status != 'canceled' AND pt_package_plan_id IS NOT NULL"
        ),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_online_payments_pt_package_double_tap", table_name="online_payments"
    )
    op.drop_index(
        "uq_online_payments_membership_double_tap", table_name="online_payments"
    )
    op.drop_table("online_payments")
