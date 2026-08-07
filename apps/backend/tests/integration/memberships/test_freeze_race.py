"""MEM-FRZ-TEST-03 — N parallel POST /freeze => exactly 1x200 + (N-1)x409.

Asserts the database converges to exactly one open freeze period. Depending on
transaction visibility, a loser may observe either the already-frozen state or
the now-invalid active-to-frozen transition; both are valid conflict responses.

Mirrors `tests/integration/visits/test_visits_concurrent.py:54-160` with
constraint name + endpoint swapped. Uses db_session_real_commit because
SAVEPOINT-isolated db_session interferes with concurrent INSERT serialisation.
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
from app.modules.memberships.models import Membership, MembershipFreezePeriod, MembershipPlan

_RACE_OWNER_EMAIL = "freeze-race-owner@example.com"
_RACE_OWNER_PASSWORD = "hunter22hunter22"  # noqa: S105


async def _build_authed_client(app: FastAPI) -> AsyncClient:
    """Build and authenticate a client against the REAL app (no SAVEPOINT override)."""
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
async def test_concurrent_freeze_race_serialised_by_partial_unique_index(
    db_session_real_commit: AsyncSession,
    app: FastAPI,
) -> None:
    """MEM-FRZ-TEST-03: 5 parallel POST /freeze on same membership.

    Expected outcome: exactly 1x200 + 4x409 conflict responses.

    Asserts the database invariant remains the source of truth. A concurrent
    loser can be rejected by the unique constraint as already_frozen or can
    observe the committed frozen status and fail the transition guard first.
    """
    # Seed owner + client + plan + active membership via real-commit session
    hashed = await hash_password(_RACE_OWNER_PASSWORD)
    owner = User(
        email=_RACE_OWNER_EMAIL,
        password_hash=hashed,
        role=Role.OWNER,
        full_name="Freeze Race Owner",
    )
    db_session_real_commit.add(owner)
    await db_session_real_commit.commit()
    await db_session_real_commit.refresh(owner)
    owner_id = owner.id

    plan = MembershipPlan(
        name=f"RacePlan-{uuid4().hex[:6]}",
        duration_days=30,
        price_kopecks=250000,
        freeze_days_limit=14,
        active=True,
    )
    db_session_real_commit.add(plan)
    await db_session_real_commit.commit()

    phone_suffix = uuid4().int % 10**7
    client_obj = Client(
        last_name=f"RaceClient-{uuid4().hex[:6]}",
        first_name="Test",
        phone=f"+7905{phone_suffix:07d}",
        created_by_user_id=owner_id,
    )
    db_session_real_commit.add(client_obj)
    await db_session_real_commit.commit()

    today = datetime.now(tz=UTC).date()
    membership = Membership(
        client_id=client_obj.id,
        plan_id=plan.id,
        plan_name_snapshot=plan.name,
        duration_days_snapshot=plan.duration_days,
        price_kopecks_snapshot=plan.price_kopecks,
        freeze_days_limit_snapshot=plan.freeze_days_limit,
        start_date=today - timedelta(days=1),
        end_date=today + timedelta(days=29),
        status="active",
        activation_policy="purchase_date",
    )
    db_session_real_commit.add(membership)
    await db_session_real_commit.commit()
    await db_session_real_commit.refresh(membership)
    membership_id = membership.id

    # Flush Redis so rate-limit keys don't bleed
    await app.state.redis.flushdb()

    authed = await _build_authed_client(app)
    csrf_token = authed.cookies.get("clubcore_csrf") or ""

    async def _post() -> Any:
        # Phase 66 IDM-07: freeze_membership now requires Idempotency-Key.
        # Each concurrent request uses a UNIQUE key so all 5 pass the idempotency
        # guard and race to the DB UNIQUE index — exactly the serialisation we test.
        headers = {
            "X-CSRF-Token": csrf_token,
            "Idempotency-Key": uuid4().hex,
        }
        return await authed.post(
            f"/api/v1/memberships/{membership_id}/freeze",
            headers=headers,
        )

    # 5 parallel POST requests
    n_concurrent = 5
    responses = await asyncio.gather(*[_post() for _ in range(n_concurrent)])
    await authed.aclose()

    statuses = sorted(r.status_code for r in responses)
    assert statuses == [200] + [409] * (n_concurrent - 1), (
        f"MEM-FRZ-TEST-03 failed: expected [200] + [409]*{n_concurrent - 1}, got {statuses}"
    )

    bodies_409 = [r.json() for r in responses if r.status_code == 409]
    codes = [b.get("code") for b in bodies_409]
    expected_conflict_codes = {"already_frozen", "invalid_transition"}
    assert all(c in expected_conflict_codes for c in codes), f"Unexpected 409 codes: {codes}"

    # DB invariant: exactly 1 row in membership_freeze_periods with ended_at IS NULL
    open_count = await db_session_real_commit.scalar(
        select(func.count())
        .select_from(MembershipFreezePeriod)
        .where(
            MembershipFreezePeriod.membership_id == membership_id,
            MembershipFreezePeriod.ended_at.is_(None),
        )
    )
    assert open_count == 1, f"Expected exactly 1 open freeze period, got {open_count}"

    # Audit invariant: exactly 1 membership_frozen row.
    # Losing tasks rollback BEFORE audit emit (service.py: rollback then raise),
    # so no audit row is written for failed inserts.
    frozen_audit_count = await db_session_real_commit.scalar(
        select(func.count())
        .select_from(AuditLog)
        .where(
            AuditLog.action == "membership_frozen",
            AuditLog.resource_id == membership_id,
        )
    )
    assert frozen_audit_count == 1, (
        f"Expected exactly 1 membership_frozen audit row, got {frozen_audit_count}"
    )
