"""Shared fixtures for payroll integration tests (Phase 58 PAY-01..06).

Re-exports the standard authed-client + DB-factory fixtures from memberships/
conftest, then adds payroll-specific factories:
  - ``make_comp_config`` — INSERT a TrainerCompConfig row directly via the
    SAVEPOINT-mode session (avoids the HTTP round-trip + audit row emission
    for tests that only need the config to exist as a seed).
  - ``make_accrual`` — INSERT a TrainerPayrollAccrual row directly; used by
    PAY-03..06 tests that need to seed a completed accrual.

The payroll conftest defines its own ``_client_app_overrides`` fixture that
additionally mounts the payroll router under /api/v1/payroll/. The
memberships-originated ``authed_client_owner`` / ``authed_client_reception``
fixtures resolve ``_client_app_overrides`` by name from the test's conftest
scope — pytest fixture shadowing ensures they pick up the local override
instead of the memberships one.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import date
from uuid import UUID, uuid4

import pytest_asyncio
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.redis import get_redis
from app.modules.payroll.models import TrainerCompConfig, TrainerPayrollAccrual
from app.modules.payroll.router import router as payroll_router
from app.modules.trainers.models import Trainer

# ---------------------------------------------------------------------------
# Re-export memberships fixtures so they are visible to payroll tests.
# pytest discovers fixtures via conftest.py; importing them here makes them
# available without explicit re-declaration. Using "name as name" idiom so
# ruff treats them as public re-exports (PEP 484 explicit re-export).
# ---------------------------------------------------------------------------
from tests.integration.memberships.conftest import (
    authed_client_owner as authed_client_owner,  # re-export
)
from tests.integration.memberships.conftest import (
    authed_client_reception as authed_client_reception,  # re-export
)
from tests.integration.memberships.conftest import (
    db_session_real_commit as db_session_real_commit,  # re-export
)
from tests.integration.memberships.conftest import (
    make_client as make_client,  # re-export
)
from tests.integration.memberships.conftest import (
    make_plan as make_plan,  # re-export
)
from tests.integration.memberships.conftest import (
    make_user as make_user,  # re-export
)
from tests.integration.memberships.conftest import (
    redis_clean as redis_clean,  # re-export
)
from tests.integration.memberships.conftest import (
    seeded_owner as seeded_owner,  # re-export
)
from tests.integration.memberships.conftest import (
    seeded_reception as seeded_reception,  # re-export
)


@pytest_asyncio.fixture
async def _client_app_overrides(
    app: FastAPI,
    db_session: AsyncSession,
) -> AsyncIterator[FastAPI]:
    """Install dependency overrides + mount payroll router under /api/v1/payroll/.

    Shadows the memberships ``_client_app_overrides`` for payroll tests:
      1. Override ``get_db`` → SAVEPOINT-wrapped session (D-22 TEST-01).
      2. Override ``get_redis`` → app.state.redis (rate-limit / session keys).
      3. Mount payroll router under /api/v1/payroll/ (production mounting is
         deferred to Plan 58-10; tests self-mount to exercise endpoints now).

    ``authed_client_owner`` / ``authed_client_reception`` (re-exported from
    memberships) resolve ``_client_app_overrides`` by name from this conftest —
    pytest fixture shadowing ensures they pick up this override instead of the
    memberships one.
    """

    async def _override_get_db() -> AsyncIterator[AsyncSession]:
        yield db_session

    def _override_get_redis() -> object:
        return app.state.redis

    # Mount payroll router if not already present (idempotent guard for
    # test-session reuse — the `app` fixture is function-scoped so this
    # usually fires once per test, but the guard is cheap and explicit).
    existing_paths = {r.path for r in app.routes}  # type: ignore[attr-defined]
    if "/api/v1/payroll/trainer-configs/{trainer_id}" not in existing_paths:
        app.include_router(payroll_router, prefix="/api/v1/payroll", tags=["payroll"])

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_redis] = _override_get_redis
    try:
        yield app
    finally:
        app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def make_trainer(
    db_session: AsyncSession,
) -> Callable[..., Awaitable[Trainer]]:
    """Seed a Trainer row directly via the SAVEPOINT-mode session.

    Mirrors tests/integration/pt_sessions/conftest.py:make_trainer.
    Phase 31 D-31-01 — Trainer has no created_by_user_id FK.
    """
    _counter: dict[str, int] = {"i": 0}

    async def _make(
        *,
        full_name: str | None = None,
        is_active: bool = True,
        phone: str | None = None,
    ) -> Trainer:
        _counter["i"] += 1
        resolved_name = full_name or f"Тренер-{_counter['i']}-{uuid4().hex[:4]}"
        trainer = Trainer(
            full_name=resolved_name,
            is_active=is_active,
            phone=phone,
        )
        db_session.add(trainer)
        await db_session.commit()
        await db_session.refresh(trainer)
        return trainer

    return _make


@pytest_asyncio.fixture
async def make_comp_config(
    db_session: AsyncSession,
) -> Callable[..., Awaitable[TrainerCompConfig]]:
    """INSERT a TrainerCompConfig row directly via the SAVEPOINT-mode session.

    Avoids the PUT endpoint round-trip + audit row emission for tests that
    only need the config to exist as a seed row. Uses SAVEPOINT-rolled session
    so teardown wipes the insert regardless.

    Args:
        trainer_id: FK to trainers.id (required).
        commission_pct_bps: 0..10000 or None.
        session_fee_kopecks: >= 0 or None.
        effective_from: date; defaults to 2026-01-01.
        created_by_user_id: optional FK to users.id.
    """

    async def _make(
        *,
        trainer_id: UUID,
        commission_pct_bps: int | None = None,
        session_fee_kopecks: int | None = None,
        effective_from: date = date(2026, 1, 1),
        created_by_user_id: UUID | None = None,
    ) -> TrainerCompConfig:
        config = TrainerCompConfig(
            trainer_id=trainer_id,
            commission_pct_bps=commission_pct_bps,
            session_fee_kopecks=session_fee_kopecks,
            effective_from=effective_from,
            created_by_user_id=created_by_user_id,
        )
        db_session.add(config)
        await db_session.commit()
        await db_session.refresh(config)
        return config

    return _make


@pytest_asyncio.fixture
async def make_accrual(
    db_session: AsyncSession,
) -> Callable[..., Awaitable[TrainerPayrollAccrual]]:
    """INSERT a TrainerPayrollAccrual row directly via the SAVEPOINT-mode session.

    Seed factory for PAY-03..06 tests. Snapshot columns are required at insert
    time (mirrors the service-layer obligation per D-58-03). Clawback fields
    default to None (regular accrual).

    Required kwargs: trainer_id, period_start, period_end, sessions_count,
        revenue_kopecks, comp_config_id_snapshot, accrual_kopecks.
    Optional kwargs: status (default 'pending'), commission_pct_bps_snapshot,
        session_fee_kopecks_snapshot, clawback_of_accrual_id,
        source_refund_payment_id.
    """

    async def _make(
        *,
        trainer_id: UUID,
        period_start: date,
        period_end: date,
        sessions_count: int,
        revenue_kopecks: int,
        comp_config_id_snapshot: UUID,
        accrual_kopecks: int,
        status: str = "pending",
        commission_pct_bps_snapshot: int | None = None,
        session_fee_kopecks_snapshot: int | None = None,
        clawback_of_accrual_id: UUID | None = None,
        source_refund_payment_id: UUID | None = None,
    ) -> TrainerPayrollAccrual:
        accrual = TrainerPayrollAccrual(
            trainer_id=trainer_id,
            period_start=period_start,
            period_end=period_end,
            sessions_count=sessions_count,
            revenue_kopecks=revenue_kopecks,
            comp_config_id_snapshot=comp_config_id_snapshot,
            accrual_kopecks=accrual_kopecks,
            status=status,
            commission_pct_bps_snapshot=commission_pct_bps_snapshot,
            session_fee_kopecks_snapshot=session_fee_kopecks_snapshot,
            clawback_of_accrual_id=clawback_of_accrual_id,
            source_refund_payment_id=source_refund_payment_id,
        )
        db_session.add(accrual)
        await db_session.commit()
        await db_session.refresh(accrual)
        return accrual

    return _make
