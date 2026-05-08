---
phase: 22-admin-web-wiring-memberships-visits-active-sessions-ui
plan: "01"
subsystem: api
tags: [fastapi, openapi, typescript, codegen, pydantic, rbac, cache-control]

# Dependency graph
requires:
  - phase: 21-openapi-drift-gate-refresh-api-client-codegen
    provides: openapi.json byte-stable invariants, schema.d.ts typed paths, contract test pattern
  - phase: 19-visits-checkin-endpoint
    provides: visits router + schemas + Settings.gym_hours_start/end typed fields
provides:
  - GET /api/v1/visits/_meta endpoint returning {gymHoursStart, gymHoursEnd} as HH:MM strings
  - VisitsMetaResponse Pydantic model (camelCase via BackendSchemaBase)
  - paths['/api/v1/visits/_meta']['get'] typed surface in schema.d.ts
  - Integration tests (5 assertions) for reception+owner+unauth+Cache-Control+route-order
  - Extended schema.contract.test.ts (_checks tuple length 9→10)
affects:
  - "22-02 through 22-05: all downstream FE plans can now import paths['/api/v1/visits/_meta']"
  - "CheckInPage FE-08(d): outside-hours disable fetches gymMeta from this endpoint"

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Cache-Control header injection via fastapi.Response param (no middleware)"
    - "/_meta route registered BEFORE /{visit_id} to prevent UUID path collision"
    - "TDD RED-GREEN cycle for backend endpoint (test commit then feat commit)"
    - "No DB dependency on config-only endpoints (reads Settings from lru_cache)"

key-files:
  created:
    - apps/backend/tests/integration/test_visits_meta.py
  modified:
    - apps/backend/app/modules/visits/schemas.py
    - apps/backend/app/modules/visits/router.py
    - apps/backend/openapi.json
    - packages/api-client/src/schema.d.ts
    - packages/api-client/src/schema.contract.test.ts

key-decisions:
  - "Cache-Control set via fastapi.Response header injection (not middleware) so policy travels with route"
  - "/_meta route must be registered BEFORE /{visit_id} — enforced by route-order integration test"
  - "VisitsMetaResponse inherits BackendSchemaBase (extra=forbid, camelCase alias_generator)"
  - "No DB session injected — endpoint reads Settings.gym_hours_start/end from lru_cache only"

patterns-established:
  - "Config-only endpoint pattern: no Depends(get_db), reads lru_cached Settings, Cache-Control header via Response param"

requirements-completed:
  - FE-08

# Metrics
duration: 4min
completed: 2026-05-08
---

# Phase 22 Plan 01: visits/_meta Backend Slice Summary

**GET /api/v1/visits/_meta endpoint with Cache-Control: public, max-age=300, serving HH:MM gym-hours window from Settings lru_cache; openapi.json + schema.d.ts regenerated with typed path for FE downstream plans**

## Performance

- **Duration:** 4 min
- **Started:** 2026-05-08T10:28:18Z
- **Completed:** 2026-05-08T10:33:05Z
- **Tasks:** 2 (+ 1 fix commit)
- **Files modified:** 6

## Accomplishments

- `VisitsMetaResponse(BackendSchemaBase)` Pydantic model with `gym_hours_start`/`gym_hours_end` str fields; wire names `gymHoursStart`/`gymHoursEnd` via `to_camel` alias_generator
- `GET /_meta` registered BEFORE `/{visit_id}` in the visits router (path collision safety per D-22-1); Cache-Control header injected via `fastapi.Response` param
- 5 integration tests: 200 reception, 200 owner, 401 unauth, Cache-Control header, route registration order — all pass
- `openapi.json` regenerated with `/api/v1/visits/_meta` GET path + `VisitsMetaResponse` schema component
- `schema.d.ts` regenerated with `paths['/api/v1/visits/_meta']['get']` typed surface — downstream plans 22-02..22-05 can now import this type
- `schema.contract.test.ts` extended: `_VisitsMetaGet` assertion added; `_checks` tuple 9 → 10; `expect(_checks).toHaveLength(10)` updated
- Drift gates green: `git diff --exit-code` clean for both `openapi.json` and `schema.d.ts` after regen commit

