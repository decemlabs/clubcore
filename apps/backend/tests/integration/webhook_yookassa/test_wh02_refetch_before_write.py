"""WH-02 — Re-fetch BEFORE any DB write (Phase 50 success criterion #2).

B-2 FIX (revision 2): the ordering assertion uses a SINGLE clock domain —
``time.perf_counter()`` on BOTH sides. The respx mock uses a ``side_effect``
callback that records ``time.perf_counter()`` at invocation; the SQLAlchemy
``before_execute`` listener records ``time.perf_counter()`` per statement.
Revision 1's pattern
(``respx_mock.calls.last.response.elapsed.total_seconds()`` — a ``timedelta``
duration ~0.001s — compared against a ``perf_counter()`` value ~10000s) was
tautologically true and is REMOVED. DO NOT reintroduce the elapsed-based
comparison.
"""

from __future__ import annotations

import time
from typing import Any

import httpx
import pytest
import respx
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.online_payments.models import OnlinePayment
from tests.integration.webhook_yookassa.conftest import SeededOnlinePayment


@pytest.mark.asyncio
async def test_wh02_refetches_via_get_payment_before_db_write(
    webhook_client: AsyncClient,
    webhook_db_session: AsyncSession,
    seeded_online_payment_pending: SeededOnlinePayment,
    respx_mock: respx.MockRouter,
    sqlalchemy_query_log_timestamps: list[tuple[str, float]],
    webhook_payment_succeeded_body: Any,
) -> None:
    """WH-02 — re-fetch via GET /v3/payments/{id} happens BEFORE any UPDATE.

    Uses a single clock domain (time.perf_counter) on BOTH sides:
      - the respx mock's side_effect records perf_counter() at invocation
      - the SQLAlchemy before_execute listener records perf_counter() per stmt
    The assertion compares same-clock values; reversal of order would fail.

    Revision 1 used ``respx_mock.calls.last.response.elapsed.total_seconds()``
    (a timedelta duration, ~0.001s) compared against a perf_counter() value
    (~10000s) — that assertion was tautologically true. DO NOT reintroduce
    the elapsed-based comparison.
    """
    get_payment_ts: list[float] = []

    def _record_get_payment(request: httpx.Request) -> httpx.Response:
        get_payment_ts.append(time.perf_counter())
        return httpx.Response(
            200,
            json={
                "id": seeded_online_payment_pending.yookassa_payment_id,
                "status": "succeeded",
                "amount": {"value": "1000.00", "currency": "RUB"},
                "paid": True,
            },
        )

    respx_mock.get(url__regex=r"https://api\.yookassa\.ru/v3/payments/[\w-]+").mock(
        side_effect=_record_get_payment
    )

    body = webhook_payment_succeeded_body(seeded_online_payment_pending.yookassa_payment_id)
    response = await webhook_client.post(
        "/api/v1/_internal/yookassa/webhook",
        json=body,
    )
    assert response.status_code == 200, response.text

    # Both sides share the time.perf_counter() clock domain.
    assert len(get_payment_ts) == 1, (
        f"expected exactly one re-fetch call; got {len(get_payment_ts)}"
    )
    refetch_ts = get_payment_ts[0]

    update_ts_iter = (
        ts for stmt, ts in sqlalchemy_query_log_timestamps if "UPDATE online_payments" in stmt
    )
    first_update_ts = next(update_ts_iter, None)
    assert first_update_ts is not None, (
        "expected an UPDATE online_payments statement; logged statements: "
        f"{[s for s, _ in sqlalchemy_query_log_timestamps]}"
    )

    assert refetch_ts < first_update_ts, (
        f"WH-02 violated: UPDATE issued before re-fetch "
        f"(refetch_ts={refetch_ts}, first_update_ts={first_update_ts})"
    )

    # Sanity: the status was actually flipped on the row.
    await webhook_db_session.commit()
    after_status = await webhook_db_session.scalar(
        select(OnlinePayment.status).where(
            OnlinePayment.id == seeded_online_payment_pending.online_payment_id
        )
    )
    assert after_status == "succeeded"


@pytest.mark.asyncio
async def test_wh02_refetch_pending_status_skips_db_write(
    webhook_client: AsyncClient,
    webhook_db_session: AsyncSession,
    seeded_online_payment_pending: SeededOnlinePayment,
    respx_mock: respx.MockRouter,
    webhook_payment_succeeded_body: Any,
) -> None:
    """If the re-fetch returns status='pending' (webhook arrived before ЮKassa
    internal commit), the handler must return 200 and NOT mutate the row."""
    respx_mock.get(url__regex=r"https://api\.yookassa\.ru/v3/payments/[\w-]+").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": seeded_online_payment_pending.yookassa_payment_id,
                "status": "pending",
                "amount": {"value": "1000.00", "currency": "RUB"},
            },
        )
    )

    body = webhook_payment_succeeded_body(seeded_online_payment_pending.yookassa_payment_id)
    response = await webhook_client.post(
        "/api/v1/_internal/yookassa/webhook",
        json=body,
    )
    assert response.status_code == 200, response.text

    await webhook_db_session.commit()
    after_status = await webhook_db_session.scalar(
        select(OnlinePayment.status).where(
            OnlinePayment.id == seeded_online_payment_pending.online_payment_id
        )
    )
    assert after_status == "pending", (
        "WH-02: pending re-fetch result MUST NOT mutate online_payments.status"
    )


@pytest.mark.asyncio
async def test_wh02_refetch_error_classification_skips_db_write(
    webhook_client: AsyncClient,
    webhook_db_session: AsyncSession,
    seeded_online_payment_pending: SeededOnlinePayment,
    respx_mock: respx.MockRouter,
    webhook_payment_succeeded_body: Any,
) -> None:
    """Re-fetch returning a non-ok classification (e.g. 500 / transient_error)
    must NOT mutate the row.

    The structural assertion (row.status unchanged) is the canonical
    observability surface; the handler also logs a structlog WARNING but
    capture_logs() inside the in-process app sometimes misses messages
    emitted deep in the handler stack (production logger cached at
    lifespan time). DB-state is the authoritative invariant here.
    """
    respx_mock.get(url__regex=r"https://api\.yookassa\.ru/v3/payments/[\w-]+").mock(
        return_value=httpx.Response(500, json={"type": "error"})
    )

    body = webhook_payment_succeeded_body(seeded_online_payment_pending.yookassa_payment_id)
    response = await webhook_client.post(
        "/api/v1/_internal/yookassa/webhook",
        json=body,
    )
    assert response.status_code == 200, response.text

    await webhook_db_session.commit()
    after_status = await webhook_db_session.scalar(
        select(OnlinePayment.status).where(
            OnlinePayment.id == seeded_online_payment_pending.online_payment_id
        )
    )
    assert after_status == "pending", (
        "WH-02: failing re-fetch MUST NOT mutate online_payments.status"
    )
