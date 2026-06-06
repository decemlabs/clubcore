---
phase: 86-gym-info-cms
verified: 2026-06-06T12:00:00Z
status: human_needed
score: 12/12
overrides_applied: 0
human_verification:
  - test: "docker compose up, run migrations, open PWA on GymInfoSheet"
    expected: "Sheet renders gym name 'Мой зал · Тверская', address, hours with open/closed badge, amenities grid, rules, contacts — all sourced from DB (not data/gym.js)"
    why_human: "Requires live docker stack + browser + seeded Postgres; cannot verify render without running app"
  - test: "Check open/closed badge shows correct state based on current Moscow time"
    expected: "Badge shows 'Сейчас открыто' or 'Закрыто' based on Europe/Moscow wall-clock; secondary line shows close/open time correctly"
    why_human: "Time-dependent behavior requires visual check against real clock in browser"
---

# Phase 86: Gym-Info CMS Verification Report

**Phase Goal:** Клиент видит актуальную информацию о зале из базы данных, а не захардкоженного файла.
**Verified:** 2026-06-06T12:00:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | gym_info table exists with a single seeded baseline row after migrations run | VERIFIED | `0058_gym_info.py` creates table; `0059_seed_gym_info.py` inserts Тверская row with deterministic PK `00000000-0000-0000-0000-000000000001` and `ON CONFLICT (id) DO NOTHING` |
| 2 | Re-running seed migration is a no-op (idempotent ON CONFLICT) | VERIFIED | `ON CONFLICT (id) DO NOTHING` present on line 89 of `0059_seed_gym_info.py`; SUMMARY confirms double `alembic upgrade head` ran clean |
| 3 | Resource.GYM exists and (Action.EDIT, Resource.GYM) is owner-only (reception denied) | VERIFIED | `permissions.py` line 60: `GYM = "gym"` in Resource StrEnum; `(Action.EDIT, Resource.GYM)` in OWNER_ONLY frozenset; integration test `test_reception_put_gym_info_forbidden` asserts 403 |
| 4 | GymInfo singleton can be read and upserted through the repository/service layer | VERIFIED | `repository.get_singleton` selects with `.limit(1)`; `repository.upsert_singleton` applies `model_dump(exclude_unset=True)` via setattr; `service.get_gym_info` raises GymInfoNotFoundError on None; `service.update_gym_info` flushes and commits (D-03 caller-owns-txn) |
| 5 | Backend ↔ frontend RBAC parity holds after adding gym | VERIFIED | `registry.ts` line 26: `'gym' // NEW Phase 86 GYM-02`; `can.ts` lines 77-78: `{ action: 'edit', resource: 'gym' }` under v2.4 comment; SUMMARY reports 279 parity tests passed |
| 6 | A client (require_client) can GET /api/v1/client/gym and receive the seeded gym info | VERIFIED | `router.py` `client_router.get("/gym")` with `Depends(require_client())`; `test_gym_info.py::test_client_get_gym_info_returns_seeded_baseline` asserts name + address + non-empty arrays; commit `272f3e8f` |
| 7 | An owner can PUT /api/v1/gym to update gym info; the change is persisted and returned | VERIFIED | `router.py` `owner_router.put("")` with `require_permission(EDIT, GYM)` and `verify_csrf`; `test_owner_put_gym_info_updates_and_persists` asserts 200 + read-after-write tagline |
| 8 | A reception user gets 403 on PUT /api/v1/gym (owner-only) | VERIFIED | `require_permission(Action.EDIT, Resource.GYM)` declared BEFORE `verify_csrf` (RBAC-04); `test_reception_put_gym_info_forbidden` asserts `status_code == 403` |
| 9 | Unauthenticated/non-client requests to GET /api/v1/client/gym are rejected | VERIFIED | `test_anonymous_get_gym_info_rejected` asserts `status_code in (401, 403)` |
| 10 | GymInfoSheet renders real gym data from GET /api/v1/client/gym (not data/gym.js, not ComingSoon) | VERIFIED | `GymInfoSheet.jsx` contains `import { useClientGymInfo } from '@/lib/clientQueries'`; no `ComingSoon` reference; hook calls `clientRequest('get', '/api/v1/client/gym')` |
| 11 | Loading shows skeleton; query error shows inline error state with pull-to-refresh | VERIFIED | `GymInfoSkeleton` component with `aria-label="Загрузка информации о зале…"` rendered on `gymInfoQuery.isLoading`; `GymInfoError` with "Не удалось загрузить информацию о зале" rendered on `gymInfoQuery.isError`; tests (b) and (c) pass |
| 12 | Social section renders only when social data is present | VERIFIED | `{data.social && data.social.length > 0 && ...}` guard in GymInfoSheet.jsx line 492; tests (e) social-hidden and social-shown both pass |

