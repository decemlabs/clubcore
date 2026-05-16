---
phase: 35-openapi-drift-gate-backend-only-api-handoff
plan: 02
subsystem: api
tags: [openapi, codegen, typescript, contract-test, forward-guard, api-client, documentation, backend-only-handoff]

# Dependency graph
requires:
  - phase: 35-01
    provides: regenerated apps/backend/openapi.json + packages/api-client/src/schema.d.ts pinning the v1.4 typed surface (Phases 31-34)
provides:
  - Extended forward-guard in packages/api-client/src/schema.contract.test.ts pinning every v1.4 path+method pair as compile-time AssertNonNever, plus body-realisation guards for refund + pt-session-cancel POSTs and 2xx-reachability guards per module
  - v1.4 changelog section + Auth quick-start section in packages/api-client/README.md for external design-team consumers (backend-only handoff per 2026-05-15 pivot)
affects: [phase-36-milestone-verification, v1.5-api-handoff-postman, v2.0-frontend-integration]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - AssertNonNever forward-guard for OpenAPI-typescript drift detection (compile-time)
    - Per-module 2xx-reachability anchor pattern (one per logical module)
    - Body-realisation guards for non-trivial POST endpoints (refund, pt-session record/cancel)
    - Append-only README discipline (D-35-10) — new sections inserted between existing ones with zero edits to legacy content
    - README "source-of-truth pointer" pattern instead of duplicating endpoint tables (anti-rot)
    - Auth quick-start as POINTER not tutorial (D-35-11) — defer Postman/curl to v1.5

