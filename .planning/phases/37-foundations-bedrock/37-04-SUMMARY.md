---
phase: 37-foundations-bedrock
plan: 04
subsystem: core-dependencies / composition-root
tags: [INFRA-32, INFRA-33, DEBT-06, D-37-06, REG-29-03, protocol-slots]
requires: [37-03]
provides:
  - SlotByIdResolver Protocol slot (silent-None)
  - BookingSlotRestorerCallable slot (silent-None, API-only)
  - BookingCompleterCallable slot (silent-None, API-only)
  - app.modules.schedule.service stub functions (resolve_slot_by_id + restore_slot_to_active)
  - app.modules.bookings.service stub function (complete_booking)
  - app.main.create_app() wires all 3 new slots
  - app.workers.telegram_bot.main() wires register_active_pt_package_resolver (DEBT-06) + register_slot_by_id_resolver (INFRA-33 defensive)
  - tests/integration/test_app_wiring.py (startup non-None + AST parity)
  - tests/unit/test_dependencies_slots_v15.py (round-trip + silent-None for 3 new slots)
affects: [Phase 38 schedule.service real impl, Phase 38 bookings.service real impl, Phase 40 BOT-02 /book handler]
tech-stack:
  added: []
  patterns: [protocol-slot-canonical-6-step-shape, silent-None-resolver-semantics, ast-walk-register-parity-test, composition-root-carve-out, defensive-double-wiring-REG-29-03, stub-first-Option-B]
key-files:
  created:
    - apps/backend/app/modules/schedule/service.py
    - apps/backend/app/modules/bookings/service.py
    - apps/backend/tests/unit/test_dependencies_slots_v15.py
    - apps/backend/tests/integration/test_app_wiring.py
  modified:
    - apps/backend/app/core/dependencies.py
    - apps/backend/app/main.py
    - apps/backend/app/workers/telegram_bot.py
decisions:
  - "D-37-06: All 3 new v1.5 slots use SILENT-NONE accessors (mirrors v1.4 ActivePtPackageResolver at dependencies.py:117); defensive-raise reserved for payment_recorder/refunder where misconfiguration is a hard failure."
  - "PATTERNS.md §5 Option B: ship async stub functions returning None in NEW schedule/service.py + bookings/service.py so register_* calls in main.py compile; Phase 38 swaps stubs with real implementations — Callable signatures are locked at this commit."
  - "Deterministic append-at-end discipline: the 3 new register_* calls are appended AT THE END of create_app()'s register chain (after register_active_pt_package_resolver, before app.include_router), in fixed order: slot_by_id_resolver, then booking_slot_restorer, then booking_completer. Future register_* additions must continue to append at end."
  - "DEBT-06 fix in this plan: register_active_pt_package_resolver was silently omitted from telegram_bot.py at the Phase 33 REG-29-03 sweep; Phase 40 /book handler consumes it. Added defensively alongside the new INFRA-33 register_slot_by_id_resolver double-wire."
  - "BookingSlotRestorer + BookingCompleter are EXCLUSIVELY API-side (bot does not cancel bookings or record PT-sessions); mirrors D-32-14 / D-33-12 discipline for non-bot-participant slots. The AST parity test explicitly asserts both are NOT in bot register_* calls."
metrics:
  duration: ~25 min
  completed: 2026-05-17
---

# Phase 37 Plan 04: Protocol Slots + Composition-Root Wiring + DEBT-06 Fix — Summary

## One-Liner

Locked 3 cross-module Protocol slots (SlotByIdResolver, BookingSlotRestorerCallable, BookingCompleterCallable) in `app/core/dependencies.py` with silent-None semantics; wired them at the END of `app/main.py:create_app()`'s register chain backed by stub callables in NEW `app/modules/{schedule,bookings}/service.py`; defensively double-wired SlotByIdResolver + the long-missing `register_active_pt_package_resolver` (DEBT-06) in `app/workers/telegram_bot.py`; shipped a startup integration test + AST-walk bot⊆main parity test pinning REG-29-03.

## What Was Built

### 3 new Protocol slot blocks in `app/core/dependencies.py`

Each block follows the canonical 6-step shape verbatim from the v1.4 `ActivePtPackageResolver` precedent at `dependencies.py:122-192`:

| Slot | Protocol class | Callable alias | Module-private | Setter | Consumer | Wire targets |
| ---- | -------------- | -------------- | -------------- | ------ | -------- | ------------ |
| `SlotByIdResolver` | `SlotById` (id, status, trainer_id, start_time, end_time) | `Callable[[AsyncSession, UUID], Awaitable[SlotById \| None]]` | `_slot_by_id_resolver` | `register_slot_by_id_resolver` | `resolve_slot_by_id` (silent-None) | API + bot (REG-29-03 defensive) |
| `BookingSlotRestorerCallable` | n/a (side-effect only) | `Callable[[AsyncSession, UUID], Awaitable[None]]` | `_booking_slot_restorer` | `register_booking_slot_restorer` | `restore_booking_slot` (silent-None) | API only |
| `BookingCompleterCallable` | n/a (side-effect only) | `Callable[[AsyncSession, UUID], Awaitable[None]]` | `_booking_completer` | `register_booking_completer` | `complete_booking_by_pt_session` (silent-None) | API only |

Also added `from datetime import datetime` to the imports block alongside `date` (needed for the `SlotById.start_time`/`end_time` attributes).

### Stub-first Option B service files (Phase 38 swap-in)

Per PATTERNS.md §5 Recommendation, ship async stubs returning `None` that satisfy the `Callable` types so `register_*` calls in `main.py` compile:

- **NEW** `apps/backend/app/modules/schedule/service.py`
  - `async def resolve_slot_by_id(session, slot_id) -> None`
  - `async def restore_slot_to_active(session, slot_id) -> None`
- **NEW** `apps/backend/app/modules/bookings/service.py`
  - `async def complete_booking(session, booking_id) -> None`

Zero-LOC bodies trivially satisfy the SVC001 commit-gate walker (no session writes to gate). Phase 38 replaces these with real implementations; Callable signatures are locked.

### Composition-root wiring

**`app/main.py:create_app()`** — appended 3 `register_*` calls AT THE END of the register chain (after `register_active_pt_package_resolver`, before `app.include_router(api)`), in deterministic order:

```python
register_slot_by_id_resolver(schedule_service.resolve_slot_by_id)
register_booking_slot_restorer(schedule_service.restore_slot_to_active)
register_booking_completer(bookings_service.complete_booking)
```

Local `from app.modules.{bookings,schedule} import service as ..._service` imports inside `create_app()` body — mirrors the v1.3/v1.4 carve-out pattern; `importlinter` `core-not-depend-on-modules` contract scopes `source_modules = app.core`, leaving `app.main` intentionally outside scope.

**`app/workers/telegram_bot.py:main()`** — added 2 new `register_*` calls AFTER the existing `register_trainer_by_id_resolver` line:

```python
# DEBT-06 fix (Phase 33 REG-29-03 omission)
register_active_pt_package_resolver(pt_packages_service.resolve_active_pt_package)
# INFRA-33 defensive double-wire (D-37-06)
register_slot_by_id_resolver(schedule_service.resolve_slot_by_id)
```

`BookingSlotRestorer` and `BookingCompleter` are EXCLUSIVELY API-side (bot does not cancel bookings or record PT-sessions per D-37-06 — mirrors D-32-14 / D-33-12 discipline). The AST parity test explicitly asserts both are NOT in the bot's register_* set.

### Tests shipped

**`tests/unit/test_dependencies_slots_v15.py`** — 9 tests:

- `test_slot_by_id_resolver_round_trip` — register stub, call accessor, assert one invocation with passed args
- `test_slot_by_id_resolver_silent_none_when_unregistered` — D-37-06 silent-None
- `test_booking_slot_restorer_round_trip` + `_silent_none_when_unregistered`
- `test_booking_completer_round_trip` + `_silent_none_when_unregistered`
- `test_schedule_service_stubs_importable_and_return_none` — Phase 38 stub correctness
- `test_bookings_service_stub_importable_and_returns_none`
- `test_resolver_callable_aliases_are_exported` — type-alias export smoke

All use `monkeypatch.setattr(deps, "_<slot>", None)` to capture-and-restore the module-private global state.

**`tests/integration/test_app_wiring.py`** — 2 tests pinning the INFRA-33 contract:

- `test_create_app_registers_all_protocol_slots` — asserts all 10 module-private slot variables in `app.core.dependencies` are non-None after `create_app()` returns (7 pre-existing + 3 new). Catches register-chain regressions (append-at-end discipline) AND silent missing-wire bugs.
- `test_bot_main_register_set_is_subset_of_api_main_register_set` — AST-walks both modules, asserts `bot_calls <= main_calls`, plus explicit membership assertions:
  - `register_active_pt_package_resolver` IN bot_calls (DEBT-06)
  - `register_slot_by_id_resolver` IN bot_calls (INFRA-33)
  - `register_booking_slot_restorer` NOT in bot_calls (API-only per D-37-06)
  - `register_booking_completer` NOT in bot_calls (API-only per D-37-06)

