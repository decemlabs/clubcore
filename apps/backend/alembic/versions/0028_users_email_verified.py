"""users.email_verified BOOLEAN NOT NULL DEFAULT FALSE (D-42-21 / AUTH-EM-02).

Revision ID: 0028_users_email_verified
Revises: 0027_otp_codes_channel_discriminator
Create Date: 2026-05-19 10:51:00.000000

Phase 42 ships the column + the AUTH-EM-02 read ('when channel=email: requires
user with verified email'). Phase 43 ships the verify-flow set side (open
conflict #7 — trust owner-entered addresses vs click-to-verify).

BOOTSTRAP RUNBOOK (operator-action — NOT code):
  Existing operator users default email_verified=FALSE — flip the owner
  account via direct SQL after migration lands:

    UPDATE users SET email_verified = TRUE WHERE email = '<owner_email>';

  The OWNER's first email-OTP login flow becomes Phase 43's first
  verify-flow consumer naturally.

Anti-oracle invariant preserved (D-42-22): when channel='email' and
user.email_verified=FALSE OR user not found OR is_active=FALSE, the request
returns IDENTICAL 202 shape as the success branch with a constant-time
floor sleep — no oracle leak.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0028_users_email_verified"
down_revision: str | None = "0027_otp_codes_channel_discriminator"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "email_verified",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("FALSE"),
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "email_verified")
