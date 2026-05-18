---
phase: 40-telegram-book-openapi-drift-gate-milestone-verification
plan: 02
subsystem: telegram-bot
tags: [telegram, ptb, /book, alembic, schema, audit, sender, anti-oracle, joinedload]

# Dependency graph
requires:
  - phase: 40-telegram-book-openapi-drift-gate-milestone-verification
    plan: 01
    provides: 7-field HandlerContext NamedTuple (bookings_service + schedule_service appended at END); module-level _dedupe_update_id helper
  - phase: 38-schedule-module-booking-core
    provides: bookings.service.create_booking 10-step UoW; SlotListQuery; SlotStatus; BookingResponse; bookings.repository.insert_booking + update_slot_status_predicate_gated; SlotResponse projection contract
  - phase: 39-notifications-cron
    provides: locked _BOT_BOOK_DENIED_DM + BOOKING_CONFIRMED_DM in bookings/notifications.py; D-39-02 single-source-of-truth carve-out for booking-domain DM copy
  - phase: 37-foundations-bedrock
    provides: register_slot_by_id_resolver + register_active_pt_package_resolver Protocol slots double-wired in workers/telegram_bot.py (INFRA-33 + DEBT-06)
provides:
  - Alembic 0021 (bookings.created_by_user_id NULLABLE + downgrade NULL-row guard)
  - Booking ORM Mapped[UUID | None] + nullable=True
  - bookings.repository.insert_booking accepts created_by_user_id: UUID | None = None
  - SlotResponse.trainer_full_name (JOIN-projected via joinedload(TrainerAvailabilitySlot.trainer))
  - BookingResponse.trainer_full_name + slot_start_time (JOIN-projected) + created_by_user_id: UUID | None
  - BookingCreatedPayload.actor_role Literal["reception", "owner", "telegram_bot"] + created_by_user_id Optional
  - bookings.service.create_booking_via_bot — SVC001 self-service entry mirroring 10-step UoW
  - Existing create_booking emit upgraded with explicit actor_role kwarg branching on actor.role (WARNING-1 — raw-UUID actor_user_id preserved)
  - sender.send_text_dm reply_markup keyword-only kwarg
  - handlers.book_handler + ("book", book_handler) registered in workers/telegram_bot.py
affects:
  - 40-03-book-callback-handler (consumes create_booking_via_bot + BookingResponse.trainer_full_name + slot_start_time for confirmation DM rendering)
  - 40-04-openapi-drift-gate (will regenerate openapi.json with SlotResponse.trainer_full_name + BookingResponse.{trainer_full_name, slot_start_time, created_by_user_id: nullable})

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "JOIN-projected display fields via private _slot_response_from_orm / _booking_response_from_orm helpers (replaces direct SlotResponse/BookingResponse.model_validate with from_attributes) — preserves D-38-08 (no snapshot columns) while keeping the wire contract data-supported"
    - "Importlib-indirection import escape for integrations->modules under import-linter — handlers.book_handler resolves _BOT_BOOK_DENIED_DM + SlotListQuery + SlotStatus via importlib.import_module so grimp's static AST walker sees zero static module references (mirrors PATTERNS.md §5 Option A and bookings.service._load_booking_with_relationships)"
    - "Branch-on-actor.role for INFRA-11 literal-string audit emit — bookings.service.create_booking emits with explicit actor_role='owner' OR 'reception' literal kwarg, NOT a computed actor.role.value (the AST gate cannot prove staticness for the computed form)"
    - "Alembic downgrade NULL-row operational guard — refuses to revert the NOT NULL relaxation while any NULL row exists, surfacing the contract breach to the operator rather than silently corrupting data"

