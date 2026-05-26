"""DEFER-46-03 closure — FISCAL-05 circuit-breaker open-state parity re-run (Phase 53 VER-05).

v1.6 milestone-verification (Phase 46) could only record VER-09 scenario-08
(cron-chain circuit-breaker open-state) as PARTIAL because the breaker pattern
was not yet reused in a fiscal dispatch path at that time.

Phase 53 D-05 (parity decision): now that FISCAL-05 reuses the same
circuit-breaker primitive (app/integrations/yookassa/circuit_breaker.py) via
dispatch_fiscal_receipt, this test re-runs the scenario-08 open-state fixture
against the FISCAL-05 breaker (key ``cc:yookassa:circuit:receipts``) and
confirms parity with the v1.6 expectation: the open breaker short-circuits
dispatch BEFORE any ЮKassa /receipts POST, and the seeded fiscal_receipt row
remains in its pre-dispatch status (never transitions to 'succeeded').

Parity claim: the open-state short-circuit behaviour confirmed here is
byte-identical to the unit-level assertion in
tests/unit/test_yookassa_circuit_breaker.py::test_record_failure_opens_circuit_at_threshold
and the in-task assertion in
tests/integration/fiscal_receipts/test_dispatch_fiscal_receipt.py::test_dispatch_fiscal_receipt_short_circuits_when_breaker_open
— the v1.6 PARTIAL is now resolved because we can tie the fiscal dispatch path
explicitly to the same breaker primitive exercised by the cron-chain scenarios.

VER-05 acceptance:
- Breaker pre-opened via 5 ``record_failure(redis, 'receipts')`` calls.
- ``dispatch_fiscal_receipt`` raises ``arq.Retry(defer=300)`` (short-circuit).
- No ЮKassa ``/v3/receipts`` POST is issued.
- Seeded ``fiscal_receipts`` row remains ``pending`` (status unchanged).
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest
import respx
from arq import Retry
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.integrations.yookassa.circuit_breaker import record_failure
from app.modules.fiscal_receipts.models import FiscalReceipt
from app.modules.fiscal_receipts.tasks import dispatch_fiscal_receipt
from app.modules.payments.models import Payment

pytestmark = pytest.mark.asyncio

# DEFER-46-03 / D-51-14 locked values (mirror circuit_breaker.py constants).
_OPEN_MARKER_KEY: str = "cc:yookassa:circuit:receipts"
_WINDOW_KEY: str = "cc:yookassa:circuit_window:receipts"
_FAILURE_THRESHOLD: int = 5
_OPEN_DEFER_SECONDS: int = 300  # Retry(defer=300) on short-circuit


async def _seed_pending_fiscal_receipt(
    session: AsyncSession,
) -> FiscalReceipt:
    """Seed a minimal FiscalReceipt(status='pending') row for the parity test.

    Uses the same minimal-chain pattern as
    test_e2e_fiscal_receipt_monitor_stale_cron_catches_pending_row: seed a
    Payment row (no online chain needed) then a FiscalReceipt(status='pending').
    The 'pending' status is intentional — it is the pre-dispatch status that
    should NOT change to 'succeeded' while the breaker is open.
    """
    from app.modules.payments.constants import SUBJECT_KIND_MEMBERSHIP

    payment = Payment(
        subject_kind=SUBJECT_KIND_MEMBERSHIP,
        subject_id=uuid4(),
        amount_kopecks=50_000,
        method="online",
        received_by_user_id=None,
    )
    session.add(payment)
    await session.flush()

    fr = FiscalReceipt(
        payment_id=payment.id,
        kind="payment",
        status="pending",
        customer_email=f"ver05-parity-{uuid4().hex[:8]}@example.com",
        audit_correlation_id=uuid4(),
    )
    session.add(fr)
    await session.flush()
    await session.commit()
    return fr


async def test_fiscal_receipt_dispatch_short_circuits_when_breaker_open_via_5_failures(
    fiscal_session_factory: async_sessionmaker[AsyncSession],
    fiscal_db_session: AsyncSession,
    fiscal_redis: Any,
    arq_ctx: dict[str, Any],
) -> None:
    """DEFER-46-03 parity: open-state breaker (5 record_failure calls) short-circuits dispatch.

    Scenario mirrors v1.6 VER-09 scenario-08 (cron-chain circuit-breaker
    open-state), now exercised against the FISCAL-05 circuit breaker:

    1. Pre-open the breaker for provider "receipts" via exactly 5
       ``record_failure(redis, "receipts")`` calls — crossing the
       5-failures/60s threshold (D-51-14 locked).
    2. Seed a ``fiscal_receipts(status='pending')`` row.
    3. Invoke ``dispatch_fiscal_receipt`` with the pending receipt while
       the breaker is open.
    4. Assert ``arq.Retry(defer=300)`` is raised (head-of-body short-circuit
       at lines 276-278 of tasks.py).
    5. Assert NO ЮKassa ``/v3/receipts`` POST was issued.
    6. Assert the seeded row remains ``pending`` (status unchanged —
       the short-circuit fires before any FSM transition).

    This is the parity assertion: the v1.6 PARTIAL (scenario-08) is resolved
    because the FISCAL-05 dispatch path provably reuses the same breaker
    primitive and exhibits the same open-state behaviour as expected.
    """
    # Step 1 — pre-open the breaker via 5 record_failure calls.
    # Use the plain redis client (not _ArqRedisProxy) for the failure loop —
    # record_failure only needs EXISTS/ZADD/ZCARD, not enqueue_job.
    for _ in range(_FAILURE_THRESHOLD):
        await record_failure(fiscal_redis, "receipts")

    # Confirm breaker is now open (is_circuit_open check must return True).
    open_marker_exists = await fiscal_redis.exists(_OPEN_MARKER_KEY)
    assert open_marker_exists, (
        f"Breaker should be open after {_FAILURE_THRESHOLD} record_failure calls; "
        f"open-marker key {_OPEN_MARKER_KEY!r} missing."
    )

    # Step 2 — seed a pending fiscal receipt row.
    fr = await _seed_pending_fiscal_receipt(fiscal_db_session)
    fr_id = fr.id

    # Step 3 & 4 — invoke dispatch_fiscal_receipt and assert Retry(defer=300).
    with respx.mock(assert_all_called=False) as router:
        receipts_route = router.post("https://api.yookassa.ru/v3/receipts")

        with pytest.raises(Retry) as exc_info:
            await dispatch_fiscal_receipt(arq_ctx, str(fr_id))

        # Step 5 — assert NO ЮKassa POST was issued.
        assert receipts_route.call_count == 0, (
            "ЮKassa /receipts POST was called despite open breaker — "
            "the is_circuit_open head-of-body guard did not short-circuit."
        )

    # Verify the Retry defer value is the locked 300s (NOT the per-try backoff).
    defer_ms = exc_info.value.defer_score
    assert defer_ms is not None, "Retry.defer_score must not be None on open-breaker path."
    defer_seconds = float(defer_ms) / 1000.0
    assert defer_seconds == float(_OPEN_DEFER_SECONDS), (
        f"Expected Retry(defer=300) for open-breaker short-circuit; "
        f"got defer_seconds={defer_seconds!r}."
    )

    # Step 6 — assert fiscal_receipt status is unchanged ('pending').
    async with fiscal_session_factory() as verify_session:
        row = await verify_session.scalar(select(FiscalReceipt).where(FiscalReceipt.id == fr_id))
        assert row is not None, f"FiscalReceipt {fr_id} disappeared from DB."
        assert row.status == "pending", (
            f"FiscalReceipt status must remain 'pending' under open breaker; "
            f"got {row.status!r}. The short-circuit must fire before any FSM transition."
        )
        assert row.yookassa_receipt_id is None, (
            "yookassa_receipt_id must remain None — no successful dispatch occurred."
        )
        assert row.succeeded_at is None, (
            "succeeded_at must remain None — no receipt.succeeded transition."
        )


async def test_fiscal_receipt_dispatch_short_circuits_when_breaker_open_via_direct_set(
    fiscal_session_factory: async_sessionmaker[AsyncSession],
    fiscal_db_session: AsyncSession,
    fiscal_redis: Any,
    arq_ctx: dict[str, Any],
) -> None:
    """DEFER-46-03 parity variant: direct open-marker SET short-circuits dispatch.

    This is a secondary parity assertion: directly SET the open-marker key
    (as test_yookassa_circuit_breaker.py's test_is_circuit_open_returns_true_when_marker_set
    confirms the EXISTS check), then assert the same short-circuit behaviour
    as the 5-failure variant.

    Confirms the is_circuit_open check is purely EXISTS-based (O(1)) and does
    not require a populated sliding-window — the open marker is authoritative.
    """
    # Pre-open via direct SET (mirrors the unit-test open-state setup).
    await fiscal_redis.set(_OPEN_MARKER_KEY, "1", ex=_OPEN_DEFER_SECONDS)

    fr = await _seed_pending_fiscal_receipt(fiscal_db_session)
    fr_id = fr.id

    with respx.mock(assert_all_called=False) as router:
        receipts_route = router.post("https://api.yookassa.ru/v3/receipts")

        with pytest.raises(Retry) as exc_info:
            await dispatch_fiscal_receipt(arq_ctx, str(fr_id))

        assert receipts_route.call_count == 0, (
            "ЮKassa /receipts POST was called despite open breaker (direct SET path)."
        )

    defer_ms = exc_info.value.defer_score
    assert defer_ms is not None
    defer_seconds = float(defer_ms) / 1000.0
    assert defer_seconds == float(_OPEN_DEFER_SECONDS)

    async with fiscal_session_factory() as verify_session:
        row = await verify_session.scalar(select(FiscalReceipt).where(FiscalReceipt.id == fr_id))
        assert row is not None
        assert row.status == "pending", (
            f"FiscalReceipt status must remain 'pending' (direct-SET variant); got {row.status!r}."
        )
