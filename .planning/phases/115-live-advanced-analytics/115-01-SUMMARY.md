---
phase: 115-live-advanced-analytics
plan: "01"
subsystem: backend/reports
tags: [backend, analytics, reports, aggregate, window-functions, rbac]
dependency_graph:
  requires: []
  provides:
    - GET /api/v1/reports/cohort (ANL-02)
    - GET /api/v1/reports/anomaly (ANL-02)
    - GET /api/v1/reports/at-risk (ANL-02)
    - GET /api/v1/reports/load/now (ANL-03)
  affects:
    - apps/backend/app/modules/reports/constants.py
    - apps/backend/app/modules/reports/schemas.py
    - apps/backend/app/modules/reports/repository.py
    - apps/backend/app/modules/reports/service.py
    - apps/backend/app/modules/reports/router.py
tech_stack:
  added: []
  patterns:
    - raw text() SQL with bound params (cross-module read discipline)
    - pure-Python trailing rolling mean for anomaly detection
    - ResponseData aggregate DTOs (no pagination)
    - require_permission(VIEW, REPORTS) owner-only gate
key_files:
  created: []
  modified:
    - apps/backend/app/modules/reports/constants.py
    - apps/backend/app/modules/reports/schemas.py
    - apps/backend/app/modules/reports/repository.py
    - apps/backend/app/modules/reports/service.py
    - apps/backend/app/modules/reports/router.py
decisions:
  - "Nested CohortRetentionResponse shape ({ cohorts: [{ cohortMonth, label, months: [{ offset, retentionPct }] }], maxOffset }) matches UI-SPEC CohortRetentionSchema exactly"
  - "ANOMALY_LOOKBACK_DAYS=90 days default chart span; no anomalies flagged when trailing std==0"
  - "at-risk never-visited clients included (last_visit_date=null); days_since_visit=AT_RISK_THRESHOLD_DAYS+1 as sentinel"
  - "load/now rolling window = LOAD_NOW_WINDOW_MINUTES=120 (approximation; no checkout column)"
  - "OpenAPI regen deferred to Phase 117 (TODO comment added near new routes)"
metrics:
  duration: "~6 minutes"
  completed: "2026-06-15"
  tasks_completed: 2
  files_modified: 5
---

# Phase 115 Plan 01: Advanced Analytics Backend Endpoints Summary

Four owner-only aggregate endpoints added to the existing reports module (no schema migration, no new RBAC resource) — cohort retention, visit anomaly, at-risk members, and live gym-load — using raw-SQL window-function reads over existing `visits` + `memberships` tables.

## What Was Built

### Constants (`apps/backend/app/modules/reports/constants.py`)

| Constant | Value | Purpose |
|----------|-------|---------|
| `LOAD_NOW_WINDOW_MINUTES` | `120` | Rolling-window for live headcount (no checkout column) |
| `ANOMALY_WINDOW_DAYS` | `14` | Trailing mean window for anomaly detection |
| `ANOMALY_SIGMA` | `2.0` | Standard-deviation threshold for spike/drop flag |
| `ANOMALY_LOOKBACK_DAYS` | `90` | Default chart span when no fromDate/toDate given |
| `AT_RISK_THRESHOLD_DAYS` | `14` | Days without visit for active-membership at-risk |
| `AT_RISK_MAX_ITEMS` | `50` | Result-set cap (DoS guard T-115-05) |
| `COHORT_DEFAULT_MONTHS` | `6` | Default ?cohortMonths query param |
| `COHORT_MAX_MONTHS` | `12` | Upper bound validated in service |

### Route Paths (pinned — FE Plans 03/04 MUST use these exact paths)

```
GET /api/v1/reports/cohort
GET /api/v1/reports/anomaly
GET /api/v1/reports/at-risk
GET /api/v1/reports/load/now
```

All four: `require_permission(Action.VIEW, Resource.REPORTS)` — reception 403.

---

## Final camelCase Wire Shapes (FE Zod targets for Plan 03)

### GET /api/v1/reports/load/now

```typescript
// LoadNowResponse — envelope: { data: { ... } }
{
  data: {
    count: number          // non-negative integer
    asOf: string           // ISO-8601 datetime (UTC)
    windowMinutes: number  // 120 (LOAD_NOW_WINDOW_MINUTES)
  }
}
```

**Zod:** `z.object({ data: z.object({ count: z.number().int().nonneg(), asOf: z.string(), windowMinutes: z.number().int() }) })`

---

### GET /api/v1/reports/cohort?cohortMonths=6

```typescript
// CohortRetentionResponse — envelope: { data: { ... } }
{
  data: {
    cohorts: Array<{
      cohortMonth: string          // 'YYYY-MM' membership-start month (Europe/Moscow)
      label: string                // Short Russian label, e.g. 'янв 2026'
      months: Array<{
        offset: number             // months since cohort start (0 = cohort month itself)
        retentionPct: number|null  // null when cohort_size==0 (never div-by-zero)
      }>
    }>
    maxOffset: number              // max months_since across all cohorts (0 if empty)
  }
}
```

**Query param:** `?cohortMonths=6` (1..12, default 6). Out-of-range → 422.

---

### GET /api/v1/reports/anomaly?fromDate=YYYY-MM-DD&toDate=YYYY-MM-DD

