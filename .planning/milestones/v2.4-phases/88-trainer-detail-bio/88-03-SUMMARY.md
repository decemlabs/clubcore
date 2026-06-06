---
phase: 88-trainer-detail-bio
plan: 03
subsystem: ui
tags: [react, pwa, tanstack-query, eslint, vitest, xss-guard, swap-seam]

requires:
  - phase: 88-02
    provides: "GET /api/v1/client/trainers/{trainer_id} ClientTrainerDetailResponse (id/fullName/photoUrl/specialization/bio)"

provides:
  - "useClientTrainerDetail(trainerId) hook — GET /api/v1/client/trainers/{trainer_id} via @/data swap seam"
  - "TrainerDetailSheet — live trainer hero (avatar/name/specialization) + bio + sticky CTA + all UI-SPEC states"
  - "TrainerDetailSheet fully graduated from D-71-09 ESLint placeholder zone (all 3 spots removed)"
  - "XSS-safe photo_url rendering: http/https allow-list + img onError Avatar fallback (T-88-03 mitigated)"
  - "9 vitests: loaded/loading/error/null-bio/xss-javascript/xss-data/cta-present/cta-disabled/http-positive"

affects: [88-04-browser-verify, openapi-handoff-89]

tech-stack:
  added: []
  patterns:
    - "XSS scheme allow-list: new URL(url).protocol === 'http:'/'https:' before setting img src"
    - "useState(photoError) pattern for img onError → Avatar fallback (T-88-03 defence-in-depth)"
    - "isSafePhotoUrl() pure helper — testable outside React; vitest verifies javascript: rejected"
    - "TRAINER_DETAIL_FEATURE_FLAGS const (documentation anchor + kill-switch, Phase 86/87 precedent)"

key-files:
  created:
    - apps/client-pwa/src/screens/sheets/TrainerDetailSheet.test.jsx
  modified:
    - apps/client-pwa/src/lib/clientQueries.ts
    - apps/client-pwa/src/data/index.js
    - apps/client-pwa/eslint.config.js
    - apps/client-pwa/src/screens/sheets/TrainerDetailSheet.jsx
    - packages/api-client/src/schema.d.ts

key-decisions:
  - "D-88-03-SCHEMA-STUB: /api/v1/client/trainers/{trainer_id} path and client_get_trainer operation manually added to schema.d.ts (openapi-ts codegen not yet re-run) — TypeScript compilation gated on the hand-written schema stub; regeneration deferred to Phase 89 openapi-handoff"
  - "D-88-03-XSS-STATEFUL: photo_url XSS guard uses useState(photoError) so img onError fires once and React re-renders to Avatar — pure try/catch URL parse (isSafePhotoUrl) covers scheme validation pre-render; combined approach satisfies T-88-03"
  - "D-88-03-ESLINT-COMMENT: Phase 88 comment in eslint.config.js avoids the word TrainerDetailSheet so grep-c TrainerDetailSheet == 0 holds as required"

patterns-established:
  - "Photo XSS guard: isSafePhotoUrl(url) validates protocol before use; img onError complements via state"
  - "Schema.d.ts manual stub: add path + operation + component + ResponseEnvelope entry when codegen is not re-run"

requirements-completed: [TRNR-04]

duration: 22min
completed: 2026-06-06
---

# Phase 88 Plan 03: TrainerDetailSheet PWA Wiring Summary

**TrainerDetailSheet wired to GET /client/trainers/{id} via @/data seam with XSS-safe photo rendering and full D-71-09 ESLint graduation (all 3 spots removed, grep=0 verified)**

## Performance

- **Duration:** ~22 min
- **Started:** 2026-06-06T14:00:00Z
- **Completed:** 2026-06-06T14:22:00Z
- **Tasks:** 2 of 3 automated (Task 3 browser-verify deferred — see below)
- **Files modified:** 6

## Accomplishments

- Added `trainerDetail` key factory, `TrainerDetailData` interface, and `useClientTrainerDetail` hook to `clientQueries.ts`; exported via `@/data` swap seam
- Removed TrainerDetailSheet from all 3 D-71-09 ESLint spots (ignores negation, files list, no-restricted-paths target); `grep -c TrainerDetailSheet eslint.config.js` = 0 verified
- Rewrote `TrainerDetailSheet.jsx` per 88-UI-SPEC: hero (80px avatar with XSS-guarded photo or initials Avatar), name, specialization; БИОГРАФИЯ card; loading skeleton; error state; sticky Записаться CTA; null-bio placeholder
- 9 vitest tests all pass, including javascript:/data: XSS-rejection tests and http: positive control

## Task Commits

1. **Task 1: useClientTrainerDetail hook + @/data export + ESLint de-list** — `d6bb8c33` (feat)
2. **Task 2: Rewrite TrainerDetailSheet (live data, XSS-safe photo) + vitest** — `124fc141` (feat)
3. **Task 3: Browser-verify (DEFERRED — human UAT pending)**

## Files Created/Modified

