---
phase: 116-chat-inbox-exports
plan: "02"
subsystem: backend/reports
tags: [csv-export, payments, owner-only, streaming-response]
dependency_graph:
  requires: []
  provides:
    - GET /api/v1/reports/payments.csv (StreamingResponse, owner-only, BOM, RFC-4180)
    - CSV_PAYMENTS_HEADERS (constants.py)
    - fetch_payments_for_csv (repository.py)
    - payments_csv_rows (service.py)
  affects:
    - apps/backend/app/modules/reports/constants.py
    - apps/backend/app/modules/reports/repository.py
    - apps/backend/app/modules/reports/service.py
    - apps/backend/app/modules/reports/router.py
    - apps/backend/tests/integration/reports/test_csv_export.py
tech_stack:
  added: []
  patterns:
    - StreamingResponse CSV (no ResponseEnvelope, UTF-8 BOM, RFC-4180)
    - Cross-module raw SQL text() + :name bind params (D-54-08)
    - sanitize_csv_text on free-text cells (CR-01, formula-injection guard)
key_files:
  created: []
  modified:
    - apps/backend/app/modules/reports/constants.py
    - apps/backend/app/modules/reports/repository.py
    - apps/backend/app/modules/reports/service.py
    - apps/backend/app/modules/reports/router.py
    - apps/backend/tests/integration/reports/test_csv_export.py
decisions:
  - "Query params use fromDate/toDate (alias_generator=to_camel convention matching all CSV siblings)"
  - "Client name resolved via correlated subquery: membership/pt_package rows look up client directly; refund rows walk back via refund_of to original payment then resolve client"
  - "Route uses inline Query(alias=...) params (not a schema Depends()) to match the per-endpoint fromDate/toDate pattern used in PATTERNS.md"
metrics:
  duration: "~15 minutes"
  completed: "2026-06-15"
  tasks_completed: 2
  files_modified: 5
---

# Phase 116 Plan 02: Payments CSV Export Summary

Owner-only payments ledger CSV export (`GET /api/v1/reports/payments.csv`) mirroring the existing visits/revenue CSV discipline — StreamingResponse, UTF-8 BOM, RFC-4180, sanitize_csv_text on free-text cells, validated date range, 5 ASGITransport integration tests.

## What Was Built

### Route
- **Path:** `GET /api/v1/reports/payments.csv`
- **Query params:** `fromDate=YYYY-MM-DD` and `toDate=YYYY-MM-DD`
  - FE plan 116-03 must use `fromDate` / `toDate` (NOT `from`/`to`) — these are `Query(alias="fromDate")` inline params matching the `alias_generator=to_camel` convention of all other CSV routes
- **Auth:** `require_permission(Action.VIEW, Resource.REPORTS)` — owner-only; reception → 403
- **Response:** `StreamingResponse` with `media_type='text/csv; charset=utf-8'`, `Content-Disposition: attachment; filename="payments-{fromDate}-{toDate}.csv"`, leading UTF-8 BOM (U+FEFF)
- **Range validation:** `toDate < fromDate → 422`; range > 366 days → `report_range_too_large` 422

### CSV_PAYMENTS_HEADERS (column order for 116-03)

| Index | Column name | Content |
|-------|-------------|---------|
| 0 | `date` | `received_at` in MSK as `YYYY-MM-DD` string |
| 1 | `clientName` | `first_name + ' ' + last_name`; empty string if unresolvable |
| 2 | `amountRubles` | signed rubles with 2 decimals (e.g. `-150.00` for refunds) |
| 3 | `method` | `'cash'` or `'online'` |
| 4 | `subjectKind` | `'membership'`, `'pt_package'`, or `'refund'` |
| 5 | `refundOf` | UUID string of original payment for refund rows; empty string otherwise |
| 6 | `operatorEmail` | email of `received_by_user_id`; empty for online/webhook payments |

### Client Name Resolution Rule

For **sale rows** (`subject_kind IN ('membership', 'pt_package')`): correlated subquery looks up `memberships.client_id` or `pt_packages.client_id` where `memberships/pt_packages.id = p.subject_id`, then joins `clients` (excluding soft-deleted). Returns empty string if no match.

For **refund rows** (`subject_kind = 'refund'`): walks back via `refund_of` to the original payment row, then applies the same membership/pt_package → client lookup to the original row's `subject_id`/`subject_kind`. Returns empty string if no original payment or client found.

For **unknown subject_kind**: returns empty string (forward-compatible — no crash on future subject kinds).

### Repository Query
Raw SQL `text()` with `:from_date`/`:to_date` bind params (D-54-08). LEFT JOIN `users` for operator email (NULL for webhook payments). MSK date via `(received_at AT TIME ZONE 'Europe/Moscow')::date::text`. No `session.commit()` (caller-owns-txn).

### Service Orchestrator
`payments_csv_rows(session, *, from_date, to_date)`: validates range → fetches rows → formats:
- `amountRubles` via `csv_export.format_kopecks_as_rubles`
- `clientName` via `csv_export.sanitize_csv_text` (formula-injection guard)
- `operatorEmail` via `csv_export.sanitize_csv_text` (formula-injection guard)
- `refundOf` as `str(uuid)` or `""`

## Tests Added (test_csv_export.py)

| Test | Assertion |
|------|-----------|
| `test_payments_csv_bom_and_content_type` | Owner 200 + text/csv + first byte = U+FEFF BOM |
| `test_payments_csv_header_row` | Header row = `list(CSV_PAYMENTS_HEADERS)` |
| `test_payments_csv_reception_forbidden` | Reception 403 code=`"forbidden"` |
| `test_payments_csv_cyrillic_roundtrip` | Cyrillic `"Мария Петрова"` appears intact in decoded CSV |
| `test_payments_csv_inverted_range_422` | `fromDate > toDate` → 422 |
| `test_payments_csv_formula_injection_guarded` | clientName starting with `=` is prefixed with `'` |

All 29 CSV export tests pass (24 pre-existing + 5 new).

## Deviations from Plan

None — plan executed exactly as written.

## Threat Mitigations Applied

| Threat ID | Mitigation Applied |
|-----------|--------------------|
| T-116-07 | `require_permission(VIEW, REPORTS)` — reception → 403; test asserts it |
| T-116-08 | `sanitize_csv_text` on `clientName` + `operatorEmail`; formula-injection test passes |
| T-116-09 | All params via `:from_date`/`:to_date` bind params (D-54-08); no interpolation |
| T-116-10 | `_validate_date_range` enforces ≤366-day cap; `StreamingResponse` streams rows |
| T-116-11 | `toDate < fromDate → 422`; inverted-range test asserts it |

## Self-Check: PASSED

Files exist:
- `apps/backend/app/modules/reports/constants.py` — CSV_PAYMENTS_HEADERS present
- `apps/backend/app/modules/reports/repository.py` — fetch_payments_for_csv present
- `apps/backend/app/modules/reports/service.py` — payments_csv_rows present
- `apps/backend/app/modules/reports/router.py` — /payments.csv route present
- `apps/backend/tests/integration/reports/test_csv_export.py` — 5 new tests present

Commits:
- `db439098` — Task 1: CSV_PAYMENTS_HEADERS + fetch_payments_for_csv + payments_csv_rows
- `801fdf93` — Task 2: GET /reports/payments.csv route + ASGITransport tests
