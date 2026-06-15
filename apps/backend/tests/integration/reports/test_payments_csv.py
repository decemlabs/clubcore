"""Phase 117 Plan 02 Task 1 — Backend assertion for GET /api/v1/reports/payments.csv.

Asserts at the BACKEND tier ONLY (not via FE Zod — the body is text/csv):
  - status 200
  - Content-Type starts with text/csv
  - First char is U+FEFF (UTF-8 BOM)
  - Header row after the BOM matches CSV_PAYMENTS_HEADERS

Analog: tests/integration/reports/test_csv_export.py (revenue.csv / clients.csv patterns).
Does NOT capture the CSV body as a JSON fixture.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.modules.reports.constants import CSV_PAYMENTS_HEADERS
from app.modules.reports.csv_export import BOM

pytestmark = pytest.mark.asyncio(loop_scope="function")


async def test_payments_csv_status_and_content_type(
    authed_client_owner: AsyncClient,
) -> None:
    """Owner GET /reports/payments.csv → 200; Content-Type text/csv."""
    r = await authed_client_owner.get(
        "/api/v1/reports/payments.csv",
        params={"fromDate": "2026-01-01", "toDate": "2026-12-31"},
    )
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("text/csv"), (
        f"Expected text/csv, got: {r.headers['content-type']!r}"
    )


async def test_payments_csv_bom(
    authed_client_owner: AsyncClient,
) -> None:
    """Owner GET /reports/payments.csv → body starts with UTF-8 BOM U+FEFF."""
    r = await authed_client_owner.get(
        "/api/v1/reports/payments.csv",
        params={"fromDate": "2026-01-01", "toDate": "2026-12-31"},
    )
    assert r.status_code == 200, r.text
    assert r.text[0] == BOM, f"Expected BOM as first char, got {r.text[0]!r}"
    assert ord(r.text[0]) == 0xFEFF, f"BOM must be U+FEFF, got U+{ord(r.text[0]):04X}"


async def test_payments_csv_header_row(
    authed_client_owner: AsyncClient,
) -> None:
    """Payments CSV header row matches CSV_PAYMENTS_HEADERS constant."""
    import csv
    import io

    r = await authed_client_owner.get(
        "/api/v1/reports/payments.csv",
        params={"fromDate": "2026-01-01", "toDate": "2026-12-31"},
    )
    assert r.status_code == 200, r.text

    rows = list(csv.reader(io.StringIO(r.text.lstrip(BOM))))
    assert len(rows) >= 1, "Expected at least a header row in the CSV"
    assert rows[0] == list(CSV_PAYMENTS_HEADERS), (
        f"Header mismatch.\nExpected: {list(CSV_PAYMENTS_HEADERS)}\nGot: {rows[0]}"
    )
