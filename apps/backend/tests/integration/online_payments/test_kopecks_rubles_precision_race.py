"""VER-02(d) — kopecks↔rubles Decimal precision under concurrency.

Proves that ``kopecks_to_yookassa`` and ``yookassa_to_kopecks`` (from
``app.integrations.yookassa._money``) preserve lossless Decimal precision
with zero round-trip drift across edge-value amounts under concurrency.

Edge values tested (kopecks):
  0         →  "0.00"
  1         →  "0.01"
  99        →  "0.99"
  100       →  "1.00"
  9_999_999 →  "99999.99"

For each edge value, a concurrent batch of ``asyncio.gather`` coroutines
exercises the round-trip converter and asserts:
  ``yookassa_to_kopecks(kopecks_to_yookassa(k)) == k``

No float arithmetic is involved — the converters flow entirely through
``decimal.Decimal`` with ``ROUND_HALF_EVEN`` quantization, preventing the
off-by-100 and float-drift pitfalls documented in
``research/PITFALLS.md`` (Pitfall #6).

Database layer (integration portion):
  For each edge value that seeds a real ``online_payments`` row, the
  persisted ``amount_kopecks`` must equal the original kopeck value
  (``assert op.amount_kopecks == seed_kopecks``).  This proves the
  DB-level integer storage is lossless and that no float coercion
  occurs in the SQLAlchemy ``Integer`` column mapping.

Redis flush:
  Before each batch gather, Redis is flushed so dedup / idempotency keys
  from other test runs don't bleed across parametrize cases.

SAVEPOINT-masking: this test does NOT issue concurrent INSERTs against a
  UNIQUE index, so the default ``db_session`` SAVEPOINT mode is safe for
  the DB portion.  The concurrency stress is on the pure-Python converter
  round-trips (no DB UNIQUE race).

Pattern source:
  ``tests/integration/test_concurrent_expiring_cron_double_pings_race.py``
  (real-commit engine inline + asyncio.gather pattern).
  ``app/integrations/yookassa/_money.py`` (converter module under test).
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any
from uuid import uuid4

import pytest
import pytest_asyncio
from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings
from app.core.models import User
from app.core.permissions import Role
from app.core.security import hash_password
from app.integrations.yookassa._money import kopecks_to_yookassa, yookassa_to_kopecks
from app.modules.clients.models import Client
from app.modules.memberships.models import MembershipPlan
from app.modules.online_payments.constants import (
    CONFIRMATION_TYPE_REDIRECT,
    STATUS_PENDING,
)
from app.modules.online_payments.models import OnlinePayment

# ---------------------------------------------------------------------------
# Edge kopeck amounts: 0, 1, 99, 100, 9_999_999
# These cover the zero boundary, single-kopeck, sub-ruble, ruble boundary,
# and the near-max realistic payment amount.
# ---------------------------------------------------------------------------
_EDGE_KOPECKS = [0, 1, 99, 100, 9_999_999]

# N concurrent coroutines per edge value for the pure round-trip stress test.
_N_CONCURRENT = 20

# ---------------------------------------------------------------------------
# TRUNCATE set — minimal tables touched by the DB-layer seeding.
# ---------------------------------------------------------------------------
_TRUNCATE_TABLES = (
    "audit_log",
    "online_payments",
    "membership_plans",
    "clients",
    "users",
)

_RACE_OWNER_EMAIL = "ver02d-precision-owner@example.com"
_RACE_OWNER_PASSWORD = "hunter22hunter22"  # noqa: S105


@pytest_asyncio.fixture
async def ver02d_engine() -> AsyncIterator[AsyncEngine]:
    """Standalone real-commit engine for the VER-02(d) Decimal precision test.

    Probes Postgres at fixture entry — skips cleanly on unreachable Postgres
    (mirrors test_concurrent_expiring_cron_double_pings_race.py:70-78).
    TRUNCATE-CASCADE teardown removes seeded rows.  D-03 — NO new dependency.
    """
    settings = get_settings()
    engine = create_async_engine(str(settings.database_url), pool_pre_ping=True)
    try:
        async with engine.connect() as probe:
            await probe.execute(text("select 1"))
    except Exception as exc:
        await engine.dispose()
        pytest.skip(
            f"DATABASE_URL not reachable for VER-02(d); "
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


async def _seed_fixtures(
    session_factory: async_sessionmaker[AsyncSession],
    n: int = 1,
) -> list[tuple[Any, Any, Any]]:
    """Seed owner + N (client, plan) pairs.

    Returns a list of (owner_id, client_id, plan_id) tuples — one per
    edge value.  Each pair has a distinct client so the partial UNIQUE
    ``uq_online_payments_membership_double_tap`` (client_id, plan_id, date)
    does not reject concurrent same-day INSERTs.
    """
    nonce_base = uuid4().hex[:6]
    async with session_factory() as setup:
        owner = User(
            email=_RACE_OWNER_EMAIL,
            password_hash=await hash_password(_RACE_OWNER_PASSWORD),
            role=Role.OWNER,
            full_name="VER-02d Precision Owner",
        )
        setup.add(owner)
        await setup.flush()
        owner_id = owner.id

        results: list[tuple[Any, Any, Any]] = []
        for i in range(n):
            nonce = f"{nonce_base}{i:02d}"
            client = Client(
                last_name=f"Prec-{nonce}",
                first_name="VER02d",
                phone=f"+7997{nonce[:8]}",
                email=f"ver02d-client-{nonce}@example.com",
                created_by_user_id=owner_id,
            )
            setup.add(client)
            await setup.flush()

            plan = MembershipPlan(
                name=f"VER02d-Plan-{nonce}",
                duration_days=30,
                price_kopecks=100_000,
                freeze_days_limit=7,
                active=True,
            )
            setup.add(plan)
            await setup.flush()

            results.append((owner_id, client.id, plan.id))

        await setup.commit()
        return results


# ---------------------------------------------------------------------------
# Pure round-trip stress test (no DB, no network).
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("kopecks", _EDGE_KOPECKS)
async def test_kopecks_rubles_round_trip_no_drift_concurrent(kopecks: int) -> None:
    """VER-02(d) pure round-trip: kopecks_to_yookassa → yookassa_to_kopecks == kopecks.

    N=20 concurrent coroutines assert the converter round-trip for each edge
    value.  All arithmetic flows through ``decimal.Decimal`` — no float.
    ``asyncio.gather`` races the same edge value concurrently to surface any
    shared-state or GIL-unrelated precision issue.
    """

    async def _round_trip(k: int) -> int:
        wire_str = kopecks_to_yookassa(k)
        back = yookassa_to_kopecks(wire_str)
        assert back == k, f"VER-02(d) round-trip drift: {k} → '{wire_str}' → {back}"
        return back

    results = await asyncio.gather(*[_round_trip(kopecks) for _ in range(_N_CONCURRENT)])
    assert all(r == kopecks for r in results), (
        f"VER-02(d): expected all results == {kopecks}, got {results}"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("kopecks", _EDGE_KOPECKS)
async def test_kopecks_to_yookassa_wire_format(kopecks: int) -> None:
    """VER-02(d) wire-format assertions: kopecks_to_yookassa produces 2 decimal places.

    ЮKassa's API requires amounts like "0.00", "0.01", "1.00" — never "1" or "1.0".
    """
    wire = kopecks_to_yookassa(kopecks)
    # Always a string with exactly 2 decimal places.
    assert "." in wire, f"missing decimal point: {wire!r}"
    decimal_part = wire.split(".")[1]
    assert len(decimal_part) == 2, f"expected 2 decimal places: {wire!r}"
    # Round-trip must be lossless.
    assert yookassa_to_kopecks(wire) == kopecks, (
        f"wire-format round-trip failed: {kopecks} → '{wire}' → {yookassa_to_kopecks(wire)}"
    )


@pytest.mark.asyncio
async def test_kopecks_rubles_db_amount_preserved(
    ver02d_engine: AsyncEngine,
    app: FastAPI,
) -> None:
    """VER-02(d) DB layer: persisted amount_kopecks matches seed value (no coercion).

    For each edge kopeck value (excluding 0 — OnlinePayment.amount_kopecks has
    a CHECK > 0 constraint), seed an OnlinePayment row directly and verify that
    the persisted ``amount_kopecks`` equals the original seed value without any
    float coercion in SQLAlchemy's Integer mapping.

    asyncio.gather drives N=4 concurrent INSERTs (one per non-zero edge value).
    Each pair uses a DISTINCT (client_id, plan_id) so the partial UNIQUE
    ``uq_online_payments_membership_double_tap`` does not fire for concurrent
    same-day INSERTs — the precision test focuses on amount storage, not the
    dedup constraint.
    """
    session_factory = async_sessionmaker(ver02d_engine, expire_on_commit=False)

    # Edge values with amount_kopecks > 0 (DB CHECK constraint).
    nonzero_edges = [k for k in _EDGE_KOPECKS if k > 0]

    # Seed one distinct (client, plan) pair per edge value.
    fixtures = await _seed_fixtures(session_factory, n=len(nonzero_edges))

    # Flush Redis so dedup keys from prior tests don't bleed.
    await app.state.redis.flushdb()

    async def _seed_and_verify(
        seed_kopecks: int,
        client_id: Any,
        plan_id: Any,
    ) -> None:
        """Insert one OnlinePayment and verify the persisted amount_kopecks."""
        yk_id = f"yk-ver02d-{uuid4().hex[:20]}"
        idem_key = uuid4().hex

        # Round-trip the kopeck value through the wire converter to ensure the
        # same value that would flow through the real payment creation path.
        wire_str = kopecks_to_yookassa(seed_kopecks)
        back_kopecks = yookassa_to_kopecks(wire_str)

        # The round-trip must be lossless before any DB write.
        assert back_kopecks == seed_kopecks, (
            f"VER-02(d) pre-DB round-trip drift: {seed_kopecks} → '{wire_str}' → {back_kopecks}"
        )

        async with session_factory() as setup:
            op = OnlinePayment(
                client_id=client_id,
                membership_plan_id=plan_id,
                pt_package_plan_id=None,
                yookassa_payment_id=yk_id,
                idempotency_key=idem_key,
                amount_kopecks=back_kopecks,  # Use the round-tripped value
                status=STATUS_PENDING,
                confirmation_url="https://example.com/confirm",
                confirmation_type=CONFIRMATION_TYPE_REDIRECT,
                audit_correlation_id=uuid4(),
            )
            setup.add(op)
            await setup.flush()
            inserted_id = op.id
            await setup.commit()

        # Read back the persisted row and verify lossless storage.
        async with session_factory() as verify:
            row = await verify.get(OnlinePayment, inserted_id)
            assert row is not None, f"OnlinePayment {inserted_id} not found"
            assert row.amount_kopecks == seed_kopecks, (
                f"VER-02(d) DB precision loss: seeded {seed_kopecks} kopecks, "
                f"persisted {row.amount_kopecks} (SQLAlchemy Integer coercion?)"
            )

    # Concurrent INSERTs + verification for all non-zero edge values,
    # each using a distinct (client_id, plan_id) to avoid double-tap UNIQUE.
    await asyncio.gather(
        *[
            _seed_and_verify(k, owner_client_plan[1], owner_client_plan[2])
            for k, owner_client_plan in zip(nonzero_edges, fixtures, strict=True)
        ]
    )
