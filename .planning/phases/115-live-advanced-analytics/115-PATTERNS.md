# Phase 115: Live & Advanced Analytics — Pattern Map

**Mapped:** 2026-06-15
**Files analyzed:** 11 new/modified files
**Analogs found:** 11 / 11

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `apps/backend/app/modules/reports/repository.py` | repository | CRUD / aggregate | same file (add to existing) | exact |
| `apps/backend/app/modules/reports/schemas.py` | model/schema | request-response | same file (add to existing) | exact |
| `apps/backend/app/modules/reports/service.py` | service | CRUD / aggregate | same file (add to existing) | exact |
| `apps/backend/app/modules/reports/router.py` | controller/route | request-response | same file (add to existing) | exact |
| `apps/backend/tests/integration/reports/test_reports_advanced.py` | test | request-response | `tests/integration/reports/test_reports_visits.py` | exact |
| `apps/admin-app/src/features/reports/api.ts` | hook | request-response | same file (add to existing) | exact |
| `apps/admin-app/src/features/reports/schemas.ts` | model/schema | request-response | same file (add to existing) | exact |
| `apps/admin-app/src/features/load/api.ts` | hook | request-response | `features/load/api.ts` + `features/reports/api.ts` | exact |
| `apps/admin-app/src/pages/load/components/` (new widgets) | component | request-response | `pages/load/components/PeakHourCard.tsx` | exact |
| `apps/admin-app/src/pages/dashboard/components/` (wire existing) | component | request-response | `ActivityFeed.tsx`, `TopTrainers.tsx`, `RevenueChart.tsx` | exact |
| `apps/admin-app/src/features/dashboard/api.ts` | hook | request-response | same file (add to existing) | exact |

---

## Pattern Assignments

### `apps/backend/app/modules/reports/repository.py` (add new fetch functions)

**Analog:** same file — `fetch_visits_daily` (lines 374–403) and `fetch_active_memberships_count` (lines 280–305)

**Cross-module read discipline** (lines 1–27 — copy the module-level docstring discipline):
```python
# CROSS-MODULE READ — raw SQL text() only; NO ORM import of Visit/Membership/Client.
# Verified columns (apps/backend/app/modules/visits/models.py):
#   - checked_in_at  DateTime(timezone=True) — raw timestamptz
#   - gym_date       Date STORED GENERATED (MSK)
#   - client_id      UUID NOT NULL
#   - membership_id  UUID NOT NULL
# Verified columns (apps/backend/app/modules/memberships/models.py):
#   - status   String(16) ('active' | 'expired' | 'cancelled' | 'frozen')
#   - end_date Date (inclusive)
```

**Scalar count pattern** (lines 290–305 — for `fetch_load_now_count`):
```python
async def fetch_load_now_count(session: AsyncSession, window_minutes: int) -> int:
    row = (
        (
            await session.execute(
                text(
                    "SELECT COUNT(DISTINCT client_id) AS cnt FROM visits "
                    "WHERE checked_in_at >= now() - make_interval(mins => :window_minutes)"
                ),
                {"window_minutes": window_minutes},
            )
        )
        .mappings()
        .one()
    )
    return int(row["cnt"])
```

**Daily list pattern** (lines 388–403 — template for `fetch_at_risk_members` and `fetch_visit_anomaly`):
```python
rows = (
    (
        await session.execute(
            text("SELECT ... FROM visits WHERE ..."),
            {"from_date": from_date, "to_date": to_date},
        )
    )
    .mappings()
    .all()
)
return [dict(r) for r in rows]
```

**Window function pattern** (lines 176–277 in `fetch_trainer_usage` — CTE structure for cohort):
```python
await session.execute(
    text("""
WITH cohort_base AS (
    SELECT
        client_id,
        date_trunc('month', (start_date AT TIME ZONE 'Europe/Moscow'))::date AS cohort_month
    FROM memberships
    WHERE status IN ('active', 'expired')
),
...
SELECT cohort_month, months_since, COUNT(...) AS retained
FROM ...
GROUP BY cohort_month, months_since
ORDER BY cohort_month, months_since
"""),
    {"cutoff_months": cutoff_months},
)
```

