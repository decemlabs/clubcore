---
phase: 115-live-advanced-analytics
reviewed: 2026-06-15T00:00:00Z
depth: standard
files_reviewed: 18
files_reviewed_list:
  - apps/admin-app/src/features/dashboard/api.ts
  - apps/admin-app/src/features/dashboard/audit-activity.test.ts
  - apps/admin-app/src/features/dashboard/audit-activity.ts
  - apps/admin-app/src/features/load/api.ts
  - apps/admin-app/src/features/reports/api.ts
  - apps/admin-app/src/features/reports/keys.ts
  - apps/admin-app/src/features/reports/schemas.test.ts
  - apps/admin-app/src/features/reports/schemas.ts
  - apps/admin-app/src/pages/dashboard/DashboardPage.tsx
  - apps/admin-app/src/pages/load/LoadPage.tsx
  - apps/admin-app/src/pages/load/components/AtRiskWidget.tsx
  - apps/admin-app/src/pages/load/components/CohortRetentionCard.tsx
  - apps/admin-app/src/pages/load/components/VisitAnomalyCard.tsx
  - apps/backend/app/modules/reports/constants.py
  - apps/backend/app/modules/reports/repository.py
  - apps/backend/app/modules/reports/router.py
  - apps/backend/app/modules/reports/schemas.py
  - apps/backend/app/modules/reports/service.py
findings:
  critical: 1
  warning: 6
  info: 5
  total: 12
status: issues_found
---

# Phase 115: Code Review Report

**Reviewed:** 2026-06-15
**Depth:** standard
**Files Reviewed:** 18
**Status:** issues_found

## Summary

Reviewed the four new owner-only aggregate endpoints (cohort retention, visit-anomaly,
at-risk members, live load/now), their FE Zod schemas/hooks/widgets, and the dashboard
ActivityFeed audit-log wiring.

Strong points verified:
- **SQL injection safety:** All raw `text()` queries bind user-derived values via
  `:name` params only. `period_expr` in `fetch_revenue_buckets` is chosen from
  internal `GRAIN_DAY/GRAIN_MONTH` literals, never user input. The four new queries
  use `make_interval(...)`, `:from_date`/`:to_date`, `:cohort_months`,
  `:threshold_days`, `:max_items`, `:window_minutes` — all bound. No f-string
  interpolation of user input. **No injection found.**
- **RBAC:** All four new routes carry
  `Depends(require_permission(Action.VIEW, Resource.REPORTS))`; `(VIEW, REPORTS)` is
  owner-only. Integration tests assert reception → 403 for each. ActivityFeed hook is
  gated `enabled: can(role,'view','audit-log')` and lives inside `DashboardOwnerSection`
  which only mounts for owner — reception fires zero owner-only calls. Verified sound.
- **Div-by-zero / NaN guards:** `_compute_anomaly` guards `std == 0`, NaN, Inf, and
  insufficient-baseline. Cohort `retention_pct` guards `cohort_size > 0 → None`.
  `load/now` returns a plain `COUNT` (never NaN). At-risk `LIMIT :max_items` caps the
  result. Empty-input → `[]` / `0` across all four.
- **Audit→activity mapper never throws:** `mapSingleEvent` default branch maps unknown
  actions to `'alert'`; `resolveName` falls back to a generic label. Tests cover the
  unknown-action and null-actor cases. Verified sound.
- **FE Zod ↔ wire alignment:** Cohort uses the nested `{ cohorts: [{ cohortMonth, label,
  months: [{ offset, retentionPct }] }], maxOffset }` shape matching the backend DTO.
  Anomaly/at-risk/load-now shapes match their backend DTOs. The 4 endpoints DO exist in
  `packages/api-client/src/schema.d.ts` (lines 3352–3455) despite the router TODO.

**Coverage-gap check (success criterion #3) — RESOLVED, NOT a gap.** The diff does not
modify `TopTrainers.tsx` or `RevenueChart.tsx`, but both already consume REAL data:
`DashboardOwnerSection` passes `trainersQ.data` (GET /reports/trainers) to `<TopTrainers>`
and `revenueQ.data` (GET /reports/revenue) to `<RevenueChart>`. Both components are typed
to `TrainersReportData` / `RevenueReportData` and contain no mock fallback. The mock
widgets are removed. Criterion #3 is met. (One styling defect in these files is flagged
below as WR-05/IN-05.)

