---
phase: 35-openapi-drift-gate-backend-only-api-handoff
verified: 2026-05-16T20:02:00Z
status: passed
score: 8/8 must-haves verified
overrides_applied: 0
---

# Phase 35: OpenAPI Drift Gate (backend-only API handoff) — Verification Report

**Phase Goal:** Backend контракт регенерирован байт-стабильно: `apps/backend/openapi.json` + `packages/api-client/src/schema.d.ts` экспонируют все типизированные v1.4 paths (payments, trainers, pt-package-plans, pt-packages, pt-sessions, refund endpoints). Это передача API-контракта внешней дизайн-команде.

**Verified:** 2026-05-16T20:02:00Z
**Status:** PASSED
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (ROADMAP Success Criteria + Phase verification dimensions)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Atomic single-commit regen: `apps/backend/openapi.json` + `packages/api-client/src/schema.d.ts` expose every v1.4 typed path | VERIFIED | Commit `511cbf1` modifies exactly these two files. `python3 -c "json.load(...)"` confirms all 16 v1.4 path keys present (trainers/{trainer_id}, payments, payments/by-client/{client_id}, payments/by-membership/{membership_id}, memberships/{membership_id}/refund, pt-package-plans/{plan_id}, pt-packages/{pt_package_id}/cancel/refund/sessions, pt-sessions/{pt_session_id}/cancel). Last byte `0x0a` (D-35-03 byte-stability). `git diff --exit-code` returns 0. |
| 2 | `schema.contract.test.ts` forward-guard extended — pins every v1.4 typed path + method as compile-time AssertNonNever (operationIds NOT pinned per D-35-07) | VERIFIED | 51 AssertNonNever entries (12 baseline + 39 v1.4); 6 module sub-headers (`// --- v1.4 trainers/payments/membership refund/pt-package-plans/pt-packages/pt-sessions ---`); D-35-07 explicit comment "operationIds intentionally NOT pinned" present. Tuple `_v14Checks` declared with 36 entries; `expect(_v14Checks).toHaveLength(36)` asserts. `pnpm --filter @sportzal/api-client typecheck` exits 0 (compile-time guard fires here). |
| 3 | Zero edits inside `apps/admin-web/`; existing 233+ admin-web vitest specs continue passing as canary against schema.d.ts compatibility | VERIFIED (with INFO) | `git log --oneline f273b7e..HEAD -- apps/admin-web/` empty (zero edits). `pnpm --filter sportzal-adminka test` shows 269/270 passing — 1 failure is a pre-existing **flaky wall-clock test** (CheckInPage FE-08(d), gym-hours window 20:00-20:01) that passes when re-run 1 minute later (20:01:02 → 7/7 passed). The test is unrelated to schema changes; Phase 35 cannot have caused it. |
| 4 | `packages/api-client/README.md` updated with v1.4 changelog + auth setup pointer — design team can consume artifact autonomously | VERIFIED | `## v1.4 changelog` (line 45) + `## Auth quick-start` (line 59) inserted between `## Codegen` (line 33) and `## Single-flight refresh` (line 70). 7 module bullets (Trainers, Payments ledger, Membership refund, PT-package plans, PT-packages, PT-package refund, PT-sessions). Pointer to `apps/backend/openapi.json` as source-of-truth. 4 auth entry points listed (login, refresh, mutating-CSRF, Telegram OTP triple). No inline curl examples (the single occurrence of "curl" is a forward-reference deferring to v1.5 Postman per D-35-11, NOT a tutorial example). |
| 5 | Forward-guard tests pass (api-client typecheck + test green) | VERIFIED | `pnpm --filter @sportzal/api-client typecheck` exits 0; `pnpm --filter @sportzal/api-client test` shows 10 passed (2 in schema.contract.test.ts, 8 in fetcher.test.ts). |
| 6 | Drift-gate posture: regen artifacts have no uncommitted changes | VERIFIED | `git diff --exit-code apps/backend/openapi.json packages/api-client/src/schema.d.ts` exits 0. |
| 7 | Frozen surfaces respected (apps/admin-web/src, apps/backend/app/modules, apps/backend/scripts/export_openapi.py, packages/api-client/package.json) untouched since Phase 35 start | VERIFIED | `git log --oneline f273b7e..HEAD -- apps/admin-web/src/ apps/backend/app/modules/ apps/backend/scripts/export_openapi.py packages/api-client/package.json` returns empty. |
| 8 | Wave 2 deviation acceptance: pt-sessions inventory faithfully reflects backend module shape (no /pt-sessions GET list endpoint) | VERIFIED | `openapi.json` confirms `/api/v1/pt-sessions` has POST only (no GET list). `schema.contract.test.ts` uses `_PtSessionsItemGet` on `/pt-sessions/{id}`, `_PtSessionsRecordPost`, `_PtSessionsRecordCreatedRealised` (201), `_PtSessionsByPackageOkRealised` (200) — matches D-34-08 subject-side ownership. Tuple length 36 (35+1 added 2xx anchor for pt-sessions module). Deviation documented in 35-02-SUMMARY.md "Auto-fixed Issues #1". |

