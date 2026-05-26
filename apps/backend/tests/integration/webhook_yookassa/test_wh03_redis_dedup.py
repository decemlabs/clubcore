"""WH-03 — Redis dedup (Phase 50 success criterion #3).

Same body POSTed twice: second POST returns 200 but does NOT invoke the
re-fetch (short-circuited at Redis ``SET NX`` per D-50-10). Dedup key shape
matches ``WEBHOOK_DEDUP_KEY_PREFIX`` constant from Plan 50-04 router.
"""

from __future__ import annotations

from typing import Any

import pytest
import respx
from httpx import AsyncClient
from redis.asyncio import Redis

from app.api.v1._internal.yookassa.router import (
    WEBHOOK_DEDUP_KEY_PREFIX,
    WEBHOOK_DEDUP_TTL_SECONDS,
)
from tests.integration.webhook_yookassa.conftest import SeededOnlinePayment


@pytest.mark.asyncio
async def test_wh03_second_identical_delivery_returns_200_no_second_refetch(
    webhook_client: AsyncClient,
    webhook_payment_succeeded_body: Any,
    yookassa_get_payment_succeeded: respx.MockRouter,
    seeded_online_payment_pending: SeededOnlinePayment,
    redis_test_client: Redis,
) -> None:
    """Second POST same body short-circuits at Redis dedup BEFORE re-fetch."""
    body = webhook_payment_succeeded_body(seeded_online_payment_pending.yookassa_payment_id)

    # First delivery — full flow runs (re-fetch happens once).
    r1 = await webhook_client.post("/api/v1/_internal/yookassa/webhook", json=body)
    assert r1.status_code == 200, r1.text

    # The dedup key is now present in Redis.
    expected_key = (
        f"{WEBHOOK_DEDUP_KEY_PREFIX}payment.succeeded:"
        f"{seeded_online_payment_pending.yookassa_payment_id}"
    )
    assert await redis_test_client.exists(expected_key) == 1

    # TTL is approximately WEBHOOK_DEDUP_TTL_SECONDS (24h). Allow a small
    # tolerance for test latency between SET and TTL probe.
    ttl = await redis_test_client.ttl(expected_key)
    assert 0 < ttl <= WEBHOOK_DEDUP_TTL_SECONDS

    # Count respx invocations after the first delivery.
    call_count_after_first = yookassa_get_payment_succeeded.calls.call_count

    # Second delivery — same body — short-circuits at dedup.
    r2 = await webhook_client.post("/api/v1/_internal/yookassa/webhook", json=body)
    assert r2.status_code == 200, r2.text

    # The re-fetch was NOT invoked on the second delivery (D-50-10 — dedup
    # runs BEFORE re-fetch to preserve ЮKassa outbound rate-budget).
    assert yookassa_get_payment_succeeded.calls.call_count == call_count_after_first, (
        "WH-03: duplicate delivery must NOT invoke a second re-fetch"
    )


@pytest.mark.asyncio
async def test_wh03_dedup_key_format(
    webhook_client: AsyncClient,
    webhook_payment_succeeded_body: Any,
    yookassa_get_payment_succeeded: respx.MockRouter,
    seeded_online_payment_pending: SeededOnlinePayment,
    redis_test_client: Redis,
) -> None:
    """Dedup key prefix matches ``WEBHOOK_DEDUP_KEY_PREFIX`` constant."""
    body = webhook_payment_succeeded_body(seeded_online_payment_pending.yookassa_payment_id)
    r = await webhook_client.post("/api/v1/_internal/yookassa/webhook", json=body)
    assert r.status_code == 200, r.text

    keys = await redis_test_client.keys(f"{WEBHOOK_DEDUP_KEY_PREFIX}*")
    assert len(keys) >= 1, (
        f"expected at least one dedup key with prefix {WEBHOOK_DEDUP_KEY_PREFIX!r}; got: {keys}"
    )
    # The keys returned by ``Redis.keys`` are bytes by default.
    decoded = [k.decode() if isinstance(k, bytes) else k for k in keys]
    assert all(k.startswith(WEBHOOK_DEDUP_KEY_PREFIX) for k in decoded), decoded
