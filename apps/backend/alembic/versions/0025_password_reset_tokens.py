"""password_reset_tokens unified table (INFRA-38 / D-41-03/04/05).

Revision ID: 0025_password_reset_tokens
Revises: 0024_notif_channel_discriminator
Create Date: 2026-05-18 19:30:00.000000

Phase 41 INFRA-38 — fourth and final v1.6 INFRA-bedrock migration. Ships the
unified password-reset + invitation token table that Phase 44 RESET-01/03
queries against. Phase 44 ships ZERO migrations (D-41-03) — schema must land
here so the entire callsite is pure application code.

DESIGN — DB-table over itsdangerous-stateless (D-41-03)
-------------------------------------------------------
A stateless `itsdangerous` token signed against a per-user secret
(`password_changed_at`) was rejected at Phase 41 discuss because it couples
reset-token revocation to a global per-user clock that ALSO governs the
invitation-acceptance flow (USERS-03). The same `password_changed_at` flip
that revokes outstanding reset tokens for User X would also invalidate
outstanding invitation tokens — a collision the invitation flow cannot
tolerate. A row-per-token table sidesteps the coupling, gives us an explicit
`purpose` discriminator (D-41-04), an atomic-consume marker
(`consumed_at`), and an `audit_correlation_id` that links the issuing
audit event to the eventual consume event.

HASH-AT-REST DISCIPLINE (D-41-04, T-41-09-01)
---------------------------------------------
Only `token_hash = sha256(raw_token_bytes)` is persisted. The raw opaque
token (~32 bytes URL-safe base64) only ever exists in (a) the URL fragment
of the password-reset / invitation email body and (b) the in-memory issuing
function before sha256. Recovery from `token_hash` is computationally
infeasible; a DB-only compromise cannot mint working confirmation URLs.

ATOMIC-CONSUME + REPLAY-SAFETY (D-41-04, T-41-09-02)
----------------------------------------------------
`consumed_at` carries two semantics simultaneously, both racing-safely
attached to a single UPDATE … RETURNING:
  - "this token has been redeemed" — Phase 44's confirm endpoint flips
    NULL → NOW() in a single statement gated by `WHERE consumed_at IS NULL`;
    the partial-UNIQUE below means at most one row qualifies; a replay
    confirm finds zero rows and returns 410 Gone.
  - "this token has been revoked" — the same column also marks revocations
    (USERS-04 invitation-revoke, owner-initiated password-reset
    cancellation). The reason for the consume — redeemed vs revoked — is
    captured in the audit-event payload, NOT in a separate column.
    A separate `revoked_at` was rejected to keep the atomic-consume SQL
    a single literal statement (no OR'd disjunctive predicates).

PARTIAL UNIQUE (user_id, purpose) WHERE consumed_at IS NULL (D-41-05)
---------------------------------------------------------------------
Mirrors `refresh_tokens.token_hash` UNIQUE and the membership-freeze
`uq_membership_freeze_periods_active_per_membership` partial-UNIQUE
discipline. Guarantees one ACTIVE token per (user, purpose) pair at any
moment — re-issuing a reset for an already-pending user either succeeds
under a transaction that first consumes the prior row (Phase 44 path) or
fails-loud at the DB constraint if a concurrent issue races. Consumed rows
no longer participate in the constraint, so historical rows accumulate
freely until the cleanup cron lands at Phase 44.

CLEANUP CRON (D-41-06)
----------------------
Phase 44 introduces an ARQ daily job: `DELETE FROM password_reset_tokens
WHERE expires_at < NOW() - INTERVAL '30 days'`. Phase 41 does NOT carry
the cron — the table starts empty and stays bounded by issuance rate
until Phase 44 ships RESET-01 anyway.

INDEXES
-------
- `uq_password_reset_tokens_active` — partial UNIQUE per D-41-05; declared
  on (user_id, purpose) WHERE consumed_at IS NULL. Same shape as
  `uq_membership_freeze_periods_active_per_membership`.
- `ix_password_reset_tokens_token_hash` — NON-UNIQUE btree on token_hash.
  Phase 44's confirm path queries
  `UPDATE … WHERE token_hash = :hash AND purpose = :purpose
   AND consumed_at IS NULL RETURNING …`
  — the index supports the hash equality predicate. Per D-41-04 the hash
  is non-unique by design: the application pairs the hash filter with the
  purpose discriminator AND the non-NULL active gate; concrete uniqueness
  in any time-slice is enforced by the partial-UNIQUE above, not by an
  index on the hash alone.

DOWNGRADE
---------
Drops both indexes then the table. Lossless reverse — no other v1.6
migration depends on this table existing (NOTIFY-* uses 0024's channel
discriminator, not the token table).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy import text

from alembic import op

revision: str = "0025_password_reset_tokens"
down_revision: str | None = "0024_notif_channel_discriminator"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "password_reset_tokens",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("purpose", sa.Text(), nullable=False),
        sa.Column("token_hash", sa.Text(), nullable=False),
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "consumed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column("audit_correlation_id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "purpose IN ('password_reset', 'invitation')",
            name=op.f("ck_password_reset_tokens_purpose"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_password_reset_tokens")),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_password_reset_tokens_user_id_users"),
            ondelete="CASCADE",
        ),
    )

    # Partial UNIQUE (D-41-05) — one ACTIVE token per (user, purpose).
    # Constraint name MUST match the Index declared on
    # `PasswordResetToken.__table_args__` letter-for-letter so `alembic check`
    # stays clean. Mirrors the bookings `uq_bookings_slot_confirmed` pattern
    # (0017_bookings.py) where the partial Index lives in both places.
    op.create_index(
        "uq_password_reset_tokens_active",
        "password_reset_tokens",
        ["user_id", "purpose"],
        unique=True,
        postgresql_where=text("consumed_at IS NULL"),
    )

    # NON-UNIQUE hash-lookup index for Phase 44's atomic-consume path
    # (`UPDATE … WHERE token_hash = :hash AND purpose = … AND consumed_at IS NULL`).
    # Per D-41-04 the hash itself is non-unique by design — application pairs
    # it with the purpose filter + active gate; the partial-UNIQUE above is
    # the actual concurrency invariant.
    op.create_index(
        "ix_password_reset_tokens_token_hash",
        "password_reset_tokens",
        ["token_hash"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_password_reset_tokens_token_hash",
        table_name="password_reset_tokens",
    )
    op.drop_index(
        "uq_password_reset_tokens_active",
        table_name="password_reset_tokens",
    )
    op.drop_table("password_reset_tokens")