---

### `apps/backend/app/modules/reports/schemas.py` (add new DTOs)

**Analog:** same file — `VisitsReportResponse` (lines 165–172) and `ClientsReportResponse` (lines 127–134)

**ResponseData aggregate pattern** (lines 97–103):
```python
class LoadNowResponse(ResponseData):
    """GET /api/v1/reports/load/now payload — rolling-window in-gym headcount."""

    count: int           # distinct clients checked_in within last window_minutes
    as_of: datetime      # wire: asOf — server UTC timestamp of the query
    window_minutes: int  # wire: windowMinutes — rolling window length used
```

**Nested ResponseData shape** (lines 165–172 — template for CohortRetentionResponse):
```python
class CohortRow(ResponseData):
    cohort_month: str    # 'YYYY-MM'
    months_since: int
    retained_count: int
    cohort_size: int
    retention_pct: float | None  # None when cohort_size=0

class CohortRetentionResponse(ResponseData):
    rows: list[CohortRow]
    cohort_months: int   # number of cohort months computed
```

**Query DTO pattern** (lines 58–67 — `RevenueReportQuery` with alias_generator=to_camel):
```python
class CohortRetentionQuery(BackendSchemaBase):
    """GET /api/v1/reports/cohort — wire: ?cohortMonths=6"""
    cohort_months: int = 6   # alias_generator maps to ?cohortMonths
```

**No-param query** (lines 280–305 — for load/now and at-risk, which take no date params):
```python
# load/now has NO query params — it's a pure point-in-time snapshot.
# Service layer reads LOAD_NOW_WINDOW_MINUTES from constants.py.
```

---

### `apps/backend/app/modules/reports/service.py` (add orchestration functions)

**Analog:** same file — `get_visits_report` (lines 211–254) and `get_clients_report` (lines 178–208)

**Thin orchestrator pattern** (lines 394–412):
```python
async def get_load_now(session: AsyncSession) -> LoadNowResponse:
    """Live gym headcount — rolling window approximation (ANL-04).

    Window length from LOAD_NOW_WINDOW_MINUTES constant (default 120 min).
    Read-only: NO session.commit(), NO session.flush().
    """
    count = await repository.fetch_load_now_count(session, LOAD_NOW_WINDOW_MINUTES)
    return LoadNowResponse(
        count=count,
        as_of=datetime.now(UTC),
        window_minutes=LOAD_NOW_WINDOW_MINUTES,
    )
```

**Validation + repo + assemble pattern** (lines 211–254):
```python
async def get_cohort_retention(
    session: AsyncSession, query: CohortRetentionQuery
) -> CohortRetentionResponse:
    if query.cohort_months < 1 or query.cohort_months > 24:
        raise ValidationAppError("cohort_months must be between 1 and 24")
    rows = await repository.fetch_cohort_retention(session, query.cohort_months)
    return CohortRetentionResponse(
        rows=[CohortRow.model_validate(r) for r in rows],
        cohort_months=query.cohort_months,
    )
```

**Sigma computation in service layer** (for anomaly — mirror `_pivot_revenue_buckets` inline pivot):
```python
def _compute_anomaly(daily_rows: list[dict[str, object]], sigma: float = 2.0) -> list[dict[str, object]]:
    """Flag days where count deviates > sigma from trailing 14-day rolling mean.

    Returns only flagged rows; never NaN (div-by-zero guarded with COALESCE/fallback).
    """
    # Pure Python rolling mean — no new dependency; small dataset (<=366 rows).
```

---

### `apps/backend/app/modules/reports/router.py` (add new GET routes)

**Analog:** same file — `get_visits_report` (lines 109–130) and `get_clients_report` (lines 86–106)

**Standard owner-only route pattern** (lines 109–130 — copy verbatim structure):
```python
@router.get(
    "/cohort",
    response_model=ResponseEnvelope[CohortRetentionResponse],
    summary="Cohort retention grid (owner-only; ANL-02)",
)
async def get_cohort_report(
    query: Annotated[CohortRetentionQuery, Depends()],
    _actor: Annotated[CurrentUser, Depends(require_permission(Action.VIEW, Resource.REPORTS))],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[CohortRetentionResponse]:
    """Cohort = membership-start month; retention = % with ≥1 visit per subsequent month.

    Owner-only: (VIEW, REPORTS) ∈ OWNER_ONLY; reception → 403.
    No try/except — AppError bubbles to _app_error_handler.
    """
    result = await service.get_cohort_retention(session, query)
    return envelope(result)
```

