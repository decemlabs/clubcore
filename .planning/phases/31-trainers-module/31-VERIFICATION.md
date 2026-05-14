---
phase: 31-trainers-module
verified: 2026-05-14T17:20:00Z
status: human_needed
score: 5/5 must-haves verified
overrides_applied: 0
human_verification:
  - test: "Navigate to /trainers as owner in mock mode; verify 8 seeded trainers visible (5 active default), filter pill works, create/edit dialog opens with RHF validation, deactivate checkbox toggles status badge, delete AlertDialog shows; with ?active=false shows 3 inactive trainers."
    expected: "Full /trainers owner CRUD flow works in browser with mock data"
    why_human: "Visual/interaction verification requires browser; pytest/vitest only covers unit/integration layer"
  - test: "Navigate to /trainers as reception; verify redirect to / with search.forbidden set"
    expected: "Reception is immediately redirected away from /trainers"
    why_human: "Browser-level navigation requires human; beforeLoad unit test passes but end-to-end redirect needs visual confirmation"
gaps: []
deferred: []
---

# Phase 31: Trainers Module Verification Report

**Phase Goal:** Owner может вести каталог тренеров (CRUD + soft-delete через `is_active`), reception видит только активных в PT-session picker; новый бизнес-модуль `trainers/` следует существующему монолитному паттерну, не нарушает `modules-independent` контракт, и закладывает Protocol slot для будущего PT-session валидатора.
**Verified:** 2026-05-14T17:20:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (ROADMAP Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Migration `0011_trainers.py` creates trainers table with all columns + partial UNIQUE on `phone WHERE deleted_at IS NULL AND phone IS NOT NULL` | ✓ VERIFIED | `revision="0011_trainers"`, `down_revision="0010_notifications"`. Index `uq_trainers_phone_alive` with `postgresql_where=text("deleted_at IS NULL AND phone IS NOT NULL")` confirmed in migration file and model `__table_args__`. Trainer class: `Base + UUIDPkMixin + TimestampMixin + SoftDeleteMixin` (no `created_by_user_id`, per D-31-01). |
| 2 | Owner-only CRUD on `/api/v1/trainers` with CSRF; PATCH allows deactivate/reactivate; hard-delete returns 409 `trainer_in_use` on FK; GET `?active=true` accessible to reception | ✓ VERIFIED | Router has 5 endpoints with `require_permission` before `verify_csrf` (RBAC-04 confirmed in router.py lines 86-88, 105-107, 123-125). 31 integration tests all pass. FK 409 monkeypatched via `pgcode="23503"`. `Action.VIEW, Resource.TRAINERS` outside OWNER_ONLY (D-31-09). |
| 3 | Protocol slot `register_trainer_by_id_resolver` registered from BOTH `app/main.py:create_app()` AND `app/workers/telegram_bot.py:main()` | ✓ VERIFIED | `grep -c 'register_trainer_by_id_resolver(' apps/backend/app/main.py` == 1 (line 143). `grep -c 'register_trainer_by_id_resolver(' apps/backend/app/workers/telegram_bot.py` == 1 (line 69). Runtime check: `_trainer_by_id_resolver is not None` confirmed. |
| 4 | Each lifecycle transition emits audit event; SVC001 gate passes | ✓ VERIFIED | 4 `audit.emit()` calls in `service.py` for `trainer_created`, `trainer_deactivated`, `trainer_reactivated`, `trainer_updated`. Combined PATCH emits 2 events. `await session.commit()` in create_trainer (line 86), update_trainer (line 157), delete_trainer (line 184). SVC001: 7 tests passed. |
| 5 | admin-web `/trainers` route (owner-only `beforeLoad`) shows table with active filter pill, create/edit modal (RHF+Zod), deactivate/reactivate buttons, hard-delete with inline 409 surface; mock service synchronized | ✓ VERIFIED | Route uses `role !== 'owner'` literal (D-31-19). `TrainerFormDialog` uses `zodResolver`. `DeleteTrainerAlertDialog` handles `trainer_in_use` with inline `<Alert variant="destructive">`. Mock service in `mock/index.ts` exports `trainers`. 270/270 admin-web tests pass. |

**Score:** 5/5 truths verified

### Requirements Coverage (TRN-01..08)

| Requirement | Description | Status | Evidence |
|-------------|-------------|--------|----------|
| TRN-01 | `trainers` table with partial UNIQUE phone | ✓ SATISFIED | `0011_trainers.py` + `models.py` |
| TRN-02 | Owner-only CRUD POST/GET/PATCH/DELETE with CSRF | ✓ SATISFIED | `router.py` 5-endpoint surface + 16 CRUD tests |
| TRN-03 | PATCH deactivate/reactivate via `isActive` boolean | ✓ SATISFIED | `service.py` D-31-12 combined-PATCH logic + audit tests |
| TRN-04 | `GET ?active=true` accessible to reception | ✓ SATISFIED | `Action.VIEW` outside OWNER_ONLY; reception RBAC test passes |
| TRN-05 | Hard-delete returns 409 `trainer_in_use` on FK violation | ✓ SATISFIED | `_is_fk_violation` maps `pgcode=23503`; monkeypatch test confirmed |
| TRN-06 | Protocol slot double-wired in `main.py` AND `telegram_bot.py` | ✓ SATISFIED | 1 call in each file; runtime slot not None |
| TRN-07 | 4 audit events: `trainer_created/_updated/_deactivated/_reactivated` | ✓ SATISFIED | 4 `audit.emit()` callsites in service.py; audit integration tests confirm exact payload keys |
| TRN-08 | admin-web `/trainers` owner-only route with full UI | ✓ SATISFIED | Route + 6 components + 5 test files; 270/270 passing |

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|---------|--------|---------|
| `apps/backend/alembic/versions/0011_trainers.py` | trainers table migration | ✓ VERIFIED | revision="0011_trainers", down_revision="0010_notifications", partial UNIQUE index |
| `apps/backend/app/modules/trainers/models.py` | Trainer ORM with mixins | ✓ VERIFIED | `class Trainer(Base, UUIDPkMixin, TimestampMixin, SoftDeleteMixin)` |
| `apps/backend/app/modules/trainers/schemas.py` | 4 Pydantic schema classes + PHONE_REGEX | ✓ VERIFIED | All 4 classes present; `PHONE_REGEX = r"^\+[1-9]\d{1,14}$"` |
| `apps/backend/app/modules/trainers/repository.py` | 5 async functions | ✓ VERIFIED | `get_alive`, `list_alive`, `insert_trainer`, `update_trainer`, `hard_delete_trainer` |
| `apps/backend/app/modules/trainers/service.py` | 6 async functions with commits | ✓ VERIFIED | 6 functions; `await session.commit()` at lines 86, 157, 184 |
| `apps/backend/app/modules/trainers/router.py` | 5-endpoint FastAPI router | ✓ VERIFIED | 5 endpoints with RBAC-04 ordering |
| `apps/backend/app/core/dependencies.py` | Protocol slot + TrainerById Protocol | ✓ VERIFIED | `register_trainer_by_id_resolver`, `class TrainerById(Protocol)` |
| `apps/backend/openapi.json` | Includes `/api/v1/trainers` | ✓ VERIFIED | grep count == 4 |
| `apps/backend/tests/integration/trainers/` | 3 test files, 31 tests | ✓ VERIFIED | 31 passed; CRUD(16), audit(7), RBAC(8) |
| `apps/admin-web/src/entities/trainer/index.ts` | TrainerId branded type | ✓ VERIFIED | `export type TrainerId = Brand<string, 'TrainerId'>` |
| `apps/admin-web/src/features/trainers/model/schema.ts` | 4 exports + PHONE_REGEX | ✓ VERIFIED | `createTrainerSchema`, `updateTrainerSchema`, `CreateTrainerInput`, `UpdateTrainerInput` |
| `apps/admin-web/src/features/trainers/api/keys.ts` | `trainersKeys` factory | ✓ VERIFIED | `export const trainersKeys` |
| `apps/admin-web/src/features/trainers/api/hooks.ts` | 4 hooks | ✓ VERIFIED | `useTrainersList/useCreateTrainer/useUpdateTrainer/useDeleteTrainer` |
| `apps/admin-web/src/features/trainers/components/TrainersPage.tsx` | Route component | ✓ VERIFIED | Composes all sub-components |
| `apps/admin-web/src/features/trainers/components/TrainerFormDialog.tsx` | RHF+Zod dialog | ✓ VERIFIED | `zodResolver` wired |
| `apps/admin-web/src/features/trainers/components/DeleteTrainerAlertDialog.tsx` | 409 surface | ✓ VERIFIED | Handles `trainer_in_use` with inline `<Alert variant="destructive">` |
| `apps/admin-web/src/shared/api/services/mock/trainers.ts` | Mock service with RBAC | ✓ VERIFIED | `ensure('view', 'trainers')` + seed of 8 trainers (5 active, 3 inactive) |
| `apps/admin-web/src/routes/_protected/trainers.tsx` | Owner-only route | ✓ VERIFIED | `role !== 'owner'` literal; `validateSearch`, `beforeLoad`, `loaderDeps`, `loader`, `component` |
| `apps/admin-web/src/shared/i18n/ru.ts` | Trainers i18n block | ✓ VERIFIED | `trainers:` top-level block + `shell.nav.trainers: 'Тренеры'`; trainerInUse copy present |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `app/main.py:create_app()` | `trainers/service.py:resolve_trainer_by_id` | `register_trainer_by_id_resolver(trainers_service.resolve_trainer_by_id)` | ✓ WIRED | Line 143 in main.py |
| `app/workers/telegram_bot.py:main()` | `trainers/service.py:resolve_trainer_by_id` | Defensive REG-29-03 second registration | ✓ WIRED | Line 69 in telegram_bot.py |
| `app/api/v1/router.py` | `trainers/router.py` | `v1.include_router(trainers_router, prefix="/trainers")` | ✓ WIRED | Lines 18+26 in api/v1/router.py |
| `trainers/service.py` | `core/audit.py:emit` | 4 emit callsites for lifecycle events | ✓ WIRED | Lines 76-148 in service.py |
| `mock/index.ts` | `mock/trainers.ts` | `import { trainers } from './trainers'` + services const | ✓ WIRED | `services = { auth, clients, memberships, trainers, visits }` |
| `features/trainers/api/hooks.ts` | `mock/trainers.ts` | `services.trainers.list/create/update/delete` | ✓ WIRED | All hooks delegate through services.trainers |
| `routes/_protected/trainers.tsx` | `features/trainers/api/keys.ts` | `trainersKeys.list(search)` in loader | ✓ WIRED | Same key shape used by `useTrainersList` hook |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|--------------|--------|-------------------|--------|
| `TrainersPage.tsx` | `data` from `useTrainersList` | `mock/trainers.ts:list()` → lazy seeds 8 trainers → localStorage | Yes (lazy seed + real CRUD) | ✓ FLOWING |
| `trainers/service.py:list_trainers` | `PaginatedData[Trainer]` | `repository.list_alive` → Postgres SELECT WHERE `deleted_at IS NULL` | Yes (real DB query) | ✓ FLOWING |
| `DeleteTrainerAlertDialog` | `inlineError: string | null` | `useDeleteTrainer().mutate()` → `services.trainers.delete()` | Yes (409 injected via vi.spyOn in tests) | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Backend ruff 0 errors | `uv run ruff check app/` | All checks passed | ✓ PASS |
| Backend mypy 0 errors | `uv run mypy app/` | Success: no issues found in 84 source files | ✓ PASS |
| Import-linter 3 contracts | `uv run lint-imports` | 3 kept, 0 broken | ✓ PASS |
| SVC001 commit gate | `pytest tests/unit/test_service_commit_gate.py` | 7 passed | ✓ PASS |
| Trainers integration tests | `pytest tests/integration/trainers/` | 31 passed in 4.00s | ✓ PASS |
| Full backend suite | `pytest tests/` | 846 passed, 1 failed (pre-existing Phase 30 regression — see below) | ⚠️ WARNING |
| Protocol slot runtime | Python: `d._trainer_by_id_resolver is not None` | True | ✓ PASS |
| admin-web typecheck | `pnpm typecheck` | Exit 0 (no TypeScript errors) | ✓ PASS |
| admin-web lint | `pnpm lint` | 0 errors, 2 pre-existing warnings (not trainers code) | ✓ PASS |
| admin-web tests | `pnpm test -- --run` | 270 passed, 0 failed across 46 files | ✓ PASS |
| No raw Tailwind palette in trainers feature | `grep -rE 'bg-(slate\|gray\|...)-[0-9]' src/features/trainers/` | 0 matches | ✓ PASS |
| TrainerStatusBadge semantic tokens | `grep 'bg-warning' TrainerStatusBadge.tsx` | `bg-warning/10 text-warning-foreground border-warning/30` | ✓ PASS |
| TanStack Router routeTree.gen.ts | `grep "'/_protected/trainers'" routeTree.gen.ts` | Found at lines 155, 207, 257 | ✓ PASS |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|---------|--------|
| `apps/backend/tests/integration/test_rbac_parity.py` | 142 | `assert len(OWNER_ONLY) == 15` — hardcoded count stale since Phase 30 expanded OWNER_ONLY to 26 entries | ⚠️ WARNING | Pre-existing Phase 30 regression; substantive parity tests (pair match, resource values, action values) all pass. Does not affect Phase 31 goal delivery. |
| `apps/admin-web/src/shared/api/services/http/trainers.ts` | 8 | HTTP service re-exports from mock (`export { trainers } from '../mock/trainers'`) | ℹ️ INFO | Intentional Phase 35 placeholder per D-31-25 scope split. Not a stub — explicitly deferred. |

### Human Verification Required

#### 1. Owner /trainers Page End-to-End Flow

**Test:** Log in as owner in mock mode (`VITE_API_MODE=mock`). Navigate to `/trainers`. Verify: (a) page loads showing "Тренеры" heading and "Добавить тренера" CTA; (b) 8 seeded trainers with active filter defaulting to "Активные" (5 trainers shown); (c) click "Неактивные" shows 3 inactive trainers with warning-tinted "Неактивен" badges; (d) click "Добавить тренера", fill fullName + phone, submit — new trainer appears in list with success toast "Тренер добавлен"; (e) click Pencil on active trainer, uncheck "Активный тренер", save — toast "Тренер деактивирован", badge changes; (f) click Trash2, confirm — toast "Тренер удалён", row removed.
**Expected:** All 6 sub-flows work without errors in the browser
**Why human:** Interactive browser session required for visual rendering and Sonner toast verification

#### 2. Reception Redirect from /trainers

**Test:** Log in as reception in mock mode. Navigate directly to `/trainers`. Verify redirect to `/` occurs immediately with `?forbidden=/trainers` in the URL.
**Expected:** Reception never sees the trainers catalog; redirected to home
**Why human:** Browser navigation required; `beforeLoad` unit test passes but end-to-end redirect in real React Router context needs visual confirmation

### Gaps Summary

No blocking gaps found. All 5 ROADMAP success criteria are VERIFIED by codebase evidence.

**One pre-existing WARNING (Phase 30 regression, not Phase 31):**
`tests/integration/test_rbac_parity.py::test_owner_only_count_is_fifteen` fails because Phase 30 expanded `OWNER_ONLY` from 15 to 26 entries but did not update the hardcoded count assertion. The three substantive parity tests (`test_owner_only_pairs_match`, `test_resource_values_match`, `test_action_values_match`) all pass — byte-parity between backend and admin-web RBAC is intact. This regression predates Phase 31 and should be addressed in Phase 32 or a hygiene pass.

**LOCKED_AUDIT_EVENTS count:** Phase 30 ROADMAP promised 51 entries; actual is 53. This too is a Phase 30 counting discrepancy — Phase 31 correctly adds 0 events (all 4 trainer events were pre-registered in Phase 30). Not a Phase 31 blocker.

---

_Verified: 2026-05-14T17:20:00Z_
_Verifier: Claude (gsd-verifier)_
