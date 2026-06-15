---
phase: 114-attendance-analytics-existing-reports
reviewed: 2026-06-15T00:00:00Z
depth: standard
files_reviewed: 7
files_reviewed_list:
  - apps/admin-app/src/pages/load/LoadPage.tsx
  - apps/admin-app/src/pages/load/components/DayOfWeekCard.tsx
  - apps/admin-app/src/pages/load/components/DurationPlaceholderCard.tsx
  - apps/admin-app/src/pages/load/components/FrequencyCard.tsx
  - apps/admin-app/src/pages/load/components/PeakHourCard.tsx
  - apps/admin-app/src/pages/load/components/derive.test.ts
  - apps/admin-app/src/pages/load/components/derive.ts
findings:
  critical: 0
  warning: 3
  info: 3
  total: 6
status: issues_found
---

# Phase 114: Code Review Report

**Reviewed:** 2026-06-15T00:00:00Z
**Depth:** standard
**Files Reviewed:** 7
**Status:** issues_found

## Summary

Reviewed the Phase 114 attendance-analytics derivations and their Load-page widgets. The core success criteria hold up under adversarial tracing:

- **Zero/NaN safety:** Verified. `deriveDayOfWeek` guards the per-weekday average (`daysWithData === 0 ? 0 : …`), `derivePeakHour` has an all-zero early-out, and `deriveFrequency` always returns 6 zero-filled buckets. `DayOfWeekCard` guards its percent math against `maxTotal === 0`. No path produces `NaN` or `Infinity`.
- **MSK / DST safety:** Verified. `derive.ts` uses `parseISO` (date-only → local midnight) and never `new Date(dateOnlyString)`. Because the values are date-only with no time component, `getDay()` returns the correct calendar weekday regardless of runtime TZ; the `(getDay()+6)%7` Mon-first shift is correct (tests confirm 2024-01-15 → Пн/0).
- **Peak-hour argmax + ties:** Correct **as wired**. `useLoad` → `fillHourlyBuckets` always emits hours 0–23 in ascending order, so the first-found-argmax tie-break yields the earlier hour. See WR-01 for the undocumented ordering precondition.
- **Frequency bucket boundaries:** Correct. `count < r.max` with maxes `[5,10,15,20,25,∞]` puts 4→"0–4", 5→"5–9", 25→"25+" (tests confirm).
- **No new API calls:** Verified. All three cards derive from the already-fetched `daily`/`hourly` aggregate; no hooks, no fetches.
- **Duration card honesty:** Verified. No numeric/mock data, muted surface, not an error state.
- **noUncheckedIndexedAccess:** Verified. `stats[dow]`, `buckets[idx]`, and `result[0]!` (tests only) are all guarded or non-null-asserted appropriately.

No blockers. Findings are robustness, visualization-correctness, and consistency concerns.

## Warnings

### WR-01: `derivePeakHour` tie-break depends on an undocumented caller ordering precondition

**File:** `apps/admin-app/src/pages/load/components/derive.ts:96-109`
**Issue:** The documented contract is "tie → the EARLIER hour wins," but the implementation iterates `hourly` in **array order**, not by `hour` value. It only returns the earliest *hour* if the input array is already sorted ascending by `hour`. The current caller (`useLoad` → `fillHourlyBuckets`) does emit hours 0–23 in order, so production is correct today — but the function is exported as a standalone pure utility with a contract it does not actually enforce. A future caller passing the raw sparse `hourly` array (the schema explicitly documents buckets as SPARSE and unordered) would silently get the wrong "earlier" hour on ties. The test only exercises the already-sorted `makeHourly` factory, so this gap is invisible to the suite.
**Fix:** Make the tie-break independent of input order, e.g.:
```ts
let best: PeakHour | null = null
for (const b of hourly) {
  if (b.count === 0) continue
  if (best === null || b.count > best.count || (b.count === best.count && b.hour < best.hour)) {
    best = { hour: b.hour, count: b.count }
  }
}
return best
```
Or document the precondition explicitly and assert/sort on entry. Add a test that passes hours in descending order to lock the behavior.