**No-param route pattern** (load/now has no query DTO — use no `Depends()` model):
```python
@router.get(
    "/load/now",
    response_model=ResponseEnvelope[LoadNowResponse],
    summary="Live gym headcount — rolling-window approximation (owner-only; ANL-04)",
)
async def get_load_now(
    _actor: Annotated[CurrentUser, Depends(require_permission(Action.VIEW, Resource.REPORTS))],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[LoadNowResponse]:
    result = await service.get_load_now(session)
    return envelope(result)
```

**Imports to add** (mirror lines 37–56 of router.py):
```python
from app.modules.reports.schemas import (
    # ... existing imports ...
    CohortRetentionQuery,
    CohortRetentionResponse,
    VisitAnomalyResponse,
    AtRiskMembersResponse,
    LoadNowResponse,
)
```

---

### `apps/backend/tests/integration/reports/test_reports_advanced.py` (new test file)

**Analog:** `tests/integration/reports/test_reports_visits.py` (full file — structure to copy exactly)

**File header pattern** (lines 1–13):
```python
"""Integration tests for GET /api/v1/reports/cohort|anomaly|at-risk|load/now (Phase 115 ANL-02..04).

Coverage per endpoint:
  - Owner receives 200 with correct shape.
  - Reception receives 403 ((VIEW, REPORTS) ∈ OWNER_ONLY).
  - Empty-data edge case returns valid empty/zero response (no NaN, no div-by-zero).
  - Small-sample edge case (1 cohort, 1 visit) returns stable result.
  - load/now: 0 visits in window → count=0.
"""
```

**Conftest reuse** (lines 17–30 of `conftest.py` — re-export from memberships conftest):
```python
from tests.integration.reports.conftest import (  # noqa: F401
    authed_client_owner,
    authed_client_reception,
    make_client,
    make_membership,
    make_plan,
    make_visit,
)
```

**Owner 200 + shape assertion pattern** (lines 25–44 of test_reports_visits.py):
```python
async def test_owner_gets_load_now(authed_client_owner: AsyncClient) -> None:
    """Owner GET /reports/load/now returns 200 with count/asOf/windowMinutes."""
    r = await authed_client_owner.get("/api/v1/reports/load/now")
    assert r.status_code == 200, r.text
    body = r.json()["data"]
    assert "count" in body
    assert "asOf" in body
    assert "windowMinutes" in body
    assert isinstance(body["count"], int)
    assert body["count"] >= 0
```

**Reception 403 pattern** (lines 46–55):
```python
async def test_reception_forbidden_load_now(authed_client_reception: AsyncClient) -> None:
    r = await authed_client_reception.get("/api/v1/reports/load/now")
    assert r.status_code == 403, r.text
    assert r.json()["code"] == "forbidden"
```

**Empty-data edge case pattern** (lines 25–44 — must always pass even with no seed data):
```python
async def test_load_now_zero_when_no_recent_visits(authed_client_owner: AsyncClient) -> None:
    """No visits in rolling window → count=0 (not NaN, not error)."""
    r = await authed_client_owner.get("/api/v1/reports/load/now")
    assert r.status_code == 200, r.text
    # count may be 0 or positive depending on DB state; must be a non-negative int
    assert r.json()["data"]["count"] >= 0
```

**make_visit fixture** (conftest.py lines 68–99 — required for data-seeded tests):
```python
# Re-use: make_visit(client_id=..., membership_id=..., checked_in_at=datetime(..., tzinfo=UTC))
# gym_date is STORED GENERATED — never pass it explicitly.
```

---

### `apps/admin-app/src/features/reports/api.ts` (add new hooks)

**Analog:** same file — `useVisitsReport` (lines 36–48) and `useTrainersReport` (lines 97–109)

