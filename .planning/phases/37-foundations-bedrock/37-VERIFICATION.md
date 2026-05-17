# Phase 37 Verification Report

**Phase:** 37 — Foundations Bedrock (v1.5 Schedule + Bookings milestone)
**Goal (ROADMAP):** All architectural contracts, RBAC permissions, audit taxonomy, FSM constants, and Protocol slot signatures for schedule + bookings are locked before any module service code is written.
**Verified:** 2026-05-17
**Status:** **PHASE COMPLETE** — all 5 ROADMAP success criteria, all 11 REQ-IDs, and all 13 spot-checks satisfied with codebase evidence.

---

## ROADMAP Success Criteria

### SC-1: `LOCKED_AUDIT_EVENTS` = 58, test assertion green — **PASS** (INFRA-24/25)

- `apps/backend/app/core/audit.py:217-226` — 5 new tuples added:
  - `("slot_published", "schedule_slot")`
  - `("slot_cancelled", "schedule_slot")`
  - `("booking_created", "booking")`
  - `("booking_cancelled", "booking")`
  - `("booking_no_show", "booking")`
- `booking_completed` correctly ABSENT — comment at lines 220-223 documents C-06 (completion signalled via `pt_session_recorded` + `booking_id`).
- `apps/backend/tests/unit/test_audit_taxonomy.py:189` — `assert len(LOCKED_AUDIT_EVENTS) == 58` passes.
- Live import: `python -c "from app.core.audit import LOCKED_AUDIT_EVENTS; print(len(LOCKED_AUDIT_EVENTS))"` → `58`.

### SC-2: `Resource.SCHEDULE_SLOTS` + `Resource.BOOKINGS` importable; `OWNER_ONLY` = 29 — **PASS** (INFRA-26/27)

- `apps/backend/app/core/permissions.py:52-53`: `SCHEDULE_SLOTS = "schedule-slots"`, `BOOKINGS = "bookings"`.
- `apps/backend/app/core/permissions.py:28`: `Action.LIST = "list"`.
- 4 new `OWNER_ONLY` entries (lines 110-113): `(CREATE/EDIT/DELETE/CANCEL, SCHEDULE_SLOTS)`. Zero `BOOKINGS` entries (reception-retained, as required by D-37-03 override).
- `apps/backend/tests/integration/test_rbac_parity.py:147`: `assert len(OWNER_ONLY) == 29` passes.
- Frontend mirror present: `apps/admin-web/src/shared/session/registry.ts:22-23,33` + `can.ts:52-55` byte-parity with backend.

### SC-3: `modules-independent` rejects cross-import — **PASS** (INFRA-28)

- `apps/backend/.importlinter:22-23` — `app.modules.schedule` and `app.modules.bookings` present in `modules-independent` contract's `modules` list (pre-existing on HEAD; not edited in Phase 37).
- Negative-fixture: `apps/backend/app/modules/bookings/_negative_importlinter_fixture.py` (forbidden import as string constant, AST-invisible).
- Test: `apps/backend/tests/unit/test_importlinter_negative_fixture.py` synthesises equivalent contract in tmp_path and asserts `lint-imports` rejects it (Strategy A).
- Live: `uv run lint-imports` → `3 kept / 0 broken`.

### SC-4: FSM constants exist + transition-set tests — **PASS** (INFRA-30/31)

- `apps/backend/app/modules/schedule/constants.py:25-31` — `SLOT_STATUS_TRANSITIONS` (`MappingProxyType`): `active → {booked, cancelled}`, `booked → {active, cancelled}`, `cancelled → ∅`.
- `apps/backend/app/modules/bookings/constants.py:26-33` — `BOOKING_STATUS_TRANSITIONS` (`MappingProxyType`): `confirmed → {cancelled, no_show, completed}`, terminals otherwise.
- Unit tests `tests/unit/schedule/test_slot_fsm.py` + `tests/unit/bookings/test_booking_fsm.py` assert legal transition set + `MappingProxyType` immutability.
- `_assert_can_transition` + `InvalidTransitionError` correctly **deferred to Phase 38** (per v1.3/v1.4 service-layer precedent; documented in both `constants.py` files).

### SC-5: Startup test + bot DEBT-06 wiring — **PASS** (INFRA-32/33, DEBT-06)

