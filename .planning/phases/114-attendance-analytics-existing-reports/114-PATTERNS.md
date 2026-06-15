# Phase 114: Attendance Analytics on Existing Reports — Pattern Map

**Mapped:** 2026-06-15
**Files analyzed:** 7 (6 new, 1 modified)
**Analogs found:** 7 / 7

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `pages/load/components/derive.ts` | utility | transform | `features/clients/sort.ts` | exact |
| `pages/load/components/derive.test.ts` | test | transform | `features/clients/sort.test.ts` | exact |
| `pages/load/components/DayOfWeekCard.tsx` | component | request-response | `pages/load/components/LoadHeatmapCard.tsx` | exact |
| `pages/load/components/PeakHourCard.tsx` | component | request-response | `pages/load/components/LoadKpis.tsx` + `components/ui/KpiTile.tsx` | role-match |
| `pages/load/components/FrequencyCard.tsx` | component | request-response | `pages/load/components/LoadHeatmapCard.tsx` | exact |
| `pages/load/components/DurationPlaceholderCard.tsx` | component | — | `components/feedback/ComingSoon.tsx` + `components/layout/Card.tsx` | role-match |
| `pages/load/LoadPage.tsx` | component | request-response | `pages/load/LoadPage.tsx` (modify) | self |

---

## Pattern Assignments

### `pages/load/components/derive.ts` (utility, transform)

**Analog:** `apps/admin-app/src/features/clients/sort.ts`

This is a pure-function module with no React imports. It takes the existing `VisitsReportDailyBucket[]` and `VisitsReportHourlyBucket[]` types (from `features/reports/schemas`) and returns derived data structures.

**Imports pattern** (sort.ts lines 1):
```typescript
import type { VisitsReportDailyBucket, VisitsReportHourlyBucket } from '@/features/reports/schemas'
```

**MSK weekday grouping — date helpers** (format.ts lines 1, 60-66, 68-71):
```typescript
// NEVER new Date(dateOnlyString) — DST risk per CLAUDE.md.
// Use parseISO from date-fns (parses to local midnight) then format.
import { format, parseISO } from 'date-fns'
import { ru } from 'date-fns/locale'

// Day-of-week index from ISO date string (MSK-safe):
// parseISO('2024-01-15') → local midnight Date, then getDay() gives 0=Sun…6=Sat
// Reorder to Mon=0…Sun=6 for Russian convention.
const d = parseISO(bucket.date)   // safe — no DST shift for date-only
const dowIndex = (d.getDay() + 6) % 7  // Mon=0, Tue=1 … Sun=6
```

**Core pattern** (sort.ts lines 10-29 as structural guide — pure functions, explicit types):
```typescript
export interface DayOfWeekBucket {
  /** 0 = Пн, 6 = Вс */
  dow: number
  label: string        // 'Пн', 'Вт', …
  total: number
  days: number         // how many calendar days mapped to this dow
  avg: number          // total / days, 0 when days === 0 (zero-guard)
}

export function deriveDayOfWeek(
  daily: VisitsReportDailyBucket[],
): DayOfWeekBucket[] { … }

export interface PeakHour {
  hour: number
  count: number
}

export function derivePeakHour(
  hourly: VisitsReportHourlyBucket[],
): PeakHour | null { … }  // null when all-zero

export interface FrequencyBucket {
  label: string     // e.g. '0', '1–5', '6–10', '11+'
  days: number      // number of calendar days in this bucket
}

export function deriveFrequency(
  daily: VisitsReportDailyBucket[],
): FrequencyBucket[] { … }
```

**Zero/NaN guard pattern** (sort.ts lines 22-26 — explicit null checks before arithmetic):
```typescript
// Always guard division:
avg: days === 0 ? 0 : total / days,

// argmax with early-out for all-zero:
const maxCount = Math.max(...hourly.map((b) => b.count), 0)
if (maxCount === 0) return null
```

---

### `pages/load/components/derive.test.ts` (test, transform)

**Analog:** `apps/admin-app/src/features/clients/sort.test.ts`

**Test file structure** (sort.test.ts lines 1-8):
```typescript
import { describe, expect, it } from 'vitest'
import { deriveDayOfWeek, derivePeakHour, deriveFrequency } from './derive'
import type { VisitsReportDailyBucket, VisitsReportHourlyBucket } from '@/features/reports/schemas'
```

**Minimal fixture factory pattern** (sort.test.ts lines 9-59 — factory function fills only touched fields):
```typescript
function makeDaily(overrides: { date: string; count: number }[]): VisitsReportDailyBucket[] {
  return overrides.map(({ date, count }) => ({ date, count }))
}
function makeHourly(counts: number[]): VisitsReportHourlyBucket[] {
  return counts.map((count, hour) => ({ hour, count }))
}
```

