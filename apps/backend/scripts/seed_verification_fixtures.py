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

Phase 46 D-46-26 / 46-13 Task 0: when both env vars
`SEED_VERIFY_OWNER_PASSWORD` and `SEED_VERIFY_RECEPTION_PASSWORD` are set
(>=12 chars each), additionally seeds two operator users for the v1.6 live
verification runbook (`.planning/milestones/v1.6-verification-evidence/run.sh`):
  - verify_owner@local.dev      (role=owner)
  - verify_reception@local.dev  (role=reception)
Password hashes use Argon2id via app.core.security.hash_password.
ON CONFLICT (id) DO UPDATE refreshes password_hash + is_active on re-runs.
If env vars are absent, this block is skipped silently (existing Phase 29
behavior preserved). If only one of the two env vars is set, FATAL exit.

TM-29-02 guard: refuses to run unless DATABASE_URL contains 'localhost' or
'postgres:5432' -- prevents accidental execution against staging/prod.
"""

from __future__ import annotations

import asyncio
import os
import sys
import uuid
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.core.permissions import Role
from app.core.security import hash_password
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

# Phase 46 D-46-26 / 46-13 Task 0 — operator user fixtures for the v1.6
# verification runbook. Seeded only when both env vars below are set
# (>=12 chars each); skipped silently otherwise so existing Phase 29 usage
# remains unaffected.
_OPERATOR_USERS: tuple[tuple[str, Role, str, str], ...] = (
    # (email, role, full_name, env_var_for_password)
    ("verify_owner@local.dev", Role.OWNER, "Verify Owner", "SEED_VERIFY_OWNER_PASSWORD"),
    (
        "verify_reception@local.dev",
        Role.RECEPTION,
        "Verify Reception",
        "SEED_VERIFY_RECEPTION_PASSWORD",
    ),
)

_OPERATOR_MIN_PASSWORD_LEN = 12


def _read_operator_passwords() -> dict[str, str] | None:
    """Return env-sourced passwords keyed by email, or None to skip seeding.

    Skip rule: BOTH env vars absent → skip silently (return None).
    FATAL rule: exactly ONE env var present, OR either value < 12 chars → exit 1.
    """
    env_pairs = [(email, os.environ.get(env_var)) for email, _, _, env_var in _OPERATOR_USERS]
    present = [(email, val) for email, val in env_pairs if val is not None]
    if not present:
        return None
    if len(present) != len(env_pairs):
        missing = [
            env_var
            for (_, _, _, env_var), (_, val) in zip(_OPERATOR_USERS, env_pairs, strict=True)
            if val is None
        ]
        print(
            "ERROR: operator-user seeding requires BOTH env vars; missing: "
            + ", ".join(missing),
            file=sys.stderr,
        )
        sys.exit(1)
    too_short = [
        env_var
        for (_, _, _, env_var), (_, val) in zip(_OPERATOR_USERS, env_pairs, strict=True)
        if val is not None and len(val) < _OPERATOR_MIN_PASSWORD_LEN
    ]
    if too_short:
        print(
            f"ERROR: operator passwords must be >= {_OPERATOR_MIN_PASSWORD_LEN} chars; "
            "too short: " + ", ".join(too_short),
            file=sys.stderr,
        )
        sys.exit(1)
    return {email: val for email, val in present if val is not None}


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

    # Phase 46 D-46-26: pre-validate operator-user env vars BEFORE opening the
    # DB session so a misconfigured run fails fast without partial side effects.
    operator_passwords = _read_operator_passwords()

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

            # Phase 46 D-46-26: seed operator users for the v1.6 verification
            # runbook. ON CONFLICT (id) DO UPDATE refreshes password_hash +
            # is_active + deleted_at on re-runs so credentials are always fresh.
            if operator_passwords is not None:
                for email, role, full_name, _env_var in _OPERATOR_USERS:
                    plain_password = operator_passwords[email]
                    password_hash = await hash_password(plain_password)
                    user_id = uuid.uuid5(uuid.NAMESPACE_DNS, email)
                    user_stmt = (
                        pg_insert(User)
                        .values(
                            id=user_id,
                            email=email,
                            email_verified=True,
                            password_hash=password_hash,
                            role=role,
                            full_name=full_name,
                            is_active=True,
                            status="active",
                            deleted_at=None,
                            deactivated_at=None,
                            deactivated_by_user_id=None,
                        )
                        .on_conflict_do_update(
                            index_elements=["id"],
                            set_={
                                "password_hash": password_hash,
                                "role": role,
                                "full_name": full_name,
                                "is_active": True,
                                "status": "active",
                                "email_verified": True,
                                "deleted_at": None,
                                "deactivated_at": None,
                                "deactivated_by_user_id": None,
                            },
                        )
                    )
                    await session.execute(user_stmt)
                print(
                    f"Seeded {len(_OPERATOR_USERS)} operator users "
                    "(verify_owner@local.dev + verify_reception@local.dev) "
                    "with env-driven passwords."
                )

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
