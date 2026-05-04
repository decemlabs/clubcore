---
phase: 11-clients-http-shape-adapter
plan: 01
subsystem: frontend/api
tags: [clients, http-adapter, integration, gap-closure]
requires:
  - apps/admin-web/src/entities/client/types.ts
  - apps/admin-web/src/shared/api/contracts/clients.ts
  - apps/admin-web/src/shared/api/services/http/_envelope.ts
  - packages/api-client/src/schema.d.ts
provides:
  - apps/admin-web/src/shared/api/services/http/_clientsAdapter.ts
  - http ClientsService that returns FE-shaped Client objects
affects:
  - apps/admin-web/src/shared/api/services/http/clients.ts
tech-stack:
  added: []
  patterns:
    - "pure adapter module between FE domain types and backend wire schemas"
    - "incremental object building (no spread+delete) for empty-string omission"
key-files:
  created:
    - apps/admin-web/src/shared/api/services/http/_clientsAdapter.ts
    - apps/admin-web/src/shared/api/services/http/_clientsAdapter.test.ts
  modified:
    - apps/admin-web/src/shared/api/services/http/clients.ts
decisions:
  - "Adapter never substitutes null for empty strings — D-01 (omit, do not clear) is honoured for both create and update."
  - "fullName is composed via filter+trim so whitespace-only backend rows cannot break list rendering."
  - "Backend-only fields (gender, tags, emergencyContact, telegramUserId, createdByUserId, updatedAt) are dropped at the boundary; Client stays narrow until v1.2."
metrics:
  duration: ~10m
  completed: 2026-05-04
gap_closure: true
closes_findings:
  - INTEGRATION-CHECK-F-01
  - INTEGRATION-CHECK-F-02
---

# Phase 11 Plan 01: Clients HTTP Shape Adapter Summary

Three-function pure adapter (`responseToClient`, `createInputToRequest`,
`updateInputToRequest`) wired into `http/clients.ts` so `VITE_API_MODE=http`
returns FE-shaped `Client` rows and sends backend-shaped `Client*Request`
bodies — closing INTEGRATION-CHECK F-01 (undefined `fullName`) and F-02
(422 on create from `birthDate`/`email=""`).

## What was built

- **`_clientsAdapter.ts` (94 lines)** — three pure exports:
  - `responseToClient(r)`: composes `fullName` from `lastName`/`firstName`/
    `middleName` (filter+trim against whitespace-only parts), maps
    `birthday` → `birthDate` (null/empty → `undefined`), drops
    backend-only fields.
  - `createInputToRequest(input)`: always emits `{lastName, firstName,
    phone}`; renames `birthDate` → `birthday`; OMITS optional fields
    whose value is `''` or absent. Never substitutes `null`.
  - `updateInputToRequest(input)`: same omission rules per-key; per
    Phase 8 D-01 empty-string `birthDate`/`email`/`middleName`/`notes`
    are treated as omit (no-change), not as explicit clear.
- **`_clientsAdapter.test.ts` (268 lines, 26 tests)** — covers every
  bullet from the plan's `<behavior>` block: full-name composition with
  and without middleName, whitespace-only parts, birthday round-trip,
  empty-string omission, no `"birthDate"` substring, no `null`
  emission, partial update semantics, backend-only field projection.
- **`http/clients.ts` rewrite** — every read flows through
  `responseToClient`, every write through the input mapper. The bad
  TypeScript-only casts (`unwrap<Pagination<Client>>`, `unwrap<Client>`)
  are gone — the new shape is `unwrap<PaginatedClientResponse>` /
  `unwrap<ClientResponse>` followed by an explicit `.map(responseToClient)`.

## Tasks executed

| # | Task | Commit |
| - | --- | ------ |
| 1 (RED)   | Failing test file for adapter helpers | `e6b329b` |
| 1 (GREEN) | Implement adapter helpers (26 tests pass) | `033aa8f` |
| 2 | Wire adapter into `http/clients.ts` | `b0f4755` |

## Verification results

| Check | Result |
| --- | --- |
| `pnpm -F sportzal-adminka test src/shared/api/services/http/_clientsAdapter.test.ts` | 26/26 pass |
| `pnpm -F sportzal-adminka test` (full suite) | 104/104 pass (no regression) |
| `pnpm -F sportzal-adminka typecheck` | exit 0 |
| `grep "from './_clientsAdapter'" http/clients.ts` | OK |
| `grep "responseToClient" http/clients.ts` | 5 occurrences (list, get, create, update, import) |
| `! grep "unwrap<Pagination<Client>>\|unwrap<Client>" http/clients.ts` | OK (bad casts gone) |
| `grep "birthday" _clientsAdapter.ts` | OK |
| Acceptance test: `createInputToRequest({…, email: '', birthDate: '', middleName: '', notes: ''})` deep-equals `{lastName:'A',firstName:'B',phone:'+71112223344'}` | OK (asserted in test file) |

