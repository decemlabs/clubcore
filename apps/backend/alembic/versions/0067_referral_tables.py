"""Referral domain tables (Phase 96 REFER-01 / REFER-03 / REFER-07).

Revision ID: 0067_referral_tables
Revises: 0066_message_attachments
Create Date: 2026-06-08

DDL for three referral tables:

  referral_codes   — one stable code per client; UNIQUE on code.
  referral_captures — one binding per referee; UNIQUE on referee_client_id.
  referral_config  — singleton owner-configurable bonus amounts (seeded in 0068).

Indexes:
  uq_referral_codes_code               UNIQUE via op.f() on referral_codes.code
  ix_referral_codes_client_id          plain index via op.f() on client_id
  uq_referral_captures_referee_client_id  UNIQUE LITERAL name (no op.f()),
                                           unconditional (not partial) — per
                                           96-PATTERNS naming discipline

FK naming: all FK constraint names are LITERAL strings (match ORM model names).
PK naming: op.f("pk_<table>") per naming convention.

Downgrade drops indexes (by their exact names) then tables in reverse FK order:
  referral_captures → referral_codes → referral_config
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy import func
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0067_referral_tables"
down_revision: str | None = "0066_message_attachments"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── referral_config ────────────────────────────────────────────────────────
    # Created first (no FK deps); seeded by migration 0068.
    op.create_table(
        "referral_config",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("referrer_bonus_kopecks", sa.BigInteger(), nullable=False),
        sa.Column("referee_welcome_kopecks", sa.BigInteger(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_referral_config")),
    )

    # ── referral_codes ─────────────────────────────────────────────────────────
    # FK → clients.id (RESTRICT).
    op.create_table(
        "referral_codes",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.String(16), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=func.now(),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_referral_codes")),
        sa.ForeignKeyConstraint(
            ["client_id"],
            ["clients.id"],
            name="fk_referral_codes_client_id_clients",
            ondelete="RESTRICT",
        ),
    )
    # Plain UNIQUE on code — op.f() because it is unconditional (not partial).
    op.create_index(
        op.f("uq_referral_codes_code"),
        "referral_codes",
        ["code"],
        unique=True,
    )
    # Plain index on client_id for GET /client/referral/code lookup performance.
    op.create_index(
        op.f("ix_referral_codes_client_id"),
        "referral_codes",
        ["client_id"],
        unique=False,
    )

    # ── referral_captures ──────────────────────────────────────────────────────
    # Three RESTRICT FKs: referee/referrer → clients, referral_code_id → referral_codes.
    op.create_table(
        "referral_captures",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("referee_client_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("referrer_client_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("referral_code_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=func.now(),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_referral_captures")),
        sa.ForeignKeyConstraint(
            ["referee_client_id"],
            ["clients.id"],
            name="fk_referral_captures_referee_client_id_clients",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["referrer_client_id"],
            ["clients.id"],
            name="fk_referral_captures_referrer_client_id_clients",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["referral_code_id"],
            ["referral_codes.id"],
            name="fk_referral_captures_referral_code_id_referral_codes",
            ondelete="RESTRICT",
        ),
    )
    # Unconditional UNIQUE on referee_client_id — LITERAL name (NOT op.f()) per
    # 96-PATTERNS discipline. No postgresql_where: the uniqueness is unconditional
    # (one capture per referee regardless of status — T-96-03 mitigate).
    op.create_index(
        "uq_referral_captures_referee_client_id",
        "referral_captures",
        ["referee_client_id"],
        unique=True,
    )


def downgrade() -> None:
    # Drop captures first (FK dep on referral_codes)
    op.drop_index(
        "uq_referral_captures_referee_client_id",
        table_name="referral_captures",
    )
    op.drop_table("referral_captures")

    # Drop codes second (FK dep on clients; no dep on config)
    op.drop_index(op.f("uq_referral_codes_code"), table_name="referral_codes")
    op.drop_index(op.f("ix_referral_codes_client_id"), table_name="referral_codes")
    op.drop_table("referral_codes")

    # Drop config last (no FK deps)
    op.drop_table("referral_config")
