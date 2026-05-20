"""Dev-only helper for Phase 46-13 verification: mint a password-reset token.

Direct service-layer invocation. Prints the raw token to stdout so the
verification runbook can recover it without MailHog in the sandbox-email
path. NOT for use in any production or staging environment.

Usage:
    cd apps/backend && uv run python -m scripts.verify.dev_mint_reset_token \\
        --email verify_reception@local.dev
    # Prints the raw token; runbook captures via `RAW_TOKEN=$(...)`.

TM-29-02 guard: refuses to run unless DATABASE_URL contains 'localhost' or
'postgres:5432' -- prevents accidental execution against staging/prod.
"""

from __future__ import annotations

import argparse
import asyncio
import secrets
import sys
import uuid
from datetime import datetime, timedelta, timezone
from hashlib import sha256

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.modules.auth.models import User
from app.modules.auth.password_reset_token_model import PasswordResetToken


async def _run(email: str) -> int:
    settings = get_settings()
    db_url = str(settings.database_url)
    if "localhost" not in db_url and "postgres:5432" not in db_url:
        print(
            "ERROR: dev_mint_reset_token refuses to run against a non-local "
            "DATABASE_URL (TM-29-02).",
            file=sys.stderr,
        )
        return 1

    engine = create_async_engine(db_url)
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with sessionmaker() as session:
            user = await session.scalar(select(User).where(User.email == email.lower()))
            if user is None:
                print(f"ERROR: no user with email={email}", file=sys.stderr)
                return 1

            # Clear any prior active reset token (uq_password_reset_tokens_active
            # has WHERE consumed_at IS NULL -- partial UNIQUE on user_id + purpose).
            existing = await session.scalar(
                select(PasswordResetToken).where(
                    PasswordResetToken.user_id == user.id,
                    PasswordResetToken.purpose == "password_reset",
                    PasswordResetToken.consumed_at.is_(None),
                )
            )
            if existing is not None:
                existing.consumed_at = datetime.now(tz=timezone.utc)
                await session.flush()

            raw_token = secrets.token_urlsafe(32)
            token_hash = sha256(raw_token.encode("utf-8")).hexdigest()
            session.add(
                PasswordResetToken(
                    user_id=user.id,
                    purpose="password_reset",
                    token_hash=token_hash,
                    expires_at=datetime.now(tz=timezone.utc) + timedelta(minutes=30),
                    audit_correlation_id=uuid.uuid4(),
                )
            )
            await session.commit()
            # Print ONLY the raw token to stdout so the runbook can $(capture) it.
            print(raw_token)
    finally:
        await engine.dispose()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", required=True)
    args = parser.parse_args()
    return asyncio.run(_run(args.email))


if __name__ == "__main__":
    raise SystemExit(main())
