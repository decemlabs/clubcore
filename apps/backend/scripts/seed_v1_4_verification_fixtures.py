"""Seed deterministic v1.4 verification fixtures for Phase 36 milestone smoke.

Idempotent: INSERT ... ON CONFLICT DO NOTHING keyed on deterministic UUIDs
(via uuid5 over the fixture's stable natural key). Re-running the script
after the fixtures exist is a no-op.

Adds reception user + trainers + PT-package plans + additional clients beyond
what `seed_demo_data.py` provides. Distinct from `seed_verification_fixtures.py`
(v1.3 era) which seeded membership-expiry fixtures for Phase 29.

NOT loaded by the demo seed, NEVER runs in CI. One-shot operator command:

    cd apps/backend && uv run python -m scripts.seed_v1_4_verification_fixtures

Fixtures created (per D-36-06):
  - Users (2): verify_owner@local.dev (role=owner) + verify_reception@local.dev
    (role=reception). Passwords sourced from SEED_VERIFY_OWNER_PASSWORD and
    SEED_VERIFY_RECEPTION_PASSWORD env vars (Argon2id-hashed via
    app.core.security.hash_password).
  - MembershipPlans (2): "Verify Standard 30d" (freeze_days_limit=14, 30 days,
    3000 RUB) + "Verify Long 90d" (freeze_days_limit=30, 90 days, 7500 RUB).
  - PtPackagePlans (2): "Verify PT-5" (5 sessions, 5000 RUB) + "Verify PT-10"
    (10 sessions, 9000 RUB).
  - Trainers (3): "Trainer Alpha" (active), "Trainer Beta" (active),
    "Trainer Gamma" (inactive — is_active=False, deleted_at=NULL — the
    deactivated-not-deleted state scenario 07 exercises).
  - Clients (4): verify_sale, verify_refund, verify_pt, verify_smoke — each
    with last_name="Verify", first_name=<slug>, phone=+7700000000{1..4},
    email=<slug>@fixture.local. No memberships at seed time — scenarios
    provision via the API.

TM-29-02 guard: refuses to run unless DATABASE_URL contains 'localhost' or
'postgres:5432' -- prevents accidental execution against staging/prod. The
guard never prints the URL itself (token-leak risk in operator logs).

Pre-flight env check (v1.3 first-run-failure lesson): SECRET_KEY must be at
least 48 bytes; otherwise the seed aborts with an actionable error before
hitting the pyjwt InsecureKeyLengthWarning trap under
pyproject.toml [tool.pytest.ini_options].filterwarnings = ["error"].
"""

from __future__ import annotations

import asyncio
import os
import sys
import uuid

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.core.permissions import Role
from app.core.security import hash_password
from app.modules.auth.models import User
from app.modules.clients.models import Client
from app.modules.memberships.models import MembershipPlan
from app.modules.pt_packages.models import PtPackagePlan
from app.modules.trainers.models import Trainer

# ---------------------------------------------------------------------------
# Fixture data — D-36-06.
# Stable natural keys are encoded in the rows below; uuid5(NAMESPACE_DNS, key)
# produces the same id on every run, making INSERT ... ON CONFLICT DO NOTHING
# trivially idempotent without requiring natural-key UNIQUE constraints on
# every column.
# ---------------------------------------------------------------------------

_OWNER_EMAIL = "verify_owner@local.dev"
_RECEPTION_EMAIL = "verify_reception@local.dev"

_MEMBERSHIP_PLANS: tuple[tuple[str, int, int, int], ...] = (
    # (name, duration_days, freeze_days_limit, price_kopecks)
    ("Verify Standard 30d", 30, 14, 300000),
    ("Verify Long 90d", 90, 30, 750000),
)

_PT_PACKAGE_PLANS: tuple[tuple[str, int, int], ...] = (
    # (name, session_count, price_kopecks)
    ("Verify PT-5", 5, 500000),
    ("Verify PT-10", 10, 900000),
)

_TRAINERS: tuple[tuple[str, bool], ...] = (
    # (full_name, is_active)
    ("Trainer Alpha", True),
    ("Trainer Beta", True),
    ("Trainer Gamma", False),  # Deactivated-not-deleted (deleted_at=NULL).
)

_CLIENTS: tuple[tuple[str, str], ...] = (
    # (slug, phone) — email derived as f"{slug}@fixture.local".
    ("verify_sale", "+77000000001"),
    ("verify_refund", "+77000000002"),
    ("verify_pt", "+77000000003"),
    ("verify_smoke", "+77000000004"),
)


def _uuid5(key: str) -> uuid.UUID:
    """Deterministic UUIDv5 over NAMESPACE_DNS for a stable natural-key string."""
    return uuid.uuid5(uuid.NAMESPACE_DNS, key)


