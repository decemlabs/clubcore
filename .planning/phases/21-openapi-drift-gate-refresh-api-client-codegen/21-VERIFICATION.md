---
phase: 21-openapi-drift-gate-refresh-api-client-codegen
verified: 2026-05-08T11:35:00Z
status: passed
score: 7/7 must-haves verified
overrides_applied: 0
---

# Phase 21: OpenAPI Drift Gate Refresh + api-client Codegen — Verification Report

**Phase Goal:** The frontend↔backend contract is byte-frozen for the new memberships/visits/sessions surface — drift becomes impossible without an explicit "I really meant it" commit.
**Verified:** 2026-05-08T11:35:00Z
**Status:** PASSED
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `git diff --exit-code apps/backend/openapi.json` returns 0 (byte-stable) | VERIFIED | `git diff --exit-code apps/backend/openapi.json packages/api-client/src/schema.d.ts` → exit 0 confirmed live |
| 2 | `git diff --exit-code packages/api-client/src/schema.d.ts` returns 0 after regeneration | VERIFIED | Same command above → exit 0; d3ab76d committed the regenerated artifact |
| 3 | Committed `schema.d.ts` exposes all five required v1.2 typed path keys | VERIFIED | grep confirms: `"/api/v1/membership-plans"`, `"/api/v1/memberships"`, `"/api/v1/visits"`, `"/api/v1/membership-plans/{plan_id}"`, `"/api/v1/memberships/{membership_id}/cancel"` all present; also `"/api/v1/visits/{visit_id}"` |
| 4 | `schema.contract.test.ts` exists, runs, asserts v1.2 surface, uses HasPath conditional for sessions (D-21-2) | VERIFIED | File exists at `packages/api-client/src/schema.contract.test.ts` (74 lines, non-empty); contains `HasPath<P>` helper; `D-21-2` comment present; sessions probe is conditional not hardcoded |
| 5 | `pnpm --filter @sportzal/api-client typecheck` exits 0 | VERIFIED | Live run → `tsc --noEmit` exit 0 |
| 6 | `pnpm --filter @sportzal/api-client test` exits 0 (9 tests) | VERIFIED | Live run → 2 test files, 9 tests, all passed |
| 7 | REQUIREMENTS.md API-04 + API-05 show `[x]` and `Complete` in status table | VERIFIED | grep confirms `- [x] **API-04**`, `- [x] **API-05**`, `\| API-04 \| Phase 21 \| Complete \|`, `\| API-05 \| Phase 21 \| Complete \|` |
| 8 | PROJECT.md Key Decisions records D-21 row referencing D-21-1 and D-21-4 | VERIFIED | Row present at PROJECT.md line 169; `D-21-1` and `D-21-4` both appear in the row text |

**Score:** 8/8 truths verified (plan listed 7 truths; truth 8 is the PROJECT.md D-21 check, which was enumerated separately in the plan but cross-checks out as the 8th item).

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `apps/backend/openapi.json` | Byte-stable OpenAPI spec covering v1.1 + v1.2 HTTP surface; contains `"/api/v1/membership-plans"` | VERIFIED | All required path keys confirmed via grep; 0-byte diff vs fresh export |
| `packages/api-client/src/schema.d.ts` | Auto-generated TypeScript types for v1.2 paths; contains `"/api/v1/visits"` | VERIFIED | Path keys grep confirmed; auto-generated banner intact; committed via d3ab76d |
| `packages/api-client/src/schema.contract.test.ts` | Type-level smoke test; contains `schema.contract`; non-empty | VERIFIED | 74 lines; `describe('schema.contract', ...)` present; no `as any`, no `@ts-ignore` |
| `.planning/PROJECT.md` | D-21 entry in Key Decisions table | VERIFIED | Row appended at line 169; references D-21-1, D-21-3, D-21-4, D-21-2 |
| `.planning/REQUIREMENTS.md` | API-04 + API-05 marked Complete | VERIFIED | Both checkbox `[x]` and status-table `Complete` rows confirmed |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `schema.contract.test.ts` | `schema.d.ts` | `import type { paths } from './schema'` | WIRED | Line 10: `import type { paths } from './schema'` — exact match |
| `packages/api-client/package.json` | `apps/backend/openapi.json` | `scripts.codegen` invokes `openapi-typescript` | WIRED | Script: `openapi-typescript ../../apps/backend/openapi.json --output src/schema.d.ts` |
| `apps/backend/scripts/export_openapi.py` | `apps/backend/openapi.json` | `python -m scripts.export_openapi` writes byte-stable JSON | WIRED | 0-byte diff confirmed; commit d3ab76d proves idempotent regeneration |

---

### Data-Flow Trace (Level 4)

Not applicable. Phase 21 produces type declaration files (`schema.d.ts`) and a compile-time test — no runtime data rendering is involved. The contract test's single runtime assertion (`expect(_checks).toHaveLength(9)`) operates on a compile-time-frozen constant array, not a dynamic data source.

