---
phase: 117-openapi-handoff-milestone-gate
plan: "01"
subsystem: api-contract
tags: [openapi, codegen, contract-guard, cast-removal, v3.2]
dependency_graph:
  requires: []
  provides:
    - apps/backend/openapi.json (regenerated v3.2 additive)
    - packages/api-client/src/schema.d.ts (regenerated from v3.2 openapi.json)
    - packages/api-client/src/schema.contract.test.ts (_v32Checks forward-guard)
  affects:
    - apps/admin-app/src/features/promoCodes/api.ts (cast-free typed paths)
    - apps/admin-app/src/features/messages/api.ts (cast-free typed paths)
tech_stack:
  added: []
  patterns:
    - openapi-typescript codegen (additive regen)
    - AssertNonNever tuple forward-guard
    - typed staffRequest path strings (no casts)
key_files:
  created: []
  modified:
    - apps/backend/openapi.json
    - packages/api-client/src/schema.d.ts
    - packages/api-client/src/schema.contract.test.ts
    - apps/admin-app/src/features/promoCodes/api.ts
    - apps/admin-app/src/features/messages/api.ts
decisions:
  - _v32Checks tuple has 22 entries (15 path×methods + 5 requestBody probes + 2 responses['200'] anchors) to satisfy noUnusedLocals; toHaveLength(22) reflects the actual count
  - messages/api.ts template-literal paths replaced with typed path strings + params: { thread_id } to match the openapi-typescript path key format
  - promoCodes/api.ts unused 'import type { paths }' removed along with casts
metrics:
  duration_seconds: 346
  completed_date: "2026-06-15"
  tasks_completed: 3
  files_modified: 5
---

# Phase 117 Plan 01: OpenAPI Contract Regen + _v32Checks Guard + Cast Removal Summary

**One-liner:** Additive OpenAPI regen for 15 new v3.2 routes via uv export_openapi + openapi-typescript codegen, extended schema.contract.test.ts with a 22-entry _v32Checks AssertNonNever tuple (15 path×methods + probes), and removed `as unknown as keyof paths` / `as never` casts from promoCodes/api.ts and messages/api.ts.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Regenerate openapi.json + schema.d.ts additively | da431b89 | apps/backend/openapi.json, packages/api-client/src/schema.d.ts |
| 2 | Add _v32Checks forward-guard tuple | 290d3284 | packages/api-client/src/schema.contract.test.ts |
| 3 | Remove temporary path casts | 17d6da97 | apps/admin-app/src/features/promoCodes/api.ts, apps/admin-app/src/features/messages/api.ts |

## Key Results

### Task 1: Regen
- `uv run python -m scripts.export_openapi` produced 562724 bytes (ADDITIVE — new v3.2 paths added)
- `pnpm -F @clubcore/api-client codegen` (openapi-typescript 7.13.0) regenerated schema.d.ts
- All 15 new v3.2 path×methods confirmed present in both openapi.json and schema.d.ts:
  1. POST /api/v1/payments/{payment_id}/refund
  2. PATCH /api/v1/users/{user_id}/role
  3. GET /api/v1/promo-codes
  4. POST /api/v1/promo-codes
  5. PATCH /api/v1/promo-codes/{promo_id}
  6. PATCH /api/v1/promo-codes/{promo_id}/deactivate
  7. GET /api/v1/reports/cohort
  8. GET /api/v1/reports/anomaly
  9. GET /api/v1/reports/at-risk
  10. GET /api/v1/reports/load/now
  11. GET /api/v1/messages/threads
  12. GET /api/v1/messages/threads/{thread_id}
  13. POST /api/v1/messages/threads/{thread_id}/reply
  14. POST /api/v1/messages/threads/{thread_id}/read
  15. GET /api/v1/reports/payments.csv
- No manual stub residue (`// stub` / `// Phase 117`) in generated schema.d.ts
- Codegen deterministic: second run produced zero diff

### Task 2: _v32Checks Tuple
- 22 total entries in the tuple (all resolving to true at compile time):
  - 15 path×method AssertNonNever aliases (one per v3.2 path)
  - 5 requestBody probes (refund POST, role PATCH, promo-create POST, promo-patch PATCH, messages-reply POST)
  - 2 responses['200'] anchors (promo-codes GET list, messages/threads GET list)
  - 1 CSV responses['200'] anchor (payments.csv, per _ReportsRevenueCsvGet pattern)
- payments.csv guarded via responses['200'] per existing CSV-endpoint anchor style (no JSON body)
- api-client typecheck clean; vitest 23 tests passed (15 test blocks)

### Task 3: Cast Removal
- promoCodes/api.ts: 4 `as unknown as keyof paths` casts removed (GET+POST promo-codes, PATCH promo_id, PATCH deactivate); NOTE comment block removed; unused `import type { paths }` removed
- messages/api.ts: 4 `as never` casts removed; template literals replaced with typed path strings + `params: { thread_id }` to match openapi-typescript key format
- admin-app typecheck clean after removal

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing critical functionality] _v32Checks toHaveLength uses 22 not 15**
- **Found during:** Task 2
- **Issue:** TypeScript noUnusedLocals requires all declared type aliases to be used. Declaring body probes and response anchors as separate type aliases (not in the tuple) caused TS6196 errors.
- **Fix:** Included all 22 aliases in the _v32Checks tuple. toHaveLength(22) reflects the actual count of aliases (15 path×methods + 7 probes). The plan_checker_correction's "toHaveLength(15)" referred to the minimum path count correction (14→15), not the final tuple length.
- **Files modified:** packages/api-client/src/schema.contract.test.ts
- **Commit:** 290d3284

**2. [Rule 2 - Missing critical functionality] messages/api.ts template literals replaced with typed path strings + params**
- **Found during:** Task 3
- **Issue:** Template literals like `/api/v1/messages/threads/${threadId}` cannot be typed as `keyof paths` because TypeScript cannot reduce the template to a specific literal type at compile time. The openapi-typescript path format uses `{thread_id}` placeholders.
- **Fix:** Replaced template literals with typed path strings using params: `{ thread_id: threadId }` — consistent with how payments/api.ts and users/api.ts handle parameterized paths.
- **Files modified:** apps/admin-app/src/features/messages/api.ts
- **Commit:** 17d6da97

## Verification Results

- `apps/backend/openapi.json` — 15 new v3.2 path×methods present (grep gate passed)
- `packages/api-client/src/schema.d.ts` — 15 new v3.2 path×methods present (grep gate passed)
- `pnpm -F @clubcore/api-client typecheck` — PASSED
- `pnpm -F @clubcore/api-client test` — PASSED (23 tests)
- `pnpm -F @clubcore/admin-app typecheck` — PASSED
- No `as unknown as keyof paths` in promoCodes/api.ts — CONFIRMED
- No `as never` in messages/api.ts — CONFIRMED
- Codegen deterministic (second run zero diff) — CONFIRMED

## Known Stubs

None. All paths are real (backend-generated), all type aliases resolve to non-never.

## Threat Flags

None. Regen used `create_app().openapi()` which honors `include_in_schema`; no `_internal` or debug routes appeared in the diff.

## Self-Check: PASSED

- apps/backend/openapi.json: FOUND
- packages/api-client/src/schema.d.ts: FOUND
- packages/api-client/src/schema.contract.test.ts: FOUND (contains _v32Checks)
- Commits da431b89, 290d3284, 17d6da97: FOUND
