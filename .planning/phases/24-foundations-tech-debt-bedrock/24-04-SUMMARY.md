---
phase: 24-foundations-tech-debt-bedrock
plan: 04
subsystem: api
tags: [memberships, query-params, mock-http-parity, fastapi, pydantic, vitest, tech-debt]

# Dependency graph
requires:
  - phase: 17-memberships-instances
    provides: MembershipListQuery DTO + GET /api/v1/memberships endpoint + repository.list_memberships predicate composition + integration test fixtures
  - phase: 22-frontend-memberships
    provides: admin-web mock + http memberships service + MembershipsListPage filter toggle + BLK-06 single-page collapse
  - phase: 24-foundations-tech-debt-bedrock
    provides: 24-03's resolver `today` injection pattern (mirrored for `list_memberships`'s Europe/Moscow today resolution)
provides:
  - "?expiring=true&within=N (1..30, default 7) on GET /api/v1/memberships, server-side filtered + paginated"
  - "Pydantic 422 on within=0 / within=31"
  - "ValidationAppError query_invalid {status: incompatible_with_expiring} on conflicting filters"
  - "Mock + http parity: both impls accept query.within; http forwards to backend, drops client-side filter + BLK-06 collapse"
  - "TypeScript contract MembershipsListQuery exposes within?: number"
affects:
  - 28-frontend-pwa-final  # FE-13 wires within selector UI + flips MembershipsListPage to honest pagination

# Tech tracking
tech-stack:
  added: []  # no new libraries; reuses ValidationAppError, Pydantic Field, SQLAlchemy ORM, Vitest
  patterns:
    - "DTO: bool flag + bounded int via Pydantic Field(ge=1, le=30) — defence-in-depth at schema layer"
    - "Repository conflict check raised at boundary AFTER predicate composition refactor (else-branch keeps legacy status filter intact)"
    - "Setting .code on instance to override AppError class-level default when subclassing isn't justified"
    - "Mock+http parity: contract change drives both impls; http strips post-filter when backend gains parity (D-24-13)"

key-files:
  created:
    - apps/backend/tests/integration/memberships/test_list_expiring.py
    - apps/admin-web/src/shared/api/services/mock/memberships.expiring.test.ts
    - .planning/phases/24-foundations-tech-debt-bedrock/deferred-items.md
  modified:
    - apps/backend/app/modules/memberships/schemas.py
    - apps/backend/app/modules/memberships/repository.py
    - apps/backend/app/modules/memberships/router.py
    - apps/admin-web/src/shared/api/contracts/memberships.ts
    - apps/admin-web/src/shared/api/services/mock/memberships.ts
    - apps/admin-web/src/shared/api/services/http/memberships.ts

key-decisions:
  - "Set ValidationAppError.code='query_invalid' on the instance because AppError.__init__ stores positional arg as `message`; subclassing wasn't justified for a single conflict path."
  - "Inclusive-window predicate uses `today + (within - 1)` per PATTERNS.md §6b. Boundary fixtures pin within=7 → today+6 included / today+7 excluded; within=14 → today+13 included / today+14 excluded."
  - "Mock keeps BLK-06 single-page collapse for in-memory predictability; only the http adapter strips it because the backend now paginates the filtered set honestly (D-24-13)."
  - "Repository owns its own Europe/Moscow `today` resolution for the list path. The resolver path keeps the explicit-`today`-kwarg purity (24-03), but `list_memberships` is operator-facing and resolves wall-clock once per call."

patterns-established:
  - "Dual-context flat AppError envelope: tests assert top-level `body['code']` / `body['fields']`, NOT nested `body['error']['code']`"
  - "Mock parity tests follow the seed-and-inject pattern: `loadDB()` returns a parsed snapshot — mutations require `saveDB()` to persist back to versioned localStorage"

requirements-completed: [DEBT-02]

# Metrics
duration: 8min
completed: 2026-05-08
---

# Phase 24 Plan 04: ?expiring=true&within=N Backend + Mock/Http Parity Summary