The one BLOCKER is a cohort-retention correctness bug (M0 retention is systematically
under-counted because not every cohort member is guaranteed a self-month visit row).
Remaining findings are warnings/info.

## Critical Issues

### CR-01: Cohort retention M0 (and any offset) under-counts — only visiting clients ever contribute to `retained_count`, but the comment/UI imply a per-offset retention of the full cohort

**File:** `apps/backend/app/modules/reports/repository.py:668-692`
**Issue:**
The `retention` CTE inner-joins `cohort_base` to `visit_months`:

```sql
FROM cohort_base cb
JOIN visit_months vm ON vm.client_id = cb.client_id
                    AND vm.visit_month >= cb.cohort_month
GROUP BY cb.cohort_month, months_since
```

`retained_count = COUNT(DISTINCT cb.client_id)` per `(cohort_month, months_since)`. This
is correct *as far as it goes*, but the offset `months_since` is computed from
`vm.visit_month`, so a cohort row only produces an offset bucket for months in which the
client actually visited. That is the intended retention semantic — **but the join also
silently drops cohort members who never visited at all from every bucket**, which is fine,
*and* it produces a subtle correctness problem at the cohort-month grain:

A client whose membership starts in month M but whose first visit is in M+1 contributes a
row at `months_since = 1` but **no row at `months_since = 0`**. The service then renders
M0 with whatever `retained_count` the SQL produced. Because `cohort_size` (denominator) is
the full distinct-client count of the cohort while the M0 numerator only counts clients
who happened to visit in their very first month, **M0 retention is reported as a fraction
of the whole cohort even though many members simply hadn't started visiting yet** — and
critically, offsets where *zero* cohort members visited produce **no row at all**, so the
UI's `cohort.months.find((mo) => mo.offset === offset)` returns `undefined` →
`retentionPct = null` → cell renders `—`. A genuine 0% retention month is therefore
indistinguishable from a "no data" month. For a churn dashboard this misrepresents the
core metric: a real 0%-retention month looks like missing data, and partial-month
under-counting makes early-offset retention look artificially low.

This is the headline KPI of the feature (ANL-02 "cohort retention %"), and the small-sample
integration test (`test_cohort_small_sample`) only asserts each `retentionPct` is in
`[0,100]` or `None` — it never asserts a *specific* value, so the under-count/zero-vs-null
ambiguity passes CI undetected.

**Fix:** Emit an explicit row for every `(cohort_month, offset)` in range so 0% is
distinguishable from null, and make M0 semantics explicit. Generate the offset grid and
LEFT JOIN the visit aggregation onto it:

```sql
-- after cohort_base / cohort_sizes / visit_months CTEs:
offsets AS (
    SELECT cs.cohort_month, gs.offset
    FROM cohort_sizes cs
    CROSS JOIN LATERAL generate_series(
        0,
        (EXTRACT(YEAR FROM date_trunc('month', now() AT TIME ZONE 'Europe/Moscow'))
         - EXTRACT(YEAR FROM cs.cohort_month)) * 12
        + (EXTRACT(MONTH FROM date_trunc('month', now() AT TIME ZONE 'Europe/Moscow'))
         - EXTRACT(MONTH FROM cs.cohort_month))
    ) AS gs(offset)
),
visited AS (
    SELECT cb.cohort_month,
           ((EXTRACT(YEAR FROM vm.visit_month) - EXTRACT(YEAR FROM cb.cohort_month)) * 12
            + (EXTRACT(MONTH FROM vm.visit_month) - EXTRACT(MONTH FROM cb.cohort_month)))::int AS months_since,
           COUNT(DISTINCT cb.client_id) AS retained_count
    FROM cohort_base cb
    JOIN visit_months vm ON vm.client_id = cb.client_id AND vm.visit_month >= cb.cohort_month
    GROUP BY cb.cohort_month, months_since
)
SELECT o.cohort_month, o.offset AS months_since,
       COALESCE(v.retained_count, 0) AS retained_count,
       cs.cohort_size
FROM offsets o
JOIN cohort_sizes cs ON cs.cohort_month = o.cohort_month
LEFT JOIN visited v ON v.cohort_month = o.cohort_month AND v.months_since = o.offset
WHERE o.cohort_month >= (date_trunc('month', now() AT TIME ZONE 'Europe/Moscow')::date
                         - make_interval(months => :cohort_months))
ORDER BY o.cohort_month, o.offset
```

