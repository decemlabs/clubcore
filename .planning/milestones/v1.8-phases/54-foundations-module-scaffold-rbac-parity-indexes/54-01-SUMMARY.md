---
phase: 54-foundations-module-scaffold-rbac-parity-indexes
plan: "01"
subsystem: rbac
tags: [rbac, permissions, parity, owner-only, audit-log, infra]
dependency_graph:
  requires: []
  provides:
    - Resource.AUDIT_LOG in backend permissions.py
    - (VIEW, AUDIT_LOG) + (LIST, AUDIT_LOG) in OWNER_ONLY frozenset
    - audit-log mirror in admin-web can.ts OWNER_ONLY array
    - audit-log member in admin-web registry.ts Resource union
    - three-way parity test green at count 35
  affects:
    - apps/backend/app/core/permissions.py
    - apps/admin-web/src/shared/session/can.ts
    - apps/admin-web/src/shared/session/registry.ts
    - apps/backend/tests/integration/test_rbac_parity.py
tech_stack:
  added: []
  patterns:
    - Three-way RBAC parity (backend StrEnum <-> frontend OWNER_ONLY array <-> registry.ts Resource union)
key_files:
  created: []
  modified:
    - apps/backend/app/core/permissions.py
    - apps/admin-web/src/shared/session/can.ts
    - apps/admin-web/src/shared/session/registry.ts
    - apps/backend/tests/integration/test_rbac_parity.py
decisions:
  - D-54-04: audit-log read API is owner-only; reception has zero audit perms (403); reuses Action.VIEW (filterable read) + Action.LIST (paginated listing); no new Action value introduced
  - D-02/D-05: Action enum unchanged — no new Action.READ; VIEW + LIST reused as per existing design decisions
  - D-03: Resource.REPORTS + (VIEW, REPORTS) already existed and were not re-added
metrics:
  duration: "5m 4s"
  completed: "2026-05-24T15:15:49Z"
  tasks_completed: 3
  tasks_total: 3
  files_modified: 4
---

# Phase 54 Plan 01: RBAC Parity — AUDIT_LOG Resource + Owner-Only Pairs Summary

**One-liner:** Added `Resource.AUDIT_LOG = "audit-log"` with two owner-only pairs `(VIEW, AUDIT_LOG)` + `(LIST, AUDIT_LOG)` to backend + mirrored byte-for-byte into admin-web `can.ts` + `registry.ts`; parity count assertion bumped 33 -> 35 and all 4 parity tests green.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Extend backend RBAC source of truth | 21638be | apps/backend/app/core/permissions.py |
| 2 | Mirror audit-log pairs into admin-web can.ts + registry.ts | aa5509b | apps/admin-web/src/shared/session/can.ts, apps/admin-web/src/shared/session/registry.ts |
| 3 | Bump parity count assertion and run three-way parity test | 3a18a45 | apps/backend/tests/integration/test_rbac_parity.py |

## What Was Built

Extended the three-way RBAC contract so the v1.8 audit-log read API is owner-only from day one, without shipping any endpoint. Satisfies INFRA-42:

- **Backend (`permissions.py`):** `Resource.AUDIT_LOG = "audit-log"` added to the `Resource` StrEnum after `USERS`, following the kebab-on-wire multi-word convention (mirrors `OWNER_AREA` / `SCHEDULE_SLOTS`). Two new pairs added to `OWNER_ONLY` frozenset: `(Action.VIEW, Resource.AUDIT_LOG)` and `(Action.LIST, Resource.AUDIT_LOG)`. OWNER_ONLY size: 33 -> 35. Action enum unchanged.
- **Frontend (`can.ts`):** Two entries appended to `OWNER_ONLY` array: `{ action: 'view', resource: 'audit-log' }` and `{ action: 'list', resource: 'audit-log' }`. Exact single-quote literal shape preserved so parity regex `_PAIR_RE` matches.
- **Frontend (`registry.ts`):** `| 'audit-log'` added to the `Resource` union type after `| 'users'`. Action union and `routeRegistry` unchanged (no sidebar entry for audit-log in v1.8 per D-54-04).
- **Parity test (`test_rbac_parity.py`):** `test_owner_only_count_is_thirty_three` renamed to `test_owner_only_count_is_thirty_five`; both `== 33` assertions changed to `== 35`; module-header docstring updated with v1.8 breakdown term. All 4 tests pass: `test_owner_only_pairs_match`, `test_resource_values_match`, `test_action_values_match`, `test_owner_only_count_is_thirty_five`.

## Verification Results

```
cd apps/backend && uv run pytest tests/integration/test_rbac_parity.py -q
....
4 passed in 0.01s
```

All success criteria satisfied:
- `Resource.AUDIT_LOG == "audit-log"` ✓
- `(Action.VIEW, Resource.AUDIT_LOG) in OWNER_ONLY` ✓
- `(Action.LIST, Resource.AUDIT_LOG) in OWNER_ONLY` ✓
- `len(OWNER_ONLY) == 35` ✓
- `grep -c "READ = " permissions.py` returns 0 (Action enum unchanged) ✓
- `grep -c "resource: 'audit-log'" can.ts` returns 2 ✓
- `grep -c "'audit-log'" registry.ts` returns 1 (Resource union only, not routeRegistry) ✓
- `tsc --noEmit` clean ✓
- `grep -c "== 33" test_rbac_parity.py` returns 0 ✓

## Decisions Made

- **D-02/D-05 honored:** No new `Action.READ` introduced. `Action.VIEW` (filterable read) and `Action.LIST` (paginated listing) reused as established design decisions.
- **D-03 honored:** `Resource.REPORTS` and `(VIEW, REPORTS)` already present — not re-added.
- **D-54-04:** Reception denied ALL audit-log perms at the RBAC level; the `require_permission` chokepoint will return 403 the moment Phase 56 endpoint lands.
- **No sidebar entry:** `audit-log` intentionally omitted from `routeRegistry` — no frontend UI surface in v1.8.

## Deviations from Plan

None - plan executed exactly as written. The only deviation-adjacent item was that the parity test initially failed due to missing env vars for the full app (conftest.py imports `create_app`). Resolution: copied the main repo's `.env` file to the worktree backend directory — the env was already present in the repo, the worktree simply didn't have it. This is a pre-existing infrastructure characteristic, not a bug introduced by this plan.

## Known Stubs

None. All changes are concrete RBAC entries; no placeholder values or TODO items in the modified files.

## Threat Flags

None beyond what is already covered in the plan's threat model:

- T-54-01 mitigated: `(VIEW, AUDIT_LOG)` + `(LIST, AUDIT_LOG)` added to `OWNER_ONLY` frozenset; reception is denied (403).
- T-54-02 mitigated: parity count assertion bumped to 35; set-equality tests pick up new members automatically; count prevents silently-dropped pairs.
- T-54-03 accepted: no audit-log read path lands until Phase 56.

## Self-Check: PASSED