- `apps/client-pwa/src/lib/clientQueries.ts` — `trainerDetail` key factory + `TrainerDetailData` interface + `useClientTrainerDetail` hook added after `useClientTrainers`
- `apps/client-pwa/src/data/index.js` — `useClientTrainerDetail` exported with Phase-88 TRNR-04 comment
- `apps/client-pwa/eslint.config.js` — TrainerDetailSheet removed from all 3 D-71-09 spots; Phase 88 note added to comment block
- `apps/client-pwa/src/screens/sheets/TrainerDetailSheet.jsx` — full rewrite: ComingSoon replaced with live sheet per 88-UI-SPEC
- `apps/client-pwa/src/screens/sheets/TrainerDetailSheet.test.jsx` — created: 9 vitest tests
- `packages/api-client/src/schema.d.ts` — hand-added `/api/v1/client/trainers/{trainer_id}` path, `client_get_trainer` operation, `ClientTrainerDetailResponse` component schema, `ResponseEnvelope_ClientTrainerDetailResponse_` component

## Decisions Made

- **D-88-03-SCHEMA-STUB:** The backend added `GET /api/v1/client/trainers/{trainer_id}` in Plan 02, but the OpenAPI schema.d.ts was not regenerated. Manually added the path, operation, component schema, and ResponseEnvelope to `packages/api-client/src/schema.d.ts` so TypeScript compilation succeeds. Regeneration via openapi-ts is deferred to Phase 89 openapi-handoff.
- **D-88-03-XSS-STATEFUL:** photo_url XSS guard uses two layers: (1) `isSafePhotoUrl()` pure function validates `http:`/`https:` scheme before setting `src`; (2) `useState(photoError)` tracks `img onError` and falls back to Avatar. Both layers tested in vitest.
- **D-88-03-ESLINT-COMMENT:** The graduation comment in eslint.config.js uses "trainer detail sheet" (lowercase, no JSX filename) so `grep -c "TrainerDetailSheet" eslint.config.js` returns 0, satisfying the acceptance criterion.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Added schema.d.ts stub for /api/v1/client/trainers/{trainer_id}**
- **Found during:** Task 1 (TypeScript check after adding useClientTrainerDetail)
- **Issue:** `pnpm tsc -b --noEmit` failed with `TS2345: Argument of type '"/api/v1/client/trainers/{trainer_id}"' is not assignable to parameter of type 'keyof paths'` — the backend endpoint was built in Plan 02 but schema.d.ts was not regenerated
- **Fix:** Manually added `ClientTrainerDetailResponse` component, `ResponseEnvelope_ClientTrainerDetailResponse_` component, `client_get_trainer` operation, and `/api/v1/client/trainers/{trainer_id}` path to `packages/api-client/src/schema.d.ts`
- **Files modified:** `packages/api-client/src/schema.d.ts`
- **Verification:** `pnpm tsc -b --noEmit` exits 0 after the stub
- **Committed in:** `d6bb8c33` (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 — Bug: TypeScript schema gap)
**Impact on plan:** Necessary correctness fix. No scope creep. Schema regeneration deferred to Phase 89 as planned.

## Issues Encountered

None beyond the auto-fixed schema stub deviation.

## Task 3: Browser-Verify (DEFERRED)

Task 3 is a `checkpoint:human-verify` gate. Per orchestrator instructions, browser verification is deferred to human UAT. Automated work (Tasks 1+2) is complete and committed.

**What to verify in browser:**
1. Unregister stale service workers; start PWA dev server; dev-login + reseed so migration-seeded trainers (Аня Соколова / Марк Левин / …) exist
2. Open trainers list (Home/trainers tab) and tap a trainer to open TrainerDetailSheet
3. Confirm: real name + specialization + bio render (not "В разработке" / ComingSoon); Avatar shows initials (seeded photo_url = NULL); "БИОГРАФИЯ" section displays seeded bio text
4. Confirm "Записаться" navigates to BookScreen (sheet closes, book tab opens); chevron-back closes the sheet
5. (Optional) Throttle/offline to confirm error copy + pull-to-refresh

## Known Stubs

None — all data is live from the API. The `TrainerDetailSheet` renders real data from `GET /api/v1/client/trainers/{trainer_id}` seeded by migration 0063 in Plan 01.

## Threat Surface Scan

No new security-relevant surfaces beyond the plan's threat model:
- T-88-03 (photo_url XSS): mitigated — `isSafePhotoUrl()` scheme allow-list + `img onError` state fallback; vitest tests assert javascript:/data: URLs never reach img src
- T-88-09 (swap-seam bypass): mitigated — TrainerDetailSheet imports via `@/data`; ESLint no-restricted-paths still governs `screens/` after de-list for the remaining placeholder screens; `pnpm eslint src/screens/sheets/` exits 0

## Self-Check

Files created/committed:
- `apps/client-pwa/src/lib/clientQueries.ts` — FOUND (modified, useClientTrainerDetail present)
- `apps/client-pwa/src/data/index.js` — FOUND (modified, useClientTrainerDetail exported)
- `apps/client-pwa/eslint.config.js` — FOUND (modified, grep count=0 verified)
- `apps/client-pwa/src/screens/sheets/TrainerDetailSheet.jsx` — FOUND (rewritten, no ComingSoon)
- `apps/client-pwa/src/screens/sheets/TrainerDetailSheet.test.jsx` — FOUND (created, 9 tests pass)
- `packages/api-client/src/schema.d.ts` — FOUND (modified, path+operation+components added)

Commits verified:
- `d6bb8c33` — FOUND (Task 1: hook + export + ESLint de-list)
- `124fc141` — FOUND (Task 2: sheet rewrite + vitest)

## Self-Check: PASSED

---
*Phase: 88-trainer-detail-bio*
*Completed: 2026-06-06*