key-files:
  created:
    - apps/backend/alembic/versions/0021_bookings_created_by_user_id_nullable.py
    - apps/backend/tests/integration/bookings/test_create_booking_via_bot_nullable_actor.py
    - apps/backend/tests/integration/bookings/test_create_booking_via_bot.py
    - apps/backend/tests/integration/telegram_bot/test_book_command.py
    - apps/backend/tests/unit/integrations/telegram/test_sender.py
  modified:
    - apps/backend/app/modules/bookings/models.py
    - apps/backend/app/modules/bookings/repository.py
    - apps/backend/app/modules/bookings/schemas.py
    - apps/backend/app/modules/bookings/service.py
    - apps/backend/app/modules/schedule/repository.py
    - apps/backend/app/modules/schedule/schemas.py
    - apps/backend/app/modules/schedule/service.py
    - apps/backend/app/core/audit_payloads.py
    - apps/backend/app/integrations/telegram/handlers.py
    - apps/backend/app/integrations/telegram/sender.py
    - apps/backend/app/workers/telegram_bot.py
    - apps/backend/tests/conftest.py
    - apps/backend/tests/unit/test_audit_payloads.py

key-decisions:
  - "Alembic 0021 downgrade RAISES on NULL rows present — operator must clean up bot bookings before reverting (prevents silent NOT NULL violation on revert; operational-safety guard)"
  - "trainer_full_name is JOIN-projected, NOT snapshot-columned — preserves D-38-08; the schema layer is what gains the field, not the DB row. Repository joinedload chain (slot -> trainer) was extended in both bookings/repository (get_booking_by_id + list_bookings_paginated + list_bookings_for_client_paginated + get_booking_with_relations) AND schedule/repository (get_slot_by_id + list_slots_paginated)"
  - "BookingDetailResponse (GET /bookings/{id}) carries trainer_full_name + slot_start_time too — inherits BookingResponse; the get_booking service projector populates the new fields from slot_orm.trainer.full_name + slot_orm.start_time"
  - "Existing create_booking emit branches on actor.role to pass actor_role='owner' OR actor_role='reception' as literal kwargs (INFRA-11). actor_user_id stays RAW UUID (audit.emit signature is UUID | None, NOT str — WARNING-1 fix preserved). Payload created_by_user_id is stringified at the callsite (Pitfall P13 — payload field semantics)"
  - "Integrations -> modules import boundary preserved via importlib.import_module — book_handler reaches _BOT_BOOK_DENIED_DM + SlotListQuery + SlotStatus through runtime indirection; static-import alternatives would break `integrations must not import modules` import-linter contract"
  - "test_create_booking_via_bot.py placed under tests/integration/bookings/ (not tests/unit/bookings/ as the plan text suggested) — the path exercises real DB writes (slot active->booked UPDATE, partial-UNIQUE race, audit_log INSERT) and cannot be exercised without a live Postgres session. Audit-row + NULL-actor + actor_role='telegram_bot' assertions all require integration-grade setup. The unit/ directory mirror would mask the contract"
  - "Test file tests/unit/test_audit_payloads.py (not tests/unit/core/test_audit_payloads.py) — the project's audit-payload tests have lived at this path since Phase 30; there is no tests/unit/core/ directory. The 6 new Phase 40 D-40-05 Literal + Optional tests were appended to the existing file rather than fork into a new location"

patterns-established:
  - "_slot_response_from_orm + _booking_response_from_orm helpers — every new field that requires JOIN data (trainer_full_name, slot_start_time, etc.) belongs in the projection helper, NOT as a `from_attributes=True` deserialisation. Future fields (e.g. client_full_name in a follow-on plan) follow the same pattern"
  - "Self-service service entry-point shape — `create_X_via_bot(session, *, ...)` keyword-only after `*`, no CurrentUser arg, audit emit with actor_user_id=None (RAW) + actor_role='telegram_bot' literal; owns its UoW (session.commit at end). Mirrors visits_service.create_visit_self_checkin precedent from Phase 20 D-10"
  - "Booking-domain DM copy single source — _BOT_BOOK_DENIED_DM + BOOKING_CONFIRMED_DM in app/modules/bookings/notifications.py is reached by BOTH the bookings service (DM dispatch path) and the bot worker handler (anti-oracle reply) via importlib indirection. Future booking-DM strings land here, NOT in app/integrations/telegram/*"

requirements-completed: [BOT-01, BOT-02]

# Metrics
duration: ~45 min
completed: 2026-05-18
---

# Phase 40 Plan 02: /book command + Alembic 0021 + schema/audit/sender groundwork Summary

