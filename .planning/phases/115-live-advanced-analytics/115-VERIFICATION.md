---
phase: 115-live-advanced-analytics
verified: 2026-06-15T15:17:00Z
status: human_needed
score: 11/11
overrides_applied: 0
human_verification:
  - test: "Owner opens the Load page and sees the LiveNowCard counter (сейчас в зале) above the heatmap. Confirm it shows a non-negative integer with the sub-label 'Оценка присутствующих · окно N мин'."
    expected: "LiveNowCard renders with a count (may be 0), the approximation sub-label is visible, no error state shown."
    why_human: "refetchInterval 60s auto-poll and live counter display require a running backend + browser; Vitest renders mocked data only."
  - test: "Owner opens the Load page and sees the CohortRetentionCard (Таблица удержания). Scroll to the Расширенная аналитика section. Confirm the table renders with at least one row, M0..M{N} headers, colored cells, and the gradient legend footer."
    expected: "Cohort grid visible with color-scale tinting and retention percentages. Empty DB scenario shows EmptyState 'Нет данных по когортам'."
    why_human: "Color-scale correctness (retentionBg CSS color-mix) and layout cannot be verified without rendering in a real browser."
  - test: "Owner opens the Load page and sees the VisitAnomalyCard. Confirm the area chart renders with an x-axis of dates and that anomaly dots appear with distinct spike (chart-1) and drop (chart-4) colors when anomalies exist."
    expected: "AreaChart visible, spike dots red/orange, drop dots distinct color. If no anomalies, footnote 'Аномалий не обнаружено' appears."
    why_human: "Custom AnomalyDot renderer and recharts rendering requires a real browser viewport."
  - test: "Owner opens the Load page and sees the AtRiskWidget. Confirm count badge shows a number, up to 5 member rows appear (or EmptyState 'Отток под контролем' when count is 0)."
    expected: "Count badge with bg-warning-soft styling, member rows with name + membershipType + lastVisitLabel. Overflow line 'И ещё N клиентов' when count > 5."
    why_human: "Visual token rendering (bg-warning-soft, text-warning-deep) and list layout need browser verification."
  - test: "Switch session role to reception. Open the Load page. Confirm the page shows a role-gate message (not the analytics widgets). Open the Dashboard. Confirm the activity feed section is empty or shows a non-owner placeholder — NOT actual audit log rows."
    expected: "Reception cannot see Load page analytics content. Reception DashboardPage shows no activity feed data (hook disabled)."
    why_human: "Role-switching behavior and conditional render for reception require a browser session with role toggle."
  - test: "Owner opens the Dashboard page. Confirm the ActivityFeed section shows real recent audit events (e.g., check-ins, payments) rather than an EmptyState or Link stub."
    expected: "ActivityFeed renders at least one event row with type icon, title (e.g. 'Клиент · чек-ин'), and relative time label."
    why_human: "Real audit-log data and event row rendering require a running backend with audit history and a browser render."
---

# Phase 115: Live Advanced Analytics — Verification Report

