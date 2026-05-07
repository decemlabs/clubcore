---
phase: 15-foundations-rbac-audit-taxonomy-helper-hoisting
plan: 01
subsystem: rbac
tags: [rbac, permissions, parity, foundations, v1.2, infra-08, infra-09, tests-08]
requirements: [INFRA-08, INFRA-09, TESTS-08]

dependency_graph:
  requires:
    - "apps/backend/app/core/permissions.py (v1.1 — 5 Actions / 11 Resources / 9 OWNER_ONLY)"
    - "apps/admin-web/src/shared/session/registry.ts (v1.1 — Resource/Action unions)"
    - "apps/admin-web/src/shared/session/can.ts (v1.1 — 9 OWNER_ONLY entries)"
    - "apps/backend/tests/integration/test_rbac_parity.py (v1.1 three-way set-equality test)"
  provides:
    - "Action.CANCEL, Action.CHECK_IN (backend StrEnum)"
    - "Resource.MEMBERSHIPS, Resource.MEMBERSHIP_PLANS, Resource.VISITS (backend StrEnum)"
    - "OWNER_ONLY 6-tuple v1.2 extension (backend frozenset, admin-web array — byte-paritetic)"
    - "Three-way parity test sanity belt @ 15 entries"
  affects:
    - "Phase 16 (memberships): can use Resource.MEMBERSHIP_PLANS / .MEMBERSHIPS + Action.CANCEL in route Depends(require_permission)"
    - "Phase 17 (memberships continued): can() short-circuits owner-only correctly"
    - "Phase 19 (visits): can use Resource.VISITS + Action.CHECK_IN; reception retains check-in permission"
    - "Phase 22 (admin-web FE-06): sidebar wiring for /memberships and /visits — type unions ready"

tech_stack:
  added: []
  patterns:
    - "Three-way RBAC parity: backend permissions.py + admin-web registry.ts + admin-web can.ts must change atomically. Enforced by tests/integration/test_rbac_parity.py three set-equality assertions."
    - "Sanity-belt count assertion as drift tripwire (count: 9 -> 15)."

key_files:
  created: []
  modified:
    - "apps/backend/app/core/permissions.py"
    - "apps/admin-web/src/shared/session/registry.ts"
    - "apps/admin-web/src/shared/session/can.ts"
    - "apps/backend/tests/integration/test_rbac_parity.py"
    - "apps/backend/tests/unit/test_permissions.py"

decisions:
  - "Per D-06 INFRA-08, the 6 v1.2 OWNER_ONLY tuples are: (VIEW|EDIT|CREATE|DELETE, MEMBERSHIP_PLANS) + (CANCEL, MEMBERSHIPS) + (DELETE, MEMBERSHIPS). Reception RETAINS (CREATE, MEMBERSHIPS) and (CHECK_IN, VISITS)."
  - "Action.CHECK_IN value is 'check_in' (underscore) — wire-format mirrors Python identifier. admin-web Action union accepts 'check_in' literal."
  - "Resource.MEMBERSHIP_PLANS value is 'membership-plans' (kebab) — mirrors OWNER_AREA precedent (member uses underscore, value uses hyphen)."
  - "test_permissions.py sanity belts (Rule 2 auto-add): updated v1.1 hard-coded counts (9 entries / 5 Actions / 11 Resources) to v1.2 (15 / 7 / 14) so the existing test suite remains green alongside the contract change. Required because the plan's acceptance criteria mandate `pytest tests/unit/test_permissions.py -x` exits 0."

metrics:
  duration: "~7 minutes wall clock (autonomous wave 1 executor)"
  tasks_completed: 3
  files_modified: 5
  files_created: 0
  commits: 3
  completed_date: 2026-05-07

# Phase 15 Plan 01: RBAC Three-Way Parity Extension Summary

**One-liner:** Extended v1.1 RBAC by 2 Actions / 3 Resources / 6 OWNER_ONLY pairs across backend StrEnums + admin-web type unions + can.ts mirror, in lock-step with the three-way parity test (now @ 15 entries) — enabling Phases 16/17/19/22 to land owner-only routes without contract drift.

## Tasks Executed

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 | Extend backend `permissions.py` with v1.2 Action / Resource / OWNER_ONLY (INFRA-08) | `dd6ffe8` | `apps/backend/app/core/permissions.py`, `apps/backend/tests/unit/test_permissions.py` |
| 2 | Mirror to admin-web `registry.ts` + `can.ts` (INFRA-09) | `ae149c8` | `apps/admin-web/src/shared/session/registry.ts`, `apps/admin-web/src/shared/session/can.ts` |
| 3 | Update three-way parity sanity belt 9 -> 15 (TESTS-08) | `7c2c098` | `apps/backend/tests/integration/test_rbac_parity.py` |

