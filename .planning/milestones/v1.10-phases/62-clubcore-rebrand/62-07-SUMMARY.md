---
phase: 62-clubcore-rebrand
plan: 07
subsystem: infra
tags: [smoke-tests, ci-gates, openapi, import-linter, pytest, vitest, rebrand-verification]

requires:
  - phase: 62-clubcore-rebrand
    provides: All plans 62-01..62-06 merged (package + workspace rename, code refs, localStorage migrator, Redis prefix rename, db-rename runbook, docs forward-only rewrite)
provides:
  - 12-gate smoke evidence capture for Phase 62 closing-out
  - Surfaced regressions for gap-closure (G7-E openapi drift, G7-H 2 npm-scope misses)
affects: [milestone-v1.10-close, phase-67-cleanup-RUN-07]

tech-stack:
  added: []
  patterns:
    - "Smoke-gate evidence file = single source of truth for phase-complete; verbatim command output + classification table per gate."

key-files:
  created:
    - .planning/phases/62-clubcore-rebrand/62-07-SMOKE-EVIDENCE.md
  modified: []

key-decisions:
  - "Surface 2 gate failures instead of silently fixing — per executor scope-boundary rule and plan G7-H/E acceptance criteria. Gap-closure plan should fix in a tiny follow-up."
  - "G7-E byte-stability invariant separated from G7-E drift-vs-HEAD invariant. Regen IS byte-stable (identical output across 3 runs) but committed openapi.json is stale by 2 lines because no 62-0X plan included openapi regen task after the sz:→cc: idempotency-prefix rename."
  - "G7-H matches classified by intent: 14/16 are deliberately retained sportzal.local test-domain placeholders per D-62-03 (CLAUDE.md keeps sportzal.ru/.local domain); 2 are genuine npm-scope misses (api-client JSDoc + eslint fixture message)."
  - "Used pnpm filter name clubcore-adminka (the actual workspace name) instead of plan-text's admin-web filter, since the package was renamed in 62-01."

patterns-established:
  - "Evidence file structure: per-gate section (criterion / verbatim command / exit code / summary line / verdict) + overall verdict table — keeps gap-closure mode unambiguous about what failed and why."
  - "Worktree bootstrap: copy gitignored apps/backend/.env from main checkout; run vite build once to regenerate gitignored src/routeTree.gen.ts; pnpm install to populate node_modules."

requirements-completed: [REB-08]

duration: 11min
completed: 2026-05-26
---

# Phase 62 Plan 07: G-7 Final Smoke Gauntlet — Summary

**Phase 62 smoke gauntlet executed end-to-end: 10 of 12 gates PASSED, 2 gates surfaced regressions traceable to upstream plans 62-01 / 62-04 — gap-closure required before v1.10 milestone-close.**

## Performance

- **Duration:** 11 min (~654s)
- **Started:** 2026-05-26T11:51:11Z
- **Completed:** 2026-05-26T12:02:05Z
- **Tasks:** 1 (single composite smoke task)
- **Files modified:** 0 (per plan design — only evidence file created)
- **Files created:** 1 (`62-07-SMOKE-EVIDENCE.md`, 372 lines)

## Accomplishments

- Captured verbatim stdout + exit codes + summary lines for all 12 Phase 62 smoke gates (G7-A through G7-L) into a 372-line evidence file.
- Validated backend pytest baseline holds (**2185 passed / 6 skipped**, 4 above the v1.9 baseline of 2181).
- Validated frontend test suite holds (**282 passed / 0 failed** in admin-web, **16 passed** in api-client).
- Validated architectural contracts holds (**import-linter: 3 kept, 0 broken**).
- Validated Phase 62 trust invariants: RBAC parity files unchanged (`G7-G` clean diff), Redis `sz:` prefix fully migrated to `cc:` (`G7-I` 0 matches), Phase 67 shim sites all annotated (`G7-J` 4 matches).
- Identified two real residue/drift defects from upstream plans and documented gap-closure recommendations.

## Gate result table (12 gates)

