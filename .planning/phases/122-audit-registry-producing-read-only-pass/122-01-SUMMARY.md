---
phase: 122-audit-registry-producing-read-only-pass
plan: 1
subsystem: testing
tags: [audit, registry, markdown-tables, node-esm, bash, git-diff-allowlist]

requires: []
provides:
  - "Single-file v4.1 defect registry skeleton (.planning/audits/v4.1-DEFECT-REGISTRY.md) with 11-column schema legend, FUNC/HYGIENE/INFRA tables, and Discovered-during-fix section"
  - "Concurrent-write staging protocol: .planning/audits/staging/{1a-hygiene,1b-live,1c-infra}.md"
  - "tools/audit/merge-registry.mjs — idempotent, category-routed, duplicate-ID-safe merge script with --self-test"
  - "The two v4.0 HARD GATE rows (SEC-02, BAK-03) seeded into staging and merged into the registry as V41-INFRA-001/002, dispositioned deferred:operator-pending"
  - "tools/audit/.phase122-start-sha baseline + tools/audit/check-read-only.sh — proven AUD-08 read-only enforcement mechanism"
affects: [122-02, 122-03, 122-04, 122-05, 122-06]

tech-stack:
  added: []
  patterns:
    - "Category-column routing (not staging-filename routing) for concurrent-write merges"
    - "Idempotent regenerate-from-source merge (table bodies always rebuilt fresh from staging, never accumulated)"
    - "git diff --name-only <baseline-sha>..HEAD + allowlist case-pattern matching for mechanical read-only enforcement"

key-files:
  created:
    - .planning/audits/v4.1-DEFECT-REGISTRY.md
    - .planning/audits/staging/1a-hygiene.md
    - .planning/audits/staging/1b-live.md
    - .planning/audits/staging/1c-infra.md
    - .planning/audits/.phase122-start-sha
    - tools/audit/merge-registry.mjs
    - tools/audit/README.md
    - tools/audit/check-read-only.sh
  modified: []

key-decisions:
  - "Reworded the registry's schema-legend example ID (was a literal `V41-INFRA-001`) to a non-colliding pattern description after discovering it double-counted against the plan's own verify grep (Rule 1 bug fix)"
  - "Phase-start SHA (ed2f9181) re-derived from current git log as the commit immediately preceding phase 122's first plan-authoring commit — matches the plan's scouted baseline (ed2f918), confirming no drift between scout time and execution"

requirements-completed: [AUD-01, AUD-08]

coverage:
  - id: D1
    description: "v4.1-DEFECT-REGISTRY.md skeleton exists with exactly one FUNC/HYGIENE/INFRA table (11 columns each) and an empty Discovered-during-fix section"
    requirement: AUD-01
    verification:
      - kind: other
        ref: "node tools/audit/merge-registry.mjs --self-test && node tools/audit/merge-registry.mjs (run twice) && git diff --quiet -- .planning/audits/v4.1-DEFECT-REGISTRY.md"
        status: pass
    human_judgment: false
  - id: D2
    description: "Concurrent-write staging protocol: three staging files, merge routes each row by its own category column (not staging-file name), proven via --self-test fixture including a FUNC row placed in 1a-hygiene.md"
    requirement: AUD-01
    verification:
      - kind: unit
        ref: "node tools/audit/merge-registry.mjs --self-test (7 in-memory checks, all pass)"
        status: pass
    human_judgment: false
  - id: D3
    description: "Two v4.0 HARD GATE rows (SEC-02, BAK-03) flow staging -> merge -> registry as V41-INFRA-001/002, both deferred:operator-pending"
    requirement: AUD-01
    verification:
      - kind: other
        ref: "grep -c \"V41-INFRA-001\" .planning/audits/v4.1-DEFECT-REGISTRY.md == 1; grep -q \"V41-INFRA-002\""
        status: pass
    human_judgment: false
  - id: D4
    description: "AUD-08 read-only guard: .phase122-start-sha recorded, check-read-only.sh passes against the skeleton commit, proving zero app-code diffs"
    requirement: AUD-08
    verification:
      - kind: other
        ref: "bash tools/audit/check-read-only.sh (16 changed paths, all within .planning/** / tools/audit/** allowlist)"
        status: pass
    human_judgment: false

duration: 15min
completed: 2026-07-26
status: complete
---

# Phase 122 Plan 1: Registry Skeleton + Staging Protocol + Merge Script Summary

**Registry pipeline scaffold proven end-to-end: the frozen-shaped v4.1-DEFECT-REGISTRY.md skeleton, the three-file staging protocol, a category-routed idempotent merge script carrying the two v4.0 HARD GATE rows through the pipeline, and a passing AUD-08 read-only git-diff allowlist check.**

## Performance

- **Duration:** ~15 min
- **Completed:** 2026-07-26
- **Tasks:** 2 completed
- **Files modified:** 8 created (0 modified)

## Accomplishments