## Exact Pairs Added (verbatim)

The 6 v1.2 OWNER_ONLY tuples appended on both sides (identical order on backend frozenset and admin-web array, for diff-friendly review):

```
(Action.VIEW,   Resource.MEMBERSHIP_PLANS)    /  { action: 'view',   resource: 'membership-plans' }
(Action.EDIT,   Resource.MEMBERSHIP_PLANS)    /  { action: 'edit',   resource: 'membership-plans' }
(Action.CREATE, Resource.MEMBERSHIP_PLANS)    /  { action: 'create', resource: 'membership-plans' }
(Action.DELETE, Resource.MEMBERSHIP_PLANS)    /  { action: 'delete', resource: 'membership-plans' }
(Action.CANCEL, Resource.MEMBERSHIPS)         /  { action: 'cancel', resource: 'memberships' }
(Action.DELETE, Resource.MEMBERSHIPS)         /  { action: 'delete', resource: 'memberships' }
```

**Reception retains** (NOT in OWNER_ONLY — reception can sell + check in):

- `(CREATE, MEMBERSHIPS)` — reception sells memberships
- `(CHECK_IN, VISITS)` — reception checks clients in

## Enum Additions

| Side | Type | New members |
|------|------|-------------|
| Backend | `Action(StrEnum)` | `CANCEL = "cancel"`, `CHECK_IN = "check_in"` |
| Backend | `Resource(StrEnum)` | `MEMBERSHIPS = "memberships"`, `MEMBERSHIP_PLANS = "membership-plans"`, `VISITS = "visits"` |
| Admin-web | `Resource` union | `'memberships'`, `'membership-plans'`, `'visits'` |
| Admin-web | `Action` union | `'cancel'`, `'check_in'` |

Total: 5 v1.1 + 2 v1.2 Actions = 7. 11 v1.1 + 3 v1.2 Resources = 14. 9 v1.1 + 6 v1.2 OWNER_ONLY = 15.

## Parity Test Count Update

`test_owner_only_count_is_nine` -> `test_owner_only_count_is_fifteen`. Both `assert len(OWNER_ONLY) == 15` and `assert len(_parse_owner_only_pairs()) == 15`. Module docstring counts also updated (Action 5->7, Resource 11->14, OWNER_ONLY 9->15). The three set-equality tests (`test_owner_only_pairs_match`, `test_resource_values_match`, `test_action_values_match`) require **no code change** — their regex anchors and `_parse_ts_union` accept new pairs/values transparently.

## Verification Run

```
$ cd apps/backend && uv run pytest tests/integration/test_rbac_parity.py -x -v
tests/integration/test_rbac_parity.py::test_owner_only_pairs_match PASSED      [ 25%]
tests/integration/test_rbac_parity.py::test_resource_values_match PASSED       [ 50%]
tests/integration/test_rbac_parity.py::test_action_values_match PASSED         [ 75%]
tests/integration/test_rbac_parity.py::test_owner_only_count_is_fifteen PASSED [100%]
============================== 4 passed in 0.01s ===============================

$ cd apps/backend && uv run pytest -x
======================= 200 passed, 121 skipped in 2.06s =======================

$ cd apps/backend && uv run mypy app/core/permissions.py
Success: no issues found in 1 source file

$ cd apps/backend && uv run ruff check app/core/permissions.py
All checks passed!

$ cd apps/backend && uv run lint-imports
core must not import modules KEPT
modules cannot import each other KEPT
integrations must not import modules KEPT
Contracts: 3 kept, 0 broken.

$ pnpm --filter sportzal-adminka typecheck
(exit 0 — clean)

$ pnpm --filter sportzal-adminka lint
0 errors, 2 warnings (pre-existing — eslint-disable directive in vendored .codex/state.cjs and a react-hooks hint in data-grid-table-virtual.tsx — not introduced by this plan)

$ git diff --exit-code -- apps/backend/openapi.json
(exit 0 — RBAC change is python-internal, openapi byte-stable)
```

## OpenAPI byte-stability