**Backend gains `GET /api/v1/memberships?expiring=true&within=N` (1..30, default 7) with inclusive end-date semantics + 422 conflict on incompatible status; admin-web mock parametrizes `query.within ?? 7` and http drops its client-side filter + BLK-06 single-page pagination collapse so both impls share semantics with the backend.**

## Performance

- **Duration:** ~8 min
- **Started:** 2026-05-08T18:37:23Z
- **Completed:** 2026-05-08T18:45:37Z
- **Tasks:** 2
- **Files modified:** 6 (3 backend + 3 admin-web)
- **Files created:** 3 (1 backend integration test, 1 admin-web Vitest, 1 deferred-items.md)

## Accomplishments

- **Backend ?expiring=true&within=N contract live.** `MembershipListQuery` exposes `expiring: bool = False` + `within: int = Field(default=7, ge=1, le=30)`. Pydantic 422 on out-of-range `within`. Repository forces `status='active'` when `expiring=True` and applies the inclusive window `[today_msk, today_msk + (within - 1)]`. Conflict on `expiring=true&status=expired` returns 422 `query_invalid` with `fields.status="incompatible_with_expiring"` (no silent override).
- **Pagination envelope intact on the backend.** No single-page collapse — a 25-row result with `pageSize=10` reports `total=25` and 10 items on page 1.
- **Admin-web mock + http parity restored.** Mock reads `query.within ?? 7`; http forwards both params and no longer post-filters or collapses pagination. The legacy `EXPIRING_DAYS = 7` constant is gone from both files. The unused `todayMSK` import is dropped from the http adapter.
- **9 backend integration tests + 5 admin-web Vitest cases.** Backend coverage: default-within boundary inclusivity, explicit within=14 boundary, Pydantic bound rejections (within=0 / within=31), non-active exclusion, status conflict, `status=active` compatibility, `expiring=false` ignoring `within`, pagination envelope intactness. Admin-web: `within=undefined` defaults to legacy 7-day window (FE-08 D-2 non-regression), within=14 boundary inclusivity (today+13 in / today+14 out), 7d-subset-of-14d invariant, `expiring=false` silently ignoring `within`, `status='active'` forcing.

## Task Commits

1. **Task 1: Backend MembershipListQuery + repository predicate + 422 conflict + integration tests** — `dfa3072` (feat)
2. **Task 2: admin-web mock+http parity (drop client-side filter, forward expiring/within)** — `60f3a43` (feat)

## Files Created/Modified

- `apps/backend/app/modules/memberships/schemas.py` — `MembershipListQuery` extended with `expiring` + `within` fields (Pydantic-bounded). Updated docstring with conflict semantics.
- `apps/backend/app/modules/memberships/repository.py` — `list_memberships` extended with `expiring=True` branch (status forcing, inclusive end-date window, MSK today). Conflict path raises `ValidationAppError` with `code="query_invalid"`. Else-branch preserves legacy `status` filter.
- `apps/backend/app/modules/memberships/router.py` — endpoint docstring enumerates `expiring` and `within` query params.
- `apps/backend/tests/integration/memberships/test_list_expiring.py` (NEW) — 9 integration tests covering happy path, boundary inclusivity, Pydantic bound rejections, status forcing, conflict envelope, status=active compatibility, expiring=false silent ignore, and pagination envelope intactness.
- `apps/admin-web/src/shared/api/contracts/memberships.ts` — `MembershipsListQuery` exposes `within?: number`. Updated `expiring` comment to drop "client-side filter flag".
- `apps/admin-web/src/shared/api/services/mock/memberships.ts` — drops module-local `EXPIRING_DAYS` constant; reads `query.within ?? 7`; inclusive cutoff matches backend predicate.
- `apps/admin-web/src/shared/api/services/http/memberships.ts` — drops client-side filter + BLK-06 single-page collapse; forwards `expiring`/`within` to backend; drops unused `todayMSK` import.
- `apps/admin-web/src/shared/api/services/mock/memberships.expiring.test.ts` (NEW) — 5 Vitest cases pinning the FE-08 D-2 non-regression default and the inclusive-boundary contract.
- `.planning/phases/24-foundations-tech-debt-bedrock/deferred-items.md` (NEW) — 3 pre-existing admin-web typecheck errors recorded for follow-up (out of scope for this plan).