**Score:** 12/12 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `apps/backend/app/modules/gym/__init__.py` | Empty package init | VERIFIED | File exists |
| `apps/backend/app/modules/gym/models.py` | GymInfo ORM singleton (scalar + JSONB cols) | VERIFIED | `class GymInfo(Base, UUIDPkMixin, TimestampMixin)` with 7 scalar Text cols and 4 JSONB cols |
| `apps/backend/app/modules/gym/schemas.py` | GymInfoResponse + GymInfoUpdateRequest DTOs | VERIFIED | `GymInfoResponse(ResponseData)` + `GymInfoUpdateRequest(BackendSchemaBase)` + `SocialItem` typed sub-model (CR-02 addition) |
| `apps/backend/app/modules/gym/repository.py` | get_singleton + upsert_singleton | VERIFIED | Both functions present; D-03 caller-owns-txn docstring confirmed |
| `apps/backend/app/modules/gym/service.py` | get_gym_info + update_gym_info | VERIFIED | Both functions present; `GymInfoNotFoundError(NotFoundError)` with 404 mapping |
| `apps/backend/app/modules/gym/router.py` | client_router (GET /gym) + owner_router (PUT /gym) | VERIFIED | Both routers defined; `require_client` on GET; `require_permission(EDIT, GYM)` before `verify_csrf` on PUT |
| `apps/backend/alembic/versions/0058_gym_info.py` | gym_info DDL migration | VERIFIED | `op.create_table("gym_info", ...)` with all columns; down_revision `0057_payment_notifications_widen_kind` |
| `apps/backend/alembic/versions/0059_seed_gym_info.py` | Idempotent baseline seed | VERIFIED | `INSERT INTO gym_info ... ON CONFLICT (id) DO NOTHING`; Тверская content; CAST syntax for asyncpg compatibility |
| `apps/backend/app/api/v1/router.py` | Gym router registration | VERIFIED | `gym_client_router` at `/client`, `gym_owner_router` at `/gym`; Phase 86 comment block |
| `apps/backend/alembic/env.py` | GymInfo model registered | VERIFIED | Line 46: `import app.modules.gym.models  # Phase 86 GYM-01 / 0058` |
| `apps/backend/tests/integration/test_gym_info.py` | 5 integration tests | VERIFIED | 5 tests: client read, owner write-then-read, reception 403, anon reject, unknown key 422 |
| `apps/admin-web/src/shared/session/registry.ts` | `'gym'` in Resource union | VERIFIED | Line 26: `'gym' // NEW Phase 86 GYM-02` |
| `apps/admin-web/src/shared/session/can.ts` | `{ action: 'edit', resource: 'gym' }` in OWNER_ONLY | VERIFIED | Lines 77-78 under v2.4 comment block |
| `apps/client-pwa/src/lib/clientQueries.ts` | useClientGymInfo hook + GymInfoData interface | VERIFIED | Interface + hook exported at lines 796-820; `gymInfo` key in `clientPortalKeys` factory (line 43) |
| `apps/client-pwa/src/data/index.js` | useClientGymInfo re-export through swap seam | VERIFIED | Line 57: `useClientGymInfo` in the clientQueries export block with Phase-86 GYM-01 comment |
| `apps/client-pwa/src/screens/sheets/GymInfoSheet.jsx` | Full GymInfoSheet with live data | VERIFIED | 539-line file; all 7 UI sections implemented; no ComingSoon; imports from `@/lib/clientQueries` (D-71-09 boundary correct) |
| `apps/client-pwa/src/screens/sheets/GymInfoSheet.test.jsx` | Vitest coverage (7 tests) | VERIFIED | 7 tests: loaded, loading, error, badge-open, badge-closed, social-hidden, social-shown |
| `packages/api-client/src/schema.d.ts` | Forward entry for /api/v1/client/gym | VERIFIED | Lines 892-905 (client GET) and 1480-1494 (owner PUT) + operations at 7445 and 7497 |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `0059_seed_gym_info.py` | gym_info table | `INSERT INTO gym_info ... ON CONFLICT (id) DO NOTHING` | VERIFIED | Exact pattern confirmed in file |
| `permissions.py OWNER_ONLY` | Resource.GYM | `(Action.EDIT, Resource.GYM)` frozenset entry | VERIFIED | Entry present in OWNER_ONLY frozenset |
| `permissions.py Resource.GYM` | registry.ts + can.ts | RBAC parity mirror | VERIFIED | `'gym'` in registry.ts union; `{ action: 'edit', resource: 'gym' }` in can.ts |
| `gym/router.py GET /gym` | `service.get_gym_info` | `require_client()` principal gate | VERIFIED | `client_get_gym_info` calls `service.get_gym_info(session)` after `require_client()` dep |
| `gym/router.py PUT /gym` | `service.update_gym_info` | `require_permission(EDIT, GYM)` + `verify_csrf` (RBAC-04) | VERIFIED | `require_permission` declared before `verify_csrf` in handler signature |
| `v1/router.py` | gym routers | `v1.include_router(...)` with prefix | VERIFIED | `gym_client_router` at `/client`, `gym_owner_router` at `/gym` |
| `GymInfoSheet.jsx` | `useClientGymInfo` from `@/lib/clientQueries` | hook call to `/api/v1/client/gym` | VERIFIED | Import on line 21 from `@/lib/clientQueries` (not `@/data` — D-71-09 boundary correct) |
| `clientQueries.ts useClientGymInfo` | `/api/v1/client/gym` | `clientRequest('get', '/api/v1/client/gym')` | VERIFIED | `queryFn` calls `clientRequest('get', '/api/v1/client/gym')` on line 815 |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `GymInfoSheet.jsx` | `gymInfoQuery.data` | `useClientGymInfo()` → `clientRequest('get', '/api/v1/client/gym')` → `GET /api/v1/client/gym` → `service.get_gym_info` → `repository.get_singleton` → `select(GymInfo).limit(1)` | Yes — DB query with seeded row | FLOWING |
| `test_gym_info.py` (test_client_get_gym_info) | `resp.json()["data"]` | Live in-memory ASGI test with SAVEPOINT session; seed row comes from migration 0059 applied to test DB | Yes — integration test asserts "Мой зал · Тверская" from DB | FLOWING |

