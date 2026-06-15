---
phase: 115-live-advanced-analytics
plan: "02"
subsystem: backend/tests
tags: [backend, tests, analytics, reports, aggregate, rbac, asgi]
dependency_graph:
  requires:
    - GET /api/v1/reports/cohort (ANL-02, Plan 01)
    - GET /api/v1/reports/anomaly (ANL-02, Plan 01)
    - GET /api/v1/reports/at-risk (ANL-02, Plan 01)
    - GET /api/v1/reports/load/now (ANL-03, Plan 01)
  provides:
    - ASGITransport integration tests for all 4 advanced analytics endpoints
    - Pinned camelCase wire shapes for Plan 03 FE Zod alignment
  affects:
    - apps/backend/tests/integration/reports/test_reports_advanced.py (created)
    - apps/backend/app/modules/reports/repository.py (bug fix: full_name -> concatenation)
    - apps/backend/app/modules/reports/constants.py (cosmetic: sigma unicode)
    - apps/backend/app/modules/reports/schemas.py (cosmetic: line-length, sigma)
tech_stack:
  added: []
  patterns:
    - ASGITransport + pytest-asyncio (httpx AsyncClient, no real network)
    - pure pytest fixture injection (no explicit conftest imports in test module)
    - NaN-guard assertion pattern (x == x, isinstance float)
    - reception-403 shape assertion (code == 'forbidden')
key_files:
  created:
    - apps/backend/tests/integration/reports/test_reports_advanced.py
  modified:
    - apps/backend/app/modules/reports/repository.py
    - apps/backend/app/modules/reports/constants.py
    - apps/backend/app/modules/reports/schemas.py
decisions:
  - "Fixture injection via pure pytest conftest (no explicit module-level imports) — avoids ruff F811 redefinition warnings"
  - "NaN guard: assert pct == pct catches float NaN; isinstance check catches non-numeric types"
  - "at-risk test seeds stale (30 days) vs recent (today) visit to prove the threshold gate"
  - "anomaly small-sample: 3 visits over 30 days; consistent direction assertion covers spike/drop/None"
metrics:
  duration: "~3 minutes"
  completed: "2026-06-15"
  tasks_completed: 1
  files_modified: 4
---

# Phase 115 Plan 02: Advanced Analytics Tests Summary

13 ASGITransport integration tests covering all four owner-only aggregate endpoints from Plan 01 — reception-403 gate, owner-200 shape, empty-data, and small-sample edge cases.

## What Was Built

### `apps/backend/tests/integration/reports/test_reports_advanced.py` (created)

13 tests across 4 endpoints:

| Endpoint | Owner-200+Shape | Reception-403 | Empty/Zero | Small-Sample |
|----------|----------------|---------------|------------|--------------|
| /load/now | test_owner_gets_load_now | test_reception_forbidden_load_now | test_load_now_zero_when_no_recent_visits | — |
| /cohort | test_owner_gets_cohort | test_reception_forbidden_cohort | test_owner_gets_cohort (empty cohorts=[]) | test_cohort_small_sample |
| /cohort | — | — | — | test_cohort_months_param_bounds (0→422, 12→200) |
| /anomaly | test_owner_gets_anomaly | test_reception_forbidden_anomaly | test_owner_gets_anomaly (empty points) | test_anomaly_small_sample_no_nan |
| /at-risk | test_owner_gets_at_risk | test_reception_forbidden_at_risk | test_owner_gets_at_risk (empty items) | test_at_risk_flags_stale_member |

### Confirmed camelCase Wire Keys (Plan 03 FE Zod targets — pinned by passing tests)

**GET /api/v1/reports/load/now:**
- `data.count` — int >= 0
- `data.asOf` — ISO-8601 string
- `data.windowMinutes` — positive int (120)

**GET /api/v1/reports/cohort:**
- `data.cohorts` — list of `{ cohortMonth: 'YYYY-MM', label: str, months: [{ offset: int, retentionPct: float|null }] }`
- `data.maxOffset` — int (0 when empty)
- cohortMonths=0 → 422; cohortMonths=12 → 200

**GET /api/v1/reports/anomaly:**
- `data.points` — list of `{ date: 'YYYY-MM-DD', count: int, isAnomaly: bool, direction: 'spike'|'drop'|null, label: str }`
- `data.windowDays` — int
- `data.sigmaThreshold` — float
- `data.anomalyCount` — int (count of isAnomaly==True points)

**GET /api/v1/reports/at-risk:**
- `data.count` — int >= 0
- `data.items` — list of `{ clientId: str, name: str, membershipType: str, lastVisitDate: str|null, daysSinceVisit: int, lastVisitLabel: str }`
- `data.thresholdDays` — positive int (14)

---

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] clients table has no full_name column**

- **Found during:** Task 1 (test_owner_gets_at_risk failure)
- **Issue:** `fetch_at_risk_members` in repository.py referenced `c.full_name` but the `clients` table only has `first_name` and `last_name` columns (PostgreSQL `UndefinedColumnError`).
- **Fix:** Changed `c.full_name AS name` to `c.last_name || ' ' || c.first_name AS name` in the SQL. Updated docstring to reflect correct column names.
- **Files modified:** `apps/backend/app/modules/reports/repository.py`
- **Commit:** f64fa873

**2. [Rule 1 - Bug / Cosmetic] Ruff F811 — test module explicit fixture imports**

- **Found during:** Task 1 ruff check
- **Issue:** Explicit `from tests.integration.reports.conftest import (authed_client_owner, ...)` block triggered ruff F811 (function params redefine module-level symbols). The analog `test_reports_visits.py` uses pure pytest fixture injection (no explicit imports).
- **Fix:** Removed the explicit import block; fixtures are injected automatically by pytest via conftest.py. This matches the pattern in all other test modules in the suite.
- **Files modified:** `apps/backend/tests/integration/reports/test_reports_advanced.py`
- **Commit:** f64fa873

---

## Verification Results

- `uv run pytest tests/integration/reports/test_reports_advanced.py -v` — **13 passed**
- `uv run ruff check tests/integration/reports/test_reports_advanced.py app/modules/reports/repository.py` — **All checks passed**
- `uv run mypy app/modules/reports/repository.py` — **Success: no issues found in 1 source file**

---

## Threat Surface Scan

No new threat surface. The test file exercises existing endpoints; no new routes or auth paths added. The repository.py bug fix (column name) is a pure correctness fix with no security implications.

## Self-Check: PASSED

- `apps/backend/tests/integration/reports/test_reports_advanced.py` exists and contains 13 test functions.
- Commit f64fa873 confirmed in git log.
- 13 tests pass under ASGITransport.
