---
phase: 122-audit-registry-producing-read-only-pass
plan: 06
subsystem: testing
tags: [audit, registry, freeze, read-only-enforcement, git-diff-allowlist]

# Dependency graph
requires:
  - phase: 122-01
    provides: registry schema + staging/merge/freeze protocol (tools/audit/merge-registry.mjs, tools/audit/check-read-only.sh, .planning/audits/.phase122-start-sha)
  - phase: 122-02
    provides: 1a-hygiene.md staging rows (72 HYGIENE + 8 FUNC reachability rows)
  - phase: 122-04
    provides: 1c-infra.md staging rows (2 HARD GATE rows + 28 k3d-scope/hardware-gated triage rows)
  - phase: 122-05
    provides: 1b-live.md staging rows (26 FUNC Zod-wire coverage rows + 2 deferred:blocked live-run rows)
provides:
  - The single, frozen v4.1 defect registry (.planning/audits/v4.1-DEFECT-REGISTRY.md, 136 rows: FUNC=34, HYGIENE=72, INFRA=30)
  - Mechanical AUD-08 read-only proof (check-read-only.sh PASSED against the phase-start SHA)
  - A bugfix to merge-registry.mjs (escaped-pipe handling) that any future milestone reusing this tool inherits
affects: [123-test-infra-unblock, 124-func-fixes, 125-hygiene-fixes, 126-infra-fixes, 127-registry-consolidation]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Two-commit freeze stamp: the substantive freeze commit (merge + staging deletion + frozen_at/row_count_at_freeze) cannot embed its own resulting SHA in frozen_at_commit (circular hash dependency); a tiny immediate follow-up commit records that SHA"
    - "Markdown table splitter must respect backslash-escaped pipes (\\|) inside cells — naive split(‘|’) breaks any repro/evidence cell containing a literal shell pipe"

key-files:
  created: []
  modified:
    - tools/audit/merge-registry.mjs
    - .planning/audits/v4.1-DEFECT-REGISTRY.md
  deleted:
    - .planning/audits/staging/1a-hygiene.md
    - .planning/audits/staging/1b-live.md
    - .planning/audits/staging/1c-infra.md

key-decisions:
  - "Freeze approved by user via orchestrator before this plan ran (checkpoint:decision pre-confirmed) — AUD-05 (runtime Zod-wire divergence) and AUD-06 (browser UAT walk) recorded as deferred:blocked rows (V41-FUNC-033/034) rather than fabricated live-run results, since the local backend's seed owner credentials were permission-protected this session."
  - "frozen_at_commit stamping requires two commits (2ce5da33 substantive freeze, f02f9c68 SHA stamp) because a commit cannot contain its own post-commit hash — documented as a mechanical necessity, not a scope deviation."
  - "AUD-05/AUD-06 stay unchecked in REQUIREMENTS.md per phase-specific instruction — their live layers are the two deferred:blocked rows in the now-frozen registry, to be picked up by a future seeded re-run."

requirements-completed: [AUD-01, AUD-08]

coverage:
  - id: D1
    description: "Merge the three staging files into the single frozen v4.1-DEFECT-REGISTRY.md (136 rows: FUNC=34, HYGIENE=72, INFRA=30), header stamped frozen_at_commit/frozen_at/row_count_at_freeze, staging files deleted, HARD GATE rows byte-identical, deferred count nonzero (40)"
    requirement: "AUD-01"
    verification:
      - kind: other
        ref: "node tools/audit/merge-registry.mjs --self-test (7/7 checks pass) + node tools/audit/merge-registry.mjs (wrote 136 rows) + re-run byte-identical diff (idempotency) + diff of V41-INFRA-001/002 against staging source (byte-identical)"
        status: pass
    human_judgment: false
  - id: D2
    description: "AUD-08 mechanical read-only enforcement: git diff --name-only <phase-start-sha>..HEAD, all 34 changed paths within the allowlist (.planning/**, tools/audit/** new, apps/backend/scripts/seed_edge_cases.py new-only)"
    requirement: "AUD-08"
    verification:
      - kind: other
        ref: "bash tools/audit/check-read-only.sh (exit 0, PASSED) + git diff --name-only ed2f918..HEAD filtered against the allowlist regex (empty result)"
        status: pass
    human_judgment: false

