"""PTS-TEST-01 — N parallel POST /pt-sessions → 1x201 + (N-1)x409 pt_package_exhausted.

Asserts the predicate ``sessions_remaining > 0 AND status='active'`` on the
atomic ``UPDATE pt_packages ... RETURNING`` (D-34-04a / PT-16) is the
source-of-truth race winner, NOT app-layer logic. The
``fetch_pt_package_metadata`` pre-decrement guard performs a SELECT-then-
DECREMENT (TOCTOU), so app-side checks alone cannot serialise concurrent
recordings — only the DB row lock + predicate wins.

Mirrors ``tests/integration/pt_packages/test_pt_package_refund_race.py``
(REF-TEST-02) with the subject swap pt_packages.refund → pt_sessions.record.
Uses ``db_session_real_commit`` because SAVEPOINT-isolated ``db_session``
interferes with concurrent UPDATE serialisation.

Per D-34-10 every POST /pt-sessions requires ``Idempotency-Key`` — the race
test uses 2 DISTINCT keys (one per concurrent request) so the idempotency
layer does NOT collapse them into a replay branch; the race we want to
observe is at the DB predicate, NOT at the idempotency cache.

Postgres-only — the test is skipped automatically when the database is
unreachable via the same fixture-skip convention as REF-TEST-02.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit_models import AuditLog
from app.core.permissions import Role
from app.core.security import hash_password
from app.modules.auth.models import User
from app.modules.clients.models import Client
from app.modules.pt_packages.models import PtPackage, PtPackagePlan
from app.modules.pt_sessions.models import PtSession
from app.modules.trainers.models import Trainer

_RACE_OWNER_EMAIL = "ptsess-record-race-owner@example.com"
_RACE_OWNER_PASSWORD = "hunter22hunter22"  # noqa: S105


async def _build_authed_client(app: FastAPI) -> AsyncClient:
    """Authenticate against the REAL app (no SAVEPOINT override)."""
    transport = ASGITransport(app=app)
    client = AsyncClient(transport=transport, base_url="http://testserver")
    r = await client.post(
        "/api/v1/auth/login",
        json={
            "email": _RACE_OWNER_EMAIL,
            "password": _RACE_OWNER_PASSWORD,
        },
    )
    assert r.status_code == 200, f"login failed: {r.text}"
    return client


@pytest.mark.asyncio
async def test_concurrent_record_pt_session_decrement_at_db_layer(
    db_session_real_commit: AsyncSession,
    app: FastAPI,
) -> None:
    """PTS-TEST-01: 2 parallel POST /pt-sessions against ``sessions_remaining=1``.

    Expected outcome: exactly 1x201 + 1x409 ``pt_package_exhausted``.

    Asserts the ``WHERE sessions_remaining > 0 AND status='active'`` predicate
    on the atomic ``UPDATE pt_packages ... RETURNING`` in
    ``pt_sessions.repository.atomic_decrement_pt_package`` is the
    source-of-truth race winner. The orchestrator's app-layer
    fetch_pt_package_metadata pre-check cannot serialise the race — only the
    DB row lock + predicate can. Race losers translate the 0-row UPDATE to
    ``PtPackageExhaustedError(code='pt_package_exhausted')`` per D-34-04a.

    Uses 2 DISTINCT Idempotency-Keys so the race surfaces at the DB layer
    rather than at the idempotency replay branch (a single shared key would
    collapse one of the requests into a cached-replay 201, masking the
    race).
    """
    # Seed owner + client + plan + active pt_package + trainer.
    hashed = await hash_password(_RACE_OWNER_PASSWORD)
    owner = User(
        email=_RACE_OWNER_EMAIL,
        password_hash=hashed,
        role=Role.OWNER,
        full_name="PT-Session Record Race Owner",
    )
    db_session_real_commit.add(owner)
    await db_session_real_commit.commit()
    await db_session_real_commit.refresh(owner)
    owner_id = owner.id

    plan = PtPackagePlan(
        name=f"RecordRacePlan-{uuid4().hex[:6]}",
        session_count=10,
        price_kopecks=500000,
        validity_days=90,
    )
    db_session_real_commit.add(plan)
    await db_session_real_commit.commit()
    await db_session_real_commit.refresh(plan)

    phone_suffix = uuid4().int % 10**7
    client_obj = Client(
        last_name=f"RecRaceClient-{uuid4().hex[:6]}",
        first_name="Test",
        phone=f"+7906{phone_suffix:07d}",
        created_by_user_id=owner_id,
    )
    db_session_real_commit.add(client_obj)
    await db_session_real_commit.commit()
    await db_session_real_commit.refresh(client_obj)

    today = datetime.now(tz=UTC).date()
    validity_days = plan.validity_days
    assert validity_days is not None
    pt_package = PtPackage(
        client_id=client_obj.id,
        plan_id=plan.id,
        plan_name_snapshot=plan.name,
        session_count_snapshot=plan.session_count,
        price_kopecks_snapshot=plan.price_kopecks,
        validity_days_snapshot=validity_days,
        sessions_remaining=1,  # The race target — only one session left.
        status="active",
        start_date=today,
        end_date=today + timedelta(days=validity_days - 1),
    )
    db_session_real_commit.add(pt_package)
    await db_session_real_commit.commit()
    await db_session_real_commit.refresh(pt_package)
    pt_package_id = pt_package.id

    trainer = Trainer(
        full_name=f"RaceTrainer-{uuid4().hex[:6]}",
        is_active=True,
    )
    db_session_real_commit.add(trainer)
    await db_session_real_commit.commit()
    await db_session_real_commit.refresh(trainer)
    trainer_id = trainer.id

    # Flush Redis so rate-limit / idempotency keys don't bleed across tests.
    await app.state.redis.flushdb()

    authed = await _build_authed_client(app)
    csrf_token = authed.cookies.get("sportzal_csrf") or ""

    performed_at = (datetime.now(tz=UTC) - timedelta(minutes=10)).isoformat()

    async def _post(idx: int) -> Any:
        # 2 DISTINCT Idempotency-Keys so the race surfaces at the DB layer.
        return await authed.post(
            "/api/v1/pt-sessions",
            json={
                "ptPackageId": str(pt_package_id),
                "trainerId": str(trainer_id),
                "performedAt": performed_at,
            },
            headers={
                "X-CSRF-Token": csrf_token,
                "Idempotency-Key": f"ptsess-record-race-{idx}-{uuid4().hex}",
            },
        )

    # 2 parallel POST requests.
    n_concurrent = 2
    responses = await asyncio.gather(*[_post(i) for i in range(n_concurrent)])
    await authed.aclose()

    statuses = sorted(r.status_code for r in responses)
    assert statuses == [201, 409], (
        f"PTS-TEST-01 failed: expected [201, 409], got {statuses}; "
        f"bodies: {[r.text for r in responses]}"
    )

    bodies_409 = [r.json() for r in responses if r.status_code == 409]
    codes = [b.get("code") for b in bodies_409]
    assert all(c == "pt_package_exhausted" for c in codes), (
        f"Unexpected 409 codes (expected all 'pt_package_exhausted'): {codes}"
    )

    # DB invariants: exactly 1 pt_sessions row + sessions_remaining=0 +
    # status='exhausted' (auto-transition from PT-17 / D-34-05).
    session_count = await db_session_real_commit.scalar(
        select(func.count())
        .select_from(PtSession)
        .where(PtSession.pt_package_id == pt_package_id)
    )
    assert session_count == 1, (
        f"Expected exactly 1 pt_sessions row after race, got {session_count}"
    )
    refreshed_pkg = await db_session_real_commit.scalar(
        select(PtPackage).where(PtPackage.id == pt_package_id)
    )
    assert refreshed_pkg is not None
    assert refreshed_pkg.sessions_remaining == 0
    assert refreshed_pkg.status == "exhausted"

    # Audit invariants: exactly 1 pt_session_recorded + exactly 1
    # pt_package_exhausted. The race-loser rolled back BEFORE audit emit
    # (the 0-row UPDATE returned None and the orchestrator raised
    # PtPackageExhaustedError, never reaching audit.emit).
    recorded_count = await db_session_real_commit.scalar(
        select(func.count())
        .select_from(AuditLog)
        .where(AuditLog.action == "pt_session_recorded")
    )
    assert recorded_count == 1, (
        f"Expected exactly 1 pt_session_recorded audit row, got {recorded_count}"
    )
    exhausted_count = await db_session_real_commit.scalar(
        select(func.count())
        .select_from(AuditLog)
        .where(
            AuditLog.action == "pt_package_exhausted",
            AuditLog.resource_id == pt_package_id,
        )
    )
    assert exhausted_count == 1, (
        f"Expected exactly 1 pt_package_exhausted audit row, got {exhausted_count}"
    )