---

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| openapi.json byte-stable | `git diff --exit-code apps/backend/openapi.json` | exit 0 | PASS |
| schema.d.ts byte-stable after regen | `git diff --exit-code packages/api-client/src/schema.d.ts` | exit 0 | PASS |
| typecheck passes | `pnpm --filter @sportzal/api-client typecheck` | exit 0 | PASS |
| 9 tests pass | `pnpm --filter @sportzal/api-client test` | 9/9 passed, exit 0 | PASS |
| v1.2 path keys in schema.d.ts | grep for all 5 required paths | all 5 match | PASS |
| sessions paths absent (D-21-1) | `grep '"/api/v1/auth/sessions"' packages/api-client/src/schema.d.ts` | 0 matches | PASS |
| No escape hatches | grep for `as any`, `@ts-ignore`, `as unknown as` | 0 matches each | PASS |

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| API-04 | 21-01-PLAN.md | `openapi.json` byte-stable; CI `git diff --exit-code` passes | SATISFIED | `git diff --exit-code apps/backend/openapi.json` → exit 0; `[x]` in REQUIREMENTS.md |
| API-05 | 21-01-PLAN.md | `schema.d.ts` regenerated; v1.2 operation IDs surface; CI diff gate passes | SATISFIED | `git diff --exit-code packages/api-client/src/schema.d.ts` → exit 0; v1.2 path keys confirmed; `[x]` in REQUIREMENTS.md |

No orphaned requirements: REQUIREMENTS.md maps exactly API-04 and API-05 to Phase 21; no additional Phase 21 IDs exist in the traceability table.

---

### D-21-* Decision Compliance

| Decision | Requirement | Verified? | Evidence |
|----------|-------------|-----------|----------|
| D-21-1: No `/api/v1/auth/sessions*` in openapi.json or schema.d.ts | Sessions absent (Phase 23 not merged) | YES | `grep '"/api/v1/auth/sessions"' packages/api-client/src/schema.d.ts` → 0 matches |
| D-21-2: `HasPath<P>` conditional helper for sessions probe — not hardcoded | Conditional type probe | YES | `type HasPath<P extends string> = P extends keyof paths ? true : false` on line 21; sessions probe uses `_HasSessions extends true ? ... : true` |
| D-21-3: No explicit `operation_id` added to backend routers | Backend code untouched | YES | `git log --name-only --oneline 6482749..HEAD -- 'apps/backend/app/**'` → empty output |
| D-21-4: `schema.contract.test.ts` exists and is non-empty | Contract test shipped | YES | 74-line file confirmed; `test -s` equivalent passes |

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `packages/api-client/src/schema.contract.test.ts` | 62 | Sessions probe assumes `get` verb — WR-01 from REVIEW.md | Warning | Could fail to compile when Phase 23 ships if sessions surface lands with only POST/DELETE (no GET on the collection route). Per REVIEW.md WR-01, this is a stylistic improvement tracked for follow-up, not a phase blocker. Current state (sessions absent) compiles and passes correctly. |
| `packages/api-client/src/schema.contract.test.ts` | 71 | Magic number `9` in `toHaveLength` — WR-02 from REVIEW.md | Warning | Adding a new type check requires remembering to bump the number. Not a current correctness issue; the count matches the tuple arity. |

Both warnings are carried forward from 21-REVIEW.md (0 critical findings). Neither blocks phase goal achievement — the contract test compiles and runs 9/9 green today. The WR-01 issue only activates when Phase 23 merges sessions endpoints; the Phase 23 executor should address it as a prerequisite to their own verification passing.

---

### Human Verification Required

None. All must-haves are verifiable programmatically. Phase 21 has no user-visible copy, no UI changes, and no external service integration.

---

### ROADMAP Success Criteria Verification

| SC | Criterion | Status |
|----|-----------|--------|
| SC1 | `export_openapi.py` regenerates `openapi.json` byte-stably; CI `git diff --exit-code apps/backend/openapi.json` passes | VERIFIED — live `git diff` exit 0 confirmed |
| SC2 | `pnpm codegen` regenerates `schema.d.ts` to match new spec; CI `git diff --exit-code packages/api-client/src/schema.d.ts` passes | VERIFIED — live `git diff` exit 0 confirmed; commit d3ab76d |
| SC3 | Committed `schema.d.ts` exposes typed `paths['/membership-plans']`, `paths['/memberships']`, `paths['/visits']` consumable from `apps/admin-web/src/shared/api` | VERIFIED — all three top-level path keys confirmed in `schema.d.ts`; `@sportzal/api-client` typecheck exit 0 means types are consumable. Sessions paths correctly absent (D-21-1; Phase 23 has not merged) |

---

## Gaps Summary

No gaps. All 7 plan must-haves verified, all 3 ROADMAP success criteria verified, both requirement IDs (API-04, API-05) satisfied and marked Complete, all D-21-* decisions honored, no backend source files touched, artifacts byte-stable, tests passing.

The two code-review warnings (WR-01, WR-02) from 21-REVIEW.md are stylistic improvements that do not affect correctness in the current (Phase 23 pre-merge) state. They are tracked in 21-REVIEW.md for the Phase 23 executor to address.

---

_Verified: 2026-05-08T11:35:00Z_
_Verifier: Claude (gsd-verifier)_
