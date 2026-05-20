"""Fixtures for ARQ scheduled-worker integration tests (Phase 18 CD-05).

Phase 18 W-2 SAVEPOINT auto-restart note:
This conftest relies on the outer `db_session` fixture (apps/backend/tests/
conftest.py:101) using `async_sessionmaker(..., join_transaction_mode=
'create_savepoint')` — SQLAlchemy 2.0's built-in equivalent of the older
`event.listen(session, 'after_transaction_end', restart_savepoint)` hook.
Both shapes guarantee that each worker call's `session.commit()` releases a
SAVEPOINT cleanly and the NEXT operation auto-begins a fresh nested
transaction. If a future regression removes `join_transaction_mode=
'create_savepoint'` from the outer conftest WITHOUT replacing it with the
event-listener hook, the second worker call in
`test_expire_memberships_idempotent.py` will raise InvalidRequestError /
PendingRollbackError. In that scenario, switch `_SessionContext.__aenter__`
to issue `await session.begin_nested()` before yielding the session, so each
worker call gets a fresh SAVEPOINT explicitly.

Provides:
  - `seeded_user` — a single owner User row (committed via SAVEPOINT) used as
    the FK target for `clients.created_by_user_id` (NOT NULL FK).
  - `seeded_plan` — a single MembershipPlan row (committed via SAVEPOINT) the
    fixture functions reuse for all memberships in a test.
  - `seeded_client` — a single Client row (committed via SAVEPOINT) used as
    the FK target for memberships. Memberships have `client_id NOT NULL FK
    clients.id ON DELETE RESTRICT`.
  - `make_membership_with_dates(end_date=...)` — extension of the Phase 17
    `make_membership` factory that defaults the FK references to the
    seeded plan + client and lets the test pass an explicit `end_date`
    without recomputing snapshot fields.
  - `worker_ctx` — a hand-crafted ARQ ctx dict that wraps the SAVEPOINT-mode
    `db_session` so the worker entry's `async with session_factory() as session`
    yields the SAME session the test queries directly. Without this aliasing,
    the worker would open a fresh sessionmaker that doesn't see the test's
    seeded data (Postgres READ COMMITTED at separate connections).

Note on `seeded_client` vs the Plan 18-05 stub spec: the plan template used
`Client(full_name=..., phone=...)` but the canonical `Client` ORM model
(apps/backend/app/modules/clients/models.py) has `last_name`/`first_name`
NOT NULL columns and a NOT NULL `created_by_user_id` FK to `users.id`. The
fixture below seeds the actual schema (last_name + first_name + phone +
created_by_user_id). This is a Rule 3 fix — the plan's literal content was
infeasible against the live schema, so the conftest seeds what the DB
requires. The W-2 SAVEPOINT contract is unchanged.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import Role
from app.core.security import hash_password
from app.modules.auth.models import User
from app.modules.clients.models import Client
from app.modules.memberships.models import Membership, MembershipPlan


@pytest.fixture(autouse=True)
def _reset_worker_logger_cache() -> None:
    """Invalidate the module-level structlog logger cache in `expire_memberships`.

    Phase 18 W-3 — `app.core.logging.configure_logging` runs `structlog.configure(
    processors=[...], cache_logger_on_first_use=True)` from `create_app()`, which
    is fired by the `app` fixture (tests/conftest.py:app). Each test gets a
    fresh `processors=[...]` list, but the module-level
    `_log = structlog.get_logger('workers.scheduled.expire_memberships')` in
    `app/workers/scheduled/expire_memberships.py` caches its
    BoundLogger (with the FIRST test's processor list ref) on first call.
    When `structlog.testing.capture_logs()` mutates the CURRENT config's
    processor list, the cached logger still points at the previous list,
    so capture_logs misses the call.

    Fix: delete the cached `bind` attribute on the module-level proxy
    before each test. The proxy's BoundLoggerLazyProxy.__getattr__ then
    re-resolves processors from the current `_CONFIG.default_processors`
    on the next call — which is the list `capture_logs` mutates.
    """
    from app.workers.scheduled import (
        cleanup_password_reset_tokens as cleanup_mod,
    )
    from app.workers.scheduled import expire_memberships as worker_mod

    # `bind` is the cached attribute set by BoundLoggerLazyProxy's first call
    # under `cache_logger_on_first_use=True`. Removing it forces re-resolution.
    for mod in (worker_mod, cleanup_mod):
        if "bind" in mod._log.__dict__:
            del mod._log.__dict__["bind"]


@pytest_asyncio.fixture
async def seeded_user(db_session: AsyncSession) -> User:
    """An owner User row committed via SAVEPOINT (rolled back at teardown).

    Required because `clients.created_by_user_id` is a NOT NULL FK to
    `users.id` ON DELETE RESTRICT — the worker test fixture can't insert a
    Client row without a real user behind it.
    """
    user = User(
        email="arq-test-user@example.com",
        password_hash=await hash_password("hunter22hunter22"),
        role=Role.OWNER,
        full_name="ARQ Test User",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def seeded_plan(db_session: AsyncSession) -> MembershipPlan:
    """A single 30-day plan committed via SAVEPOINT (rolled back at teardown)."""
    plan = MembershipPlan(
        name="ARQ Test Plan",
        duration_days=30,
        price_kopecks=250000,
        freeze_days_limit=14,
        active=True,
    )
    db_session.add(plan)
    await db_session.commit()
    await db_session.refresh(plan)
    return plan


@pytest_asyncio.fixture
async def seeded_client(
    db_session: AsyncSession,
    seeded_user: User,
) -> Client:
    """A single Client row committed via SAVEPOINT (rolled back at teardown).

    Phase 18 worker tests insert memberships referencing this client; the
    `clients.id ON DELETE RESTRICT` FK requires a real client row, and the
    `clients.created_by_user_id` NOT NULL FK requires the `seeded_user`.
    """
    client = Client(
        last_name="Тестовый",
        first_name="Клиент",
        phone="+79990000001",
        created_by_user_id=seeded_user.id,
    )
    db_session.add(client)
    await db_session.commit()
    await db_session.refresh(client)
    return client


@pytest_asyncio.fixture
async def make_membership_with_dates(
    db_session: AsyncSession,
    seeded_plan: MembershipPlan,
    seeded_client: Client,
) -> Callable[..., Awaitable[Membership]]:
    """Insert a Membership row with explicit `end_date` (defaults to seeded plan + client).

    Used by worker tests to seed today-1 / today / today+1 rows in a single
    test without repeating boilerplate. Snapshot fields are copied from the
    seeded plan so the row is shape-identical to what `service.create_membership`
    would write.
    """

    async def _make(
        *,
        end_date: date,
        status: str = "active",
        client: Client | None = None,
        start_date: date | None = None,
    ) -> Membership:
        c = client or seeded_client
        today = start_date or datetime.now(tz=UTC).date()
        # If end_date is in the past, ensure start_date precedes it.
        if start_date is None and end_date < today:
            today = end_date - timedelta(days=1)
        membership = Membership(
            client_id=c.id,
            plan_id=seeded_plan.id,
            plan_name_snapshot=seeded_plan.name,
            duration_days_snapshot=seeded_plan.duration_days,
            price_kopecks_snapshot=seeded_plan.price_kopecks,
        freeze_days_limit_snapshot=seeded_plan.freeze_days_limit,
            start_date=today,
            end_date=end_date,
            status=status,
        )
        db_session.add(membership)
        await db_session.commit()
        await db_session.refresh(membership)
        return membership

    return _make


@pytest_asyncio.fixture
async def worker_ctx(
    db_session: AsyncSession,
) -> AsyncIterator[dict[str, Any]]:
    """Hand-crafted ARQ ctx whose `sessionmaker` yields the SAVEPOINT-mode db_session.

    The worker entry calls `async with ctx["sessionmaker"]() as session: ...`.
    For tests, we want that block to yield the SAME `db_session` the test
    seeds against — otherwise the route's view of the data is via a different
    connection and READ COMMITTED isolation hides the seed. The
    `_SavepointSessionmaker` wrapper exposes a callable that returns an async
    context manager yielding `db_session` (and swallows exit/aexit so the
    fixture teardown owns rollback).

    SAVEPOINT auto-restart relies on the outer `db_session` fixture's
    `join_transaction_mode='create_savepoint'` — see the module docstring
    note above for the fallback if that mode is ever removed.

    Also pre-populates `ctx["job_id"]` and `ctx["function_name"]` to mimic
    what ARQ would set in production — the contextvars hooks (Plan 18-03)
    bind these.
    """

    class _SessionContext:
        def __init__(self, session: AsyncSession) -> None:
            self._session = session

        async def __aenter__(self) -> AsyncSession:
            return self._session

        async def __aexit__(self, *args: Any) -> None:
            # Teardown belongs to the outer fixture (db_session rolls back the
            # SAVEPOINT at end of test). Do NOT close the session here.
            return None

    class _SavepointSessionmaker:
        def __call__(self) -> _SessionContext:
            return _SessionContext(db_session)

    yield {
        "sessionmaker": _SavepointSessionmaker(),
        "job_id": "test-job-00000000-0000-0000-0000-000000000001",
        "function_name": "expire_memberships",
    }