## Task Commits

Each task was committed atomically:

1. **Task 1 (TDD RED):** `b99d8df` — test(22-01): add failing integration tests for GET /api/v1/visits/_meta
2. **Task 1 (TDD GREEN):** `8351bfb` — feat(22-01): add VisitsMetaResponse + GET /api/v1/visits/_meta endpoint
3. **Task 2:** `6123ae6` — feat(22-01): regenerate openapi.json + schema.d.ts + extend contract test
4. **Deviation fix:** `1bbc11e` — fix(22-01): fix ruff violations in test_visits_meta.py

_Note: TDD plan — RED commit + GREEN commit per task 1; task 2 is a single feat commit._

## Files Created/Modified

- `apps/backend/tests/integration/test_visits_meta.py` — NEW; 5 integration tests (200 reception, 200 owner, 401 unauth, Cache-Control, route order)
- `apps/backend/app/modules/visits/schemas.py` — Added `VisitsMetaResponse(BackendSchemaBase)` class
- `apps/backend/app/modules/visits/router.py` — Added `GET /_meta` handler + imports (Response, get_settings, VisitsMetaResponse); updated module docstring
- `apps/backend/openapi.json` — Regenerated; adds `/api/v1/visits/_meta` path + `VisitsMetaResponse` schema component
- `packages/api-client/src/schema.d.ts` — Regenerated; adds `paths['/api/v1/visits/_meta']['get']` typed surface
- `packages/api-client/src/schema.contract.test.ts` — Extended with `_VisitsMetaGet` assertion; `_checks` length 9 → 10

## Decisions Made

- **Cache-Control via Response param** (not middleware): the cache policy travels with the route handler explicitly. This makes intent visible at the route level and avoids inadvertently caching other visits endpoints.
- **`/_meta` before `/{visit_id}` ordering**: FastAPI evaluates routes in registration order; `_meta` would be matched by the `UUID` path param with a 422 error (confirmed during RED phase test run which shows exactly this: `"invalid character: found '_' at 1"`). Route-order integration test locks this invariant.
- **No DB dependency**: the endpoint is intentionally O(1) — reads from `lru_cache` Settings, no database round-trip. This enables the `Cache-Control: public, max-age=300` caching strategy and reduces upstream load (T-22-03 accept disposition).
- **`_checks` tuple length 10**: test counted before extending (was 9), incremented by 1 for the new `/visits/_meta` assertion (per plan spec).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed ruff violations in generated test file**
- **Found during:** Task 1 ruff check after GREEN phase commit
- **Issue:** `test_visits_meta.py` had: (a) unused top-level `get_redis` import (each function does a local import instead), (b) I001 import block unsorted, (c) two E501 long assertion lines
- **Fix:** Removed top-level `get_redis` import; ran `ruff check --fix` for I001; wrapped long assertion messages in parentheses for E501
- **Files modified:** `apps/backend/tests/integration/test_visits_meta.py`
- **Verification:** `uv run ruff check` exits 0; all 5 tests still pass
- **Committed in:** `1bbc11e` (separate fix commit after task 2)

---

**Total deviations:** 1 auto-fixed (Rule 1 - Bug in generated test file)
**Impact on plan:** Minor — ruff style fix in test file only. No scope creep, no logic changes.

## Issues Encountered

- During RED phase, confirmed that without the `/_meta` route, FastAPI routes `GET /api/v1/visits/_meta` to `/{visit_id}` handler with a 422 response (`"invalid character: found '_' at 1"`). This validated that the route ordering constraint is real and necessary.

## Next Phase Readiness

- `paths['/api/v1/visits/_meta']['get']` is typed and available in `@sportzal/api-client` — plans 22-02..22-05 can import it immediately
- Backend endpoint live and tested (5 assertions green)
- CI drift gates green; byte-stable openapi.json committed
- Plans 22-02 and 22-03 are now unblocked (parallel-eligible per CD-01)

---
*Phase: 22-admin-web-wiring-memberships-visits-active-sessions-ui*
*Completed: 2026-05-08*

## Self-Check: PASSED