## Side Effects (Wave-1 Cleanup)

The wave-1-deferred test `tests/unit/test_service_commit_gate.py::test_service_commit_gate_against_app_modules` now passes — wave 1 pre-registered `_SCHEDULE_SERVICE` + `_BOOKINGS_SERVICE` in `_INSPECTED_SERVICES` and asserted `service_path.is_file()`. Creating the two new stub service files in this plan satisfies that assertion. Confirmed by `uv run pytest tests/unit/test_service_commit_gate.py` exiting 7/7 green.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 — Bug] E501 + I001 ruff failures in initial test file**
- **Found during:** Task 1 verification
- **Issue:** `tests/unit/test_dependencies_slots_v15.py` had an unsorted import block (auto-fixed via `ruff check --fix`) plus a 102-char docstring line; `apps/backend/app/modules/bookings/service.py` had a 104-char docstring line.
- **Fix:** Auto-sorted imports, split long docstrings to multi-line, no behavior change.
- **Files modified:** `tests/unit/test_dependencies_slots_v15.py`, `apps/backend/app/modules/bookings/service.py`
- **Commit:** included in `22421f1`

**2. [Rule 1 — Bug] SIM102 nested-if ruff failure in integration test**
- **Found during:** Task 2 verification
- **Issue:** The AST-walker in `test_app_wiring.py` used nested `if` statements (`if isinstance(node, ast.Call) and ...:` then `if node.func.id.startswith("register_"):`), which `ruff` flagged as SIM102.
- **Fix:** Collapsed into a single multi-line `if` with `and` joins.
- **Files modified:** `tests/integration/test_app_wiring.py`
- **Commit:** included in `c63d62c`

### Plan-Interpretation Note (not a deviation, recorded for clarity)

The plan said "append (at the END of the file, after the existing ActivePtPackage block at lines 122-192)" three new slot blocks in `dependencies.py`. Literally appending at end-of-file conflicts with the existing `get_current_user` / `require_permission` / `verify_csrf` function definitions (which start at line 422). Interpreted as "append at the end of the slot-block section": placed the 3 new blocks BETWEEN the last existing slot (`get_payment_refunder`, line ~419) AND the first request-bound dependency function (`get_current_user`). This preserves the slot-blocks-then-dependencies file organization and is consistent with how `ActivePtPackage` was inserted between `resolve_active_membership` and the `ClientByTelegram` block in Phase 33.

## Verification Results

- `cd apps/backend && uv run pytest tests/integration/test_app_wiring.py tests/unit/test_dependencies_slots_v15.py -x` — **11/11 PASS**
- `cd apps/backend && uv run pytest -x tests/unit/test_dependencies_slots_v15.py tests/integration/test_app_wiring.py` (scoped Phase 37 sweep) — **11/11 PASS**
- `cd apps/backend && uv run pytest tests/unit/test_service_commit_gate.py` (wave-1-deferred test) — **7/7 PASS** (now green)
- `cd apps/backend && uv run ruff check <all 7 files>` — **clean**
- `cd apps/backend && uv run mypy <5 source files>` — **clean** (`Success: no issues found in 5 source files`)
- `cd apps/backend && uv run lint-imports` — **3 contracts kept** (core-not-depend-on-modules, modules-independent, integrations-not-depend-on-modules)

Cross-phase full-suite no-regression sweep is OUT OF SCOPE per the plan (`<verification>` block) — 11 known DEFER-36-04-A failures are deferred to Phase 38 pre-flight per STATE.md.

## Commits

| Task | Hash | Message |
| ---- | ---- | ------- |
| 1    | `22421f1` | `feat(37-04): add 3 v1.5 Protocol slot blocks + stub services + round-trip tests` |
| 2    | `c63d62c` | `feat(37-04): wire v1.5 slots in composition roots + DEBT-06 bot fix + parity test` |

## Self-Check: PASSED

- `apps/backend/app/core/dependencies.py` — modified (3 new slot blocks + `datetime` import)
- `apps/backend/app/modules/schedule/service.py` — FOUND (created)
- `apps/backend/app/modules/bookings/service.py` — FOUND (created)
- `apps/backend/app/main.py` — modified (3 new register_* calls + imports)
- `apps/backend/app/workers/telegram_bot.py` — modified (2 new register_* calls + imports)
- `apps/backend/tests/unit/test_dependencies_slots_v15.py` — FOUND (created, 9 tests)
- `apps/backend/tests/integration/test_app_wiring.py` — FOUND (created, 2 tests)
- Commit `22421f1` — FOUND in git log
- Commit `c63d62c` — FOUND in git log