| Gate | Acceptance criterion | Status |
|------|----------------------|--------|
| G7-A | backend pytest ≥ 2181 passed / ≤ 6 skipped | PASSED (2185/6) |
| G7-B | @clubcore/api-client typecheck + test exit 0 | PASSED (16 tests) |
| G7-C | clubcore-adminka typecheck + lint + test exit 0 | PASSED (282 tests, 0 lint errors) |
| G7-D | lint-imports 3 kept / 0 broken | PASSED |
| G7-E | openapi regen drift-gate clean vs HEAD | **FAIL** (2-line drift; regen IS byte-stable) |
| G7-F | docker compose config exit 0 | PASSED |
| G7-G | RBAC parity files unchanged | PASSED |
| G7-H | zero @sportzal in active code | **FAIL** (2 real misses; 14 intentional per D-62-03) |
| G7-I | zero sz: Redis prefix in active backend | PASSED |
| G7-J | ≥ 3 Phase 67 / RUN-07 shim annotations | PASSED (4) |
| G7-K | HISTORICAL_NOTE.md exists | PASSED |
| G7-L | clubcore-db-rename-runbook.md exists | PASSED |

## Task Commits

1. **Task 1: Run full smoke gauntlet and capture evidence** — `263dd182` (docs)

(Single-task plan, no per-step breakdown.)

## Files Created/Modified

- **Created:** `.planning/phases/62-clubcore-rebrand/62-07-SMOKE-EVIDENCE.md` — 372 lines; per-gate verbatim command + exit + summary; root-cause analysis for the two FAIL verdicts; gap-closure recommendations.
- **Modified:** none (evidence-only plan per design; T-62-07-01 mitigation enforced).

Confirmed by `git diff HEAD~1` showing only the evidence file as `create mode 100644`. No source files, no docs/, no STATE.md, no ROADMAP.md modifications by this plan (orchestrator owns those writes per spawn contract).

## Decisions Made

- **Surfaced FAIL instead of self-healing:** Plan G7-H Step (per `<action>` block) reads: "any residual match means a downstream plan (G-2..G-6) missed something. The plan FAILS — do NOT silently fix; report and let gap-closure handle it." Honored verbatim — both G7-E drift and G7-H residue were captured with full diff context and recommended fix steps, NOT auto-applied.
- **Decoupled G7-E byte-stability from G7-E drift-vs-HEAD:** Per plan action rule "if the second pair still shows diffs, the regen is not byte-stable and the gate FAILS" — regen IS byte-stable (3 consecutive runs produce identical output), so the byte-stability sub-invariant holds. But the literal `git diff --exit-code` is non-zero, so the strict drift-gate sub-invariant fails. Recorded as PARTIAL FAIL with both sub-results documented.
- **Used correct workspace package names (`clubcore-adminka`, `@clubcore/api-client`):** Plan text said `pnpm --filter admin-web` but the actual `package.json:name` is `clubcore-adminka` (renamed in 62-01). The orchestrator's context override (which provided the correct names) was used; this naming mismatch in the plan text itself is noted in Deviations.

## Deviations from Plan

### Plan-text vs Workspace-reality mismatch (executable-fidelity)

**1. [Rule 1 - Plan-text bug] Plan G7-C uses `pnpm --filter admin-web`, but workspace name is `clubcore-adminka`**
- **Found during:** Pre-execution package.json verification
- **Issue:** `apps/admin-web/package.json` `name` field is `clubcore-adminka` (renamed in 62-01); `pnpm --filter admin-web` would resolve nothing.
- **Fix:** Used `pnpm --filter clubcore-adminka` per orchestrator context override. Documented in evidence file G7-C section.
- **Files modified:** none (no plan-file edits per executor scope; flagged for verification).
- **Committed in:** N/A (text-only callout in evidence + this summary).

### Worktree environment bootstrap (infra)