**Score:** 8/8 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `apps/backend/openapi.json` | Byte-stable v1.4 OpenAPI 3.x spec exposing all locked paths | VERIFIED | 16/16 v1.4 paths present (trainers, payments, refund, pt-package-plans, pt-packages, pt-sessions). Trailing newline 0x0a. Modified in commit `511cbf1`. |
| `packages/api-client/src/schema.d.ts` | TypeScript paths + components from openapi-typescript ^7.13.0 | VERIFIED | openapi-typescript auto-generated header (lines 1-4) preserved. 58 references to v1.4 path tokens. Modified in commit `511cbf1`. |
| `packages/api-client/src/schema.contract.test.ts` | Forward-guard pinning every v1.4 path+method+body+2xx | VERIFIED | 51 AssertNonNever entries; 6 module sub-headers; 36-entry `_v14Checks` tuple; new `it()` block with `toHaveLength(36)`. Lines 1-78 of original forward-guard preserved verbatim (append-only). Modified in commit `bec30ea`. |
| `packages/api-client/README.md` | v1.4 changelog + Auth quick-start sections | VERIFIED | Both H2 sections inserted between Codegen and Single-flight refresh. 7 module bullets + source-of-truth pointer + 4 auth entry points + section pointers to existing `## CSRF` / `## Single-flight refresh`. No path/method tables (D-35-10). Modified in commit `bec30ea`. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| `apps/backend/scripts/export_openapi.py` | `apps/backend/openapi.json` | `uv run python -m scripts.export_openapi` (byte-stable JSON) | VERIFIED | openapi.json was regenerated; trailing `0x0a` confirms byte-stable contract honored. |
| `apps/backend/openapi.json` | `packages/api-client/src/schema.d.ts` | `pnpm --filter @sportzal/api-client codegen` (openapi-typescript ^7.13.0) | VERIFIED | Auto-generated header present in schema.d.ts; 58 v1.4 path tokens in TS file match openapi.json paths. |
| Atomic single commit | CI drift-gate | `git diff --exit-code` post-commit | VERIFIED | Both artifacts in single commit `511cbf1`; post-commit diff returns 0. |
| `schema.contract.test.ts` | `schema.d.ts` typed paths surface | Compile-time `AssertNonNever<paths['/api/v1/...']['method']>` | VERIFIED | `pnpm typecheck` exits 0 — all 36 v1.4 assertions resolve to non-`never` types. |
| `README.md ## Auth quick-start` | existing `## CSRF` + `## Single-flight refresh` sections | In-document section pointers (`см. § "CSRF"`, `см. § "Single-flight refresh"`) | VERIFIED | Both reference strings present at lines 64-65. |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| api-client typecheck compiles forward-guard | `pnpm --filter @sportzal/api-client typecheck` | exit 0 | PASS |
| api-client vitest passes | `pnpm --filter @sportzal/api-client test` | 10/10 passed (2 in schema.contract.test.ts) | PASS |
| OpenAPI paths inventory matches D-35-05 | `python3 -c "json.load(...)"` | 16/16 v1.4 paths present | PASS |
| OpenAPI byte-stability (trailing newline) | `tail -c1 apps/backend/openapi.json \| od` | `0a` | PASS |
| Drift-gate green (no uncommitted regen drift) | `git diff --exit-code apps/backend/openapi.json packages/api-client/src/schema.d.ts` | exit 0 | PASS |
| Frozen surfaces untouched since Phase 35 start | `git log --oneline f273b7e..HEAD -- apps/admin-web/src/ apps/backend/app/modules/ apps/backend/scripts/export_openapi.py packages/api-client/package.json` | empty | PASS |
| admin-web canary (isolated re-run after flaky window) | `pnpm --filter sportzal-adminka test src/features/visits/components/CheckInPage.test.tsx` | 7/7 passed | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| FE-10 | 35-01, 35-02 | OpenAPI drift gate: single byte-stable regen + schema.contract.test.ts forward-guard + README v1.4 changelog + auth setup pointer | SATISFIED | All four sub-deliverables verified above. REQUIREMENTS.md line 109 marked `[x]`. |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `packages/api-client/README.md` | 68 | "Sample curl examples и полный Postman collection будут опубликованы в v1.5..." | INFO | Word "curl" appears once but only as forward-reference deferring to v1.5 Postman milestone, NOT as an inline tutorial example. Spirit of D-35-11 (auth as pointer not tutorial, no inline curl examples) upheld. Plan acceptance criterion `grep -c 'curl ' == 0` was strict-literal; reality is benign deferral mention. Documented for transparency. |

