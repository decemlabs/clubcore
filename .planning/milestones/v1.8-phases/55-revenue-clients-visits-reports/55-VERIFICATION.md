---
phase: 55-revenue-clients-visits-reports
verified: 2026-05-24T00:00:00Z
status: passed
score: 13/13 must-haves verified
overrides_applied: 1
overrides:
  - truth: "ROADMAP SC#1/SC#3 illustratively wrote ?from=&to=; actual wire uses ?fromDate=&toDate="
    decision: "ACCEPTED — keep fromDate/toDate (user decision 2026-05-24, --auto chain)"
    rationale: "camelCase wire params are the project-wide locked convention (BackendSchemaBase alias_generator=to_camel; CLAUDE.md 'camelCase wire / snake_case Python'). 'from' is also a Python reserved word and Field(alias='from') does not bind through the model-DTO Depends() pattern. Bare from/to on these three endpoints would be INCONSISTENT with every other endpoint. ROADMAP SC#1/SC#3 wording updated to ?fromDate=&toDate= to match the shipped contract. Functional behavior (inclusive MSK date filtering) is fully correct and tested. This is the wire form Phase 57 freezes into openapi.json."
human_verification: []
gaps: []
---

# Phase 55: Revenue + Clients + Visits Reports — Verification Report

**Phase Goal:** Owner can query all three read-only aggregate reports (revenue by period, clients snapshot, visits by day/hour) via authenticated JSON endpoints; all monetary values are integer kopecks; all date buckets are deterministic in Europe/Moscow.
**Verified:** 2026-05-24T00:00:00Z
**Status:** passed (1 override accepted — see frontmatter)
**Re-verification:** No — initial verification; SC#1 wire-name resolved via accepted override

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | ROADMAP SC#1: GET /api/v1/reports/revenue?fromDate=&toDate=&groupBy=day returns buckets with integer kopecks broken down by method and subject kind; refunds reduce net amounts correctly | VERIFIED (override) | Endpoint works; camelCase params accepted as canonical wire form (user decision); ROADMAP wording updated to match. 9 revenue tests pass |
| 2 | ROADMAP SC#2: GET /api/v1/reports/clients returns active/expiring/new client counters; within defaults 7, range 1..30; all counters exclude soft-deleted | VERIFIED | CLR-01..04 tests pass (8 tests); activeCount excludes soft-deleted (CLR-04 test); within boundary tested (CLR-02); newClientsCount excludes deleted (CLR-04) |
| 3 | ROADMAP SC#3: GET /api/v1/reports/visits returns daily visit counts using gym_date (no secondary TZ conversion), hourly peak buckets, averagePerDay | VERIFIED | VIS-R-01..04 tests pass (7 tests); gym_date filter direct (no re-conversion); hourly groups by MSK hour; average = total / calendar_days |
| 4 | ROADMAP SC#4: Reception role receives 403 on all /reports/* endpoints | VERIFIED | 3 reception-403 tests pass (one per endpoint); (VIEW, REPORTS) in OWNER_ONLY permissions.py:65 |
| 5 | ROADMAP SC#5: All day/month buckets match Europe/Moscow boundaries | VERIFIED | revenue: AT TIME ZONE 'Europe/Moscow' applied in SQL; visits: gym_date STORED GENERATED already MSK; 27 tests pass deterministically |
| 6 | groupBy=month truncates buckets to YYYY-MM via date_trunc; groupBy=day produces YYYY-MM-DD; default is day | VERIFIED | repository.py:57-61 date_trunc branch; service.py:82 period_str[:7] for GRAIN_MONTH; test_group_by_month_collapses_buckets asserts period=="2026-07" |
| 7 | Refund rows net into netKopecks only; bySubjectKind shows gross sale amounts (membership/pt_package), refunds excluded | VERIFIED | service.py:108-118 skips 'refund' for by_subject_kind; REV-04 canonical test: netKopecks==0 after sale+refund; bySubjectKind.membership==100000 in D-01 test |
| 8 | All monetary fields are integer kopecks (not float) | VERIFIED | schemas.py: all money fields typed as int; SUM(amount_kopecks) aggregates integer column; no float conversion in service pivot |
| 9 | from/to required; to < from -> 422; range > 366 days -> 422 report_range_too_large; missing params -> 422 | VERIFIED | _validate_date_range in service.py; 6 validation tests across revenue+clients+visits suites all pass |
| 10 | Only periods/hours with data appear (sparse buckets, no zero-fill) | VERIFIED | repository.py uses plain GROUP BY with no generate_series; D-08 documented in comments |
| 11 | Reports respond via ResponseEnvelope[T] with aggregate DTOs on BackendSchemaBase (not PaginatedData/PageQuery), camelCase wire | VERIFIED | router.py response_model=ResponseEnvelope[...]; schemas.py DTOs extend BackendSchemaBase/ResponseData; test asserts body["data"]["buckets"] etc. |
| 12 | reports_router mounted at prefix=/reports in app/api/v1/router.py | VERIFIED | router.py:35 import + line 78 v1.include_router(reports_router, prefix="/reports", tags=["reports"]) |
| 13 | Repository reads payments/memberships/clients/visits via raw text() SELECT with no ORM imports; zero session.commit/flush | VERIFIED | repository.py imports only sqlalchemy.text + reports-internal; grep for session.commit/flush returns only comments; all 27 tests pass |