**Phase Goal:** Owner sees cohort, anomaly, and at-risk member widgets backed by new aggregate queries, a live gym-load counter, and real-data dashboard feed/KPI/sales widgets.
**Verified:** 2026-06-15T15:17:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Owner GET /api/v1/reports/cohort returns 200 with a cohort retention grid (rows keyed by membership-start month) | VERIFIED | 16/16 integration tests pass; `test_owner_gets_cohort` + `test_cohort_small_sample` + `test_cohort_exact_retention_value` confirm correct nested shape and 100.0% M0 value |
| 2 | Owner GET /api/v1/reports/anomaly returns 200 with daily visit points flagged >2σ from a ~14-day rolling mean | VERIFIED | `test_owner_gets_anomaly` + `test_anomaly_small_sample_no_nan` pass; `_compute_anomaly` with `std==0` guard confirmed in `service.py:506` |
| 3 | Owner GET /api/v1/reports/at-risk returns 200 with count + list of active-membership clients whose last visit was >14 days ago | VERIFIED | `test_owner_gets_at_risk` + `test_at_risk_flags_stale_member` + `test_at_risk_ignores_visits_predating_membership` pass; IN-02 fixed: true uncapped count via `fetch_at_risk_count`; WR-04 fixed: last_visit scoped to membership start_date |
| 4 | Owner GET /api/v1/reports/load/now returns 200 with {count, asOf, windowMinutes} | VERIFIED | `test_owner_gets_load_now` + `test_load_now_zero_when_no_recent_visits` pass; `LoadNowResponse` schema confirmed at `schemas.py:290-303`; WR-01 fixed: comment says "minutes" |
| 5 | Reception receives 403 on all four new endpoints ((VIEW, REPORTS) is OWNER_ONLY) | VERIFIED | `test_reception_forbidden_load_now`, `test_reception_forbidden_cohort`, `test_reception_forbidden_anomaly`, `test_reception_forbidden_at_risk` — all 4 reception-403 tests pass with `code == 'forbidden'` |
| 6 | Empty/small-sample data yields valid responses — no NaN, no division-by-zero, stable ordering | VERIFIED | CR-01 fixed: dense `generate_series`+`COALESCE` offset grid ensures 0% != null; `test_cohort_exact_retention_value` pins exact value 100.0; `test_anomaly_small_sample_no_nan` uses `x == x` NaN guard; `test_load_now_zero_when_no_recent_visits` confirms count>=0 |
| 7 | Owner sees CohortRetentionCard, VisitAnomalyCard, AtRiskWidget + LiveNowCard in a Расширенная аналитика section on the Load page | VERIFIED (automated partial) | `grep -q "Расширенная аналитика" LoadPage.tsx` confirmed; `useLoadNow` wired; all three widget files exist with 40+ lines each (137/186/103); `pnpm exec tsc --noEmit` clean; visual correctness deferred to human UAT |
| 8 | Each new widget shows its own loading skeleton and empty state; reception never sees Load page content | VERIFIED (automated partial) | Skeleton + EmptyState patterns confirmed in each widget file; `can(role,'view','reports')` gate on every hook + existing page-level guard; router-smoke 20/20 pass; visual layout deferred to human UAT |
| 9 | Owner dashboard activity feed renders real recent events from GET /api/v1/audit-log (no mock) | VERIFIED (automated partial) | `useActivityFeed` in `DashboardPage.tsx:175`; `audit-activity.ts` exports `mapAuditToActivityFeed`; no `from '@/mocks/dashboard'` import; `audit-activity.test.ts` 15/15 pass; real data display deferred to human UAT |
| 10 | Top-trainer KPIs render real GET /reports/trainers data; Plans sales chart renders real GET /reports/revenue data (no mock) | VERIFIED | `DashboardPage.tsx` imports `useTrainersReport` + `useRevenueReport` (confirmed at lines 23, 26, 158–170); no mock import feeds these widgets; code review confirmed no mock fallback |
| 11 | Reception does not fetch the owner-only audit feed (gated by can(role,'view','audit-log')) | VERIFIED | `enabled: can(role, 'view', 'audit-log')` at `api.ts:100`; `useActivityFeed` declared inside owner-only block in DashboardPage (`DashboardOwnerSection` mounts only when `isOwner`); `router-smoke.test.tsx` 20/20 pass |

