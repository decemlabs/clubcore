"""Seed a fake-linked test client for local PWA login UAT (dev-only).

Creates (idempotently) a single alive client with a known E.164 phone and a
fake ``telegram_user_id`` so the client OTP flow treats it as "linked" and
generates a code. In ENVIRONMENT=dev the OTP sender (app.main) logs the code to
the backend console — see ``_send_client_otp_dm`` — so you can sign in without a
real Telegram chat:

    Phone to enter in the PWA login screen : +7 999 000-00-01
    Backend log line after "Получить код"  : client_otp_dev_code ... code=NNNNNN

Run once (the compose stack does NOT auto-run it):

    cd apps/backend && uv run python -m scripts.seed_dev_client

Refuses to run unless ENVIRONMENT=dev — this client is a test fixture and must
never exist in staging/prod. Requires the bootstrap owner to exist first
(``scripts.seed_demo_data``) because clients.created_by_user_id is NOT NULL.
"""

from __future__ import annotations

import asyncio
import sys

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.modules.auth.models import User
from app.modules.clients.models import Client

# Stable, recognisable test fixture values.
_DEV_CLIENT_PHONE = "+79990000001"  # entered as "999 000-00-01" in the +7 field
_DEV_CLIENT_TELEGRAM_USER_ID = 999000001  # fake chat id — never a real Telegram chat


async def _run() -> int:
    settings = get_settings()
    if settings.environment != "dev":
        print(
            f"Refusing to seed the dev test client: ENVIRONMENT={settings.environment!r} "
            "(only 'dev' is allowed).",
            file=sys.stderr,
        )
        return 1

    engine = create_async_engine(str(settings.database_url))
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with sessionmaker() as session:
            owner = await session.scalar(
                select(User).where(User.deleted_at.is_(None)).order_by(User.created_at).limit(1)
            )
            if owner is None:
                print(
                    "No user found for clients.created_by_user_id. Seed the owner first:\n"
                    "    uv run python -m scripts.seed_demo_data",
                    file=sys.stderr,
                )
                return 1

            existing = await session.scalar(
                select(Client).where(
                    Client.phone == _DEV_CLIENT_PHONE,
                    Client.deleted_at.is_(None),
                )
            )

            if existing is not None:
                if existing.telegram_user_id is None:
                    existing.telegram_user_id = _DEV_CLIENT_TELEGRAM_USER_ID
                    await session.commit()
                    print(
                        f"Linked existing client {_DEV_CLIENT_PHONE} "
                        f"(telegram_user_id={_DEV_CLIENT_TELEGRAM_USER_ID})."
                    )
                else:
                    print(
                        f"Dev test client {_DEV_CLIENT_PHONE} already linked "
                        f"(telegram_user_id={existing.telegram_user_id}) — no-op."
                    )
            else:
                session.add(
                    Client(
                        last_name="Тестовый",
                        first_name="Клиент",
                        phone=_DEV_CLIENT_PHONE,
                        telegram_user_id=_DEV_CLIENT_TELEGRAM_USER_ID,
                        created_by_user_id=owner.id,
                    )
                )
                await session.commit()
                print(
                    f"Seeded dev test client {_DEV_CLIENT_PHONE} "
                    f"(telegram_user_id={_DEV_CLIENT_TELEGRAM_USER_ID})."
                )

            print(
                "\nLogin in the PWA with phone '999 000-00-01'. After tapping "
                "'Получить код', read the 6-digit code from the backend log "
                "(structlog event 'client_otp_dev_code')."
            )
    finally:
        await engine.dispose()
    return 0


def main() -> int:
    return asyncio.run(_run())


if __name__ == "__main__":
    raise SystemExit(main())
