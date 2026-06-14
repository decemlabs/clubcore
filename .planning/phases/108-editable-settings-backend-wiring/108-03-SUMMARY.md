---
phase: 108-editable-settings-backend-wiring
plan: "03"
subsystem: api
tags: [fastapi, sqlalchemy, bookings, notifications, settings, enforcement, testing]

# Dependency graph
requires:
  - phase: 108-01
    provides: booking_config + working_hours_config + notification_prefs_config singleton tables (migration 0071_seed_settings)

provides:
  - Booking enforcement guards: booking-ahead window, cutoff window, closure dates, working hours — all read live from booking_config/working_hours_config via raw SQL
  - Cancel-window config read from booking_config (cancel_window_hours), with CANCEL_WINDOW_HOURS_RECEPTION fallback when row absent
  - Notification dispatcher matrix gate: suppress by kind×channel, quiet hours for non-in_app channels, always-on bypass for autopay_charge_failed/payment_succeeded
  - 11 integration tests for booking enforcement (all guards + fail-open)
  - 12 unit tests for notification matrix gate (pure function tests + mock session)
  - autouse permissive_booking_config fixture in bookings conftest so pre-existing tests are not broken by the new enforcement code

affects:
  - 108-04 (settings API wiring — admin can update these config rows via PUT endpoints from Plan 02)
  - 108-05 (settings UI wiring — frontend reads the live config values)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Cross-module raw SQL config read: use sa.text() SELECT against deterministic singleton PKs, never import app.modules.settings (D-54-08 modules-independent contract)"
    - "Fail-open enforcement: absent config row never blocks operation — always fall through to allow (T-108-11)"
    - "Always-on notification kinds (frozenset): bypass matrix + quiet hours entirely — no config read performed"
    - "Autouse permissive fixture: reset shared config rows to permissive defaults before each test so new enforcement guards don't break unrelated tests"
    - "Pure function unit tests for helpers: test _is_quiet_hours directly instead of patching datetime.datetime internals"

key-files:
  created:
    - apps/backend/tests/integration/bookings/test_booking_settings_enforcement.py
    - apps/backend/tests/unit/test_notification_matrix_gate.py
  modified:
    - apps/backend/app/modules/bookings/service.py
    - apps/backend/app/modules/notifications/service.py
    - apps/backend/tests/integration/bookings/conftest.py

key-decisions:
  - "D-108-03-01: Raw sa.text() SELECT only for cross-module config reads — ZERO new import-linter edges. Verified with lint-imports (3 contracts kept, 0 broken)."
  - "D-108-03-02: _ALWAYS_ON_KINDS = {autopay_charge_failed, payment_succeeded} — payment receipt and billing failure are never suppressible. autopay_charge_succeeded is informational and owner-toggleable."
  - "D-108-03-03: in_app channel bypasses quiet-hours gate (inbox is never suppressed by time-of-day). channel != 'in_app' guard applied before quiet-hours check."
  - "D-108-03-04: Quiet-hours tests use direct _is_quiet_hours unit tests (pure function) rather than patching datetime.datetime — avoids brittle mock chain where now_msk.time().replace() returns MagicMock."
  - "D-108-03-05: autouse permissive_booking_config fixture in conftest resets cancel_window_hours=24 (migration default), not 1 — preserves the 24h cancel window contract that existing cancel tests depend on."

patterns-established:
  - "Pattern: TABLE_REF noqa on sa.text() cross-module reads (bookings reading booking_config, notifications reading notification_prefs_config)"
  - "Pattern: SVC001 noqa on private helpers that don't commit (caller-owns-txn)"
  - "Pattern: autouse fixture for shared config tables in integration tests — prevents enforcement guards from polluting unrelated test bodies"

requirements-completed: [CFG-02, CFG-03, CFG-04]

# Metrics
duration: 90min
completed: 2026-06-14
---

# Phase 108 Plan 03: Booking + Notification Settings Enforcement Summary

