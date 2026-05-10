---
phase: 28
plan: "01"
subsystem: openapi-drift-gate
tags: [openapi, drift-gate, codegen, memberships]
dependency_graph:
  requires: []
  provides:
    - apps/backend/openapi.json (post-Phase-25/26/27 surface)
    - packages/api-client/src/schema.d.ts (typed FE surface for freeze/unfreeze/renew)
  affects:
    - packages/api-client (consumed by all admin-web plans 28-02 through 28-08)
tech_stack:
  added: []
  patterns:
    - byte-stable openapi export (indent=2, sort_keys=True, ensure_ascii=False, trailing newline)
    - openapi-typescript v7 codegen (string literal unions, not uppercased enum names)
key_files:
  created: []
  modified:
    - apps/backend/openapi.json
    - packages/api-client/src/schema.d.ts
decisions:
  - "D-28-01 honored: single atomic commit for both drift artifacts; subsequent plans MUST NOT regenerate"
  - "openapi-typescript v7 emits lowercase string literals ('frozen' not 'FROZEN') — plan acceptance criterion was based on outdated assumption; actual output is correct"
metrics:
  duration: ~5 minutes
  completed: "2026-05-10T12:02:11Z"
  tasks_completed: 3
  files_modified: 2
---

# Phase 28 Plan 01: OpenAPI Drift-Gate Refresh Summary

Single, atomic regenerate-then-commit cycle closing Phase 25/26/27 backend drift: FROZEN status enum, freeze/unfreeze/renew endpoints, FreezePeriodResponse schema, and all freeze/renewal projection fields in MembershipResponse.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Regenerate apps/backend/openapi.json | 525b8d2 | apps/backend/openapi.json |
| 2 | Regenerate packages/api-client/src/schema.d.ts | 525b8d2 | packages/api-client/src/schema.d.ts |
| 3 | Atomic commit of both regenerated artifacts | 525b8d2 | both (one commit) |

## Verification Results

All acceptance criteria verified:

**openapi.json:**
- `"frozen"` enum value present in MembershipStatus
- `/api/v1/memberships/{membership_id}/freeze` path present (POST 200)
- `/api/v1/memberships/{membership_id}/unfreeze` path present (POST 200)
- `/api/v1/memberships/{membership_id}/renew` path present (POST 201)
- `freezeDaysRemaining`, `freezeDaysLimitSnapshot`, `currentFreezePeriod`, `previousMembershipId` fields present in MembershipResponse
- Byte-stable: MD5 `0b364e66966b6c6253db0a11ff762299` identical across multiple runs

**schema.d.ts:**
- `"frozen"` string literal in MembershipStatus union type
- All three new paths present in the `paths` interface
- `freezeDaysRemaining`, `currentFreezePeriod`, `previousMembershipId` present in MembershipResponse component
- Byte-stable: MD5 `4f694f37581a43dbffaa4a34a3c68053` identical across multiple runs
- `pnpm --filter @sportzal/api-client typecheck` exits 0

**Drift-gate post-commit:**
- `git diff --exit-code -- apps/backend/openapi.json` exits 0 after re-run
- `git diff --exit-code -- packages/api-client/src/schema.d.ts` exits 0 after re-codegen
- Commit contains exactly 2 files, no others

## Deviations from Plan

### Notes (not deviations — expected behavior)

**openapi-typescript v7 enum representation**
- **Found during:** Task 2
- **Issue:** Plan acceptance criterion said `grep -q 'FROZEN'` (uppercase), but openapi-typescript v7 emits string literal unions using the actual JSON schema values (`"active" | "expired" | "cancelled" | "frozen"` — all lowercase), not uppercased identifiers.
- **Fix:** No fix needed — the correct value `"frozen"` is present as a lowercase string literal on line 1069 of schema.d.ts. This is the correct openapi-typescript v7 behavior. The plan's acceptance check was based on an older version's behavior.
- **Impact:** None. Consuming code in plans 28-02 onward will use `'frozen'` (lowercase) for the frozen status, which matches the actual TypeScript union type.

None - plan executed exactly as designed. Three tasks completed in one atomic commit.

## Threat Surface Scan

No new network endpoints, auth paths, or trust boundaries introduced. This plan only regenerates generated artifacts from the existing FastAPI app surface. The threat mitigations T-28-01-01 and T-28-01-02 are satisfied: both files are now generated and committed, with `git diff --exit-code` CI gates confirmed green.

## Known Stubs

None. Both files are fully generated artifacts with no placeholder content.

## Self-Check: PASSED

- `apps/backend/openapi.json` modified: FOUND (508 net insertions in commit 525b8d2)
- `packages/api-client/src/schema.d.ts` modified: FOUND (in same commit)
- Commit 525b8d2 exists: CONFIRMED (`git log -1` shows it as HEAD)
- Drift-gate clean: CONFIRMED (`git status` shows clean working tree)
- Exactly 2 files in commit: CONFIRMED (grep count = 0 for unexpected files)