**Owner-gated hook pattern** (lines 36–48 — copy exactly):
```typescript
export function useCohortReport(query: CohortRetentionQuery, role: Role) {
  return useQuery({
    queryKey: reportsQueryKeys.cohort(query),
    queryFn: async () => {
      const raw = await staffRequest('get', '/api/v1/reports/cohort', {
        query: { cohortMonths: query.cohortMonths },
      });
      return CohortRetentionSchema.parse(raw).data;
    },
    enabled: can(role, 'view', 'reports'),
    staleTime: 30_000,
  });
}
```

**No-param hook** (for load/now — no query DTO):
```typescript
export function useLoadNow(role: Role) {
  return useQuery({
    queryKey: reportsQueryKeys.loadNow(),
    queryFn: async () => {
      const raw = await staffRequest('get', '/api/v1/reports/load/now');
      return LoadNowSchema.parse(raw).data;
    },
    enabled: can(role, 'view', 'reports'),
    staleTime: 60_000,         // or refetchInterval: 60_000 for polling
    refetchInterval: 60_000,   // poll every 60s to show live count
  });
}
```

**Imports block** (lines 16–22 — extend existing):
```typescript
import { useQuery } from '@tanstack/react-query'
import { staffRequest, ApiError } from '@/api/client'
import { can } from '@/shared/session/can'
import { reportsQueryKeys } from './keys'
import {
  // existing ...
  CohortRetentionSchema, VisitAnomalySchema, AtRiskMembersSchema, LoadNowSchema,
} from './schemas'
import type { CohortRetentionQuery, VisitAnomalyQuery } from './schemas'
import type { Role } from '@/shared/session/types'
```

---

### `apps/admin-app/src/features/reports/schemas.ts` (add new Zod shapes)

**Analog:** same file — `VisitsReportSchema` (lines 27–35) and `TrainersReportSchema` (lines 99–107)

**Aggregate schema pattern** (lines 57–65 — ResponseEnvelope `{ data: {...} }` shape):
```typescript
export const LoadNowSchema = z.object({
  data: z.object({
    count: z.number().int().nonnegative(),
    asOf: z.string(),           // ISO-8601 datetime
    windowMinutes: z.number().int().positive(),
  }),
})
export type LoadNowData = z.infer<typeof LoadNowSchema>['data']
```

**Nested list schema** (lines 86–107 — for cohort grid rows):
```typescript
export const CohortRowSchema = z.object({
  cohortMonth: z.string(),      // 'YYYY-MM'
  monthsSince: z.number().int().nonnegative(),
  retainedCount: z.number().int().nonnegative(),
  cohortSize: z.number().int().nonnegative(),
  retentionPct: z.number().nullable(),  // null when cohortSize=0
})
export const CohortRetentionSchema = z.object({
  data: z.object({
    rows: z.array(CohortRowSchema),
    cohortMonths: z.number(),
  }),
})
export type CohortRetentionData = z.infer<typeof CohortRetentionSchema>['data']
export type CohortRow = z.infer<typeof CohortRowSchema>
```

**Query type pattern** (lines 114–134):
```typescript
export type CohortRetentionQuery = { cohortMonths: number }
export type VisitAnomalyQuery = { fromDate: string; toDate: string }
```

---

### `apps/admin-app/src/features/load/api.ts` (add `useLoadNow`)

**Analog:** same file (lines 1–45) — `useLoad` re-exports from `features/reports/api`

**Re-export + thin wrapper pattern** (lines 16–21):
```typescript
// Add alongside useLoad:
export { useLoadNow } from '@/features/reports/api'
// or inline if transform is needed:
export function useLoadNow(role: Role) {
  return useLoadNowFromReports(role)
}
```

The existing file imports from `features/reports/api` and applies client-side transforms. `useLoadNow` needs no transform — export it directly from reports/api or re-export through load/api for colocation with LoadPage.

---

### `apps/admin-app/src/pages/load/components/` (new CohortRetentionCard, VisitAnomalyCard, AtRiskWidget)

**Analog:** `pages/load/components/PeakHourCard.tsx` (full file — exact chrome pattern)