### Behavioral Spot-Checks

Step 7b: No running server to test against. Integration tests (5 tests in `test_gym_info.py`) serve as behavioral verification of all API behaviors. SUMMARY reports 5 passed.

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| GymInfoSheet.test.jsx — 7 vitest tests | `pnpm vitest run src/screens/sheets/GymInfoSheet.test.jsx` | 7 passed (per SUMMARY 86-03) | PASS (claimed; see Human Verification for live stack check) |
| Backend integration test — 5 tests | `uv run pytest tests/integration/test_gym_info.py -q` | 5 passed (per SUMMARY 86-02) | PASS (claimed; see Human Verification for live stack check) |

### Probe Execution

No `probe-*.sh` scripts found for this phase. SUMMARY reports tests ran via `pytest` and `vitest run`. No conventional probe file convention applicable here.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| GYM-01 | 86-02, 86-03 | Клиент видит инфо о зале в PWA через GET /client/gym | SATISFIED | `GET /api/v1/client/gym` implemented and wired to GymInfoSheet; integration test asserts seeded content returned |
| GYM-02 | 86-01, 86-02 | Owner создаёт/обновляет gym-info через owner-only write-API (reception 403) | SATISFIED | `PUT /api/v1/gym` with `require_permission(EDIT, GYM)`; reception 403 test passes; no admin-web UI by requirement |
| GYM-03 | 86-01 | Базовая запись gym-info засеяна (seed/миграция) | SATISFIED | Migration 0059 seeds Тверская content with `ON CONFLICT (id) DO NOTHING`; double-run is a no-op |

All 3 phase requirements (GYM-01, GYM-02, GYM-03) satisfied. No orphaned requirements.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `service.py` | 28 | Word "placeholder" in docstring | INFO | "show an appropriate placeholder rather than a generic error" — this is a comment about UX behavior, not a code placeholder. Not a stub. |

No TBD, FIXME, or XXX markers found in any phase-modified files. No empty return stubs, no `return null` in rendering paths.

**Note on gym.js:** `data/gym.js` was intentionally retained per CONTEXT.md decision. GymInfoSheet no longer imports from it (the import is from `@/lib/clientQueries`). The file remains for other unrelated consumers and the STATIC_PHOTOS constant is inlined directly in GymInfoSheet.jsx — this is the documented product decision (D-86-03-STATIC-PHOTOS), not a stub.

### Human Verification Required

#### 1. End-to-end render on fresh docker stack (Success Criterion 3)

**Test:** Run `docker compose up`, execute `alembic upgrade head`, open the PWA, navigate to GymInfoSheet.
**Expected:** Sheet renders gym name "Мой зал · Тверская", address "Тверская, 18, 3 этаж", hours rows, amenities grid (8 items), rules list (5 items), contacts with phone and email — all from the seeded DB row. No fallback to `data/gym.js` content (structurally the same here, but proves live DB path is active).
**Why human:** Requires running docker compose + live Postgres + seeded migrations + browser. Cannot verify the full render pipeline programmatically without the stack.

#### 2. Open/closed badge time-dependent behavior in browser

**Test:** Open GymInfoSheet in a browser where the current Moscow time is known. Compare badge state against gym hours (Пн–Пт 07:00–23:00, Сб 09:00–22:00, Вс 09:00–21:00).
**Expected:** Badge shows "Сейчас открыто" (chip-accent) during open hours with "до HH:MM" secondary line; shows "Закрыто" (chip-danger) outside hours with "откроется в HH:MM" secondary line. Today's row appears first.
**Why human:** Badge derivation uses `Intl.DateTimeFormat` with `timeZone:'Europe/Moscow'` — the vitest tests mock the clock, but the live browser behavior across different user timezones requires manual verification.

### Gaps Summary

No gaps found. All 12 must-have truths are VERIFIED. The 2 human verification items are behavioral checks requiring a live environment — they do not indicate missing implementation, only that the full end-to-end path (docker stack + browser render) cannot be asserted statically.

---

_Verified: 2026-06-06T12:00:00Z_
_Verifier: Claude (gsd-verifier)_