**2. [Rule 3 - Blocking] `apps/backend/.env` missing in worktree (gitignored, not copied by `git worktree add`)**
- **Found during:** Initial G7-A pytest run (5 pydantic validation errors on YooKassaSettings)
- **Issue:** `app.integrations.yookassa.webhook_verifier` instantiates `YooKassaSettings()` at import time. Without `.env`, pydantic-settings raises `ValidationError` for `shop_id`, `secret_key`, `return_url`, `tax_system_code`, `default_vat_code`.
- **Fix:** Copied `/Users/andre/Workspace/Development/clubcore/apps/backend/.env` into the worktree's `apps/backend/.env`. Operator-managed env file with sandbox placeholders; not committed (gitignored).
- **Files modified:** `apps/backend/.env` (gitignored, untracked).
- **Verification:** G7-A pytest then ran to completion (2185 passed).
- **Committed in:** N/A (gitignored file).

**3. [Rule 3 - Blocking] `apps/admin-web/src/routeTree.gen.ts` missing in worktree (gitignored, auto-generated)**
- **Found during:** Initial G7-C typecheck attempt; vite was also not installed.
- **Issue:** `routeTree.gen.ts` is generated by `@tanstack/router-plugin` during vite dev/build; gitignored. Without it, admin-web typecheck cascades into "Cannot find module '@/routeTree.gen'" errors.
- **Fix:** Ran `pnpm install` (populated workspace node_modules), then `pnpm --filter clubcore-adminka exec vite build` once to regenerate the file. Build succeeded; resulting `apps/admin-web/dist/` is gitignored and not committed.
- **Files modified:** `apps/admin-web/src/routeTree.gen.ts` (gitignored, untracked), `apps/admin-web/dist/**` (gitignored, untracked), `node_modules/` (gitignored).
- **Verification:** G7-C typecheck/lint/test all subsequently exit 0.
- **Committed in:** N/A (gitignored).

### Gates that surfaced regressions (NOT auto-fixed per plan design)

**4. [Surface only — gap-closure required] G7-E openapi drift vs HEAD**
- **Found during:** Gate G7-E execution
- **Issue:** Committed `apps/backend/openapi.json` is 2 lines stale relative to source code. The pt_packages router docstring was renamed `sz:idem:{key}` → `cc:idem:{key}` in Phase 62 (likely 62-04) but no 62-0X plan included an openapi regen task. Last openapi.json regen was commit `5ceab85d chore(61-01)`.
- **Resolution:** NOT FIXED in this plan. Reverted the regenerated `openapi.json` + `schema.d.ts` via `git checkout --` to honor the "no source modifications" invariant. Captured the 2-line drift verbatim in `62-07-SMOKE-EVIDENCE.md` G7-E section.
- **Recommended gap-closure:** `cd apps/backend && uv run python -m scripts.export_openapi && pnpm --filter @clubcore/api-client codegen && git commit -m "chore(62-99): regen openapi for Phase 62 idempotency-prefix rename"`.

**5. [Surface only — gap-closure required] G7-H residual @sportzal misses (2 of 16 matches are real)**
- **Found during:** Gate G7-H execution
- **Issue:** `grep -rn '@sportzal' apps packages .github --include='*.ts/.tsx/.js/.json/.yml/.yaml/.py'` returned 16 matches. After classification:
  - 14 are deliberate `sportzal.local` test-domain placeholders (intentional per D-62-03 — CLAUDE.md retains the `sportzal.ru/.local` domain for email-from defaults and test fixtures).
  - 2 are REAL misses:
    - `packages/api-client/src/index.ts:2` JSDoc header still says `@sportzal/api-client`
    - `apps/admin-web/scripts/eslint.fixtures.config.js:68` lint message still says `Use @sportzal/api-client.request<P,M>`
- **Resolution:** NOT FIXED in this plan. Recorded the 2-row table with file:line in `62-07-SMOKE-EVIDENCE.md` G7-H section.
- **Recommended gap-closure:** 2-line edit replacing `@sportzal/api-client` → `@clubcore/api-client` in the two locations above, then re-run G7-H to confirm zero non-intentional matches.

