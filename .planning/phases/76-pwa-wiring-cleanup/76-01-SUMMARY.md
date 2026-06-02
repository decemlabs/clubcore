---
phase: 76-pwa-wiring-cleanup
plan: "01"
subsystem: client-pwa
tags: [react, tanstack-query, live-data, nhome-01, nhome-02]
dependency_graph:
  requires: [Phase 69 GET /client/trainers endpoint, Phase 69 GET /client/plans endpoint]
  provides: [useClientTrainers hook, live trainer avatar strip, live plan info chip]
  affects: [apps/client-pwa/src/screens/HomeScreen.jsx, apps/client-pwa/src/lib/clientQueries.ts]
tech_stack:
  added: []
  patterns: [TanStack Query useQuery, @/data swap seam re-export, D-76-04 fail-open fallback]
key_files:
  created:
    - apps/client-pwa/src/lib/clientQueries.trainers.test.ts
  modified:
    - apps/client-pwa/src/lib/clientQueries.ts
    - apps/client-pwa/src/data/index.js
    - apps/client-pwa/src/screens/HomeScreen.jsx
    - apps/client-pwa/src/screens/HomeScreen.identity.test.jsx
decisions:
  - "Used liveTrainers fallback to STATIC_TRAINERS_FALLBACK (direct import per D-76-05) so static trainers.js file is preserved and never crashes on failed fetch"
  - "pluralPlan helper inlined in HomeScreen.jsx (single usage; no separate module needed)"
  - "Plan chip renders only when plans?.length > 0; on loading/error the existing hardcoded tariff selector layout stays visible per D-76-09"
  - "Avatar IIFE pattern for the live/fallback render avoids repeated variable declarations in JSX"
metrics:
  duration: 6min
  completed_date: "2026-06-02"
  tasks: 3
  files: 5
---

# Phase 76 Plan 01: PWA Home Wiring — Trainer Strip + Plan Chip Summary

Live trainer avatar strip (NHOME-01) and plan info chip (NHOME-02) wired to `GET /client/trainers` and `GET /client/plans` respectively, with fail-open fallbacks and a full identity test suite update.

## What Was Built

### Task 1: useClientTrainers() hook + @/data re-export (TDD)

- Added `trainers: () => [...clientPortalKeys.all, 'trainers'] as const` to `clientPortalKeys` factory in `clientQueries.ts`
- Added `useClientTrainers()` export — byte-for-byte copy of `useClientPlans()` with path changed to `/api/v1/client/trainers` (staleTime 30_000, unknown[] cast, JSDoc citing D-76-01)
- Added `useClientTrainers` to the named re-export block in `data/index.js` alongside `useClientPlans`

### Task 2: HomeNewbie + HeroNewbie live data wiring

**HomeNewbie (NHOME-01):**
- Replaced `import TRAINERS from '@/data'` with `useClientTrainers` hook call inside `HomeNewbie`
- Added separate direct `STATIC_TRAINERS_FALLBACK` import from `@/data/trainers.js` (bypasses swap seam per D-76-05)
- Loading state: 3 grey skeleton circles (34px, `var(--surface-2)`, no pulse, per D-76-04)
- Live state: `liveTrainers.slice(0, 3)` with per-index accent colors; initial from `[...(tr.full_name ?? tr.name ?? '').trim()][0]`
- Fallback: `STATIC_TRAINERS_FALLBACK` when `liveTrainers` is empty/null (D-76-04)
- Overflow chip `+{count - 3}` shown when `count > 3` (live count drives number)

**HeroNewbie (NHOME-02):**
- Added `useClientPlans()` call inside `HeroNewbie`
- Added `pluralPlan(n)` module-level helper for Russian plural (тариф/тарифа/тарифов)
- Plan chip renders `.chip` span when `plans?.length > 0`: `"{N} {pluralPlan(N)} · от {formatMoney(min)}/мес"`
- `minMonthlyKopecks = Math.min(...plans.map(p => Math.round(p.price_kopecks / (p.duration_days / 30))))` per D-76-06
- On loading/error/empty: chip renders nothing; existing hardcoded tariff selector layout stays (D-76-09)

### Task 3: Identity test update (TDD)

- Extended `vi.mock('@/data')` factory with `useClientTrainers` and `useClientPlans` shims
- Added `vi.mock('@/data/trainers.js')` for the direct `STATIC_TRAINERS_FALLBACK` import
- Added `vi.mock('@/utils/format.js')` with deterministic `formatMoney: (k) => String(k/100)`
- `beforeEach` safe defaults: empty data arrays, `isLoading: false`
- **NHOME-01 test**: mock two live trainers with `full_name: 'Олег Борисов'` / `'Нина Козлова'`; assert 'О' renders; assert static 'А' (Аня from fallback) does NOT render
- **NHOME-02 test**: mock two plans; assert chip text matches `/тарифа · от .+\/мес/` and contains "2 тарифа"
- All 7 tests pass (5 pre-existing + 2 new)

## Verification

- `pnpm exec tsc -b` in `apps/client-pwa`: exits 0
- `pnpm lint` in `apps/client-pwa`: exits 0
- `pnpm build` in `apps/client-pwa`: exits 0 (55.83 kB HomeScreen bundle)
- `pnpm exec vitest run src/screens/HomeScreen.identity.test.jsx`: 7/7 pass
- Full test suite: 64/64 pass

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None — all data sources are live API hooks with fail-open fallbacks.

## Threat Flags

None — no new network endpoints, auth paths, file access patterns, or schema changes introduced. Both hooks (`useClientTrainers`, `useClientPlans`) are read-only catalog reads already IDOR-safe (Phase 69/75). Fail-open behavior per T-76-02 mitigation is implemented (D-76-04/09).

## Self-Check: PASSED

All created/modified files confirmed present. All task commits verified in git log:
- `cc2041cb` — test(76-01): RED phase failing test for useClientTrainers
- `462b18f4` — feat(76-01): GREEN phase — useClientTrainers hook + key + re-export
- `fd8bcee3` — feat(76-01): HomeNewbie trainer strip + HeroNewbie plan chip wired
- `fe42609d` — feat(76-01): identity test updated with new mocks + NHOME-01/02 assertions