- `apps/backend/tests/integration/test_app_wiring.py:54-90`: `test_create_app_registers_all_protocol_slots` asserts `_slot_by_id_resolver`, `_booking_slot_restorer`, `_booking_completer` are non-None after `create_app()`.
- `apps/backend/tests/integration/test_app_wiring.py:93-132`: AST bot⊆main parity test asserts:
  - `register_active_pt_package_resolver` ∈ bot calls (DEBT-06 fix)
  - `register_slot_by_id_resolver` ∈ bot calls (INFRA-33 defensive)
  - `register_booking_slot_restorer` ∉ bot calls (API-only)
  - `register_booking_completer` ∉ bot calls (API-only)

---

## REQ-ID Coverage Matrix

| REQ-ID | Plan | Status | Evidence |
|--------|------|--------|----------|
| INFRA-24 | 37-01 | PASS | `audit.py:217-226` (5 new tuples) + count test |
| INFRA-25 | 37-01 | PASS | `audit_payloads.py:337-425` (5 schemas) + registry + `PtSessionRecordedPayload.booking_id` |
| INFRA-26 | 37-02 | PASS | `permissions.py:52-53, 28` (2 Resources + Action.LIST) |
| INFRA-27 | 37-02 | PASS | `permissions.py:110-113` (+4 OWNER_ONLY → 29 total) |
| INFRA-28 | 37-05 | PASS | `.importlinter:22-23` + negative-fixture test |
| INFRA-29 | 37-05 | PASS | `tests/unit/test_service_commit_gate.py:177-178` (walker scope) |
| INFRA-30 | 37-03 | PASS | `bookings/constants.py:26-33` |
| INFRA-31 | 37-03 | PASS | `schedule/constants.py:25-31` |
| INFRA-32 | 37-04 | PASS | `dependencies.py:444-599` (3 Protocols + register_* + accessors) |
| INFRA-33 | 37-04 | PASS | `main.py:193-195` (3 register_* before include_router) + startup test |
| DEBT-06 | 37-04 | PASS | `telegram_bot.py:77` (`register_active_pt_package_resolver`) + AST parity |

**Coverage: 11/11 REQ-IDs satisfied.**

---

## Spot-Check Results (13 probes)

| # | Probe | Status |
|---|-------|--------|
| 1 | 5 new v1.5 events in `audit.py`; `booking_completed` absent | PASS |
| 2 | 5 new payload schemas + registry + `PtSessionRecordedPayload.booking_id` | PASS |
| 3 | `Resource.SCHEDULE_SLOTS`/`BOOKINGS`, `Action.LIST`, 4 OWNER_ONLY pairs, reception-retained pairs NOT in OWNER_ONLY | PASS |
| 4 | Frontend `registry.ts`/`can.ts` byte-parity mirror | PASS |
| 5 | `.importlinter` adds 2 modules; rest unchanged | PASS |
| 6 | Both `*_STATUS_TRANSITIONS` constants; no `_assert_can_transition` / `InvalidTransitionError` | PASS |
| 7 | 3 new Protocol classes + register/get accessors in `dependencies.py` | PASS |
| 8 | All 3 register_* in `main.py:create_app()` BEFORE routers | PASS |
| 9 | `register_slot_by_id_resolver` + `register_active_pt_package_resolver` in `telegram_bot.py:main()` | PASS |
| 10 | Stub services match Protocol signatures, no real impl | PASS |
| 11 | Zero Alembic migrations in Phase 37 | PASS |
| 12 | Zero new HTTP endpoints / routers | PASS |
| 13 | DEFER-36-04-A NOT swept | PASS |

---

## Pre-flight Quality Gates

| Gate | Result |
|------|--------|
| ruff | All checks passed |
| mypy --strict (13 Phase 37 source files) | Success |
| lint-imports | 3 contracts kept / 0 broken |
| Phase 37 scoped pytest (9 test files) | 50/50 passed |

---

## Verdict

**PHASE COMPLETE.** All 5 ROADMAP success criteria PASS, all 11 REQ-IDs satisfied, all 13 spot-checks verified against the actual codebase. The phase goal — locking architectural contracts before module service code lands in Phase 38 — is achieved. Phase 37 ships zero migrations and zero HTTP routes (correctly defers all runtime business logic). DEBT-06 closed.

**Ready for Phase 38: Schedule Module + Booking Core.**

---

*Verified: 2026-05-17*
*Phase: 37-foundations-bedrock*