## Decisions Made

- **Setting `.code` on the `ValidationAppError` instance vs subclassing.** `AppError.__init__(message, *, fields)` stores the positional arg as `message`; the class-level `code = "validation_error"` was being returned in 422 responses. Two options: (a) subclass `_QueryInvalidError(ValidationAppError)` with `code = "query_invalid"`, or (b) post-construction `err.code = "query_invalid"`. Chose (b) — single conflict path, no need for a class hierarchy point. If more `query_invalid` callsites arrive in v1.4+, refactor to a subclass.
- **Inclusive-window formula matches PATTERNS.md §6b**, not the alternate phrasing in `<behavior>`. The plan's `<behavior>` block had "today+7 included with within=7" but `<action>` Step B and PATTERNS.md §6b stipulate `end_date <= today + (within - 1)` — i.e. within=7 caps at today+6 inclusive. Plan's NOTE explicitly authorized this resolution. Boundary fixtures pin the actual contract.
- **Mock keeps BLK-06 single-page collapse.** D-24-13 says only the http adapter strips it (the backend now paginates honestly). Mock stays in-memory and predictable; matching backend pagination semantics in mock would require synthetic page-counting that adds no operator value.
- **Repository resolves `today` for `list_memberships`** rather than receiving it as a kwarg (unlike `find_active_for_client` which does receive `today` per 24-03). Rationale: `list_memberships` is operator-facing (one HTTP request → one wall-clock read); the resolver is called from cron-adjacent paths where determinism matters more.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `ValidationAppError("query_invalid", ...)` returns code="validation_error", not "query_invalid"**
- **Found during:** Task 1 (running `test_list_expiring_status_conflict_returns_422`)
- **Issue:** `AppError.__init__(message, *, fields)` stores the positional arg as `message`; the class-level `code = "validation_error"` was being returned in the 422 envelope. The conflict test asserted `body["code"] == "query_invalid"` and failed.
- **Fix:** Set `err.code = "query_invalid"` on the instance after construction. Inline comment cites `AppError` class-level default. The hard contract from D-24-11 / PATTERNS.md S-4 (use existing `ValidationAppError`, don't add a parallel class) is preserved.
- **Files modified:** `apps/backend/app/modules/memberships/repository.py`
- **Verification:** `test_list_expiring_status_conflict_returns_422` passes — `body["code"] == "query_invalid"` and `body["fields"]["status"] == "incompatible_with_expiring"`.
- **Committed in:** `dfa3072` (Task 1 commit)

**2. [Rule 1 - Bug] Conflict envelope shape in test fixtures: `body["error"]["code"]` vs flat `body["code"]`**
- **Found during:** Task 1 (writing the conflict test)
- **Issue:** The orchestrator's prompt and the plan referenced `body["error"]["code"]=="query_invalid"`, but the codebase's `register_exception_handlers` (`app/core/exceptions.py:243-256`) emits a flat envelope: `{"code": ..., "message": ..., "fields": ...}` — no `error` key wrapping.
- **Fix:** Test asserts `body["code"]` and `body["fields"]["status"]` directly. Docstring on the test file documents the actual envelope shape.
- **Files modified:** `apps/backend/tests/integration/memberships/test_list_expiring.py`
- **Verification:** Conflict test passes against the real handler.
- **Committed in:** `dfa3072` (Task 1 commit)

**3. [Rule 1 - Bug] Vitest mock fixture didn't persist — `loadDB()` returns a parsed snapshot, not a live reference**
- **Found during:** Task 2 (running the within=14 boundary test)
- **Issue:** First draft of `injectMembership` mutated the `loadDB()` snapshot directly. `loadDB()` calls `JSON.parse(localStorage.getItem(...))` each time, so the mutation didn't persist across the subsequent `memberships.list({...})` call (which calls `loadDB()` again, gets a fresh parse). The `inWindow` fixture wasn't visible.
- **Fix:** After mutating, call `saveDB(db)` to write the modified DB back to the versioned localStorage key (`sportzal:mock:v1`). Inline comment cites the snapshot semantics.
- **Files modified:** `apps/admin-web/src/shared/api/services/mock/memberships.expiring.test.ts`
- **Verification:** All 5 Vitest cases pass.
- **Committed in:** `60f3a43` (Task 2 commit)

**4. [Rule 3 - Blocking] Ruff line-length on docstring (>100 chars)**
- **Found during:** Task 1 (`uv run ruff check`)
- **Issue:** Updated `MembershipListQuery` docstring header line was 100 chars + `"""` → over the project line limit.
- **Fix:** Shortened the header to "GET /api/v1/memberships query parameters (Phase 17 D-09; Phase 24 DEBT-02)."
- **Files modified:** `apps/backend/app/modules/memberships/schemas.py`
- **Verification:** `ruff check` clean.
- **Committed in:** `dfa3072` (Task 1 commit)

---

**Total deviations:** 4 auto-fixed (3 Rule 1 bugs, 1 Rule 3 blocking)
**Impact on plan:** All four were corrections of small mismatches between the plan's prompt text and the actual codebase contracts (envelope shape, AppError ctor semantics, mock DB persistence model). No scope creep; the contract delivered matches D-24-10..D-24-13 exactly.

## Issues Encountered

- **Pre-existing admin-web typecheck errors** in 3 unrelated files (`SellMembershipDialog.tsx:99`, `CheckInPage.test.tsx:83`, `RecentVisitsBlock.test.tsx:46`) surfaced during `pnpm typecheck`. Verified pre-existing by stashing 24-04 changes and re-running — same 3 errors. Recorded in `deferred-items.md`. Out of scope for 24-04 (DEBT-02 mock/http parity); recommend resolution as a small follow-up plan in v1.3 (e.g. inside Phase 28 FE-13's typecheck pass) or a dedicated tech-debt micro-plan.

## Threat Flags

None — plan stayed within the documented threat model (T-24-04-01..04). All four threats have implemented mitigations: `Field(ge=1, le=30)` caps the date-range scan (T-01), authz unchanged (T-02), conflict raises 422 with discriminating field (T-03), all predicates use SQLAlchemy ORM (T-04).

## User Setup Required

None — the contract change is server-side schema + repository + admin-web service code only. No env vars, no external services. Phase 28 (FE-13) will surface a `within` selector in `MembershipsListPage` if it chooses; Phase 24 leaves the FE-08 default (7-day window) intact in the UI.

## Next Phase Readiness

- **Phase 28 FE-13** can now flip `MembershipsListPage` to honest pagination on `VITE_API_MODE=http` (the http adapter no longer collapses to a single page) and optionally wire a `within` selector — both backend contract + admin-web service contract are ready.
- **Phase 25 freeze migration (DEBT MEM-FRZ)** unaffected — the new `frozen` status string in CHECK constraint (24-01) doesn't intersect the expiring filter contract (which forces `status='active'`).
- No blockers introduced. Plan's success criteria all satisfied; integration suite (162 tests) + admin-web memberships suite (29 tests) green.

## Self-Check: PASSED

**Files exist:**
- `apps/backend/tests/integration/memberships/test_list_expiring.py` — FOUND
- `apps/admin-web/src/shared/api/services/mock/memberships.expiring.test.ts` — FOUND
- `.planning/phases/24-foundations-tech-debt-bedrock/deferred-items.md` — FOUND
- `apps/backend/app/modules/memberships/schemas.py` (modified) — FOUND
- `apps/backend/app/modules/memberships/repository.py` (modified) — FOUND
- `apps/backend/app/modules/memberships/router.py` (modified) — FOUND
- `apps/admin-web/src/shared/api/contracts/memberships.ts` (modified) — FOUND
- `apps/admin-web/src/shared/api/services/mock/memberships.ts` (modified) — FOUND
- `apps/admin-web/src/shared/api/services/http/memberships.ts` (modified) — FOUND

**Commits exist:**
- `dfa3072` (Task 1) — FOUND
- `60f3a43` (Task 2) — FOUND

---
*Phase: 24-foundations-tech-debt-bedrock*
*Completed: 2026-05-08*
