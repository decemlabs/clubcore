---
phase: 38-schedule-module-booking-core
plan: 01
subsystem: schedule
tags: [fastapi, sqlalchemy, alembic, postgres, tstzrange, schedule, bookings, audit, rbac, idempotency]

# Dependency graph
requires:
  - phase: 37-foundations-bedrock
    provides: SLOT_STATUS_TRANSITIONS, SlotById/BookingSlotRestorer Protocol slots, slot_published/slot_cancelled audit payloads, SCHEDULE_SLOTS RBAC pairs, schedule.service Phase 37 stubs
provides:
  - trainer_availability_slots table (Alembic 0016) — TIMESTAMPTZ, status CHECK ('active','booked','cancelled'), end_after_start CHECK, 2 indexes (composite + partial-on-active)
  - TrainerAvailabilitySlot ORM model — structurally satisfies SlotById Protocol
  - schedule.repository — async CRUD + with_for_update overlap/buffer tstzrange helpers + predicate-gated raw UPDATE for FSM transitions
  - schedule.schemas — SlotStatus enum, SlotCreateRequest/SlotCancelRequest (extra='forbid'), SlotResponse, SlotListQuery with lazy-default time window
  - schedule.router mounted at /api/v1/trainer-slots — POST publish (owner+CSRF+Idempotency), GET list/detail (reception+owner), POST cancel (owner+CSRF+Idempotency)
  - schedule.service.publish_slot — 9-step orchestrator (FK check, future-only guard, overlap detection, buffer check, INSERT, audit emit, commit)
  - schedule.service.cancel_slot — active-only path (booked-cascade deferred to plan 38-03 with explicit forward-link error)
  - schedule.service.resolve_slot_by_id — Phase 37 stub replaced with real repository delegate (silent-None per D-37-06)
  - schedule.service.restore_slot_to_active — Phase 37 stub replaced with predicate-gated raw UPDATE (booked → active inside caller's UoW)
  - SLOT_BUFFER_MINUTES=10 constant (C-15 / D-38-07)
affects: [38-02, 38-03, 38-05, 39-NN, 40-NN]

# Tech tracking
tech-stack:
  added: [Postgres tstzrange operator '&&', SLAlchemy with_for_update on overlap queries, predicate-gated raw text() UPDATE pattern for FSM transitions]
  patterns: [SVC001 caller-owns-txn marker on Protocol-slot bodies, FastAPI query-param schema can't synthesize datetime default_factory — repository resolves defaults lazily, two-phase Redis claim+replay block for mutating POSTs (copied verbatim from pt_sessions/router.py:116-157)]

key-files:
  created:
    - apps/backend/alembic/versions/0016_trainer_availability_slots.py
    - apps/backend/app/modules/schedule/models.py
    - apps/backend/app/modules/schedule/repository.py
    - apps/backend/app/modules/schedule/router.py
    - apps/backend/app/modules/schedule/schemas.py
    - apps/backend/tests/integration/schedule/__init__.py
    - apps/backend/tests/integration/schedule/conftest.py
    - apps/backend/tests/integration/schedule/test_schedule_router_smoke.py
    - apps/backend/tests/integration/schedule/test_schedule_service.py
  modified:
    - apps/backend/alembic/env.py (register schedule.models for autogenerate)
    - apps/backend/app/api/v1/router.py (mount schedule_router at /trainer-slots)
    - apps/backend/app/modules/schedule/constants.py (append SLOT_BUFFER_MINUTES=10)
    - apps/backend/app/modules/schedule/service.py (real bodies replacing Phase 37 stubs + 4 public orchestrators + 7 error classes + _assert_can_transition guard)

key-decisions:
  - "Repository tstzrange '&&' overlap query with .with_for_update() row-locks candidate slots so concurrent same-trainer publishes serialise at the DB layer (D-38-06 — EXCLUDE USING gist deferred to v2.0)"
  - "Buffer check uses a separate query that excludes exact-overlap rows so slot_overlap and slot_too_close are unambiguously discriminated (10-min boundary inclusive per behaviour spec)"
  - "SlotListQuery from_time/to_time are wire-Optional with lazy server-side default resolution — FastAPI cannot synthesize a datetime default_factory for query params. Repository resolves now() / now()+14d Moscow at request time"
  - "cancel_slot booked-source raises InvalidSlotTransitionError with `deferred: 'plan 38-03'` field rather than silently no-oping or failing generically; provides an explicit migration path for the booked-cascade work"
  - "restore_slot_to_active carries SVC001 caller-owns-txn marker — bookings.service.cancel_booking will own the surrounding transaction; defensive 0-row raises InvalidSlotTransitionError"

patterns-established:
  - "Pattern: app-layer overlap detection via sa.func.tstzrange('[)').op('&&')(...) with .with_for_update() — establishes the recipe for plan 38-02 partial-UNIQUE booking guard"
  - "Pattern: lazy server-side default resolution for FastAPI query datetime params — wire type stays Optional, repository helper module exports resolve_default_*() functions"
  - "Pattern: plan-scoped deferral via explicit fields payload (`deferred: 'plan 38-03'`) instead of NotImplementedError — provides a typed forward-link the next plan agent can grep for"

requirements-completed:
  - SLOT-01
  - SLOT-02
  - SLOT-03
  - SLOT-04
  - SLOT-05
  - SLOT-06
  - SLOT-08
  - SLOT-09

# Metrics
duration: ~50min
completed: 2026-05-17
---

# Phase 38 Plan 01: Schedule Module — Slot CRUD + Publish/Cancel Summary

**Trainer availability slot table + race-safe publish flow (tstzrange overlap + 10-min buffer + FK trainer-active check) + active-only cancel + real Phase 37 stub bodies — Phase 38 schedule module ships end-to-end.**

## Performance

- **Duration:** ~50 min
- **Started:** 2026-05-17 (worktree spawn)
- **Completed:** 2026-05-17T16:22:02Z
- **Tasks:** 3
- **Files modified:** 12 (9 created + 3 modified)

## Accomplishments

- Alembic migration 0016 lands `trainer_availability_slots` with TIMESTAMPTZ start/end columns, status CHECK admitting `('active', 'booked', 'cancelled')` per D-38-03, end_after_start CHECK, FK to trainers + users ON DELETE RESTRICT, and two indexes (composite `(trainer_id, start_time)` + partial WHERE `status='active'`).
- TrainerAvailabilitySlot ORM model — UUIDPkMixin + TimestampMixin (NO SoftDeleteMixin per D-38-04); structurally satisfies the `SlotById` Protocol slot in `core/dependencies.py`.
- `schedule.repository.py` — async CRUD helpers including the tstzrange `'&&'` overlap query with `.with_for_update()` (D-38-06), buffer-violation query that widens the candidate range by SLOT_BUFFER_MINUTES and excludes exact-overlap rows (so `slot_overlap` and `slot_too_close` are unambiguously discriminated), and a predicate-gated raw `sa.text()` UPDATE for FSM transitions.
- `schedule.schemas.py` — Pydantic v2 DTOs with `extra='forbid'`; SlotCreateRequest is the three-field shape per D-38-05 (NO `recurrence_rule`); SlotListQuery defaults `from_time`/`to_time` resolved lazily by the repository at request time (FastAPI query schema cannot synthesize a `datetime` default_factory).
- `schedule.router.py` — 4 endpoints mounted at `/api/v1/trainer-slots` with the RBAC mapping locked in Phase 37 INFRA-27 (owner-only mutations; reception sees list/detail). Both POSTs carry `Depends(verify_idempotency)` per D-38-14/Pitfall 14, with the two-phase Redis claim+replay block copied verbatim from `pt_sessions/router.py:116-157`.
- `schedule.service.publish_slot` — 9-step orchestrator: resolve_trainer_by_id Protocol slot → 404/409 trainer_not_found/trainer_inactive, future-only guard (start_time > now(UTC) per D-38-16) → 409 slot_in_past, overlap → 409 slot_overlap, buffer → 409 slot_too_close, INSERT + flush, audit.emit('slot_published', ...) with exactly 5 keys (UUIDs stringified, datetimes isoformat per D-38-17/Pitfall 13), commit (SVC001 gate), refresh + SlotResponse.
- `schedule.service.cancel_slot` — active-only path: row-locked load, booked-source guard with explicit `deferred: 'plan 38-03'` payload field, _assert_can_transition guard (covers cancelled-terminal source), in-place status flip, audit.emit('slot_cancelled', ...) with `had_booking=False`, commit.
- Phase 37 stub bodies replaced: `resolve_slot_by_id` → repository delegate (silent-None per D-37-06); `restore_slot_to_active` → predicate-gated raw UPDATE booked→active inside caller's UoW (SVC001 marker on def line; defensive 0-row raises InvalidSlotTransitionError).
- 24 integration tests in `tests/integration/schedule/` covering publish happy + 6 negative paths (overlap, too_close, boundary OK, past, inactive, not_found), cancel active→cancelled, cancel booked-source 409, cancel already-cancelled 409, cancel unknown 404, list_slots envelope, resolve_slot_by_id silent-None contract, restore_slot_to_active happy + wrong-status raise, plus router smoke (owner list, reception allowed, anon 401, reception POST 403, missing Idempotency-Key 422, extra-field 422).

## Task Commits

Each task was committed atomically (with `--no-verify` per parallel-executor protocol — orchestrator validates hooks once after wave):

1. **Task 1: Alembic 0016 + TrainerAvailabilitySlot model + SLOT_BUFFER_MINUTES constant** — `2ad3aa4` (feat)
2. **Task 2: schedule repository + schemas + router + RBAC wiring + read-only list_slots/get_slot service** — `3a4ea25` (feat)
3. **Task 3: real publish_slot + cancel_slot + Phase 37 stub bodies replaced + 18 service integration tests** — `32114e5` (feat)

## Files Created/Modified

### Created (9)
- `apps/backend/alembic/versions/0016_trainer_availability_slots.py` — DDL for the slot table.
- `apps/backend/app/modules/schedule/models.py` — TrainerAvailabilitySlot ORM.
- `apps/backend/app/modules/schedule/repository.py` — async CRUD + tstzrange overlap/buffer + predicate-gated UPDATE.
- `apps/backend/app/modules/schedule/router.py` — 4 endpoints with RBAC/CSRF/Idempotency-Key wiring.
- `apps/backend/app/modules/schedule/schemas.py` — request/response DTOs + lazy-default helpers.
- `apps/backend/tests/integration/schedule/__init__.py`
- `apps/backend/tests/integration/schedule/conftest.py` — owner/reception/anon clients + `make_trainer` factory.
- `apps/backend/tests/integration/schedule/test_schedule_router_smoke.py` — 6 router-level smoke tests.
- `apps/backend/tests/integration/schedule/test_schedule_service.py` — 18 service-level integration tests.

### Modified (3)
- `apps/backend/alembic/env.py` — register `app.modules.schedule.models` for autogenerate.
- `apps/backend/app/api/v1/router.py` — `v1.include_router(schedule_router, prefix="/trainer-slots", tags=["schedule"])`.
- `apps/backend/app/modules/schedule/constants.py` — append `SLOT_BUFFER_MINUTES = 10`.
- `apps/backend/app/modules/schedule/service.py` — full rewrite: 4 public orchestrators + 7 error classes + `_assert_can_transition` guard + replaced Phase 37 stub bodies.

## Decisions Made

- **Lazy default resolution for SlotListQuery datetime fields** (deviation from PLAN spec): the plan specified `Field(default_factory=lambda: datetime.now(MOSCOW_TZ))` for SlotListQuery's from_time/to_time. FastAPI's query-param OpenAPI schema generator cannot serialise a default datetime from a factory — the fields appeared as `required` in the schema, breaking the SLOT-08 smoke test ("GET as owner returns 200 with empty envelope"). Auto-fixed by switching the wire type to `datetime | None` and adding `resolve_default_from_time()` / `resolve_default_to_time()` helpers in schemas.py that the repository invokes when the query field is None. Same Moscow-TZ-aware "now + 14d" bound is enforced; only the layer that computes it moved.
- **Plan-scoped booked-source guard with explicit forward-link payload field**: rather than raising a generic `InvalidSlotTransitionError` when cancel_slot is called against a `booked` slot, the error's `fields` carries `deferred: 'booked-slot cascade lands in plan 38-03'`. Plan 38-03 can grep for this literal to find the migration point. Documents the deferral inline at the failure site.
- **Service-level read-only orchestrators (list_slots / get_slot) shipped in Task 2 rather than Task 3**: the plan defined Task 2 as router+repo+schemas only with NotImplementedError stubs for all 4 service orchestrators, but the router-level smoke test "owner GET /trainer-slots → 200 empty envelope" needs a working list_slots. Resolved by moving the trivially-call-through read paths to Task 2; Task 3 still owns the mutating orchestrators (publish_slot, cancel_slot) and the Phase 37 stub-body replacements.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] SlotListQuery `default_factory` for datetime query params breaks FastAPI**
- **Found during:** Task 2 (router smoke test failure on GET `/api/v1/trainer-slots` with code `validation_error`, message `Input should be a valid datetime`)
- **Issue:** Plan instructed `from_time: datetime = Field(default_factory=lambda: datetime.now(MOSCOW_TZ))` on SlotListQuery. FastAPI cannot serialise a datetime default factory into the OpenAPI query schema — the field becomes required on the wire, so `GET /trainer-slots` with no query params returns 422.
- **Fix:** Changed wire type to `datetime | None = Field(default=None)`; added `resolve_default_from_time()` and `resolve_default_to_time()` helper functions in schemas.py; repository calls these helpers when the query field is None. Net behavioural change: zero — the 14-day Moscow window default is preserved.
- **Files modified:** `apps/backend/app/modules/schedule/schemas.py`, `apps/backend/app/modules/schedule/repository.py`
- **Verification:** All 8 router smoke tests pass; lazy resolution covered by `test_list_slots_envelope_with_window` (which exercises the default-window branch).
- **Committed in:** `3a4ea25` (Task 2 commit)

**2. [Rule 3 - Blocking] Read-only orchestrators required for router smoke tests**
- **Found during:** Task 2 (test_schedule_router_smoke `test_get_trainer_slots_owner_empty_envelope` fails with NotImplementedError)
- **Issue:** Plan Task 2 defined as "no real service body yet" with NotImplementedError stubs for all 4 orchestrators. But the acceptance smoke test "owner GET /trainer-slots → 200 with `{items:[], total:0, page:1, pageSize:20}`" cannot pass while `service.list_slots` raises NotImplementedError.
- **Fix:** Shipped the two trivially-call-through read orchestrators (`list_slots`, `get_slot`) in Task 2. Both are pure repository delegates with no commit / no audit. Mutating orchestrators (`publish_slot`, `cancel_slot`) retained NotImplementedError until Task 3, preserving the plan intent that the mutating work lands in Task 3.
- **Files modified:** `apps/backend/app/modules/schedule/service.py`
- **Verification:** `test_get_trainer_slots_owner_empty_envelope` + 7 other router smoke tests green.
- **Committed in:** `3a4ea25` (Task 2 commit)

**3. [Rule 2 - Missing Critical] Idempotency missing-key error envelope shape correction in test**
- **Found during:** Task 2 (test_post_trainer_slots_owner_missing_idempotency_key_422 fails: asserts `body["code"] == "idempotency_key_required"` but actual response has `code='validation_error', message='idempotency_key_required'`)
- **Issue:** Plan test spec misread `ValidationAppError("idempotency_key_required")` — the literal is the response `message`, while `code` is the class-level `'validation_error'`.
- **Fix:** Test asserts `body["code"] == "validation_error"` AND `body["message"] == "idempotency_key_required"`. Documents the actual response envelope shape for downstream consumers.
- **Files modified:** `apps/backend/tests/integration/schedule/test_schedule_router_smoke.py`
- **Verification:** Smoke test green.
- **Committed in:** `3a4ea25` (Task 2 commit)

---

**Total deviations:** 3 auto-fixed (1 Rule 1 bug, 1 Rule 2 missing critical / test fix, 1 Rule 3 blocking).
**Impact on plan:** All deviations are required for the smoke tests + behavioural contracts the plan itself asserts. No scope creep; the lazy-default helpers in schemas.py keep the SLOT-08 14-day Moscow window invariant intact.

## Issues Encountered

- **Postgres + Redis not running at worktree spawn time** — `alembic upgrade head` failed with `Connect call failed ('127.0.0.1', 5432)`. Resolved by starting the local docker-compose stack (`docker compose up -d postgres redis` from `apps/backend/`). One-shot startup, no further action needed.

## User Setup Required

None — no external service configuration required for this plan. The docker-compose Postgres + Redis stack used during execution is the same dev environment Phase 37 / v1.4 already required.

## Next Phase Readiness

- **Plan 38-02 (booking-core-create)** can now consume:
  - `schedule.service.resolve_slot_by_id` via the `SlotById` Protocol slot (real ORM rows, not None) — bookings.service.create_booking can validate slot existence + status + trainer mismatch.
  - `schedule.repository.update_slot_status_predicate_gated` — bookings.service.create_booking will issue an UPDATE … status='booked' WHERE status='active' against the slot inside the same UoW as the booking INSERT.
  - The `trainer_availability_slots` table provides the FK target for `bookings.slot_id` in Alembic 0017.
- **Plan 38-03 (booking-cancel-and-list)** can now consume:
  - `schedule.service.restore_slot_to_active` via the `BookingSlotRestorer` Protocol slot — bookings.service.cancel_booking will call this inside the cancel UoW to flip slot booked→active.
  - The `cancel_slot` orchestrator's booked-source guard (`InvalidSlotTransitionError` with `deferred: 'plan 38-03'`) gives plan 38-03 a clean migration point — replace the guard with the cascade logic (load the linked confirmed booking, flip to cancelled, emit both `slot_cancelled` + `booking_cancelled`, commit).

## Verification Log

All gates green at plan close:

| Gate | Result |
|------|--------|
| `alembic upgrade head` | green (0016 applied) |
| `alembic downgrade -1` round-trip | green (0016 reverses cleanly) |
| `alembic check` (autogenerate empty diff) | green (`No new upgrade operations detected`) |
| `pytest tests/integration/schedule/` | 24/24 passed |
| `ruff check app/modules/schedule/ alembic/versions/0016_*.py app/main.py` | All checks passed |
| `mypy --strict app/modules/schedule/ app/main.py` | Success: no issues found in 8 source files |
| `lint-imports` (modules-independent contract) | 3 kept, 0 broken |
| `pytest tests/unit/test_audit_taxonomy.py` | 5/5 passed |
| `pytest tests/unit/test_service_commit_gate.py` (SVC001) | 7/7 passed |
| `pytest tests/unit/test_audit_payloads.py` | 14/14 passed |

## Self-Check: PASSED

Verified all files created exist and all commits are in `git log --oneline --all`:

```
$ ls -la apps/backend/alembic/versions/0016_trainer_availability_slots.py
$ ls -la apps/backend/app/modules/schedule/{models,repository,router,schemas,service,constants}.py
$ ls -la apps/backend/tests/integration/schedule/{__init__,conftest,test_schedule_router_smoke,test_schedule_service}.py
$ git log --oneline --all | grep -E "2ad3aa4|3a4ea25|32114e5"
2ad3aa4 feat(38-01): add trainer_availability_slots table + TrainerAvailabilitySlot model + SLOT_BUFFER_MINUTES
3a4ea25 feat(38-01): add schedule repository + schemas + router + RBAC wiring
32114e5 feat(38-01): real schedule.service.py — publish_slot + cancel_slot + replace Phase 37 stubs
```

All claimed artifacts and commits are present.

---
*Phase: 38-schedule-module-booking-core*
*Plan: 01*
*Completed: 2026-05-17*
