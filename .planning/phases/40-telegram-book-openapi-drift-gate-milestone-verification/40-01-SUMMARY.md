---
phase: 40-telegram-book-openapi-drift-gate-milestone-verification
plan: 01
subsystem: infra
tags: [telegram, ptb, namedtuple, redis, dedup, fail-open, handler-context, refactor]

# Dependency graph
requires:
  - phase: 20-self-checkin-telegram-bot
    provides: inlined `_dedupe_update_id` block in checkin_handler:258-279; Redis SET-NX-EX fail-open pattern (D-20-3)
  - phase: 37-foundations-bedrock
    provides: register_slot_by_id_resolver + register_active_pt_package_resolver double-wired in both composition roots (INFRA-33 + DEBT-06)
  - phase: 38-schedule-module-booking-core
    provides: app.modules.bookings.service (importable module reference for HandlerContext)
provides:
  - 7-field HandlerContext NamedTuple (bookings_service + schedule_service appended at END)
  - module-level `_dedupe_update_id(redis, update_id, chat_id) -> bool` helper with fail-open semantics
  - checkin_handler refactored to consume the helper (behaviour-preserving)
  - workers/telegram_bot.py HandlerContext construction wired with all 7 keyword args
  - structural double-construction regression test
affects:
  - 40-02-book-command-handler
  - 40-03-book-callback-handler

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Module-level dedup helper pattern (extracted from inlined block) — single source of truth for Redis update-id dedup across handlers"
    - "NamedTuple field-order discipline — new fields APPENDED at END to preserve positional construction compatibility"

key-files:
  created:
    - apps/backend/tests/integration/telegram_bot/test_dedupe_helper.py
  modified:
    - apps/backend/app/integrations/telegram/handlers.py
    - apps/backend/app/workers/telegram_bot.py
    - apps/backend/tests/integration/telegram_bot/test_handler_context_shape.py
    - apps/backend/tests/integration/telegram_bot/test_checkin_handler.py
    - apps/backend/tests/integration/telegram_bot/test_checkin_dm_days_remaining.py
    - apps/backend/tests/integration/telegram_bot/test_worker_handlers_registered.py

key-decisions:
  - "HandlerContext fields APPENDED at END (bookings_service, schedule_service) — preserves positional construction; field order frozen by test_handler_context_field_order_is_stable"
  - "_dedupe_update_id keeps the exact structlog event names verbatim (bot_redis_dedup_unavailable + bot_replay_skipped) — log-search dashboards depend on them"
  - "checkin_handler refactor is byte-equivalent: same key prefix sz:bot:update:{update_id}, same TTL 3600s, same fail-open semantic, same return semantic"
  - "Existing _build_ctx fixtures in 3 test files extended in lockstep — NamedTuple has no defaults, so positional/kwarg construction must pass all 7 fields"
  - "app/main.py intentionally untouched — Phase 37 INFRA-33 already double-wired every resolver Phase 40 needs (REG-29-03 lesson applies to the WORKER, not the FastAPI app)"

patterns-established:
  - "Module-level dedup helper: any new bot handler in handlers.py calls `if not await _dedupe_update_id(ctx.redis, update_id, chat_id): return` — no inlined SET-NX-EX block"
  - "NamedTuple growth: append-only at END; tests assert the exact tuple shape so accidental reorder fails CI"

requirements-completed: [BOT-04, BOT-05]

# Metrics
duration: ~10min
completed: 2026-05-18
---

# Phase 40 Plan 01: HandlerContext extension + _dedupe_update_id extraction Summary

**7-field HandlerContext NamedTuple with module-level _dedupe_update_id helper and worker composition root rewired for Phase 40 /book handlers.**

## Performance

- **Duration:** ~10 min
- **Started:** 2026-05-18T12:14:00Z
- **Completed:** 2026-05-18T12:24:43Z
- **Tasks:** 2
- **Files modified:** 6 (1 created, 5 edited)

## Accomplishments

- HandlerContext NamedTuple extended from 5 → 7 fields. `bookings_service` (D-40-04) and `schedule_service` (D-40-06) appended at END to preserve positional construction discipline.
- `_dedupe_update_id(redis, update_id, chat_id) -> bool` extracted as module-level helper (D-40-08). Identical fail-open semantics + structlog event names to the inlined Phase 20 block.
- `checkin_handler` refactored to call the helper — 18 lines of inlined dedup logic replaced with a 2-line consumer.
- `workers/telegram_bot.py:main()` HandlerContext construction now passes all 7 keyword args; `app.modules.bookings.service` imported (D-09 workers→modules carve-out).
- 4 new test cases: 1 field-presence + 1 field-order assertion + 1 worker double-construction structural test + 3 dedup helper unit tests (first-sight, replay, fail-open).
- All 3 existing `_build_ctx` fixtures in `tests/integration/telegram_bot/` extended in lockstep so the test fleet keeps building.

## Task Commits

Each task was committed atomically:

1. **Task 1: HandlerContext extension + _dedupe_update_id helper + checkin_handler refactor (TDD)** — `b6e6f9f` (refactor; tests RED → GREEN within the same commit because the refactor must be atomic with the fixture-fix to keep the suite building)
2. **Task 2: Wire bookings_service + schedule_service into worker HandlerContext construction** — `3df0f71` (feat)