**Booking enforcement guards (ahead-window, cutoff, closures, working-hours) wired to live booking_config + notification dispatcher matrix gate + quiet-hours suppression, both reading settings via raw SQL (modules-independent contract)**

## Performance

- **Duration:** ~90 min (resumed from prior context)
- **Started:** 2026-06-14T15:00:00Z (prior context)
- **Completed:** 2026-06-14T16:34:13Z
- **Tasks:** 4 (+ 3 deviation auto-fixes)
- **Files modified:** 5

## Accomplishments

- `create_booking` rejects bookings outside the ahead-window, within cutoff, on closure dates, and outside working hours — all read from `booking_config`/`working_hours_config` via raw `sa.text()` SELECT (zero new import-linter edges)
- `cancel_booking` reads `cancel_window_hours` from `booking_config`; falls back to `CANCEL_WINDOW_HOURS_RECEPTION` (24h) when row absent (T-108-11 fail-open)
- `create_notification` gates via matrix, quiet hours (non-`in_app` only), and always-on bypass — with sender signature append for text channels
- 23 tests (11 integration + 12 unit) covering all enforcement paths including fail-open and edge cases

## Task Commits

1. **Task 1: Booking enforcement guards** - `888c0e19` (feat)
2. **Task 2: Booking settings integration tests** - `fcc74e70` (test)
3. **Task 3: Notification matrix gate + quiet hours** - `2852ff8d` (feat)
4. **Task 4: Notification gate unit tests** - `9b001ee3` (test)
5. **[Rule 1 - Bug] Permissive booking config autouse fixture** - `10b297b2` (fix)
6. **[Rule 1 - Bug] mypy type fixes in enforcement test** - `e07e3376` (fix)

## Files Created/Modified

- `apps/backend/app/modules/bookings/service.py` — added 3 error classes, 2 PK constants, 2 snapshot dataclasses, 3 raw-SQL helper functions, step 4b enforcement in `create_booking`, dynamic cancel window reads in `cancel_booking`/`cancel_booking_for_client`/`reschedule_booking_for_client`
- `apps/backend/app/modules/notifications/service.py` — added `_ALWAYS_ON_KINDS`, `_channel_enabled`, `_parse_hhmm_time`, `_is_quiet_hours` helpers; matrix + quiet-hours gate in `create_notification`; `channel` parameter added
- `apps/backend/tests/integration/bookings/test_booking_settings_enforcement.py` — created; 11 integration tests via direct DB config manipulation against known PKs
- `apps/backend/tests/unit/test_notification_matrix_gate.py` — created; 12 unit tests using AsyncMock session + direct `_is_quiet_hours` function tests
- `apps/backend/tests/integration/bookings/conftest.py` — added `permissive_booking_config` autouse fixture + `_BOOKING_CONFIG_ID`/`_WORKING_HOURS_CONFIG_ID` constants + `json`/`sqlalchemy` imports

## Decisions Made