key-files:
  created: []
  modified:
    - packages/api-client/src/schema.contract.test.ts (+167 lines; new v1.4 surface block + _v14Checks tuple + new it() describe)
    - packages/api-client/README.md (+25 lines; ## v1.4 changelog + ## Auth quick-start)

key-decisions:
  - "Added _PtSessionsRecordCreatedRealised (201 anchor) and _PtSessionsByPackageOkRealised (200 anchor) instead of the plan-template _PtSessionsListOkRealised which referenced a non-existent path['/api/v1/pt-sessions']['get']. Re-derived inventory from schema.d.ts per CROSS-CHECK 2 directive."
  - "Used pnpm filter target 'sportzal-adminka' for admin-web canary (Wave 1 deviation propagation — package name is sportzal-adminka, not @sportzal/admin-web)."
  - "Generated apps/admin-web/src/routeTree.gen.ts via `pnpm exec vite build` to enable admin-web typecheck (gitignored auto-generated artifact, required before tsc -b)."

patterns-established:
  - "Pattern 1: Forward-guard appended ONLY, never reshapes existing helpers/blocks — keeps Phase 21 / Phase 23 conditional probes verbatim and adds a sibling _v14Checks tuple."
  - "Pattern 2: Module 2xx anchor location is flexible — for modules where the list surface lives on a different path (pt-sessions list via /pt-packages/{id}/sessions), the anchor moves to that path rather than inventing a non-existent endpoint."

requirements-completed: [FE-10]

# Metrics
duration: 7min
completed: 2026-05-16
---

# Phase 35 Plan 02: Forward-Guard Extension + README v1.4 Handoff Summary

**Pinned all 36 v1.4 path+method+body+2xx assertions as compile-time AssertNonNever in api-client schema.contract.test.ts and appended v1.4 changelog + Auth quick-start pointer sections to api-client README for external design-team consumers.**

## Performance

- **Duration:** 7 min
- **Started:** 2026-05-16T16:50:11Z
- **Completed:** 2026-05-16T16:57Z
- **Tasks:** 2 (Task 1 forward-guard + Task 2 README append, bundled in one commit per plan)
- **Files modified:** 2

## Accomplishments

- Forward-guard now hard-pins every v1.4 typed path+method pair from Phases 31-34 (trainers, payments, membership refund, pt-package-plans, pt-packages, pt-sessions). Any future codegen regression that collapses one of these paths to `never` will fail `pnpm --filter @sportzal/api-client typecheck` before it can ship.
- Body-realisation guards in place for the three high-risk POSTs identified by D-35-08: membership refund, pt-package refund, pt-session cancel. Plus pt-session POST + trainer POST + pt-package-plan POST + pt-package POST request bodies.
- One 2xx-reachability anchor per module (D-35-09): trainers 200 list, payments 200 list, pt-package-plans 200 list, pt-packages 200 list, pt-sessions 201 record + 200 by-package-list.
- README has a concise per-module v1.4 changelog (7 bullets) with a pointer to `apps/backend/openapi.json` as source-of-truth — no path/method tables that would rot.
- README has an Auth quick-start section that ENUMERATES the four entry points (login, refresh, mutating-CSRF, Telegram OTP triple) and POINTS to the existing `## CSRF` + `## Single-flight refresh` sections for the runtime contract. No inline curl (deferred to v1.5 Postman per D-35-11).
- Admin-web canary green: 46 test files, 270 tests passed unchanged.

## Task Commits

Both tasks bundled per plan frontmatter (`files_modified` lists exactly the two files):

1. **Task 1 + Task 2: Extend forward-guard + README v1.4 handoff** — `bec30ea` (docs)

Final file metrics:
- `packages/api-client/src/schema.contract.test.ts`: 91 → 257 lines (+166)
- `packages/api-client/README.md`: 57 → 82 lines (+25)

## Files Created/Modified

- `packages/api-client/src/schema.contract.test.ts` — Appended `// --- v1.4 surface (Phases 31-34, backend-only handoff) ---` block with 34 type-aliases pinning each path+method, request-body realisation guards for refund + pt-session POSTs, and 2xx anchors per module. New `const _v14Checks: [...] = [...]` tuple of 36 entries consumed by a new `it('compiles against the regenerated v1.4 typed paths surface ...')` block. Existing v1.2 block (lines 1-78) untouched verbatim.
- `packages/api-client/README.md` — Inserted `## v1.4 changelog` (7 module bullets + source-of-truth pointer) and `## Auth quick-start` (4 entry points + section pointers) between existing `## Codegen` and `## Single-flight refresh`. Zero edits to existing sections.

## Decisions Made

- **D-35-02 / D-35-07 honored:** Comment in the new v1.4 block calls out explicitly that operationIds are NOT pinned (`grep -c 'operations\[' schema.contract.test.ts` == 0 in the new block).
- **D-35-10 changelog format honored:** Concise per-module bullets only; zero markdown tables (`grep -c '| Method |' README.md` == 0).
- **D-35-11 auth as pointer honored:** Zero inline curl examples (`grep -c 'curl ' README.md` == 0); explicit references to `## CSRF` and `## Single-flight refresh` sections.
- **D-35-13 admin-web canary honored:** Filter target updated to `sportzal-adminka` (Wave 1 deviation propagation); 270 tests passed (Wave 1 SUMMARY confirms the actual count is 270, not the 233 in the plan frontmatter `must_haves.truths`).
- **D-35-18 pre-commit verification honored:** `git diff --exit-code apps/backend/openapi.json packages/api-client/src/schema.d.ts packages/api-client/package.json` returned 0 — Wave 1 artifacts untouched.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 — Bug in plan template] Plan referenced non-existent `paths['/api/v1/pt-sessions']['get']`**
- **Found during:** Task 1 typecheck (first compile attempt failed with `error TS2339: Property 'responses' does not exist on type 'undefined'` at `_PtSessionsListOkRealised`).
- **Issue:** The plan's verbatim template included three aliases referencing `paths['/api/v1/pt-sessions']['get']` (`_PtSessionsListGet`, `_PtSessionsListOkRealised`). But the regenerated `schema.d.ts` confirms `/api/v1/pt-sessions` exposes **POST only** (record); the list surface lives at `/api/v1/pt-packages/{pt_package_id}/sessions` GET (subject-side ownership per D-34-08). The list path was already represented as `_PtSessionsByPackageGet`.
- **Fix:** Per the plan's own "CROSS-CHECK 2" directive ("STOP and re-derive the inventory from `schema.d.ts` `interface paths { ... }` keys directly. Do NOT invent paths."), replaced:
  - `_PtSessionsListGet` → `_PtSessionsItemGet` (covers the existing `/api/v1/pt-sessions/{pt_session_id}` GET read endpoint, which the plan otherwise omitted).
  - `_PtSessionsListPost` → `_PtSessionsRecordPost` (semantic rename — `/api/v1/pt-sessions` POST is "record", not "list").
  - `_PtSessionsListOkRealised` → `_PtSessionsRecordCreatedRealised` (201 anchor for the POST) + new `_PtSessionsByPackageOkRealised` (200 anchor on the by-package list path).
  - Tuple length adjusted from 35 → 36 (added the second 2xx anchor for pt-sessions module).
