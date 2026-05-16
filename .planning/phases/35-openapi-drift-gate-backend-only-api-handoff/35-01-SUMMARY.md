---
phase: 35-openapi-drift-gate-backend-only-api-handoff
plan: 01
subsystem: api-handoff
tags: [openapi, codegen, drift-gate, handoff]
requires:
  - apps/backend/scripts/export_openapi.py (canonical byte-stable exporter)
  - apps/backend/app/api/v1/router.py (v1.4 path source-of-truth)
  - packages/api-client/package.json scripts.codegen (openapi-typescript ^7.13.0)
provides:
  - apps/backend/openapi.json (byte-stable v1.4 OpenAPI 3.x spec)
  - packages/api-client/src/schema.d.ts (TypeScript paths + components types)
affects:
  - CI drift-gate (.github/workflows/ci.yml) — both gates now evaluate the v1.4 surface
tech-stack:
  added: []
  patterns:
    - "Atomic single-commit regen (v1.2 Phase 21 → v1.3 Phase 28 → v1.4 Phase 35 precedent)"
key-files:
  created: []
  modified:
    - apps/backend/openapi.json
    - packages/api-client/src/schema.d.ts
decisions:
  - "D-35-01 honored: single atomic commit holds both regenerated artifacts (commit 511cbf1)"
  - "D-35-02 honored: zero hand-edits — both files written verbatim by their respective generators"
  - "D-35-03 honored: byte-stable canonical form (indent=2, sort_keys=True, ensure_ascii=False, trailing newline 0x0a verified)"
  - "D-35-04 honored: git diff --exit-code returns 0 post-commit (drift-gate green locally)"
  - "D-35-13 honored: admin-web canary green (46 test files / 270 tests passing — see deviation note on spec count)"
  - "D-35-14 honored: zero edits under apps/admin-web/src/"
  - "D-35-18 honored: full local pre-commit sequence executed (export → codegen → typecheck → test → admin-web canary → diff-exit-code)"
  - "D-35-19 honored: rollback posture preserved — no source-fix needed; regen completed cleanly"
metrics:
  duration: "~3min wall-clock"
  completed: 2026-05-16
---

# Phase 35 Plan 01: Atomic v1.4 OpenAPI + api-client Schema Regen — Summary

Byte-stable atomic regen of `apps/backend/openapi.json` + `packages/api-client/src/schema.d.ts` landing in a single git commit (`511cbf1`) — exposes every v1.4 typed path (Phases 31–34) to the external design team via the canonical handoff artifacts.

## Artifact Deltas

| Artifact | Lines (before → after) | Bytes (before → after) | Delta |
|---|---|---|---|
| `apps/backend/openapi.json` | 3,571 → 5,479 | 104,018 → 169,192 | +1,908 lines / +65,174 bytes |
| `packages/api-client/src/schema.d.ts` | 2,291 → 4,086 | 75,833 → 141,093 | +1,795 lines / +65,260 bytes |

Both files grew by roughly the same proportion — symmetric expansion confirms codegen ran cleanly against the new spec with no shape regression.

## v1.4 Paths Exposed (10 grep-verified)

All present in regenerated `apps/backend/openapi.json`:

- `/api/v1/trainers` (Phase 31 — owner-only CRUD)
- `/api/v1/payments` (Phase 32 — append-only ledger)
- `/api/v1/pt-package-plans` (Phase 33 — owner-only catalog)
- `/api/v1/pt-packages` (Phase 33 — sale + lifecycle)
- `/api/v1/pt-sessions` (Phase 34 — session recording)
- `/api/v1/memberships/{membership_id}/refund` (Phase 32)
- `/api/v1/pt-packages/{pt_package_id}/refund` (Phase 33)
- `/api/v1/pt-packages/{pt_package_id}/cancel` (Phase 33)
- `/api/v1/pt-sessions/{pt_session_id}/cancel` (Phase 34)
- `/api/v1/pt-packages/{pt_package_id}/sessions` (Phase 34 — package-scoped listing)

## Verification Sequence (D-35-18, all six steps green)

