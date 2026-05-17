---
phase: 37-foundations-bedrock
plan: 02
subsystem: infra
tags: [rbac, permissions, contracts, frontend-backend-parity, strenum, typescript-union, owner-only]

# Dependency graph
requires:
  - phase: 30-foundations-trainers-payments
    provides: "OWNER_ONLY frozenset at 25 entries (post Phase 30 INFRA-19, post Phase 34 D-34-09a removal); Resource enum tail PT_PACKAGE_PLANS/PT_PACKAGES/PT_SESSIONS as kebab-on-wire precedent; Action enum with CANCEL/CHECK_IN baseline; test_rbac_parity.py 3 set-equality tests + sanity-belt count assert."
  - phase: 06
    provides: "TEST-06 (test_rbac_parity.py) structural control — regex-based static-file parser + set-equality assertion between backend OWNER_ONLY and frontend can.ts OWNER_ONLY."
provides:
  - "Resource.SCHEDULE_SLOTS = \"schedule-slots\" — v1.5 slot resource (kebab-on-wire, multi-word)."
  - "Resource.BOOKINGS = \"bookings\" — v1.5 booking resource (single-word)."
  - "Action.LIST = \"list\" — semantic separation from VIEW for endpoint listings (D-37-03a)."
  - "4 new OWNER_ONLY pairs: (CREATE|EDIT|DELETE|CANCEL, SCHEDULE_SLOTS). Slot publication is owner-only (no trainer self-service per v1.5 anti-feature list)."
  - "Frontend byte-for-byte mirror: registry.ts Resource/Action unions and can.ts OWNER_ONLY array."
  - "Refreshed TEST-06 sanity-belt count: 25 -> 29 (function renamed test_owner_only_count_is_twenty_nine)."
  - "Locked OVERRIDE D-37-03 documentation across 4 surfaces (truths, objective, permissions.py inline comment, can.ts inline comment)."
affects: [37-03-fsm-constants, 37-04-protocol-slots-and-wiring, 37-05-import-linter, 38-schedule-bookings-core, 40-telegram-book]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Phase 37 INFRA-27 OWNER_ONLY section block (mirrors Phase 15 INFRA-08 and Phase 30 INFRA-19 inline-comment delta blocks)."
    - "Cross-stack RBAC byte-parity atomic landing: backend permissions.py + frontend registry.ts + frontend can.ts + tests/integration/test_rbac_parity.py in the same plan (the only acceptable cross-stack edit in Phase 37 per D-37-08)."
    - "OVERRIDE-vs-CONTEXT documentation pattern: when a downstream plan corrects a CONTEXT.md decision (here D-37-03 \"25 → 35\" miscount), the override is recorded in 4 places — must_haves.truths, <objective> body, the source comment block in permissions.py, and the mirror comment block in can.ts — so future reviewers seeing the drift between CONTEXT.md and shipped code find the rationale without archaeology."

key-files:
  created:
    - ".planning/phases/37-foundations-bedrock/37-02-SUMMARY.md"
    - ".planning/phases/37-foundations-bedrock/deferred-items.md (pre-existing admin-web routeTree typecheck drift logged out of scope)"
  modified:
    - "apps/backend/app/core/permissions.py — Resource +2 (SCHEDULE_SLOTS, BOOKINGS), Action +1 (LIST), OWNER_ONLY 25 -> 29 (+4 SCHEDULE_SLOTS write pairs)."
    - "apps/admin-web/src/shared/session/registry.ts — Resource union +2 ('schedule-slots', 'bookings'), Action union +1 ('list')."
    - "apps/admin-web/src/shared/session/can.ts — OWNER_ONLY array +4 entries under Phase 37 INFRA-27 mirror block."
    - "apps/backend/tests/integration/test_rbac_parity.py — count assert 25 -> 29 (both branches), function rename to test_owner_only_count_is_twenty_nine, docstring updated to reflect 9+6+10+4 breakdown."

