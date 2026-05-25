---
phase: 60-trainer-usage-report
verified: 2026-05-25T00:00:00Z
status: passed
score: 4/4 must-haves verified
overrides_applied: 0
---

# Phase 60: Trainer-Usage Report Verification Report

**Phase Goal:** Owner can view a read-only trainer-usage report covering load, PT-utilization, revenue attribution, and payroll summary with CSV export
**Verified:** 2026-05-25
**Status:** PASSED
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Owner GET /api/v1/reports/trainers returns per-trainer rows ordered session_count DESC; each row has session_count, cancelled_session_count, total_hours, unique_client_count, utilization_pct (NULL when 0 slots); reception receives 403 | VERIFIED | `router.py:218-251` `/trainers` endpoint with `require_permission(Action.VIEW, Resource.REPORTS)`; SQL `ORDER BY session_count DESC, t.full_name ASC, t.id ASC`; `CASE WHEN published_slot_count=0 THEN NULL` for utilization; `test_reception_forbidden_on_trainers_json` PASSED |
| 2 | Each row includes revenue_attribution_note in the response envelope; revenue follows pt_packages.trainer_id (D-58-21); known double-count disclosed | VERIFIED | `TrainerUsageReportResponse.revenue_attribution_note: str = TRAINER_REPORT_REVENUE_NOTE` (schemas.py:277); SQL revenue_agg CTE uses `pkg.trainer_id` not `ps.trainer_id` (repository.py:212-224); PITFALL 6 golden test PASSED |
| 3 | Each row includes total_accrued_kopecks and total_paid_kopecks from trainer_payroll_accruals for the same period; clawbacks net out via signed SUM | VERIFIED | payroll_agg CTE (repository.py:226-236): `COALESCE(SUM(accrual_kopecks), 0)` + `FILTER (WHERE status='paid')`; period overlap `period_start <= :to_date AND period_end >= :from_date` (D-60-05); `test_rpt04_clawback_nets_in_total_accrued` and `test_rpt04_payroll_overlap_includes_straddling_periods` both PASSED |
| 4 | GET /api/v1/reports/trainers.csv streams UTF-8 BOM RFC-4180 CSV; report module has ZERO new import-linter ignores; makes no writes | VERIFIED | `csv_export.py:28 BOM = "﻿"`, `csv.writer(buf, dialect="excel")` (CRLF); `lint-imports` exits 0; `grep -rE "from app.modules.*models"` exits 1 (no cross-module ORM imports); all 4 CSV golden tests PASSED; `test_pitfall_10_no_orm_imports_in_reports_module` PASSED including inline `uv run lint-imports` assertion |

