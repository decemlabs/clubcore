---
phase: 11-clients-http-shape-adapter
verified: 2026-05-04T23:30:00Z
status: passed
score: 9/9 must-haves verified
overrides_applied: 0
deferred:
  - truth: "Owner runs the live E2E runbook (`11-E2E-RUNBOOK.md`) end-to-end against `docker compose up` + admin-web with `VITE_API_MODE=http` and ticks every checkbox (SC #4)."
    addressed_in: "Phase 12.1"
    evidence: "ROADMAP.md Phase 12.1 SC #3: 'Re-running Phase 11 11-E2E-RUNBOOK.md end-to-end ... ticks every checkbox ... 11-HUMAN-UAT.md status: flips from deferred to resolved'. Backend defect (clients/service.py missing await session.commit()) blocks SC #4 — not a Phase 11 defect."
---

# Phase 11: Clients HTTP Shape Adapter Verification Report

**Phase Goal:** Make Phase 10 SC #2 actually true on a running backend — close INTEGRATION-CHECK F-01 (response shape: `fullName` composition + `birthday → birthDate`) and F-02 (request shape: `birthDate → birthday` + empty-string omission). Also harden `useUpdateClient` optimistic path against undefined `fullName`.

**Verified:** 2026-05-04T23:30:00Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | http `list()` and `get()` return objects whose `fullName` is a non-empty string composed from `lastName + firstName + middleName` (single-space, trimmed) — never undefined | VERIFIED | `_clientsAdapter.ts:37-53` composes via `[r.lastName, r.firstName, r.middleName].filter((s): s is string => Boolean(s)).join(' ').trim()`. `clients.ts:33-36, 38-43` flow `list().items` and `get()` through `responseToClient`. Asserted by `_clientsAdapter.test.ts:30-55` (4 fullName composition tests including whitespace-only collapse) |
| 2 | http `list()` and `get()` return objects whose `birthDate` mirrors backend `birthday` (or undefined when null/empty) | VERIFIED | `_clientsAdapter.ts:50` `if (r.birthday) client.birthDate = r.birthday`. Tests `_clientsAdapter.test.ts:57-73` cover null→undefined, "1990-04-12"→"1990-04-12", ''→undefined |
| 3 | http `create()` and `update()` send a body containing key `birthday` (not `birthDate`) and OMIT optional fields with `''` value | VERIFIED | `_clientsAdapter.ts:64-94` builds incrementally with `if (input.X) out.X = ...`. `clients.ts:46, 54` invoke `createInputToRequest`/`updateInputToRequest`. Tests `_clientsAdapter.test.ts:128-267` include `JSON.stringify(out)).not.toContain('"birthDate"')` and assert empty-string `email`/`birthDate`/`middleName`/`notes` produce omission |
| 4 | Adapter helpers are pure, exported, with unit tests covering composition / round-trip / omission | VERIFIED | Three named exports in `_clientsAdapter.ts`: `responseToClient`, `createInputToRequest`, `updateInputToRequest`. 26 vitest cases in `_clientsAdapter.test.ts` cover every required behavior |
| 5 | `pnpm -F admin-web typecheck` exits 0 and `pnpm -F admin-web test` exits 0 | VERIFIED | Re-run during verification: typecheck exit 0; `Test Files: 21 passed (21); Tests: 108 passed (108)` |
| 6 | `useUpdateClient` optimistic-update path never crashes when `current.fullName === undefined` | VERIFIED | `hooks.ts:45` reads `(current.fullName ?? '').split(' ')`. Regression test `hooks.test.ts:18-26` asserts `expect(run).not.toThrow()` and produces `'Иванов Сергей'` |
| 7 | Partial name update recomposes `fullName` from `current` + `input` without `.split` on a possibly-undefined value | VERIFIED | `hooks.ts:44-50` `buildOptimisticFullName` always coalesces. Test `hooks.test.ts:13-16` confirms 3-token mock parity ('Иванов Сергей Иван') |
| 8 | Mock-mode regression: `clients.crud.test.ts:96` (`updated.fullName.split(' ').length >= 3`) still passes | VERIFIED | Full suite shows `clients.crud.test.ts (9 tests)` green, including `preserves split-by-space behavior on partial name update of a 4-token full name` |
| 9 | E2E runbook lives at `11-E2E-RUNBOOK.md` with numbered checklist for `VITE_API_MODE=http` against running backend | VERIFIED | File exists (61 lines, 35 unticked checkboxes covering prerequisites + 7 numbered walkthrough sections + sign-off); contains `VITE_API_MODE=http`, `POST/PATCH/DELETE /api/v1/clients`, `birthday`, `birthDate` distinction |

**Score:** 9/9 truths verified

### Deferred Items

