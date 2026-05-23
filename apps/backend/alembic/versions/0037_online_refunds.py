"""online_refunds table + UNIQUEs (Phase 51 REFUND-01 / D-51-04 / D-51-06).

Revision ID: 0037_online_refunds
Revises: 0036_payments_received_by_user_id_nullable
Create Date: 2026-05-23 00:00:00.000000

Ships table + UNIQUE(yookassa_refund_id) + UNIQUE(idempotency_key) +
partial UNIQUE(online_payment_id) WHERE status IN ('pending','succeeded')
(D-51-04).

The partial UNIQUE backs REFUND-03 at the schema layer: at most one
in-flight ('pending') or successful ('succeeded') refund request per
original online payment. A second concurrent refund attempt raises
``IntegrityError`` from this index, which the service layer maps to a
409 response (no duplicate ЮKassa /refunds call).

PATTERNS.md erratum honored: ``down_revision`` points at
``0036_payments_received_by_user_id_nullable`` (NOT ``0035_fiscal_receipts``
as CONTEXT D-51-06 incorrectly states). Phase 50 plan 50-03 Blocker #2
shipped 0036 before this plan; 0037 follows it.

Partial UNIQUE follows the Phase 49 0034 pattern: ``postgresql_where`` with
a plain text predicate. The index name
(``uq_online_refunds_alive_per_online_payment``) is a literal — NOT wrapped
in ``op.f()`` — because ``op.create_index`` Index objects use explicit
literal names in this project (see 0034 lines 137-156 precedent).

ORM model lives at app/modules/online_refunds/models.py (Plan 51-02).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy import text
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0037_online_refunds"
down_revision: str | None = "0036_payments_received_by_user_id_nullable"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "online_refunds",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("online_payment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("original_payment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("yookassa_refund_id", sa.Text(), nullable=False),
        sa.Column("idempotency_key", sa.Text(), nullable=False),
        sa.Column("amount_kopecks", sa.Integer(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("requested_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("audit_correlation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "requested_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("succeeded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("canceled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_online_refunds")),
        sa.ForeignKeyConstraint(
            ["online_payment_id"],
            ["online_payments.id"],
            name=op.f("fk_online_refunds_online_payment_id_online_payments"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["original_payment_id"],
            ["payments.id"],
            name=op.f("fk_online_refunds_original_payment_id_payments"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["client_id"],
            ["clients.id"],
            name=op.f("fk_online_refunds_client_id_clients"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["requested_by_user_id"],
            ["users.id"],
            name=op.f("fk_online_refunds_requested_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "amount_kopecks > 0",
            name=op.f("ck_online_refunds_amount_kopecks_positive"),
        ),
        sa.CheckConstraint(
            "status IN ('pending','succeeded','canceled')",
            name=op.f("ck_online_refunds_status"),
        ),
        sa.UniqueConstraint(
            "yookassa_refund_id",
            name=op.f("uq_online_refunds_yookassa_refund_id"),
        ),
        sa.UniqueConstraint(
            "idempotency_key",
            name=op.f("uq_online_refunds_idempotency_key"),
        ),
    )
    # Partial UNIQUE — at most one in-flight ('pending') or successful
    # ('succeeded') refund per original online_payment_id. Literal index name
    # (NOT via op.f()) per the 0034 precedent for create_index calls.
    op.create_index(
        "uq_online_refunds_alive_per_online_payment",
        "online_refunds",
        ["online_payment_id"],
        unique=True,
        postgresql_where=text("status IN ('pending','succeeded')"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_online_refunds_alive_per_online_payment",
        table_name="online_refunds",
    )
    op.drop_table("online_refunds")