**Score:** 11/11 truths verified (all automated checks pass; visual/browser UAT items routed to human verification)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `apps/backend/app/modules/reports/constants.py` | LOAD_NOW_WINDOW_MINUTES + 7 new constants | VERIFIED | All 8 constants present: lines 81-94 |
| `apps/backend/app/modules/reports/schemas.py` | LoadNowResponse, CohortRetentionResponse/Query, VisitAnomalyResponse/Query, AtRiskMembersResponse | VERIFIED | All 9 DTO classes at lines 290-456 |
| `apps/backend/app/modules/reports/repository.py` | fetch_load_now_count, fetch_at_risk_members, fetch_at_risk_count, fetch_visit_anomaly_daily, fetch_cohort_retention | VERIFIED | All functions present; CR-01 dense offset grid with `generate_series`+`COALESCE`; WR-04 membership-scoped at-risk |
| `apps/backend/app/modules/reports/service.py` | get_load_now, get_at_risk_members, get_cohort_retention, get_visit_anomaly, _compute_anomaly | VERIFIED | All 5 functions present; div-by-zero/NaN guards confirmed |
| `apps/backend/app/modules/reports/router.py` | GET /cohort, /anomaly, /at-risk, /load/now with require_permission(VIEW, REPORTS) | VERIFIED | All 4 routes at lines 293/321/349/375; every route has `Depends(require_permission(Action.VIEW, Resource.REPORTS))` |
| `apps/backend/tests/integration/reports/test_reports_advanced.py` | 16 integration tests (owner-200 + reception-403 + empty + small-sample + CR-01 exact + IN-02 cap) | VERIFIED | 16 tests present; all 16 PASS under ASGITransport |
| `apps/admin-app/src/features/reports/schemas.ts` | LoadNowSchema, CohortRetentionSchema, VisitAnomalySchema, AtRiskSchema | VERIFIED | All 4 schemas present at lines 122-203 |
| `apps/admin-app/src/features/reports/api.ts` | useCohortReport, useVisitAnomaly, useAtRiskMembers, useLoadNow | VERIFIED | All 4 hooks with `enabled: can(role,'view','reports')`; useLoadNow has `refetchInterval: 60_000` |
| `apps/admin-app/src/pages/load/components/CohortRetentionCard.tsx` | Cohort grid component, min 40 lines | VERIFIED | 137 lines; table role=grid, th scope=col/row, retentionBg color-scale, skeleton h-[240px], EmptyState |
| `apps/admin-app/src/pages/load/components/VisitAnomalyCard.tsx` | Visit anomaly chart component, min 40 lines | VERIFIED | 186 lines; ChartContainer+AreaChart, custom AnomalyDot via dot prop, skeleton h-[180px], EmptyState |
| `apps/admin-app/src/pages/load/components/AtRiskWidget.tsx` | At-risk widget, min 40 lines | VERIFIED | 103 lines; count badge aria-label, 5-row cap, overflow line, zero-risk EmptyState |
| `apps/admin-app/src/pages/load/LoadPage.tsx` | Расширенная аналитика section + useLoadNow wiring | VERIFIED | Section aria-label confirmed; useLoadNow + LiveNowCard wired at lines 67, 130-131, 157-163 |
| `apps/admin-app/src/features/dashboard/audit-activity.ts` | mapAuditToActivityFeed pure function | VERIFIED | `export function mapAuditToActivityFeed` at line 160; all 6 known actions + 'alert' fallback; never-throw pattern |
| `apps/admin-app/src/features/dashboard/audit-activity.test.ts` | Unit tests for mapper | VERIFIED | 15 tests pass (known actions + unknown fallback + empty + timeLabel + actor fallback) |
| `apps/admin-app/src/features/dashboard/api.ts` | useActivityFeed(role) hook | VERIFIED | `export function useActivityFeed` at line 91; `enabled: can(role,'view','audit-log')`; hits `/api/v1/audit-log` |
| `apps/admin-app/src/pages/dashboard/DashboardPage.tsx` | Real ActivityFeed render; no mock feeding any of 3 widgets | VERIFIED | `useActivityFeed` imported and called at line 175; `<ActivityFeed data={activityFeedQ.data}>` at line 241; no mock import found |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `router.py` | `service.get_cohort_retention` / `get_visit_anomaly` / `get_at_risk_members` / `get_load_now` | `await service.get_xxx(session, ...)` + `envelope(result)` | WIRED | Confirmed at router lines 293-392 |
| `router.py` | `require_permission(Action.VIEW, Resource.REPORTS)` | `Depends(require_permission(...))` on every new route | WIRED | 4 routes × confirmed in grep |
| `service.py` | `repository.fetch_*` functions | `await repository.fetch_xxx(session, ...)` | WIRED | `fetch_load_now_count`, `fetch_at_risk_members`, `fetch_at_risk_count`, `fetch_visit_anomaly_daily`, `fetch_cohort_retention` all called |
| `reports/api.ts` | `/api/v1/reports/cohort|anomaly|at-risk|load/now` | `staffRequest('get', ...) + Schema.parse(raw).data` | WIRED | All 4 exact path strings confirmed in `api.ts` |
| `LoadPage.tsx` | `useLoadNow / useCohortReport / useVisitAnomaly / useAtRiskMembers` | Hook calls inside owner-gated content | WIRED | All 4 hooks imported from `@/features/load/api` and called; `liveData` mapped to `LiveNowCard` |
| `features/dashboard/api.ts` | `/api/v1/audit-log` | `staffRequest('get', '/api/v1/audit-log', {query:{pageSize:20}}) → AuditLogResponseSchema.parse → mapAuditToActivityFeed` | WIRED | Confirmed at `api.ts:95` |
| `DashboardPage.tsx` | `<ActivityFeed data={activityFeedQ.data}>` | `activityFeedQ = useActivityFeed(role)` → render with skeleton/error fallback | WIRED | Lines 175 + 241 confirmed |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `LoadPage.tsx` / `LiveNowCard` | `liveNowData` from `useLoadNow` | GET /api/v1/reports/load/now → backend SQL `COUNT(DISTINCT client_id) FROM visits WHERE checked_in_at >= now() - make_interval(mins => :window_minutes)` | Yes — real DB query with bound params | FLOWING |
| `CohortRetentionCard` | `cohortData` from `useCohortReport` | GET /api/v1/reports/cohort → repository `fetch_cohort_retention` with dense `generate_series` + `COALESCE` SQL | Yes — real DB window-function query | FLOWING |
| `VisitAnomalyCard` | `anomalyData` from `useVisitAnomaly` | GET /api/v1/reports/anomaly → repository `fetch_visit_anomaly_daily` → `_compute_anomaly` | Yes — real DB query + pure-Python rolling mean | FLOWING |
| `AtRiskWidget` | `atRiskData` from `useAtRiskMembers` | GET /api/v1/reports/at-risk → repository `fetch_at_risk_members` (CTE with `DISTINCT ON` + membership-scoped last_visit) | Yes — real DB query; true uncapped count via `fetch_at_risk_count` | FLOWING |
| `DashboardPage.tsx` / `ActivityFeed` | `activityFeedQ.data` from `useActivityFeed` | GET /api/v1/audit-log → `mapAuditToActivityFeed` | Yes — real audit-log endpoint; no mock import | FLOWING |
| `DashboardPage.tsx` / `TopTrainers` | `trainersQ.data` from `useTrainersReport` | GET /api/v1/reports/trainers (existing endpoint, pre-Phase 115) | Yes — pre-existing real endpoint; no mock fallback | FLOWING |
| `DashboardPage.tsx` / `RevenueChart` | `revenueQ.data` from `useRevenueReport` | GET /api/v1/reports/revenue (existing endpoint, pre-Phase 115) | Yes — pre-existing real endpoint; no mock fallback | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| 16 integration tests pass (owner-200, reception-403, empty-data, small-sample, CR-01, IN-02) | `uv run pytest tests/integration/reports/test_reports_advanced.py -v` | 16 passed in 7.95s | PASS |
| mypy strict on reports module | `uv run mypy --strict app/modules/reports/` | Success: no issues found in 8 source files | PASS |
| ruff on reports module | `uv run ruff check app/modules/reports/` | All checks passed | PASS |
| import-linter contracts | `uv run lint-imports` | 3 contracts KEPT, 0 broken | PASS |
| TypeScript clean | `pnpm exec tsc --noEmit` | No output (clean) | PASS |
| ESLint on all new/modified FE files | `pnpm exec eslint [10 files]` | No output (clean) | PASS |
| Zod schema tests | `pnpm exec vitest run src/features/reports/schemas.test.ts` | 26 tests passed | PASS |
| Audit mapper tests | `pnpm exec vitest run src/features/dashboard/audit-activity.test.ts` | 15 tests passed | PASS |
| Router smoke (owner + reception dashboard render without error) | `pnpm exec vitest run src/app/router-smoke.test.tsx` | 20 tests passed | PASS |
| "Расширенная аналитика" section + useLoadNow present in LoadPage | `grep -q "Расширенная аналитика" LoadPage.tsx && grep -q "useLoadNow" LoadPage.tsx` | Both found | PASS |
| No mock import feeds any of the 3 dashboard widgets | `grep -nE "from '@/mocks/dashboard'" DashboardPage.tsx` | No matches | PASS |