async def _run() -> int:
    settings = get_settings()
    db_url = str(settings.database_url)

    # TM-29-02 guard: refuse to run against a non-local DB. Do NOT print the
    # URL itself (token-leak risk in operator logs).
    if "localhost" not in db_url and "postgres:5432" not in db_url:
        print(
            "ERROR: seed_v1_4_verification_fixtures refuses to run against a "
            "non-local DATABASE_URL (TM-29-02). Expected 'localhost' or "
            "'postgres:5432' in the URL.",
            file=sys.stderr,
        )
        return 1

    # SECRET_KEY pre-flight (v1.3 first-run-failure lesson).
    secret = os.environ.get("SECRET_KEY", "") or settings.secret_key.get_secret_value()
    if len(secret) < 48:
        print(
            "ERROR: SECRET_KEY must be at least 48 bytes (v1.3 first-run-failure "
            "lesson — pyjwt InsecureKeyLengthWarning under "
            "pyproject.toml [tool.pytest.ini_options].filterwarnings=['error']).",
            file=sys.stderr,
        )
        return 1

    # Password sourcing.
    owner_pwd = os.environ.get("SEED_VERIFY_OWNER_PASSWORD")
    reception_pwd = os.environ.get("SEED_VERIFY_RECEPTION_PASSWORD")
    if not owner_pwd or len(owner_pwd) < 12:
        print(
            "ERROR: SEED_VERIFY_OWNER_PASSWORD must be set and at least 12 "
            "characters (NIST 800-63B 2024 + project password policy).",
            file=sys.stderr,
        )
        return 1
    if not reception_pwd or len(reception_pwd) < 12:
        print(
            "ERROR: SEED_VERIFY_RECEPTION_PASSWORD must be set and at least 12 "
            "characters (NIST 800-63B 2024 + project password policy).",
            file=sys.stderr,
        )
        return 1

    # Hash passwords ONCE before opening the session (Argon2id is CPU-bound).
    owner_hash = await hash_password(owner_pwd)
    reception_hash = await hash_password(reception_pwd)

    engine = create_async_engine(db_url)
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with sessionmaker() as session:
            # --- Users ---------------------------------------------------
            owner_id = _uuid5(_OWNER_EMAIL)
            reception_id = _uuid5(_RECEPTION_EMAIL)

            await session.execute(
                pg_insert(User)
                .values(
                    id=owner_id,
                    email=_OWNER_EMAIL,
                    password_hash=owner_hash,
                    role=Role.OWNER.value,
                    full_name="Verify Owner",
                )
                .on_conflict_do_nothing(index_elements=["id"])
            )
            await session.execute(
                pg_insert(User)
                .values(
                    id=reception_id,
                    email=_RECEPTION_EMAIL,
                    password_hash=reception_hash,
                    role=Role.RECEPTION.value,
                    full_name="Verify Reception",
                )
                .on_conflict_do_nothing(index_elements=["id"])
            )

            # --- MembershipPlans ----------------------------------------
            for name, duration_days, freeze_days_limit, price_kopecks in _MEMBERSHIP_PLANS:
                await session.execute(
                    pg_insert(MembershipPlan)
                    .values(
                        id=_uuid5(f"membership_plan:{name}"),
                        name=name,
                        duration_days=duration_days,
                        freeze_days_limit=freeze_days_limit,
                        price_kopecks=price_kopecks,
                    )
                    .on_conflict_do_nothing(index_elements=["id"])
                )

            # --- PtPackagePlans -----------------------------------------
            for name, session_count, price_kopecks in _PT_PACKAGE_PLANS:
                await session.execute(
                    pg_insert(PtPackagePlan)
                    .values(
                        id=_uuid5(f"pt_package_plan:{name}"),
                        name=name,
                        session_count=session_count,
                        price_kopecks=price_kopecks,
                    )
                    .on_conflict_do_nothing(index_elements=["id"])
                )

            # --- Trainers -----------------------------------------------
            for full_name, is_active in _TRAINERS:
                await session.execute(
                    pg_insert(Trainer)
                    .values(
                        id=_uuid5(f"trainer:{full_name}"),
                        full_name=full_name,
                        is_active=is_active,
                    )
                    .on_conflict_do_nothing(index_elements=["id"])
                )

            # --- Clients ------------------------------------------------
            # Clients require created_by_user_id — attribute to the verify owner.
            for slug, phone in _CLIENTS:
                email = f"{slug}@fixture.local"
                await session.execute(
                    pg_insert(Client)
                    .values(
                        id=_uuid5(f"client:{email}"),
                        last_name="Verify",
                        first_name=slug,
                        phone=phone,
                        email=email,
                        created_by_user_id=owner_id,
                    )
                    .on_conflict_do_nothing(index_elements=["id"])
                )

            await session.commit()
            print(
                "Seeded v1.4 verification fixtures: "
                "2 users (1 owner + 1 reception), "
                "2 membership plans, 2 PT-package plans, "
                "3 trainers (2 active + 1 inactive), 4 clients."
            )
    finally:
        await engine.dispose()
    return 0


def main() -> int:
    return asyncio.run(_run())


if __name__ == "__main__":
    raise SystemExit(main())
