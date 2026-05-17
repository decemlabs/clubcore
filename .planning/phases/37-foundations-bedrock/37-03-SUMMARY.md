---
phase: 37-foundations-bedrock
plan: 03
subsystem: infra
tags: [fsm, constants, mappingproxytype, schedule, bookings, state-machine, python]

# Dependency graph
requires:
  - phase: 33-pt-packages
    provides: PT_PACKAGE_STATUS_TRANSITIONS MappingProxyType template (verbatim shape mirror at app/modules/pt_packages/constants.py:34-41)
  - phase: 32-memberships
    provides: precedent for placing `_assert_can_transition` guard in service.py (not constants.py) — anchors PATTERNS.md §3 divergence
provides:
  - SLOT_STATUS_TRANSITIONS — locked 3-state schedule FSM matrix (active ↔ booked, both → cancelled terminal) at app/modules/schedule/constants.py
  - BOOKING_STATUS_TRANSITIONS — locked 4-state booking FSM matrix (confirmed → {cancelled, no_show, completed}; all three terminal) at app/modules/bookings/constants.py
  - tests/unit/schedule/test_slot_fsm.py — 3 contract tests (MappingProxyType + per-key contents + terminal)
  - tests/unit/bookings/test_booking_fsm.py — 4 contract tests (MappingProxyType + per-key contents + count-of-3 + terminal triple)
  - New test packages tests/unit/schedule/ and tests/unit/bookings/ with __init__.py markers
affects: [38-schedule-service, 38-bookings-service, 39-pt-sessions-bookings-bridge, 40-bookings-api]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "MappingProxyType-wrapped FSM transition constant (Phase 37 mirrors v1.4 pt_packages/constants.py)"
    - "str-keyed transition map (not schema-layer Enum) to keep constants.py importable from models.py + service.py without circular import"
    - "_assert_can_transition guard placement: service.py (next to consumers), NOT constants.py — divergence from CONTEXT.md D-37-04 per PATTERNS.md §3"

key-files:
  created:
    - apps/backend/app/modules/schedule/constants.py
    - apps/backend/app/modules/bookings/constants.py
    - apps/backend/tests/unit/schedule/__init__.py
    - apps/backend/tests/unit/schedule/test_slot_fsm.py
    - apps/backend/tests/unit/bookings/__init__.py
    - apps/backend/tests/unit/bookings/test_booking_fsm.py
  modified: []

key-decisions:
  - "Ship constants ONLY in Phase 37; defer `_assert_can_transition` guard + `InvalidTransitionError` subclass to Phase 38's service.py (mirrors v1.3 memberships + v1.4 pt_packages precedent; overrides CONTEXT.md D-37-04 per PATTERNS.md §3)."
  - "MappingProxyType wrapping enforces runtime immutability (TypeError on item assignment); pinned by isinstance + assignment-raises test in each FSM test file."
  - "Use `str` keys (not schema-layer Enum) to keep these modules importable from models.py / service.py without circular imports — mirrors pt_packages/constants.py top-doc rationale."
  - "Booking `no_show` is a terminal state in v1.5 (no reverse transition), per Q3 SUMMARY."

patterns-established:
  - "FSM constants module template: docstring (matrix table + circular-import rationale + deferred-guard note) → `from collections.abc import Mapping` / `from types import MappingProxyType` → `*_STATUS_TRANSITIONS: Mapping[str, frozenset[str]] = MappingProxyType({...})` → `__all__` list."
  - "FSM unit-test template: 3-4 tests pinning isinstance(MappingProxyType) + assignment-raises-TypeError + per-key frozenset contents + key-set equality + terminal/count cardinality assertions."

requirements-completed: [INFRA-30, INFRA-31]

# Metrics
duration: ~12min
completed: 2026-05-17
---

# Phase 37 Plan 03: FSM Constants Lock Summary

**Locked SLOT_STATUS_TRANSITIONS (3-state) and BOOKING_STATUS_TRANSITIONS (4-state) as MappingProxyType-wrapped declarative source of truth, mirroring v1.4 pt_packages/constants.py template; guard helper deferred to Phase 38 service.py per PATTERNS.md §3.**