**Card chrome pattern** (lines 1–32):
```typescript
import { Card, CardHeader } from '@/components/layout/Card'
import { KpiTile } from '@/components/ui/KpiTile'
import { SomeIcon } from '@/components/icons'
import type { CohortRetentionData } from '@/features/reports/schemas'

export function CohortRetentionCard({ data }: { data: CohortRetentionData | undefined }) {
  // data may be undefined (owner-gated; show skeleton/empty state)
  return (
    <Card as="section" className="flex min-w-0 flex-col">
      <CardHeader title="Удержание клиентов" subtitle="% когорты с ≥1 визитом по месяцам" />
      <div className="px-5 pb-4 pt-0">
        {/* grid or chart here */}
      </div>
    </Card>
  )
}
```

**Dark "live" card pattern** for a "сейчас в зале" counter — `LiveNowCard.tsx` (lines 1–94):
```typescript
// For the live headcount counter on LoadPage: adapt LiveNowCard.tsx
// Replace data.current (mock) with count from useLoadNow().data?.count
// Replace data.time with formatted asOf timestamp
// Keep the pulse dot + dark gradient chrome
```

**Skeleton + empty state pattern** — `TopTrainers.tsx` (lines 86–97):
```typescript
{isPending ? (
  <div className="flex flex-col gap-2 px-5 py-3">
    <Skeleton className="h-[52px] w-full rounded-xl" />
  </div>
) : data == null || data.rows.length === 0 ? (
  <EmptyState icon={SomeIcon} title="Нет данных" message="..." />
) : (
  /* render content */
)}
```

**Recharts area/bar for anomaly chart** — `RevenueChart.tsx` (lines 1–177):
```typescript
// VisitAnomalyCard uses BarChart/AreaChart from recharts via ChartContainer.
// Mirror the RevenueChart ChartContainer + ChartTooltip pattern.
// Flag anomaly bars with a different fill color (e.g. 'var(--danger)').
import { ChartContainer, ChartTooltip, type ChartConfig } from '@/components/ui/chart'
import { Bar, BarChart, CartesianGrid, XAxis } from 'recharts'
```

---

### `apps/admin-app/src/pages/dashboard/components/` (wire ActivityFeed, TopTrainers, RevenueChart)

**Analogs:** `ActivityFeed.tsx` (full), `TopTrainers.tsx` (full), `RevenueChart.tsx` (full)

**ActivityFeed → audit-log wire:**
- `ActivityFeed` currently receives `data: ActivityFeedData` (mock shape). The wiring replaces the mock with real audit-log data from `features/audit/api.ts`.
- Map AuditLog `action` + `resource_type` pairs → `ActivityType` icons using the existing `ICONS` and `ICON_BG` records (lines 21–49).
- The component itself does NOT change — only the parent (DashboardPage) switches from mock data to hook data.

**TopTrainers → reports/trainers wire:**
- `TopTrainers` already accepts `data: TrainersReportData | undefined` and `isPending: boolean` (lines 11–13). It is ALREADY wired — confirm the parent passes `useTrainersReport()` data.
- If the parent still passes mock data, replace mock call with `useTrainersReport({ fromDate, toDate }, role)` from `features/reports/api`.

**RevenueChart → reports/revenue wire:**
- `RevenueChart` already accepts `data: RevenueReportData | undefined` and `isPending: boolean` (lines 10–15). Same pattern — confirm parent calls `useRevenueReport()`.

**Parent (DashboardPage) hook call pattern** (mirror `features/dashboard/api.ts` lines 41–52):
```typescript
// In DashboardPage or a DashboardDataProvider:
const { data: auditData, isPending: auditPending } = useAuditLog({ pageSize: 20 }, role)
const { data: trainersData, isPending: trainersPending } = useTrainersReport({ fromDate, toDate }, role)
const { data: revenueData, isPending: revenuePending } = useRevenueReport({ fromDate, toDate, groupBy: 'day' }, role)
```

---

### `apps/admin-app/src/features/dashboard/api.ts` (add new hooks)

**Analog:** same file — `useScheduleToday` (lines 41–52) and re-export pattern (lines 76–81)