- **Files modified:** `packages/api-client/src/schema.contract.test.ts` (only the v1.4 pt-sessions sub-block + tuple + describe length).
- **Verification:** `pnpm --filter @sportzal/api-client typecheck` exits 0; `test` passes 10 tests (2 in `schema.contract.test.ts`, 8 in `fetcher.test.ts`); admin-web canary unchanged at 270 passed.
- **Committed in:** `bec30ea` (single bundled commit per plan commit_strategy).

**2. [Rule 3 — Blocking] Generated `apps/admin-web/src/routeTree.gen.ts` to unblock admin-web typecheck canary**
- **Found during:** D-35-18 pre-commit verification sequence (admin-web typecheck failed with TanStack Router context errors).
- **Issue:** `routeTree.gen.ts` is gitignored (`apps/admin-web/.gitignore` line 27) and auto-generated by Vite's TanStack Router plugin during dev/build. A fresh worktree has no `routeTree.gen.ts`, so `tsc -b --noEmit` fails with `Property 'queryClient' does not exist on type 'never'` errors. This is pre-existing baseline behavior (stashed-baseline verification confirmed same failure on `HEAD~0` without my changes).
- **Fix:** Ran `pnpm exec vite build` inside `apps/admin-web` to trigger the router plugin and generate `src/routeTree.gen.ts`. Build artifacts in `dist/` are gitignored.
- **Files modified:** None tracked (generated file is gitignored; `dist/` build output gitignored).
- **Verification:** After generation, `pnpm --filter sportzal-adminka typecheck` exits 0; `lint` exits 0 (with 2 pre-existing warnings, 0 errors); `test` passes 270/270.
- **Committed in:** N/A (no tracked file changes).

---

**Total deviations:** 2 auto-fixed (1 plan-template path-shape correction, 1 environment-setup unblock)
**Impact on plan:** Both deviations were essential for correctness; no scope creep. The pt-sessions deviation actually **improved** module coverage by adding the item-read GET endpoint (`/api/v1/pt-sessions/{pt_session_id}`) that the plan template would otherwise have missed, and added a second 2xx anchor (201 for record + 200 for list-by-package) instead of one. Final tuple count: 36 (vs plan's 35).

## Issues Encountered

- **Workspace pnpm filter glob:** `pnpm --filter ...` printed `No projects matched the filters "<cwd>"` warnings before each command despite running successfully. This is a known pnpm 9 behavior when the cwd is a worktree path with no project at root. Non-blocking, no action taken.

## User Setup Required

None — no external service configuration changed.

## Next Phase Readiness

- **Phase 35 complete:** Wave 1 (regen — commit `511cbf1`) + Wave 2 (forward-guard + README — commit `bec30ea`) together deliver the v1.4 backend-only handoff artifact set. The api-client is now drift-protected at compile time and self-documenting for the external design team (per 2026-05-15 pivot).
- **Phase 36 milestone verification** can proceed: regen artifacts pinned, contract tests pinning every method-level path, README pointer-style published. No frontend integration work in this repo — that lives downstream in the v2.0 milestone with the external design team.
- **No blockers.**

---
*Phase: 35-openapi-drift-gate-backend-only-api-handoff*
*Completed: 2026-05-16*

## Self-Check: PASSED

- FOUND: packages/api-client/src/schema.contract.test.ts (257 lines, +166 vs HEAD~1)
- FOUND: packages/api-client/README.md (82 lines, +25 vs HEAD~1)
- FOUND: commit bec30ea (`docs(35-02): extend forward-guard + README for v1.4 backend-only handoff`)
- VERIFIED: `git diff --exit-code apps/backend/openapi.json packages/api-client/src/schema.d.ts packages/api-client/package.json` → 0 (Wave 1 artifacts untouched)
- VERIFIED: `pnpm --filter @sportzal/api-client typecheck` → 0
- VERIFIED: `pnpm --filter @sportzal/api-client test` → 10 passed (2 describe blocks in schema.contract.test.ts)
- VERIFIED: `pnpm --filter sportzal-adminka typecheck && lint && test` → 270 passed (canary green)
- VERIFIED: No emojis in modified files (`LC_ALL=C grep -lP '[\x{1F300}-\x{1FAFF}\x{2600}-\x{27BF}]' …` → empty)
- VERIFIED: README header order correct (Usage → Codegen → v1.4 changelog → Auth quick-start → Single-flight refresh → CSRF → Phase 9 deviation note, 7 H2 sections total)
- VERIFIED: No edits outside `files_modified` (`git log --stat HEAD~1..HEAD` shows exactly 2 files changed)
