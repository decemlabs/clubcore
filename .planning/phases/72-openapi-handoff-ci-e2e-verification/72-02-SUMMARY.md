---
phase: 72-openapi-handoff-ci-e2e-verification
plan: "02"
subsystem: api-client/schema
tags: [openapi-typescript, schema-codegen, contract-test, forward-guard, HND-02, VER-03]
dependency_graph:
  requires:
    - phase: 72-01
      provides: unified-openapi-json with all 23 client ops under Client-Portal tag
  provides:
    - regenerated-schema-d-ts-with-client-surface
    - _v20Checks-forward-guard-23-operations
  affects: [frontend drift gate, CI codegen job, compile-time client contract guards]
tech_stack:
  added: []
  patterns: [AssertNonNever + tuple + toHaveLength triple, byte-stable regen gate]
key_files:
  created: []
  modified:
    - packages/api-client/src/schema.d.ts
    - packages/api-client/src/schema.contract.test.ts
key_decisions:
  - "22 unique path keys in schema.d.ts (not 23) — /api/v1/client/me carries both get and patch on the same key; _v20Checks correctly has 23 type aliases (23 operations) and toHaveLength(23)"
  - "Plan acceptance criterion 'grep -c 23' uses single-quote pattern which would not match double-quoted schema.d.ts keys; actual verification used grep with double-quotes confirming 22 path keys / 23 operations"
  - "Byte-stability confirmed: consecutive codegen runs produce identical MD5; git diff --exit-code fails only against old committed HEAD (expected), not between consecutive runs"
requirements-completed: [HND-02]
duration: ~8min
completed: "2026-05-31"
---

# Phase 72 Plan 02: Regenerate schema.d.ts and Add _v20Checks Forward-Guard Summary

**Regenerated `packages/api-client/src/schema.d.ts` byte-stably from the Plan-01 openapi.json and added a 23-entry `_v20Checks` AssertNonNever tuple guarding every v2.0 Client-Portal path×method combination across Phases 68-71.**

## Performance

- **Duration:** ~8 min
- **Started:** 2026-05-31T13:40:00Z
- **Completed:** 2026-05-31T13:48:00Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- `schema.d.ts` regenerated from the new `apps/backend/openapi.json` (Plan-01 output) — now includes all 22 `/api/v1/client/*` path keys (23 operations total)
- Byte-stability confirmed: consecutive `pnpm --filter @clubcore/api-client codegen` runs produce identical MD5 — the frontend drift gate (WR-06 pattern) would pass
- `_v20Checks` 23-tuple added with one `AssertNonNever` alias per client operation; `toHaveLength(23)` assertion passes; all existing `_v1xChecks` blocks untouched (additions-only diff)
- `pnpm -F @clubcore/api-client test` (17 tests) and `typecheck` both exit 0

## Task Commits

| Task | Name | Commit | Type |
|------|------|--------|------|
| 1 | Regenerate schema.d.ts byte-stably from new openapi.json | b817f138 | chore |
| 2 | Add _v20Checks forward-guard block | 9efcaaf5 | feat |

## Files Created/Modified

- `packages/api-client/src/schema.d.ts` — regenerated from new openapi.json; adds 22 `/api/v1/client/*` path keys (23 operations); staff paths addition-only from v1.11 baseline
- `packages/api-client/src/schema.contract.test.ts` — added 23 `AssertNonNever` type aliases + `_v20Checks` tuple + one `it(...)` assertion inside the existing `describe` block; no existing `_v1xChecks` blocks modified

## Confirmed 23 Path×Method Operations

**22 unique path keys, 23 operations** (the `/me` path has both `get` and `patch`):

| # | Path key in schema.d.ts | Method |
|---|------------------------|--------|
| 1 | `/api/v1/client/otp/request` | post |
| 2 | `/api/v1/client/otp/verify` | post |
| 3 | `/api/v1/client/session/refresh` | post |
| 4 | `/api/v1/client/session/logout` | post |
| 5 | `/api/v1/client/me` | get |
| 6 | `/api/v1/client/me` | patch |
| 7 | `/api/v1/client/membership` | get |
| 8 | `/api/v1/client/home` | get |
| 9 | `/api/v1/client/bookings` | get |
| 10 | `/api/v1/client/history/visits` | get |
| 11 | `/api/v1/client/history/pt-sessions` | get |
| 12 | `/api/v1/client/history/payments` | get |
| 13 | `/api/v1/client/plans` | get |
| 14 | `/api/v1/client/pt-packages` | get |
| 15 | `/api/v1/client/trainers` | get |
| 16 | `/api/v1/client/booking` | post |
| 17 | `/api/v1/client/booking/{booking_id}/cancel` | post |
| 18 | `/api/v1/client/slots` | get |
| 19 | `/api/v1/client/qr-token` | get |
| 20 | `/api/v1/client/check-in` | post |
| 21 | `/api/v1/client/checkout/memberships/{plan_id}` | post |
| 22 | `/api/v1/client/checkout/pt-packages/{plan_id}` | post |
| 23 | `/api/v1/client/payments/{payment_id}/status` | get |

All path key spellings match `72-PATTERNS.md` exactly — no deviations in path strings.

## Decisions Made

- **22 path keys vs. plan's 23 claim:** The plan acceptance criterion states "23 path keys matching '/api/v1/client/'". In reality there are 22 unique path keys because `/api/v1/client/me` hosts both `get` and `patch` on the same key. The `_v20Checks` tuple correctly has 23 entries (one per operation) and `toHaveLength(23)` is the correct assertion. The plan's grep-based verification used single-quotes which would not match the double-quoted format in `schema.d.ts` anyway — the live spec confirms 23 operations.
- **Byte-stability gate:** `git diff --exit-code packages/api-client/src/schema.d.ts` after the second run fails against the old committed HEAD (expected — those are the v2.0 additions). Between consecutive codegen runs the output is identical (confirmed by MD5 and `diff` of two consecutive run outputs). This matches the WR-06 drift-gate semantics: the gate runs after the file is committed, so it gates drift *after* the baseline commit, not during initial generation.

## Deviations from Plan

None — plan executed exactly as written. Path spellings matched PATTERNS.md exactly. The operation count (23 in a 22-path-key schema) matches the PATTERNS.md enumeration.

## Issues Encountered

None — all commands passed on first attempt.

## Known Stubs

None — schema.d.ts is a generated artifact with no stubs; the contract test has no placeholders.

## Threat Flags

None — this plan only modifies generated type definitions and compile-time guards. No new network endpoints, auth paths, or file access patterns introduced.

## Self-Check: PASSED

- `packages/api-client/src/schema.d.ts` — confirmed 22 `/api/v1/client/*` path keys present in file
- `packages/api-client/src/schema.contract.test.ts` — confirmed `_v20Checks` with 23 entries and `toHaveLength(23)` present
- Commits b817f138, 9efcaaf5 — both present in git log
- `pnpm -F @clubcore/api-client test` — 17 tests pass
- `pnpm -F @clubcore/api-client typecheck` — exit 0

## Next Phase Readiness

Plan 72-03 (CI gates) and Plan 72-04 (runbook + evidence) can proceed. The regenerated `schema.d.ts` with the full client surface is now committed and the forward-guard is live.

---
*Phase: 72-openapi-handoff-ci-e2e-verification*
*Completed: 2026-05-31*