**describe/it naming pattern** (sort.test.ts lines 61-149 — Russian sentence names):
```typescript
describe('deriveDayOfWeek', () => {
  it('all-zero daily → avg = 0, NaN не появляется', () => { … })
  it('single bucket → days=1, total=count, avg=count', () => { … })
  it('MSK weekday: 2024-01-15 = Пн (dow=0)', () => { … })
})
describe('derivePeakHour', () => {
  it('все нули → null', () => { … })
  it('единственный ненулевой → возвращает его час', () => { … })
  it('ничья → ранний час побеждает', () => { … })
})
describe('deriveFrequency', () => {
  it('пустой массив → все бакеты с days=0', () => { … })
  it('single bucket count=3 попадает в правильный бакет', () => { … })
})
```

---

### `pages/load/components/DayOfWeekCard.tsx` (component, request-response)

**Analog:** `apps/admin-app/src/pages/load/components/LoadHeatmapCard.tsx`

**Imports pattern** (LoadHeatmapCard.tsx lines 15-21):
```typescript
import { cn } from '@/lib/cn'
import { Card, CardHeader } from '@/components/layout/Card'
import type { VisitsReportDailyBucket } from '@/features/reports/schemas'
import { deriveDayOfWeek } from './derive'
```

**Card chrome pattern** (LoadHeatmapCard.tsx lines 68-89):
```tsx
<Card as="section" className="flex min-w-0 flex-col">
  <CardHeader
    title="По дням недели"
    subtitle="Суммарные и средние визиты по каждому дню недели за период"
  />
  <div className="px-5 pb-4">
    {/* bar list or AreaTrendChart over 7 dow buckets */}
  </div>
</Card>
```

**Zero-guard at consumption site** (LoadHeatmapCard.tsx lines 46-53 — Math.max guard):
```typescript
// max used for relative bar widths; guard against divide-by-zero:
const maxTotal = Math.max(...buckets.map((b) => b.total), 0)
const barPct = (b: DayOfWeekBucket) => maxTotal === 0 ? 0 : (b.total / maxTotal) * 100
```

**Prop interface** — receives raw `daily` and derives inline (same pattern as LoadHeatmapCard receives raw buckets):
```typescript
export function DayOfWeekCard({ daily }: { daily: VisitsReportDailyBucket[] }) { … }
```

---

### `pages/load/components/PeakHourCard.tsx` (component, request-response)

**Analog:** `apps/admin-app/src/pages/load/components/LoadKpis.tsx` + `components/ui/KpiTile.tsx`

**Imports pattern** (LoadKpis.tsx lines 8-11):
```typescript
import { Card, CardHeader } from '@/components/layout/Card'
import { KpiTile } from '@/components/ui/KpiTile'
import { Clock } from '@/components/icons'
import type { VisitsReportHourlyBucket } from '@/features/reports/schemas'
import { derivePeakHour } from './derive'
```

**KpiTile usage pattern** (LoadKpis.tsx lines 19-35):
```tsx
// KpiTile: icon + label + value (string) + optional unit
<KpiTile
  icon={Clock}
  label="Пиковый час"
  value={peak ? `${peak.hour}:00` : '—'}
  unit={peak ? `${peak.count} визитов` : undefined}
/>
```

**Prop interface** — receives raw `hourly`:
```typescript
export function PeakHourCard({ hourly }: { hourly: VisitsReportHourlyBucket[] }) { … }
```

This card may be a slim `KpiTile`-style tile (no separate Card wrapper) or wrapped in a `Card as="section"`. Both patterns exist. Use `Card` + `CardHeader` for consistency with the other new widgets.

---

### `pages/load/components/FrequencyCard.tsx` (component, request-response)

**Analog:** `apps/admin-app/src/pages/load/components/LoadHeatmapCard.tsx` (card chrome) + `components/charts/AreaTrendChart.tsx` or a horizontal bar list

**Imports pattern** (LoadHeatmapCard.tsx lines 15-21):
```typescript
import { Card, CardHeader } from '@/components/layout/Card'
import type { VisitsReportDailyBucket } from '@/features/reports/schemas'
import { deriveFrequency } from './derive'
```

**Card chrome pattern** (LoadHeatmapCard.tsx lines 91-105 — daily trend section):
```tsx
<Card as="section" className="flex min-w-0 flex-col">
  <CardHeader
    title="Распределение дневной посещаемости"
    subtitle="Сколько дней приходилось на каждый диапазон числа визитов"
  />
  <div className="px-5 pb-4">
    {/* AreaTrendChart over FrequencyBucket[] or horizontal bar list */}
  </div>
</Card>
```

**AreaTrendChart usage when used as bar chart** (LoadHeatmapCard.tsx lines 96-104):
```tsx
<AreaTrendChart
  data={freqBuckets.map((b) => ({ label: b.label, value: b.days }))}
  height={180}
/>
```

**Prop interface**:
```typescript
export function FrequencyCard({ daily }: { daily: VisitsReportDailyBucket[] }) { … }
```

---

### `pages/load/components/DurationPlaceholderCard.tsx` (component, —)

