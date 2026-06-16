"""Phase 117 Plan 02 Task 1 — Capture real load/now response (D-V32-DRIFT-LESSON).

Hits GET /api/v1/reports/load/now via ASGITransport, serializes the actual JSON
response to the shared FE fixtures dir:
  apps/admin/src/features/reports/capture/load-now-response.json

Representative analytics endpoint for the cohort/anomaly/at-risk/load-now group
(per 117-CONTEXT.md "CONTEXT permits one analytics capture").

The captured JSON is parsed by the FE vitest contract test
(features/reports/load-now.contract.test.ts) using the REAL FE Zod LoadNowSchema.
"""

from __future__ import annotations

import json
import pathlib

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio(loop_scope="function")

# ---------------------------------------------------------------------------
# Shared fixtures dir
# tests/integration/reports/ → parents[5] = repo root
# ---------------------------------------------------------------------------

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[5]
FIXTURES_DIR = _REPO_ROOT / "apps/admin/src/features/reports/capture"


# ---------------------------------------------------------------------------
# Capture test — serialize REAL load/now response to shared FE fixture
# ---------------------------------------------------------------------------


async def test_capture_load_now_response(
    authed_client_owner: AsyncClient,
) -> None:
    """GET /api/v1/reports/load/now → 200; serialize r.json() to capture dir.

    No visit seeding needed — the endpoint returns count=0 when no visits are
    in the rolling window, and that is a valid parseable response.
    """
    r = await authed_client_owner.get("/api/v1/reports/load/now")
    assert r.status_code == 200, r.text

    body = r.json()
    # Stable field assertions — test fails loudly if the response shape collapses.
    data = body["data"]
    assert "count" in data, f"Expected 'count' in data, got: {data}"
    assert "asOf" in data, f"Expected 'asOf' in data, got: {data}"
    assert "windowMinutes" in data, f"Expected 'windowMinutes' in data, got: {data}"
    assert isinstance(data["count"], int), f"count must be int, got: {type(data['count'])}"
    assert data["count"] >= 0, f"count must be non-negative, got: {data['count']}"

    # Verify captured path is inside repo root before writing.
    assert str(FIXTURES_DIR).startswith(str(_REPO_ROOT)), (
        f"FIXTURES_DIR {FIXTURES_DIR} is outside the repo root {_REPO_ROOT}"
    )

    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    (FIXTURES_DIR / "load-now-response.json").write_text(
        json.dumps(body, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