- Established the single-file registry contract (D-122-01/02/03): `.planning/audits/v4.1-DEFECT-REGISTRY.md` with an 11-column schema legend, three empty category tables (`## FUNC` / `## HYGIENE` / `## INFRA`), and an empty `## Discovered during fix` section.
- Implemented the concurrent-write staging protocol (D-122-04): three staging files under `.planning/audits/staging/`, each headered with its sub-pass name and primary ID prefix.
- Seeded the two v4.0 HARD GATE rows (SEC-02 off-node sealed-secrets RSA-key custody, BAK-03 verified restore round-trip) into `1c-infra.md` as `V41-INFRA-001`/`V41-INFRA-002`, per D-122-23 — permanent, `deferred:operator-pending`, never edited by v4.1.
- Built `tools/audit/merge-registry.mjs`: routes every row by its own `category` column (not by staging-file name), preserves row IDs verbatim, is idempotent (re-running twice produces byte-identical output), refuses duplicate IDs across staging files, and asserts category/section agreement on every emitted row. `--self-test` runs 7 in-memory fixture checks including the required "FUNC row placed in 1a-hygiene.md routes to `## FUNC`" case.
- Documented the staging→merge→freeze protocol in `tools/audit/README.md`.
- Recorded the phase-start baseline (`.planning/audits/.phase122-start-sha`, commit `ed2f9181...`) and implemented `tools/audit/check-read-only.sh`, which diffs that baseline against `HEAD` and asserts every changed path matches the AUD-08 allowlist (`.planning/**`, `tools/audit/**`, `apps/backend/scripts/seed_edge_cases.py` new-only). Ran it against the real skeleton commits — passed, proving the mechanism end-to-end before the three sub-passes fan out.

## Task Commits

Each task was committed atomically:

1. **Task 1: Registry skeleton + staging protocol + merge script, proven on the HARD GATE payload** - `b81d7da2` (feat)
   - Follow-up bug fix (Rule 1, discovered during tracer verification): `4f1be780` (fix) — schema-legend example ID collided with the real HARD GATE row of the same ID in the plan's own verify grep.
2. **Task 2: Record phase-start SHA and prove the AUD-08 read-only guard** - `eb4080c7` (feat)

## Files Created/Modified

- `.planning/audits/v4.1-DEFECT-REGISTRY.md` - the single frozen-shape registry skeleton (frontmatter `PENDING` until 122-06 freeze)
- `.planning/audits/staging/1a-hygiene.md` - static-hygiene sub-pass staging file (header only)
- `.planning/audits/staging/1b-live.md` - live-backend sub-pass staging file (header only)
- `.planning/audits/staging/1c-infra.md` - infra-triage sub-pass staging file; holds the two permanent HARD GATE rows
- `.planning/audits/.phase122-start-sha` - AUD-08 baseline commit SHA
- `tools/audit/merge-registry.mjs` - staging→registry merge, category-routed, idempotent, `--self-test` mode
- `tools/audit/README.md` - staging→merge→freeze protocol documentation
- `tools/audit/check-read-only.sh` - AUD-08 mechanical read-only allowlist gate (also 122-06's phase-exit gate)

## Decisions Made

- The registry's schema-legend prose originally used a literal example ID `V41-INFRA-001`, identical to the real HARD GATE row ID it also contains. This double-counted in the plan's `grep -c "V41-INFRA-001"` verify check (returned 2, not 1). Fixed by rewording the legend to describe the ID pattern abstractly instead of using a colliding literal example — no functional change to the registry contract, pure documentation-text fix (Rule 1: auto-fixed bug, committed separately as `4f1be780`).
- Phase-start SHA re-derived independently from the current git log (per plan instruction "do not hardcode the scouted value") rather than copied blindly from the plan's scouted `ed2f918` reference — confirmed to be the same commit (`ed2f9181`, "docs(state): record phase 122 context session"), the commit immediately preceding phase 122's first plan-authoring commit. No drift occurred between scout time and execution time.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Schema-legend example ID collided with real data, breaking the plan's own verify grep**
- **Found during:** Task 1 tracer feedback gate (re-running `<verify>` after the first commit, per the autonomous tracer protocol)
- **Issue:** `.planning/audits/v4.1-DEFECT-REGISTRY.md`'s schema legend used the literal example `V41-INFRA-001` in prose, identical to the real HARD GATE row's ID. `grep -c "V41-INFRA-001" .planning/audits/v4.1-DEFECT-REGISTRY.md` returned `2` (one legend mention, one real row) instead of the expected `1`, failing the task's automated verify.
- **Fix:** Reworded the legend's ID-format example to a non-literal pattern description (`V41-FUNC-`, `V41-HYG-`, `V41-INFRA-` followed by a zero-padded sequence number) instead of a concrete colliding ID.
- **Files modified:** `.planning/audits/v4.1-DEFECT-REGISTRY.md`
- **Verification:** Re-ran the full Task 1 verify chain (self-test, merge x2, idempotency diff, both grep checks) — all pass.
- **Committed in:** `4f1be780`

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Pure documentation-text correction; no change to the registry contract, merge logic, or row data. No scope creep.

## Issues Encountered

None beyond the auto-fixed issue above.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- The registry pipeline (skeleton, staging files, merge script, README) and the AUD-08 read-only guard are both proven end-to-end on a real payload — 122-02 through 122-05 (the three sub-passes) can now append rows to their respective staging files and run `node tools/audit/merge-registry.mjs` freely, in any order, with zero merge-conflict risk.
- `tools/audit/check-read-only.sh` is ready to be re-run as the authoritative phase-exit gate in 122-06.
- No blockers. The two HARD GATE rows (`V41-INFRA-001`, `V41-INFRA-002`) are permanent fixtures of the registry going forward — later plans must never edit, close, or renumber them (D-V41-K3D-SCOPE).

---
*Phase: 122-audit-registry-producing-read-only-pass*
*Completed: 2026-07-26*