## Performance

- **Duration:** ~12 min
- **Started:** 2026-05-17T12:45:00Z (approx)
- **Completed:** 2026-05-17T12:57:21Z
- **Tasks:** 2 (each TDD: RED + GREEN commits)
- **Files modified:** 6 created, 0 modified

## Accomplishments
- SLOT_STATUS_TRANSITIONS locked: `active → {booked, cancelled}`, `booked → {active, cancelled}`, `cancelled → ∅`. 3-state FSM per INFRA-31.
- BOOKING_STATUS_TRANSITIONS locked: `confirmed → {cancelled, no_show, completed}` (exactly 3 legal next states per C-04), all three target states terminal (no_show terminal per Q3 SUMMARY).
- 7 contract tests (3 schedule + 4 bookings) all green; MappingProxyType immutability pinned at runtime.
- Zero cross-module imports added — importlinter `modules-independent` contract stays green.
- Test packages tests/unit/schedule/ + tests/unit/bookings/ established for downstream Phase 38 schedule-service + bookings-service plans.

## Task Commits

Each task was committed atomically via TDD (RED → GREEN):

1. **Task 1 RED: failing test for SLOT_STATUS_TRANSITIONS** — `7b8e556` (test)
2. **Task 1 GREEN: SLOT_STATUS_TRANSITIONS constants module** — `0479d96` (feat)
3. **Task 2 RED: failing test for BOOKING_STATUS_TRANSITIONS** — `e1b6d09` (test)
4. **Task 2 GREEN: BOOKING_STATUS_TRANSITIONS constants module** — `86ea3ea` (feat)

_TDD gate compliance: both tasks have ordered `test(...)` then `feat(...)` commits in git log._

## Files Created/Modified
- `apps/backend/app/modules/schedule/constants.py` — NEW: SLOT_STATUS_TRANSITIONS MappingProxyType + module docstring with transition matrix + `__all__`.
- `apps/backend/app/modules/bookings/constants.py` — NEW: BOOKING_STATUS_TRANSITIONS MappingProxyType + module docstring with transition matrix + `__all__`.
- `apps/backend/tests/unit/schedule/__init__.py` — NEW: empty package marker (new test package).
- `apps/backend/tests/unit/schedule/test_slot_fsm.py` — NEW: 3 contract tests for SLOT_STATUS_TRANSITIONS.
- `apps/backend/tests/unit/bookings/__init__.py` — NEW: empty package marker (new test package).
- `apps/backend/tests/unit/bookings/test_booking_fsm.py` — NEW: 4 contract tests for BOOKING_STATUS_TRANSITIONS.

## Decisions Made
- **Ship constants only, defer guard.** Per PATTERNS.md §3 divergence note and v1.3/v1.4 precedent, `_assert_can_transition` + `InvalidTransitionError` are NOT in constants.py — they will land in Phase 38 alongside `service.py` where consumers live. This overrides CONTEXT.md D-37-04's "alongside the constant" placement.
- **MappingProxyType wrapping.** Runtime immutability (TypeError on item assignment) is asserted in each FSM test file — same pattern as pt_packages/constants.py:34-41.
- **`str` keys, not Enum keys.** Avoids circular import with the future schema-layer SlotStatus / BookingStatus enums — mirrors pt_packages/constants.py top-doc rationale.
- **Booking `no_show` is terminal in v1.5.** Per Q3 SUMMARY: no reverse transition; if operator misclicks no-show, only fix is data-correction outside the FSM.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Shortened docstring lines in schedule/constants.py to satisfy ruff E501 (line length ≤ 100)**
- **Found during:** Task 1 (ruff verification gate)
- **Issue:** The plan's literal docstring sample for schedule/constants.py contained two lines >100 chars (lines 9-10 in the inlined sample): "active → {booked, cancelled} (publish → booked on booking; → cancelled on owner cancel)" was 103 chars; the booked-row docstring with ARCHITECTURE.md rationale was 132 chars. ruff E501 failed the gate.
- **Fix:** Rewrote both lines in compressed form preserving the same information (publish→booked on booking, →cancelled owner cancel; active = booking-cancel restore per ARCHITECTURE.md). Matrix semantics and per-state intent retained.
- **Files modified:** apps/backend/app/modules/schedule/constants.py
- **Verification:** `uv run ruff check app/modules/schedule/constants.py` → All checks passed; `uv run pytest tests/unit/schedule/test_slot_fsm.py -x` → 3/3 green.
- **Committed in:** `0479d96` (Task 1 GREEN commit — applied before the commit landed; no separate fix commit).

