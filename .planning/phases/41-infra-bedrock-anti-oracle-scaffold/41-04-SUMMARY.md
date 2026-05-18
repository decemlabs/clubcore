---
phase: 41-infra-bedrock-anti-oracle-scaffold
plan: 04
subsystem: infra
tags: [rbac, permissions, owner-only, users, three-way-parity, strenum, typescript-union]

# Dependency graph
requires:
  - phase: 41
    provides: existing OWNER_ONLY frozenset (29 entries through Phase 37 INFRA-27)
provides:
  - Resource.USERS = "users" StrEnum member (backend Python)
  - Action.UPDATE = "update" StrEnum member (backend Python)
  - 4 OWNER_ONLY pairs (CREATE/UPDATE/DELETE/LIST x USERS); reception denied all
  - admin-web 'users' Resource literal + 'update' Action literal (TS unions)
  - admin-web can.ts OWNER_ONLY array extended with 4 USERS entries
  - Three-way RBAC parity contract bumped 29 -> 33 (test green)
affects: [phase-43-users-module, phase-44-invitation-reset-flow]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Pre-register Resource + OWNER_ONLY before any router callsite (INFRA-15 lineage)"
    - "Three-way RBAC parity (backend StrEnum ↔ admin-web Resource/Action unions ↔ can.ts array) enforced by static-file analysis test"

key-files:
  created: []
  modified:
    - apps/backend/app/core/permissions.py
    - apps/admin-web/src/shared/session/registry.ts
    - apps/admin-web/src/shared/session/can.ts
    - apps/backend/tests/integration/test_rbac_parity.py

key-decisions:
  - "Added Action.UPDATE (not previously in Action StrEnum) per D-41-22 — verb chosen over EDIT for semantic clarity (deactivate/reactivate/invitation-revoke all map to UPDATE)"
  - "Bumped sanity-belt count test 29 -> 33 (data-only extension, not test-logic relaxation) — three set-equality tests pass dynamically without modification"
  - "No routeRegistry entry for 'users' per D-41-23 — admin-web is frozen-as-of-v1.3 mock-reference; Phase 41 is RBAC-contract-only"

patterns-established:
  - "Action verb additions land in the bedrock phase with their OWNER_ONLY pairs (mirrors Resource additions, not split across phases)"

requirements-completed: [INFRA-37]

# Metrics
duration: 3min
completed: 2026-05-18
---

# Phase 41 Plan 04: Resource.USERS + 4 OWNER_ONLY entries + three-way RBAC parity bump Summary

**Backend Resource.USERS + Action.UPDATE StrEnum members + 4 OWNER_ONLY pairs (CREATE/UPDATE/DELETE/LIST × USERS) mirrored byte-for-byte into admin-web TS Resource/Action unions and can.ts OWNER_ONLY array; three-way parity test green at 33 entries.**

## Performance

- **Duration:** 3 min
- **Started:** 2026-05-18T18:21:45Z
- **Completed:** 2026-05-18T18:24:28Z
- **Tasks:** 3
- **Files modified:** 4

## Accomplishments

- Backend `Resource.USERS = "users"` added to `permissions.py:Resource` StrEnum
- Backend `Action.UPDATE = "update"` added to `permissions.py:Action` StrEnum (verb new to v1.6)
- Backend `OWNER_ONLY` frozenset grew 29 → 33 with `(CREATE|UPDATE|DELETE|LIST, USERS)` block
- admin-web `Resource` TS union extended with `'users'`; `Action` TS union extended with `'update'`
- admin-web `can.ts:OWNER_ONLY` array extended with matching 4 entries (`{action, resource}` shape)
- Three-way RBAC parity test (`test_rbac_parity.py`) green — all 4 tests pass (3 dynamic set-equalities + sanity-belt count)
- Reception holds zero USERS permissions; owner short-circuits to allowed (RBAC contract ready for Phase 43 router callsites via `require_permission(Action.X, Resource.USERS)`)

## Task Commits

1. **Task 1: Backend — add Resource.USERS + 4 OWNER_ONLY entries** — `68878e2` (feat)
2. **Task 2: admin-web — mirror 'users' resource + 4 OWNER_ONLY entries** — `1769def` (feat)
3. **Task 3: Verify three-way RBAC parity holds (sanity-belt count bump)** — `08918ba` (test)

**Plan metadata commit:** _to be set on final commit_

## Files Created/Modified

- `apps/backend/app/core/permissions.py` — added Action.UPDATE, Resource.USERS, and 4 OWNER_ONLY entries (+11 / −1 lines); updated docstring count comment 29 → 33
- `apps/admin-web/src/shared/session/registry.ts` — added `'users'` to Resource union, `'update'` to Action union (+2 lines)
- `apps/admin-web/src/shared/session/can.ts` — appended 4 OWNER_ONLY entries with v1.6-commented block (+7 lines)
- `apps/backend/tests/integration/test_rbac_parity.py` — renamed sanity-belt test to `test_owner_only_count_is_thirty_three`, bumped assertion 29 → 33, updated module docstring count breakdown to include v1.6 contribution (+9 / −8 lines; no logic change)

## Decisions Made

