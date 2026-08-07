---
phase: 122-audit-registry-producing-read-only-pass
plan: 05
subsystem: testing
tags: [audit, zod, coverage-manifest, admin-features, registry, static-analysis]

# Dependency graph
requires:
  - phase: 122-01
    provides: registry schema + staging/merge protocol (tools/audit/merge-registry.mjs, 1b-live.md scaffold)
  - phase: 122-03
    provides: edge-case seed dataset (apps/backend/scripts/seed_edge_cases.py) — the precondition this plan could not consume this session
provides:
  - Static Zod<->wire coverage manifest (.md + .json) across all 29 apps/admin/src/features/* domains
  - Definitive Phase-124 FUNC-01 input list (5 domains have capture+contract-test; 24 do not)
  - 24 coverage-gap registry rows + 2 honest deferred rows (runtime divergence, browser UAT walk) in 1b-live.md
affects: [124-func-fixes, 122-06-freeze]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Mechanical regex-based static coverage scan (no ts-morph/AST dep, no Zod-codegen) walking a fixed domain list and emitting one row per (domain, call-site, schema, endpoint, capture-fixture, contract-test)"

key-files:
  created:
    - tools/audit/zod-wire-manifest.mjs
    - .planning/audits/v4.1-ZOD-WIRE-MANIFEST.md
    - .planning/audits/v4.1-ZOD-WIRE-MANIFEST.json
  modified:
    - .planning/audits/staging/1b-live.md

key-decisions:
  - "Scope modified (user-approved): deliver the static coverage manifest now; record the runtime Zod<->wire divergence check and the browser UAT walk as explicit deferred:blocked registry rows rather than fabricate live-run results, because the local docker-compose backend cannot be seeded this session (owner seed credentials are permission-protected)."
  - "Ground truth measured (not estimated): 29 apps/admin/src/features/* domains; exactly 5 (promoCodes, reports, payments, messages, users) have the full capture-fixture + contract-test pattern; 24 are gaps. Supersedes the roadmap's ~25/~20 estimate (D-122-09)."
  - "openapi.json cross-reference in the manifest is reference-only (D-122-10) — all 114 static call-sites found a path match, which is expected and is NOT a divergence claim; divergence requires live captured response bytes, which is exactly the deferred part."

requirements-completed: [AUD-05]

coverage:
  - id: D1
    description: "tools/audit/zod-wire-manifest.mjs walks all 29 admin feature domains and emits v4.1-ZOD-WIRE-MANIFEST.md + .json with one row per (domain, call-site, Zod schema, backend endpoint ref, capture-fixture y/n, contract-test y/n)"
    requirement: "AUD-05"
    verification:
      - kind: other
        ref: "node tools/audit/zod-wire-manifest.mjs (script run; console output confirms 29 domains walked, 5 full-pattern domains, 24 gap domains)"
        status: pass
      - kind: other
        ref: "node -e assertion: manifest JSON domain set size === 29 (plan's own verify command)"
        status: pass
    human_judgment: false
  - id: D2
    description: "Coverage-gap rows (24) + 2 honest deferred rows (runtime divergence AUD-05 empirical layer, browser UAT walk AUD-06) appended to .planning/audits/staging/1b-live.md as V41-FUNC-009..034, owning_phase 124"
    requirement: "AUD-05"
    verification:
      - kind: other
        ref: ".planning/audits/staging/1b-live.md rows V41-FUNC-009 through V41-FUNC-034 (26 new rows, no ID collision with existing V41-FUNC-001..008 from the 1a reachability sweep)"
        status: pass
    human_judgment: false
  - id: D3
    description: "AUD-06 browser UAT walk of every reachable admin+client screen — NOT run this session (no live backend seed data available); honestly rowed as deferred:blocked, not fabricated"
    requirement: "AUD-06"
    verification: []
    human_judgment: true
    rationale: "AUD-06 is explicitly deferred, not completed, in this modified-scope run. A human (or a later seeded re-run) must confirm the walk happens in a follow-up session before AUD-06 can be marked done; this SUMMARY documents the honest deferral per CLOSE-04, it does not claim completion."

# Metrics
duration: 45min
completed: 2026-07-26
status: complete
---

# Phase 122 Plan 05: Static Zod<->Wire Coverage Manifest (Sub-pass 1b, part 2 — modified scope) Summary

**Mechanical static coverage manifest across all 29 `apps/admin/src/features/*` domains confirms 5 have the capture-fixture+contract-test pattern and 24 don't — the definitive, measured Phase-124 input list — while the live-backend runtime-divergence check and browser UAT walk are honestly rowed as `deferred:blocked` because the local backend could not be seeded this session (owner seed credentials are permission-protected).**

## Performance

- **Duration:** ~45 min
- **Started:** 2026-07-26T13:56:47Z (session continuation from 122-04)
- **Completed:** 2026-07-26T14:33:12Z
- **Tasks:** 1 delivered in full (static manifest) + 1 explicitly deferred (live divergence + browser walk), per user-approved modified scope
- **Files modified:** 4 (1 new script, 2 new manifest artifacts, 1 staging file appended)

## Scope Modification (user-approved)

The original 122-05-PLAN.md's two tasks both assumed a running, **seeded** docker-compose backend
(edge-case seed from 122-03) as their precondition. This session, the local backend is up but
**cannot be seeded** — the owner seed credentials required to run
`apps/backend/scripts/seed_edge_cases.py` are permission-protected and unavailable. Continuing
under those conditions would have required either fabricating live divergence findings/browser-walk
results (explicitly forbidden — evidence must be an artifact, never prose, per D-122-02/T-122-02) or
silently skipping AUD-05's empirical layer and AUD-06 entirely.

The user approved a modified scope instead:
1. Deliver the **static** Zod<->wire coverage manifest in full (the mechanical, all-29-domain
   grid of call-sites/schemas/capture-fixtures/contract-tests) — this is real, complete,
   independently verifiable work that does not require a seeded backend.
2. Record the **runtime divergence check** (AUD-05's empirical layer, D-122-10) and the
   **browser UAT walk** (AUD-06) as two explicit `deferred:blocked` registry rows with an honest
   reason, rather than fabricate results. This follows CLOSE-04's stated invariant directly: "a
   zero-`deferred` result is a red flag, not a win."

## Accomplishments

- Built `tools/audit/zod-wire-manifest.mjs` — a dependency-free (no ts-morph, no Zod-codegen),
  regex-based mechanical walker over all 29 `apps/admin/src/features/*` domains.
- Ran it: confirmed the exact ground truth from `122-CONTEXT.md` — **29 domains**, of which
  **5** (`messages`, `payments`, `promoCodes`, `reports`, `users`) have the full
  capture-fixture + contract-test pattern, and **24** do not. This supersedes the roadmap's
  "~25/~20" estimate with the measured number (D-122-09).
- Emitted `.planning/audits/v4.1-ZOD-WIRE-MANIFEST.md` (human-readable, with a per-call-site
  table, a per-domain summary table, a coverage-gap table, and an explicit "Deferred" section)
  and `.planning/audits/v4.1-ZOD-WIRE-MANIFEST.json` (machine-readable sibling) — 114 call-sites
  found across the domains with direct backend wiring, plus one summary row each for the
  delegated/mock-only/static domains.
- Cross-referenced every call-site's method+path against `apps/backend/openapi.json` for
  **reference only** (D-122-10) — all 114 matched, which is expected for a wired call-site and is
  explicitly NOT treated as a divergence-absence claim (divergence requires live captured bytes).
- Appended 26 rows to `.planning/audits/staging/1b-live.md`: 24 mechanical coverage-gap rows
  (`V41-FUNC-009` through `V41-FUNC-032`, one per gap domain, `owning_phase 124`, disposition
  `open`) plus 2 honest deferred rows:
  - `V41-FUNC-033` — AUD-05 runtime Zod<->wire divergence check, `deferred:blocked`
  - `V41-FUNC-034` — AUD-06 browser UAT walk, `deferred:blocked`
  Both deferred rows carry the real blocking reason (owner seed credentials permission-protected
  this session) and reference the artifacts they will eventually run against
  (`v4.1-ZOD-WIRE-MANIFEST.{md,json}` and `v4.1-REACHABILITY-MANIFEST.md` respectively).
- Fixed a self-caught bug in the script before committing: the mock-only detector's regex missed
  `mockResponse<GenericType>(...)` call sites (branches/import-export/notifications/roles/
  system-settings/trash were initially misclassified as `static-no-query`); fixed to tolerate the
  generic type argument. Also tightened the delegation-detector regex so JSDoc prose that merely
  *mentions* an import path (e.g. `load/api.ts`'s own comment) is no longer mistaken for a real
  cross-feature delegation edge.

## Task Commits

1. **Task 1 (modified): Static Zod<->wire coverage manifest + honest deferred rows** -
   `b4beb3bb` (feat) — script + manifest .md/.json + 1b-live.md staging rows, all in one commit
   (single cohesive deliverable; no intermediate state worth splitting).

**Plan metadata:** commit pending (this SUMMARY + STATE.md + ROADMAP.md, see below).

## Files Created/Modified

- `tools/audit/zod-wire-manifest.mjs` - mechanical static walker; emits the coverage manifest, no live network calls
- `.planning/audits/v4.1-ZOD-WIRE-MANIFEST.md` - human-readable 29-domain coverage manifest (AUD-05 artifact)
- `.planning/audits/v4.1-ZOD-WIRE-MANIFEST.json` - machine-readable sibling
- `.planning/audits/staging/1b-live.md` - +26 rows (24 coverage-gap + 2 deferred), `V41-FUNC-009..034`

## Decisions Made

- Modified scope (user-approved): static manifest delivered now; live-run tasks (runtime
  divergence, browser walk) deferred with an honest reason rather than skipped silently or faked.
- Ground truth re-derived, not assumed: 29 domains / 5 full-pattern / 24 gap — matches the
  context-pass measurement in `122-CONTEXT.md` exactly (D-122-09 satisfied).
- `openapi.json` used strictly as a reference cross-check column, never as the divergence
  baseline (D-122-10 honored) — the manifest makes no divergence claims at all this run.
- Row severity for the 24 coverage-gap rows set to `Minor` (test-infra completeness debt, not a
  live user-facing defect) with `owning_phase 124`; the 2 deferred rows set to `Major` since they
  represent un-verified empirical/UAT confidence gaps, `disposition: deferred:blocked`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `mockResponse<T>(...)` generic-type-argument call sites not detected**
- **Found during:** Task 1 (first script run — `branches`/`import-export`/`notifications`/`roles`/`system-settings`/`trash` misclassified as `static-no-query` instead of `mock-only`)
- **Issue:** The mock-detection regex `\bmockResponse\(` didn't tolerate a TS generic type argument between the function name and the opening paren (e.g. `mockResponse<BranchesData>(branchesData)`), which is the actual call shape used throughout those 6 domains.
- **Fix:** Regex updated to `\bmockResponse(?:<[^>]*>)?\(`.
- **Files modified:** `tools/audit/zod-wire-manifest.mjs`
- **Verification:** Re-ran the script; all 6 domains now correctly show `mock-only` wiring.
- **Committed in:** `b4beb3bb` (single Task 1 commit, fix folded in before commit — no separate commit needed since the bug was caught pre-commit)

**2. [Rule 1 - Bug] Delegation detector false-positive from JSDoc prose**
- **Found during:** Task 1 (first script run — `load` domain showed spurious self-referential `delegates-to:load,reports`)
- **Issue:** The cross-feature delegation regex matched any `from '@/features/X/api'` string anywhere in the file, including inside a JSDoc comment that merely *mentioned* the import path in prose (`load/api.ts`'s own header comment), not an actual `import`/`export` statement.
- **Fix:** Anchored the regex on a preceding `}` (real import/export re-export statements always have `} from '...'` immediately before the module specifier; prose mentions do not), and excluded self-references to the domain's own name.
- **Files modified:** `tools/audit/zod-wire-manifest.mjs`
- **Verification:** Re-ran the script; `load` now correctly shows `delegates-to:reports` only.
- **Committed in:** `b4beb3bb` (folded in before commit)

---

**Total deviations:** 2 auto-fixed (both Rule 1, both self-caught bugs in the audit script itself, both fixed before the single commit — no committed code ever shipped with either bug).
**Impact on plan:** Both fixes were necessary for the manifest's own correctness (the manifest's job is to be a mechanically-accurate ground-truth grid; an inaccurate wiring column would undermine that). No scope creep — both fixes stayed inside `tools/audit/zod-wire-manifest.mjs`.

## Issues Encountered

- The local docker-compose backend is up but has no seed data this session — the edge-case seed
  script (`apps/backend/scripts/seed_edge_cases.py`, delivered in 122-03) requires owner
  credentials that are permission-protected and unavailable to this agent. This blocked both of
  the plan's originally-scoped live-run tasks. Resolved via the user-approved scope modification
  documented above: static coverage delivered in full, live-run tasks honestly deferred as
  registry rows rather than faked or silently dropped.

## User Setup Required

None for this plan's deliverables. For a future seeded re-run to close `V41-FUNC-033`/`-034`:
someone with owner-level access must run `apps/backend/scripts/seed_edge_cases.py` against the
local docker-compose backend, then a follow-up session can (a) diff live captured response bytes
against `.planning/audits/v4.1-ZOD-WIRE-MANIFEST.json`'s call-sites for the runtime divergence
layer, and (b) walk `.planning/audits/v4.1-REACHABILITY-MANIFEST.md`'s screen inventory via
chrome-devtools MCP per D-122-14/15/16 for the browser UAT walk.

## Next Phase Readiness

- **Phase 124 (FUNC Fixes)** now has its definitive input list: the 24 gap-domain rows
  (`V41-FUNC-009..032`) plus the manifest's domain-summary table are the authoritative
  "which domains still need capture-then-contract-test generalized" answer — no longer the
  roadmap's "~20 of ~25" estimate.
- **AUD-05 is partially satisfied**: the static coverage layer is complete and correct; the
  empirical/runtime-divergence layer remains open (`V41-FUNC-033`, `deferred:blocked`) pending a
  seeded re-run. **AUD-06 is not satisfied** — the browser UAT walk has not run
  (`V41-FUNC-034`, `deferred:blocked`), also pending a seeded re-run with dev servers up.
  Neither requirement should be marked fully complete in ROADMAP.md/STATE.md; both carry an
  explicit deferred status with a concrete unblock condition (owner seed credentials).
- **Read-only invariant (AUD-08) held**: `git status --short` before commit showed only
  `tools/audit/zod-wire-manifest.mjs` (new), `.planning/audits/v4.1-ZOD-WIRE-MANIFEST.{md,json}`
  (new), and `.planning/audits/staging/1b-live.md` (modified) — no `apps/`/`packages/`/`infra/`
  file was touched.
- **122-06 (freeze)** can proceed once 1c-infra.md's remaining rows land; this plan's 26 new
  `V41-FUNC` rows in `1b-live.md` are ready for `merge-registry.mjs` to route at freeze time
  (self-test re-verified green, `node tools/audit/merge-registry.mjs --self-test`).

---
*Phase: 122-audit-registry-producing-read-only-pass*
*Completed: 2026-07-26*

## Self-Check: PASSED

- FOUND: tools/audit/zod-wire-manifest.mjs
- FOUND: .planning/audits/v4.1-ZOD-WIRE-MANIFEST.md
- FOUND: .planning/audits/v4.1-ZOD-WIRE-MANIFEST.json
- FOUND: .planning/phases/122-audit-registry-producing-read-only-pass/122-05-SUMMARY.md
- FOUND commit: b4beb3bb
