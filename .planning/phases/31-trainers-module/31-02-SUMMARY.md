---
phase: "31"
plan: "02"
subsystem: admin-web
tags: [trainers, mock-service, react, tanstack-query, tanstack-router, rbac, vitest]
dependency-graph:
  requires:
    - "31-01"  # Trainer ORM, migration, FastAPI router (backend)
  provides:
    - trainers-mock-service
    - trainers-entity
    - trainers-feature-components
    - trainers-route
  affects:
    - admin-web/shared/api/services  # added trainers to mock+http swap seam
    - admin-web/shared/i18n/ru.ts    # new trainers i18n block
    - admin-web/shared/api/services/mock/_db.ts  # added trainers[] to DB
tech-stack:
  added:
    - TrainersPage / TrainersTable / TrainerFormDialog / DeleteTrainerAlertDialog components
    - useTrainersList / useCreateTrainer / useUpdateTrainer / useDeleteTrainer hooks
    - TanStack Router route with validateSearch + beforeLoad RBAC guard
    - Trainer entity type with branded TrainerId
    - createTrainerSchema / updateTrainerSchema (Zod, shared with mock service)
  patterns:
    - Lazy-seed pattern in mock service (seeds 8 trainers on first getDB() call)
    - Empty phone string coercion in Zod ('' → undefined before regex)
    - vi.hoisted() + vi.mock('sonner') for toast capture in component tests
    - _latency mock (delay → Promise.resolve()) to eliminate timing flakiness
key-files:
  created:
    - apps/admin-web/src/entities/trainer/index.ts
    - apps/admin-web/src/features/trainers/model/schema.ts
    - apps/admin-web/src/features/trainers/api/keys.ts
    - apps/admin-web/src/features/trainers/api/hooks.ts
    - apps/admin-web/src/features/trainers/components/TrainerStatusBadge.tsx
    - apps/admin-web/src/features/trainers/components/ActiveFilterPill.tsx
    - apps/admin-web/src/features/trainers/components/TrainersTable.tsx
    - apps/admin-web/src/features/trainers/components/TrainerFormDialog.tsx
    - apps/admin-web/src/features/trainers/components/DeleteTrainerAlertDialog.tsx
    - apps/admin-web/src/features/trainers/components/TrainersPage.tsx
    - apps/admin-web/src/routes/_protected/trainers.tsx
    - apps/admin-web/src/shared/api/services/mock/trainers.ts
    - apps/admin-web/src/shared/api/services/http/trainers.ts
    - apps/admin-web/src/shared/api/services/mock/trainers.crud.test.ts
    - apps/admin-web/src/shared/api/services/mock/trainers.rbac.test.ts
    - apps/admin-web/src/features/trainers/__tests__/trainers.crud.test.tsx
    - apps/admin-web/src/features/trainers/__tests__/trainers.filter.test.tsx
    - apps/admin-web/src/features/trainers/__tests__/trainers.rbac.test.tsx
  modified:
    - apps/admin-web/src/shared/api/services/mock/_db.ts
    - apps/admin-web/src/shared/api/services/mock/index.ts
    - apps/admin-web/src/shared/api/services/http/index.ts
    - apps/admin-web/src/shared/i18n/ru.ts
decisions:
  - "RBAC guard uses literal `role !== 'owner'` not can() — D-31-19: reception can view trainer list via API for PT-session picker, but admin-web /trainers route is owner-only (D-31-22 default active='true')"
  - "Zod empty-string coercion: phone '' → undefined before regex. Required because RHF uncontrolled inputs emit '' not null/undefined for empty optional fields"
  - "HTTP trainers placeholder re-exports from mock (Phase 35 will replace with real httpFetch calls) — needed to satisfy swap seam TypeScript contract"
  - "useDeleteTrainer uses onSuccess (not onSettled) so trainer_in_use 409 stays visible in AlertDialog before list invalidation clears the mutation state"
  - "Toast test uses _latency mock to zero delay — avoids accumulating 3x 120-300ms (list + create + re-list) causing 10s waitFor timeout"
metrics:
  duration: "~3 hours (context-compacted continuation)"
  completed: "2026-05-14T14:07:47Z"
  tasks-completed: 3
  files-changed: 22
---

# Phase 31 Plan 02: Admin-Web Trainers Route Summary