| Step | Command | Result |
|---|---|---|
| 1 | `cd apps/backend && uv run python -m scripts.export_openapi` | Wrote `openapi.json` (168,968 bytes initial — final 169,192 bytes after pnpm write; see byte-stability note below) |
| 2 | `pnpm --filter @sportzal/api-client codegen` | openapi-typescript 7.13.0 → `schema.d.ts` in 80.3ms |
| 3 | `pnpm --filter @sportzal/api-client typecheck` | exit 0 |
| 4 | `pnpm --filter @sportzal/api-client test` | 2 files / 9 tests passed (includes `schema.contract.test.ts` forward-guard) |
| 5a | `pnpm --filter sportzal-adminka typecheck` | exit 0 (after one-time `vite build` to materialize the gitignored `routeTree.gen.ts`) |
| 5b | `pnpm --filter sportzal-adminka lint` | 0 errors, 2 pre-existing warnings (both in files outside this plan's scope) |
| 5c | `pnpm --filter sportzal-adminka test` | 46 files / **270 tests passed** (D-35-13 canary green) |
| 6 | `git diff --exit-code apps/backend/openapi.json packages/api-client/src/schema.d.ts` (post-commit) | exit 0 |
| 6b | `git ls-files --error-unmatch …` (WR-06) | exit 0 |

## Acceptance Criteria

All twelve acceptance criteria from `35-01-PLAN.md` satisfied:

- [x] `git diff --exit-code` on both artifacts post-commit returns 0
- [x] `git ls-files --error-unmatch` on both artifacts returns 0
- [x] `git log -1 --stat` shows exactly two files (`apps/backend/openapi.json`, `packages/api-client/src/schema.d.ts`)
- [x] Commit subject matches conventional-commits (`chore(35-01): regenerate v1.4 OpenAPI artifact + api-client schema`)
- [x] All 10 v1.4 path tokens present in `openapi.json` (grep count = 1 each)
- [x] Trailing byte of `openapi.json` is `0x0a` (byte-stability per D-35-03)
- [x] `schema.d.ts` retains openapi-typescript header on line 1–4
- [x] api-client typecheck + test green
- [x] admin-web typecheck + lint + test green
- [x] Zero edits in `apps/admin-web/src/**` (`git status --short` empty)
- [x] Zero edits in `apps/backend/app/modules/**` (`git status --short` empty)
- [x] Zero edits in `apps/backend/scripts/export_openapi.py` and `packages/api-client/package.json`

## Commit

| Hash | Subject | Files |
|---|---|---|
| `511cbf1` | `chore(35-01): regenerate v1.4 OpenAPI artifact + api-client schema` | `apps/backend/openapi.json`, `packages/api-client/src/schema.d.ts` |

## Deviations from Plan

### Minor — Plan documentation drift (not code drift)

**1. [Rule 3 - Setup blocker] pnpm node_modules missing on first invocation**
- **Found during:** Step 2 of execution sequence (codegen).
- **Issue:** Worktree had no `node_modules`; `pnpm --filter ... codegen` failed with `openapi-typescript: command not found`.
- **Fix:** Ran `pnpm install --frozen-lockfile` (zero source edits — restored expected baseline; lockfile unchanged).
- **Files modified:** None tracked (node_modules is gitignored).
- **Commit:** N/A — restorative action only.

**2. [Plan doc drift] pnpm filter target uses package name `sportzal-adminka`, not `@sportzal/admin-web`**
- **Found during:** Step 4 admin-web verification.
- **Issue:** Plan references `pnpm --filter @sportzal/admin-web ...` (4 occurrences) but the actual package name in `apps/admin-web/package.json` is `sportzal-adminka`. The plan also references `predev` hook as `pnpm --filter @sportzal/api-client codegen` which IS the actual hook value (api-client name matches).
- **Fix:** Used the actual package name `sportzal-adminka` for the canary filter. No source/script edits. The canary still ran and passed.
- **Files modified:** None.
- **Recommendation:** Wave-2 planner should either (a) use `sportzal-adminka` in the next plan's verification commands or (b) rename the package to `@sportzal/admin-web` in a separate hygiene plan — out of scope for Phase 35 per D-35-14.

**3. [Plan doc drift] Test spec count is 270, not 233**
- **Found during:** Step 5c admin-web test canary.
- **Issue:** Plan acceptance criteria references "233 vitest specs" but actual count is 46 files / 270 tests. D-35-13 says "233 specs unchanged" — the literal `233` count is stale (likely from when context was gathered against an earlier state).
- **Fix:** Treated the canary intent literally — "tests pass unchanged after regen". All 270 tests pass, confirming the schema change is backwards-compatible. No source/test edits.
- **Files modified:** None.
- **Recommendation:** Wave-2 plan should update its expected spec count to ≥270 (any growth from new test authoring would only happen via committed source changes — Phase 35 doesn't author admin-web tests per D-35-14).

**4. [Rule 3 - Setup blocker] admin-web typecheck requires `routeTree.gen.ts` which is gitignored**
- **Found during:** Step 5a admin-web typecheck.
- **Issue:** `tsc -b --noEmit` fails with 25+ errors when `src/routeTree.gen.ts` is missing (file is auto-generated by the `tanstackRouter` Vite plugin on `dev`/`build`). The file is in `.gitignore`. The `typecheck` script has no `pretypecheck` hook to regenerate it. Confirmed pre-existing by stash-testing on the unmodified baseline — failures are identical.
- **Fix:** Ran `pnpm exec vite build` once (inside `apps/admin-web/`) to materialize the route tree. This is a workspace-setup action equivalent to running `pnpm dev` once — does NOT modify any tracked file. Then typecheck passed cleanly.
- **Files modified:** None tracked. Generated `dist/` and `src/routeTree.gen.ts` are both gitignored.
- **Commit:** N/A — restorative action only.
- **Recommendation:** Pre-existing admin-web tooling debt (a `pretypecheck` script invoking `tsr generate` or `vite build --mode generate-routes` would close the gap). Out of scope for Phase 35.

**5. [Rule 3 - Path safety self-fix] SUMMARY.md initially written to main repo (#3099)**
- **Found during:** Post-task SUMMARY creation.
- **Issue:** Executor used the orchestrator-context absolute path `/Users/andre/Workspace/Development/clubcore/.planning/...` for the Write tool call — that path resolved to the **main repo**, not the worktree (`WT_ROOT=/Users/andre/Workspace/Development/clubcore/.claude/worktrees/agent-afb8bbb8f5897b04c`).
- **Detection:** Self-check `git status --short` returned empty inside the worktree even though the file existed at the typed path. The executor's own `<absolute_path_safety>` guard caught it on inspection.
- **Fix:** Copied the file from the main repo into the worktree at the correct `WT_ROOT/.planning/...` path; removed the stray copy from the main repo. The atomic commit `511cbf1` was never affected (it had already landed correctly on the worktree branch).
- **Files modified:** None tracked; SUMMARY.md is the same artifact, now correctly located in the worktree.
- **Recommendation:** Future executors should derive SUMMARY.md absolute paths from `git rev-parse --show-toplevel` rather than constructing them from working-directory string-prefix knowledge.

### Auto-fixed code issues

None. Zero source-fix-required deviations encountered. The regen surfaced no backwards-incompatible schema change (D-35-13 canary intact), confirming Phases 31–34 routers + schemas are clean.

### Architectural deviations (Rule 4 — required user decision)

None.

## CLAUDE.md Compliance

- pnpm workspaces honored (per "Tech stack — Frontend" constraint).
- No emojis in committed files (per CLAUDE.md style).
- Conventional commit format used: `chore(35-01): ...`.
- `apps/admin-web` frozen-as-of-v1.3 — zero edits inside the tree per project Constraint and D-35-14.
- `apps/backend/scripts/export_openapi.py` and `packages/api-client/package.json` unmodified — pin discipline preserved (D-35-03).

## Self-Check: PASSED

**Created files exist:**
- FOUND: `.planning/phases/35-openapi-drift-gate-backend-only-api-handoff/35-01-SUMMARY.md` (this file)

**Commit exists:**
- FOUND: `511cbf1` on branch `worktree-agent-afb8bbb8f5897b04c`

**Forbidden zones untouched (re-verified):**
- `git status --short -- apps/admin-web/src/` → empty
- `git status --short -- apps/backend/app/modules/` → empty
- `git status --short -- apps/backend/scripts/export_openapi.py` → empty
- `git status --short -- packages/api-client/package.json` → empty

## Pointer Forward

**Plan 35-02 (Wave 2)** will consume these regenerated artifacts to:
1. Extend `packages/api-client/src/schema.contract.test.ts` with method-level `AssertNonNever` forward-guards for every v1.4 path (D-35-05..D-35-09).
2. Append `## v1.4 changelog` + `## Auth quick-start` sections to `packages/api-client/README.md` (D-35-10..D-35-12).
3. Re-run the full D-35-18 verification sequence — admin-web canary expected to remain at 270+ tests green.

Wave 2 depends on this commit (`511cbf1`) for path enumeration; the schema is now stable to read from.
