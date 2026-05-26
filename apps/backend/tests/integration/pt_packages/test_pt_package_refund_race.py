"""REF-TEST-02 — N parallel /pt-packages/{id}/refund POSTs → 1x200 + (N-1)x409 already_refunded.

Asserts the partial UNIQUE index ``uq_payments_refund_of_alive`` is the
source-of-truth race winner for the PT-package refund flow, NOT app-layer
logic. The orchestrator's FSM guard (``_assert_can_transition``) performs a
SELECT-then-WRITE (TOCTOU) so app-side checks alone cannot serialise
concurrent refunds; only the DB-level partial UNIQUE
(``WHERE refund_of IS NOT NULL``) wins the race.

Mirrors ``tests/integration/payments/test_payments_refund_race.py`` (REF-TEST-01)
verbatim with the membership/PT-package subject swap. Uses
``db_session_real_commit`` because SAVEPOINT-isolated ``db_session`` interferes
with concurrent INSERT serialisation.

Per D-33-16 every PT-package POST requires ``Idempotency-Key`` — the race
test uses 5 DISTINCT keys (one per concurrent request) so the idempotency
layer does NOT collapse them into a replay branch; the race we want to
observe is at the DB partial UNIQUE, NOT at the idempotency cache.
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
from app.modules.payments.constants import (
    SUBJECT_KIND_PT_PACKAGE,
    SUBJECT_KIND_REFUND,
)
from app.modules.payments.models import Payment
from app.modules.pt_packages.models import PtPackage, PtPackagePlan

_REFUND_OWNER_EMAIL = "ptpkg-refund-race-owner@example.com"
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
async def test_concurrent_refund_pt_package_loses_at_db_layer(
    db_session_real_commit: AsyncSession,
    app: FastAPI,
) -> None:
    """REF-TEST-02: 5 parallel POST /pt-packages/{id}/refund on same instance.

    Expected outcome: exactly 1x200 + 4x409 already_refunded.

    Asserts ``uq_payments_refund_of_alive`` is the source-of-truth race
    winner. The orchestrator's app-layer FSM guard cannot serialise the race
    — only the DB-level partial UNIQUE on
    ``(refund_of) WHERE refund_of IS NOT NULL`` can. Race losers translate
    IntegrityError to ``AlreadyRefundedError(code='already_refunded')`` via
    the ``payments.repository._is_refund_of_uniqueness_conflict``
    discriminator inside ``issue_refund``.
    """
    # Seed owner + client + plan + active pt_package + ORIGINAL sale payment.
    hashed = await hash_password(_REFUND_OWNER_PASSWORD)
    owner = User(
        email=_REFUND_OWNER_EMAIL,
        password_hash=hashed,
        role=Role.OWNER,
        full_name="PT-Package Refund Race Owner",
    )
    db_session_real_commit.add(owner)
    await db_session_real_commit.commit()
    await db_session_real_commit.refresh(owner)
    owner_id = owner.id

    plan = PtPackagePlan(
        name=f"RefundRacePlan-{uuid4().hex[:6]}",
        session_count=10,
        price_kopecks=500000,
        validity_days=90,
    )
    db_session_real_commit.add(plan)
    await db_session_real_commit.commit()
    await db_session_real_commit.refresh(plan)

    phone_suffix = uuid4().int % 10**7
    client_obj = Client(
        last_name=f"RefundClient-{uuid4().hex[:6]}",
        first_name="Test",
        phone=f"+7905{phone_suffix:07d}",
        created_by_user_id=owner_id,
    )
    db_session_real_commit.add(client_obj)
    await db_session_real_commit.commit()
    await db_session_real_commit.refresh(client_obj)

    today = datetime.now(tz=UTC).date()
    # Plan above was seeded with validity_days=90 — coerce for mypy strict
    # (the column type is int | None even though we set a concrete int).
    validity_days = plan.validity_days
    assert validity_days is not None
    pt_package = PtPackage(
        client_id=client_obj.id,
        plan_id=plan.id,
        plan_name_snapshot=plan.name,
        session_count_snapshot=plan.session_count,
        price_kopecks_snapshot=plan.price_kopecks,
        validity_days_snapshot=validity_days,
        sessions_remaining=plan.session_count,
        status="active",
        start_date=today,
        end_date=today + timedelta(days=validity_days - 1),
    )
    db_session_real_commit.add(pt_package)
    await db_session_real_commit.commit()
    await db_session_real_commit.refresh(pt_package)
    pt_package_id = pt_package.id

    # Seed ORIGINAL sale payment row directly (bypassing /pt-packages sale flow
    # so we don't need to thread Idempotency-Key + recorder wiring here; the
    # refunder loads original by (subject_kind, subject_id) and the row's
    # presence is the only sale-side precondition).
    sale_payment = Payment(
        subject_kind=SUBJECT_KIND_PT_PACKAGE,
        subject_id=pt_package_id,
        amount_kopecks=plan.price_kopecks,
        method="cash",
        received_by_user_id=owner_id,
        refund_of=None,
    )
    db_session_real_commit.add(sale_payment)
    await db_session_real_commit.commit()
    await db_session_real_commit.refresh(sale_payment)

    # Flush Redis so rate-limit / idempotency keys don't bleed across tests.
    await app.state.redis.flushdb()

    authed = await _build_authed_client(app)
    csrf_token = authed.cookies.get("sportzal_csrf") or ""

    async def _post(idx: int) -> Any:
        # 5 DISTINCT Idempotency-Keys so the race surfaces at the DB layer,
        # NOT at the idempotency replay branch (a single shared key would
        # collapse 4 of the 5 into cached-replay 200s — masking the race).
        return await authed.post(
            f"/api/v1/pt-packages/{pt_package_id}/refund",
            json={"reason": f"race test {idx}"},
            headers={
                "X-CSRF-Token": csrf_token,
                "Idempotency-Key": f"ptpkg-refund-race-{idx}-{uuid4().hex}",
            },
        )

    # 5 parallel POST requests.
    n_concurrent = 5
    responses = await asyncio.gather(*[_post(i) for i in range(n_concurrent)])
    await authed.aclose()

    statuses = sorted(r.status_code for r in responses)
    assert statuses == [200] + [409] * (n_concurrent - 1), (
        f"REF-TEST-02 failed: expected [200] + [409]*{n_concurrent - 1}, got {statuses}"
    )

    bodies_409 = [r.json() for r in responses if r.status_code == 409]
    codes = [b.get("code") for b in bodies_409]
    assert all(c == "already_refunded" for c in codes), (
        f"Unexpected 409 codes (expected all 'already_refunded'): {codes}"
    )

    # DB invariant: exactly 1 refund Payment row (partial UNIQUE
    # uq_payments_refund_of_alive serialised the concurrent INSERTs; losers
    # rolled back BEFORE audit emit).
    refund_count = await db_session_real_commit.scalar(
        select(func.count())
        .select_from(Payment)
        .where(
            Payment.refund_of == sale_payment.id,
            Payment.subject_kind == SUBJECT_KIND_REFUND,
        )
    )
    assert refund_count == 1, f"Expected exactly 1 refund row, got {refund_count}"

    # Audit invariant: exactly 1 pt_package_refunded row + 1 refund_issued row.
    # Losing tasks rollback BEFORE both audit emits (issue_refund rolls back
    # on IntegrityError; orchestrator never reaches its pt_package_refunded
    # emit).
    refunded_audit_count = await db_session_real_commit.scalar(
        select(func.count())
        .select_from(AuditLog)
        .where(
            AuditLog.action == "pt_package_refunded",
            AuditLog.resource_id == pt_package_id,
        )
    )
    assert refunded_audit_count == 1, (
        f"Expected exactly 1 pt_package_refunded audit row, got {refunded_audit_count}"
    )
    refund_issued_count = await db_session_real_commit.scalar(
        select(func.count()).select_from(AuditLog).where(AuditLog.action == "refund_issued")
    )
    assert refund_issued_count == 1, (
        f"Expected exactly 1 refund_issued audit row, got {refund_issued_count}"
    )
