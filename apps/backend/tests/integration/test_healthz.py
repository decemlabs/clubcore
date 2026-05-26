"""Integration test: GET /healthz returns 200 with the documented body.

Two assertions:
1. Status + body — satisfies TEST-02 verbatim.
2. `x-request-id` header is a valid UUID4 — proves Phase 2 RequestIdMiddleware
   fires under httpx.ASGITransport (catches "tests pass but middleware silently
   bypassed" bugs). See CONTEXT `<code_context>` and Phase 2 D-09.

No DB needed (`/healthz` makes no DB query — Phase 2 D-14 / CONTEXT D-10).
"""

from __future__ import annotations

import uuid

from httpx import AsyncClient


async def test_healthz_returns_200_and_status_ok(async_client: AsyncClient) -> None:
    response = await async_client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_healthz_emits_request_id_header(async_client: AsyncClient) -> None:
    """Phase 2 D-09: RequestIdMiddleware echoes a UUID4 X-Request-ID on every response."""
    response = await async_client.get("/healthz")
    headers_lower = {k.lower() for k in response.headers}
    assert "x-request-id" in headers_lower
    # Must parse as a valid UUID4.
    parsed = uuid.UUID(response.headers["x-request-id"])
    assert parsed.version == 4
