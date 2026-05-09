"""VIS-TEST-01 — 10 parallel POST /api/v1/visits => exactly 1x201 + 9x409 duplicate_checkin.

Proves Postgres UNIQUE INDEX uq_visits_client_id_gym_date wins the race (D-08),
NOT app-layer logic. Uses db_session_real_commit (D-13 sibling) because
SAVEPOINT-isolated db_session interferes with concurrent INSERT serialisation.

After the burst, audit_log has exactly:
  - 1 visit_created
  - 9 visit_rejected_duplicate
"""

from __future__ import annotations

import asyncio
from datetime import datetime, time, timedelta
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit_models import AuditLog
from app.core.config import get_settings
from app.core.permissions import Role
from app.core.security import hash_password
from app.modules.auth.models import User
from app.modules.clients.models import Client
from app.modules.memberships.models import Membership, MembershipPlan

_MSK = ZoneInfo("Europe/Moscow")
_CONCURRENT_OWNER_EMAIL = "concurrent-owner@example.com"
_CONCURRENT_OWNER_PASSWORD = "hunter22hunter22"  # noqa: S105


async def _build_authed_client(app: FastAPI) -> AsyncClient:
    """Build and authenticate a client against the REAL app (no SAVEPOINT override)."""
    transport = ASGITransport(app=app)
    client = AsyncClient(transport=transport, base_url="http://testserver")
    r = await client.post(
        "/api/v1/auth/login",
        json={
            "email": _CONCURRENT_OWNER_EMAIL,
            "password": _CONCURRENT_OWNER_PASSWORD,
        },
    )
    assert r.status_code == 200, f"login failed: {r.text}"
    return client


@pytest.mark.asyncio
async def test_concurrent_check_in_one_wins(
    db_session_real_commit: AsyncSession,
    app: FastAPI,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """VIS-TEST-01 -- 10 parallel POST => exactly 1x201 + 9x409 duplicate_checkin.

    Proves Postgres UNIQUE INDEX uq_visits_client_id_gym_date wins the race
    (D-08), NOT app-layer logic. Uses db_session_real_commit (D-13 sibling)
    because SAVEPOINT-isolated db_session interferes with concurrent insert
    serialisation.
    """
    # Open gym hours wide so the test runs at any wall-clock time
    settings = get_settings()
    monkeypatch.setattr(settings, "gym_hours_start", time(0, 0))
    monkeypatch.setattr(settings, "gym_hours_end", time(23, 59))

    # Seed owner user + client + plan + membership via real-commit session
    hashed = await hash_password(_CONCURRENT_OWNER_PASSWORD)
    owner = User(
        email=_CONCURRENT_OWNER_EMAIL,
        password_hash=hashed,
        role=Role.OWNER,
        full_name="Concurrent Owner",
    )
    db_session_real_commit.add(owner)
    await db_session_real_commit.commit()
    await db_session_real_commit.refresh(owner)
    owner_id = owner.id

    plan = MembershipPlan(
        name=f"ConcPlan-{uuid4().hex[:6]}",
        duration_days=30,
        price_kopecks=250000,
        freeze_days_limit=14,
        active=True,
    )
    db_session_real_commit.add(plan)
    await db_session_real_commit.commit()

    phone_suffix = uuid4().int % 10**7
    client_obj = Client(
        last_name=f"ConcClient-{uuid4().hex[:6]}",
        first_name="Test",
        phone=f"+7906{phone_suffix:07d}",
        created_by_user_id=owner_id,
    )
    db_session_real_commit.add(client_obj)
    await db_session_real_commit.commit()

    today_msk = datetime.now(_MSK).date()
    membership = Membership(
        client_id=client_obj.id,
        plan_id=plan.id,
        duration_days_snapshot=plan.duration_days,
        price_kopecks_snapshot=plan.price_kopecks,
        freeze_days_limit_snapshot=plan.freeze_days_limit,
        plan_name_snapshot=plan.name,
        start_date=today_msk - timedelta(days=1),
        end_date=today_msk + timedelta(days=29),
        status="active",
        activation_policy="purchase_date",
    )
    db_session_real_commit.add(membership)
    await db_session_real_commit.commit()

    # Flush Redis so rate-limit keys don't bleed
    await app.state.redis.flushdb()

    authed = await _build_authed_client(app)
    csrf_token = authed.cookies.get("sportzal_csrf") or ""
    headers = {"X-CSRF-Token": csrf_token}
    payload = {"clientId": str(client_obj.id)}

    async def _post() -> Any:
        return await authed.post("/api/v1/visits", json=payload, headers=headers)

    # 10 parallel POST requests
    responses = await asyncio.gather(*[_post() for _ in range(10)])
    await authed.aclose()

    statuses = sorted(r.status_code for r in responses)
    assert statuses == [201] + [409] * 9, (
        f"VIS-TEST-01 failed: expected [201] + [409]*9, got {statuses}"
    )

    bodies_409 = [r.json() for r in responses if r.status_code == 409]
    assert all(b.get("code") == "duplicate_checkin" for b in bodies_409), (
        f"Unexpected 409 codes: {[b.get('code') for b in bodies_409]}"
    )

    # Audit row count assertions
    created_count = await db_session_real_commit.scalar(
        select(func.count()).select_from(AuditLog).where(
            AuditLog.action == "visit_created"
        )
    )
    rejected_count = await db_session_real_commit.scalar(
        select(func.count()).select_from(AuditLog).where(
            AuditLog.action == "visit_rejected_duplicate"
        )
    )
    assert created_count == 1, (
        f"Expected exactly 1 visit_created audit row, got {created_count}"
    )
    assert rejected_count == 9, (
        f"Expected exactly 9 visit_rejected_duplicate audit rows, got {rejected_count}"
    )