key-decisions:
  - "OVERRIDE D-37-03: CONTEXT.md said \"OWNER_ONLY 25 → 35\"; correct shipped delta is \"25 → 29\" (+4 owner-only SCHEDULE_SLOTS write pairs). The 6 reception-retained pairs CONTEXT.md enumerated ((VIEW|LIST, SCHEDULE_SLOTS), (CREATE|CANCEL|VIEW|LIST, BOOKINGS)) describe what reception SEES, not what is restricted — they MUST NOT appear in OWNER_ONLY."
  - "Resource.SCHEDULE = \"schedule\" (legacy left-nav route resource) is NOT renamed — coexists with new Resource.SCHEDULE_SLOTS (API-side scope). Two distinct concepts."
  - "(CANCEL, BOOKINGS) is NOT in OWNER_ONLY — the 24h booking cancel-window (C-05 / BOOK-06) is enforced server-side via `cancel_window_expired` 403 in bookings.service, mirroring Phase 34 D-34-09a PT-session pattern. Reception cancels are RBAC-allowed but business-rule-gated."
  - "Action.LIST has no OWNER_ONLY entries in v1.5 — reception sees all listings. The (LIST, X) reception-retained semantic is informational for Phase 38+ endpoint authors; explicit dead-code clarification comment lives at the head of the Phase 37 INFRA-27 block so future maintainers don't strip Action.LIST as unused."
  - "Frontend mirror lands in a SECOND commit (3511313) immediately after the backend commit (52172ae). The atomic-pair sequencing is intentional: Task 1's per-task verify gate doesn't run TEST-06, Task 2's does. Between the two commits the parity test is briefly red — accepted by plan design."

patterns-established:
  - "Two-commit atomic-pair sequence for cross-stack RBAC contract edits: backend first (Task 1, parity test temporarily red, ruff+mypy+grep gates green); frontend mirror + test count bump second (Task 2, all four parity tests green). Pattern carries to any future cross-stack contract extension under D-37-08."
  - "Phase NN INFRA-NN OWNER_ONLY section block with leading rationale prose enumerating reception-RETAINED pairs (by exclusion), then the literal pair tuples. Mirrors v1.2 Phase 15 INFRA-08 and v1.4 Phase 30 INFRA-19 inline comment shape."

requirements-completed: [INFRA-26, INFRA-27]

# Metrics
duration: ~18min
completed: 2026-05-17
---

# Phase 37 Plan 02: RBAC Extension Summary

**v1.5 RBAC contract extended atomically across backend + frontend: Resource +2 (SCHEDULE_SLOTS, BOOKINGS), Action +1 (LIST), OWNER_ONLY 25 -> 29; TEST-06 byte-parity invariant preserved.**

## Performance

- **Duration:** ~18 min
- **Started:** 2026-05-17T15:43Z
- **Completed:** 2026-05-17T16:01Z
- **Tasks:** 2 (both autonomous, both committed atomically)
- **Files modified:** 4 source files + 1 new deferred-items.md + 1 SUMMARY.md

## Accomplishments
- Extended backend `app.core.permissions` with 2 new Resource members (SCHEDULE_SLOTS=`schedule-slots`, BOOKINGS=`bookings`), 1 new Action member (LIST=`list`), and 4 new OWNER_ONLY tuples (CREATE/EDIT/DELETE/CANCEL on SCHEDULE_SLOTS).
- Mirrored byte-for-byte to admin-web frontend `src/shared/session/registry.ts` (Resource +2, Action +1) and `src/shared/session/can.ts` (OWNER_ONLY +4 entries).
- Refreshed `tests/integration/test_rbac_parity.py` count assert from 25 to 29 and renamed `test_owner_only_count_is_twenty_five` -> `test_owner_only_count_is_twenty_nine`; updated module docstring breakdown.
- All 4 TEST-06 parity tests pass post-commit (owner_only_pairs_match, resource_values_match, action_values_match, owner_only_count_is_twenty_nine).
- Recorded OVERRIDE of CONTEXT.md D-37-03 ("25 → 35" miscount) in 4 surfaces for future reviewer traceability.

## Task Commits

Each task was committed atomically:

1. **Task 1: Extend backend Resource/Action/OWNER_ONLY** — `52172ae` (feat)
2. **Task 2: Mirror frontend + bump TEST-06 count 25→29** — `3511313` (feat)

_Note: This is a contract-extension plan; the existing TEST-06 parity test IS the test. Task 2's commit is the RED→GREEN gate for the parity test (Task 1's commit briefly leaves parity red — accepted by plan design)._

