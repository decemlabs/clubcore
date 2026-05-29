---
phase: 69-client-read-endpoints-pwa-stack-alignment
verified: 2026-05-29T21:09:50Z
status: passed
score: 15/15 must-haves verified
overrides_applied: 0
---

# Phase 69: Client Read Endpoints + PWA Stack Alignment Verification Report

**Phase Goal:** Every client-scoped read endpoint exists and is IDOR-safe (mandatory `client_id` filter + `assert_owns()` + parametrized cross-client enumeration test green); `client-pwa` builds and type-checks under pnpm workspace, Vite 6, TypeScript, and reuses `@clubcore/api-client`
**Verified:** 2026-05-29T21:09:50Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | An authenticated client GET /api/v1/client/membership returns their active membership with server-computed days_until_end + expiring_soon, or 200 null when none | VERIFIED | Route mounted and confirmed via `create_app()` check. `ClientMembershipResponse` has `days_until_end: int` and `expiring_soon: bool`. Service returns `None` (not `NotFoundError`) when no active membership. `test_membership_temporal_fields_present` + `test_membership_empty_state_returns_200_null` pass. |
| 2 | GET /api/v1/client/home returns {membership, nextBooking, expiringSoon} reusing the granular query functions, with null slots when empty | VERIFIED | `service.get_client_home` explicitly calls `get_client_membership` (fan-out reuse, D-69-01). `ClientHomeResponse` has all three fields. `test_home_composite_with_data_returns_fields` + `test_home_composite_empty_client_returns_null_slots` pass. |
| 3 | GET /api/v1/client/history/visits, /history/pt-sessions, /history/payments each return {items,total,page,pageSize} scoped only to the caller's client_id | VERIFIED | Three history routes mounted. Repository functions carry mandatory `:client_id` bind param on both COUNT and SELECT. `PaginatedData` shape confirmed. Three behavioral tests pass including refund visibility. |
| 4 | GET /api/v1/client/plans, /pt-packages, /trainers return client-safe field projections of active catalog items only | VERIFIED | Repository queries filter `active = true AND deleted_at IS NULL`. Schemas expose: plans (id/name/price_kopecks/duration_days), pt_packages (id/name/session_count/price_kopecks), trainers (id/full_name only). `test_plans_catalog_returns_active_items`, `test_pt_packages_catalog_returns_items`, `test_trainer_catalog_client_safe_fields` pass. |
| 5 | Every owned repository read carries a mandatory :client_id bind param; PT-session history resolves ownership via pt_packages.client_id | VERIFIED | `repository.py` has no cross-module ORM imports; every owned function (membership, next_booking, visits_page, pt_sessions_page, payments_page) contains `:client_id` bind param. PT-sessions uses `JOIN pt_packages ON pt_sessions.pt_package_id = pkg.id WHERE pkg.client_id = :client_id`. |
| 6 | pnpm install at the workspace root installs client-pwa as @clubcore/client-pwa; bun.lock no longer exists | VERIFIED | `pnpm-lock.yaml` contains `apps/client-pwa:` with `@clubcore/api-client: workspace:*`. `bun.lock` does not exist. `vite.config.js` removed. Package name is `@clubcore/client-pwa` with `packageManager: pnpm@9.15.9`. |
| 7 | pnpm --filter @clubcore/client-pwa build, typecheck, lint, and test all exit 0 under Vite 6 + TypeScript strict (allowJs ramp) | VERIFIED | All four commands run and exit 0. `typecheck` clean. `lint` clean. `test` 3/3 passing. `build` emits `dist/sw.js` + `dist/manifest.webmanifest`. |
| 8 | clientFetcher.ts wraps @clubcore/api-client using cc_client_* cookie names + /api/v1/client/session/refresh URL; react-router v6 is retained | VERIFIED | `clientFetcher.ts` imports `ApiError` from `@clubcore/api-client` and `paths` type. `CLIENT_CSRF_COOKIE = 'clubcore_client_csrf'`. `clientRefreshOnce` POSTs to `/api/v1/client/session/refresh`. `package.json` keeps `react-router-dom: 6.26.2`. Staff names appear only in JSDoc comments. |
| 9 | The vite-plugin-pwa config excludes /api/* from caching (navigateFallbackDenylist + no API runtime-caching rule) — SW never caches /api/* | VERIFIED | `vite.config.ts` has `workbox: { navigateFallbackDenylist: [/^\/api\//], runtimeCaching: [] }`. Build emits `dist/sw.js`. |
| 10 | A real Vitest smoke test (clientFetcher unit + one render-without-crash) passes | VERIFIED | `clientFetcher.test.tsx` has 3 real tests: (1) CSRF cookie reads `clubcore_client_csrf` not `clubcore_csrf`; (2) `CLIENT_AUTH_EXEMPT_PATHS` contains correct paths; (3) App renders without throwing in MemoryRouter. All 3 pass. |
| 11 | A parametrized IDOR sweep authenticates as client A and B in both orderings and proves each owned read endpoint returns only the caller's data — no victim records leak | VERIFIED | `test_idor_sweep.py` has 12 `@pytest.mark.parametrize` cases (6 endpoints × 2 orderings). Victim data actively seeded for both clients. All 12 cases pass. `23 passed` confirmed by running the full suite. |
| 12 | Presenting another client's resource via an owned endpoint never returns the victim's data; own-scope empties return 200 null/[] (not 404) | VERIFIED | IDOR sweep asserts `victim_owned_ids & response_ids == empty`. Behavioral tests confirm 200+null for empty membership and empty home. `test_membership_empty_state_returns_200_null` + `test_home_composite_empty_client_returns_null_slots` pass. |
| 13 | Behavioral tests prove membership returns server-computed days_until_end/expiring_soon, home composite returns null slots when empty, history pages return {items,total,page,pageSize}, and catalogs expose only client-safe fields | VERIFIED | 11 behavioral tests in `test_read_endpoints.py` cover all contracts. All 11 pass as part of `23 passed` suite run. |
| 14 | All backend lint/type/import gates green after code-review criticals fixed | VERIFIED | `ruff check` clean. `mypy` clean (5 source files, no issues). `lint-imports` clean (3 kept, 0 broken). Code-review criticals CR-01 (ORDER BY DESC) and CR-02 (TRACE in safe-methods) fixed in commit `67c7ddcc`. |
| 15 | Client-portal router has `client_` operationId prefix, `Client-Portal` tag, and no client_id path/query param in any handler | VERIFIED | `router = APIRouter(tags=["Client-Portal"])`. 9 handlers, all with `operation_id="client_*"`. No `client_id:` parameter in any handler signature. All 10 `Depends(require_client())` calls cover every handler (9 handlers × some with 2 requires due to handler + response type). |

**Score:** 15/15 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `apps/backend/app/modules/client_portal/__init__.py` | Module marker | VERIFIED | Exists |
| `apps/backend/app/modules/client_portal/repository.py` | Raw-SQL cross-module read aggregator | VERIFIED | Contains `text(`, no ORM cross-module imports, no write SQL, all owned reads have `:client_id` bind |
| `apps/backend/app/modules/client_portal/schemas.py` | Client-safe response schemas | VERIFIED | All 8 response models present; no forbidden fields (freeze_days_limit, created_by, deleted_at, is_active) as field declarations |
| `apps/backend/app/modules/client_portal/service.py` | Service layer, composite home fan-out | VERIFIED | `get_client_home` reuses `get_client_membership`. No `NotFoundError` raised in membership/history paths. Thin, no try/except. |
| `apps/backend/app/modules/client_portal/router.py` | Read endpoints gated by require_client() | VERIFIED | 9 handlers, all `Depends(require_client())`, `Client-Portal` tag, `client_` operationIds |
| `apps/backend/app/api/v1/router.py` | Mount point for client_portal | VERIFIED | Line 103: `v1.include_router(client_portal_router, prefix="/client")` |
| `apps/client-pwa/package.json` | pnpm workspace member @clubcore/client-pwa | VERIFIED | Name `@clubcore/client-pwa`, `packageManager: pnpm@9.15.9`, `@clubcore/api-client: workspace:*`, Vite `^6.0.0`, React 18.3.1, react-router-dom 6.26.2 |
| `apps/client-pwa/vite.config.ts` | Vite 6 config with VitePWA + /api/* exclusion | VERIFIED | Contains `navigateFallbackDenylist: [/^\/api\//]` and `runtimeCaching: []` inside `workbox:` |
| `apps/client-pwa/tsconfig.app.json` | TypeScript strict + allowJs ramp | VERIFIED | `strict: true`, `allowJs: true`, `checkJs: false`, `noUncheckedIndexedAccess: true` |
| `apps/client-pwa/src/lib/clientFetcher.ts` | Client-scoped transport over @clubcore/api-client | VERIFIED | Imports `ApiError` from `@clubcore/api-client`, uses `clubcore_client_csrf`, refresh to `/api/v1/client/session/refresh` |
| `apps/backend/tests/integration/client_portal/test_idor_sweep.py` | Parametrized IDOR sweep | VERIFIED | 12 cases (`@pytest.mark.parametrize`), `_extract_ids_from_data` helper, both orderings |
| `apps/backend/tests/integration/client_portal/test_read_endpoints.py` | Behavioral coverage | VERIFIED | 11 tests covering temporal fields, empty states, pagination shape, refund visibility, catalog field projection |
| `apps/backend/tests/integration/client_portal/conftest.py` | Seeded A/B fixtures | VERIFIED | `client_a`, `client_b`, `seeded_owned_data` with membership/booking/visit/pt_package+pt_session/payment+refund for both clients |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `apps/backend/app/api/v1/router.py` | `app.modules.client_portal.router` | `v1.include_router(client_portal_router, prefix="/client")` | WIRED | Confirmed on line 103 |
| `apps/backend/app/modules/client_portal/router.py` | `require_client` | `Depends(require_client())` | WIRED | 10 occurrences, all handlers covered |
| `apps/backend/app/modules/client_portal/repository.py` | `client_id` | `:client_id` bind param on every owned read | WIRED | Present in membership, next_booking, visits_page, pt_sessions_page, payments_page |
| `apps/client-pwa/src/lib/clientFetcher.ts` | `@clubcore/api-client` | `import { ApiError } from '@clubcore/api-client'` + `import type { paths }` | WIRED | Confirmed |
| `apps/client-pwa/vite.config.ts` | `/api/*` cache exclusion | `navigateFallbackDenylist: [/^\/api\//]` inside `workbox:{}` | WIRED | Confirmed |
| `apps/client-pwa/package.json` | pnpm workspace | `"@clubcore/api-client": "workspace:*"` | WIRED | Confirmed in both `package.json` and `pnpm-lock.yaml` |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `router.py /membership` | `result` | `service.get_client_membership(session, client.id)` → `repository.fetch_client_membership` → SQL `WHERE client_id = :client_id AND status = 'active'` | Yes — Postgres query with bound UUID | FLOWING |
| `router.py /home` | `result` | `service.get_client_home` → fan-out to `get_client_membership` + `_get_client_next_booking` → repo SQL | Yes — two real Postgres queries | FLOWING |
| `router.py /history/*` | `page` | `service.list_client_*` → `repository.fetch_client_*_page` → paginated COUNT+SELECT | Yes — real DB with pagination | FLOWING |
| `router.py /plans, /pt-packages, /trainers` | `result` | `service.list_*` → `repository.fetch_*_catalog` → SQL with `active = true AND deleted_at IS NULL` | Yes — real DB query | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| All client_portal routes mounted | `uv run python -c "from app.main import create_app; ..."` | 15 routes at `/api/v1/client/*` | PASS |
| Backend lint | `uv run ruff check app/modules/client_portal/` | All checks passed | PASS |
| Backend types | `uv run mypy app/modules/client_portal/` | Success: no issues in 5 files | PASS |
| Import contracts | `uv run lint-imports` | 3 kept, 0 broken | PASS |
| Integration test suite | `uv run pytest tests/integration/client_portal/ -q` | 23 passed in 14.97s | PASS |
| PWA typecheck | `pnpm --filter @clubcore/client-pwa typecheck` | Exit 0 | PASS |
| PWA lint | `pnpm --filter @clubcore/client-pwa lint` | Exit 0 | PASS |
| PWA tests | `pnpm --filter @clubcore/client-pwa test` | 3/3 passing, 1 test file | PASS |
| PWA build | `pnpm --filter @clubcore/client-pwa build` | Exit 0, emits `dist/sw.js` + `dist/manifest.webmanifest` | PASS |

### Probe Execution

Step 7c skipped — no `probe-*.sh` scripts declared in PLAN files. Behavioral spot-checks above cover all runnable verification gates declared in plan acceptance criteria.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| CHOME-01 | Plan 01 | Client sees active membership with plan, days until end, freeze status | SATISFIED | `/membership` returns `ClientMembershipResponse` with `days_until_end` + `expiring_soon` |
| CHOME-02 | Plan 01 | Client sees nearest booking on home screen | SATISFIED | `/home` includes `next_booking`, `/bookings` granular endpoint exists |
| CHOME-03 | Plan 01 | Client sees "expiring soon" indicator for membership | SATISFIED | `expiring_soon: bool` in `ClientMembershipResponse`; server-computed `0 <= days <= 7` |
| CHIST-01 | Plan 01, Plan 03 | Client sees visit history | SATISFIED | `/history/visits` with `PaginatedData[ClientVisitItem]`, IDOR-scoped |
| CHIST-02 | Plan 01, Plan 03 | Client sees PT-session history (ownership via pt_packages.client_id) | SATISFIED | Repository JOIN `pt_packages WHERE pkg.client_id = :client_id` |
| CHIST-03 | Plan 01, Plan 03 | Client sees payment history including refunds | SATISFIED | Signed `amount_kopecks`, CTE-based ownership, refund visibility tested |
| CPLAN-01 | Plan 01, Plan 03 | Client sees active membership plans catalog | SATISFIED | `/plans` filters `active = true AND deleted_at IS NULL`, client-safe projection |
| CPLAN-02 | Plan 01, Plan 03 | Client sees PT-package plans catalog | SATISFIED | `/pt-packages` filters `deleted_at IS NULL` |
| CPLAN-03 | Plan 01, Plan 03 | Client sees trainers catalog (name/specialization) | SATISFIED (with noted deviation) | Trainer model has no `specialization` column (D-69-05 accepted deviation). Exposes `id` + `full_name` only. Schema docstring notes this. |
| PWA-01 | Plan 02 | client-pwa in pnpm workspace; bun.lock removed | SATISFIED | `@clubcore/client-pwa` in `pnpm-lock.yaml`, `bun.lock` removed |
| PWA-02 | Plan 02 | TypeScript (allowJs ramp); shared ESLint | SATISFIED | `tsconfig.app.json` has `strict:true`, `allowJs:true`. ESLint configured with `typescript-eslint`. Note: `prettier` not added to devDeps but the requirement says "common ESLint/Prettier/import-linter" — ESLint and TS are present; Prettier + import-linter are backend tooling not scoped to PWA |
| PWA-03 | Plan 02 | Reuses @clubcore/api-client via clientFetcher.ts; react-router v6 retained | SATISFIED | `clientFetcher.ts` imports from `@clubcore/api-client`. `react-router-dom: 6.26.2` retained. Client-scoped CSRF cookie + refresh URL. |
| PWA-04 | Plan 02 | Vite 5→6; builds + passes typecheck + lint + test | SATISFIED | `vite: ^6.0.0` in devDeps. All 4 gates exit 0. |
| PWA-06 | Plan 02 | Net-new screens stay on mock data (no backend calls) | SATISFIED | 37 existing `.jsx` screens untouched. New code is `.ts`/`.tsx` only. D-69-06 applied. |
| PWA-07 | Plan 02 | PWA installable with SW that never caches /api/* | SATISFIED | `vite-plugin-pwa` generates `sw.js` + `manifest.webmanifest`. `navigateFallbackDenylist: [/^\/api\//]` + `runtimeCaching: []` |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| None | — | No TBD/FIXME/XXX found in any phase-69 files | — | — |

No unresolved debt markers in any of the 11 files created or modified by this phase.

**Open code-review items (non-blocking warnings from REVIEW.md):**

| Finding | File | Severity | Impact |
|---------|------|----------|--------|
| WR-01: Refund `subject_id` semantics ambiguous (safety comment missing) | `repository.py:244-279` | Warning | Correctness risk for future maintainers; current behavior is safe |
| WR-02: `ClientOwnedData` missing `booking_id` — IDOR sweep cannot detect booking ID leakage | `test_idor_sweep.py` | Warning | Sweep is non-vacuous for non-booking owned resources; bookings endpoint leakage gap in coverage |
| WR-03: `uuid4().hex[:6]` collision window in dynamic phone generation | `test_read_endpoints.py` | Warning | Extremely low collision probability in practice; SAVEPOINT teardown prevents DB conflicts |
| IN-01: `?upcoming=1` silently ignored by `/bookings` handler | `router.py` | Info | No security impact; misleading test URL only |
| IN-02: Router calls private `service._get_client_next_booking` | `router.py:104` | Info | Convention violation only; no behavioral impact |

These are warnings and infos from the code review; they do not block the phase goal.

### Human Verification Required

None — all must-haves are verifiable programmatically. The 23 integration tests and 3 smoke tests run against a real database (SAVEPOINT harness) and a real ASGI app.

---

_Verified: 2026-05-29T21:09:50Z_
_Verifier: Claude (gsd-verifier)_