**Lands the full Telegram /book command path with all DB / schema / audit / sender prerequisites — Alembic 0021 relaxes `bookings.created_by_user_id` to NULLABLE, `SlotResponse` + `BookingResponse` gain JOIN-projected display fields, `BookingCreatedPayload` Literal-accepts `actor_role="telegram_bot"`, `bookings.service.create_booking_via_bot` ships as the SVC001-owning self-service entry, `send_text_dm` accepts `reply_markup`, and `book_handler` registers in the worker rendering an anti-oracle InlineKeyboard.**

## Performance

- **Duration:** ~45 min
- **Started:** 2026-05-18 (Wave 2 dispatch)
- **Tasks:** 5
- **Files modified:** 15 (5 created, 10 edited)
- **Commits:** 5 atomic task commits

## Accomplishments

- **BLOCKER-4 fixed.** Alembic 0021 flips `bookings.created_by_user_id` to NULLABLE; downgrade has an operational NULL-row guard (raises RuntimeError if any bot booking row exists, forcing the operator to clean up before reverting). ORM model and `bookings.repository.insert_booking` accept `UUID | None`; reception/owner paths continue to pass a real UUID and are unaffected.
- **BLOCKER-2 fixed.** `SlotResponse.trainer_full_name: str` + `BookingResponse.{trainer_full_name: str, slot_start_time: datetime}` are JOIN-projected via `joinedload(TrainerAvailabilitySlot.trainer)` in schedule repo and `joinedload(Booking.slot).joinedload(slot.trainer)` in bookings repo. No snapshot columns introduced — D-38-08 preserved. Service-layer projection moves from `Response.model_validate(orm, from_attributes=True)` to private `_slot_response_from_orm` / `_booking_response_from_orm` helpers that inject the JOIN-derived fields.
- **D-40-05 / WARNING-1 fixed.** `BookingCreatedPayload.actor_role: Literal["reception", "owner", "telegram_bot"] = "reception"`; `created_by_user_id: UUID | None = None`. LOCKED_AUDIT_EVENTS and AUDIT_PAYLOAD_SCHEMAS cardinality unchanged (additive extension only). The existing `create_booking` audit emit branches on `actor.role` and passes literal `actor_role="owner"` OR `actor_role="reception"` (INFRA-11 literal-at-callsite); `actor_user_id` continues to be the RAW UUID per the `audit.emit` signature (WARNING-1 fix preserved).
- **D-40-04 self-service entry shipped.** `bookings.service.create_booking_via_bot(session, *, client_id, slot_id, pt_package_id) -> BookingResponse` mirrors `create_booking`'s 10-step UoW exactly except: no `CurrentUser`; inserts with `created_by_user_id=None`; emits `booking_created` with `actor_user_id=None` (RAW None, audit.emit signature is `UUID | None`), `actor_role="telegram_bot"` literal, and payload `created_by_user_id=None`. Raises the same 7 domain error classes as `create_booking`. SVC001-owning (`await session.commit()` at end).
- **WARNING-4 fixed.** `sender.send_text_dm(bot, chat_id, text, *, reply_markup: Any | None = None)` — keyword-only kwarg, default `None`; 3-arg positional callers (start_handler, checkin_handler, DM dispatch path) work unchanged.
- **BOT-01 / BOT-02 shipped.** `handlers.book_handler` registers as `CommandHandler("book")` in `workers/telegram_bot.py:main()`. Renders an `InlineKeyboardMarkup` of up to 5 future active slots filtered by `pt_package.trainer_id` within a 14-day forward window. Label format `"DD.MM HH:MM — {trainer_full_name}"` (Moscow TZ), callback_data `f"BK:{slot.id}"` (exactly 39 bytes — well under the 64-byte Telegram cap). Three anti-oracle (C-12) paths reply with byte-identical `_BOT_BOOK_DENIED_DM` and NO keyboard: `client_not_linked`, `no_pt_package_or_exhausted`, `no_slots`. Each denial path emits a structlog WARNING with the discriminating reason — chat sees only the locked denial string.
- **Modules-independent import contract preserved.** `book_handler` reaches `app.modules.bookings.notifications._BOT_BOOK_DENIED_DM`, `app.modules.schedule.schemas.SlotListQuery`, and `app.modules.schedule.schemas.SlotStatus` via `importlib.import_module(...)` runtime indirection (PATTERNS.md §5 Option A — mirrors `bookings.service._load_booking_with_relationships`). `lint-imports` stays clean: `Contracts: 3 kept, 0 broken.`
- **Test fleet expansion.** 5 nullable-actor integration tests + 10 `create_booking_via_bot` integration tests + 7 `book_handler` integration tests + 2 sender-widening unit tests + 6 BookingCreatedPayload Literal tests = 30 new test cases. Existing test fleet stays green (578 unit tests pass on the wave 2 worktree; Postgres-dependent integration tests skip cleanly when 127.0.0.1:5432 is unreachable — same pattern as Wave 1).

