"""REF-TEST-01 — N parallel POST /refund → exactly 1x200 + (N-1)x409 already_refunded.

Asserts the partial UNIQUE index ``uq_payments_refund_of_alive`` is the
source-of-truth race winner, NOT app-layer logic. The orchestrator's status
guard performs a SELECT-then-WRITE (TOCTOU), so app-side checks alone cannot
serialise concurrent refunds. Only the DB-level partial UNIQUE
(``WHERE refund_of IS NOT NULL``) wins the race.

Mirrors ``tests/integration/memberships/test_freeze_race.py:53-173`` with
constraint name + endpoint swapped. Uses ``db_session_real_commit`` because
SAVEPOINT-isolated ``db_session`` interferes with concurrent INSERT
serialisation (re-entrant nested transactions mask IntegrityError on race
losers).
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
from app.modules.memberships.models import Membership, MembershipPlan
from app.modules.payments.constants import SUBJECT_KIND_MEMBERSHIP, SUBJECT_KIND_REFUND
from app.modules.payments.models import Payment

_REFUND_OWNER_EMAIL = "refund-race-owner@example.com"
_REFUND_OWNER_PASSWORD = "hunter22hunter22"  # noqa: S105


async def _build_authed_client(app: FastAPI) -> AsyncClient:
    """Build and authenticate a client against the REAL app (no SAVEPOINT override)."""
    transport = ASGITransport(app=app)
    client = AsyncClient(transport=transport, base_url="http://testserver")
    r = await client.post(
        "/api/v1/auth/login",
        json={
            "email": _REFUND_OWNER_EMAIL,
            "password": _REFUND_OWNER_PASSWORD,
        },
    )
    assert r.status_code == 200, f"login failed: {r.text}"
    return client


@pytest.mark.asyncio
async def test_concurrent_refund_loses_at_db_layer(
    db_session_real_commit: AsyncSession,
    app: FastAPI,
) -> None:
    """REF-TEST-01: 5 parallel POST /refund on same membership.

    Expected outcome: exactly 1x200 + 4x409 already_refunded.

    Asserts the partial UNIQUE index ``uq_payments_refund_of_alive`` is the
    source-of-truth race winner. The orchestrator's app-layer status guard
    (status == 'frozen' / 'cancelled') cannot serialise the race — only the
    DB-level partial UNIQUE on ``(refund_of) WHERE refund_of IS NOT NULL``
    can. Race losers translate IntegrityError to
    ``AlreadyRefundedError(code='already_refunded')`` via the
    ``payments.repository._is_refund_of_uniqueness_conflict`` discriminator.
    """
    # Seed owner + client + plan + active membership + ORIGINAL sale payment
    hashed = await hash_password(_REFUND_OWNER_PASSWORD)
    owner = User(
        email=_REFUND_OWNER_EMAIL,
        password_hash=hashed,
        role=Role.OWNER,
        full_name="Refund Race Owner",
    )
    db_session_real_commit.add(owner)
    await db_session_real_commit.commit()
    await db_session_real_commit.refresh(owner)
    owner_id = owner.id

    plan = MembershipPlan(
        name=f"RefundRacePlan-{uuid4().hex[:6]}",
        duration_days=30,
        price_kopecks=250000,
        freeze_days_limit=14,
        active=True,
    )
    db_session_real_commit.add(plan)
    await db_session_real_commit.commit()

    phone_suffix = uuid4().int % 10**7
    client_obj = Client(
        last_name=f"RefundClient-{uuid4().hex[:6]}",
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

    # Seed ORIGINAL sale payment row directly (bypassing /memberships sale flow
    # so we don't need to thread Idempotency-Key + recorder wiring here).
    sale_payment = Payment(
        subject_kind=SUBJECT_KIND_MEMBERSHIP,
        subject_id=membership_id,
        amount_kopecks=plan.price_kopecks,
        method="cash",
        received_by_user_id=owner_id,
        refund_of=None,
    )
    db_session_real_commit.add(sale_payment)
    await db_session_real_commit.commit()

    # Flush Redis so rate-limit / idempotency keys don't bleed across tests.
    await app.state.redis.flushdb()

    authed = await _build_authed_client(app)
    csrf_token = authed.cookies.get("clubcore_csrf") or ""
    headers = {"X-CSRF-Token": csrf_token}

    async def _post(idx: int) -> Any:
        return await authed.post(
            f"/api/v1/memberships/{membership_id}/refund",
            json={"reason": f"race test {idx}"},
            headers=headers,
        )

    # 5 parallel POST requests (idx differentiates reasons; partial UNIQUE
    # ignores reason value).
    n_concurrent = 5
    responses = await asyncio.gather(*[_post(i) for i in range(n_concurrent)])
    await authed.aclose()

    statuses = sorted(r.status_code for r in responses)
    assert statuses == [200] + [409] * (n_concurrent - 1), (
        f"REF-TEST-01 failed: expected [200] + [409]*{n_concurrent - 1}, got {statuses}"
    )

    bodies_409 = [r.json() for r in responses if r.status_code == 409]
    codes = [b.get("code") for b in bodies_409]
    assert all(c == "already_refunded" for c in codes), (
        f"Unexpected 409 codes (expected all 'already_refunded'): {codes}"
    )

    # DB invariant: exactly 1 refund Payment row (uq_payments_refund_of_alive
    # serialised the concurrent INSERTs; losers rolled back BEFORE audit emit).
    refund_count = await db_session_real_commit.scalar(
        select(func.count())
        .select_from(Payment)
        .where(
            Payment.refund_of == sale_payment.id,
            Payment.subject_kind == SUBJECT_KIND_REFUND,
        )
    )
    assert refund_count == 1, f"Expected exactly 1 refund row, got {refund_count}"

    # Audit invariant: exactly 1 membership_refunded row + 1 refund_issued row.
    # Losing tasks rollback BEFORE both audit emits (issue_refund rolls back on
    # IntegrityError; orchestrator never reaches its membership_refunded emit).
    refunded_audit_count = await db_session_real_commit.scalar(
        select(func.count())
        .select_from(AuditLog)
        .where(
            AuditLog.action == "membership_refunded",
            AuditLog.resource_id == membership_id,
        )
    )
    assert refunded_audit_count == 1, (
        f"Expected exactly 1 membership_refunded audit row, got {refunded_audit_count}"
    )
    refund_issued_count = await db_session_real_commit.scalar(
        select(func.count()).select_from(AuditLog).where(AuditLog.action == "refund_issued")
    )
    assert refund_issued_count == 1, (
        f"Expected exactly 1 refund_issued audit row, got {refund_issued_count}"
    )