**Score:** 4/4 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `apps/backend/app/modules/reports/schemas.py` | TrainerUsageReportQuery, TrainerUsageRow (11 fields), TrainerUsageReportResponse | VERIFIED | All 3 classes present; 11 fields in TrainerUsageRow; revenue_attribution_note defaults to TRAINER_REPORT_REVENUE_NOTE |
| `apps/backend/app/modules/reports/constants.py` | CSV_TRAINER_USAGE_HEADERS (10-tuple camelCase), TRAINER_REPORT_REVENUE_NOTE | VERIFIED | 10-element tuple confirmed; both in `__all__`; camelCase English convention matches v1.8 |
| `apps/backend/app/modules/reports/repository.py` | fetch_trainer_usage single-CTE raw SQL reader | VERIFIED | Single text() CTE with 4 sub-CTEs (session_agg, slot_agg, revenue_agg, payroll_agg); in `__all__`; no ORM model imports |
| `apps/backend/app/modules/reports/service.py` | get_trainer_usage_report, trainer_usage_csv_rows | VERIFIED | Both functions present; date range validation called; sanitize_csv_text applied to trainer_name_snapshot only; None -> empty string for utilization_pct/avg_revenue_per_session |
| `apps/backend/app/modules/reports/router.py` | GET /trainers JSON + GET /trainers.csv on main router | VERIFIED | Both endpoints on `@router` (not audit_log_router); both gate on `require_permission(Action.VIEW, Resource.REPORTS)` |
| `apps/backend/tests/integration/reports/test_reports_trainers.py` | 20 integration test goldens | VERIFIED | Exactly 20 async test functions; all 4 PITFALL goldens (6/10/11/12) present and named correctly |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| router.get_trainers_report | service.get_trainer_usage_report | `await service.get_trainer_usage_report(session, query)` | WIRED | router.py:250 |
| router.get_trainers_csv | service.trainer_usage_csv_rows | `await service.trainer_usage_csv_rows(session, query)` | WIRED | router.py:287 |
| service.get_trainer_usage_report | repository.fetch_trainer_usage | `await repository.fetch_trainer_usage(session, query.from_date, query.to_date)` | WIRED | service.py:419 |
| service.trainer_usage_csv_rows | service.get_trainer_usage_report | `r = await get_trainer_usage_report(session, query)` | WIRED | service.py:448 (includes date validation) |
| TrainerUsageReportResponse.revenue_attribution_note | constants.TRAINER_REPORT_REVENUE_NOTE | Pydantic field default | WIRED | schemas.py:277; service.py:424 passes explicitly too |
| csv_export.make_csv_streaming_response | CSV_TRAINER_USAGE_HEADERS | router.py:288 | WIRED | Correct 10-element tuple passed |
| service.trainer_usage_csv_rows | csv_export.sanitize_csv_text | Line 451 (trainer_name_snapshot column only) | WIRED | Formula injection protection active for free-text column |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|--------------|--------|-------------------|--------|
| get_trainers_report handler | TrainerUsageReportResponse | `repository.fetch_trainer_usage` via raw SQL CTE (4-CTE JOIN) | Yes — queries 6 tables: trainers, pt_sessions, bookings, trainer_availability_slots, payments/pt_packages, trainer_payroll_accruals | FLOWING |
| get_trainers_csv handler | list[list[object]] rows | `service.trainer_usage_csv_rows` -> `get_trainer_usage_report` -> same DB CTE | Yes — same real DB query path | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| All 20 integration tests | `uv run pytest tests/integration/reports/test_reports_trainers.py -v` | 20 passed in 4.94s | PASS |
| Route introspection (gating) | `uv run pytest tests/integration/test_route_introspection.py -v` | 3 passed in 0.13s | PASS |
| lint-imports | `uv run lint-imports` | 3 contracts kept, 0 broken | PASS |
| Cross-module ORM import guard | `grep -rE "from app.modules.*.models" app/modules/reports/` | exit code 1 (no matches) | PASS |
| Pydantic smoke test | `uv run python -c "..."` (schema validation, nullable fields, envelope default) | All assertions pass | PASS |

### Probe Execution

No conventional probe scripts found for Phase 60. Integration tests and lint gates serve as the probe layer.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|---------|
| RPT-01 | 60-01, 60-02, 60-03, 60-04 | Owner sees trainer load report (session_count, hours, utilization_pct NULL when 0 slots), ordered session_count DESC; reception 403 | SATISFIED | PITFALL 11/12 goldens + ordering golden + reception 403 tests all PASSED |
| RPT-02 | 60-01, 60-02, 60-03, 60-04 | Revenue attribution via pt_packages.trainer_id (assigned-at-sale); double-count disclosed in response envelope | SATISFIED | revenue_agg CTE uses pkg.trainer_id; TRAINER_REPORT_REVENUE_NOTE in response; PITFALL 6 golden PASSED |
| RPT-03 | 60-03, 60-04 | CSV export UTF-8 BOM RFC-4180 excel dialect | SATISFIED | csv.writer dialect="excel" (CRLF); BOM="﻿"; CSV BOM/Cyrillic/formula-injection/NULL-cell goldens all PASSED |
| RPT-04 | 60-01, 60-02, 60-03, 60-04 | total_accrued_kopecks/total_paid_kopecks from trainer_payroll_accruals; ZERO new import-linter ignores | SATISFIED | payroll_agg signed SUM; lint-imports exits 0; PITFALL 10 ship gate PASSED inside test suite; clawback netting golden PASSED |

### D-60 Decision Audit