Confirmed: `git diff --exit-code -- apps/backend/openapi.json` exits 0. The RBAC change does not introduce or modify any FastAPI route schema — Action/Resource StrEnums are internal to `Depends(require_permission)`. No Phase 21 drift caused by this plan.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 — Missing critical functionality] Updated `tests/unit/test_permissions.py` v1.1 sanity belts to match v1.2 reality**
- **Found during:** Task 1 verification (`uv run pytest tests/unit/test_permissions.py -x` failed)
- **Issue:** Three v1.1 sanity-belt tests hard-coded the v1.1 totals (`len(OWNER_ONLY) == 9`, `{r.value for r in Action} == {"view","create","edit","delete","refund"}`, `{r.value for r in Resource} == {<11 values>}`, plus `test_specific_owner_only_membership` which froze the 9 v1.1 pairs). Without updates these tests fail the moment Task 1 lands, regardless of the parity test or plan.
- **Fix:** Renamed `test_owner_only_has_exactly_nine_entries` -> `test_owner_only_has_exactly_fifteen_entries`, expanded the Action/Resource value-set assertions to include the v1.2 members, and extended `test_specific_owner_only_membership` with the 6 v1.2 tuples.
- **Why required:** The plan's Task 1 `<acceptance_criteria>` explicitly mandates `cd apps/backend && uv run pytest tests/unit/test_permissions.py -x` exits 0. The plan's `<files_modified>` list does not include `test_permissions.py`, but the change there is a correctness consequence of Task 1's contract change — exactly the v1.2 Decision Pattern (D-12 / TESTS-08-spirit) that v1.2 sanity belts must move alongside the contract.
- **Files modified:** `apps/backend/tests/unit/test_permissions.py` (3 hunks)
- **Commit:** `dd6ffe8` (combined with Task 1 — the v1.2 contract change and its sanity-belt updates are atomic by the same logic the plan invokes for the three-way parity)

**2. [Rule 3 — Blocking issue] Installed worktree pnpm dependencies and ran initial Vite build to generate `routeTree.gen.ts`**
- **Found during:** Task 2 `pnpm --filter sportzal-adminka typecheck`
- **Issue:** The fresh worktree had no `node_modules/` and no `routeTree.gen.ts` (the latter is gitignored per `apps/admin-web/.gitignore` — auto-generated by `tanstackRouter` Vite plugin on dev/build). Without these artefacts, `tsc -b --noEmit` flagged 16 pre-existing errors in `_protected.tsx`/`_public.tsx`/etc. — none of which touched my edits to `registry.ts` or `can.ts`.
- **Fix:** `pnpm install --frozen-lockfile` (2.1s, 577 packages) + `pnpm exec vite build` (2.57s) to seed `routeTree.gen.ts`. Subsequent `pnpm --filter sportzal-adminka typecheck` exits clean.
- **Why required:** The plan's Task 2 `<acceptance_criteria>` mandates `pnpm --filter admin-web typecheck` exits 0. (Note: actual workspace package name is `sportzal-adminka`; `admin-web` is the directory. Both filters work after dependency install.)
- **Files modified:** none (build artefacts in `dist/` and `src/routeTree.gen.ts` are gitignored).
- **Commit:** none (dependency install + build are env setup, not code change).

### Out-of-scope

None — the only change beyond the plan's explicit `<files_modified>` list was `tests/unit/test_permissions.py` (Rule 2 auto-fix above; correctness consequence of Task 1).

## Authentication Gates

None encountered.

## Self-Check

Files created (this plan creates none):
- `n/a`

Files modified (verify exist with v1.2 markers):
- `apps/backend/app/core/permissions.py` — `grep -c 'CANCEL = "cancel"'` = 1 — FOUND
- `apps/backend/app/core/permissions.py` — `grep -cE '\(Action\.(VIEW|EDIT|CREATE|DELETE), Resource\.MEMBERSHIP_PLANS\)'` = 4 — FOUND
- `apps/admin-web/src/shared/session/registry.ts` — `grep -c "'check_in'"` = 1 — FOUND
- `apps/admin-web/src/shared/session/can.ts` — 6 v1.2 entries each grep = 1 — FOUND
- `apps/backend/tests/integration/test_rbac_parity.py` — `grep -c "test_owner_only_count_is_fifteen"` = 1, `_is_nine` = 0 — FOUND
- `apps/backend/tests/unit/test_permissions.py` — sanity belts updated to 15/7/14 — FOUND

Commits exist:
- `dd6ffe8`: `feat(15-01): extend backend permissions with v1.2 Action/Resource/OWNER_ONLY` — FOUND
- `ae149c8`: `feat(15-01): mirror v1.2 RBAC additions to admin-web (INFRA-09)` — FOUND
- `7c2c098`: `test(15-01): update RBAC parity sanity belt to 15 entries (TESTS-08)` — FOUND

## Self-Check: PASSED

## Threat Flags

None — this plan extends an existing closed-set RBAC contract whose boundaries were already in `<threat_model>`. No new network endpoint, no new auth path, no new schema.