# Metrics
duration: 25min
completed: 2026-07-26
status: complete
---

# Phase 122 Plan 6: Merge + Freeze Registry + AUD-08 Read-Only Enforcement Summary

**Merged all three audit sub-pass staging files into the single frozen v4.1-DEFECT-REGISTRY.md (136 rows), fixed an escaped-pipe parsing bug in merge-registry.mjs discovered during the merge, and ran the authoritative AUD-08 git-diff allowlist check (PASSED, zero app-code edits across the entire phase).**

## Performance

- **Duration:** ~25 min
- **Started:** 2026-07-26T14:28:00Z (approx, session start)
- **Completed:** 2026-07-26T14:52:34Z
- **Tasks:** 2 (checkpoint:decision pre-approved by orchestrator; Task 1 merge+freeze; Task 2 read-only enforcement)
- **Files modified:** 5 (2 modified, 3 deleted)

## Accomplishments
- Merged `staging/{1a-hygiene,1b-live,1c-infra}.md` into `.planning/audits/v4.1-DEFECT-REGISTRY.md` via `merge-registry.mjs`, routing every row by its own `category` column: **FUNC=34, HYGIENE=72, INFRA=30 → 136 total rows**
- Fixed a real bug in `merge-registry.mjs`'s `splitRow()`: it split on every literal `|`, which corrupted three INFRA rows (`V41-INFRA-007/018/023`) whose `repro` cells legitimately contain backslash-escaped shell pipes (`\|`). Now splits only on unescaped pipes via a negative-lookbehind regex.
- Verified merge idempotency: re-running `merge-registry.mjs` against unchanged staging input produced a byte-identical registry file.
- Verified the two v4.0 HARD GATE rows (`V41-INFRA-001` SEC-02, `V41-INFRA-002` BAK-03) are byte-identical between the staging source and the frozen registry (D-122-23 — never edited).
- Stamped the freeze header: `frozen_at: 2026-07-26T14:51:05Z`, `row_count_at_freeze: 136`, `frozen_at_commit: 2ce5da33dbfd2fdd652f011e1cb5e9411c017d8c` (recorded in a small follow-up commit — see Deviations).
- Deleted the three staging files in the freeze commit (D-122-04/D-122-05).
- Asserted the CLOSE-04 honesty invariant: **40 rows carry a `deferred` disposition** (28 `deferred:accepted-risk` + 2 `deferred:blocked` + 10 `deferred:operator-pending`) — nonzero, as required.
- Ran the authoritative AUD-08 read-only enforcement (`tools/audit/check-read-only.sh`): **PASSED**, 34 changed paths since the phase-start SHA, all within the allowlist; zero modifications to any existing file under `apps/`, `packages/`, or `infra/`.

## Task Commits

Each task was committed atomically:

1. **Task 1: Merge staging into registry + freeze (part 1 — substantive)** - `2ce5da33` (feat) — merge bugfix, merged+frozen registry (frozen_at/row_count_at_freeze stamped), staging files deleted
2. **Task 1: Merge staging into registry + freeze (part 2 — SHA stamp)** - `f02f9c68` (docs) — records `2ce5da33` as `frozen_at_commit` (unavoidable two-commit split — a commit cannot embed its own resulting hash)
3. **Task 2: AUD-08 read-only enforcement** - verification-only, no code changes; evidence captured below