_Note:_ For the bookings/constants.py module I pre-shortened the docstring at write time using the same compressed form (no E501 fired in Task 2 — ruff passed on first try).

---

**Total deviations:** 1 auto-fixed (1 bug per Rule 1)
**Impact on plan:** Necessary for CI invariant compliance (ruff stays green). Zero scope change — pure formatting fix preserving documented semantics.

## Issues Encountered
None — both tasks followed the planned RED/GREEN TDD cycle and verification gates passed cleanly after the single ruff fix above.

## Verification Results

- `uv run pytest tests/unit/schedule/ tests/unit/bookings/ -x` → **7 passed** in 0.01s.
- `uv run pytest tests/unit/` (full unit sweep) → **497 passed, 1 skipped** in 1.20s (no regressions).
- `uv run ruff check apps/backend/app/modules/schedule/constants.py apps/backend/app/modules/bookings/constants.py apps/backend/tests/unit/schedule/test_slot_fsm.py apps/backend/tests/unit/bookings/test_booking_fsm.py` → All checks passed.
- `uv run mypy app/modules/schedule/constants.py app/modules/bookings/constants.py` → Success: no issues found.
- `uv run lint-imports` → 3 contracts kept, 0 broken (no cross-module imports introduced).

## User Setup Required
None — pure constants module + unit tests; no external services, no env vars, no migrations.

## Next Phase Readiness

**Ready for Phase 38:**
- `from app.modules.schedule.constants import SLOT_STATUS_TRANSITIONS` — Phase 38 schedule-service plan can now implement `_assert_can_transition` directly in `apps/backend/app/modules/schedule/service.py` using this immutable matrix.
- `from app.modules.bookings.constants import BOOKING_STATUS_TRANSITIONS` — Phase 38 bookings-service plan can implement its own `_assert_can_transition` in `apps/backend/app/modules/bookings/service.py`.
- Test packages tests/unit/schedule/ + tests/unit/bookings/ established with `__init__.py` markers — Phase 38 can drop service tests in alongside the FSM tests without re-creating the package.

**Blockers/concerns:**
- None. Phase 38 should mirror v1.4 pt_packages/service.py:184-197 for the `_assert_can_transition` helper shape and the InvalidTransitionError subclass placement (alongside other module-local exceptions).

## Self-Check

- [x] `apps/backend/app/modules/schedule/constants.py` exists → FOUND
- [x] `apps/backend/app/modules/bookings/constants.py` exists → FOUND
- [x] `apps/backend/tests/unit/schedule/__init__.py` exists → FOUND
- [x] `apps/backend/tests/unit/schedule/test_slot_fsm.py` exists → FOUND
- [x] `apps/backend/tests/unit/bookings/__init__.py` exists → FOUND
- [x] `apps/backend/tests/unit/bookings/test_booking_fsm.py` exists → FOUND
- [x] Commit `7b8e556` (test RED slot FSM) → FOUND in git log
- [x] Commit `0479d96` (feat GREEN slot constants) → FOUND in git log
- [x] Commit `e1b6d09` (test RED booking FSM) → FOUND in git log
- [x] Commit `86ea3ea` (feat GREEN booking constants) → FOUND in git log
- [x] No `_assert_can_transition` helper added (verified by grep below)
- [x] No `InvalidTransitionError` class added (verified by grep below)

## Self-Check: PASSED

---
*Phase: 37-foundations-bedrock*
*Completed: 2026-05-17*