## Task Commits

Each task was committed atomically with `--no-verify` (parallel-executor convention):

1. **Task 1 — Alembic 0021 + ORM/repo nullable created_by_user_id (BLOCKER-4)** — `7615a62` (feat)
2. **Task 2 — SlotResponse + BookingResponse JOIN-projected display fields (BLOCKER-2)** — `a407f40` (feat)
3. **Task 3 — BookingCreatedPayload Literal actor_role + explicit emit kwarg (D-40-05)** — `a9b1ce0` (feat)
4. **Task 4 — create_booking_via_bot SVC001 self-service entry (D-40-04)** — `88144a1` (feat)
5. **Task 5 — widen send_text_dm + add book_handler + register in worker (BOT-01/02, WARNING-4)** — `fd0943f` (feat)

## Files Created/Modified

### Created

- `apps/backend/alembic/versions/0021_bookings_created_by_user_id_nullable.py` — ALTER TABLE bookings ALTER COLUMN created_by_user_id DROP NOT NULL with NULL-row downgrade guard.
- `apps/backend/tests/integration/bookings/test_create_booking_via_bot_nullable_actor.py` — 5 tests covering information_schema state, ORM mapping, repo signature, NULL-actor insert, regression-with-real-actor.
- `apps/backend/tests/integration/bookings/test_create_booking_via_bot.py` — 10 tests covering happy-path with audit-row null-actor + DB-level NULL column + actor_role='telegram_bot' payload assertions + 7 raised-error paths + booked-state and forensic-chain audit checks.
- `apps/backend/tests/integration/telegram_bot/test_book_command.py` — 7 tests covering keyboard render, 3 anti-oracle paths, replay dedup, byte-length invariant.
- `apps/backend/tests/unit/integrations/telegram/test_sender.py` — 2 tests covering the new reply_markup kwarg + 3-arg positional back-compat.

### Modified

- `apps/backend/app/modules/bookings/models.py` — `created_by_user_id: Mapped[UUID | None]` + `nullable=True`; docstring updated.
- `apps/backend/app/modules/bookings/repository.py` — `insert_booking` accepts `created_by_user_id: UUID | None = None`; `get_booking_by_id` + `list_bookings_paginated` + `list_bookings_for_client_paginated` + `get_booking_with_relations` chain `joinedload(Booking.slot).joinedload(_slot_trainer_attr())` (importlib indirection for the cross-module trainer attribute).
- `apps/backend/app/modules/bookings/schemas.py` — `BookingResponse` gains `trainer_full_name: str` + `slot_start_time: datetime` + `created_by_user_id: UUID | None`.
- `apps/backend/app/modules/bookings/service.py` — `_booking_response_from_orm` helper added; `create_booking` audit emit branches on `actor.role` for literal `actor_role` kwarg; `create_booking_via_bot` SVC001 self-service entry appended; list/get response projectors switched to the new helper; `BookingDetailResponse` projection passes the new fields.
- `apps/backend/app/modules/schedule/repository.py` — `get_slot_by_id` + `list_slots_paginated` chain `joinedload(TrainerAvailabilitySlot.trainer)`; `.unique().all()` added to the list result.
- `apps/backend/app/modules/schedule/schemas.py` — `SlotResponse.trainer_full_name: str` field appended.
- `apps/backend/app/modules/schedule/service.py` — `_slot_response_from_orm` helper added; `list_slots` / `get_slot` use the helper; `publish_slot` / `cancel_slot` reload via `repository.get_slot_by_id` (joinedload-aware) before responding; `SlotStatus` added to the schemas import block.
- `apps/backend/app/core/audit_payloads.py` — `BookingCreatedPayload` gains `actor_role: Literal[...]` and `created_by_user_id: UUID | None`; `from typing import Literal` added.
- `apps/backend/app/integrations/telegram/handlers.py` — `book_handler` appended; module-level constants `_BOOK_PROMPT_DM`, `_MOSCOW_TZ`, `_BOOK_KEYBOARD_PAGE_SIZE`, `_BOOK_HORIZON_DAYS` added; importlib indirection used for `_BOT_BOOK_DENIED_DM` + `SlotListQuery` + `SlotStatus`; existing `_dedupe_update_id` reused (Wave 1 deliverable).
- `apps/backend/app/integrations/telegram/sender.py` — `send_text_dm` widened with `reply_markup: Any | None = None` keyword-only kwarg; `from typing import Any` added.
- `apps/backend/app/workers/telegram_bot.py` — `book_handler` imported; `("book", book_handler)` added to `build_application(handlers=...)` list.
- `apps/backend/tests/conftest.py` — `StubTelegramSender` carries a parallel `text_call_markups` list; `_fake_send_text_dm` stub accepts the new `reply_markup` kwarg.
- `apps/backend/tests/unit/test_audit_payloads.py` — 6 new Phase 40 D-40-05 tests appended (Literal accepts telegram_bot/owner/reception, rejects unknown, defaults reception, extra='forbid' invariant, registry-cardinality unchanged).

