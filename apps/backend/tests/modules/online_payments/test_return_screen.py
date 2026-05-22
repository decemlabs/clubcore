"""Phase 49 PAY-07 — anti-oracle return-screen tests (D-49-17 / D-49-18 / W3)."""

from __future__ import annotations

import re
import time

import pytest

RETURN_PATH = "/api/v1/online-payments/return"

# Words that MUST NOT appear in the response body — D-49-17 prohibits any
# payment-status leakage. Note: we only check that NO payment-status words
# appear; the static body contains "Оплата получена" and "Ожидаем
# подтверждение от платёжной системы" by design — neither leaks status.
FORBIDDEN_TOKENS = (
    "succeeded",
    "pending",
    "canceled",
    "failed",
    "статус",
    "status",
    "amount",
    "сумма",
)
UUID_RE = re.compile(
    r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
    re.IGNORECASE,
)


@pytest.mark.asyncio
async def test_return_screen_200_anonymous(async_client):
    """No cookies, no CSRF, no Idempotency-Key — should still return 200."""
    response = await async_client.get(RETURN_PATH)
    assert response.status_code == 200
    assert "Ожидаем подтверждение" in response.text


@pytest.mark.asyncio
async def test_return_screen_body_identical_across_query_shapes(async_client):
    """D-49-17 — query params are accepted but discarded; body is byte-identical."""
    responses = [
        await async_client.get(RETURN_PATH),
        await async_client.get(RETURN_PATH + "?payment_id=abc"),
        await async_client.get(
            RETURN_PATH + "?payment_id=29ab1a59-000f-5000-8000-1399cb40ba0e&foo=bar"
        ),
        await async_client.get(RETURN_PATH + "?status=succeeded"),  # attacker probing
    ]
    bodies = {r.content for r in responses}
    assert len(bodies) == 1, "All responses MUST be byte-identical (no query-param branching)"


@pytest.mark.asyncio
async def test_return_screen_no_status_leakage(async_client):
    """D-49-17 — body MUST NOT contain payment status words or UUIDs."""
    response = await async_client.get(
        RETURN_PATH + "?payment_id=29ab1a59-000f-5000-8000-1399cb40ba0e"
    )
    body_lower = response.text.lower()
    for token in FORBIDDEN_TOKENS:
        assert token.lower() not in body_lower, (
            f"Forbidden token {token!r} leaked into response — anti-oracle violation"
        )
    assert UUID_RE.search(response.text) is None, (
        "UUID-shaped string leaked into response — anti-oracle violation"
    )


@pytest.mark.asyncio
async def test_return_screen_cache_control_no_store(async_client):
    """D-49-17 — Cache-Control: no-store, max-age=0."""
    response = await async_client.get(RETURN_PATH)
    cc = response.headers.get("cache-control", "")
    assert "no-store" in cc
    assert "max-age=0" in cc


@pytest.mark.asyncio
async def test_return_screen_content_type_html(async_client):
    response = await async_client.get(RETURN_PATH)
    ct = response.headers.get("content-type", "")
    assert ct.startswith("text/html")


@pytest.mark.asyncio
async def test_return_screen_constant_time_floor(async_client):
    """W3 — minimum wall time >= 40 ms (60 ms floor with 20 ms CI-jitter tolerance).

    Original D-49-18 specified 50 ms / 5 ms tolerance; W3 raised the floor to
    60 ms and relaxed the assertion to 40 ms to prevent CI scheduler-jitter
    false positives. The 60 ms floor stays well below the 100 ms human
    perception threshold — UX is unchanged.
    """
    timings = []
    for _ in range(10):
        start = time.perf_counter()
        response = await async_client.get(RETURN_PATH)
        elapsed = time.perf_counter() - start
        assert response.status_code == 200
        timings.append(elapsed)
    min_elapsed = min(timings)
    assert min_elapsed >= 0.040, (
        f"Minimum elapsed {min_elapsed:.3f}s breaches 40 ms floor — "
        f"constant-time mitigation regressed (D-49-18 / W3 / PITFALLS Pitfall 4)."
    )
