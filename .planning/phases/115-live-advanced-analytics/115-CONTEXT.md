# Phase 115: Live & Advanced Analytics - Context

**Gathered:** 2026-06-15
**Status:** Ready for planning

<domain>
## Phase Boundary

Advanced + live analytics for the owner (ANL-02, ANL-03, ANL-04):

1. **New backend aggregate endpoints** on the EXISTING reports module (window functions over
   the existing `visits` + `memberships` tables — NO schema changes): cohort retention,
   visit-anomaly, and at-risk members. Owner-only (mirror existing reports RBAC).
2. **Live gym-load** — NEW `GET /api/v1/reports/load/now` returning a current in-gym headcount
   (rolling-window approximation — there is NO checkout model), surfaced as "сейчас в зале" on
   the Load page.
3. **Dashboard real data** — wire the activity feed to the EXISTING owner-only `GET /audit-log`,
   top-trainer KPIs to the EXISTING `GET /reports/trainers`, and the plans sales chart to the
   EXISTING `GET /reports/revenue`; remove the mock widgets.

Out of scope: a check-in/check-out model (live count is a window approximation); ML-based
forecasting; per-member retention drill-downs beyond the cohort grid; new persisted tables.
</domain>

<decisions>
## Implementation Decisions

### Live gym-load (load/now) — no checkout model
- **Headcount = distinct clients with `checked_in_at` within a rolling window** ending now
  (approximation of "currently present", since `Visit` has only `checked_in_at`, no checkout).
- **Window length:** configurable, default ~120 minutes (≈ average session). Read from settings
  if a suitable knob exists; otherwise a named constant.
- **Endpoint:** `GET /api/v1/reports/load/now` → `{ count, asOf, windowMinutes }`.
- **RBAC:** owner-only (`require_permission(VIEW, REPORTS)` — already OWNER_ONLY); reception 403.

### Advanced analytics metric definitions
- **Cohort retention:** cohort = the month a membership STARTED; retention = % of the cohort
  with ≥1 visit in each subsequent month. Computed with window functions over visits+memberships.
- **Visit-anomaly:** a gym_date whose daily visit count deviates > 2σ from a trailing rolling
  mean (≈14-day window); flag both spikes and drops.
- **At-risk member:** a client with an ACTIVE membership whose last visit was > 14 days ago
  (churn risk). Returned as a list/count for the widget.
- **RBAC:** all new aggregate endpoints are owner-only (same as existing reports); reception 403.

### Dashboard feed / KPIs / sales (wire to existing endpoints)
- **Activity feed:** existing owner-only `GET /audit-log` (most recent N events; render
  human-readable labels per the audit taxonomy). No new backend.
- **Top-trainer KPIs:** existing `GET /reports/trainers`. No new backend.
- **Plans sales chart:** existing `GET /reports/revenue` (revenue mix by plan). No new backend.
- **Remove mock widget data**; render a clear empty state per widget when its endpoint returns
  nothing.

### Claude's Discretion
- Exact response schema field names (camelCase wire) and Pydantic/Zod shapes for the new
  cohort/anomaly/at-risk endpoints; whether they are one composite "advanced report" endpoint
  or separate routes (prefer separate, focused routes under /reports/...).
- Cohort grid time-span (e.g. last 6–12 cohort months) and anomaly window exact size.
- Whether load/now polls on an interval (e.g. refetchInterval) or is fetched on mount/focus.
- Chart primitives reused for cohort grid / anomaly chart (existing Recharts wrappers).
</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- **Reports module** (`apps/backend/app/modules/reports/`): router has revenue/clients/visits/
  trainers reports + CSVs + audit-log; `repository.py` has `fetch_visits_daily`/`fetch_visits_hourly`
  (window-function patterns to mirror); `service.py` aggregate orchestration; `schemas.py`
  ResponseData aggregates (NOT paginated — D-11). Add cohort/anomaly/at-risk/load-now here.
- **Audit-log read:** `GET /audit-log` (paginated, owner-only, AUD-01..06) — feed source.
  Audit taxonomy + payloads in `app/core/audit*.py` for human-readable label mapping.
- **Trainers report:** `GET /reports/trainers` (`get_trainers_report`) — top-trainer KPI source.
- **Revenue report:** `GET /reports/revenue` (`get_revenue_report`) — plans sales chart source.
- **Visit model:** `app/modules/visits/models.py` — `checked_in_at` (server now()), generated
  `gym_date` (MSK), `client_id`, `membership_id`. NO checkout column (drives the window approximation).
- **RBAC:** `Resource.REPORTS` is OWNER_ONLY; `require_permission(VIEW, REPORTS)` gates reception out.
- **Frontend dashboard:** `apps/admin-app/src/features/dashboard/api.ts` already has per-domain
  hooks (`useScheduleToday`, `useExpiringMemberships`) replacing the monolithic mock — follow that
  pattern for new hooks. Widgets: `pages/dashboard/components/` — ActivityFeed, TopTrainers,
  RevenueChart, KpiStrip, OccupancyNow, etc. `features/reports/` (api + schemas) for report hooks.
- **Load page:** `pages/load/LoadPage.tsx` (+ phase-114 widgets) — add the "сейчас в зале" counter.
  `features/load/api.ts` for the new useLoadNow hook.

### Established Patterns
- Modular monolith; reports are aggregate ResponseData (no pagination); window functions in
  repository; `require_permission(VIEW, REPORTS)` owner-only gate; backend tests httpx ASGITransport.
- Frontend: per-feature TanStack Query hooks + `staffRequest`; `can()` gating; semantic tokens;
  MSK-pinned dates; Recharts wrappers (AreaTrendChart, BarChart, ChartContainer); Sonner toasts.

### Integration Points
- New routes in `reports/router.py` (cohort, anomaly, at-risk, load/now) + service + repository +
  schemas; registered via the existing reports router mount (no new RBAC resource — reuse REPORTS).
- New FE hooks in `features/reports/api.ts` + `features/load/api.ts`; new dashboard/load widget
  wiring; mock removal.
- OpenAPI regen DEFERRED to Phase 117 — note the new routes for the gate.
</code_context>

<specifics>
## Specific Ideas

- Live "сейчас в зале" is an explicit rolling-window APPROXIMATION (no checkout model) — the UI
  copy / tooltip should not over-claim precision; window default ~120 min.
- Cohort = membership-start month; at-risk threshold = last visit > 14 days with active membership;
  anomaly = >2σ from ~14-day rolling mean.
- Feed/KPIs/sales reuse EXISTING endpoints (audit-log, reports/trainers, reports/revenue) — only
  load/now + cohort + anomaly + at-risk are new backend.
- Backend window-function queries should be unit/integration tested (ASGITransport) incl. the
  empty-data and small-sample edge cases (no NaN, no div-by-zero, stable ordering).
</specifics>

<deferred>
## Deferred Ideas

- Check-in/check-out model for a precise live count — future; this phase approximates via window.
- Forecasting / ML churn scoring — out of scope (simple recency threshold for at-risk).
- OpenAPI regeneration — Phase 117 milestone gate.
</deferred>
