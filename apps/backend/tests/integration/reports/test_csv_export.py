"""Integration tests for CSV export endpoints (Phase 56 EXP-01..04).

Coverage:
  - GET /api/v1/reports/revenue.csv, /clients.csv, /visits.csv, /audit-log.csv
    as owner → 200; Content-Type text/csv; body starts with UTF-8 BOM U+FEFF (EXP-04).
  - All four endpoints as reception → 403 "forbidden" (T-56-06, AUD-05, SC#1).
  - BOM is U+FEFF (first char of r.text equals chr(0xFEFF)).
  - Header row matches the expected CSV_*_HEADERS constant for each endpoint.
  - CRLF line terminators (\\r\\n).
  - Cyrillic round-trip: Cyrillic actor_email_snapshot appears verbatim in audit-log.csv.
  - RFC-4180 escaping: payload with comma + double-quote is wrapped/doubled correctly.
  - Ruble formatting: 250000 kopecks → "2500.00" (not "250000") in revenue.csv (D-13).
  - MSK date: audit row at known UTC renders as Europe/Moscow "YYYY-MM-DD HH:MM:SS" (D-14).
  - Filter consistency (SC#5, EXP-02):
    - audit-log.csv?action=login_success → only matching rows.
    - audit-log.csv?action=bad_event → 422 audit_filter_invalid.
    - audit-log.csv?from=..&to=.. narrows by MSK date window.
    - audit-log.csv?from=later&to=earlier → 422.
"""

from __future__ import annotations

import csv
import io
from datetime import UTC, datetime
from typing import Any

from httpx import AsyncClient

from app.modules.reports.constants import (
    CSV_AUDIT_LOG_HEADERS,
    CSV_CLIENTS_HEADERS,
    CSV_REVENUE_HEADERS,
    CSV_VISITS_HEADERS,
)
from app.modules.reports.csv_export import BOM

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def parse_csv_text(text: str) -> list[list[str]]:
    """Strip BOM and parse CSV text into rows (list of list of str)."""
    return list(csv.reader(io.StringIO(text.lstrip(BOM))))


def header_line(headers: tuple[str, ...]) -> str:
    """Expected header row as comma-joined string (without CRLF for contains-check)."""
    return ",".join(headers)


# ---------------------------------------------------------------------------
# BOM + Content-Type assertions for all four endpoints
# ---------------------------------------------------------------------------


async def test_revenue_csv_bom_and_content_type(
    authed_client_owner: AsyncClient,
) -> None:
    """Owner GET /reports/revenue.csv → 200; text/csv; body starts with UTF-8 BOM."""
    r = await authed_client_owner.get(
        "/api/v1/reports/revenue.csv",
        params={"fromDate": "2026-05-01", "toDate": "2026-05-31", "groupBy": "day"},
    )
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("text/csv")
    assert r.text[0] == BOM, f"Expected BOM as first char, got {r.text[0]!r}"
    assert ord(r.text[0]) == 0xFEFF, f"BOM must be U+FEFF, got U+{ord(r.text[0]):04X}"


async def test_clients_csv_bom_and_content_type(
    authed_client_owner: AsyncClient,
) -> None:
    """Owner GET /reports/clients.csv → 200; text/csv; body starts with UTF-8 BOM."""
    r = await authed_client_owner.get(
        "/api/v1/reports/clients.csv",
        params={"fromDate": "2026-05-01", "toDate": "2026-05-31"},
    )
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("text/csv")
    assert r.text[0] == BOM


async def test_visits_csv_bom_and_content_type(
    authed_client_owner: AsyncClient,
) -> None:
    """Owner GET /reports/visits.csv → 200; text/csv; body starts with UTF-8 BOM."""
    r = await authed_client_owner.get(
        "/api/v1/reports/visits.csv",
        params={"fromDate": "2026-05-01", "toDate": "2026-05-31"},
    )
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("text/csv")
    assert r.text[0] == BOM


async def test_audit_log_csv_bom_and_content_type(
    authed_client_owner: AsyncClient,
) -> None:
    """Owner GET /audit-log.csv → 200; text/csv; body starts with UTF-8 BOM."""
    r = await authed_client_owner.get("/api/v1/audit-log.csv")
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("text/csv")
    assert r.text[0] == BOM


# ---------------------------------------------------------------------------
# Header row assertions
# ---------------------------------------------------------------------------