```typescript
// VisitAnomalyResponse — envelope: { data: { ... } }
{
  data: {
    points: Array<{
      date: string                       // 'YYYY-MM-DD' (gym_date MSK)
      count: number                      // visit count for that day (0 for gap-filled days)
      isAnomaly: boolean                 // true if |count - trailing_mean| > sigma * std
      direction: 'spike' | 'drop' | null // null when not anomalous
      label: string                      // Short Russian label, e.g. '12 июн'
    }>
    windowDays: number                   // 14 (ANOMALY_WINDOW_DAYS)
    sigmaThreshold: number               // 2.0 (ANOMALY_SIGMA)
    anomalyCount: number                 // count of flagged points
  }
}
```

**Query params:** `?fromDate=YYYY-MM-DD&toDate=YYYY-MM-DD` (both optional; default = last 90 MSK days).
Series is contiguous (gap-filled with count=0). std==0 → no anomaly.

---

### GET /api/v1/reports/at-risk

```typescript
// AtRiskMembersResponse — envelope: { data: { ... } }
{
  data: {
    count: number                // total items returned (capped at 50)
    items: Array<{
      clientId: string           // UUID string
      name: string               // clients.full_name
      membershipType: string     // membership plan name
      lastVisitDate: string|null // 'YYYY-MM-DD' or null if never visited
      daysSinceVisit: number     // AT_RISK_THRESHOLD_DAYS+1 for never-visited
      lastVisitLabel: string     // Pre-formatted Russian: 'N дней назад' or 'не посещал'
    }>
    thresholdDays: number        // 14 (AT_RISK_THRESHOLD_DAYS)
  }
}
```

**No query params.** Never-visited clients (lastVisitDate=null) are included and listed first.

---

## Implementation Notes

### SQL Injection Mitigation (T-115-02)
All repository functions use `sqlalchemy.text()` with `:name` bound params exclusively. No f-string interpolation of any user-supplied or query value. Confirmed by import-linter (no cross-module ORM imports in repository.py).

### Div-by-Zero / NaN Guards
- **Cohort retention:** `retention_pct = None` when `cohort_size == 0` (Python, not SQL).
- **Anomaly std:** `std == 0 or std is NaN/Inf` → `is_anomaly = False` (no flag for constant periods).
- **Anomaly baseline:** Fewer than `ANOMALY_WINDOW_DAYS` preceding points → no anomaly (insufficient window).
- **Load/now:** `COUNT(DISTINCT ...)` returns 0 on empty result — never NULL from Postgres.

### Cohort Retention SQL Design
Uses two CTEs: `cohort_base` (distinct client × cohort_month from active/expired memberships) and `visit_months` (distinct client × visit_month). Months-since computed as integer arithmetic on extracted year/month. SQL returns `(cohort_month, months_since, retained_count, cohort_size)` flat rows; service pivots to nested shape.

### Visit Anomaly Algorithm
Pure-Python trailing rolling mean: for each day at index `i`, window = `daily[max(0, i-window_days):i]`. Population std (not sample std). Guard: `len(window) < window_days` → no anomaly (edge). `std == 0` → no anomaly. Direction: `count > mean` → `spike`, else `drop`.

### At-Risk SQL Design
CTE `active_memberships` uses `DISTINCT ON (m.client_id)` to pick one active membership per client (most recent by `m.id DESC`). Left joins `last_visit` CTE. Filter: `last_at IS NULL OR last_at < now() - make_interval(days => :threshold_days)`. Ordering: `lv.last_at NULLS FIRST` (never-visited first), then `days_since_visit DESC`.

---

## Deviations from Plan

### Auto-fixed Issues (Rule 1)

**1. [Rule 1 - Bug] Ruff RUF001/RUF002/RUF003 — Greek/special Unicode chars in comments/strings**
- **Found during:** Task 2 verification
- **Issue:** Used `σ` (Greek sigma) in constant comments, docstrings, and router summary strings; `×` in docstrings; two E501 line-too-long; unused `noqa` directives.
- **Fix:** Replaced `σ` with `sigma` in all comments/strings; `×` with `x`; fixed long lines; removed unused noqa; moved `from collections import defaultdict` and `from typing import Literal` to module level.
- **Files modified:** `constants.py`, `schemas.py`, `service.py`, `router.py`, `repository.py`
- **Commit:** Included in 288bebb3

None of the above changed behavior or wire shapes.

---

## Verification Results

- `uv run mypy app` — **Success: no issues found in 282 source files**
- `uv run lint-imports` — **3 contracts KEPT (0 broken)** — no cross-module ORM imports in repository.py
- `uv run ruff check app/modules/reports/` — **All checks passed**
- Route smoke: `/cohort`, `/anomaly`, `/at-risk`, `/load/now` all registered on reports router
- Reception-403 + empty-data / small-sample edge cases — proven by Plan 02 ASGITransport tests

---

## Threat Surface Scan

No new threat surface beyond what was in the plan's `<threat_model>`. All four routes are gated by the existing `require_permission(ACTION.VIEW, Resource.REPORTS)` owner-only dependency. The at-risk member list (T-115-03) returns data the owner already sees in the existing clients report; no new PII surface.

## Self-Check: PASSED

All 5 modified files confirmed to exist and contain expected content. Commits c648a12a (Task 1) and 288bebb3 (Task 2) both confirmed in git log.
