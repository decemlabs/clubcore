---
phase: 09-openapi-pipeline-api-client
verified: 2026-05-04T00:00:00Z
status: passed
score: 4/4 success criteria verified; 5/5 requirement IDs satisfied
overrides_applied: 0
re_verification: false
requirements: [API-01, API-02, API-05, API-06, API-07]
gaps: []
deferred: []
---

# Phase 9: OpenAPI Pipeline + packages/api-client — Verification Report

**Phase Goal:** "A change to a backend Pydantic schema either updates `apps/backend/openapi.json` and the generated TS types in the same PR, or CI fails — making FE/BE drift impossible without an explicit 'I really meant it' commit."

**Verified:** 2026-05-04
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (ROADMAP Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| SC-1 | Running `uv run python apps/backend/scripts/export_openapi.py` writes `apps/backend/openapi.json` deterministically (`indent=2, sort_keys=True`, byte-stable across macOS/Linux) without touching Postgres or Redis. | VERIFIED | `09-UAT.md` Test 2: two consecutive runs each wrote 37266 bytes to `apps/backend/openapi.json`; `diff -q /tmp/openapi.run1.json openapi.json` was silent (byte-identical). File ends with `}\n}\n` (trailing newline ✓) and `grep -c '"version": "1.1.0"'` returned 1. CI invokes the same `-m scripts.export_openapi` form (`.github/workflows/ci.yml:51`). The lifespan-safe export script is documented in `09-01-SUMMARY.md` (uses `os.environ.setdefault(...)` to satisfy Settings without live infra). |
| SC-2 | CI runs the export script and `git diff --exit-code apps/backend/openapi.json` — a PR that changed a schema without regenerating fails the build. | VERIFIED | `09-UAT.md` Test 5: locally simulated drift via `sed -i '' 's/"version": "1.1.0"/"version": "9.9.9"/' apps/backend/openapi.json` → `git diff --exit-code` exited 1 (drift detected). CI workflow at `.github/workflows/ci.yml:63-64` adds `git ls-files --error-unmatch` belt-and-braces gate before the diff to close the WR-06 untracked-file silent-pass loophole (per `09-REVIEW-FIX.md` WR-06 fix, commit 2d364f0). |
| SC-3 | CI runs `pnpm --filter @sportzal/api-client codegen` and `git diff --exit-code` against the generated `src/schema.d.ts`. | VERIFIED | `09-UAT.md` Test 4: `apps/admin-web/package.json` `predev` script invokes `pnpm --filter @sportzal/api-client codegen`; `dependencies['@sportzal/api-client']: workspace:*`. Three-way verification: (1) idempotent codegen produces byte-equal `schema.d.ts` to committed copy; (2) adding a `/uat-test-only` path to `openapi.json` produces a 16-line schema delta; (3) restoring the spec restores the schema byte-for-byte. CI frontend gate at `.github/workflows/ci.yml:113-114`. Note: D-07 keeps the schema COMMITTED (not gitignored — ROADMAP wording predates D-07); `09-UAT.md` Test 8 confirmed REQUIREMENTS.md API-05 wording was aligned to D-07 (committed-spec reality). |
| SC-4 | A FE consumer can call `request<P, M>(method, path, init)` from `@sportzal/api-client/fetcher` with `credentials: 'include'`; on 401 (non-`/auth/*`) the wrapper does a single-flight `/auth/refresh` and retries once; failures throw a typed `ApiError { code, message, fields? }`. | VERIFIED | `09-UAT.md` Test 6 (CR-01 path-param interpolation): vitest smoke confirmed three behaviors — substitutes `{client_id}` with provided param, throws `ApiError('client_error', ...)` on missing param, returns path unchanged with no placeholders. `09-UAT.md` Test 7 (CR-02 single-flight): mocked fetch returned 401 for first three non-refresh calls; counted refresh calls explicitly → `refreshCalls === 1` after three concurrent `request()` calls all settled `fulfilled`. The `queueMicrotask` deferral in `refreshOnce()` correctly holds the in-flight slot across the same-tick 401 burst. Cross-reference `09-REVIEW-FIX.md` CR-01 (commit 659e9da) + CR-02 (commit de2ba3a). |

**Score:** 4/4 success criteria verified.

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `apps/backend/scripts/export_openapi.py` | Lifespan-safe export CLI; deterministic JSON (`indent=2, sort_keys=True`); does not touch Postgres/Redis | VERIFIED | `09-01-SUMMARY.md`: lifespan-safe export script implementation. Confirmed by `09-UAT.md` Test 2 (two consecutive byte-stable runs without infra). |
| `apps/backend/openapi.json` | 37266 bytes, `"version": "1.1.0"`, trailing newline, byte-stable | VERIFIED | `09-UAT.md` Test 2: 37266 bytes; `grep -c '"version": "1.1.0"'` returned 1; ends with `}\n}\n`. |
| `packages/api-client/package.json` | Declares `openapi-typescript@^7.13.0` devDep, `codegen` and `typecheck` scripts | VERIFIED | `09-02-SUMMARY.md`: devDep + scripts wired. `09-UAT.md` Test 3 confirms `pnpm --filter @sportzal/api-client typecheck` exits 0 (`tsc --noEmit` clean). |
| `packages/api-client/src/fetcher.ts` | `request<P,M>(method, path, init)` with `credentials: 'include'`, X-CSRF-Token injection, single-flight refresh, path-param interpolation | VERIFIED | `09-02-SUMMARY.md` for base implementation; `09-REVIEW-FIX.md` CR-01 (path-param interpolation, commit 659e9da), CR-02 (single-flight microtask deferral, commit de2ba3a), WR-02 (HeadersInit normalization, commit 5a49974), WR-03 (body-type branching, commit eef3155). UAT Tests 6 + 7 confirm runtime behavior. |
| `packages/api-client/src/errors.ts` | `ApiError` class with `{code, message, fields?}` + `cause` option | VERIFIED | `09-REVIEW-FIX.md` WR-01 (commit 18cab7f): extended constructor to accept `{ cause?: unknown }` options bag and forward to `super(message, options)` (ES2022-native). |
| `packages/api-client/src/index.ts` | Barrel re-exports for `request`, `ApiError`, types | VERIFIED | `09-02-SUMMARY.md`: barrel file present. |
| `packages/api-client/src/schema.d.ts` | Generated, COMMITTED per D-07; byte-deterministic from `openapi.json` | VERIFIED | `09-UAT.md` Test 4: byte-equal idempotent codegen against committed copy; reacts to real type-changing spec edits with corresponding schema delta. |
| `apps/admin-web/package.json` | `predev` invokes `pnpm --filter @sportzal/api-client codegen`; `dependencies['@sportzal/api-client']: workspace:*` | VERIFIED | `09-UAT.md` Test 4 — both fields confirmed verbatim. |
| `.github/workflows/ci.yml` | Backend + frontend drift-gate jobs with `git ls-files --error-unmatch` belt | VERIFIED | `09-03-SUMMARY.md` for initial drift-gate wiring; `09-REVIEW-FIX.md` WR-06 (commit 2d364f0) added `git ls-files --error-unmatch` before each `git diff --exit-code` for both `apps/backend/openapi.json` (`.github/workflows/ci.yml:63-64`) and `packages/api-client/src/schema.d.ts` (`.github/workflows/ci.yml:113-114`). |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `apps/backend/scripts/export_openapi.py` | `app.main.create_app` | Lifespan-safe app construction without Postgres/Redis | WIRED | `09-UAT.md` Test 2 confirms script runs to completion in clean shell with `os.environ.setdefault(...)` stubs satisfying Settings (per `09-01-SUMMARY.md`). |
| `packages/api-client/src/fetcher.ts` | `packages/api-client/src/errors.ts` | `import { ApiError } from './errors'` | WIRED | `09-02-SUMMARY.md`: fetcher imports and throws `ApiError` for all error paths (`client_error`, `session_expired`, `unknown_error`, plus typed server-side codes). |
| `apps/admin-web` workspace | `@sportzal/api-client` | `dependencies['@sportzal/api-client']: workspace:*` (pnpm workspace protocol) | WIRED | `09-UAT.md` Test 4: workspace dep verbatim; `pnpm -r typecheck` → all 3 workspace projects (`api-client + admin-web`) exit 0 (Test 3). |
| `.github/workflows/ci.yml` backend job | `apps/backend/openapi.json` | Export step + `git ls-files --error-unmatch` + `git diff --exit-code` | WIRED | `.github/workflows/ci.yml:51` (export invocation), `:63-64` (drift gate). UAT Test 5 confirms gate fires on local edit. |
| `.github/workflows/ci.yml` frontend job | `packages/api-client/src/schema.d.ts` | Codegen step + `git ls-files --error-unmatch` + `git diff --exit-code` | WIRED | `.github/workflows/ci.yml:113-114`. UAT Test 5 confirms gate fires on local edit. |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Export determinism | `uv run python -m scripts.export_openapi` × 2 + `diff -q /tmp/openapi.run1.json openapi.json` | Both runs wrote 37266 bytes; `diff -q` silent (UAT Test 2) | PASS |
| Workspace typecheck | `pnpm -r typecheck` | exit 0 across all 3 workspace projects (api-client + admin-web) (UAT Test 3) | PASS |
| Codegen idempotence | `pnpm --filter @sportzal/api-client codegen` | byte-equal output to committed `schema.d.ts` (UAT Test 4) | PASS |
| Backend drift gate | `git diff --exit-code apps/backend/openapi.json` after `sed` edit | exit 1 (drift detected) (UAT Test 5) | PASS |
| Frontend drift gate | `git diff --exit-code packages/api-client/src/schema.d.ts` after schema edit | exit 1 (drift detected) (UAT Test 5) | PASS |
| CR-01 path-param interpolation | vitest smoke (`packages/api-client/src/__uat__/fetcher.uat.test.ts`) | 3/3 behaviors confirmed: substitutes `{client_id}`, throws `ApiError('client_error')` on missing param, unchanged when no placeholders (UAT Test 6) | PASS |
| CR-02 single-flight refresh | vitest smoke same file | `refreshCalls === 1` after 3 concurrent 401-bound `request()` calls all settled `fulfilled` (UAT Test 7) | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| API-01 | 09-01 | Lifespan-safe export script writes byte-stable `apps/backend/openapi.json` (`indent=2, sort_keys=True`) without Postgres/Redis | SATISFIED | `09-UAT.md` Test 2 (two consecutive 37266-byte runs, `diff -q` silent, trailing newline, `version: "1.1.0"` exactly once); `09-01-SUMMARY.md` (lifespan-safe CLI implementation with env stubs). |
| API-02 | 09-03 | CI drift gate on backend `openapi.json` (`git diff --exit-code` + `git ls-files --error-unmatch` belt) | SATISFIED | `09-UAT.md` Test 5 (local drift simulation exits 1); `.github/workflows/ci.yml:51` (export), `:63-64` (drift gate); `09-REVIEW-FIX.md` WR-06 fix (commit 2d364f0) closes silent-pass loophole. |
| API-05 | 09-02 | `packages/api-client` real package with `openapi-typescript` codegen producing committed `src/schema.d.ts` | SATISFIED | `09-UAT.md` Test 3 (`pnpm -r typecheck` exit 0), Test 4 (predev hook + 3-way codegen verification), Test 8 (REQUIREMENTS.md API-05 wording aligned to D-07 committed-spec reality at line 91); `09-02-SUMMARY.md` (package layout, scripts, devDep). |
| API-06 | 09-02 | `request<P,M>(method, path, init)` typed wrapper with `credentials: 'include'`, X-CSRF-Token, single-flight `/auth/refresh`, retry-once, typed `ApiError { code, message, fields? }` | SATISFIED | `09-UAT.md` Test 6 (CR-01 path-param interpolation, 3/3 behaviors), Test 7 (CR-02 single-flight under 401 storm); `09-REVIEW-FIX.md` CR-01 (commit 659e9da), CR-02 (commit de2ba3a), WR-01 cause propagation (commit 18cab7f), WR-02 HeadersInit (commit 5a49974), WR-03 body-type branching (commit eef3155), WR-04 empty-JSON 200 handling (commit 608696d). |
| API-07 | 09-03 | CI drift gate on `packages/api-client/src/schema.d.ts` | SATISFIED | `09-UAT.md` Test 5 (frontend drift gate exits 1 on local edit); `.github/workflows/ci.yml:113-114`; `09-REVIEW-FIX.md` WR-06 fix applies the `git ls-files --error-unmatch` belt to the schema as well as openapi.json. |

**Orphan check:** Phase 9 plan frontmatters declare exactly API-01, API-02, API-05, API-06, API-07. All 5 IDs accounted for above. No orphans.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `apps/backend/.env.example` / `app/core/config.py` | (missing) | Backend boot via `uvicorn app.main:create_app --factory --reload` aborts with `ValidationError: telegram_bot_token / telegram_bot_username Field required` when developer's `.env` does not include those fields | INFO | Out-of-scope (pre-existing project hygiene gap exposed by Phase 9 smoke test, NOT a Phase 9 regression). Backend boot via uvicorn fails without `TELEGRAM_BOT_TOKEN` / `TELEGRAM_BOT_USERNAME` env vars; the export CLI works around this with `os.environ.setdefault(...)` per `09-01-SUMMARY.md`. Tracked as Phase 13 deliverable per ROADMAP Phase 13 SC #4. (`09-UAT.md` Gap 1.) |
| `packages/api-client` | (missing) | No permanent regression test for fetcher CR-01 / CR-02 fixes — verified via throwaway vitest smoke run through admin-web's vitest install, then deleted | INFO | The CR-01 path-param interpolation and CR-02 single-flight refresh fixes were verified architecturally and behaviorally in `09-UAT.md` Tests 6 + 7, but no permanent test runner is configured on `packages/api-client`. Tracked as Phase 13 deliverable per ROADMAP Phase 13 SC #5. (`09-UAT.md` Gap 2.) |

No BLOCKER or WARNING anti-patterns found. The two INFO-class items above are advisory follow-ups already scheduled into Phase 13 (v1.1 Minor Drift & Hygiene Cleanup).

### Human Verification Required

None outstanding. All goal-blocking behaviors are covered by the existing UAT (8 tests, 7 passed + 1 out-of-scope) and the REVIEW-FIX iteration (8/8 findings closed). The two advisory follow-ups from `09-UAT.md` Gaps 1 + 2 are scheduled into Phase 13 (v1.1 Minor Drift & Hygiene Cleanup).

### Gaps Summary

No gaps. All 4 ROADMAP success criteria are observably satisfied; all 5 declared requirement IDs (API-01, API-02, API-05, API-06, API-07) map to verified artifacts and behaviour; `09-REVIEW-FIX.md` closed 8/8 critical+warning findings (CR-01, CR-02, WR-01..WR-06). Two INFO-class follow-ups (Telegram env safe-defaults, permanent fetcher regression tests) are scheduled into Phase 13 per ROADMAP.

---

_Verified: 2026-05-04_
_Verifier: Claude (gsd-verifier)_
_Source: aggregated from 09-UAT.md (2026-05-03) + 09-REVIEW-FIX.md (2026-05-03) + 09-0{1,2,3}-SUMMARY.md_