| # | Item | Addressed In | Evidence |
|---|------|--------------|----------|
| 1 | Owner ticks every box in `11-E2E-RUNBOOK.md` against live backend (Phase 11 SC #4) | Phase 12.1 (clients-service-commit-fix) | ROADMAP.md Phase 12.1 SC #3 explicitly states the runbook will be re-run after that phase lands. The blocker is a Phase 8 backend defect (`apps/backend/app/modules/clients/service.py` missing `await session.commit()`), not Phase 11 FE work. Documented in `11-HUMAN-UAT.md` (`status: deferred`, `deferred_until: phase-12.1-clients-service-commit`) |

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `apps/admin-web/src/shared/api/services/http/_clientsAdapter.ts` | Pure mapping helpers (3 exports) | VERIFIED | 94 lines, exports `responseToClient`, `createInputToRequest`, `updateInputToRequest`. Pure (no I/O), uses incremental object building (no spread+delete), narrows via `(s): s is string => Boolean(s)` for strict-mode joining |
| `apps/admin-web/src/shared/api/services/http/_clientsAdapter.test.ts` | Unit tests for the three adapter functions | VERIFIED | 269 lines, 26 vitest cases across 3 `describe` blocks; covers full-name composition, null/empty/whitespace edge cases, birthday round-trip, omission contract, "no birthDate substring" assertion, "no null in JSON" assertion |
| `apps/admin-web/src/shared/api/services/http/clients.ts` | http impl piping reads through `responseToClient` and writes through input mappers | VERIFIED | 65 lines; imports adapter helpers (`clients.ts:10-14`); `list` unwraps `PaginatedClientResponse` then `.map(responseToClient)`; `get`/`create`/`update` all unwrap `ClientResponse` then return `responseToClient(raw)`; `create`/`update` build body via input mappers; `unwrap<Pagination<Client>>`/`unwrap<Client>` casts removed |
| `apps/admin-web/src/features/clients/api/hooks.ts` | Hardened `useUpdateClient` optimistic builder; `applyOptimisticUpdate` exported | VERIFIED | `hooks.ts:45` uses `(current.fullName ?? '').split(' ')` (guarded form); `hooks.ts:52` `export function applyOptimisticUpdate(...)` |
| `apps/admin-web/src/features/clients/api/hooks.test.ts` | Regression test for `applyOptimisticUpdate` undefined `fullName` | VERIFIED | 41 lines, 4 vitest cases: 3-token parity, undefined-fullName non-throw, no-name-field passthrough, empty-string email omission |
| `.planning/phases/11-clients-http-shape-adapter/11-E2E-RUNBOOK.md` | Numbered manual checklist for SC #4 | VERIFIED | 62 lines, 35 unticked checkboxes; 7 walkthrough sections; explicit body-shape assertions |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| `http/clients.ts` | `http/_clientsAdapter.ts` | named imports | WIRED | `clients.ts:10-14` `import { responseToClient, createInputToRequest, updateInputToRequest } from './_clientsAdapter'`; 9 in-file references |
| `http/clients.ts` | `@sportzal/api-client` schema | `components['schemas']['ClientResponse']` | WIRED | `clients.ts:1` imports `request, type components`; `clients.ts:16` aliases `ClientResponse` |
| `useUpdateClient` cache | `applyOptimisticUpdate(Client, ClientUpdateInput)` | onMutate optimistic write to TanStack Query cache | WIRED | `hooks.ts:77` calls `applyOptimisticUpdate(c, input)` for each cached list row; `hooks.ts:83` calls it for detail snapshot |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `http/clients.ts` `list()` | `raw.items` (backend pagination items) | `unwrap<PaginatedClientResponse>(await request('get', '/api/v1/clients?...'))` then `.map(responseToClient)` | Yes (real backend pagination payload mapped to FE Client) | FLOWING |
| `http/clients.ts` `get()` | `raw` ClientResponse | live `GET /api/v1/clients/{client_id}` then `responseToClient(raw)` | Yes | FLOWING |
| `http/clients.ts` `create()` body | `createInputToRequest(input)` | FE form → Zod-validated input → adapter builder | Yes | FLOWING |
| `http/clients.ts` `update()` body | `updateInputToRequest(input)` | FE partial diff → adapter builder | Yes | FLOWING |

Note: live API curl evidence in `11-HUMAN-UAT.md` confirms POST minimal/full body shapes are correct AND that pre-adapter shapes (`birthDate` key, `email: ""`) are rejected with backend 422 — proves the adapter rename and omission are mechanically required and correct.

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Adapter unit tests pass | `pnpm -F sportzal-adminka test src/shared/api/services/http/_clientsAdapter.test.ts` | 26 tests pass (re-run during verification) | PASS |
| Optimistic-update regression tests pass | `pnpm -F sportzal-adminka test src/features/clients/api/hooks.test.ts` | 4 tests pass | PASS |
| Full admin-web suite green | `pnpm -F sportzal-adminka test` | 21 files / 108 tests pass | PASS |
| Strict typecheck clean | `pnpm -F sportzal-adminka typecheck` | exit 0 | PASS |
| `clients.ts` no longer uses bad TS-only casts | `grep -E 'unwrap<Pagination<Client>>\|unwrap<Client>' clients.ts` | no matches | PASS |
| Hardened guard present, unguarded form gone | `grep "(current.fullName ?? '').split"` matches; `grep "current\.fullName\.split"` outside the guarded form returns no match | guarded form found, raw form absent | PASS |
| Live API contract verification (curl + cookies, port 8000) | See `11-HUMAN-UAT.md` evidence table | POST 201 with correct body shape; pre-adapter `birthDate` key → 422; `email: ""` → 422 | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| CLIENTS-01 | 11-01, 11-02 | `clients` schema (last/first/middle/birthday/etc.) — FE consumption side | SATISFIED | `responseToClient` correctly maps every field of `ClientResponse` documented in `schema.d.ts` to FE `Client`; backend-only fields (`gender`, `tags`, `emergencyContact`, `telegramUserId`, `createdByUserId`, `updatedAt`) are intentionally projected away |
| CLIENTS-05 | 11-01, 11-02 | `GET /api/v1/clients/{id}` returns single client | SATISFIED | `clients.ts:38-43` `get(id)` calls `request('get', '/api/v1/clients/{client_id}', ...)` then `responseToClient(raw)`. Hook `useClient` wired in `hooks.ts:19-26` |
| CLIENTS-06 | 11-01, 11-02 | `POST /api/v1/clients` create with required `lastName`/`firstName`/`phone` | SATISFIED | `clients.ts:44-49` `create()` always emits the three required keys via `createInputToRequest` (`_clientsAdapter.ts:64-75`); empty-string optionals omitted; `birthDate` renamed to `birthday`. Live curl shows 201 |
| CLIENTS-07 | 11-01, 11-02 | `PATCH /api/v1/clients/{id}` partial update | SATISFIED | `clients.ts:50-58` `update()` sends only present non-empty keys (`updateInputToRequest`, `_clientsAdapter.ts:84-94`); `{}` for empty input; `birthDate` renamed to `birthday` |
| FE-01 | 11-01, 11-02 | `http/clients.ts` implements service contract using `@sportzal/api-client` | SATISFIED | `clients.ts:1` imports `request, type components` from `@sportzal/api-client`; all 5 service methods now produce/consume the FE-shaped `Client` correctly |
| FE-04 | 11-01, 11-02 | TanStack Query hooks use `clientsKeys`; mutations use `onMutate`/`onError`/`onSettled` for optimistic updates with rollback | SATISFIED | `hooks.ts:67-98` `useUpdateClient` uses `clientsKeys.lists()`/`clientsKeys.detail(id)`, has `onMutate` (with cancel + snapshot), `onError` (rollback from snapshot), `onSettled` (invalidate). Optimistic builder hardened against undefined `fullName` |

All 6 PLAN-declared requirements are accounted for. No orphaned requirements: REQUIREMENTS.md maps each of `CLIENTS-01`, `CLIENTS-05`, `CLIENTS-06`, `CLIENTS-07`, `FE-01`, `FE-04` to "Phase 8, 11" or "Phase 10, 11" — every Phase 11 ID claimed in plans matches the REQUIREMENTS.md row, and no Phase-11-mapped REQ-ID is missing from the plans.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| (none in Phase 11 files) | — | — | — | Scan of `_clientsAdapter.ts`, `clients.ts`, `hooks.ts` for `TODO`, `FIXME`, `XXX`, `HACK`, `placeholder` returned no matches |

Note: `11-REVIEW.md` records 3 warnings (WR-01: optimistic clear vs request omit semantics; WR-02 / WR-03 not blockers). These are acknowledged future hardening, not blockers for the phase goal.

### Human Verification Required

None outstanding. The single human-verify item (E2E runbook walkthrough, SC #4) is **deferred** to Phase 12.1 because of an out-of-scope backend defect (`clients/service.py` missing `await session.commit()`), as documented in `11-HUMAN-UAT.md` and `ROADMAP.md` Phase 12.1.

### Gaps Summary

No gaps. Phase 11's stated scope (the FE adapter that closes INTEGRATION-CHECK F-01 and F-02 plus the optimistic-update hardening) is fully delivered:

- Adapter helpers exist as pure exports with comprehensive unit tests (26 cases).
- `http/clients.ts` is rewired so every read flows through `responseToClient` and every write through the input mappers; the bad TS-only casts (`unwrap<Pagination<Client>>`, `unwrap<Client>`) are gone.
- `useUpdateClient.buildOptimisticFullName` cannot crash on undefined `fullName`; the regression test locks the new behavior.
- The full admin-web suite is green (108/108) and typecheck exits 0.
- Live API curl tests in `11-HUMAN-UAT.md` mechanically verify the F-01/F-02 contract on the running backend, including 422 negative tests proving the rename and omission rules are required and correct.

The only outstanding scope is SC #4 (live runbook walkthrough), which is explicitly deferred to Phase 12.1 (`clients-service-commit-fix`) per ROADMAP.md and `11-HUMAN-UAT.md`. The blocker is a separate backend defect that Phase 11 does not own; Phase 11's frontend work is complete and verified.

---

_Verified: 2026-05-04T23:30:00Z_
_Verifier: Claude (gsd-verifier)_
