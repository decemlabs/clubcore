"""otp_codes.channel discriminator + active partial-UNIQUE (AUTH-EM-01 / D-42-20).

Revision ID: 0027_otp_channel_discriminator
Revises: 0026_email_send_log
Create Date: 2026-05-19 00:00:00.000000

Phase 42 AUTH-EM-01 / D-42-20. Adds the cross-channel discriminator
required so Wave 2/3 OTP-email service logic can mint a per-channel
active code without colliding with the in-flight Telegram code, and so
the atomic UPDATE-to-consumed + INSERT-new in same UoW (D-42-22)
preserves RFC 6238 single-active discipline PER CHANNEL.

For ``otp_codes``:
  1. ADD COLUMN channel TEXT NOT NULL DEFAULT 'telegram'
     CHECK (channel IN ('telegram','email'))
  2. CREATE UNIQUE INDEX uq_otp_codes_user_channel_active
     ON otp_codes (user_id, channel) WHERE consumed_at IS NULL

Zero-row backfill -- production data is reproducible by the next OTP
mint (RFC 6238 codes expire in 10 minutes; pre-v1.6 rows are stale by
deploy time anyway). The DEFAULT 'telegram' assigns every pre-v1.6 row
to the Telegram channel without an explicit UPDATE.

Naming-convention note (mirrors 0024 commentary): pass the literal CHECK
constraint name through ``op.f()`` so the project ``naming_convention``
(``ck_%(table_name)s_%(constraint_name)s`` in
``app/core/database.py:31``) does NOT re-prefix the table name and
produce ``ck_otp_codes_ck_otp_codes_channel``.

DEVIATION FROM PLAN (Rule 1 — bug in plan assumption): the plan
referenced an existing partial-UNIQUE ``(user_id) WHERE consumed_at IS
NULL`` to DROP+RECREATE on ``(user_id, channel)``. Live introspection
against ``otp_codes`` (Postgres) and ``Base.metadata`` (ORM)
confirms NO such partial-UNIQUE exists in the v1.5 schema -- the only
otp_codes UNIQUEs are ``pk_otp_codes`` (PK on ``id``) and
``uq_otp_codes_deep_link_token_hash``. This migration therefore
CREATES the partial-UNIQUE outright; the downgrade DROPs it
symmetrically without recreating a non-existent predecessor. The
schema end-state matches the AUTH-EM-01 contract verbatim.

CR-04 DEFENSIVE CLEANUP (Phase 42 plan 42-15): Before the partial-UNIQUE
index creation, this migration now runs an UPDATE pass that marks any
duplicate same-(user_id, channel) ``consumed_at IS NULL`` rows as
``consumed_at = now()``, keeping only the latest by ``created_at DESC``.
Today the risk is bounded -- ``telegram_service.start_deep_link`` writes
``user_id = NULL`` (NULLs are distinct under UNIQUE in Postgres), so the
SC#1 demo path cannot trigger the collision. But ANY future writer that
inserts ``user_id IS NOT NULL + consumed_at IS NULL`` rows across the
channel will collide on this partial-UNIQUE without the cleanup, and
alembic upgrade will fail with ``duplicate key value violates unique
constraint "uq_otp_codes_user_channel_active"``. The defensive pass is
idempotent: zero rows match on a clean schema. See VERIFICATION.md CR-04
and REVIEW.md CR-04 for the full reasoning.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0027_otp_channel_discriminator"
down_revision: str | None = "0026_email_send_log"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# New partial-UNIQUE on (user_id, channel) WHERE consumed_at IS NULL --
# the AUTH-EM-01 contract. Allows one active Telegram OTP AND one
# active email OTP per user simultaneously (D-42-20 / D-42-22).
_OTP_NEW_UNIQUE = "uq_otp_codes_user_channel_active"


def upgrade() -> None:
    # 1. Channel column with zero-row-backfill default.
    op.add_column(
        "otp_codes",
        sa.Column(
            "channel",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'telegram'"),
        ),
    )

    # 2. CHECK constraint -- op.f() wrap is MANDATORY per PATTERNS.md §C
    # and the 0024 lesson (see module docstring).
    op.create_check_constraint(
        op.f("ck_otp_codes_channel"),
        "otp_codes",
        "channel IN ('telegram','email')",
    )

    # 2b. CR-04 defensive cleanup (plan 42-15) -- mark duplicate
    # same-(user_id, channel) consumed_at IS NULL rows as consumed_at = now(),
    # keeping only the latest by created_at DESC. Idempotent on a clean
    # schema. See module docstring for the full rationale.
    op.execute(
        "UPDATE otp_codes SET consumed_at = now() "
        "WHERE consumed_at IS NULL "
        "AND id NOT IN ("
        "    SELECT DISTINCT ON (user_id, channel) id FROM otp_codes "
        "    WHERE consumed_at IS NULL "
        "    ORDER BY user_id, channel, created_at DESC"
        ")"
    )

    # 3. Partial-UNIQUE on (user_id, channel) WHERE consumed_at IS NULL.
    # Single CREATE (no predecessor to DROP -- see deviation note in
    # module docstring).
    op.create_index(
        _OTP_NEW_UNIQUE,
        "otp_codes",
        ["user_id", "channel"],
        unique=True,
        postgresql_where=sa.text("consumed_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index(_OTP_NEW_UNIQUE, table_name="otp_codes")
    op.drop_constraint(
        op.f("ck_otp_codes_channel"),
        "otp_codes",
        type_="check",
    )
    op.drop_column("otp_codes", "channel")