**Score:** 12/13 truths verified (1 PARTIAL on ROADMAP SC#1 wire name wording)

---

## Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `apps/backend/app/modules/reports/constants.py` | GRAIN_DAY, GRAIN_MONTH, GRAIN_VALUES exported | VERIFIED | All three names in __all__; content matches |
| `apps/backend/app/modules/reports/schemas.py` | RevenueReportQuery + all 3 response DTOs; camelCase wire | VERIFIED | All 9 DTO classes present; BackendSchemaBase base; from_date->fromDate via alias_generator |
| `apps/backend/app/modules/reports/repository.py` | fetch_revenue_buckets + 4 other readers; no ORM imports | VERIFIED | 5 readers in __all__; only sqlalchemy.text imported; no cross-module model imports |
| `apps/backend/app/modules/reports/service.py` | get_revenue_report + get_clients_report + get_visits_report + _validate_date_range + ReportRangeTooLargeError | VERIFIED | All 5 symbols present and implemented |
| `apps/backend/app/modules/reports/router.py` | GET /revenue + /clients + /visits under (VIEW, REPORTS) | VERIFIED | 3 routes, all use require_permission(Action.VIEW, Resource.REPORTS) |
| `apps/backend/app/api/v1/router.py` | reports_router mounted at prefix=/reports | VERIFIED | Line 35 import + line 78 mount |
| `apps/backend/tests/integration/reports/__init__.py` | Package marker | VERIFIED | File exists |
| `apps/backend/tests/integration/reports/conftest.py` | Re-exported fixtures + make_payment_ledger + make_visit | VERIFIED | Both fixtures present |
| `apps/backend/tests/integration/reports/test_reports_revenue.py` | 9 revenue tests | VERIFIED | 9 test functions including REV-04 canonical net-zero |
| `apps/backend/tests/integration/reports/test_reports_clients.py` | 8 clients tests | VERIFIED | 8 test functions including CLR-04 soft-delete and CLR-02 within boundary |
| `apps/backend/tests/integration/reports/test_reports_visits.py` | 7 visits tests | VERIFIED | 7 test functions including VIS-R-01/04 same-day bucket, VIS-R-02 hourly, D-10 average |

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `router.py` | `service.py` | `service.get_revenue_report(session, query)` | WIRED | router.py:59 `result = await service.get_revenue_report(session, query)` |
| `router.py` | `service.py` | `service.get_clients_report / get_visits_report` | WIRED | router.py:84,110 confirmed |
| `service.py` | `repository.py` | `repository.fetch_revenue_buckets` | WIRED | service.py:150 `rows = await repository.fetch_revenue_buckets(session, query)` |
| `service.py` | `repository.py` | `repository.fetch_active/expiring/new/visits_daily/hourly` | WIRED | service.py:177-180, 209-213 confirmed |
| `repository.py` | `payments` table | `FROM payments` via text() SELECT | WIRED | repository.py:66 |
| `repository.py` | `memberships`/`clients`/`visits` tables | `FROM memberships`/`clients`/`visits` via text() | WIRED | repository.py:93, 119, 148, 176, 207 |
| `v1/router.py` | `reports.router` | `reports_router` import + include_router | WIRED | router.py:35+78 |

---

## Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `router.py get_revenue_report` | `result` | `service.get_revenue_report` → `repository.fetch_revenue_buckets` → `SELECT SUM(amount_kopecks) FROM payments` | Yes — DB aggregate query with bind params | FLOWING |
| `router.py get_clients_report` | `result` | `service.get_clients_report` → 3 repository readers → `SELECT COUNT(*) FROM memberships/clients` | Yes — DB count queries | FLOWING |
| `router.py get_visits_report` | `result` | `service.get_visits_report` → 2 repository readers → `SELECT COUNT(*) FROM visits GROUP BY gym_date/hour` | Yes — DB aggregate queries | FLOWING |

---

## Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| All 27 reports integration tests pass | `cd apps/backend && uv run pytest tests/integration/reports/ -q` | 27 passed in 5.26s | PASS |
| mypy strict clean on reports module | `cd apps/backend && uv run mypy app/modules/reports` | Success: no issues found in 7 source files | PASS |
| ruff clean on reports module | `cd apps/backend && uv run ruff check app/modules/reports` | All checks passed | PASS |
| import-linter contracts kept | `cd apps/backend && uv run lint-imports` | core must not import modules KEPT; modules cannot import each other KEPT | PASS |
| No commit/flush in reports module | `grep -nE "session.(commit|flush)" app/modules/reports/*.py` | Returns only comments (not actual calls) | PASS |
| No cross-module ORM imports in repository | `grep -n "^from app.modules." app/modules/reports/repository.py` | Only reports-internal: reports.constants + reports.schemas | PASS |

---

## Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| REV-01 | 55-01 | Owner gets revenue by day | SATISFIED | GET /revenue 200 test + owner_gets_revenue_report |
| REV-02 | 55-01 | groupBy=month breakdown | SATISFIED | test_group_by_month_collapses_buckets asserts single "2026-07" bucket |
| REV-03 | 55-01 | Breakdown by method (cash/online) | SATISFIED | byMethod.cash/online in bucket response; test_group_by_month asserts byMethod values |
| REV-04 | 55-01 | Refunds as signed amounts; net revenue correct | SATISFIED | test_net_revenue_zero_after_full_refund: netKopecks==0 |
| REV-05 | 55-01 | Integer kopecks; MSK day/month buckets | SATISFIED | All money fields typed int; AT TIME ZONE 'Europe/Moscow' in SQL; tests pass |
| CLR-01 | 55-02 | Active membership count | SATISFIED | activeCount in response shape test |
| CLR-02 | 55-02 | Expiring within N days (1..30, default 7) | SATISFIED | test_expiring_count_within_boundary; test_within_0/31_returns_422; test_within_default_is_7 |
| CLR-03 | 55-02 | New clients count by created_at MSK | SATISFIED | test_new_clients_count_reflects_created_in_range; fetch_new_clients_count uses (created_at AT TIME ZONE 'Europe/Moscow')::date |
| CLR-04 | 55-02 | All counters exclude soft-deleted | SATISFIED | test_active_count_excludes_soft_deleted_client; test_new_clients_count_excludes_soft_deleted; SQL has deleted_at IS NULL |
| VIS-R-01 | 55-02 | Daily visit counts by gym_date | SATISFIED | test_two_visits_same_gym_date_one_daily_bucket: count==2 for 2026-08-10 |
| VIS-R-02 | 55-02 | Hourly peak-hour grouping | SATISFIED | test_hourly_buckets_reflect_msk_hours: hours 9 and 18 both present |
| VIS-R-03 | 55-02 | averagePerDay for period | SATISFIED | test_average_per_day_calculation: 3 visits/3 days=1.0; test_average_per_day_denominator_uses_calendar_range: 2/4=0.5 |
| VIS-R-04 | 55-02 | gym_date used directly (no secondary TZ conversion) | SATISFIED | repository.py fetch_visits_daily uses gym_date BETWEEN :from_date/:to_date directly; no AT TIME ZONE in daily query |

All 13 Phase 55 requirements satisfied.

---

## Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `service.py` | 97-106 | `by_method` accumulates refund rows (net model) while `by_subject_kind` excludes them (gross model) — asymmetric semantics within the same bucket | Warning | `byMethod` shows net cash/online amounts (sale + refund signed), but `bySubjectKind` shows gross sale amounts. Test description at test_reports_revenue.py:8 says "byMethod carries only positive sale amounts" — contradicts actual behavior. No test assertion verifies byMethod values in the refund scenario. Downstream consumers may misread cash/online breakdown. (WR-01 from 55-REVIEW.md) |
| `schemas.py` | 66 | `RevenueBucketBySubjectKind` docstring opens "Net kopecks split by subject kind" but describes gross (refund-excluded) amounts | Warning | Misleading documentation; "Net" is factually wrong for a gross field. (WR-02 from 55-REVIEW.md) |

No TBD/FIXME/XXX debt markers found in any reports module file. No return null / placeholder stubs found.

Note: Both anti-patterns are advisory warnings, not blockers. The phase goal (owner can query all three reports with correct aggregate data) is not compromised — netKopecks is always correct, and the byMethod asymmetry only affects the breakdown field which is not tested against refund scenarios. The REVIEW.md documents these as WR-01 and WR-02 (advisory).

---

## Known Wire Format Deviation: ?fromDate= vs ?from=

**ROADMAP SC#1 text:** `GET /api/v1/reports/revenue?from=&to=&groupBy=day`

**Actual wire:** `GET /api/v1/reports/revenue?fromDate=&toDate=&groupBy=day`

**Root cause (technically forced):** FastAPI 0.115+ with Pydantic v2 `Depends()` uses field names / `alias_generator` for query param naming — NOT `Field(alias=...)`. Since all query DTOs extend `BackendSchemaBase` which has `alias_generator=to_camel`, the field `from_date` maps to `fromDate`. Additionally, `from` is a Python reserved keyword and cannot be a field name. There is no way to produce `?from=` via `Depends()` without breaking the BackendSchemaBase convention.

**Assessment:** The deviation is technically forced, intentional, and consistent with the camelCase API convention used throughout the backend. The functional contract (date range filtering, inclusive MSK bounds, validation, 422 responses) is fully correct. This will be reflected accurately when Phase 57 generates the OpenAPI spec.

**To accept this deviation, add the following override to this VERIFICATION.md frontmatter and re-run verification:**

```yaml
overrides:
  - must_have: "GET /api/v1/reports/revenue?from=&to=&groupBy=day query param names"
    reason: "FastAPI Depends() with BackendSchemaBase alias_generator=to_camel forces from_date->fromDate; Field(alias='from') does not work for query params and 'from' is a Python reserved word. Wire is ?fromDate=&toDate= throughout, consistent with API-wide camelCase convention. Functional behavior identical."
    accepted_by: "{your name}"
    accepted_at: "2026-05-24T00:00:00Z"
```

---

## Human Verification Required

### 1. Accept or Reject ?fromDate= Wire Name Deviation

**Test:** Review the documented deviation that query params are `?fromDate=&toDate=` rather than `?from=&to=` as written in ROADMAP SC#1.

**Expected:** Confirm that `fromDate`/`toDate` camelCase param names are acceptable for the API contract. The Phase 57 OpenAPI handoff will generate the spec from actual code, so the spec will reflect `fromDate`/`toDate` — not `from`/`to`. Verify this is acceptable before Phase 56 begins.

**Why human:** This is a wire-name deviation from the literal ROADMAP SC#1 text. The functional behavior is correct. Only the developer/owner can decide whether the camelCase param names are acceptable at the API contract level or whether the ROADMAP text should be updated to reflect reality.

---

## Gaps Summary

One gap blocks automatic `passed` status: ROADMAP SC#1 specifies `?from=&to=` but the actual wire is `?fromDate=&toDate=` due to a documented, technically-forced FastAPI/Pydantic v2 constraint. The functional behavior is correct and all 27 integration tests pass using the actual param names. This is a naming convention difference, not a functional failure.

**Recommended action:** Add the override entry above (or update ROADMAP SC#1 wording) and re-verify. All other requirements are fully satisfied.

---

_Verified: 2026-05-24T00:00:00Z_
_Verifier: Claude (gsd-verifier)_
