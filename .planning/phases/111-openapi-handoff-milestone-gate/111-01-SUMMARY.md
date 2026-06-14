---
phase: 111-openapi-handoff-milestone-gate
plan: "01"
subsystem: api
tags: [openapi, openapi-typescript, schema, contract, typescript, vitest]

# Dependency graph
requires:
  - phase: 109-profile-and-security
    provides: PATCH /auth/me and POST /auth/change-password backend routes
  - phase: 108-editable-settings
    provides: GET+PUT /settings/hours, /settings/booking, /settings/notifications backend routes
  - phase: 107-admin-fe-completion
    provides: GET /api/v1/gym staff route (CFG-01 read)
provides:
  - Regenerated apps/backend/openapi.json with all 6 new v3.1 paths (additive, byte-stable baseline)
  - Regenerated packages/api-client/src/schema.d.ts typed paths for all new routes
  - _v31Checks AssertNonNever forward-guard (14 entries) in schema.contract.test.ts
  - Zero-diff baseline for Plan 02 drift gates
affects:
  - 111-02-GATE-EVIDENCE (drift gates use the committed artifacts as baseline)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "_vNNChecks AssertNonNever tuple pattern extended with v3.1 block (14 entries)"
    - "Additive openapi.json regen (not byte-stable no-op like Phase 106)"

key-files:
  created: []
  modified:
    - apps/backend/openapi.json
    - packages/api-client/src/schema.d.ts
    - packages/api-client/src/schema.contract.test.ts

key-decisions:
  - "D-111-01-ADDITIVE: openapi.json regen is additive (not byte-stable no-op) per D-V31-CONTRACT-ADDITIVE; +788 insertions / -6 deletions (description text reformatting + minor schema reorg); no auth/CSRF/RBAC metadata removed"
  - "D-111-02-14-ENTRIES: _v31Checks tuple has 14 entries covering 9 path×method combos + 5 JSON requestBody carriers; PUT /api/v1/gym was already in _v24Checks, so only GET /api/v1/gym is new here"

patterns-established:
  - "Forward-guard after commit: re-export + re-codegen both produce zero diff against committed baseline (drift gates pass)"

requirements-completed: [HND-01]

# Metrics
duration: 4min
completed: "2026-06-14"
---

# Phase 111 Plan 01: Regenerate v3.1 OpenAPI Contract + _v31Checks Guard Summary

**Additive openapi.json regen (+788 insertions) for 6 new v3.1 staff routes, regenerated schema.d.ts, and 14-entry _v31Checks AssertNonNever forward-guard — all committed as the new byte-stable baseline**

## Performance

- **Duration:** 4 min
- **Started:** 2026-06-14T20:57:25Z
- **Completed:** 2026-06-14T21:01:08Z
- **Tasks:** 2 (combined into 1 commit)
- **Files modified:** 3

## Accomplishments

- Regenerated apps/backend/openapi.json with all 6 new v3.1 paths: PATCH /auth/me, POST /auth/change-password, GET /api/v1/gym, GET+PUT /settings/hours, GET+PUT /settings/booking, GET+PUT /settings/notifications (additive diff: +788/-6)
- Regenerated packages/api-client/src/schema.d.ts from the new contract via openapi-typescript v7 (+579/-3); all new typed path entries verified present
- Added _v31Checks block (14 AssertNonNever entries) after _v26Checks in schema.contract.test.ts; runtime toHaveLength(14) assertion passes; api-client test 22/22 + typecheck clean
- Post-commit drift gates both green: re-export → zero diff on openapi.json; re-codegen → zero diff on schema.d.ts

## Task Commits

Each task was committed atomically:

1. **Task 1+2: Regen openapi.json + schema.d.ts + _v31Checks guard** - `662b623d` (docs)

## Files Created/Modified

- `apps/backend/openapi.json` - Regenerated v3.1 staff contract; 6 new paths added (additive only; no auth/CSRF/RBAC metadata removed)
- `packages/api-client/src/schema.d.ts` - Regenerated openapi-typescript v7 output from new contract; new typed path entries for all v3.1 routes
- `packages/api-client/src/schema.contract.test.ts` - Added _v31Checks (14 entries: 9 path×method + 5 requestBody carriers) + runtime `expect(_v31Checks).toHaveLength(14)` inside describe block

## Decisions Made

- **D-111-01-ADDITIVE:** openapi.json regen is additive per D-V31-CONTRACT-ADDITIVE. The -6 deletions are non-security text reformatting in description strings and minor schema component reorg; zero auth/CSRF/RBAC metadata removed (confirmed by grep).
- **D-111-02-14-ENTRIES:** _v31Checks has 14 entries. GET /api/v1/gym is new (staff owner read, CFG-01); PUT /api/v1/gym was already in _v24Checks. All body-carrying PUT/PATCH routes get both a method check and a requestBody carrier entry.

## Deviations from Plan

None — plan executed exactly as written. Both tasks combined into a single commit as the plan instructed.

## Issues Encountered

None. The git diff --exit-code invocation from within the backend subdirectory returned an ambiguous argument error (no relative paths from subdirectory); resolved by running from repo root — no code change required.

## Known Stubs

None. Generated files (openapi.json, schema.d.ts) contain no stub data; the contract test _v31Checks tuple is fully wired to the regenerated schema.

## Threat Flags

None. Files describe API shape only (no secrets, env values, or credentials). Additive-only diff verified — no auth/CSRF/RBAC metadata dropped.

## Next Phase Readiness

- Plan 02 (Gate Evidence) drift gates are green: committed artifacts ARE the regenerated baseline; re-export + re-codegen both produce zero diff
- All 6 new v3.1 paths typed and forward-guarded at compile time
- api-client test (22/22) + typecheck clean

---
*Phase: 111-openapi-handoff-milestone-gate*
*Completed: 2026-06-14*