This makes every offset present (0% renders as `0%`, not `—`), and dense rows let the
service compute a meaningful `max_offset`. At minimum, add an integration assertion that
pins an exact retention value for a deterministic seed so the metric can't silently drift.

## Warnings

### WR-01: `windowMinutes` field documented as "seconds" in two places — comment contradicts the value (120 minutes)

**File:** `apps/backend/app/modules/reports/schemas.py:303`
**Issue:** `LoadNowResponse.window_minutes` carries the inline comment
`# wire: windowMinutes — rolling window used (seconds)`. The value is `LOAD_NOW_WINDOW_MINUTES = 120`
**minutes** (constants.py:81), and the SQL uses `make_interval(mins => :window_minutes)`.
The "(seconds)" annotation is wrong and will mislead any consumer reading the schema.
**Fix:** Change the comment to `# wire: windowMinutes — rolling window length in minutes`.

### WR-02: `_RU_DAY_ABBR` is a verbatim duplicate of `_RU_MONTH_ABBR` (month names, not day names) — dead/misleading constant

**File:** `apps/backend/app/modules/reports/service.py:489-493`
**Issue:** `_RU_DAY_ABBR` is declared as a separate tuple but contains the identical 12
month abbreviations as `_RU_MONTH_ABBR`. `_ru_day_label` (line 501-503) uses it as
`_RU_DAY_ABBR[d.month - 1]` to build labels like `"12 июн"` — so it is functionally a
*month* lookup, not a day-of-week lookup. The constant name and the comment
("Russian day abbreviations") are wrong and invite a future maintainer to "fix" the
duplication by inserting weekday names, which would silently break the `12 июн` labels.
**Fix:** Delete `_RU_DAY_ABBR` and have `_ru_day_label` reuse `_RU_MONTH_ABBR`:
```python
def _ru_day_label(d: date) -> str:
    return f"{d.day} {_RU_MONTH_ABBR[d.month - 1]}"
```

### WR-03: Cohort `cohort_base` comment claims `DISTINCT ON ... keep earliest start_date` but code uses plain `DISTINCT` — no ordering, no earliest-start guarantee

**File:** `apps/backend/app/modules/reports/repository.py:646-654`
**Issue:** The CTE comment states it uses `DISTINCT ON` to "keep earliest start_date for
that month," but the query is `SELECT DISTINCT client_id, date_trunc(...) AS cohort_month`.
Plain `DISTINCT` over `(client_id, cohort_month)` does correctly dedupe to one row per
client per cohort month, but there is no `start_date` selected and no `ORDER BY`, so the
"earliest start_date" claim is meaningless. Misleading comments around dedup logic are a
maintenance hazard (a reader may assume an ordering invariant that does not exist).
**Fix:** Correct the comment to describe the actual behavior (plain `DISTINCT` on
`(client_id, cohort_month)`; multiple same-month memberships collapse to one cohort row).

### WR-04: At-risk `last_visit` aggregates across ALL visits regardless of which membership — never-visited classification can misfire for re-joining clients

**File:** `apps/backend/app/modules/reports/repository.py:540-560`
**Issue:** `last_visit` is `MAX(checked_in_at) ... GROUP BY client_id` over the entire
`visits` table with no membership scoping. `active_memberships` picks the active membership
via `DISTINCT ON (m.client_id) ... ORDER BY m.client_id, m.id DESC`. A client who churned,
then re-joined with a brand-new active membership but has only historical visits from the
*old* membership will be evaluated against those old visits — so a genuinely-new active
member can be flagged "not at-risk" on the strength of visits that predate their current
membership (or vice-versa). For the single-gym pet-project scope this is low-likelihood,
but the at-risk list drives churn outreach and a wrong classification has real cost.
**Fix:** Either document this as an accepted approximation in the docstring, or scope
`last_visit` to `checked_in_at >= <current membership start_date>` by joining
`active_memberships` to the membership `start_date`.

### WR-05: Raw hex colors in dashboard widgets violate the project's semantic-token rule

