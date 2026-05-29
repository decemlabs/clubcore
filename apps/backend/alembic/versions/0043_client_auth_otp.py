"""Add client_id FK + XOR CHECK + partial-unique to otp_codes (Phase 68 D-03).

Revision ID: 0043_client_auth_otp
Revises: 0042_recurring_schedule_time_off
Create Date: 2026-05-29 00:00:00.000000

Additive migration — adds one nullable column + one CHECK constraint + one
partial-unique index to the existing otp_codes table.  Existing staff rows
keep user_id non-null and satisfy the XOR automatically — no backfill writes
(T-68-02 tamper-prevention).

Security:
  T-68-01 — ck_otp_codes_principal_xor CHECK forces exactly one of
             (user_id, client_id) non-null, preventing ownership confusion.
  T-68-02 — column added nullable with no default; existing rows untouched.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0043_client_auth_otp"
down_revision: str | None = "0042_recurring_schedule_time_off"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Add nullable client_id FK column — existing staff rows keep user_id
    # non-null and satisfy the XOR CHECK automatically (T-68-02).
    op.add_column(
        "otp_codes",
        sa.Column("client_id", sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        op.f("fk_otp_codes_client_id_clients"),
        "otp_codes",
        "clients",
        ["client_id"],
        ["id"],
        ondelete="CASCADE",
    )
    # XOR CHECK: exactly one of (user_id, client_id) must be non-null (T-68-01).
    op.create_check_constraint(
        "ck_otp_codes_principal_xor",
        "otp_codes",
        "(user_id IS NULL) <> (client_id IS NULL)",
    )
    # Client-principal partial-unique — mirrors uq_otp_codes_user_channel_active
    # for the client side: one active OTP per (client_id, channel).
    op.create_index(
        "uq_otp_codes_client_channel_active",
        "otp_codes",
        ["client_id", "channel"],
        unique=True,
        postgresql_where=sa.text("consumed_at IS NULL"),
    )


def downgrade() -> None:
    # Reverse order: index → check → FK → column.
    op.drop_index("uq_otp_codes_client_channel_active", table_name="otp_codes")
    op.drop_constraint("ck_otp_codes_principal_xor", "otp_codes", type_="check")
    op.drop_constraint(
        op.f("fk_otp_codes_client_id_clients"), "otp_codes", type_="foreignkey"
    )
    op.drop_column("otp_codes", "client_id")
