"""Integration tests for the ARQ expire_pt_packages cron (Phase 33 PT-12 / D-33-13).

Direct calls to the service helper ``_expire_due_pt_packages(session, today=)``
against the SAVEPOINT-rolled ``db_session``. Mirrors
tests/integration/workers/test_expire_memberships.py shape but exercises
the new PT-package surface.

Coverage:
  1. 3-row fixture: overdue-active → expired (+ audit emit); future-active
     untouched; NULL-end-date untouched (D-33-14 contract).
  2. Idempotent re-run: 2nd call returns 0 — WHERE status='active' guard
     skips already-expired rows.
  3. NULL-end-date with today=9999-12-31 never expires (D-33-14).
  4. Worker e2e: expire_pt_packages(ctx) invokes the helper, commits,
     emits 'expire_pt_packages_complete' structlog summary AFTER commit.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest_asyncio
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit_models import AuditLog
from app.modules.clients.models import Client
from app.modules.pt_packages import service as pt_packages_service
from app.modules.pt_packages.models import PtPackage, PtPackagePlan
from app.workers.scheduled.expire_pt_packages import expire_pt_packages


@pytest_asyncio.fixture(autouse=True)
async def _reset_pt_packages_worker_logger_cache() -> AsyncIterator[None]:
    """Invalidate the module-level structlog cache for expire_pt_packages.

    Mirrors `_reset_worker_logger_cache` in
    tests/integration/workers/conftest.py — without this reset,
    `structlog.testing.capture_logs()` misses the worker's INFO line
    because the BoundLoggerLazyProxy caches its first-call processor list.
    """
    from app.workers.scheduled import expire_pt_packages as worker_mod

    if "bind" in worker_mod._log.__dict__:
        del worker_mod._log.__dict__["bind"]
    yield


async def test_expire_pt_packages_cron_3_row_fixture(
    db_session: AsyncSession,
    make_client: Callable[..., Awaitable[Client]],
    make_pt_package_plan: Callable[..., Awaitable[PtPackagePlan]],
    make_pt_package: Callable[..., Awaitable[PtPackage]],
) -> None:
    """3-row fixture: overdue/future/NULL — only overdue flips to expired."""
    plan = await make_pt_package_plan(name="cron-3row")
    today = datetime.now(tz=UTC).date()
    c_overdue = await make_client(phone="+79991010001")
    c_future = await make_client(phone="+79991010002")
    c_indef = await make_client(phone="+79991010003")

    overdue = await make_pt_package(
        client_id=c_overdue.id,
        plan=plan,
        start_date=today - timedelta(days=10),
        end_date=today - timedelta(days=2),
    )
    future = await make_pt_package(
        client_id=c_future.id,
        plan=plan,
        start_date=today,
        end_date=today + timedelta(days=5),
    )
    indef = await make_pt_package(
        client_id=c_indef.id,
        plan=plan,
        start_date=today,
        end_date=None,
    )

    count = await pt_packages_service._expire_due_pt_packages(
        db_session, today=today
    )
    await db_session.commit()
    assert count == 1, f"expected 1 flipped row, got {count}"

    await db_session.refresh(overdue)
    await db_session.refresh(future)
    await db_session.refresh(indef)
    assert overdue.status == "expired"
    assert future.status == "active"
    assert indef.status == "active"

    audit_rows = (
        await db_session.scalars(
            select(AuditLog).where(
                AuditLog.action == "pt_package_expired",
                AuditLog.resource_id == overdue.id,
            )
        )
    ).all()
    assert len(audit_rows) == 1
    payload = audit_rows[0].payload
    assert set(payload.keys()) == {"pt_package_id", "client_id", "end_date"}
    assert payload["pt_package_id"] == str(overdue.id)
    assert payload["client_id"] == str(c_overdue.id)
    assert payload["end_date"] == (today - timedelta(days=2)).isoformat()


async def test_expire_pt_packages_cron_idempotent_rerun(
    db_session: AsyncSession,
    make_client: Callable[..., Awaitable[Client]],
    make_pt_package_plan: Callable[..., Awaitable[PtPackagePlan]],
    make_pt_package: Callable[..., Awaitable[PtPackage]],
) -> None:
    """2nd call returns 0: WHERE status='active' guard makes re-run a no-op."""
    plan = await make_pt_package_plan(name="cron-idem")
    today = datetime.now(tz=UTC).date()
    c = await make_client(phone="+79991020001")
    await make_pt_package(
        client_id=c.id,
        plan=plan,
        start_date=today - timedelta(days=10),
        end_date=today - timedelta(days=1),
    )

    n1 = await pt_packages_service._expire_due_pt_packages(db_session, today=today)
    await db_session.commit()
    n2 = await pt_packages_service._expire_due_pt_packages(db_session, today=today)
    await db_session.commit()
    assert n1 == 1
    assert n2 == 0


async def test_expire_pt_packages_cron_null_end_date_never_expires(
    db_session: AsyncSession,
    make_client: Callable[..., Awaitable[Client]],
    make_pt_package_plan: Callable[..., Awaitable[PtPackagePlan]],
    make_pt_package: Callable[..., Awaitable[PtPackage]],
) -> None:
    """D-33-14: NULL end_date — even today=9999-12-31 leaves status='active'."""
    plan = await make_pt_package_plan(name="cron-indef", validity_days=None)
    today = datetime.now(tz=UTC).date()
    c = await make_client(phone="+79991030001")
    pkg = await make_pt_package(
        client_id=c.id,
        plan=plan,
        start_date=today,
        end_date=None,
    )

    far_future = date(9999, 12, 31)
    count = await pt_packages_service._expire_due_pt_packages(
        db_session, today=far_future
    )
    await db_session.commit()
    assert count == 0

    await db_session.refresh(pkg)
    assert pkg.status == "active"


async def test_expire_pt_packages_worker_e2e_summary_log(
    db_session: AsyncSession,
    make_client: Callable[..., Awaitable[Client]],
    make_pt_package_plan: Callable[..., Awaitable[PtPackagePlan]],
    make_pt_package: Callable[..., Awaitable[PtPackage]],
) -> None:
    """Worker invocation emits 'expire_pt_packages_complete' AFTER commit."""
    plan = await make_pt_package_plan(name="cron-worker-e2e")
    today = datetime.now(tz=UTC).date()
    c = await make_client(phone="+79991040001")
    overdue = await make_pt_package(
        client_id=c.id,
        plan=plan,
        start_date=today - timedelta(days=10),
        end_date=today - timedelta(days=1),
    )

    # ctx with a sessionmaker that yields the SAVEPOINT-rolled db_session.
    class _SessionContext:
        async def __aenter__(self) -> AsyncSession:
            return db_session

        async def __aexit__(self, *args: Any) -> None:
            return None

    class _Sessionmaker:
        def __call__(self) -> _SessionContext:
            return _SessionContext()

    ctx: dict[str, Any] = {
        "sessionmaker": _Sessionmaker(),
        "job_id": "test-pt-cron-0001",
        "function_name": "expire_pt_packages",
    }

    with structlog.testing.capture_logs() as captured:
        count = await expire_pt_packages(ctx)

    assert count == 1
    completion = [
        e for e in captured if e.get("event") == "expire_pt_packages_complete"
    ]
    assert len(completion) == 1
    assert completion[0].get("count") == 1

    await db_session.refresh(overdue)
    assert overdue.status == "expired"
