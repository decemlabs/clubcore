---
phase: 57-openapi-handoff-milestone-verification
plan: "01"
subsystem: api-contract
tags: [openapi, codegen, contract-test, v1.8, reports, audit-log]
dependency_graph:
  requires:
    - "Phase 55-56: reports + audit-log modules (8 v1.8 paths landed)"
  provides:
    - "apps/backend/openapi.json (byte-stable, includes v1.8 surface)"
    - "packages/api-client/src/schema.d.ts (regenerated from v1.8 openapi.json)"
    - "packages/api-client/src/schema.contract.test.ts (_v18Checks block + runtime count)"
  affects:
    - "packages/api-client consumers (schema.d.ts now typed for v1.8)"
    - "CI drift gates (backend openapi.json + frontend schema.d.ts) — both green"
tech_stack:
  added: []
  patterns:
    - "Byte-stable artifact regen (sort_keys=True) — existing pattern"
    - "AssertNonNever forward guards — existing contract-test pattern"
    - "2xx-reachability anchor for CSV GETs — mirrors _v15Checks _TrainerSlotsListOkRealised"
key_files:
  created: []
  modified:
    - apps/backend/openapi.json
    - packages/api-client/src/schema.d.ts
    - packages/api-client/src/schema.contract.test.ts
decisions:
  - "Used AssertNonNever<paths[...]['get']> for 4 JSON GET endpoints (hard guard, paths are landed)"
  - "Used AssertNonNever<paths[...]['get']['responses']['200']> for 4 CSV GETs (2xx-reachability anchor per D-v15 pattern)"
  - "No edits to export_openapi.py or package.json codegen script (D-01, D-02 preserved)"
metrics:
  duration: "4 minutes"
  completed: "2026-05-24"
  tasks_completed: 3
  tasks_total: 3
  files_modified: 3
---

# Phase 57 Plan 01: OpenAPI Handoff — v1.8 Regen + Contract Guards Summary

**One-liner:** Byte-stable regen of openapi.json + schema.d.ts adding all 8 v1.8 reports/audit paths, then 8 AssertNonNever compile-time guards + runtime toHaveLength(8) assertion in schema.contract.test.ts.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Regenerate openapi.json byte-stably | 2eb24c7 | apps/backend/openapi.json |
| 2 | Regenerate schema.d.ts from new openapi.json | 394e745 | packages/api-client/src/schema.d.ts |
| 3 | Add _v18Checks forward guards + count assertion | 45e9236 | packages/api-client/src/schema.contract.test.ts |

## What Was Done

**Task 1:** Ran `uv run python -m scripts.export_openapi` from `apps/backend/` unchanged.
The exporter called `create_app().openapi()` (no lifespan, no DB/Redis). The artifact
predated the reports module (May 20 vs May 24), so regen produced a real diff adding all 8
v1.8 paths (1864 insertions, 390 deletions). Final file: 285987 bytes. Byte-stable on
second run — `git diff --exit-code` exits 0.

**Task 2:** Ran `pnpm --filter @sportzal/api-client codegen` unchanged, which invoked
`openapi-typescript ../../apps/backend/openapi.json --output src/schema.d.ts`. All 8 v1.8
paths appear in the `paths` interface. Byte-stable on second run.

**Task 3:** Added to `packages/api-client/src/schema.contract.test.ts` (additive only):
- 8 type aliases: `_ReportsRevenueGet`, `_ReportsClientsGet`, `_ReportsVisitsGet`,
  `_AuditLogGet` (hard AssertNonNever on GET operation) + `_ReportsRevenueCsvGet`,
  `_ReportsClientsCsvGet`, `_ReportsVisitsCsvGet`, `_AuditLogCsvGet` (2xx-reachability
  anchor via `['get']['responses']['200']` per _v15Checks pattern)
- `const _v18Checks: [8 aliases] = [true, true, true, true, true, true, true, true]`
- New `it('compiles against the regenerated v1.8 reports/audit surface (Phases 55-57)', ...)`
  with `expect(_v18Checks).toHaveLength(8)`
- All existing frozen count blocks (10/36/11/5/4/2) are byte-unchanged

Tests pass: `pnpm --filter @sportzal/api-client test` → 15 passed (7 in schema.contract.test.ts).

## Verification Results

- All 8 v1.8 path strings present in both `apps/backend/openapi.json` and `packages/api-client/src/schema.d.ts`
- `git diff --exit-code apps/backend/openapi.json` exits 0 after regen (byte-stable)
- `git diff --exit-code packages/api-client/src/schema.d.ts` exits 0 after codegen (byte-stable)
- `pnpm --filter @sportzal/api-client test` exits 0 (15/15 passed)
- `export_openapi.py` unmodified; `package.json` codegen script unmodified

## Deviations from Plan

None — plan executed exactly as written. Load-bearing wave ordering (Task 1 → Task 2 → Task 3) was followed strictly. The expected large diff on openapi.json and schema.d.ts was verified against D-03 (verify presence, do not assume no diff).

## Threat Surface Scan

No new network endpoints, auth paths, file access patterns, or schema changes introduced.
The regenerated artifacts expose only path shapes already present in the FastAPI router
(authenticated routes). T-57-01 (information disclosure) and T-57-02 (tampering via drift
gate) are both in the plan's threat model and addressed: CI drift gate gates are green.

## Known Stubs

None — regenerated artifacts are complete; contract test guards are wired to real paths.

## Self-Check

- [x] `apps/backend/openapi.json` modified and committed (2eb24c7)
- [x] `packages/api-client/src/schema.d.ts` modified and committed (394e745)
- [x] `packages/api-client/src/schema.contract.test.ts` modified and committed (45e9236)
- [x] All 8 v1.8 paths verified present in both artifacts
- [x] Tests pass: 15/15
- [x] Both artifacts byte-stable (drift gates exit 0)
