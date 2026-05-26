"""VER-02(c) — concurrent refund arbitration: partial UNIQUE uq_payments_refund_of_alive.

Proves the partial UNIQUE index ``uq_payments_refund_of_alive`` on the
``payments`` table is the load-bearing race arbiter for concurrent refund
attempts — NOT any app-layer SELECT-then-guard (TOCTOU).

Race surface:
  N=5 concurrent ``POST /api/v1/memberships/{id}/refund`` requests on the
  SAME succeeded membership.  The orchestrator's status guard performs a
  SELECT-before-INSERT which is a TOCTOU gap: all N requests can pass the
  app-layer check simultaneously.  Only the DB-level partial UNIQUE index
  ``uq_payments_refund_of_alive`` on ``(refund_of) WHERE refund_of IS NOT NULL``
  serialises the race — exactly ONE INSERT wins, the rest raise
  ``IntegrityError`` which ``payments.repository._is_refund_of_uniqueness_conflict``
  discriminates to ``AlreadyRefundedError(code='already_refunded')`` → 409.

REFUND-03 idempotent semantics (webhook path):
  The ``refund.succeeded`` webhook handler (``handle_refund_succeeded``) also
  calls ``_settle_online_refund`` → ``get_payment_refunder()`` which issues the
  same INSERT.  On ``AlreadyRefundedError`` or ``IntegrityError`` the handler
  logs ``yookassa_refund_idempotent_replay`` and returns 200 — the webhook
  returns 200 even when its INSERT is rejected by the constraint.  This test
  asserts exactly ONE surviving ``payments.refund_of`` row — the same
  guarantee holds regardless of which path arrived first.

Constraint name reference: ``uq_payments_refund_of_alive``
  See: ``app/modules/payments/models.py:113`` (partial UNIQUE definition)
       ``app/modules/payments/repository.py:53-62`` (discriminator)
       ``app/modules/payments/service.py:58-67`` (AlreadyRefundedError)

SAVEPOINT-masking rationale (MUST read before modifying this test):
  The default ``db_session`` fixture wraps each test in a SAVEPOINT.  Concurrent
  INSERTs racing against the UNIQUE index inside one outer SAVEPOINT are masked —
  the loser's ``IntegrityError`` is swallowed by the SAVEPOINT rollback and the
  second SELECT-FOR-UPDATE re-reads the already-committed winner row, making the
  race invisible.  Real-commit sessions are mandatory.  D-03 — NO new
  pytest-postgresql / testcontainers dependency.

Pattern source: ``tests/integration/payments/test_payments_refund_race.py``
(real-commit rationale :1-14, ``_build_authed_client`` :42-54,
asyncio.gather body + status/DB asserts :139-205).
Mirrors ``tests/integration/memberships/test_freeze_race.py`` with
constraint name + endpoint swapped.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    async_sessionmaker,
    create_async_engine,
)

from app.core.audit_models import AuditLog
from app.core.config import get_settings
from app.core.models import User
from app.core.permissions import Role
from app.core.security import hash_password
from app.modules.clients.models import Client
from app.modules.memberships.models import Membership, MembershipPlan
from app.modules.payments.constants import SUBJECT_KIND_MEMBERSHIP, SUBJECT_KIND_REFUND
from app.modules.payments.models import Payment

# ---------------------------------------------------------------------------
# VER-02(c) TRUNCATE set — tables seeded + touched by the cash refund UoW.
# CASCADE handles the FK chain.
# ---------------------------------------------------------------------------
_TRUNCATE_TABLES = (
    "audit_log",
    "payments",
    "memberships",
    "membership_freeze_periods",
    "membership_plans",
    "clients",
    "users",
)

_RACE_OWNER_EMAIL = "ver02c-refund-race-owner@example.com"
_RACE_OWNER_PASSWORD = "hunter22hunter22"  # noqa: S105


@pytest_asyncio.fixture
async def ver02c_engine() -> AsyncIterator[AsyncEngine]:
    """Standalone real-commit engine for the VER-02(c) refund arbitration race.

    Probes Postgres at fixture entry — skips cleanly on unreachable Postgres
    (mirrors test_concurrent_expiring_cron_double_pings_race.py:70-78).
    TRUNCATE-CASCADE teardown removes the seeded rows so subsequent tests
    are unaffected.  D-03 — NO new dependency (no pytest-postgresql /
    testcontainers).
    """
    settings = get_settings()
    engine = create_async_engine(str(settings.database_url), pool_pre_ping=True)
    try:
        async with engine.connect() as probe:
            await probe.execute(text("select 1"))
    except Exception as exc:
        await engine.dispose()
        pytest.skip(
            f"DATABASE_URL not reachable for VER-02(c); "
            f"run `docker compose up postgres` first ({exc!r})"
        )
    try:
        yield engine
    finally:
        async with engine.begin() as conn:
            await conn.execute(
                text(f"TRUNCATE {', '.join(_TRUNCATE_TABLES)} RESTART IDENTITY CASCADE")
            )
        await engine.dispose()


async def _build_authed_client(app: FastAPI) -> AsyncClient:
    """Build and authenticate an owner client (mirrors test_payments_refund_race.py:42-54)."""
    transport = ASGITransport(app=app)
    client = AsyncClient(transport=transport, base_url="http://testserver")
    r = await client.post(
        "/api/v1/auth/login",
        json={
            "email": _RACE_OWNER_EMAIL,
            "password": _RACE_OWNER_PASSWORD,
        },
    )
    assert r.status_code == 200, f"VER-02(c) login failed: {r.text}"
    return client


@pytest.mark.asyncio
async def test_concurrent_refund_loses_at_db_layer_uq_payments_refund_of_alive(
    ver02c_engine: AsyncEngine,
    app: FastAPI,
) -> None:
    """VER-02(c): N=5 parallel POST /memberships/{id}/refund → uq_payments_refund_of_alive.

    Expected outcome: exactly 1x200 + 4x409 already_refunded.

    The partial UNIQUE index ``uq_payments_refund_of_alive`` on
    ``payments(refund_of) WHERE refund_of IS NOT NULL`` is the race arbiter.
    App-layer status guards (SELECT-before-INSERT) are TOCTOU — all N requests
    can pass them simultaneously.  Only the DB constraint serialises the race.

    ``payments.repository._is_refund_of_uniqueness_conflict`` discriminates the
    ``IntegrityError`` to ``AlreadyRefundedError(code='already_refunded')``
    which maps to 409.  The webhook's ``handle_refund_succeeded`` handler
    converts the same ``AlreadyRefundedError`` to a 200 replay response (REFUND-03).

    Exactly ONE ``payments`` refund row survives; audit chain emits exactly ONE
    ``membership_refunded`` event.
    """
    session_factory = async_sessionmaker(ver02c_engine, expire_on_commit=False)

    # ── Seed: owner + client + plan + active membership + ORIGINAL sale payment ──
    hashed = await hash_password(_RACE_OWNER_PASSWORD)
    today = datetime.now(tz=UTC).date()

    async with session_factory() as setup:
        owner = User(
            email=_RACE_OWNER_EMAIL,
            password_hash=hashed,
            role=Role.OWNER,
            full_name="VER-02c Refund Race Owner",
        )
        setup.add(owner)
        await setup.flush()
        owner_id = owner.id

        plan = MembershipPlan(
            name=f"VER02c-Plan-{uuid4().hex[:6]}",
            duration_days=30,
            price_kopecks=250_000,
            freeze_days_limit=14,
            active=True,
        )
        setup.add(plan)
        await setup.flush()

        phone_suffix = uuid4().int % 10**7
        client_obj = Client(
            last_name=f"RefundRace-{uuid4().hex[:6]}",
            first_name="VER02c",
            phone=f"+7905{phone_suffix:07d}",
            created_by_user_id=owner_id,
        )
        setup.add(client_obj)
        await setup.flush()

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
        setup.add(membership)
        await setup.flush()
        membership_id = membership.id

        # Seed the ORIGINAL sale payment directly (bypass /memberships sell flow
        # so we don't need Idempotency-Key + recorder wiring here).
        sale_payment = Payment(
            subject_kind=SUBJECT_KIND_MEMBERSHIP,
            subject_id=membership_id,
            amount_kopecks=plan.price_kopecks,
            method="cash",
            received_by_user_id=owner_id,
            refund_of=None,
        )
        setup.add(sale_payment)
        await setup.flush()
        sale_payment_id = sale_payment.id
        await setup.commit()

    # Flush Redis so rate-limit / idempotency keys don't bleed across tests.
    await app.state.redis.flushdb()

    authed = await _build_authed_client(app)
    csrf_token = authed.cookies.get("sportzal_csrf") or ""
    headers = {"X-CSRF-Token": csrf_token}

    n_concurrent = 5

    async def _post(idx: int) -> Any:
        return await authed.post(
            f"/api/v1/memberships/{membership_id}/refund",
            json={"reason": f"ver02c race test {idx}"},
            headers=headers,
        )

    # N=5 parallel POST /refund requests (idx differentiates reasons;
    # uq_payments_refund_of_alive ignores the reason column).
    responses = await asyncio.gather(*[_post(i) for i in range(n_concurrent)])
    await authed.aclose()

    statuses = sorted(r.status_code for r in responses)
    assert statuses == [200] + [409] * (n_concurrent - 1), (
        f"VER-02(c): expected [200] + [409]*{n_concurrent - 1}, got {statuses}. "
        f"uq_payments_refund_of_alive must serialize concurrent refund INSERTs."
    )

    # All 409 responses must carry the 'already_refunded' code —
    # _is_refund_of_uniqueness_conflict discriminated the IntegrityError.
    bodies_409 = [r.json() for r in responses if r.status_code == 409]
    codes = [b.get("code") for b in bodies_409]
    assert all(c == "already_refunded" for c in codes), (
        f"VER-02(c): unexpected 409 codes (expected all 'already_refunded'): {codes}"
    )

    # ── DB invariant: exactly ONE refund Payment row ──────────────────────────
    # The partial UNIQUE uq_payments_refund_of_alive serialised the concurrent
    # INSERTs.  Race losers rolled back BEFORE audit emit.
    async with session_factory() as verify:
        refund_count = await verify.scalar(
            select(func.count())
            .select_from(Payment)
            .where(
                Payment.refund_of == sale_payment_id,
                Payment.subject_kind == SUBJECT_KIND_REFUND,
            )
        )
        assert refund_count == 1, (
            f"VER-02(c): expected exactly 1 refund row (uq_payments_refund_of_alive "
            f"is the arbiter), got {refund_count}"
        )

        # Audit invariant: exactly 1 membership_refunded row + 1 refund_issued row.
        refunded_audit_count = await verify.scalar(
            select(func.count())
            .select_from(AuditLog)
            .where(
                AuditLog.action == "membership_refunded",
                AuditLog.resource_id == membership_id,
            )
        )
        assert refunded_audit_count == 1, (
            f"VER-02(c): expected exactly 1 membership_refunded audit row, "
            f"got {refunded_audit_count}"
        )

        refund_issued_count = await verify.scalar(
            select(func.count()).select_from(AuditLog).where(AuditLog.action == "refund_issued")
        )
        assert refund_issued_count == 1, (
            f"VER-02(c): expected exactly 1 refund_issued audit row, got {refund_issued_count}"
        )
