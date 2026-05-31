"""Seed the bootstrap owner (AUTH-EP-04 / D-25).

Idempotent: INSERT ... ON CONFLICT DO NOTHING keyed on the partial-UNIQUE
index `uq_users_email_active` (lower(email) WHERE deleted_at IS NULL,
Alembic 0022). Re-running the script after the owner exists is a no-op.
The compose stack does NOT auto-run this — it is a one-shot operator
command:

    uv run python -m scripts.seed_demo_data

Reads SEED_OWNER_EMAIL + SEED_OWNER_PASSWORD from the environment. Both must
be set; otherwise the script exits 1 with a clear message.

The created owner has full_name='Owner' (D-01: single column). Operators can
update it via a future admin endpoint or `psql` once the owner has logged in.

Plan 71-09 (Gap 4): also seeds a minimal client catalog — one membership plan
and one PT-package plan — so /client/plans and /client/pt-packages are non-empty
out of the box for local UAT. Both inserts are idempotent (ON CONFLICT DO NOTHING
on the partial-UNIQUE lower(name) WHERE deleted_at IS NULL indexes).
"""

from __future__ import annotations

import asyncio
import os
import sys

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings
from app.core.permissions import Role
from app.core.security import hash_password
from app.modules.auth.models import User
from app.modules.memberships.models import MembershipPlan
from app.modules.pt_packages.models import PtPackagePlan


async def _seed_catalog(session: AsyncSession) -> None:
    """Idempotently seed a minimal client catalog (Plan 71-09 Gap 4).

    One active membership plan + one PT-package plan so the client catalog is
    non-empty for local UAT. Idempotency mirrors the owner seed: ON CONFLICT
    DO NOTHING on the partial-UNIQUE lower(name) WHERE deleted_at IS NULL
    indexes (uq_membership_plans_name_alive / uq_pt_package_plans_name_alive).
    Column names verified against the ORM models imported above.
    """
    plan_stmt = (
        pg_insert(MembershipPlan)
        .values(
            name="Месяц безлимит",
            duration_days=30,
            price_kopecks=500_000,
            freeze_days_limit=14,
            active=True,
        )
        .on_conflict_do_nothing(
            index_elements=[func.lower(MembershipPlan.name)],
            index_where=MembershipPlan.deleted_at.is_(None),
        )
    )
    await session.execute(plan_stmt)

    pt_stmt = (
        pg_insert(PtPackagePlan)
        .values(
            name="5 тренировок",
            session_count=5,
            price_kopecks=1_500_000,
            validity_days=90,
        )
        .on_conflict_do_nothing(
            index_elements=[func.lower(PtPackagePlan.name)],
            index_where=PtPackagePlan.deleted_at.is_(None),
        )
    )
    await session.execute(pt_stmt)
    await session.commit()
    print("Seeded client catalog: 1 membership plan + 1 PT-package (idempotent).")


async def _seed_promo_codes(session: AsyncSession) -> None:
    """Idempotently seed demo promo codes for 999.4 UAT (D-04).

    ON CONFLICT DO NOTHING on partial-UNIQUE uq_promo_codes_code_alive
    (upper(code) WHERE deleted_at IS NULL). Re-running is a no-op.

    discount_value encoding:
    - 'percentage' type: store value * 100 as integer (10% → 1000,
      keeping kopeck-integer discipline — no float in the DB).
    - 'fixed' type: store directly in kopecks (500 ₽ → 50000).
    """
    from app.modules.promo_codes.models import PromoCode

    codes = [
        {
            "code": "FIT10",
            "discount_type": "percentage",
            "discount_value": 10_00,  # 10% encoded as percent*100 = 1000
            "max_uses": None,
            "per_client_limit": 1,
            "is_active": True,
        },
        {
            "code": "FIRST500",
            "discount_type": "fixed",
            "discount_value": 500_00,  # 500 ₽ = 50000 kopecks
            "max_uses": 50,
            "per_client_limit": 1,
            "is_active": True,
        },
    ]
    for c in codes:
        stmt = (
            pg_insert(PromoCode)
            .values(**c)
            .on_conflict_do_nothing(
                index_elements=[func.upper(PromoCode.code)],
                index_where=PromoCode.deleted_at.is_(None),
            )
        )
        await session.execute(stmt)
    await session.commit()
    print(f"Seeded {len(codes)} promo codes (idempotent).")


async def _run() -> int:
    email = os.environ.get("SEED_OWNER_EMAIL")
    password = os.environ.get("SEED_OWNER_PASSWORD")
    if not email or not password:
        print(
            "SEED_OWNER_EMAIL and SEED_OWNER_PASSWORD must be set (see .env.example).",
            file=sys.stderr,
        )
        return 1
    if len(password) < 12:
        print(
            "SEED_OWNER_PASSWORD must be at least 12 characters (AUTH-EP-05 / NIST 800-63B 2024).",
            file=sys.stderr,
        )
        return 1

    email_lower = email.lower()
    settings = get_settings()
    engine = create_async_engine(str(settings.database_url))
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with sessionmaker() as session:
            stmt = (
                pg_insert(User)
                .values(
                    email=email_lower,
                    password_hash=await hash_password(password),
                    role=Role.OWNER.value,
                    full_name="Owner",
                )
                # Partial UNIQUE index `uq_users_email_active` was introduced
                # in Alembic 0022 (lower(email) WHERE deleted_at IS NULL).
                # ON CONFLICT must reference the same expression + predicate.
                .on_conflict_do_nothing(
                    index_elements=[func.lower(User.email)],
                    index_where=User.deleted_at.is_(None),
                )
            )
            await session.execute(stmt)
            await session.commit()
            print(f"Seeded owner {email_lower} (idempotent: no-op if existed).")

            # Phase 7 D-03 — optional Telegram username binding.
            telegram_username = os.environ.get("TELEGRAM_OWNER_USERNAME")
            if telegram_username:
                tg_lower = telegram_username.lstrip("@").lower()
                user = await session.scalar(select(User).where(User.email == email_lower))
                if user is not None and user.telegram_username != tg_lower:
                    user.telegram_username = tg_lower
                    await session.commit()
                    print(f"Bound telegram_username={tg_lower} to {email_lower}.")
                elif user is not None:
                    print(f"telegram_username for {email_lower} already set to {tg_lower} (no-op).")

            # Plan 71-09 (Gap 4) — non-empty client catalog for local UAT.
            await _seed_catalog(session)
            # Phase 999.4 D-04 — demo promo codes for checkout UAT.
            await _seed_promo_codes(session)
    finally:
        await engine.dispose()
    return 0


def main() -> int:
    return asyncio.run(_run())


if __name__ == "__main__":
    raise SystemExit(main())