**Plan metadata:** (this SUMMARY's own commit, made immediately after this file)

## Files Created/Modified
- `tools/audit/merge-registry.mjs` - Fixed `splitRow()` to split only on unescaped `|` (negative-lookbehind regex), preserving `\|` inside repro/evidence cells as literal content
- `.planning/audits/v4.1-DEFECT-REGISTRY.md` - Merged all 136 rows (FUNC/HYGIENE/INFRA), header frozen (`frozen_at_commit`/`frozen_at`/`row_count_at_freeze`)
- `.planning/audits/staging/1a-hygiene.md` (deleted) - merged and removed per D-122-04/D-122-05
- `.planning/audits/staging/1b-live.md` (deleted) - merged and removed per D-122-04/D-122-05
- `.planning/audits/staging/1c-infra.md` (deleted) - merged and removed per D-122-04/D-122-05

## Decisions Made
- **Freeze approved pre-session** via the orchestrator's `<freeze_is_user_approved>` directive; the plan's `checkpoint:decision` gate was treated as answered "freeze" and execution proceeded straight through without pausing.
- **AUD-05/AUD-06 stay `[ ]` Pending** in REQUIREMENTS.md — their live layers are the `deferred:blocked` rows `V41-FUNC-033`/`V41-FUNC-034` in the frozen registry (backend up, seed owner creds permission-protected this session); a future seeded re-run resolves them without reopening the freeze.
- **Two-commit freeze stamp** — `frozen_at_commit` cannot equal the hash of the commit that writes it (circular dependency: the hash is computed over a tree that would need to already contain the hash). Resolved with `2ce5da33` (the substantive freeze: merge, frozen_at/row_count_at_freeze, staging deletion) followed immediately by `f02f9c68` (a metadata-only commit recording `2ce5da33` as `frozen_at_commit`). This is a mechanical necessity of the freeze design, not a scope or honesty deviation — no registry row content changed in the second commit.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed escaped-pipe parsing bug in merge-registry.mjs**
- **Found during:** Task 1 (running the real merge for the first time against the completed 1c-infra.md staging rows)
- **Issue:** `splitRow()` split every table line on every literal `|` character, including backslash-escaped pipes (`\|`) that are the standard markdown-table escape for a literal pipe inside a cell. Three INFRA rows (`V41-INFRA-007`, `V41-INFRA-018`, `V41-INFRA-023`) have `repro` cells containing shell one-liners with `\|` (e.g. `` `helm template ... \| kubectl apply --dry-run=client -f -` ``), which broke the 11-column parse and made the merge fail entirely (`Error: row does not have 11 columns (got 12)`).
- **Fix:** Changed the split regex from `.split('|')` to `.split(/(?<!\\)\|/)` — a negative-lookbehind that only splits on pipes not preceded by a backslash, leaving `\|` intact as cell content (which remains valid markdown when the row is re-serialized).
- **Files modified:** `tools/audit/merge-registry.mjs`
- **Verification:** `--self-test` still passes (7/7 checks); the real merge now succeeds and writes 136 rows; re-running produces a byte-identical registry (idempotency preserved); the three previously-broken rows now parse and land correctly under `## INFRA`.
- **Committed in:** `2ce5da33` (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 bug fix in shared tooling)
**Impact on plan:** Necessary to complete the merge at all — without the fix, `merge-registry.mjs` could not process the real 1c-infra.md staging data. No scope creep; the fix is confined to the merge tool's parsing logic and does not touch registry content or application code.

## Issues Encountered
None beyond the auto-fixed parsing bug above.

## User Setup Required
None - no external service configuration required.

## Success-Criterion-7 Evidence (AUD-08 read-only enforcement)

```
$ bash tools/audit/check-read-only.sh
AUD-08 read-only check PASSED — 34 path(s) changed since ed2f91815e35d3969ba1cad3ea1eb7e74d09303e, all within the allowlist.
$ echo $?
0
```

Full `git diff --name-status ed2f91815e35d3969ba1cad3ea1eb7e74d09303e..HEAD` (34 paths, all `.planning/**`, `tools/audit/**`, or the one sanctioned new file):

```
M	.planning/REQUIREMENTS.md
M	.planning/ROADMAP.md
M	.planning/STATE.md
A	.planning/audits/.phase122-start-sha
A	.planning/audits/v4.1-DEFECT-REGISTRY.md
A	.planning/audits/v4.1-EDGE-SEED-MATRIX.md
A	.planning/audits/v4.1-HYGIENE-RAW/deptry.txt
A	.planning/audits/v4.1-HYGIENE-RAW/eslint-admin.txt
A	.planning/audits/v4.1-HYGIENE-RAW/import-linter.txt
A	.planning/audits/v4.1-HYGIENE-RAW/jscpd.txt
A	.planning/audits/v4.1-HYGIENE-RAW/knip.txt
A	.planning/audits/v4.1-HYGIENE-RAW/markers.txt
A	.planning/audits/v4.1-HYGIENE-RAW/vulture.txt
A	.planning/audits/v4.1-REACHABILITY-MANIFEST.md
A	.planning/audits/v4.1-ZOD-WIRE-MANIFEST.json
A	.planning/audits/v4.1-ZOD-WIRE-MANIFEST.md
M	.planning/config.json
A	.planning/phases/122-audit-registry-producing-read-only-pass/122-01-PLAN.md
A	.planning/phases/122-audit-registry-producing-read-only-pass/122-01-SUMMARY.md
A	.planning/phases/122-audit-registry-producing-read-only-pass/122-02-PLAN.md
A	.planning/phases/122-audit-registry-producing-read-only-pass/122-02-SUMMARY.md
A	.planning/phases/122-audit-registry-producing-read-only-pass/122-03-PLAN.md
A	.planning/phases/122-audit-registry-producing-read-only-pass/122-03-SUMMARY.md
A	.planning/phases/122-audit-registry-producing-read-only-pass/122-04-PLAN.md
A	.planning/phases/122-audit-registry-producing-read-only-pass/122-04-SUMMARY.md
A	.planning/phases/122-audit-registry-producing-read-only-pass/122-05-PLAN.md
A	.planning/phases/122-audit-registry-producing-read-only-pass/122-05-SUMMARY.md
A	.planning/phases/122-audit-registry-producing-read-only-pass/122-06-PLAN.md
A	apps/backend/scripts/seed_edge_cases.py
A	tools/audit/README.md
A	tools/audit/check-read-only.sh
A	tools/audit/merge-registry.mjs
A	tools/audit/reachability-manifest.mjs
A	tools/audit/zod-wire-manifest.mjs
```

Note: this diff is against `ed2f918` (the phase-start SHA), so it also includes the staging-file additions/deletions net-summed away by later commits within the phase (the staging files were added in 122-01/02/04/05 and deleted in this plan's freeze commit, so they no longer appear as a diff against phase-start — only the final registry file does). `apps/backend/scripts/seed_edge_cases.py` shows status `A` (new file only), satisfying the "new file only" allowlist condition. No existing file under `apps/`, `packages/`, or `infra/` was modified.

## Next Phase Readiness
- The frozen registry (`.planning/audits/v4.1-DEFECT-REGISTRY.md`, 136 rows) is the authoritative hand-off to Phases 123-127. All rows carry `owning_phase`; `locked_invariant_risk: yes` rows are flagged for first-in-phase handling.
- AUD-05/AUD-06 remain formally incomplete (deferred:blocked rows `V41-FUNC-033`/`034`) — a future seeded backend session should re-run the live Zod-wire divergence capture and the chrome-devtools browser UAT walk, then flip those two rows' disposition without reopening the freeze (append findings only, per D-122-05).
- Phase 122 is complete. Phase 123 (Test-Infra Unblock) can begin.

## Self-Check: PASSED

- FOUND: `.planning/phases/122-audit-registry-producing-read-only-pass/122-06-SUMMARY.md`
- FOUND: `tools/audit/merge-registry.mjs`
- FOUND: `.planning/audits/v4.1-DEFECT-REGISTRY.md`
- CONFIRMED ABSENT: `.planning/audits/staging/1a-hygiene.md`
- CONFIRMED ABSENT: `.planning/audits/staging/1b-live.md`
- CONFIRMED ABSENT: `.planning/audits/staging/1c-infra.md`
- FOUND commit: `2ce5da33`
- FOUND commit: `f02f9c68`

---
*Phase: 122-audit-registry-producing-read-only-pass*
*Completed: 2026-07-26*