| Decision | Verified | Evidence |
|----------|----------|---------|
| D-60-01: Reports module, no models.py, zero new ignore_imports, zero writes | PASS | `ls reports/` shows no models.py; lint-imports 0 broken; no session.commit/flush calls |
| D-60-02: ALL cross-module reads via sqlalchemy.text() — no ORM imports | PASS | grep guard exits 1 (no matches); repository.py uses `text()` for all 6 referenced tables |
| D-60-03: Single CTE-driven LEFT JOIN statement; NO is_active filter; secondary order full_name ASC, tertiary t.id ASC | PASS | One text() statement with 4 CTEs; `ORDER BY session_count DESC, t.full_name ASC, t.id ASC`; comment "PITFALL 11: NO is_active filter" |
| D-60-04: total_hours from slot (end_time-start_time) via booking chain; walk-ins contribute 0.0 | PASS | `EXTRACT(EPOCH FROM (s.end_time - s.start_time)) FILTER (WHERE cancelled_at IS NULL)` via LEFT JOIN; walk-in test PASSED |
| D-60-05: Payroll overlap = period_start <= to_date AND period_end >= from_date; no proration | PASS | `WHERE period_start <= :to_date AND period_end >= :from_date`; overlap test PASSED |
| D-60-06: utilization_pct NULL when 0 active|booked slots; 0.0 when slots but no bookings; cancelled excluded from both | PASS | `CASE WHEN COALESCE(sla.published_slot_count, 0) = 0 THEN NULL`; FILTER WHERE status IN ('active','booked') for denominator; both goldens PASSED |
| D-60-07: Revenue note in response envelope from TRAINER_REPORT_REVENUE_NOTE constant | PASS | schemas.py:277 `revenue_attribution_note: str = TRAINER_REPORT_REVENUE_NOTE`; service.py:424 passes explicitly |
| D-60-08: Both endpoints gate on existing (VIEW, REPORTS) OWNER_ONLY pair — no new RBAC entries | PASS | `require_permission(Action.VIEW, Resource.REPORTS)` on both; permissions.py unmodified; route introspection PASSED |
| D-60-09: No pagination — single response with all trainers | PASS | TrainerUsageReportResponse has `trainers: list[TrainerUsageRow]` without page/pageSize |
| D-60-10: Zero new LOCKED_AUDIT_EVENTS | PASS | No trainer_report_viewed or similar event found in audit.py; Phase 60 added 0 audit events |
| D-60-11: CSV BOM "﻿" (escape not glyph); CRLF; None -> empty cell; sanitize_csv_text on trainer_name_snapshot; money as "%.2f" rubles | PASS | csv_export.py: BOM="﻿"; dialect="excel"; service.py:456 `"" if row.utilization_pct is None`; sanitize applied on line 451; format_kopecks_as_rubles used |
| D-60-12: Both endpoints on main router (not audit_log_router); mounted under /api/v1/reports/ | PASS | `@router.get("/trainers"...)` and `@router.get("/trainers.csv"...)`; api/v1/router.py mounts `reports_router` under `/reports` |
| D-60-13: PITFALL goldens 6/10/11/12 mandatory; module-level REPORTS_DIR with is_dir() assertion | PASS | All 4 named PITFALL test functions present; module-level REPORTS_DIR with is_dir() guard at line 66-71 |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| None | — | No TBD/FIXME/XXX/TODO/HACK/PLACEHOLDER markers in any Phase 60 source file | — | None |

No anti-patterns detected. All Phase 60 source files are clean.

### Human Verification Required

None. All success criteria are programmatically verifiable. The 20 integration tests against a real Postgres instance + Redis cover all observable behaviors end-to-end.

### Gaps Summary

No gaps. All 4 success criteria are fully achieved:

1. SC-1 (load report + ordering + reception 403): JSON endpoint returns per-trainer rows with all 11 locked fields, ordered `session_count DESC, full_name ASC, id ASC`; reception receives 403 on both JSON and CSV endpoints. All 4 PITFALL golden tests confirm the behavioral correctness.

2. SC-2 (revenue attribution + double-count disclosure): `revenue_attribution_note` is in the response envelope (defaulted from `TRAINER_REPORT_REVENUE_NOTE`); revenue CTE uses `pkg.trainer_id` exclusively (PITFALL 6 golden confirms trainer B conducting but not assigned gets 0 revenue).

3. SC-3 (payroll fold-in): `total_accrued_kopecks` and `total_paid_kopecks` computed from `trainer_payroll_accruals` with signed sum (clawback netting golden: 50000 - 30000 = 20000); period overlap golden (straddle includes full amount) confirmed.

4. SC-4 (CSV BOM + RFC-4180 + ZERO new ignore_imports): CSV starts with U+FEFF, `csv.writer(dialect="excel")` provides CRLF, Cyrillic renders correctly, formula injection sanitized, NULL cells empty; lint-imports exits 0 with 0 broken contracts; both PITFALL 10 grep guard (exit 1) and `uv run lint-imports` assertion pass inside the test suite itself.

---

_Verified: 2026-05-25_
_Verifier: Claude (gsd-verifier)_