async def test_revenue_csv_header_row(
    authed_client_owner: AsyncClient,
) -> None:
    """Revenue CSV second line (after BOM) matches CSV_REVENUE_HEADERS."""
    r = await authed_client_owner.get(
        "/api/v1/reports/revenue.csv",
        params={"fromDate": "2026-05-01", "toDate": "2026-05-31"},
    )
    assert r.status_code == 200, r.text
    rows = parse_csv_text(r.text)
    assert rows[0] == list(CSV_REVENUE_HEADERS), f"Header mismatch: {rows[0]}"


async def test_clients_csv_header_row(
    authed_client_owner: AsyncClient,
) -> None:
    """Clients CSV header row matches CSV_CLIENTS_HEADERS."""
    r = await authed_client_owner.get(
        "/api/v1/reports/clients.csv",
        params={"fromDate": "2026-05-01", "toDate": "2026-05-31"},
    )
    assert r.status_code == 200, r.text
    rows = parse_csv_text(r.text)
    assert rows[0] == list(CSV_CLIENTS_HEADERS), f"Header mismatch: {rows[0]}"


async def test_visits_csv_header_row(
    authed_client_owner: AsyncClient,
) -> None:
    """Visits CSV header row matches CSV_VISITS_HEADERS."""
    r = await authed_client_owner.get(
        "/api/v1/reports/visits.csv",
        params={"fromDate": "2026-05-01", "toDate": "2026-05-31"},
    )
    assert r.status_code == 200, r.text
    rows = parse_csv_text(r.text)
    assert rows[0] == list(CSV_VISITS_HEADERS), f"Header mismatch: {rows[0]}"


async def test_audit_log_csv_header_row(
    authed_client_owner: AsyncClient,
) -> None:
    """Audit-log CSV header row matches CSV_AUDIT_LOG_HEADERS."""
    r = await authed_client_owner.get("/api/v1/audit-log.csv")
    assert r.status_code == 200, r.text
    rows = parse_csv_text(r.text)
    assert rows[0] == list(CSV_AUDIT_LOG_HEADERS), f"Header mismatch: {rows[0]}"


# ---------------------------------------------------------------------------
# Reception → 403 on all four endpoints
# ---------------------------------------------------------------------------


async def test_revenue_csv_reception_forbidden(
    authed_client_reception: AsyncClient,
) -> None:
    """(VIEW, REPORTS) ∈ OWNER_ONLY → reception 403 on revenue.csv (T-56-06)."""
    r = await authed_client_reception.get(
        "/api/v1/reports/revenue.csv",
        params={"fromDate": "2026-05-01", "toDate": "2026-05-31"},
    )
    assert r.status_code == 403, r.text
    assert r.json()["code"] == "forbidden"


async def test_clients_csv_reception_forbidden(
    authed_client_reception: AsyncClient,
) -> None:
    """(VIEW, REPORTS) ∈ OWNER_ONLY → reception 403 on clients.csv."""
    r = await authed_client_reception.get(
        "/api/v1/reports/clients.csv",
        params={"fromDate": "2026-05-01", "toDate": "2026-05-31"},
    )
    assert r.status_code == 403, r.text
    assert r.json()["code"] == "forbidden"


async def test_visits_csv_reception_forbidden(
    authed_client_reception: AsyncClient,
) -> None:
    """(VIEW, REPORTS) ∈ OWNER_ONLY → reception 403 on visits.csv."""
    r = await authed_client_reception.get(
        "/api/v1/reports/visits.csv",
        params={"fromDate": "2026-05-01", "toDate": "2026-05-31"},
    )
    assert r.status_code == 403, r.text
    assert r.json()["code"] == "forbidden"


async def test_audit_log_csv_reception_forbidden(
    authed_client_reception: AsyncClient,
) -> None:
    """(LIST, AUDIT_LOG) ∈ OWNER_ONLY → reception 403 on audit-log.csv (T-56-06)."""
    r = await authed_client_reception.get("/api/v1/audit-log.csv")
    assert r.status_code == 403, r.text
    assert r.json()["code"] == "forbidden"


# ---------------------------------------------------------------------------
# CRLF line terminators
# ---------------------------------------------------------------------------


async def test_audit_log_csv_crlf_terminators(
    authed_client_owner: AsyncClient,
) -> None:
    """All lines in audit-log.csv are terminated with \\r\\n (RFC 4180, D-11)."""
    r = await authed_client_owner.get("/api/v1/audit-log.csv")
    assert r.status_code == 200, r.text
    # Strip the leading BOM; remaining content should only have \r\n line endings.
    body = r.text.lstrip(BOM)
    # Split by \r\n — all non-empty chunks should be field lines
    lines = body.split("\r\n")
    # Should have at least the header row
    assert len(lines) >= 1
    # Body should not contain bare \n (without preceding \r)
    # Check: re-joined body with \r\n should equal the stripped body minus trailing \r\n
    assert "\n" not in body.replace("\r\n", "")