### WR-02: Negative visit counts fall into the "0–4" bucket without validation

**File:** `apps/admin-app/src/pages/load/components/derive.ts:144-152`
**Issue:** `count` is typed `z.number()` in the schema (not constrained to be non-negative). `deriveFrequency` uses `day.count < r.max`, so a negative count (e.g. -3) matches the first range and is labeled "0–4" — a silently wrong label. Same latent issue in `deriveDayOfWeek` (a negative count would reduce `total`/`avgPerWeekday`). Visit counts realistically should never be negative, but nothing in this layer or the Zod contract enforces that, so a backend regression would render misleading analytics rather than an obvious error.
**Fix:** Either tighten the schema (`z.number().int().nonnegative()` for bucket counts in `features/reports/schemas.ts`) so the contract guarantees the precondition, or clamp defensively in the derivation (`Math.max(0, day.count)`). Prefer fixing the schema so all consumers benefit.

### WR-03: Categorical histogram rendered as a smooth interpolated area chart

**File:** `apps/admin-app/src/pages/load/components/FrequencyCard.tsx:26-29`
**Issue:** The "frequency histogram" (count of days per visit-volume bucket) is rendered with `AreaTrendChart`, which draws a `type="monotone"` smoothed area between the 6 categorical buckets. A frequency distribution over discrete bins is not a continuous trend; the monotone interpolation invents values between bins (e.g. a smooth slope between "5–9" and "10–14" suggests intermediate-bin days that don't exist) and the gradient fill implies area-under-curve semantics that are meaningless here. This misrepresents the data — a correctness-of-visualization concern, not just style.
**Fix:** Render as a bar chart (the project already builds bespoke chart markup with Recharts per `apps/admin-app/CLAUDE.md`), or at minimum use `type="step"`/`type="linear"` and drop the area gradient so the discrete-bin nature is visually honest. Confirm with the design reference whether a bar widget was intended.

## Info

### IN-01: Inconsistent style/quote conventions vs. the rest of the app

**File:** `apps/admin-app/src/pages/load/components/derive.ts` (all lines), `DayOfWeekCard.tsx`, `FrequencyCard.tsx`, `PeakHourCard.tsx`, `DurationPlaceholderCard.tsx`, `derive.test.ts`
**Issue:** The new Phase 114 files omit semicolons and use no trailing semicolons, while sibling files in the same app (`LoadPage.tsx`, `format.ts`, `schemas.ts`, `AreaTrendChart.tsx`) use semicolons. The repo CLAUDE.md formatting section ("No semicolons") describes the *frontend* (sportzal) package, but this is `apps/admin-app`, whose existing code consistently uses semicolons. Mixed styles within one package hurt consistency.
**Fix:** Run Prettier/ESLint for `@clubcore/admin-app` and conform to whatever the package's config dictates so the new files match their neighbors. (Confirm against `pnpm -F @clubcore/admin-app lint`.)

### IN-02: Magic font-size literals duplicated across the new cards

**File:** `apps/admin-app/src/pages/load/components/DayOfWeekCard.tsx:33,43`, `DurationPlaceholderCard.tsx:22,25`
**Issue:** Repeated arbitrary Tailwind values (`text-[11.5px]`, `text-[13px]`) are scattered across the new widgets. These are pre-existing patterns in the codebase, but the repetition is a minor maintainability smell.
**Fix:** Low priority; acceptable if it matches the design tokens used elsewhere. No action required unless a shared text-scale utility exists.

### IN-03: "Unreachable" return relies on a comment rather than a type guarantee

**File:** `apps/admin-app/src/pages/load/components/derive.ts:107-108`
**Issue:** `derivePeakHour` ends with `return null` annotated "Unreachable." It is logically unreachable today (`maxCount > 0` guarantees a match), but it exists only to satisfy the type checker and is dead under correct inputs. This is acceptable defensive code; flagged for completeness.
**Fix:** No change required. If WR-01 is addressed with the single-pass argmax above, this dead branch disappears naturally.

---

_Reviewed: 2026-06-15T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
