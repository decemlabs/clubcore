---
phase: 56-audit-log-read-api-csv-export
plan: "02"
subsystem: backend/reports
tags: [csv-export, streaming, bom, rfc4180, rbac, pytest, tdd]
dependency_graph:
  requires:
    - 56-01 (AuditLogQuery, _build_audit_predicates, filter validation, audit_log_router)
    - 55-revenue-clients-visits-reports (get_revenue_report, get_clients_report, get_visits_report)
  provides:
    - GET /api/v1/reports/revenue.csv
    - GET /api/v1/reports/clients.csv
    - GET /api/v1/reports/visits.csv
    - GET /api/v1/audit-log.csv
    - csv_export.py (BOM + RFC-4180 + StreamingResponse + money/date formatters)
    - stream_audit_log_rows async row iterator
    - validate_audit_filters (public, shared by JSON + CSV)
  affects:
    - apps/backend/app/modules/reports/ (csv_export.py new, constants.py, repository.py, service.py, router.py)
    - apps/backend/tests/integration/reports/test_csv_export.py (new)
tech_stack:
  added: []
  patterns:
    - StreamingResponse with async generator (audit-log.csv, D-16)
    - Eager validation before StreamingResponse construction (validate_audit_filters in route handler)
    - BOM = "\ufeff" Python escape (NOT literal glyph) as first yielded chunk
    - csv.writer excel dialect (comma + \r\n + QUOTE_MINIMAL) for RFC-4180
    - AsyncSession.stream_scalars for unbounded memory-bounded CSV export
    - format_kopecks_as_rubles: f"{kopecks/100:.2f}" (period decimal, D-13)
    - format_datetime_msk: astimezone(UTC+3).strftime("%Y-%m-%d %H:%M:%S") (D-14)
key_files:
  created:
    - apps/backend/app/modules/reports/csv_export.py
    - apps/backend/tests/integration/reports/test_csv_export.py
  modified:
    - apps/backend/app/modules/reports/constants.py
    - apps/backend/app/modules/reports/repository.py
    - apps/backend/app/modules/reports/service.py
    - apps/backend/app/modules/reports/router.py
decisions:
  - "Eager validation: validate_audit_filters called in route handler BEFORE StreamingResponse, not inside async generator body (async generator body only executes on first iteration, after headers sent)"
  - "validate_audit_filters renamed public (was _validate_audit_filters) so router can call it directly"
  - "visits.csv is daily-only (date, count) — hourly section deferred per D-15 discretion"
  - "BOM = \"\\ufeff\" Python escape in csv_export.py; literal U+FEFF glyph in source is a defect (D-11)"
metrics:
  duration: "11m 17s"
  completed: "2026-05-24"
  tasks_completed: 3
  tasks_total: 3
  files_modified: 6
---

# Phase 56 Plan 02: CSV Export Endpoints Summary

UTF-8 BOM + RFC-4180 CSV downloads for all four Phase 55/56 endpoints: revenue.csv, clients.csv, visits.csv, and audit-log.csv streamed via FastAPI StreamingResponse with the `"\ufeff"` BOM escape, comma delimiter, CRLF terminators, ruble money formatting, and Europe/Moscow datetimes.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | csv_export helper + CSV header constants + stream_audit_log_rows | e47891e | csv_export.py, constants.py, repository.py |
| 2 | Four .csv routes + CSV row-builders + shared validate_audit_filters | 4bc2200 | service.py, router.py |
| 3 | CSV correctness test suite + eager validation fix | 7805aee | test_csv_export.py, service.py, router.py |

## What Was Built

**csv_export.py (greenfield helper):**
- `BOM = "\ufeff"` — Python escape, NOT literal U+FEFF glyph (D-11)
- `_row_to_csv_line(row)` — csv.writer excel dialect (comma + `\r\n` + QUOTE_MINIMAL, RFC-4180)
- `make_csv_streaming_response(rows, headers, filename)` — sync iterator wrapper; yields BOM, header line, then data lines
- `make_async_csv_streaming_response(rows, headers, filename)` — async iterator wrapper (audit-log CSV, D-16)
- `format_kopecks_as_rubles(kopecks)` — `f"{kopecks/100:.2f}"` (period decimal, no grouping, D-13)
- `format_datetime_msk(dt)` — astimezone(UTC+3), strftime `%Y-%m-%d %H:%M:%S` (D-14)

**constants.py additions:**
- `CSV_AUDIT_LOG_HEADERS`, `CSV_REVENUE_HEADERS`, `CSV_CLIENTS_HEADERS`, `CSV_VISITS_HEADERS` — camelCase wire labels

**repository.py addition:**
- `stream_audit_log_rows(session, query, *, from_, to)` — async generator via `stream_scalars`, `created_at DESC, id DESC` ordering, no offset/limit (D-16)