No blockers or warnings.

### admin-web Canary Note

One CheckInPage FE-08(d) test failed in the full-suite run at 20:00:14 Moscow time. Investigation:

- Test sets gym-hours window `20:00-20:01` deliberately ("almost always outside") and asserts the button is disabled outside hours.
- Wall-clock at full-suite run was 20:00:14 MSK — **inside** that window — so the test's premise ("almost always outside") was wrong.
- Re-run at 20:01:02 MSK passes 7/7 in isolation.
- The test file was last modified in commit `7a7bcda` (Phase 28-02, 2026-04-08); Phase 35 makes zero edits to admin-web/src/.
- Conclusion: pre-existing flaky test, time-bound to a 1-minute window per day. NOT introduced by Phase 35. NOT a regression caused by the schema change (the failure mode is "missing Russian text in DOM", not "type mismatch / paths collapsed to never").

This does NOT block Phase 35 verification because:
1. The phase goal is contract handoff, not admin-web behavior.
2. Phase 35 made zero edits to admin-web/src/ (D-35-14 frozen surface).
3. The canary's intent (D-35-13: "tests pass unchanged after regen") is satisfied — the schema change is backwards-compatible, confirmed by the 269 unrelated tests passing and the failing test passing in isolation when wall-clock advances.

Recommendation for future: file a tech-debt note to either freeze the system clock in this test or widen the assumption window. Out of scope for Phase 35.

### Anti-Patterns Scanned (per Step 7)

Files modified by Phase 35 (from commits `511cbf1`, `4b4b845`, `bec30ea`, `ba12c41`):

| File | TBD/FIXME/XXX | TODO/HACK/PLACEHOLDER | Empty returns | Status |
|------|---------------|----------------------|---------------|--------|
| `apps/backend/openapi.json` | 0 | 0 | 0 | clean |
| `packages/api-client/src/schema.d.ts` | 0 | 0 (auto-generated) | 0 | clean |
| `packages/api-client/src/schema.contract.test.ts` | 0 | 0 | 0 | clean |
| `packages/api-client/README.md` | 0 | 0 | 0 | clean |

No debt markers in any Phase 35 file.

### Bookkeeping Checks

| Document | Expected State | Status | Evidence |
|----------|---------------|--------|----------|
| `.planning/ROADMAP.md` Phase 35 row | "Complete" | VERIFIED | Line 82: `[x] **Phase 35: OpenAPI Drift Gate** ... (completed 2026-05-16)`. Progress table line 195: `35. OpenAPI Drift Gate ... 2/2 ... Complete ... 2026-05-16`. |
| `.planning/REQUIREMENTS.md` FE-10 | Checked `[x]` | VERIFIED | Line 109: `[x] **FE-10**: OpenAPI drift gate...` |
| `.planning/STATE.md` Phase 35 status | reflects phase complete | VERIFIED (informational) | STATE.md still shows `executing` at line 5 and progress `completed_phases: 6` — STATE.md `last_activity` is correct for the timing. Phase 35 is the 7th phase; the executor's "current_focus" line still says Phase 35 (line 24) but ROADMAP authoritative source marks it complete. Non-blocking — orchestrator typically bumps STATE.md after VERIFICATION lands. |

### Gaps Summary

None. All four ROADMAP Success Criteria are observably TRUE in the codebase:

1. **Atomic regen** — single commit `511cbf1`, both artifacts modified, byte-stable, all 16 v1.4 paths exposed, drift-gate green.
2. **Forward-guard** — 36 v1.4 AssertNonNever assertions across 6 module sub-blocks; operationIds NOT pinned (D-35-07 honored); api-client typecheck + test green.
3. **admin-web frozen** — zero edits under `apps/admin-web/src/` since Phase 35 start; 269/270 tests pass (the 1 failure is a pre-existing wall-clock-flaky test unrelated to schema, confirmed by isolation re-run).
4. **README handoff** — `## v1.4 changelog` + `## Auth quick-start` sections inserted at correct insertion point with 7 module bullets + 4 auth entry points + pointers to existing `## CSRF` and `## Single-flight refresh`; no inline curl tutorials (the single "curl" word is a v1.5 deferral mention, spirit of D-35-11 upheld).

The Wave 2 plan-template deviation (pt-sessions list path correction) is documented in 35-02-SUMMARY.md and the resulting test code matches the actual backend module shape — a faithful contract pin, not a missed requirement.

---

*Verified: 2026-05-16T20:02:00Z*
*Verifier: Claude (gsd-verifier)*