1. Raw `sa.text()` SELECT with `# noqa: TABLE_REF` for cross-module config reads — satisfies D-54-08 modules-independent contract; lint-imports confirmed 3 contracts kept, 0 broken
2. `_ALWAYS_ON_KINDS` = `{autopay_charge_failed, payment_succeeded}` — billing failure and payment receipt are never suppressible; `autopay_charge_succeeded` is informational and owner-toggleable (not always-on)
3. `in_app` channel exempt from quiet-hours gate — inbox is never time-suppressed; only non-`in_app` channels check `quiet_hours_start`/`quiet_hours_end`
4. Direct `_is_quiet_hours` unit tests preferred over patching `datetime.datetime` — the patch-based approach made `now_msk.time().replace()` return a `MagicMock` instead of a real `datetime.time`, causing `TypeError: '>=' not supported between MagicMock and datetime.time`
5. `cancel_window_hours=24` in autouse permissive fixture — preserves migration 0071 default so existing cancel-window integration tests that assert 24h behavior continue to pass

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] 7 pre-existing booking integration tests failed after Task 1**
- **Found during:** Post-task verification after Task 4
- **Issue:** Seeded `booking_config` has `cutoff_minutes=60` and `working_hours_config` has Mon-Fri 08:00-22:00 / Sat-Sun 09:00-21:00. Cancel/list tests create bookings with slots 1h-48h ahead or at arbitrary times, which now trigger `BookingCutoffError` (cutoff=60min) or `OutsideWorkingHoursError` (wrong weekday/time).
- **Fix:** Added `permissive_booking_config` autouse fixture to `tests/integration/bookings/conftest.py`. Resets `booking_ahead_days=365`, `cutoff_minutes=0`, `cancel_window_hours=24` (preserving migration default), `working_hours` to all-days 00:00–23:59 before each test.
- **Files modified:** `tests/integration/bookings/conftest.py`
- **Verification:** All 111 booking integration tests pass
- **Committed in:** `10b297b2`

**2. [Rule 1 - Bug] 38 mypy errors in test_booking_settings_enforcement.py**
- **Found during:** Final mypy verification pass
- **Issue:** `_seed_booking_prerequisites` return typed as `tuple[object, object, object]` causing `.id` attribute errors; `_set_working_hours` typed `list[object]` (invariant) rejecting `list[dict[str,object]]`; `closures` list contained `str` date strings not `dict`
- **Fix:** Imported `PtPackage`, `TrainerAvailabilitySlot`, `Client`; typed return as `tuple[PtPackage, TrainerAvailabilitySlot, Client]`; used `list[Any]` for `schedule`/`closures`; added `from typing import Any`
- **Files modified:** `tests/integration/bookings/test_booking_settings_enforcement.py`
- **Verification:** `mypy` reports 0 errors on all 5 modified files
- **Committed in:** `e07e3376`

**3. [Rule 1 - Bug] Quiet-hours unit tests failing with MagicMock TypeError**
- **Found during:** Task 4 test execution
- **Issue:** Tests patched `datetime.datetime` as class mock, then created `fake_msk_dt = datetime.datetime(...)` inside the patch context. Because `datetime.datetime` was the mock, this returned a `MagicMock`, not a real datetime. Then `now_msk.time().replace()` was also a `MagicMock`, causing `TypeError: '>=' not supported between MagicMock and datetime.time`
- **Fix:** Replaced brittle `patch("datetime.datetime")` approach with direct `_is_quiet_hours` pure-function unit tests (no mocking needed) plus gate integration tests via matrix config
- **Files modified:** `tests/unit/test_notification_matrix_gate.py` (rewritten)
- **Verification:** All 12 unit tests pass
- **Committed in:** `9b001ee3`

---

**Total deviations:** 3 auto-fixed (all Rule 1 - Bug)
**Impact on plan:** All auto-fixes required for correctness. No scope creep.

## Issues Encountered

- Working hours midnight-crossing window: the `_is_quiet_hours` function correctly handles `start >= end` (wrapping midnight) with `current >= quiet_start or current < quiet_end`. Tested with the 22:00–07:00 window.
- The conftest autouse fixture must set `cancel_window_hours=24` (not 1) to preserve the cancel-window contract that 9 pre-existing cancel tests assert against.

## Known Stubs

None — all enforcement guards are wired to real DB rows.

## Threat Flags

None — no new network endpoints or auth paths added. All changes are internal service-layer logic reading existing tables.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- Plan 04 (notification settings wiring) can now build on the `channel` parameter added to `create_notification`
- Plan 05 (frontend settings wiring) depends on Plan 02 (settings API) which is already complete
- The `_ALWAYS_ON_KINDS` frozenset is a named extension point — add future security notification kinds there when they are added to the notification enum

---
*Phase: 108-editable-settings-backend-wiring*
*Completed: 2026-06-14*