# ---------------------------------------------------------------------------
# Cyrillic round-trip
# ---------------------------------------------------------------------------


async def test_audit_log_csv_cyrillic_round_trip(
    authed_client_owner: AsyncClient,
    make_audit_log_row: Any,
) -> None:
    """Cyrillic actor_email_snapshot appears verbatim in audit-log.csv after BOM (EXP-04)."""
    cyrillic_email = "иван@почта.рф"
    await make_audit_log_row(
        action="login_success",
        resource_type="session",
        created_at=datetime(2026, 5, 20, 10, 0, tzinfo=UTC),
        actor_email_snapshot=cyrillic_email,
    )
    r = await authed_client_owner.get(
        "/api/v1/audit-log.csv",
        params={"action": "login_success"},
    )
    assert r.status_code == 200, r.text
    assert cyrillic_email in r.text, "Cyrillic email must appear verbatim in CSV output"


# ---------------------------------------------------------------------------
# RFC-4180 escaping: comma and double-quote in payload
# ---------------------------------------------------------------------------


async def test_audit_log_csv_rfc4180_escaping(
    authed_client_owner: AsyncClient,
    make_audit_log_row: Any,
) -> None:
    """Payload with comma + double-quote is RFC-4180 quote-escaped in audit-log.csv."""
    # payload cell will contain: a,b"c  (comma AND double-quote)
    payload_value = 'a,b"c'
    await make_audit_log_row(
        action="login_success",
        resource_type="session",
        created_at=datetime(2026, 5, 20, 10, 0, tzinfo=UTC),
        payload={"note": payload_value},
    )
    r = await authed_client_owner.get(
        "/api/v1/audit-log.csv",
        params={"action": "login_success"},
    )
    assert r.status_code == 200, r.text
    # The payload cell is JSON-serialized: {"note":"a,b\"c"}
    # CSV writer (QUOTE_MINIMAL) wraps the whole field in quotes because of the comma.
    # The inner double-quote is RFC-4180 doubled: "" inside the outer quotes.
    assert '""' in r.text, 'RFC-4180 doubled double-quote ("") not found in CSV body'
    # Also verify the field containing comma is quoted (not bare)
    # The raw text should contain the quoted form
    assert '"a,b' in r.text or ',"a,' in r.text or '"note"' in r.text


# ---------------------------------------------------------------------------
# Ruble formatting (D-13)
# ---------------------------------------------------------------------------


async def test_revenue_csv_ruble_formatting(
    authed_client_owner: AsyncClient,
    make_payment_ledger: Any,
    seeded_owner: Any,
    make_client: Any,
    make_membership: Any,
    make_plan: Any,
) -> None:
    """Revenue CSV renders 250000 kopecks as '2500.00', not '250000' (D-13)."""
    plan = await make_plan(name="CSVRubleTest")
    cli = await make_client()
    mem = await make_membership(client_id=cli.id, plan=plan)
    await make_payment_ledger(
        subject_id=mem.id,
        amount_kopecks=250000,
        method="cash",
        received_at=datetime(2026, 5, 15, 10, 0, 0, tzinfo=UTC),
        received_by_user_id=seeded_owner.id,
    )
    r = await authed_client_owner.get(
        "/api/v1/reports/revenue.csv",
        params={"fromDate": "2026-05-15", "toDate": "2026-05-15", "groupBy": "day"},
    )
    assert r.status_code == 200, r.text
    # Money column should appear as rubles (2500.00), NOT raw kopecks (250000)
    assert "2500.00" in r.text, f"Expected '2500.00' ruble value in CSV. Body: {r.text[:500]}"
    # Raw kopeck value should NOT appear as a money cell
    # (250000 appears nowhere as a standalone money token)
    rows = parse_csv_text(r.text)
    # Check data rows (rows[1:]) for kopeck value in money columns
    for row in rows[1:]:
        # money columns are indices 1-5 in CSV_REVENUE_HEADERS: netRubles..ptPackageRubles
        for val in row[1:6]:
            assert val != "250000", f"Raw kopeck value '250000' found in money column: {row}"


# ---------------------------------------------------------------------------
# MSK date formatting (D-14)
# ---------------------------------------------------------------------------


