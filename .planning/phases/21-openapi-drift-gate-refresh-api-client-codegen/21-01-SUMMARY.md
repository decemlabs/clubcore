---
phase: 21-openapi-drift-gate-refresh-api-client-codegen
plan: "01"
subsystem: api-client
tags:
  - openapi
  - codegen
  - api-client
  - drift-gate
  - typescript
dependency_graph:
  requires:
    - phases/16-membership-plans-catalog-backend (membership-plans routes)
    - phases/17-membership-instances-resolver-backend (memberships routes)
    - phases/19-visits-db-reception-check-in-backend (visits routes)
  provides:
    - packages/api-client/src/schema.d.ts (v1.2 typed paths surface)
    - packages/api-client/src/schema.contract.test.ts (forward-guard drift test)
  affects:
    - phases/22-admin-web-wiring (consumes typed paths for features/memberships, features/visits)
tech_stack:
  added: []
  patterns:
    - openapi-typescript v7 → TypeScript paths interface (byte-stable codegen)
    - AssertNonNever<T> conditional type helper for compile-time surface pinning
    - HasPath<P> conditional type helper for future-path conditional probe (D-21-2)
key_files:
  created:
    - packages/api-client/src/schema.contract.test.ts
  modified:
    - packages/api-client/src/schema.d.ts
    - .planning/PROJECT.md
    - .planning/REQUIREMENTS.md
decisions:
  - "D-21-1: Phase 21 shipped without sessions endpoints (Phase 23 not merged). openapi.json had 0-byte drift — already byte-stable from Phases 16/17/19 CI gates."
  - "D-21-2: Contract test uses HasPath<P> conditional probe so it stays green whether or not Phase 23 has merged."
  - "D-21-3: Auto-derived FastAPI operationIds retained (no explicit overrides)."
  - "D-21-4: schema.contract.test.ts forward-guard added as a single sibling vitest file."
metrics:
  duration_minutes: 4
  completed_date: "2026-05-08"
  tasks_completed: 4
  files_changed: 4
---

# Phase 21 Plan 01: OpenAPI drift gate refresh + api-client codegen Summary

Regenerated `packages/api-client/src/schema.d.ts` to the v1.2 surface (+896/-13 lines), added a type-level contract test as a forward-guard against codegen regressions, and reconciled docs. Phase 22 (admin-web wiring) can now consume typed `paths['/api/v1/membership-plans']`, `paths['/api/v1/memberships']`, and `paths['/api/v1/visits']` from `@sportzal/api-client`.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Verify byte-stability of `apps/backend/openapi.json` | (noop — 0-byte diff) | — |
| 2 | Regenerate `packages/api-client/src/schema.d.ts` | d3ab76d | `packages/api-client/src/schema.d.ts` |
| 3 | Add `schema.contract.test.ts` forward-guard | 88b4bfe | `packages/api-client/src/schema.contract.test.ts` |
| 4 | Update PROJECT.md (D-21) + REQUIREMENTS.md (API-04/API-05) | c8f39f9 | `.planning/PROJECT.md`, `.planning/REQUIREMENTS.md` |

## Byte Counts

```
git diff --stat 82b214911d2bdbdb5a101d8e53e8100ad3cad430 HEAD

 .planning/PROJECT.md                            |   1 +
 .planning/REQUIREMENTS.md                       |   8 +-
 packages/api-client/src/schema.contract.test.ts |  74 ++
 packages/api-client/src/schema.d.ts             | 909 +++++++++++++++++++++++-
 4 files changed, 975 insertions(+), 17 deletions(-)
```

## Task 1 Outcome (openapi.json)

**Default path (noop):** `cd apps/backend && uv run python -m scripts.export_openapi` produced a 0-byte diff against `HEAD`. The committed `apps/backend/openapi.json` was already byte-stable — Phases 16/17/19 each shipped their spec changes via the CI drift gate, so no defensive commit was required.

Confirmed v1.2 path keys present in spec:
- `/api/v1/membership-plans`
- `/api/v1/membership-plans/{plan_id}`
- `/api/v1/memberships`
- `/api/v1/memberships/{membership_id}`
- `/api/v1/memberships/{membership_id}/cancel`
- `/api/v1/visits`
- `/api/v1/visits/{visit_id}`

## Sessions Paths Status

Sessions paths (`/api/v1/auth/sessions`, `/api/v1/auth/sessions/{family_id}/revoke`) are **NOT** present in the regenerated `schema.d.ts`. Phase 23 has not merged. The `HasPath<P>` conditional probe in `schema.contract.test.ts` evaluates to `false` for `'/api/v1/auth/sessions'`, so `_SessionsProbe = true` and the test compiles and runs green in the current Phase 23-absent state.

## Verification Results

All 7 verification commands from the plan's `<verification>` section pass:

1. `cd apps/backend && uv run python -m scripts.export_openapi` → exit 0
2. `git diff --exit-code apps/backend/openapi.json` → exit 0
3. `pnpm --filter @sportzal/api-client codegen` → exit 0
4. `git diff --exit-code packages/api-client/src/schema.d.ts` → exit 0 (idempotent)
5. `pnpm --filter @sportzal/api-client typecheck` → exit 0
6. `pnpm --filter @sportzal/api-client test` → exit 0 (2 test files, 9 tests total)
7. `git status --porcelain` → clean tree

CI drift gates: both `Drift gate — apps/backend/openapi.json` and `Drift gate — packages/api-client/src/schema.d.ts` will be green on the resulting HEAD (the local equivalents pass clean).

## Deviations from Plan

None — plan executed exactly as written.

Task 1 took the default path (noop / no commit), which was the expected outcome documented in the plan. The pnpm install step was required before `pnpm --filter @sportzal/api-client codegen` because the worktree's `node_modules` was not pre-populated; this is standard worktree initialization behavior, not a deviation.

## Known Stubs

None. The regenerated `schema.d.ts` is fully populated with the v1.2 surface. The contract test is fully wired. No placeholder text, no TODO markers introduced.

## Threat Flags

No new HTTP routes, authentication paths, file access patterns, or schema changes at trust boundaries introduced in Phase 21. The plan's threat model covers all surface: T-21-02 (schema.d.ts tampering) is mitigated by the contract test + CI drift gate. No new threats beyond the plan's STRIDE register.

## Self-Check: PASSED

Files exist:
- `packages/api-client/src/schema.d.ts` — EXISTS
- `packages/api-client/src/schema.contract.test.ts` — EXISTS
- `.planning/PROJECT.md` — EXISTS (D-21 row appended)
- `.planning/REQUIREMENTS.md` — EXISTS (API-04 + API-05 flipped to Complete)

Commits exist:
- `d3ab76d` — chore(21): regenerate packages/api-client/src/schema.d.ts (v1.2 surface)
- `88b4bfe` — test(21): add schema.contract.test.ts forward-guard for v1.2 typed paths
- `c8f39f9` — docs(21): record D-21 + flip API-04/API-05 to Complete