**Analog:** `apps/admin-app/src/components/feedback/ComingSoon.tsx` (pattern) + `components/layout/Card.tsx` (chrome)

This is a coming-soon card scoped to a single card position on the page — NOT the full-page `ComingSoon` component. It must use the `Card` + `CardHeader` chrome to stay visually consistent with the other analytics cards.

**ComingSoon muted-content pattern** (ComingSoon.tsx lines 12-26):
```tsx
// Muted icon + heading + explanatory text, no action button.
<Clock className="size-8 text-fg-subtle" strokeWidth={1.5} />
<h3 className="… text-fg">Длительность визитов</h3>
<p className="… text-fg-muted">
  Данные о длительности появятся, когда backend-агрегат будет
  расширен в следующей фазе.
</p>
```

**Card chrome** (Card.tsx lines 7-26 + CardHeader lines 29-63):
```tsx
export function DurationPlaceholderCard() {
  return (
    <Card as="section" className="flex min-w-0 flex-col">
      <CardHeader
        title="Длительность визитов"
        subtitle="Скоро"
      />
      <div className="flex flex-col items-center justify-center gap-2 px-5 py-10 text-center text-fg-muted">
        <Clock className="size-8 text-fg-subtle" strokeWidth={1.5} />
        <p className="max-w-[280px] text-[13px] leading-[1.55]">
          Агрегат не содержит данных о длительности — виджет появится в следующей фазе.
        </p>
      </div>
    </Card>
  )
}
```

No props. No mock data.

---

### `pages/load/LoadPage.tsx` (modify)

**Analog:** self (current file) — additive change only.

**Current import block** (LoadPage.tsx lines 14-27) — add three new imports after `LoadHeatmapCard`:
```typescript
import { DayOfWeekCard } from './components/DayOfWeekCard'
import { PeakHourCard } from './components/PeakHourCard'
import { FrequencyCard } from './components/FrequencyCard'
import { DurationPlaceholderCard } from './components/DurationPlaceholderCard'
```

**Current render site** (LoadPage.tsx lines 94-97) — the new widgets go below `LoadHeatmapCard` inside the same `allZero`-guarded branch. `DurationPlaceholderCard` renders unconditionally alongside the others (it is a "coming soon", not data-dependent):
```tsx
) : (
  <>
    <LoadHeatmapCard hourly={hourly} daily={daily} />
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
      <DayOfWeekCard daily={daily} />
      <PeakHourCard hourly={hourly} />
    </div>
    <FrequencyCard daily={daily} />
    <DurationPlaceholderCard />
  </>
)}
```

All props come from already-destructured `hourly` and `daily` — no new hooks, no new API calls.

---

## Shared Patterns

### Card chrome
**Source:** `apps/admin-app/src/components/layout/Card.tsx` (Card, CardHeader)
**Apply to:** DayOfWeekCard, PeakHourCard, FrequencyCard, DurationPlaceholderCard

```tsx
// Card: rounded-lg border-[0.5px] border-border bg-surface shadow-1
// CardHeader: title (15px font-[650]) + optional subtitle (xs text-fg-subtle)
<Card as="section" className="flex min-w-0 flex-col">
  <CardHeader title="…" subtitle="…" />
  <div className="px-5 pb-4">…</div>
</Card>
```

### MSK-safe date parsing
**Source:** `apps/admin-app/src/lib/format.ts` lines 1, 60-66
**Apply to:** derive.ts (day-of-week grouping)

```typescript
import { parseISO } from 'date-fns'
// parseISO('YYYY-MM-DD') → local midnight — safe, no DST shift.
// NEVER: new Date('YYYY-MM-DD') — DST risk per CLAUDE.md.
const d = parseISO(bucket.date)
const dow = (d.getDay() + 6) % 7   // Mon=0 … Sun=6
```

### Zero/NaN guard
**Source:** `apps/admin-app/src/pages/load/components/LoadHeatmapCard.tsx` lines 24-26
**Apply to:** derive.ts (every division and argmax)

```typescript
if (max === 0 || count === 0) return 0
const ratio = count / max   // safe — max !== 0
```

### Semantic color tokens only
**Apply to:** all new .tsx files. No raw palette classes (`bg-slate-*`, `bg-blue-*`).
Use: `text-fg`, `text-fg-muted`, `text-fg-subtle`, `bg-surface`, `bg-surface-3`, `border-border`, `text-primary-deep`.

---

## No Analog Found

None. All 7 files have workable analogs in the codebase.

---

## Metadata

**Analog search scope:** `apps/admin-app/src/pages/load/`, `apps/admin-app/src/features/clients/`, `apps/admin-app/src/components/charts/`, `apps/admin-app/src/components/layout/`, `apps/admin-app/src/components/feedback/`, `apps/admin-app/src/components/ui/`, `apps/admin-app/src/lib/format.ts`
**Files scanned:** ~15 source files read
**Pattern extraction date:** 2026-06-15