### Known planning-defect watch (per orchestrator context)

Did NOT encounter any in-task STOP directive conflicting with `must_haves.truths`. The plan is internally consistent.

---

**Total deviations:** 5 (2 plan-text/workspace mismatches, 3 worktree env bootstrap, 2 surfaced regressions — overlap because items 1+ are categorical bookkeeping).
**Impact on plan:** Bootstrap deviations (#2, #3) were necessary to execute the gauntlet at all; no source modifications. Plan-text mismatch (#1) flagged for verification (not blocking). Two real surfaced regressions (#4, #5) require a tiny gap-closure plan — recommended scope < 5 lines of source + one openapi regen commit.

## Verifier acceptance gate (plan task <verify><automated>)

The plan's automated verify script expected:
- File exists: PASSED
- `≥ 12` gate sections (counting `PASS` or `SKIPPED`): PASSED (file has 24 such occurrences)
- `0` `FAIL` matches: **FAILED** (file has 9 `FAIL` matches — this is BY DESIGN because the plan FAILED)

The plan's `<action>` block explicitly states: "If a gate fails, the SUMMARY records the failure and the plan exits non-PASS — the orchestrator's `/gsd-execute-phase` then escalates to verification / gap-closure mode." The script's "0 FAIL" requirement was authored under the OPTIMISTIC assumption that all gates would pass; when they don't, the surfaced FAILs become the canonical contract for gap-closure scope. Honoring the action-block instruction (surface, don't hide) takes precedence over the automated assertion.

## Issues Encountered

- Backend pytest initial run crashed at import time due to missing `.env`. Diagnosed: env file is gitignored and not copied into git worktrees. Copied from main checkout to unblock.
- Frontend typecheck would have failed catastrophically (the documented "getSession does not exist on type 'never'" cascade) — pre-emptively resolved by running vite build before any typecheck per orchestrator's CRITICAL note.
- G7-E openapi drift: regen IS byte-stable (good — pipeline is deterministic) but committed snapshot is stale (Phase 62 missed an openapi regen task). Documented + reverted.
- G7-H found 16 `@sportzal` matches. Classified by intent into 14 deliberate retentions (per D-62-03) and 2 real misses. Documented + flagged for gap-closure.

## User Setup Required

None for this plan (smoke-only).

For gap-closure follow-up, a human/agent needs to apply the 2-line edits + openapi regen documented in deviations #4 and #5 above.

## Self-Check: PASSED

- [x] Evidence file exists: `.planning/phases/62-clubcore-rebrand/62-07-SMOKE-EVIDENCE.md` (372 lines, 15447 bytes)
- [x] Evidence file contains literal token `PASSED` (23 occurrences) — satisfies must_haves.artifacts contains:'PASSED'
- [x] Evidence file ≥ 40 lines (372 ≥ 40) — satisfies must_haves.artifacts min_lines:40
- [x] Evidence commit exists in git log: `263dd182 docs(62-07): capture Phase 62 G-7 smoke gauntlet evidence (10/12 PASS, 2 FAIL surfaced)`
- [x] Tree clean after revert: `git status --short` returns no modified files (only the new evidence file at commit time)
- [x] No modifications to .planning/STATE.md or .planning/ROADMAP.md (orchestrator owns those)
- [x] No modifications to RBAC files (G7-G clean)
- [x] No modifications to any source file outside the evidence file itself

## Next Phase Readiness

- **NOT ready to close v1.10 milestone yet** — gap-closure required for the 2 surfaced regressions before milestone-close vote.
- Phase 62 functional code-rename work IS complete (10/12 gates green; the two failing gates are documentation drift, not behavioural).
- Recommended next step: tiny `62-08-cleanup-final` plan or `chore(62-99)` direct commit applying the 3 fixes (2× `@sportzal/api-client` → `@clubcore/api-client` text edits, 1× openapi regen), then re-run G7-E and G7-H only.

---
*Phase: 62-clubcore-rebrand*
*Completed: 2026-05-26*