**File:** `apps/admin-app/src/pages/dashboard/components/TopTrainers.tsx:16-22`; `apps/admin-app/src/pages/dashboard/components/RevenueChart.tsx:133-134`
**Issue:** `TopTrainers` defines `const COLORS = ['#4f46e5','#0891b2','#059669','#d97706','#dc2626']`
used for avatar initials, and `RevenueChart` hardcodes `stopColor="#2dd4a4"` in the gradient.
Both repo CLAUDE.md files mandate semantic tokens only ("Use semantic classes … NOT raw
values"; the frontend ESLint bans raw palette classes). These are theme-fixed colors that
will not adapt to light/dark and bypass the token system. (These two files are outside the
115 diff but are in the dashboard surface this phase wires to real data; flagging because
the phase touches DashboardPage which composes them.)
**Fix:** Replace with chart-palette CSS vars (`var(--chart-1..5)`) / semantic tokens, or at
minimum move the palette into the token layer.

### WR-06: `useClientsReport` default `within` (30) diverges from the dashboard caller and the schema default (7) — silent semantic mismatch

**File:** `apps/admin-app/src/features/reports/api.ts:98`
**Issue:** The hook sends `within: query.within ?? 30`, but the backend
`ClientsReportQuery.within` defaults to `7` (schemas.py:124) and the DashboardPage caller
passes `within: 7`. Any caller that omits `within` will silently get a 30-day expiring
window while the backend/UI assume 7, and the KPI ("expiring within N days") label can
disagree with the data. The `30` magic number is undocumented.
**Fix:** Default to `7` to match the contract (`query.within ?? 7`), or extract a shared
constant; document the choice if 30 is intentional.

## Info

### IN-01: `LoadNowResponse.as_of` is `datetime.now(UTC)` from the app server, not the DB clock used by the window

**File:** `apps/backend/app/modules/reports/service.py:578-583`
**Issue:** The window count uses Postgres `now()`, but `as_of` is the FastAPI process clock.
Under clock skew between app and DB the displayed `asOf` may not exactly correspond to the
window boundary actually used. Cosmetic for a single-host deploy.
**Fix:** Optionally return the DB `now()` alongside the count, or accept the skew.

### IN-02: `AtRiskMembersResponse.count` equals `len(items)`, contradicting the docstring "may exceed items if capped"

**File:** `apps/backend/app/modules/reports/service.py:635-639`; `schemas.py:447`
**Issue:** The DTO docstring says `count` "may exceed items if capped by AT_RISK_MAX_ITEMS,"
but the service sets `count=len(items)` where `items` is already capped at 50 by the SQL
`LIMIT`. So `count` can never exceed `len(items)` and a club with >50 at-risk members will
under-report. The FE `AtRiskWidget` renders "И ещё {count - 5} клиентов" assuming `count`
is the true total. **Fix:** Either run a separate `COUNT(*)` (uncapped) for the true total
and keep `items` capped, or update the docstring + FE copy to reflect "showing up to 50."

### IN-03: Router TODO claims openapi/schema.d.ts regen is pending, but schema.d.ts already contains all four endpoints

**File:** `apps/backend/app/modules/reports/router.py:285-287`
**Issue:** `# TODO Phase 117: regen openapi.json + schema.d.ts + _v32Checks for /reports/cohort
| /reports/anomaly | /reports/at-risk | /reports/load/now` — but those four paths already
exist in `packages/api-client/src/schema.d.ts` (lines 3352–3455), with `content: unknown`
response bodies. Stale TODO; clarify whether only the response-body typing remains.
**Fix:** Update the TODO to scope only the remaining work (typed response bodies), or remove
it if regen is complete.

### IN-04: `AtRiskWidget` recomputes `data.items.slice(0,5)` inside the map for every row

**File:** `apps/admin-app/src/pages/load/components/AtRiskWidget.tsx:67-75`
**Issue:** `.slice(0, 5)` is called once for the outer `.map` and again inside the className
expression (`data.items.slice(0, 5).length - 1`) on each iteration. Minor redundancy; not a
correctness bug. **Fix:** Hoist `const top = data.items.slice(0, 5)` and reuse.

### IN-05: `formatRelativeRu(event.createdAt)` assumes a parseable timestamp but the mapper never guards a malformed `createdAt`

**File:** `apps/admin-app/src/features/dashboard/audit-activity.ts:108`
**Issue:** The mapper is documented as "never throws," and unknown *actions* are handled,
but `formatRelativeRu` is called on `event.createdAt` without a guard. If the wire ever
delivers a non-ISO string, behavior depends on `formatRelativeRu`'s own robustness. The Zod
layer (`AuditLogResponseSchema`) validates upstream, so this is defense-in-depth only.
**Fix:** Confirm `formatRelativeRu` tolerates invalid input (returns a fallback string), or
wrap defensively.

---

_Reviewed: 2026-06-15_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