## Deviations from plan

### Auto-fixed issues

**[Rule 3 — Blocking issue] Workspace dependencies were not installed in the worktree**

- **Found during:** Task 1 RED execution (vitest binary missing).
- **Issue:** Fresh worktree had no `node_modules`, so `pnpm -F admin-web test` failed
  with "Command 'vitest' not found".
- **Fix:** Ran `pnpm install` (lockfile-up-to-date, ~2s).
- **Files modified:** none (only `node_modules`).
- **Commit:** none (install is a side effect of executing tests, not code change).

**[Rule 3 — Blocking issue] `routeTree.gen.ts` was not generated**

- **Found during:** Task 1 typecheck verification.
- **Issue:** TanStack Router auto-generates `src/routeTree.gen.ts` only when Vite
  plugin runs (build / dev). A standalone `tsc -b --noEmit` saw 21 pre-existing
  errors caused entirely by the missing file. These errors were not introduced
  by Plan 11-01 — `git stash` showed identical errors with my changes reverted.
- **Fix:** Ran `pnpm exec vite build` once to materialise `routeTree.gen.ts`;
  typecheck then exited 0 cleanly.
- **Files modified:** none in source tree (only `dist/` and the gitignored
  `src/routeTree.gen.ts`).
- **Commit:** none.

**[Filter pattern adjustment]**

- **Found during:** Task 1 GREEN.
- **Issue:** Plan's draft code used `filter(Boolean)` followed by `.trim()`. With
  TypeScript `strict: true` + `noUncheckedIndexedAccess`, `filter(Boolean)` on
  `(string | null | undefined)[]` does not narrow the result type to `string[]`
  for the subsequent `.join(' ')` call (the inferred element stays
  `string | null | undefined`).
- **Fix:** Used `.filter((s): s is string => Boolean(s))` (the alternative the
  plan explicitly allowed under "filter(Boolean)|filter((s)") — narrows to
  `string[]` and joins cleanly.
- **Files modified:** `_clientsAdapter.ts`.
- **Commit:** `033aa8f`.

### Tech-stack additions

None. Plan was contained to three files in
`apps/admin-web/src/shared/api/services/http/`.

### Authentication gates

None. Plan ran fully autonomously.

## Threat model compliance

All four STRIDE entries from the plan's `<threat_model>` are honoured:

- **T-11-01 (Tampering — request output):** Adapter only OMITS empty-string
  optionals; never substitutes `null`. `JSON.stringify(out).not.toContain('null')`
  is asserted by tests.
- **T-11-02 (Information Disclosure):** `responseToClient` projects to the
  narrow `Client` shape; tests assert the absence of `gender`/`tags`/
  `emergencyContact`/`telegramUserId`/`createdByUserId`/`updatedAt` on the result.
- **T-11-03 (DoS — fullName composition):** `.filter(Boolean)` + `.trim()` is
  asserted to collapse a `lastName: ' '` row down to the remaining tokens.
- **T-11-04 (Validation bypass via empty string):** `email: ''` produces
  `{}` (or omits the key from a larger payload), so the backend's `EmailStr`
  validator never sees an empty string.

No new threat surfaces were introduced; this plan is strictly narrower than
the existing http transport.

## Known stubs

None. The adapter is fully wired; no placeholder data flows to the UI.

## Self-Check: PASSED

Files verified to exist:

- `apps/admin-web/src/shared/api/services/http/_clientsAdapter.ts` — FOUND
- `apps/admin-web/src/shared/api/services/http/_clientsAdapter.test.ts` — FOUND
- `apps/admin-web/src/shared/api/services/http/clients.ts` — FOUND (modified)

Commits verified to exist on the worktree branch:

- `e6b329b` — FOUND (`test(11-01): add failing test for clients http shape adapter`)
- `033aa8f` — FOUND (`feat(11-01): implement clients http shape adapter`)
- `b0f4755` — FOUND (`feat(11-01): wire clients adapter into http impl`)

## TDD Gate Compliance

This plan is `type: execute` with `tdd="true"` on Task 1 only — full plan-level
TDD gate is not required, but Task 1 followed RED → GREEN cleanly:

1. RED commit `e6b329b` (`test(...)`) — added failing test file (vite reported
   "Failed to resolve import './_clientsAdapter'"). Verified failing before
   adding the implementation.
2. GREEN commit `033aa8f` (`feat(...)`) — added the three exports; the same
   test file then reported 26/26 pass.
3. No REFACTOR commit was needed — implementation is small enough that the
   GREEN code already meets the project's no-semicolons / single-quotes /
   100-col conventions.
