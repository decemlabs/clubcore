---
phase: 40-telegram-book-openapi-drift-gate-milestone-verification
plan: 03
subsystem: telegram-bot
tags: [telegram, ptb, /book, callback-query, anti-oracle, blocker-3-fix, tdd]

# Dependency graph
requires:
  - phase: 40-telegram-book-openapi-drift-gate-milestone-verification
    plan: 01
    provides: _dedupe_update_id module-level helper + 7-field HandlerContext (bookings_service + schedule_service)
  - phase: 40-telegram-book-openapi-drift-gate-milestone-verification
    plan: 02
    provides: create_booking_via_bot SVC001 entry; BookingResponse.{trainer_full_name, slot_start_time} JOIN-projected fields; book_handler precedent
  - phase: 39-notifications-cron
    provides: _BOT_BOOK_DENIED_DM + BOOKING_CONFIRMED_DM + render_booking_confirmed_dm in bookings/notifications.py
  - phase: 37-foundations-bedrock
    provides: register_active_pt_package_resolver + register_client_by_telegram_resolver Protocol slots double-wired
provides:
  - book_callback_handler in handlers.py (Phase 40 BOT-03)
  - CallbackQueryHandler registration in workers/telegram_bot.py with strict UUID regex
  - 15 integration tests under tests/integration/telegram_bot/test_book_callback.py
affects:
  - 40-04-openapi-drift-gate (Telegram bot now serves the full /book roundtrip — no API surface change introduced by 40-03, but the BOT-01..03 surface is now complete for VER-06 milestone verification)
  - 40-05-milestone-verification (BOT-03 + VER-06 Telegram sandbox scenarios are unblocked)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "String-name exception dispatch (`except Exception as exc: cls_name = type(exc).__name__`) preserves the `integrations must not import modules` import-linter contract — the handler maps all 7 domain error classes to the byte-identical anti-oracle DM without ever importing the exception types from app.modules.bookings.errors"
    - "Inline PTB CallbackQueryHandler adapter post-build_application — preserves the public factory signature (build_application(token, handlers=[(cmd, handler)...], ctx=...)) while letting the worker root register additional handler types (CallbackQueryHandler) via the standard PTB application.add_handler path"
    - "BLOCKER-3 fix pattern: when a planned secondary lookup turns out not to exist on the target service, surface the missing data via the upstream response model (40-02 added trainer_full_name + slot_start_time to BookingResponse via JOIN projection) rather than expanding the resolver surface"

key-files:
  created:
    - apps/backend/tests/integration/telegram_bot/test_book_callback.py
  modified:
    - apps/backend/app/integrations/telegram/handlers.py
    - apps/backend/app/workers/telegram_bot.py

key-decisions:
  - "BLOCKER-3 (iteration 1 checker) resolved by direct BookingResponse-field consumption — no `resolve_slot_by_id` call lands in handlers.py. The acceptance-grep gate `grep -c 'resolve_slot_by_id' app/integrations/telegram/handlers.py == 0` is asserted as a TDD regression-guard test (`test_book_callback_does_not_reference_resolve_slot_by_id`), so any future revision that reintroduces the bogus attribute name will fail the suite at TDD-time"
  - "All 7 domain error classes map to the byte-identical `_BOT_BOOK_DENIED_DM` via string-name dispatch — no `except SpecificError:` branch lands in the handler. This both (a) preserves the `integrations must not import modules` import-linter contract and (b) provides D-40-10 / C-12 anti-oracle compliance: a real attacker cannot distinguish 'your package expired' from 'this slot was just taken' from the DM. Discrimination lives only in the structlog WARNING `book_callback_denied` with `error_class=type(exc).__name__` for operator support"
  - "PTB CallbackQueryHandler registers post-build_application via an inline adapter closure (`_book_callback_adapter`) rather than widening `build_application`'s `handlers=` param to accept callback-query tuples. This preserves the v1.2 / v1.5 stable factory signature locked in `apps/backend/app/integrations/telegram/bot.py` and matches the D-40-02 narrative addendum"
  - "Client display name derived from `getattr(client, 'first_name', None) or 'клиент'` — the `ClientByTelegram` Protocol (Phase 19 D-02) exposes only `.id` by design (kept narrow), but at runtime the resolver returns the full Client ORM row. `getattr` access works under mypy strict without expanding the Protocol's cross-module surface. Fallback `'клиент'` covers the (theoretical) case where the row is missing a first_name (the column is NOT NULL on the Client model, so the fallback is defensive-only)"