## Files Created/Modified
- `apps/backend/app/core/permissions.py` — +22 / -1: Action.LIST added; Resource.SCHEDULE_SLOTS + Resource.BOOKINGS appended; 4-tuple Phase 37 INFRA-27 block + section-leading rationale prose appended inside OWNER_ONLY frozenset; pre-comment block size note bumped 26 → 29.
- `apps/admin-web/src/shared/session/registry.ts` — +3: Resource union appended with `'schedule-slots'` + `'bookings'`; Action union appended with `'list'`. routeRegistry untouched per D-37-08.
- `apps/admin-web/src/shared/session/can.ts` — +12: Phase 37 INFRA-27 mirror block + 4 OWNER_ONLY entries appended after Phase 30 INFRA-19 block.
- `apps/backend/tests/integration/test_rbac_parity.py` — +8 / -8: module docstring rewritten to reflect 9+6+10+4 breakdown; sanity-belt function renamed and its two count asserts bumped 25 → 29.
- `.planning/phases/37-foundations-bedrock/deferred-items.md` — new file: logs 63 pre-existing admin-web routeTree typecheck failures as out-of-scope (SCOPE BOUNDARY rule).

## Decisions Made
- **OVERRIDE D-37-03** (shipped delta is 25 → 29, not 25 → 35). Rationale captured in 4 places (plan must_haves.truths, plan <objective>, permissions.py section comment, can.ts section comment).
- **Atomic-pair commit sequence** (Task 1 backend → Task 2 frontend + test bump). Parity test is briefly red between the two commits; this is intentional per plan design and matches D-37-08's "only acceptable cross-stack edit" framing.
- **Resource.SCHEDULE coexists with Resource.SCHEDULE_SLOTS.** No rename — the legacy `'schedule'` value still scopes the left-nav route resource; the new `'schedule-slots'` scopes the API-side slot resource.
- **No `(*, BOOKINGS)` pair in OWNER_ONLY.** Reception retains all four booking-side actions (CREATE, CANCEL, VIEW, LIST). The 24h booking cancel-window (C-05 / BOOK-06) is enforced server-side via `cancel_window_expired` 403 in bookings.service when that module ships in Phase 38, mirroring the Phase 34 D-34-09a PT-session pattern. RBAC layer is not the right place for time-window business rules.
- **No routeRegistry / no UI components touched** (D-37-08 scope boundary preserved). This plan touched only the shared session contract layer.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Trimmed Action.LIST inline comment to fit ruff line-length limit**
- **Found during:** Task 1 (post-edit ruff check)
- **Issue:** The exact inline comment specified in the plan action (`# Phase 37 INFRA-26 / D-37-03a — semantic separation from VIEW for endpoint listings`) exceeded the project's 100-char line-width limit (103 chars). Ruff E501 hard error.
- **Fix:** Trimmed trailing word "endpoint" so the comment reads `# Phase 37 INFRA-26 / D-37-03a — semantic separation from VIEW for listings`. Semantic intent identical; the word "endpoint" is implicit from context (the surrounding Phase 37 INFRA-27 section block already explains that LIST is for endpoint listings).
- **Files modified:** apps/backend/app/core/permissions.py (single line)
- **Verification:** ruff check on permissions.py — All checks passed. mypy strict on permissions.py — Success: no issues.
- **Committed in:** 52172ae (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 bug — verbatim plan literal violated project lint rule)
**Impact on plan:** No scope creep, no behavior change, semantic intent preserved. The plan's literal-text directives are templates not contracts — adjusting to project lint rules is correctness work.

