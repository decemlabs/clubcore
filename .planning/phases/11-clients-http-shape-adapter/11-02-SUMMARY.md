---
phase: 11-clients-http-shape-adapter
plan: 02
subsystem: frontend/api
tags: [clients, optimistic-update, defensive-hardening, e2e-runbook, gap-closure]
requires:
  - apps/admin-web/src/features/clients/api/hooks.ts
  - apps/admin-web/src/entities/client/types.ts
  - apps/admin-web/src/shared/api/contracts/clients.ts
provides:
  - Hardened useUpdateClient optimistic-update path (cannot crash on undefined fullName)
  - Phase 11 live E2E runbook (35-box manual checklist for SC #4)
affects:
  - apps/admin-web/src/features/clients/api/hooks.ts
tech-stack:
  added: []
  patterns:
    - "defensive nullish coalescing on cache values whose runtime shape may be wider than the static type"
    - "promote-private-helper-to-named-export pattern for unit-testability without exposing through index barrels"
key-files:
  created:
    - apps/admin-web/src/features/clients/api/hooks.test.ts
    - .planning/phases/11-clients-http-shape-adapter/11-E2E-RUNBOOK.md
  modified:
    - apps/admin-web/src/features/clients/api/hooks.ts
decisions:
  - "applyOptimisticUpdate is now a named export (not a module-private fn) so unit tests can target the pure builder directly without a TanStack Query test harness."
  - "Single-character fix `current.fullName.split(' ')` -> `(current.fullName ?? '').split(' ')` keeps semantics for the defined-string path byte-equivalent and adds belt-and-suspenders for adapter regressions."
  - "E2E gate is human-verify, not automated — repo has no Playwright/Cypress infrastructure. Runbook is the precise script the owner walks through."
metrics:
  duration: ~7m
  completed: 2026-05-04
gap_closure: true
closes_findings:
  - INTEGRATION-CHECK-F-01
---

# Phase 11 Plan 02: Hardening + E2E Runbook Summary

Belt-and-suspenders against a future regression in the Plan 11-01 adapter:
`useUpdateClient`'s optimistic-update builder now coerces `current.fullName`
to `''` before splitting, so a malformed cache row can never crash the table.
Plus the human-verify runbook that owns Phase 11 success criterion #4.

## What was built

- **`hooks.ts` hardening** — single-character fix in
  `buildOptimisticFullName`: `current.fullName.split(' ')` →
  `(current.fullName ?? '').split(' ')`. Promoted `applyOptimisticUpdate`
  from module-private to named export so the regression test can target
  the pure builder directly.
- **`hooks.test.ts` (40 lines, 4 vitest cases)** — locks the new behaviour:
  - 3-token mock parity preserved on partial firstName update.
  - `current.fullName === undefined` does NOT throw and produces
    `'Иванов Сергей'` from `{ lastName, firstName }` input.
  - Non-name updates (phone-only) leave `fullName` intact.
  - Empty-string `email` maps to `undefined`.
- **`11-E2E-RUNBOOK.md` (61 lines, 35 unticked checkboxes)** — Phase 11 SC #4
  human-verify checklist:
  - Prerequisites (Postgres + Redis + backend + admin-web with
    `VITE_API_MODE=http`).
  - 7 numbered walkthrough sections: login, list, create (default), create
    with all optionals, edit, delete, negative checks.
  - Body-shape assertions: `birthday` (not `birthDate`), no `email: ""`,
    PATCH body contains only the changed field.
  - Console + network negative checks: no `TypeError`, no 422.

## Tasks executed

| # | Task | Commit |
| - | --- | ------ |
| 1 (RED)   | Failing test file for `applyOptimisticUpdate` | `3e0e30a` |
| 1 (GREEN) | Harden `buildOptimisticFullName` + promote helper to named export | `110c406` |
| 2 | Author `11-E2E-RUNBOOK.md` | `2daa2c9` |
| 3 | Live E2E walkthrough sign-off | (human-verify checkpoint — pending) |

## Verification results

| Check | Result |
| --- | --- |
| `pnpm test src/features/clients/api/hooks.test.ts` | 4/4 pass |
| `pnpm test` (full admin-web suite) | 108/108 pass (was 104; +4 new) |
| `pnpm typecheck` | exit 0 |
| `grep -q "export function applyOptimisticUpdate" hooks.ts` | OK |
| `grep -q "(current.fullName ?? '').split" hooks.ts` | OK |
| `! grep -E "current\.fullName\.split" hooks.ts \| grep -v "?? ''"` | OK (no unguarded form) |
| Mock parity: `clients.crud.test.ts:96` (3-token assert) | passes (no regression) |
| Runbook contains `VITE_API_MODE=http`, `POST/PATCH/DELETE /api/v1/clients`, `birthday` | OK |
| Runbook unticked-checkbox count | 35 (≥ 20 required) |

## Deviations from plan

### Auto-fixed issues

**[Rule 3 — Blocking issue] Workspace dependencies were not installed in the worktree**

- **Found during:** Task 1 RED execution (vitest binary missing).
- **Issue:** Fresh worktree — `node_modules` symlinks not yet materialised.
- **Fix:** Ran `pnpm install` (lockfile up-to-date, ~2s).
- **Files modified:** none (only `node_modules`).
- **Commit:** none.

**[Rule 3 — Blocking issue] `routeTree.gen.ts` was not generated**

- **Found during:** Task 1 typecheck verification (after GREEN).
- **Issue:** Same precondition issue Plan 11-01 documented:
  TanStack Router auto-generates `src/routeTree.gen.ts` only when the Vite
  plugin runs. A standalone `tsc -b --noEmit` then sees pre-existing errors
  caused entirely by the missing file.
- **Fix:** Ran `pnpm exec vite build` once to materialise the file;
  typecheck then exited 0 cleanly.
- **Files modified:** none in source tree (only `dist/` and the gitignored
  `src/routeTree.gen.ts`).
- **Commit:** none.

**[Filter pattern note]** Plan referenced `pnpm -F admin-web ...`; the
workspace name is actually `sportzal-adminka`. Ran commands from
`apps/admin-web/` directory with bare `pnpm test` / `pnpm typecheck`. No
behavioural change; the verification block in the plan is identical when
executed via either filter form because the same `package.json` scripts
run.

### Tech-stack additions

None.

### Authentication gates

None. Code/doc tasks ran fully autonomously. Task 3 (human-verify) is the
intentional manual gate.

## Threat model compliance

- **T-11-05 (Denial of Service — useUpdateClient.onMutate):** mitigated.
  The crash vector (`undefined.split(' ')`) is now guarded by `?? ''`.
  Test 2 in `hooks.test.ts` is the regression lock — any future revert
  of the guard re-introduces the crash and is caught by CI.
- **T-11-06 (Tampering / Information Disclosure — runbook execution):**
  accepted as planned. Runbook runs against the developer's local seeded
  stack; no production data, no PII risk beyond the developer's own
  session.

No new threat surfaces were introduced.

## Known stubs

None. Hardening is fully wired; the runbook is the documented gate, not a
stub for future automation. (If E2E test infrastructure is added later,
the runbook becomes the source-of-truth for the test scenarios.)

## Self-Check: PASSED

Files verified to exist:

- `apps/admin-web/src/features/clients/api/hooks.test.ts` — FOUND
- `apps/admin-web/src/features/clients/api/hooks.ts` — FOUND (modified;
  contains `export function applyOptimisticUpdate` and the `?? ''` guard)
- `.planning/phases/11-clients-http-shape-adapter/11-E2E-RUNBOOK.md` — FOUND

Commits verified to exist on the worktree branch:

- `3e0e30a` — FOUND (`test(11-02): add failing test for applyOptimisticUpdate`)
- `110c406` — FOUND (`feat(11-02): harden useUpdateClient against undefined fullName`)
- `2daa2c9` — FOUND (`docs(11-02): add Phase 11 live E2E runbook`)

## TDD Gate Compliance

Task 1 followed RED → GREEN cleanly:

1. **RED commit `3e0e30a`** (`test(...)`) — added `hooks.test.ts` with 4
   cases. Verified failing: `TypeError: applyOptimisticUpdate is not a
   function` (helper was module-private at that point).
2. **GREEN commit `110c406`** (`feat(...)`) — promoted helper to named
   export and added the `?? ''` guard; same test file then 4/4 pass.
3. No REFACTOR commit — the change was a single token; no further cleanup
   needed.

Plan-level type is `execute` (not `tdd`), so plan-wide gate enforcement is
not required — but the per-task `tdd="true"` gate is satisfied.