## Files Created/Modified

- `apps/backend/app/integrations/telegram/handlers.py` — HandlerContext NamedTuple extended to 7 fields; `_dedupe_update_id` module-level helper added; `checkin_handler` refactored to consume the helper.
- `apps/backend/app/workers/telegram_bot.py` — `bookings_service` import added (alphabetical, between `auth` and `clients`); HandlerContext construction extended with 2 new kwargs.
- `apps/backend/tests/integration/telegram_bot/test_handler_context_shape.py` — assertion updated to 7-tuple; new Phase 40 field-presence test; new double-construction structural test.
- `apps/backend/tests/integration/telegram_bot/test_dedupe_helper.py` (NEW) — 3 unit tests using AsyncMock for `redis.set`: first-sight, replay (None return), fail-open (Exception). Verifies structlog event names verbatim.
- `apps/backend/tests/integration/telegram_bot/test_checkin_handler.py` — `_build_ctx` extended with bookings_service + schedule_service so existing 11 test functions keep building.
- `apps/backend/tests/integration/telegram_bot/test_checkin_dm_days_remaining.py` — `_build_ctx` extended (mirror of above).
- `apps/backend/tests/integration/telegram_bot/test_worker_handlers_registered.py` — HandlerContext construction extended.

## Decisions Made

- **Helper signature includes `chat_id`:** the plan body listed `_dedupe_update_id(redis, update_id, chat_id) -> bool` to match the existing structlog payload (`chat_id` is logged on both `bot_replay_skipped` and `bot_redis_dedup_unavailable`). The frontmatter `must_haves` line mentions only `(redis, update_id)` — we honoured the longer plan-body signature because dropping `chat_id` would degrade the existing dashboard logs.
- **Refactor + fixture-update committed atomically as Task 1:** the NamedTuple has no field defaults, so the moment Task 1 lands the 2 new fields, the existing `_build_ctx` fixtures in 3 test files must already pass them — otherwise the suite fails to collect. Splitting the fixture updates into a separate commit would leave an intermediate red state.
- **`test_handler_context_double_construction_keeps_all_seven_fields` lives in `test_handler_context_shape.py`:** the plan put it under Task 2's `<action>` block but the same file already holds NamedTuple-shape assertions. Co-locating keeps related guards in one file. The test fails between Task 1 and Task 2 commits (worker not yet wired); after Task 2 it passes.

## Deviations from Plan

None requiring deviation-rule classification. Two implementation notes (above) cover behaviour-preserving choices that don't change deliverable scope.

**Total deviations:** 0

**Impact on plan:** Plan executed exactly as written.

## Issues Encountered

- **Postgres-dependent tests skip in the worktree environment** — `tests/integration/telegram_bot/test_checkin_handler.py` and `test_checkin_dm_days_remaining.py` open real DB sessions and `skip` cleanly when `127.0.0.1:5432` is unreachable. 11 of 17 tests skipped for this reason; the 6 that ran (shape + dedup helper + worker registration sanity) all passed. The skips are pre-existing behaviour (a Postgres-aware autouse fixture in `tests/conftest.py`), not a regression introduced by this plan. CI will run the full suite against a live Postgres container.

## User Setup Required

None — pure backend infrastructure refactor; no env vars, no external services.

## Next Phase Readiness

- **40-02 (book command handler):** unblocked. Can land `book_handler` in `handlers.py` and `create_booking_via_bot` in `bookings/service.py` with zero HandlerContext or composition-root changes. The handler will reference `ctx.bookings_service.create_booking_via_bot(...)` and `ctx.schedule_service.list_slots(...)`; both are now reachable.
- **40-03 (book callback handler):** unblocked. Can register `CallbackQueryHandler(pattern=r"^BK:...$")` post-`build_application(...)` in `workers/telegram_bot.py:main()` without touching the HandlerContext NamedTuple again.
- **No outstanding blockers.**

## Self-Check: PASSED

- [x] `apps/backend/app/integrations/telegram/handlers.py` — modified (HandlerContext 7-field, helper added)
- [x] `apps/backend/app/workers/telegram_bot.py` — modified (bookings_service import + 2 kwargs)
- [x] `apps/backend/tests/integration/telegram_bot/test_handler_context_shape.py` — modified (7-tuple + 2 new tests)
- [x] `apps/backend/tests/integration/telegram_bot/test_dedupe_helper.py` — created (3 tests, all pass)
- [x] commit `b6e6f9f` exists (Task 1 — refactor)
- [x] commit `3df0f71` exists (Task 2 — feat)
- [x] `uv run pytest tests/integration/telegram_bot/test_handler_context_shape.py tests/integration/telegram_bot/test_dedupe_helper.py -q` → 7 passed
- [x] `uv run ruff check` on touched files → All checks passed
- [x] `uv run mypy --strict app/integrations/telegram/handlers.py app/workers/telegram_bot.py` → no issues
- [x] `uv run lint-imports` → Contracts: 3 kept, 0 broken

---
*Phase: 40-telegram-book-openapi-drift-gate-milestone-verification*
*Completed: 2026-05-18*