### Probe Execution

Step 7c: SKIPPED — no `scripts/*/tests/probe-*.sh` files exist for this phase; no phase-declared probes in PLAN/SUMMARY files.

### Requirements Coverage

| Requirement | Source Plans | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| ANL-02 | 115-01, 115-02, 115-03 | Owner sees cohort/anomaly/risk-list attendance widgets backed by new aggregate queries | SATISFIED | 4 new backend endpoints; 3 FE widgets wired; 16 integration tests green |
| ANL-03 | 115-01, 115-02, 115-03 | Owner sees live load ("сейчас в зале") on Load page backed by /reports/load/now | SATISFIED | `/load/now` endpoint live; `useLoadNow` with `refetchInterval:60000` wired to `LiveNowCard` |
| ANL-04 | 115-04 | Dashboard activity feed, top-trainer KPIs, and sales chart render real data | SATISFIED | `useActivityFeed` wired; `useTrainersReport`+`useRevenueReport` confirmed real; no mock import |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `apps/backend/app/modules/reports/router.py` | 285-288 | `TODO Phase 117: regen typed response bodies` | INFO | References formal follow-up work (Phase 117 HND-01); not unresolved debt. The 4 endpoint paths already exist in `schema.d.ts` with `content: unknown` — only typed response bodies remain. Per PLAN frontmatter this deferral is intentional. |