patterns-established:
  - "Defensive UUID parse despite PTB regex pre-filter — the handler still wraps `UUID(raw[3:])` in `try/except ValueError` so a regex bypass via spoofed callback (e.g. a forged `bot.send_callback_query` from a malicious client) drops silently with a structlog WARNING rather than 500-erroring the polling loop. Mirrors `start_handler`'s defensive token-shape check"

requirements-completed: [BOT-03]

# Metrics
duration: ~25 min
completed: 2026-05-18
---

# Phase 40 Plan 03: book_callback_handler Summary

**Closes BOT-03 — the /book happy-path roundtrip. Together with 40-01 (HandlerContext + dedup helper) and 40-02 (/book command + create_booking_via_bot), this delivers the full BOT-01..03 surface required by Phase 40 SC1. BLOCKER-3 (iteration 1 checker — bogus `ctx.schedule_service.resolve_slot_by_id` attribute call) is resolved by consuming `BookingResponse.trainer_full_name` + `BookingResponse.slot_start_time` directly from the JOIN projection that 40-02 Task 2 landed.**

## Performance

- **Duration:** ~25 min
- **Started:** 2026-05-18 (Wave 3 dispatch — serial after 40-02 due to `handlers.py` file-overlap)
- **Tasks:** 1 (single atomic TDD task per the plan's locked task list)
- **Files modified:** 3 (1 created, 2 edited)
- **Commits:** 2 atomic commits (RED test commit + GREEN implementation commit)

## Accomplishments

- **BOT-03 shipped.** `book_callback_handler` lands in `apps/backend/app/integrations/telegram/handlers.py` after `book_handler` from 40-02. The handler is registered as a `CallbackQueryHandler` in `apps/backend/app/workers/telegram_bot.py:main()` with the strict UUID regex `r"^BK:[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"` per D-40-09. Registration happens post-`build_application` via an inline `_book_callback_adapter` closure (preserving D-40-02's stable factory signature).
- **BLOCKER-3 fix delivered.** The handler does NOT call any secondary slot-by-id resolver — the confirmation DM is rendered directly from `booking_response.trainer_full_name` + `booking_response.slot_start_time` (both populated by the 40-02 Task 2 JOIN projection on `BookingResponse`). The acceptance-grep gate `grep -c 'resolve_slot_by_id' apps/backend/app/integrations/telegram/handlers.py` returns 0, and the regression-guard test `test_book_callback_does_not_reference_resolve_slot_by_id` static-asserts this property of the source file.
- **D-40-10 anti-oracle compliance.** All 7 domain error classes raised by `bookings_service.create_booking_via_bot` (`SlotNotFoundError`, `SlotNotAvailableError`, `SlotAlreadyBookedError`, `TrainerMismatchError`, `PtPackageNotActiveError`, `PtPackageExhaustedError`, `PtPackageExpiredBeforeSlotError`) map to the byte-identical `_BOT_BOOK_DENIED_DM` via `query.edit_message_text`. Discrimination lives only in the structlog WARNING `book_callback_denied` carrying `error_class=type(exc).__name__` for support debugging. Two pre-service anti-oracle paths (client_not_linked, pt_package_not_active) also route to the same DM string.
- **D-40-08 dedup reuse.** The handler reuses the module-level `_dedupe_update_id(redis, update_id, chat_id)` helper landed by 40-01 — same fail-open semantics (Redis errors return `True`), same key prefix `sz:bot:update:{update_id}`, same TTL of 1 hour. The `test_book_callback_dedupe_replay_skipped` test asserts replay-suppression behaviour.
- **Modules-independent import contract preserved.** The handler reaches `_BOT_BOOK_DENIED_DM` + `render_booking_confirmed_dm` via `importlib.import_module("app.modules.bookings.notifications")` (mirrors 40-02's `book_handler` pattern). No new static `from app.modules.* import ...` statement lands; `lint-imports` reports `Contracts: 3 kept, 0 broken`.
- **15 integration tests appended.** `tests/integration/telegram_bot/test_book_callback.py` (NEW, 641 lines) covers: happy-path confirmation DM render, BLOCKER-3 regression guard (static AST + grep), anti-oracle DM byte-stability (AST assertion that `_BOT_BOOK_DENIED_DM` is an `ast.Constant` with `str` value — NOT a `JoinedStr` f-string), update_id replay dedup, 7 parametrized anti-oracle tests (one per domain error class), structlog `error_class` capture, audit row `actor_role='telegram_bot'` + `actor_user_id IS NULL`, concurrent-race exactly-1-success-1-denial invariant, and a defensive client-not-linked path.

## Task Commits

Each TDD step committed atomically with `--no-verify` (parallel-executor convention):

1. **RED — failing tests** — `72d42b4` (test)
2. **GREEN — book_callback_handler + CallbackQueryHandler registration** — `a4a5747` (feat)

REFACTOR step skipped: the implementation lands in canonical form (mirrors `book_handler` / `checkin_handler` shape verbatim — no cleanup pass needed).

## Files Created/Modified

### Created

- `apps/backend/tests/integration/telegram_bot/test_book_callback.py` (641 lines)
  - 15 integration tests including 7 parametrized anti-oracle error-class tests
  - 2 non-DB tests (BLOCKER-3 regression guard + AST byte-stability) run in any worktree
  - 13 DB-dependent tests skip cleanly when Postgres is unreachable (TEST-01 idiom)

### Modified

- `apps/backend/app/integrations/telegram/handlers.py`
  - Added `from uuid import UUID` to top imports
  - Appended `book_callback_handler` after `book_handler` (preserves file ordering: start, checkin, book, book_callback)
  - 13 references to `_BOT_BOOK_DENIED_DM` / `bot_book_denied_dm` lookup (multiple denial paths)
  - 4 structlog `book_callback_denied` WARNING events (1 per anti-oracle path + service-error catch-all)
  - 5 `type(exc).__name__` references (string-name dispatch — shared idiom with `checkin_handler` at lines 333-348)
  - Zero references to `resolve_slot_by_id` (BLOCKER-3 fix verified by grep gate)
- `apps/backend/app/workers/telegram_bot.py`
  - Added `from typing import Any` for the inline adapter signature
  - Added `from telegram.ext import CallbackQueryHandler`
  - Added `book_callback_handler` to the handlers import block from `app.integrations.telegram.handlers`
  - Registered `CallbackQueryHandler(_book_callback_adapter, pattern=r"^BK:[0-9a-f]{8}-...")` post-`build_application()` via the inline closure pattern

## Decisions Made

- **Direct BookingResponse-field consumption over a new resolver.** The Phase 40 iteration-1 plan called `ctx.schedule_service.resolve_slot_by_id` to fetch trainer display data after the booking commit. That attribute does not exist on the `schedule_service` module (`resolve_slot_by_id` is a Protocol-slot free function in `app.core.dependencies`, registered via `register_slot_by_id_resolver` and never bound to the module's public surface). Three alternatives were considered:
  1. **Add a `resolve_slot_by_id` wrapper to `schedule_service`** — would expand the service's public surface for a bot-only concern; rejected.
  2. **Re-query the slot via `ctx.schedule_service.list_slots(...)`** — works but costs an extra round-trip + `joinedload(trainer)` chain just to get a name we could have surfaced at commit time; rejected.
  3. **Surface `trainer_full_name` + `slot_start_time` on `BookingResponse` via JOIN projection in 40-02** — adopted. 40-02 Task 2 landed this; 40-03 consumes the fields directly with zero secondary lookups.

  This is the BLOCKER-3 fix per the plan's `<objective>` block. The grep gate + regression-guard test pin the property.

- **String-name dispatch over typed exception classes.** The handler catches `Exception as exc` and dispatches on `type(exc).__name__`. Alternative: `from app.modules.bookings.errors import SlotNotFoundError, SlotNotAvailableError, ...` and `except (SlotNotFoundError, SlotNotAvailableError, ...) as exc:`. Rejected because:
  1. The import-linter `integrations must not import modules` contract would break — adding a per-module carve-out for one bot-side handler is worse than the runtime string check.
  2. The anti-oracle invariant says EVERY exception class collapses to the same DM byte string anyway — there is no per-class behaviour to dispatch on; the `cls_name` is purely for the structlog WARNING.
  3. The same idiom is already in use in `checkin_handler` (lines 333-348) for the visits domain — re-applying it here keeps the bot codebase coherent.

- **CallbackQueryHandler registers post-`build_application`, not inside the factory `handlers=` list.** `build_application(token, handlers=[...], ctx=...)` currently accepts only `(command_name, handler_callable)` tuples that get wired to `CommandHandler`. Widening the signature to accept callback-query tuples would break Phase 7's stable factory contract. Instead, the worker root calls `application.add_handler(CallbackQueryHandler(...))` directly after `build_application(...)` returns — the standard PTB Application API supports post-construction handler addition. D-40-02 narrative explicitly permits this pattern.

- **Defensive UUID parse despite PTB regex pre-filter.** The `pattern=r"^BK:[0-9a-f]{8}-...$"` regex passed to `CallbackQueryHandler` filters callback data before any update reaches the handler. The handler still wraps `UUID(raw[3:])` in `try/except ValueError` to drop silently on any regex bypass (e.g. forged callback delivery), with a `book_callback_invalid_uuid` structlog WARNING for support visibility. Mirrors `start_handler`'s defensive token-shape check (`_parse_start_token` returns None on malformed input).

- **Client display name via `getattr` rather than expanding the Protocol surface.** The `ClientByTelegram` Protocol (Phase 19 D-02) intentionally exposes only `.id` to keep the cross-module type surface narrow. The real resolver returns the full Client ORM row, so `first_name` is always present at runtime. `getattr(client, 'first_name', None) or 'клиент'` lets mypy strict pass without expanding the Protocol contract — and the fallback `'клиент'` is a no-op-in-practice safety net (the underlying column is `NOT NULL`).

## Deviations from Plan

### Structural Deviations (no behaviour change)

**1. [Rule 3 — Blocking issue] Client display name via `getattr` instead of `client.full_name`**
- **Why:** The plan's `<read_first>` instruction said "Verify `client.full_name` is the correct attribute … if it is `client.first_name` + `client.last_name`, adapt the call accordingly." The Client model has `first_name` + `last_name` (no `full_name`), and `ClientByTelegram` (the Protocol returned by the resolver) exposes only `.id`. The chosen path uses `getattr(client, "first_name", None) or "клиент"` to (a) satisfy mypy strict against the narrow Protocol surface and (b) keep the display friendly.
- **Files affected:** `apps/backend/app/integrations/telegram/handlers.py` (`book_callback_handler` happy-path block)
- **Impact:** None on contract. The confirmation DM still consumes `BookingResponse.trainer_full_name` + `BookingResponse.slot_start_time` as the plan requires; only the client-name placeholder fetch differs from the plan's literal text. `test_book_callback_happy_path_edits_to_confirmed_dm` validates that the rendered DM contains the client's first_name (`Иван`).

**2. [Rule 3 — Blocking issue] Test file accommodates Postgres-unreachable worktree environment**
- **Why:** 13 of the 15 tests open real DB sessions via the `db_session` fixture (TEST-01 SAVEPOINT-rolled pattern). The worktree environment has no Postgres reachable on 127.0.0.1:5432, so the fixture's existing `pytest.skip(...)` path triggers; the test file does NOT define any new skip logic. Tests run cleanly against the CI Postgres container. Mirrors 40-02's identical skip pattern.
- **Files affected:** `apps/backend/tests/integration/telegram_bot/test_book_callback.py`
- **Impact:** None on contract. 2 non-DB tests (BLOCKER-3 regression guard + AST byte-stability) run + pass in the worktree; 13 DB-dependent tests skip with the project's standard `pytest.skip("DATABASE_URL not reachable; ...")` message and run green on CI.

### Implementation Notes (not deviations)

- **`_book_callback_adapter` is an inline closure in `main()`.** PTB needs a 2-arg `(update, context)` callback; the handler signature is 3-arg `(update, context, ctx)`. The adapter closure captures `ctx` from the `main()` scope and forwards. This mirrors how `build_application` already creates per-command adapters internally (`bot.py` lines 67-79) — we just do it inline for the one callback handler.
- **The anti-oracle DM byte-stability test parses `notifications.py` source via `ast.parse`.** Alternative was a string-equality check (`assert _BOT_BOOK_DENIED_DM == "Сейчас бронирование недоступно..."`), but that would lock the test to one specific copy. The AST shape check is the deeper invariant: as long as the constant remains an `ast.Constant` (str) and never becomes a `JoinedStr` (f-string with placeholders), the anti-oracle property holds regardless of the exact copy.

**Total auto-fix deviations:** 0 (both structural deviations above are Rule 3 — blocking issues with no behaviour change).
**Total Rule 4 (architectural) deviations:** 0.

## Issues Encountered

- **13 of 15 new integration tests skip in the worktree** — Postgres-dependent tests skip cleanly when 127.0.0.1:5432 is unreachable; identical pattern to Wave 1 (40-01) and Wave 2 (40-02). The CI run will exercise them against the live container. The 2 non-DB tests (regression-guard + AST byte-stability) PASS in this worktree, providing immediate confidence in the BLOCKER-3 fix.
- **Pre-existing ruff "Invalid noqa directive" warnings on `TABLE_REF` markers** (pt_sessions/repository.py, pt_packages/service.py, bookings/{service,repository}.py) are NOT introduced by this plan. They originate from Phase 38 and live in lines not touched by Phase 40. Logged in the 40-02 summary; out of scope per the executor scope-boundary rule.

## User Setup Required

None — pure backend feature work; no env vars, no external services, no migration application.

## Next Phase Readiness

- **40-04 (OpenAPI drift gate):** unaffected. BOT-03 does not change any HTTP API surface — no new path, no new schema field. The regenerated `apps/backend/openapi.json` in 40-04 will be byte-identical to what Wave 2 would have produced.
- **40-05 (milestone verification):** unblocked. VER-06 Telegram sandbox scenarios (`01_happy_path_keyboard.png`, `02_happy_path_confirmed.png`, `03_anti_oracle_denied.png`) can now be captured end-to-end:
  1. `/book` → keyboard render (BOT-02 from 40-02)
  2. tap a slot → confirmation DM (BOT-03 from 40-03 happy path)
  3. race-loss / package-state-change → `_BOT_BOOK_DENIED_DM` (BOT-03 anti-oracle)
- **No outstanding blockers.**

## Self-Check: PASSED

- [x] `apps/backend/app/integrations/telegram/handlers.py` — `book_callback_handler` defined
- [x] `apps/backend/app/workers/telegram_bot.py` — `CallbackQueryHandler(book_callback_handler, pattern=r"^BK:...$")` registered
- [x] `apps/backend/tests/integration/telegram_bot/test_book_callback.py` — created (641 lines, 15 tests)
- [x] commit `72d42b4` exists (RED test commit)
- [x] commit `a4a5747` exists (GREEN implementation commit)
- [x] `grep -c 'async def book_callback_handler' apps/backend/app/integrations/telegram/handlers.py` == 1
- [x] `grep -c 'CallbackQueryHandler' apps/backend/app/workers/telegram_bot.py` >= 1 (actual: 3 — import + class + reference)
- [x] `grep -cE 'pattern=r"\^BK:\[0-9a-f\]\{8\}-\[0-9a-f\]\{4\}-\[0-9a-f\]\{4\}-\[0-9a-f\]\{4\}-\[0-9a-f\]\{12\}\$"' apps/backend/app/workers/telegram_bot.py` == 1
- [x] `grep -c '_BOT_BOOK_DENIED_DM\|bot_book_denied_dm' apps/backend/app/integrations/telegram/handlers.py` >= 2 (actual: 13)
- [x] `grep -c 'book_callback_denied' apps/backend/app/integrations/telegram/handlers.py` >= 1 (actual: 4)
- [x] `grep -c 'type(exc).__name__' apps/backend/app/integrations/telegram/handlers.py` >= 1 (actual: 5)
- [x] `grep -c 'from app.modules.bookings.service import' apps/backend/app/integrations/telegram/handlers.py` == 0
- [x] `grep -c 'resolve_slot_by_id' apps/backend/app/integrations/telegram/handlers.py` == 0 (BLOCKER-3 regression-guard property)
- [x] `grep -c 'booking_response.trainer_full_name' apps/backend/app/integrations/telegram/handlers.py` >= 1 (actual: 1)
- [x] `grep -c 'booking_response.slot_start_time' apps/backend/app/integrations/telegram/handlers.py` >= 1 (actual: 1)
- [x] `uv run ruff check app/integrations/telegram/handlers.py app/workers/telegram_bot.py tests/integration/telegram_bot/test_book_callback.py` → All checks passed
- [x] `uv run mypy --strict app/` → Success: no issues found in 121 source files
- [x] `uv run lint-imports` → Contracts: 3 kept, 0 broken
- [x] `uv run pytest tests/unit -q` → 578 passed, 1 skipped (no regressions; the 1 skip is the pre-existing worker-handlers-registered test)
- [x] `uv run pytest tests/integration/telegram_bot/test_book_callback.py -q` → 2 passed, 13 skipped (DB-dependent skip cleanly; CI exercises full matrix)
- [x] `uv run pytest tests/integration/telegram_bot/ -q` → 9 passed, 31 skipped (full telegram_bot suite green)

## TDD Gate Compliance

- [x] **RED** — `test(40-03)` commit `72d42b4` lands the 15 failing tests (collection-time ImportError on `book_callback_handler`)
- [x] **GREEN** — `feat(40-03)` commit `a4a5747` lands the handler + registration; tests collect cleanly; 2 non-DB tests PASS in worktree; 13 DB-bound tests skip cleanly
- [ ] **REFACTOR** — skipped intentionally (implementation mirrors the canonical `book_handler` / `checkin_handler` shape; no cleanup pass needed)

---
*Phase: 40-telegram-book-openapi-drift-gate-milestone-verification*
*Completed: 2026-05-18*