## Issues Encountered
- **`pnpm typecheck` reports 63 pre-existing TS errors in `src/routes/*`** — all from TanStack Router `routeTree.gen.ts` drift (`'getSession' does not exist on type 'never'`, route-id literal not assignable to `undefined`). Confirmed pre-existing by stashing my Task 2 changes and re-running typecheck: identical 63-error count. My session-layer edits produced zero new TS errors. Logged to `.planning/phases/37-foundations-bedrock/deferred-items.md` per SCOPE BOUNDARY rule. Resolve in a dedicated routeTree-regeneration plan (likely v1.5 Phase 38 pre-flight).
- **`node_modules` absent in the spawned worktree** — `pnpm typecheck` initially failed with `sh: tsc: command not found`. Resolved by running `pnpm install --frozen-lockfile` in the worktree root (2.3s using cached store).
- **ESLint warnings on admin-web** — 2 pre-existing warnings (1 stale `no-constant-condition` disable in `.codex/get-shit-done/bin/lib/state.cjs`, 1 react-hooks/exhaustive-deps in `data-grid-table-virtual.tsx`). Zero errors. Not in this plan's scope.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness
- **v1.5 RBAC contract is locked.** Phase 37-03 (FSM constants) + Phase 37-04 (Protocol slots + wiring) + Phase 37-05 (.importlinter + SVC001 scope) can now reference `Resource.SCHEDULE_SLOTS`, `Resource.BOOKINGS`, and `Action.LIST` symbolically.
- **Phase 38 endpoint authors** can use `(Action.CREATE, Resource.SCHEDULE_SLOTS)` for slot publish (owner-only), `(Action.CREATE, Resource.BOOKINGS)` for booking create (reception-allowed), and `(Action.CANCEL, Resource.BOOKINGS)` for booking cancel (reception-allowed + 24h window guard in service layer).
- **TEST-06 parity test is GREEN** — any future drift between backend `OWNER_ONLY` and frontend `can.ts:OWNER_ONLY` (or Resource/Action enum values) is caught by CI on every PR.

## TDD Gate Compliance

This plan declares `type="auto" tdd="true"` at the task level, but the existing TEST-06 parity test (`tests/integration/test_rbac_parity.py`) is the structural control — the count assert + 3 set-equality asserts ARE the failing-then-passing tests. The atomic-pair sequence is the RED → GREEN cycle:
- **RED gate** (after Task 1 commit `52172ae`): backend OWNER_ONLY has 4 new pairs frontend hasn't mirrored, AND `test_owner_only_count_is_twenty_five` still expects len==25 while backend now has len==29 — TEST-06 fails both on the set-equality and on the count assert.
- **GREEN gate** (after Task 2 commit `3511313`): frontend OWNER_ONLY has the matching 4 pairs and the test count assert is renamed and bumped to 29. All 4 parity tests pass.

No separate `test(...)` commit was created because the test file already existed and the test-side change (count bump + function rename) is logically and physically inseparable from the frontend-mirror change — both live in the Task 2 commit. The plan author intentionally combined them; this is consistent with the contract-extension nature of the work (extending a contract is not adding behavior, so the standard RED/GREEN/REFACTOR cadence collapses to ATOMIC-PAIR-LANDS).

## Self-Check: PASSED

All claimed files exist:
- apps/backend/app/core/permissions.py: FOUND
- apps/admin-web/src/shared/session/registry.ts: FOUND
- apps/admin-web/src/shared/session/can.ts: FOUND
- apps/backend/tests/integration/test_rbac_parity.py: FOUND
- .planning/phases/37-foundations-bedrock/deferred-items.md: FOUND

All claimed commits exist in `git log`:
- 52172ae (Task 1 backend): FOUND
- 3511313 (Task 2 frontend + test bump): FOUND

All success criteria from the orchestrator brief verified:
- Resource enum has SCHEDULE_SLOTS="schedule-slots" and BOOKINGS="bookings": YES (kebab on wire)
- Action enum has LIST="list": YES
- OWNER_ONLY has exactly 29 entries (25 baseline + 4 new SCHEDULE_SLOTS pairs CREATE/EDIT/DELETE/CANCEL): YES (runtime assert confirmed: `len(OWNER_ONLY) == 29`)
- Frontend registry.ts mirrors Resource additions: YES (`grep -c "'schedule-slots'"` = 1, `grep -c "'bookings'"` = 1, `grep -c "'list'"` = 1)
- Frontend can.ts mirrors Action.LIST + OWNER_ONLY deltas (byte-parity): YES (4 new entries with `resource: 'schedule-slots'`, 0 with `resource: 'bookings'`)
- test_rbac_parity.py passes with refreshed count (29): YES (4 passed in 0.01s)
- ruff + mypy strict green on apps/backend/app/core/permissions.py: YES
- Frontend type-check on src/shared/session/* clean (zero new errors): YES (the 63 errors in src/routes/* are pre-existing TanStack routeTree drift, logged to deferred-items.md per SCOPE BOUNDARY rule)

---
*Phase: 37-foundations-bedrock*
*Plan: 02*
*Completed: 2026-05-17*