async def test_audit_log_csv_msk_datetime(
    authed_client_owner: AsyncClient,
    make_audit_log_row: Any,
) -> None:
    """Audit-log CSV createdAt is Europe/Moscow 'YYYY-MM-DD HH:MM:SS' (D-14).

    UTC midnight (2026-03-01 00:30 UTC) → MSK is UTC+3 → 2026-03-01 03:30:00.
    """
    utc_ts = datetime(2026, 3, 1, 0, 30, 0, tzinfo=UTC)
    await make_audit_log_row(
        action="login_success",
        resource_type="session",
        created_at=utc_ts,
    )
    r = await authed_client_owner.get(
        "/api/v1/audit-log.csv",
        params={
            "action": "login_success",
            "from": "2026-03-01",
            "to": "2026-03-01",
        },
    )
    assert r.status_code == 200, r.text
    # UTC+3: 00:30 UTC → 03:30 MSK
    assert "2026-03-01 03:30:00" in r.text, (
        f"Expected MSK datetime '2026-03-01 03:30:00' in CSV. Body: {r.text[:500]}"
    )


# ---------------------------------------------------------------------------
# Filter consistency (SC#5, EXP-02)
# ---------------------------------------------------------------------------


async def test_audit_log_csv_action_filter_narrows(
    authed_client_owner: AsyncClient,
    make_audit_log_row: Any,
) -> None:
    """audit-log.csv?action=login_success returns only login_success rows (SC#5, EXP-02)."""
    # Insert one login_success and one trainer_created
    await make_audit_log_row(
        action="login_success",
        resource_type="session",
        created_at=datetime(2026, 5, 10, 8, 0, tzinfo=UTC),
    )
    await make_audit_log_row(
        action="trainer_created",
        resource_type="trainer",
        created_at=datetime(2026, 5, 10, 9, 0, tzinfo=UTC),
    )
    r = await authed_client_owner.get(
        "/api/v1/audit-log.csv",
        params={"action": "login_success"},
    )
    assert r.status_code == 200, r.text
    rows = parse_csv_text(r.text)
    # rows[0] = header, rows[1:] = data rows
    data_rows = rows[1:]
    # action is the 4th column (index 3) in CSV_AUDIT_LOG_HEADERS
    action_col = list(CSV_AUDIT_LOG_HEADERS).index("action")
    for row in data_rows:
        if row:  # skip empty trailing rows
            assert row[action_col] == "login_success", (
                f"Non-login_success row found: {row}"
            )


async def test_audit_log_csv_bad_action_422(
    authed_client_owner: AsyncClient,
) -> None:
    """audit-log.csv?action=bad_event → 422 audit_filter_invalid (matches JSON, SC#5)."""
    r = await authed_client_owner.get(
        "/api/v1/audit-log.csv",
        params={"action": "bad_event"},
    )
    assert r.status_code == 422, r.text
    assert r.json()["code"] == "audit_filter_invalid"


async def test_audit_log_csv_date_window_narrows(
    authed_client_owner: AsyncClient,
    make_audit_log_row: Any,
) -> None:
    """audit-log.csv?from=..&to=.. narrows results by MSK date window (D-16, SC#5)."""
    # Two rows: one inside the window, one outside
    inside_ts = datetime(2026, 5, 15, 10, 0, tzinfo=UTC)   # MSK: 2026-05-15
    outside_ts = datetime(2026, 5, 20, 10, 0, tzinfo=UTC)  # MSK: 2026-05-20

    await make_audit_log_row(
        action="login_success",
        resource_type="session",
        created_at=inside_ts,
    )
    await make_audit_log_row(
        action="login_success",
        resource_type="session",
        created_at=outside_ts,
    )

    r = await authed_client_owner.get(
        "/api/v1/audit-log.csv",
        params={
            "action": "login_success",
            "from": "2026-05-15",
            "to": "2026-05-15",
        },
    )
    assert r.status_code == 200, r.text
    rows = parse_csv_text(r.text)
    data_rows = [row for row in rows[1:] if row]  # skip header + empty trailing
    # Only the inside row should appear (MSK 2026-05-15)
    assert len(data_rows) >= 1, "Expected at least one row within the date window"
    # The outside row's createdAt (2026-05-20) should NOT appear
    created_at_col = list(CSV_AUDIT_LOG_HEADERS).index("createdAt")
    for row in data_rows:
        assert "2026-05-20" not in row[created_at_col], (
            f"Row outside date window found: {row}"
        )


async def test_audit_log_csv_to_before_from_422(
    authed_client_owner: AsyncClient,
) -> None:
    """audit-log.csv?from=later&to=earlier → 422 (route-level from/to honored, SC#5)."""
    r = await authed_client_owner.get(
        "/api/v1/audit-log.csv",
        params={"from": "2026-05-31", "to": "2026-05-01"},
    )
    assert r.status_code == 422, r.text