**New hook pattern** (lines 41–52 — for useActivityFeed / useAuditLogFeed):
```typescript
export const dashboardKeys = {
  // extend:
  activityFeed: ['dashboard', 'activity-feed'] as const,
}

export function useActivityFeed(role: Role) {
  return useQuery({
    queryKey: dashboardKeys.activityFeed,
    queryFn: async () => {
      const raw = await staffRequest('get', '/api/v1/audit-log', {
        query: { pageSize: '20' },
      })
      return AuditLogListSchema.parse(raw).data
    },
    enabled: can(role, 'list', 'audit_log'),
    staleTime: 30_000,
  })
}
```

**Re-export pattern** (lines 76–81 — for new advanced analytics hooks):
```typescript
export {
  useRevenueReport,
  useVisitsReport,
  useClientsReport,
  useTrainersReport,
  useCohortReport,
  useVisitAnomaly,
  useAtRiskMembers,
} from '@/features/reports/api'
```

---

## Shared Patterns

### RBAC owner gate (backend)
**Source:** `apps/backend/app/modules/reports/router.py` lines 70–72
**Apply to:** All four new routes
```python
_actor: Annotated[CurrentUser, Depends(require_permission(Action.VIEW, Resource.REPORTS))],
```
No new Resource needed — `Resource.REPORTS` is already `OWNER_ONLY`.

### ResponseEnvelope + envelope() (backend)
**Source:** `apps/backend/app/modules/reports/router.py` lines 82–83
**Apply to:** All four new routes
```python
result = await service.get_xxx(session, query)
return envelope(result)
```
No try/except — AppError bubbles to `_app_error_handler`.

### Raw-SQL cross-module read discipline (backend)
**Source:** `apps/backend/app/modules/reports/repository.py` lines 1–27 (module docstring)
**Apply to:** All new repository functions
- `from sqlalchemy import text` — never import another module's ORM model.
- Bind params via `:name` placeholders only — no f-string interpolation of user input.
- `.mappings().all()` for list reads; `.mappings().one()` for scalar counts.
- Document verified column names + source file:line for each foreign table accessed.

### ResponseData aggregate schema (backend)
**Source:** `apps/backend/app/modules/reports/schemas.py` lines 50–51
**Apply to:** All new response DTOs
```python
from app.core.schemas import BackendSchemaBase, ResponseData
class XxxResponse(ResponseData): ...
class XxxQuery(BackendSchemaBase): ...
```

### Owner-gated TanStack Query hook (frontend)
**Source:** `apps/admin-app/src/features/reports/api.ts` lines 36–48
**Apply to:** All new frontend hooks (useCohortReport, useVisitAnomaly, useAtRiskMembers, useLoadNow)
```typescript
enabled: can(role, 'view', 'reports'),
staleTime: 30_000,
```
Accept `role: Role` as parameter (WR-04 — avoids double-waterfall).

### Zod schema + `{ data: ... }` envelope (frontend)
**Source:** `apps/admin-app/src/features/reports/schemas.ts` lines 27–35
**Apply to:** All new Zod schemas
```typescript
export const XxxSchema = z.object({
  data: z.object({ /* fields */ }),
})
export type XxxData = z.infer<typeof XxxSchema>['data']
```

### Card chrome + skeleton + empty state (frontend)
**Source:** `apps/admin-app/src/pages/load/components/PeakHourCard.tsx` (full)
**Apply to:** CohortRetentionCard, VisitAnomalyCard, AtRiskWidget
```typescript
<Card as="section" className="flex min-w-0 flex-col">
  <CardHeader title="..." subtitle="..." />
  <div className="px-5 pb-4 pt-0">...</div>
</Card>
```

## No Analog Found

All files have close analogs. No gaps.

## Metadata

**Analog search scope:** `apps/backend/app/modules/reports/`, `apps/backend/tests/integration/reports/`, `apps/admin-app/src/features/reports/`, `apps/admin-app/src/features/dashboard/`, `apps/admin-app/src/features/load/`, `apps/admin-app/src/pages/load/components/`, `apps/admin-app/src/pages/dashboard/components/`
**Files read:** 16
**Pattern extraction date:** 2026-06-15