- **Action.UPDATE was absent from the Action StrEnum** at Phase 41 commit time (verified by reading current `permissions.py`). Per D-41-22 ("reuses existing Action.{CREATE, UPDATE, DELETE, LIST}") and the plan's Task 1 conditional ("if and only if `UPDATE` is absent, add it"), `UPDATE = "update"` was added in this plan rather than rejected as a contract violation. Mirrored to admin-web Action union to keep three-way parity green.
- **Sanity-belt count test renamed**, not deleted. The test name encoded the prior cardinality (`test_owner_only_count_is_twenty_nine`); the rename to `test_owner_only_count_is_thirty_three` keeps the discovery affordance future readers expect ("what is the count today?"), with the docstring carrying the v1.1/v1.2/v1.4/v1.5/v1.6 breakdown.
- **No `routeRegistry` entry** for `'users'` in admin-web — D-41-23 explicitly scopes admin-web changes to RBAC contract only ("frozen-as-of-v1.3 mock-reference"). The Resource literal is present in the union for type safety; no sidebar/route presence.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 — Blocking] Shortened over-length inline comment to satisfy ruff E501**

- **Found during:** Task 1 (post-edit `ruff check`)
- **Issue:** Inline comment for `UPDATE = "update"` initially placed on the same line as the StrEnum member with the full D-41-22 rationale ran to 124 chars, exceeding the project ruff line-length=100 limit. Mirrors the line-length style already in use elsewhere in this file.
- **Fix:** Moved the comment to a preceding standalone `# ...` line above the member, preserving the D-41-22 rationale verbatim.
- **Files modified:** `apps/backend/app/core/permissions.py`
- **Verification:** `uv run ruff check app/core/permissions.py` → "All checks passed!"; `uv run mypy --strict app/core/permissions.py` → "Success: no issues found".
- **Committed in:** `68878e2` (Task 1 commit — caught and fixed before staging)

**2. [Rule 3 — Blocking] Bumped sanity-belt parity test count constant 29 → 33**

- **Found during:** Task 3 (`pytest tests/integration/test_rbac_parity.py`)
- **Issue:** `test_owner_only_count_is_twenty_nine` is a hardcoded sanity-belt assertion (`assert len(OWNER_ONLY) == 29`) — three set-equality tests are dynamic and passed unchanged, but the count belt failed after Task 1 added 4 entries. Plan Task 3 done criteria explicitly permits "an allowlist add of `'users'`" — this is the analogous count-extension permitted by the rule.
- **Fix:** Renamed test function to reflect the new cardinality, bumped `29 → 33` in both `assert len(OWNER_ONLY)` and `assert len(_parse_owner_only_pairs())`, updated module docstring count breakdown to credit the 4 v1.6 INFRA-37 entries. No iteration logic, no regex anchor, no parse-helper code changed.
- **Files modified:** `apps/backend/tests/integration/test_rbac_parity.py`
- **Verification:** `uv run pytest tests/integration/test_rbac_parity.py -x -q` → "4 passed in 0.01s"; `git diff` on the file shows only data + docstring + identifier-rename (no logic change).
- **Committed in:** `08918ba` (Task 3 commit)

---

**Total deviations:** 2 auto-fixed (both Rule 3 — blocking issues solved with minimum-extension fixes).
**Impact on plan:** Both auto-fixes were anticipated edge cases (ruff line-length + sanity-belt-data-bump). No scope creep, no architectural change, no test-logic relaxation. Plan executed structurally as written.

## Issues Encountered

None — all three verify-blocks passed first or after the documented Rule-3 minimum extension.

## User Setup Required

None — no external service configuration or environment variables added.

## Next Phase Readiness

- **Phase 43 (multi-user admin module) — UNBLOCKED:** `require_permission(Action.{CREATE,UPDATE,DELETE,LIST}, Resource.USERS)` is now expressible at router callsites. Reception will receive 403 on every USERS mutation; owner allowed.
- **Phase 41 plans 02, 05–11 — UNAFFECTED:** This plan touched only RBAC primitives + their parity test. No cross-plan blast radius.
- **Three-way parity contract:** Locked at 33 entries. Any future plan that touches RBAC must extend all three files in the same commit and bump the sanity-belt count.

## Self-Check

Files modified verification:

- `apps/backend/app/core/permissions.py` — FOUND (modified)
- `apps/admin-web/src/shared/session/registry.ts` — FOUND (modified)
- `apps/admin-web/src/shared/session/can.ts` — FOUND (modified)
- `apps/backend/tests/integration/test_rbac_parity.py` — FOUND (modified, data-only)

Commits verification:

- `68878e2` — FOUND in `git log --oneline -5`
- `1769def` — FOUND in `git log --oneline -5`
- `08918ba` — FOUND in `git log --oneline -5`

Verification commands re-run at SUMMARY time:

- `uv run pytest tests/integration/test_rbac_parity.py -x -q` → 4 passed
- `uv run python -c "...(Action.LIST, Resource.USERS) in OWNER_ONLY..."` → "USERS LIST in OWNER_ONLY: OK"
- `cd apps/admin-web && pnpm tsc --noEmit` → exit 0

## Self-Check: PASSED

---
*Phase: 41-infra-bedrock-anti-oracle-scaffold*
*Plan: 04*
*Completed: 2026-05-18*
