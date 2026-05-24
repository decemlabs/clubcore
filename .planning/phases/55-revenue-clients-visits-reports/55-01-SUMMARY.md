---
phase: 55-revenue-clients-visits-reports
plan: "01"
subsystem: reports
tags: [reports, revenue, rbac, owner-only, read-only, aggregate, kopecks, europe-moscow]
dependency_graph:
  requires:
    - Phase 54 (reports module scaffold, RBAC OWNER_ONLY, ix_payments_received_at)
    - Phase 32 (payments ledger + Payment model)
  provides:
    - GET /api/v1/reports/revenue endpoint (REV-01..05)
    - reports module contracts: constants, all-three query/response DTOs
    - ReportRangeTooLargeError validation guard
    - reports test package (conftest + make_payment_ledger fixture)
  affects:
    - app/api/v1/router.py (reports_router mounted)
    - Phase 55 plans 02-03 (depend on contracts and test package from this plan)
tech_stack:
  added: []
  patterns:
    - raw-SQL cross-module aggregate reader (D-54-08 / D-49-03 precedent)
    - BackendSchemaBase query DTOs with alias_generator=to_camel (camelCase wire)
    - ResponseEnvelope[T] aggregate wrapping (no PaginatedData)
    - ValidationAppError subclass for domain-specific 422 (ReportRangeTooLargeError)
    - SAVEPOINT-mode fixture with make_payment_ledger for deterministic date windows
key_files:
  created:
    - apps/backend/app/modules/reports/constants.py
    - apps/backend/app/modules/reports/schemas.py
    - apps/backend/app/modules/reports/service.py
    - apps/backend/app/modules/reports/repository.py
    - apps/backend/app/modules/reports/router.py
    - apps/backend/tests/integration/reports/__init__.py
    - apps/backend/tests/integration/reports/conftest.py
    - apps/backend/tests/integration/reports/test_reports_revenue.py
  modified:
    - apps/backend/app/api/v1/router.py
decisions:
  - "Query param wire format is fromDate/toDate (camelCase) not from/to — FastAPI Depends() uses Python field names with alias_generator, not Field(alias=...)"
  - "refundKopecks NOT added per D-01 default — refunds fold into netKopecks only, no per-bucket refund transparency field"
  - "No Alembic migration — revenue runs on existing ix_payments_received_at (D-13 default)"
  - "within validation deferred to service layer for ClientsReportQuery (not Pydantic ge/le) for consistent 422 error codes"
metrics:
  duration: "~25 minutes"
  completed: "2026-05-24"
  tasks_completed: 3
  files_count: 9
---

# Phase 55 Plan 01: Reports Module Contracts + Revenue Endpoint Summary

Revenue report endpoint end-to-end with nested period buckets, refund netting, MSK date discipline, and all-three report DTOs ready for Plan 55-02.

## What Was Built

### Task 1: Module contracts — constants + all-three DTOs + validation guard

- `constants.py`: `GRAIN_DAY = "day"`, `GRAIN_MONTH = "month"`, `GRAIN_VALUES` tuple
- `schemas.py`: All three query DTOs (RevenueReportQuery, ClientsReportQuery, VisitsReportQuery) extending `BackendSchemaBase`; all three response DTOs (RevenueReportResponse with nested buckets, ClientsReportResponse flat counters, VisitsReportResponse composite) extending `ResponseData`
- `service.py`: `ReportRangeTooLargeError(ValidationAppError)` with `code="report_range_too_large"` (locked per D-06); `_validate_date_range()` guard raising 422 for `to<from` and >366 days

### Task 2: Revenue repository + service pivot + router + v1 mount

- `repository.py`: `fetch_revenue_buckets()` raw-SQL reader — GROUP BY period/method/subject_kind, f-string period_expr chosen from internal literal branch (GRAIN_DAY/GRAIN_MONTH), all user values bound via `:from_date`/`:to_date` params (T-55-02 SQLi mitigation)
- `service.py`: `get_revenue_report()` + `_pivot_revenue_buckets()` — refunds (subject_kind='refund') fold into `net_kopecks` but are excluded from `by_subject_kind` (D-01)
- `router.py`: `GET /revenue` with `Depends(require_permission(Action.VIEW, Resource.REPORTS))` → reception 403
- `app/api/v1/router.py`: `reports_router` mounted at `prefix="/reports"` after `visits_router`

### Task 3: Revenue test package — conftest + correctness suite (9 tests)

- `conftest.py`: Re-exports memberships fixtures + `make_payment_ledger` factory for deterministic timestamp-pinned payment rows
- `test_reports_revenue.py`: 9 tests covering REV-01..05, SC#4, D-01, D-05, D-06

## Key Decisions