Admin-web mock-mode `/trainers` route with full vertical slice: Trainer entity + Zod schemas + 8-seeded mock service + i18n strings + TanStack Query hooks + 6 React components + TanStack Router typed route with RBAC guard + 32 Vitest tests covering CRUD, RBAC, and filter URL parity.

## Tasks Completed

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| 1 | Trainer entity + mock service + i18n | `1e84e2e` | `entities/trainer`, `model/schema.ts`, `mock/trainers.ts`, `_db.ts`, `ru.ts` |
| 2 | Feature components + hooks + route | `4410fe8` | `TrainersPage`, `TrainerFormDialog`, `DeleteTrainerAlertDialog`, `hooks.ts`, `trainers.tsx` route |
| 3 | Vitest specs (CRUD + RBAC + filter) | `2b745d5` | `trainers.crud.test.tsx`, `trainers.rbac.test.tsx`, `trainers.filter.test.tsx` |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical Functionality] HTTP swap-seam placeholder for trainers**
- **Found during:** Task 2 (TypeScript compilation)
- **Issue:** `services.trainers` did not exist in the HTTP service bundle. The swap seam at `shared/api/services/index.ts` picks impl by `VITE_API_MODE`; without an HTTP counterpart TypeScript errors blocked compilation.
- **Fix:** Created `shared/api/services/http/trainers.ts` as a Phase 35 placeholder re-exporting from mock. Updated `http/index.ts` to include it.
- **Files modified:** `src/shared/api/services/http/trainers.ts` (new), `src/shared/api/services/http/index.ts`
- **Commit:** `4410fe8`

**2. [Rule 1 - Bug] Empty phone string fails regex validation on form submit**
- **Found during:** Task 3 (toast test timed out — `createTrainer.mutateAsync` throwing validation error instead of succeeding)
- **Issue:** RHF uncontrolled inputs emit `""` for untouched optional fields. `z.string().regex(PHONE_REGEX)` rejects `""`, causing a `validation_failed` DomainError that was silently caught, preventing `toast.success` from firing.
- **Fix:** Added `.transform((v) => (v === '' ? undefined : v)).pipe(...)` before the regex check in `createTrainerSchema`.
- **Files modified:** `src/features/trainers/model/schema.ts`
- **Commit:** `2b745d5`

**3. [Rule 1 - Bug] TanStack Router `redirect()` returns Response with `.options`, not plain object**
- **Found during:** Task 3 RBAC test design
- **Issue:** Initial test assumed `redirect()` throws `{ to, search }`. Actual implementation throws a `Response` with `.options.to` and `.options.search`.
- **Fix:** Used `isRedirect()` type guard and accessed `response.options['to']` / `response.options['search']` in `trainers.rbac.test.tsx`.
- **Files modified:** `src/features/trainers/__tests__/trainers.rbac.test.tsx`
- **Commit:** `2b745d5`

## Test Results

| Suite | Tests | Result |
|-------|-------|--------|
| `mock/trainers.crud.test.ts` | 11 | PASS |
| `mock/trainers.rbac.test.ts` | 5 | PASS |
| `trainers.crud.test.tsx` | 9 | PASS |
| `trainers.rbac.test.tsx` | 3 | PASS |
| `trainers.filter.test.tsx` | 4 | PASS |
| **Total** | **32** | **PASS** |

Full suite regression: 270/270 tests pass across 46 test files.

## Known Stubs

None. All UI data is wired to the real mock service (lazy 8-trainer seed). No placeholder text or hardcoded empty arrays flow to the UI.

## Threat Flags

None. The new route's `beforeLoad` guard enforces owner-only access at the route level (redirects reception to `/?forbidden=/trainers`). Mock service enforces `can(role, action, resource)` for all mutations. No new network endpoints in this plan (frontend-only mock).

## Self-Check: PASSED

Files verified present:
- `apps/admin-web/src/entities/trainer/index.ts` - FOUND
- `apps/admin-web/src/features/trainers/components/TrainersPage.tsx` - FOUND
- `apps/admin-web/src/routes/_protected/trainers.tsx` - FOUND
- `apps/admin-web/src/shared/api/services/mock/trainers.ts` - FOUND
- `apps/admin-web/src/features/trainers/__tests__/trainers.crud.test.tsx` - FOUND

Commits verified:
- `1e84e2e` - FOUND (feat: trainer entity + mock service + i18n + DB extension)
- `4410fe8` - FOUND (feat: trainers feature components + hooks + route)
- `2b745d5` - FOUND (test: Vitest specs for /trainers)