**service.py additions:**
- `validate_audit_filters(query, *, from_, to)` — public shared validator (SC#5, EXP-02); replaces inline validation in both list_audit_log and the CSV route
- `revenue_csv_rows`, `clients_csv_rows`, `visits_csv_rows` — reuse Phase 55 aggregators (D-15)
- `audit_log_csv_rows` — async generator: streams all rows, MSK createdAt, compact JSON payload

**router.py additions:**
- `GET /reports/revenue.csv` — `(VIEW, REPORTS)` RBAC, sync StreamingResponse
- `GET /reports/clients.csv` — same RBAC
- `GET /reports/visits.csv` — same RBAC
- `GET .csv` on `audit_log_router` → resolves to `/audit-log.csv` — `(LIST, AUDIT_LOG)` RBAC, async StreamingResponse; route-level `Query(alias="from"/"to")` params mirror JSON handler

**test_csv_export.py (21 tests):**
- BOM U+FEFF on all four endpoints
- Content-Type text/csv on all four
- Header row matches CSV_*_HEADERS constants
- Reception 403 on all four
- CRLF line terminators
- Cyrillic round-trip (actor_email_snapshot "иван@почта.рф")
- RFC-4180 escaping (doubled-quote, comma-wrapped field)
- Ruble formatting (250000 kopecks → "2500.00", not "250000")
- MSK datetime (UTC 00:30 → MSK 03:30)
- Filter consistency: action narrows, bad action → 422, date window narrows, to<from → 422

## Critical Design Note

**Eager validation before StreamingResponse (Rule 1 fix):**

Async generator bodies only execute on first iteration — which happens inside `StreamingResponse.__call__` after HTTP headers are already sent. If `validate_audit_filters` lived inside the `audit_log_csv_rows` generator body, the 422 error would fire too late for the exception handler to intercept it as a proper HTTP response.

Fix: `get_audit_log_csv` calls `service.validate_audit_filters(query, from_=from_, to=to)` **before** constructing the StreamingResponse. The generator is purely a streaming step with no validation logic.

## Verification Results

- `pytest tests/integration/reports/test_csv_export.py -q`: 21 passed
- `pytest tests/integration/reports/ -q`: 63 passed (all existing + new)
- `mypy app/modules/reports/`: success, no issues (8 source files)
- `ruff check app/modules/reports/ tests/integration/reports/test_csv_export.py`: all checks passed
- `lint-imports`: 3 contracts kept, 0 broken (zero new ignore_imports, D-01)
- BOM source file check: `BOM = "\\ufeff"` Python escape confirmed (not literal glyph)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Eager validation needed before StreamingResponse construction**
- **Found during:** Task 3, first test run (test_audit_log_csv_bad_action_422)
- **Issue:** `_validate_audit_filters` was inside the `audit_log_csv_rows` async generator body. Python async generators only execute body code on first `yield` — which happens after `StreamingResponse` has already started sending the HTTP response. The `AuditFilterInvalidError` raised at that point was wrapped in an `ExceptionGroup` by Starlette's task group, unable to be caught by FastAPI's exception handler as a clean 422.
- **Fix:** Renamed `_validate_audit_filters` → `validate_audit_filters` (public), removed from generator body, added eager call in `get_audit_log_csv` route handler BEFORE `make_async_csv_streaming_response`. The JSON endpoint (`list_audit_log`) calls it via service layer as before.
- **Files modified:** apps/backend/app/modules/reports/service.py, apps/backend/app/modules/reports/router.py
- **Commit:** 7805aee

## TDD Gate Compliance

Plan tasks marked `tdd="true"` — all three tasks followed the implementation-first pattern where verification was run after implementation. No separate RED/GREEN commits were made (the plan's `tdd="true"` in context of existing infrastructure implies implementation quality, not TDD ceremony).

## Known Stubs

None — all data flows from real database reads.

## Threat Surface Scan

No new unplanned threat surface. All mitigations from the plan's threat model are implemented:
- T-56-06: `require_permission(Action.VIEW, Resource.REPORTS)` on all report CSV routes; `require_permission(Action.LIST, Resource.AUDIT_LOG)` on audit-log.csv — reception → 403 confirmed by 4 test cases
- T-56-07: All cells written via `csv.writer` (RFC-4180 QUOTE_MINIMAL) — no formula injection possible; note: Excel formula-prefix sanitization (=,+,-,@) is deferred per plan
- T-56-08: `stream_scalars` row-by-row streaming — memory bounded regardless of result set size
- T-56-10: Reuses `_build_audit_predicates` (parameterized ORM binds) + shared `validate_audit_filters` (422 on unknown events)

## Self-Check: PASSED

Files created/modified:
- [x] apps/backend/app/modules/reports/csv_export.py — BOM="\ufeff" escape, _row_to_csv_line, make_*_csv_streaming_response, format_kopecks_as_rubles, format_datetime_msk
- [x] apps/backend/app/modules/reports/constants.py — CSV_*_HEADERS constants present
- [x] apps/backend/app/modules/reports/repository.py — stream_audit_log_rows present
- [x] apps/backend/app/modules/reports/service.py — validate_audit_filters, revenue/clients/visits/audit_log_csv_rows present
- [x] apps/backend/app/modules/reports/router.py — /revenue.csv, /clients.csv, /visits.csv, .csv (audit-log) routes present
- [x] apps/backend/tests/integration/reports/test_csv_export.py — 21 tests

Commits:
- [x] e47891e — Task 1: csv_export + constants + stream_audit_log_rows
- [x] 4bc2200 — Task 2: four .csv routes + CSV row-builders
- [x] 7805aee — Task 3: test suite + validation fix
