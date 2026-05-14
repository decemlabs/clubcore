"""Seed deterministic verification fixtures for Phase 29 milestone smoke.

Idempotent: INSERT ... ON CONFLICT DO NOTHING keyed on deterministic UUIDs
(via uuid5 over the fixture's email-shaped identifier `verify_*@fixture.local`).
Re-running the script after the fixtures exist is a no-op.

NOT loaded by the demo seed, NEVER runs in CI. One-shot operator command:

    cd apps/backend && uv run python -m scripts.seed_verification_fixtures

Requires the demo seed (`seed_demo_data`) to have populated the bootstrap
owner AND at least one MembershipPlan with `freeze_days_limit >= 7` BEFORE
this script runs (the verification fixtures attach to that plan; owner is
the `created_by_user_id` on every fixture client).

Loads 5 clients + 5 memberships:
  - verify_7d / verify_3d / verify_1d  -> end_date = today + {7,3,1}
                                          (3 expiring-DM scenarios)
  - verify_freezable                   -> end_date = today + 30
                                          (freeze/unfreeze/renew chain)
  - verify_cancelled                   -> status = 'cancelled', end_date = today + 30
                                          (negative renew path)

TM-29-02 guard: refuses to run unless DATABASE_URL contains 'localhost' or
'postgres:5432' -- prevents accidental execution against staging/prod.
"""

from __future__ import annotations

import asyncio
import sys
import uuid
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.core.permissions import Role
from app.modules.auth.models import User
from app.modules.clients.models import Client
from app.modules.memberships.models import Membership, MembershipPlan

_FIXTURES: tuple[tuple[str, int, int, str], ...] = (
    # (email_key, telegram_user_id, days_to_end, status)
    ("verify_7d@fixture.local", 7000000007, 7, "active"),
    ("verify_3d@fixture.local", 7000000003, 3, "active"),
    ("verify_1d@fixture.local", 7000000001, 1, "active"),
    ("verify_freezable@fixture.local", 7000000099, 30, "active"),
    ("verify_cancelled@fixture.local", 7000000000, 30, "cancelled"),
)

_PHONE_BY_EMAIL: dict[str, str] = {
    "verify_7d@fixture.local": "+79990000007",
    "verify_3d@fixture.local": "+79990000003",
    "verify_1d@fixture.local": "+79990000001",
    "verify_freezable@fixture.local": "+79990000099",
    "verify_cancelled@fixture.local": "+79990000000",
}


async def _run() -> int:
    settings = get_settings()
    db_url = str(settings.database_url)
    # TM-29-02 guard: refuse to run against a non-local DB. Do NOT print the
    # URL itself (token-leak risk in operator logs).
    if "localhost" not in db_url and "postgres:5432" not in db_url:
        print(
            "ERROR: seed_verification_fixtures refuses to run against a non-local "
            "DATABASE_URL (TM-29-02). Expected 'localhost' or 'postgres:5432' in "
            "the URL.",
            file=sys.stderr,
        )
        return 1

    today_msk = datetime.now(ZoneInfo("Europe/Moscow")).date()

    engine = create_async_engine(db_url)
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with sessionmaker() as session:
            owner = await session.scalar(
                select(User).where(User.role == Role.OWNER).order_by(User.created_at)
            )
            if owner is None:
                print(
                    "ERROR: no owner user found. Run "
                    "`uv run python -m scripts.seed_demo_data` first.",
                    file=sys.stderr,
                )
                return 1

            plan = await session.scalar(
                select(MembershipPlan)
                .where(MembershipPlan.freeze_days_limit >= 7)
                .where(MembershipPlan.deleted_at.is_(None))
                .order_by(MembershipPlan.created_at)
            )
            if plan is None:
                print(
                    "ERROR: no eligible MembershipPlan with freeze_days_limit >= 7 "
                    "found. Seed at least one plan before running this script.",
                    file=sys.stderr,
                )
                return 1

            for email_key, telegram_user_id, days_to_end, status in _FIXTURES:
                client_id = uuid.uuid5(uuid.NAMESPACE_DNS, email_key)
                membership_id = uuid.uuid5(
                    uuid.NAMESPACE_DNS, f"{email_key}-membership"
                )
                first_name, _, _ = email_key.partition("@")
                phone = _PHONE_BY_EMAIL[email_key]

                client_stmt = (
                    pg_insert(Client)
                    .values(
                        id=client_id,
                        last_name="Verify",
                        first_name=first_name,
                        phone=phone,
                        email=email_key,
                        telegram_user_id=telegram_user_id,
                        created_by_user_id=owner.id,
                    )
                    .on_conflict_do_nothing(index_elements=["id"])
                )
                await session.execute(client_stmt)

                end_date = today_msk + timedelta(days=days_to_end)
                membership_stmt = (
                    pg_insert(Membership)
                    .values(
                        id=membership_id,
                        client_id=client_id,
                        plan_id=plan.id,
                        plan_name_snapshot=plan.name,
                        duration_days_snapshot=plan.duration_days,
                        price_kopecks_snapshot=plan.price_kopecks,
                        freeze_days_limit_snapshot=plan.freeze_days_limit,
                        start_date=today_msk,
                        end_date=end_date,
                        status=status,
                    )
                    .on_conflict_do_nothing(index_elements=["id"])
                )
                await session.execute(membership_stmt)

            await session.commit()
            print(
                "Seeded verification fixtures: 5 clients, 5 memberships "
                "(3 expiring, 1 active-freezable, 1 cancelled)."
            )
    finally:
        await engine.dispose()
    return 0


def main() -> int:
    return asyncio.run(_run())


if __name__ == "__main__":
    raise SystemExit(main())