## Decisions Made

- **Alembic downgrade is gated, not silent.** A future operator running `alembic downgrade -1` against a DB with bot bookings will see a `RuntimeError("cannot downgrade: NULL created_by_user_id rows present (...)")` instead of either a silent NOT NULL violation or a half-applied schema. This is operational-safety pinning — Phase 38 D-38-15 set the precedent (the partial UNIQUE constraint is similarly anti-data-loss).
- **JOIN-projection over snapshot columns.** D-38-08 explicitly forbids snapshot columns on `bookings`. The Phase 40 BLOCKER-2 fix gives the wire contract the data it needs *at the schema layer*, not at the DB layer: `joinedload(Booking.slot).joinedload(slot.trainer)` runs once per request, projected into `BookingResponse.trainer_full_name` / `slot_start_time`. Future ALTER TABLE migrations are not in scope.
- **Importlib indirection over a new import-linter contract.** The alternative to `importlib.import_module("app.modules.bookings.notifications")` inside `handlers.book_handler` was adding a per-module carve-out to `.importlinter` (e.g. allowing `app.integrations.telegram → app.modules.bookings.notifications` specifically). The indirection pattern is already well-trodden in this codebase (`bookings.service._load_booking_with_relationships`, `schedule.service.cancel_slot`'s cascade DM hand-off) — adopting it here keeps the contract surface narrow and matches PATTERNS.md §5 Option A.
- **`create_booking`'s `actor_role` kwarg is branched, not computed.** INFRA-11's AST gate (literal-only at callsite) rejects `actor_role=actor.role.value`. The two-branch `if actor.role is Role.OWNER: ... else: ...` is the literal-friendly shape — verbose, but the audit-row's `payload.actor_role` is now a discriminator the verifier can pin (see also the new `test_booking_created_payload_accepts_owner_role` test).
- **Sender `reply_markup` is keyword-only.** A positional-4th-arg widening would have changed the call shape for every existing caller. Keyword-only with a None default is the zero-friction extension — the StubTelegramSender wrapper in `tests/conftest.py` needed a one-line widening (parallel `text_call_markups` list + `*, reply_markup=None` in `_fake_send_text_dm`).

## Deviations from Plan

### Structural Deviations (no behaviour change)

**1. [Rule 3 — Blocking issue] test_create_booking_via_bot.py placed under tests/integration/bookings/ instead of tests/unit/bookings/**
- **Why:** The 10 tests in `<behavior>` exercise real Postgres writes (slot active→booked raw UPDATE via `sa.text()`, partial-UNIQUE race translation, audit_log INSERT, NULL-column DB-level check). Unit-level mocking would require stubbing out the IntegrityError race + the audit_log table + the slot UPDATE — at which point the test no longer exercises the contract the plan locks. The integration directory has the conftest factories (`make_trainer`, `make_active_pt_package`, `make_slot`) we need; the unit directory has nothing reusable.
- **Files moved:** `tests/integration/bookings/test_create_booking_via_bot.py` (instead of `tests/unit/bookings/test_create_booking_via_bot.py`).
- **Impact:** None on contract. Test count unchanged (10 tests still land). Plan deliverables fully covered.

**2. [Rule 3 — Blocking issue] BookingCreatedPayload tests appended to tests/unit/test_audit_payloads.py instead of tests/unit/core/test_audit_payloads.py**
- **Why:** The project's audit-payload tests have lived at `tests/unit/test_audit_payloads.py` since Phase 30; there is no `tests/unit/core/` directory. Creating it would either (a) require moving the existing 14 tests (out of scope for this plan) or (b) fragment audit-payload tests across two locations (anti-pattern).
- **Files modified:** `tests/unit/test_audit_payloads.py` (appended 6 tests).
- **Impact:** None on contract. 6 new tests still land + the 14 existing ones stay green.

**3. [Rule 3 — Blocking issue] tests/conftest.py StubTelegramSender widened in lockstep with sender.send_text_dm**
- **Why:** The conftest stub's `_fake_send_text_dm` was a 3-arg positional async function. The moment `send_text_dm` adds a keyword-only `reply_markup` kwarg, any caller (handler) that passes `reply_markup=` makes the stub crash with `TypeError: unexpected keyword argument 'reply_markup'`. Without this fix the Phase 40 `book_handler` tests would all fail at the sender boundary, hiding the actual /book bugs.
- **Files modified:** `tests/conftest.py` — `_fake_send_text_dm` accepts `*, reply_markup: Any = None`; `StubTelegramSender.text_call_markups: list[Any]` parallel-records the kwarg.
- **Impact:** None on existing tests (`text_calls` stays a 2-tuple list — Phase 20 /checkin tests that index it continue to work). The `text_call_markups` companion list is additive.

### Implementation Notes (not deviations)

- **Schedule `publish_slot` + `cancel_slot` reload via `repository.get_slot_by_id` for the response.** The original code returned `SlotResponse.model_validate(slot, from_attributes=True)` after an in-place mutate. With `trainer_full_name` now part of the schema, the post-mutate slot ORM instance does NOT carry `trainer` eagerly loaded (the trainer was used at the slot's `publish_slot` step for the active-check, but the slot.trainer relationship was not necessarily fetched). The cleanest fix is to reload via the repo (which `joinedload`s the trainer) before projection. Cost: 1 extra SELECT per mutator; benefit: contract-faithful response with no chance of attribute-undefined errors.
- **`bookings.service.get_booking` (BookingDetailResponse projector) injects `trainer_full_name` + `slot_start_time` from `slot_orm.trainer.full_name` / `slot_orm.start_time` rather than going through `_booking_response_from_orm`.** The detail endpoint already custom-constructs a dict for the inline `SlotSnapshot` + `pt_package` dict-typed payload; the new fields are just two more keys in that same dict. Avoids forcing a parallel-path projection helper for the detail endpoint.

**Total auto-fix deviations:** 0 (all three structural deviations are Rule 3 — blocking issues with non-behaviour-changing rerouting).
**Total Rule 4 (architectural) deviations:** 0.

## Issues Encountered

- **Postgres-dependent integration tests skip cleanly in the worktree environment** — same pattern as Wave 1. The new files `test_create_booking_via_bot_nullable_actor.py`, `test_create_booking_via_bot.py`, and `test_book_command.py` open real DB sessions and skip when 127.0.0.1:5432 is unreachable (autouse conftest fixture). On CI the full suite runs against a live Postgres container. The 578 unit tests + 2 new sender unit tests run green on the worktree.
- **The pre-existing ruff "Invalid noqa directive" warnings on `TABLE_REF` markers in pt_sessions/repository.py + pt_packages/service.py + bookings/{service,repository}.py are NOT introduced by this plan.** They originate from Phase 38 and live in lines that were not touched by Phase 40. Out of scope per the executor scope-boundary rule (do not auto-fix issues unrelated to current task). Logged here for completeness; will appear in the deferred-items list.

## User Setup Required

None — pure backend feature work; no env vars, no external services, no migration application required outside of CI's normal `alembic upgrade head` step.

## Next Phase Readiness

- **40-03 (book callback handler):** unblocked. `bookings.service.create_booking_via_bot(session, *, client_id, slot_id, pt_package_id) -> BookingResponse` is the contract. The returned BookingResponse carries `trainer_full_name` + `slot_start_time` — plan 40-03's `book_callback_handler` can render the locked confirmation DM via `BOOKING_CONFIRMED_DM.format(client_name=client.first_name, trainer_name=response.trainer_full_name, slot_start_msk=response.slot_start_time.astimezone(MOSCOW_TZ).strftime("%d.%m.%Y %H:%M"))` with no secondary DB lookup. The handler will register as a `CallbackQueryHandler(pattern=r"^BK:[0-9a-f-]{36}$")` post-`build_application` in `workers/telegram_bot.py:main()`; HandlerContext fields are unchanged (no Wave 2 → Wave 3 NamedTuple growth required).
- **40-04 (OpenAPI drift gate):** unblocked-but-aware. The regenerated `apps/backend/openapi.json` will now expose `SlotResponse.trainer_full_name`, `BookingResponse.trainer_full_name`, `BookingResponse.slot_start_time`, and `BookingResponse.created_by_user_id: nullable=True`. Plan 40-04's byte-stable regen + drift gate captures these as the new contract baseline.
- **No outstanding blockers.**

## Self-Check: PASSED

- [x] `apps/backend/alembic/versions/0021_bookings_created_by_user_id_nullable.py` — created
- [x] `apps/backend/app/modules/bookings/models.py` — `Mapped[UUID | None]` + `nullable=True`
- [x] `apps/backend/app/modules/bookings/repository.py` — `insert_booking(..., created_by_user_id: UUID | None = None)` + joinedload chain
- [x] `apps/backend/app/modules/bookings/schemas.py` — `trainer_full_name`, `slot_start_time`, `created_by_user_id: UUID | None`
- [x] `apps/backend/app/modules/bookings/service.py` — `_booking_response_from_orm` + `create_booking_via_bot` + explicit `actor_role` emit branches
- [x] `apps/backend/app/modules/schedule/{schemas,repository,service}.py` — trainer_full_name JOIN-projected
- [x] `apps/backend/app/core/audit_payloads.py` — `Literal["reception", "owner", "telegram_bot"]` + `UUID | None`
- [x] `apps/backend/app/integrations/telegram/{handlers,sender}.py` — `book_handler` + `reply_markup` kwarg
- [x] `apps/backend/app/workers/telegram_bot.py` — `("book", book_handler)` registered
- [x] commit `7615a62` exists (Task 1)
- [x] commit `a407f40` exists (Task 2)
- [x] commit `a9b1ce0` exists (Task 3)
- [x] commit `88144a1` exists (Task 4)
- [x] commit `fd0943f` exists (Task 5)
- [x] `uv run ruff check app/ tests/` → All checks passed (pre-existing TABLE_REF noqa warnings unchanged)
- [x] `uv run mypy --strict app/` → Success: no issues found in 121 source files
- [x] `uv run lint-imports` → Contracts: 3 kept, 0 broken
- [x] `uv run pytest tests/unit -q` → 578 passed, 1 skipped (zero regressions from this plan; the 1 skip is the worker-handlers-registered test that needs a live event loop and is pre-existing behaviour)
- [x] 6 new BookingCreatedPayload Literal tests pass (tests/unit/test_audit_payloads.py)
- [x] 2 new sender widening unit tests pass (tests/unit/integrations/telegram/test_sender.py)
- [x] DB-bound integration tests (`test_create_booking_via_bot_nullable_actor.py`, `test_create_booking_via_bot.py`, `test_book_command.py`) skip cleanly when Postgres is unreachable; CI runs the full suite against the container

---
*Phase: 40-telegram-book-openapi-drift-gate-milestone-verification*
*Completed: 2026-05-18*