No `TBD`, `FIXME`, or `XXX` markers found in any phase-modified file.

### Human Verification Required

The following items require browser testing with a running backend. Per project convention (`operator-pending-verify-autodefer` memory note), these are auto-deferred in autonomous runs and do not block phase completion.

#### 1. LiveNowCard Live Counter Display

**Test:** Owner opens `/load` page. Verify the LiveNowCard appears above the LoadHeatmapCard showing a non-negative integer count and the sub-label "Оценка присутствующих · окно N мин" (where N=120).
**Expected:** Card renders, count is a non-negative integer, approximation label visible. After 60s the count auto-refreshes without page reload.
**Why human:** refetchInterval polling and live counter display require a running backend + real browser; Vitest uses mocked data.

#### 2. Cohort Retention Grid Visual

**Test:** Owner opens `/load` page, scrolls to "Расширенная аналитика" section. Examine CohortRetentionCard.
**Expected:** Table renders with M0..M{maxOffset} column headers, one row per cohort month label (e.g. "янв 2026"), cells show "{pct}%" or "—", color-scale tinting visible (light tint for low %, dark for >=70%). Gradient legend footer below table. Empty database shows EmptyState "Нет данных по когортам".
**Why human:** CSS `color-mix()` rendering, table layout, and cell color-scale correctness require a real browser viewport.

#### 3. Visit Anomaly Chart Visual

**Test:** Owner opens `/load`, examines VisitAnomalyCard in "Расширенная аналитика" section.
**Expected:** AreaChart renders with x-axis date labels, baseline area fill. When anomalies exist: spike dots in chart-1 color (orange/red), drop dots in chart-4 color (blue/teal). Summary "Найдено аномалий: N" present. When no anomalies: footnote "Аномалий не обнаружено".
**Why human:** Custom `AnomalyDot` renderer within recharts and color token rendering require browser.