### D-01: refundKopecks NOT added

Decision: net-only per the D-01 default. Refunds fold into `netKopecks` via signed `SUM(amount_kopecks)`. The `bySubjectKind` breakdown contains only positive sale amounts (`membership`, `pt_package`) — refund rows do not appear there. No `refundKopecks` per-bucket field was added (deferred to v2.0 if owner requests transparency).

### Wire format: fromDate/toDate not from/to

The 55-CONTEXT.md specified `?from=&to=` but FastAPI 0.136 with Pydantic v2 `Depends()` cannot use `Field(alias="from")` for query param naming — it uses Python field names (or alias_generator). Since `BackendSchemaBase` has `alias_generator=to_camel`, field `from_date` becomes `fromDate` query param. This is consistent with the camelCase wire convention already used throughout the API. All tests use `?fromDate=&toDate=&groupBy=`.

### No Alembic migration (D-13)

Revenue aggregate runs on existing `ix_payments_received_at DESC` index. No new migration created per D-13 default (evidence-based: single-gym volume is low; composite index deferred to when EXPLAIN ANALYZE shows seq scan).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed Field(alias="from") incompatibility with FastAPI Depends()**
- **Found during:** Task 2 verification (pytest run)
- **Issue:** `Field(alias="from")` + `BackendSchemaBase` + `Depends()` causes FastAPI to use the Python field name (`from_date`) as the query param, not the alias (`from`). FastAPI `Depends()` generates query params from field names / `alias_generator`, not `Field(alias=...)`.
- **Fix:** Removed all `Field(alias="from")` / `Field(alias="to")` from query DTOs. Used plain `from_date`/`to_date` field names which BackendSchemaBase maps to `fromDate`/`toDate` via `alias_generator=to_camel`.
- **Files modified:** `schemas.py`, `test_reports_revenue.py`
- **Commit:** `e18d4d6` (schemas updated as part of Task 2 commit)

**2. [Rule 2 - Missing Critical] Added noqa: S608 for SQL injection warning on period_expr**
- **Found during:** ruff check on repository.py
- **Issue:** ruff S608 flagged the f-string `f"SELECT {period_expr} AS..."` as potential SQL injection
- **Fix:** Added `# noqa: S608 — period_expr is chosen from internal literals (GRAIN_DAY/GRAIN_MONTH)` comment. The f-string is safe — period_expr is selected via an internal `if query.group_by == GRAIN_DAY` branch on a validated `Literal["day","month"]` enum, never from raw user input.
- **Files modified:** `repository.py`
- **Commit:** `e18d4d6`

## Threat Mitigations Applied

| Threat | Mitigation | Verified |
|--------|-----------|----------|
| T-55-01 Elevation of Privilege | `Depends(require_permission(Action.VIEW, Resource.REPORTS))` | reception 403 test passes |
| T-55-02 SQL Injection | period_expr from internal literal branch; from_date/to_date bound params | ruff S608 noqa documented |
| T-55-03 DoS via range | 366-day cap → 422 report_range_too_large | test_range_over_366_days_returns_422_with_code passes |

## Test Results

```
9 passed in 1.69s
```

All tests pass:
- `test_owner_gets_revenue_report` — REV-01 owner 200
- `test_reception_forbidden` — SC#4 reception 403
- `test_net_revenue_zero_after_full_refund` — REV-04 canonical (netKopecks == 0)
- `test_by_method_positive_sale_amounts_refund_excluded_from_subject_kind` — D-01
- `test_group_by_month_collapses_buckets` — REV-02 groupBy=month
- `test_to_before_from_returns_422` — D-05
- `test_range_over_366_days_returns_422_with_code` — D-06
- `test_missing_from_date_param_returns_422` — D-05
- `test_missing_to_date_param_returns_422` — D-05

## Known Stubs

None. All wired to real data sources (payments table via raw SQL).

## Self-Check: PASSED

Files exist:
- `apps/backend/app/modules/reports/constants.py` — FOUND
- `apps/backend/app/modules/reports/schemas.py` — FOUND
- `apps/backend/app/modules/reports/service.py` — FOUND
- `apps/backend/app/modules/reports/repository.py` — FOUND
- `apps/backend/app/modules/reports/router.py` — FOUND
- `apps/backend/tests/integration/reports/__init__.py` — FOUND
- `apps/backend/tests/integration/reports/conftest.py` — FOUND
- `apps/backend/tests/integration/reports/test_reports_revenue.py` — FOUND

Commits exist:
- `2e154af` feat(55-01): constants + DTOs + validation guard — FOUND
- `e18d4d6` feat(55-01): repository + service + router + mount — FOUND
- `b2ab7ab` test(55-01): test package — FOUND
