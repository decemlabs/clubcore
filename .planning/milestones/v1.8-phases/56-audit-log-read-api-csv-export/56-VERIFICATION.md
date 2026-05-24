---
phase: 56-audit-log-read-api-csv-export
verified: 2026-05-24T21:30:00Z
status: passed
score: 10/10 must-haves verified
overrides_applied: 0
---

# Phase 56: Audit Log Read API + CSV Export Verification Report

**Phase Goal:** Owner can browse and filter the full audit log through a paginated JSON endpoint and download any report or audit log as a UTF-8 BOM CSV suitable for Excel.
**Verified:** 2026-05-24T21:30:00Z
**Status:** passed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths (from ROADMAP Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| SC1 | GET /api/v1/audit-log returns {items,total,page,pageSize} ordered created_at DESC, id DESC; reception → 403; owner sees all event kinds | VERIFIED | `router.py:220-251`: `audit_log_router.get("")` with `require_permission(LIST, AUDIT_LOG)`; `repository.py:326-327`: `.order_by(AuditLog.created_at.desc(), AuditLog.id.desc())`; 15 passing tests inc. `test_reception_forbidden`, `test_ordering_created_at_desc` |
| SC2 | Filters actorUserId / actorEmailSnapshot (substring) / resource_type / action / from-to (Europe/Moscow) narrow and combine | VERIFIED | `repository.py:260-289`: `_build_audit_predicates` builds AND-combined predicates; ilike with ILIKE metachar escaping (WR-01 fix); MSK cast via `func.timezone("Europe/Moscow", ...)`. Tests: `test_action_filter_narrows`, `test_cyrillic_actor_email_snapshot_filter`, `test_msk_date_window_filter` |
| SC3 | Pagination stable across inserts (created_at DESC, id DESC keyset) | VERIFIED | `repository.py:326-327`: dual-column keyset ordering; `test_pagination_stability_under_concurrent_insert`: seeds 12 rows, inserts older row, asserts page1/page2 sets unchanged |
| SC4 | CSV download endpoints stream UTF-8 BOM, RFC-4180 escaping, Cyrillic round-trip, money as rubles, Europe/Moscow dates | VERIFIED | `csv_export.py`: BOM="(U+FEFF)", `_row_to_csv_line` uses `csv.writer(dialect="excel")`, `format_kopecks_as_rubles`, `format_datetime_msk`. 21 passing tests inc. `test_revenue_csv_ruble_formatting`, `test_audit_log_csv_msk_datetime`, `test_audit_log_csv_cyrillic_round_trip`, `test_audit_log_csv_rfc4180_escaping` |
| SC5 | CSV audit export accepts same filter params as JSON endpoint, produces consistent results | VERIFIED | `router.py:259-302`: audit-log.csv has route-level `Query(alias="from"/"to")` params identical to JSON handler; `service.validate_audit_filters` called eagerly before `StreamingResponse` (prevents late 422 errors). Tests: `test_audit_log_csv_action_filter_narrows`, `test_audit_log_csv_bad_action_422`, `test_audit_log_csv_date_window_narrows`, `test_audit_log_csv_to_before_from_422` |

**Score:** 5/5 roadmap success criteria verified

### Plan Must-Haves (AUD-01..06 from Plan 01)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Owner GET /api/v1/audit-log returns {items,total,page,pageSize} via ORM select(AuditLog) | VERIFIED | `repository.py:293-337`: `fetch_audit_log_page` with `PaginatedData.model_construct`; `test_owner_gets_audit_log` asserts shape |
| 2 | Results ordered created_at DESC, id DESC | VERIFIED | `repository.py:326-327`; `test_ordering_created_at_desc` |
| 3 | Reception receives 403 via require_permission(LIST, AUDIT_LOG) | VERIFIED | `router.py:228-231`; `test_reception_forbidden` asserts 403 + code="forbidden" |
| 4 | All filters narrow and combine with AND; from/to MSK day-bounds | VERIFIED | `repository.py:258-289`; service validation; all filter tests pass |
| 5 | Unknown action/resource_type → 422 audit_filter_invalid | VERIFIED | `service.py:283-292`: raises `AuditFilterInvalidError`; `test_unknown_action_filter_422`, `test_unknown_resource_type_filter_422` |
| 6 | to < from → 422 | VERIFIED | `service.py:294-295`; `test_to_before_from_422` |
| 7 | Wire params are literally `from` and `to` via route-level Query(alias=...) | VERIFIED | `router.py:226-227`: `Annotated[date | None, Query(alias="from")]`; `test_literal_from_to_params_bind` |
| 8 | Owner sees full payload JSONB in AuditLogItem (D-09 camelCase fields) | VERIFIED | `schemas.py:202-217`: `AuditLogItem` with all fields; `test_audit_log_item_fields` asserts all 8 camelCase keys |

### Plan Must-Haves (EXP-01..04 from Plan 02)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | All four .csv routes stream CSV with BOM | VERIFIED | `router.py:143-302`: 4 routes; `csv_export.make_csv_streaming_response`/`make_async_csv_streaming_response` yield BOM first; 4 BOM tests pass |
| 2 | UTF-8 BOM + RFC-4180 + Cyrillic round-trip + rubles + MSK dates | VERIFIED | `csv_export.py`: all formatters present; full test coverage in `test_csv_export.py` |

---

## Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `apps/backend/app/modules/reports/schemas.py` | AuditLogQuery + AuditLogItem DTOs | VERIFIED | Both classes present (lines 179-217); AuditLogQuery has max_length=254 on actor_email_snapshot (WR-02 fix) |
| `apps/backend/app/modules/reports/repository.py` | fetch_audit_log_page + stream_audit_log_rows ORM path | VERIFIED | Both functions present; ILIKE metachar escaping (WR-01 fix); and_(true(), *predicates) safety |
| `apps/backend/app/modules/reports/service.py` | list_audit_log + validate_audit_filters + CSV helpers | VERIFIED | All functions present; validate_audit_filters is public (callable from router for eager validation) |
| `apps/backend/app/modules/reports/router.py` | audit_log_router (JSON + CSV) + 3 report CSV routes | VERIFIED | 4 CSV routes + 1 JSON audit route; all with require_permission |
| `apps/backend/app/modules/reports/csv_export.py` | BOM + RFC-4180 + StreamingResponse helpers + formatters | VERIFIED | All functions present; BOM="(U+FEFF)" escape (not literal glyph); sanitize_csv_text (CR-01 fix) |
| `apps/backend/app/modules/reports/constants.py` | 4 CSV header tuples | VERIFIED | CSV_AUDIT_LOG_HEADERS, CSV_REVENUE_HEADERS, CSV_CLIENTS_HEADERS, CSV_VISITS_HEADERS all present in __all__ |
| `apps/backend/app/api/v1/router.py` | audit_log_router mounted at /audit-log | VERIFIED | Line 80: `v1.include_router(audit_log_router, prefix="/audit-log", tags=["audit-log"])` |
| `apps/backend/tests/integration/reports/test_audit_log.py` | 15 AUD test cases | VERIFIED | 15 tests present; all pass |
| `apps/backend/tests/integration/reports/test_csv_export.py` | 21 CSV correctness tests | VERIFIED | 21 tests present; includes formula injection + 401 auth tests from CR-01/IN-01 |
| `apps/backend/tests/integration/reports/conftest.py` | make_audit_log_row fixture | VERIFIED | Present at line 103; ORM inserts AuditLog with explicit created_at |

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `app/api/v1/router.py` | `audit_log_router` | `v1.include_router(audit_log_router, prefix="/audit-log")` | WIRED | Line 80 confirmed |
| `reports/router.py` | `service.list_audit_log` | `await service.list_audit_log(session, query, from_=from_, to=to)` | WIRED | Router line 250 |
| `reports/router.py` | `service.validate_audit_filters` (eager) | `service.validate_audit_filters(query, from_=from_, to=to)` before StreamingResponse | WIRED | Router line 297 — critical for 422 on CSV |
| `reports/service.py` | `repository.fetch_audit_log_page` | `await repository.fetch_audit_log_page(session, query, from_=from_, to=to)` | WIRED | service.py line 322 |
| `reports/service.py` | `repository.stream_audit_log_rows` | `async for row in repository.stream_audit_log_rows(...)` | WIRED | service.py line 432 |
| `reports/repository.py` | `AuditLog` ORM | `select(AuditLog).where(...).order_by(AuditLog.created_at.desc(), AuditLog.id.desc())` | WIRED | repository.py lines 322-330 |
| `reports/router.py` | `csv_export.make_(async_)csv_streaming_response` | All 4 CSV routes call the helper | WIRED | router.py lines 165, 188, 212, 300 |
| `reports/service.py` | `csv_export.format_kopecks_as_rubles` | `csv_export.format_kopecks_as_rubles(b.net_kopecks)` etc. | WIRED | service.py lines 354-360 |

---

## Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `list_audit_log` in router | `result` (PaginatedData) | `service.list_audit_log` → `repository.fetch_audit_log_page` → `select(AuditLog)` ORM query with COUNT + keyset SELECT | DB rows converted to AuditLogItem DTOs | FLOWING |
| `get_audit_log_csv` in router | async row stream | `service.audit_log_csv_rows` → `repository.stream_audit_log_rows` → `session.stream_scalars(select(AuditLog)...)` | Real DB cursor streaming | FLOWING |
| `get_revenue_csv` | row list | `service.revenue_csv_rows` → `service.get_revenue_report` → `repository.fetch_revenue_buckets` raw SQL | Real payments table query | FLOWING |

---

## Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| AuditLogQuery validates without from_/to fields | `python -c "from app.modules.reports.schemas import AuditLogQuery; q=AuditLogQuery.model_validate({'actorEmailSnapshot':'ivan','page':2}); assert q.actor_email_snapshot=='ivan' and q.page==2"` | Assertion passes | PASS |
| BOM is "(U+FEFF)" Python escape | `python -c "from app.modules.reports.csv_export import BOM; assert BOM=='(U+FEFF)'"` | Assertion passes | PASS |
| format_kopecks_as_rubles(250000)=="2500.00" | verified in spot-check script | "2500.00" | PASS |
| format_datetime_msk UTC 00:30 → MSK 03:30 | verified in spot-check script | "2026-03-01 03:30:00" | PASS |
| sanitize_csv_text("=bad") → "'=bad" | verified in spot-check script | quote-prefixed | PASS |
| All 70 integration tests | `uv run pytest tests/integration/reports/ tests/integration/clients/test_audit_writes.py -q` | 70 passed in 13.63s | PASS |
| mypy strict | `uv run mypy app/modules/reports/` | Success, no issues in 8 source files | PASS |
| ruff | `uv run ruff check app/modules/reports/ tests/integration/reports/` | All checks passed | PASS |
| import-linter | `uv run lint-imports` | 3 contracts KEPT, 0 broken | PASS |

---

## Probe Execution

No phase-declared probes. Phase 56 does not use `scripts/*/tests/probe-*.sh`. Runnable verification is the `pytest` suite above.

---

## Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| AUD-01 | Plan 01 | GET /api/v1/audit-log paginated {items,total,page,pageSize} | SATISFIED | router + repository + service; test_owner_gets_audit_log |
| AUD-02 | Plan 01 | Filter by actorUserId and actorEmailSnapshot (substring) | SATISFIED | _build_audit_predicates ilike; test_cyrillic_actor_email_snapshot_filter |
| AUD-03 | Plan 01 | Filter by resource_type and action, validated against LOCKED_AUDIT_EVENTS | SATISFIED | VALID_ACTIONS/VALID_RESOURCE_TYPES; AuditFilterInvalidError 422; 2 filter tests |
| AUD-04 | Plan 01 | Filter by from/to time-window in Europe/Moscow | SATISFIED | MSK cast in predicates; test_msk_date_window_filter |
| AUD-05 | Plan 01 | Reception 403 on /audit-log and /reports/* | SATISFIED | require_permission on all routes; 5 reception-403 tests (1 JSON + 4 CSV) |
| AUD-06 | Plan 01 | Results ordered deterministically (created_at DESC, id DESC) | SATISFIED | ORDER BY in both fetch_audit_log_page and stream_audit_log_rows; test_ordering_created_at_desc + test_pagination_stability |
| EXP-01 | Plan 02 | CSV export revenue report | SATISFIED | GET /reports/revenue.csv; test_revenue_csv_* |
| EXP-02 | Plan 02 | CSV export audit-log with same filters as JSON | SATISFIED | audit-log.csv with route-level from/to; validate_audit_filters shared; all filter parity tests pass |
| EXP-03 | Plan 02 | CSV export clients + visits reports | SATISFIED | GET /reports/clients.csv and /reports/visits.csv; header row tests pass |
| EXP-04 | Plan 02 | UTF-8 BOM + RFC-4180 + rubles + MSK dates | SATISFIED | csv_export.py all formatters; 21 CSV tests including BOM, escaping, rubles, MSK |

---

## Code Review Mitigations Verified

The code review (56-REVIEW.md) found 1 Critical + 2 Warnings + 2 Info. All were addressed in commit `3e9beed`.

| Finding | Fix Verified In Code |
|---------|---------------------|
| CR-01 (CSV formula injection) | `csv_export.py:38-59`: `sanitize_csv_text()` with `_CSV_FORMULA_TRIGGERS`; applied to `actor_email_snapshot` and `payload` in `service.py:440,444`; `test_audit_log_csv_formula_injection_sanitized` passes |
| WR-01 (ILIKE wildcard injection) | `repository.py:267-274`: backslash, %, _ escaped before ILIKE; `ilike(..., escape="\\")` |
| WR-02 (actor_email_snapshot unconstrained length) | `schemas.py:197`: `Field(default=None, max_length=254)` |
| IN-01 (no 401 tests on CSV endpoints) | `test_csv_export.py:504-515`: `test_csv_endpoints_require_auth` parametrized over all 4 CSV paths; `test_audit_writes.py:178-195`: `test_audit_log_endpoint_requires_auth` covers JSON endpoint |
| IN-02 (vacuous status-in-(200,422) wire assertion) | `test_audit_log.py:120-129`: replaced with deterministic assertion that `fromDate`/`toDate` return unfiltered set (not a narrower window) |

---

## Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| None | — | No TBD/FIXME/XXX/placeholder anti-patterns found in Phase 56 files | — | — |

Scanned: csv_export.py, schemas.py, repository.py, service.py, router.py, constants.py, test_audit_log.py, test_csv_export.py, conftest.py.

---

## Human Verification Required

None. All phase-defined behaviors are verifiable programmatically and all tests pass.

---

## Gaps Summary

No gaps. All 10 must-have requirement IDs (AUD-01..06, EXP-01..04) are satisfied. All 5 ROADMAP success criteria are verified in code. The test suite (70 tests) passes cleanly. Static analysis (mypy strict, ruff, import-linter) is clean.

**Note on "69 event kinds" in goal text:** `LOCKED_AUDIT_EVENTS` currently has 85 pairs (84 unique actions), not 69. The count in the phase goal is stale — phases subsequent to the goal's authoring added new events. The endpoint correctly exposes ALL events in the locked set; the filter validation uses the live frozenset, so this is not a regression.

**Items explicitly out of scope for Phase 56 (Phase 57 work, not gaps):**
- OpenAPI byte-stable regen (`openapi.json` + `schema.d.ts`) — HND-01 → Phase 57
- `AssertNonNever` forward-guards — HND-02 → Phase 57
- Operator runbook with live `docker compose` — VER-01 → Phase 57

---

_Verified: 2026-05-24T21:30:00Z_
_Verifier: Claude (gsd-verifier)_