#### 4. AtRiskWidget Member Rows Visual

**Test:** Owner opens `/load`, examines AtRiskWidget.
**Expected:** Count badge with warning-soft styling; up to 5 member rows with name, membership type, and last-visit label (e.g. "18 дней назад"); "И ещё N клиентов →" overflow line when count > 5; "Отток под контролем" EmptyState when count = 0.
**Why human:** `bg-warning-soft`/`text-warning-deep` token rendering and list layout need browser.

#### 5. Reception Role Gate

**Test:** Switch session to reception role. Open `/load` page. Open `/dashboard`.
**Expected:** Load page shows role-gate (not analytics content). Dashboard activity feed section does not show owner-only audit rows (hook disabled for reception).
**Why human:** Role-switching in live session and conditional hook render requires browser session.

#### 6. ActivityFeed Real Data Display

**Test:** Owner opens Dashboard. Examine the ActivityFeed card.
**Expected:** Shows real recent audit events (e.g. check-ins, payments, sign-ups) with type icon, Russian title (e.g. "Клиент · чек-ин"), and relative time label ("4 мин", "2 ч"). No EmptyState/Link stub visible.
**Why human:** Requires a running backend with audit history and browser render to confirm real data flows to the component.

### Code Review Findings — All Fixed

The following REVIEW.md findings were all resolved before verification:

| Finding | Severity in Review | Status |
|---------|-------------------|--------|
| CR-01: Cohort M0 under-count / 0%≠null ambiguity | BLOCKER | FIXED — dense `generate_series`+`COALESCE` offset grid + `test_cohort_exact_retention_value` |
| WR-01: windowMinutes comment said "seconds" | WARNING | FIXED — comment updated to "rolling window length in minutes" |
| WR-02: `_RU_DAY_ABBR` duplicate constant | WARNING | FIXED — deleted; `_ru_day_label` reuses `_RU_MONTH_ABBR` |
| WR-03: cohort_base comment claimed DISTINCT ON but used plain DISTINCT | WARNING | FIXED — comment corrected to describe plain DISTINCT behavior |
| WR-04: at-risk last_visit not scoped to current membership | WARNING | FIXED — `WHERE checked_in_at >= membership_start_date` scoping added; `test_at_risk_ignores_visits_predating_membership` passes |
| WR-05: Raw hex colors in TopTrainers/RevenueChart | WARNING | FIXED — `COLORS` uses `var(--chart-1..5)`; `stopColor` uses `var(--chart-1)` |
| WR-06: useClientsReport default `within` was 30 (not 7) | WARNING | FIXED — changed to `query.within ?? 7` |
| IN-01: `as_of` is app-server clock, not DB clock | INFO | ACCEPTED — cosmetic for single-host deploy; no fix required |
| IN-02: `count` equaled `len(items)` rather than true total | INFO | FIXED — `fetch_at_risk_count` separate uncapped count; `test_at_risk_count_can_exceed_items_when_capped` passes |
| IN-03: Router TODO scope stale | INFO | UPDATED — TODO now correctly scopes remaining work to typed response bodies only |
| IN-04: `slice(0,5)` recomputed per row in AtRiskWidget | INFO | Acceptable; not a correctness bug |
| IN-05: `formatRelativeRu` not guarded on malformed `createdAt` | INFO | ACCEPTED — Zod layer validates upstream; acceptable as defense-in-depth note |

### Gaps Summary

No gaps. All 11 must-have truths VERIFIED by automated evidence. All 6 REVIEW.md warnings and 1 BLOCKER resolved before verification. The only pending items are browser-UAT items (human_needed) deferred per project convention.

---

_Verified: 2026-06-15T15:17:00Z_
_Verifier: Claude (gsd-verifier)_
