---
phase: 93-telegram-bridge
plan: "02"
subsystem: integrations/telegram + workers + messaging
tags: [telegram, bridge, redis, reply-routing, echo-loop, idor, ws]
dependency_graph:
  requires:
    - "93-01: cc:messaging:tg_msg:{id} Redis anchor (forward_to_staff task)"
    - app.modules.messaging.service.record_staff_message (Phase 90/91)
    - app.modules.messaging.service.publish_new_message (Phase 90)
    - app.modules.messaging.service.publish_read_receipt (Phase 91)
    - audit.emit + LOCKED_AUDIT_EVENTS chat_staff_reply_sent (INFRA-15)
  provides:
    - app.integrations.telegram.handlers.staff_reply_handler (BRDG-02/BRDG-03)
    - HandlerContext.messaging_service field (8-field tuple, field-order preserved)
    - MessageHandler registration in telegram_bot.py:main() for staff-chat TEXT messages
  affects:
    - apps/backend/app/integrations/telegram/handlers.py
    - apps/backend/app/workers/telegram_bot.py
    - apps/backend/tests/integration/telegram_bot/test_handler_context_shape.py
    - apps/backend/tests/integration/telegram_bot/test_staff_reply_handler.py
    - apps/backend/tests/integration/telegram_bot/test_worker_handlers_registered.py
    - apps/backend/tests/integration/telegram_bot/test_checkin_handler.py
    - apps/backend/tests/integration/telegram_bot/test_checkin_dm_days_remaining.py
    - apps/backend/tests/integration/telegram_bot/test_book_callback.py
    - apps/backend/tests/integration/telegram_bot/test_book_command.py
tech_stack:
  added: []
  patterns:
    - "HandlerContext APPEND-AT-END contract: messaging_service appended as field 8, never inserted in the middle"
    - "integrations⊥modules: messaging_service reached via ctx.messaging_service.* (no static from app.modules.messaging import)"
    - "Triple echo-loop guard: is_bot early-return + _dedupe_update_id SET-NX (reused) + anchor-presence requirement"
    - "Stale/missing anchor drop: no most-recent-thread fallback (SC-2/BRDG-03); DM hint to staff"
    - "CR-02/DB-first (P5): session.commit() before any Redis publish"
    - "co-transactional audit: chat_staff_reply_sent emitted before commit (atomic with message insert, T-93-10)"
key_files:
  created: []
  modified:
    - apps/backend/app/integrations/telegram/handlers.py (HandlerContext.messaging_service + staff_reply_handler)
    - apps/backend/app/workers/telegram_bot.py (import messaging_service + wiring + MessageHandler registration)
    - apps/backend/tests/integration/telegram_bot/test_handler_context_shape.py (extended to 8-field assertions)
    - apps/backend/tests/integration/telegram_bot/test_staff_reply_handler.py (7-case TDD test suite)
    - apps/backend/tests/integration/telegram_bot/test_worker_handlers_registered.py (Rule 1 fix: messaging_service kwarg)
    - apps/backend/tests/integration/telegram_bot/test_checkin_handler.py (Rule 1 fix: messaging_service kwarg)
    - apps/backend/tests/integration/telegram_bot/test_checkin_dm_days_remaining.py (Rule 1 fix: messaging_service kwarg)
    - apps/backend/tests/integration/telegram_bot/test_book_callback.py (Rule 1 fix: messaging_service kwarg)
    - apps/backend/tests/integration/telegram_bot/test_book_command.py (Rule 1 fix: messaging_service kwarg)
decisions:
  - "HandlerContext.messaging_service appended at END (field 8/8) — field-order contract (D-40-04 precedent)"
  - "get_settings() called inline in staff_reply_handler for the chat-id guard — NOT captured at ctx construction time, so the in-handler guard reflects current settings"
  - "No anchor thread_id used in record_staff_message — handler passes only client_id; record_staff_message resolves thread via get_or_create_thread (idempotent)"
  - "Test patch target is app.integrations.telegram.handlers.get_settings (where used), not app.core.config.get_settings"
metrics:
  duration: "~45 minutes"
  completed: "2026-06-08"
  tasks_completed: 2
  files_created: 1
  files_modified: 8
---

# Phase 93 Plan 02: Telegram Bridge Inbound (staff→client reply) Summary

**One-liner:** Staff Telegram Reply on a forwarded message is routed to the originating client thread via the Redis `cc:messaging:tg_msg:{id}` anchor, persisted via `record_staff_message`, and delivered to the client's live WS connection; echo-loops and misroutes are made impossible by a triple guard (is_bot + update_id dedup + anchor-presence).

## Tasks Completed

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| 1 (RED) | HandlerContext.messaging_service shape tests | `c5e5e5d3` | test_handler_context_shape.py |
| 1 (GREEN) | HandlerContext.messaging_service field + worker wiring | `a4ac0cf3` | handlers.py + telegram_bot.py |
| 2 (RED) | staff_reply_handler test suite (7 cases) | `60a129d6` | test_staff_reply_handler.py |
| 2 (GREEN) | staff_reply_handler + MessageHandler registration | `bca43a87` | handlers.py + telegram_bot.py |

## What Was Built

### HandlerContext extension (`app/integrations/telegram/handlers.py`)
- `messaging_service: ModuleType` appended at END of HandlerContext (field 8/8).
- Field-order contract preserved (APPEND-ONLY; existing 7-field positional construction unchanged).

### Worker wiring (`app/workers/telegram_bot.py`)
- `from app.modules.messaging import service as messaging_service` (D-06 relaxation, mirrors visits/bookings).
- `messaging_service=messaging_service` appended last in HandlerContext(...) construction.
- `MessageHandler(tg_filters.Chat(staff_chat_id) & tg_filters.TEXT, callback=_staff_reply_adapter)` registered post-`build_application` when `staff_telegram_chat_id` is set; logs `staff_reply_handler_disabled` otherwise.

### staff_reply_handler (`app/integrations/telegram/handlers.py`)
- Defensive field guards + `is_bot` echo early-return (T-93-08).
- `_dedupe_update_id` SET-NX replay guard (reused from /checkin pattern, T-93-08).
- Defensive in-handler `chat_id == settings.staff_telegram_chat_id` check (T-93-06 belt-and-suspenders).
- Non-Reply (reply_to_message is None): sends `_DM_STAFF_USE_REPLY` hint + drops.
- Redis GET `cc:messaging:tg_msg:{reply_to.message_id}` → None: sends `_DM_STAFF_STALE_ANCHOR` hint + drops (no fallback, T-93-07 / SC-2 / BRDG-03).
- Anchor present: parses `client_id` → opens session → `ctx.messaging_service.record_staff_message(...)`.
- `chat_staff_reply_sent` audit emitted **before** `session.commit()` (co-transactional, T-93-10).
- Post-commit: `ctx.messaging_service.publish_new_message(...)` always; `ctx.messaging_service.publish_read_receipt(...)` if `result.reply_read_at is not None` (CR-02 / DB-first, P5).
- Service reached ONLY via `ctx.messaging_service.*` — zero static `from app.modules.messaging` imports (integrations⊥modules).

## Verification Results

All gates green:

| Gate | Result |
|------|--------|
| `uv run pytest tests/integration/telegram_bot/test_staff_reply_handler.py tests/integration/telegram_bot/test_handler_context_shape.py -q` | 14/14 PASSED |
| `uv run pytest tests/messaging tests/integration/telegram_bot -q` | 168/168 PASSED (no regression) |
| `uv run mypy app/integrations/telegram/handlers.py app/workers/telegram_bot.py` | Success: no issues in 2 source files |
| `uv run lint-imports` | 3 kept, 0 broken |
| `grep "^from app.modules" app/integrations/telegram/handlers.py` | 0 matches (integrations⊥modules clean) |
| HandlerContext._fields[-1] == 'messaging_service' and len == 8 | PASSED |
| MessageHandler in telegram_bot.py source | PRESENT |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] All existing telegram_bot test files needed messaging_service kwarg**
- **Found during:** Task 1 GREEN phase (mypy + test run).
- **Issue:** NamedTuple now requires `messaging_service` as field 8; all `HandlerContext(...)` constructions in existing tests were missing it → `TypeError: HandlerContext.__new__() missing 1 required positional argument`.
- **Fix:** Added `messaging_service=messaging_service` (with inline import where needed) to 5 existing test files: `test_worker_handlers_registered.py`, `test_checkin_handler.py`, `test_checkin_dm_days_remaining.py`, `test_book_callback.py`, `test_book_command.py`.
- **Commit:** `a4ac0cf3`.

**2. [Rule 1 - Bug] Test patch target corrected from app.core.config to app.integrations.telegram.handlers**
- **Found during:** Task 2 GREEN phase (first test run).
- **Issue:** Initial test file patched `app.core.config.get_settings`; the handler calls `get_settings()` from its direct import (`from app.core.config import get_settings`), so the correct patch target is `app.integrations.telegram.handlers.get_settings`.
- **Fix:** `replace_all=true` on all 7 occurrences in the test file.
- **Committed in:** same task 2 commit `bca43a87`.

**3. [Rule 1 - Bug] Test queries corrected to JOIN by client_id instead of anchor thread_id**
- **Found during:** Task 2 GREEN phase (first test run).
- **Issue:** Tests queried `messages WHERE thread_id=:tid` using the `thread_id` from the Redis anchor (a randomly generated UUID). `record_staff_message` calls `get_or_create_thread(session, client_id)` which creates/returns the actual DB thread — not the UUID in the anchor. The anchor's `thread_id` field is written by `forward_to_staff` but `record_staff_message` ignores it.
- **Fix:** Changed all message queries to `JOIN message_threads t ON t.id = m.thread_id WHERE t.client_id=:cid` (joining through the actual thread table).
- **Committed in:** same task 2 commit `bca43a87`.

## Known Stubs

None — handler is fully wired: anchor lookup → record_staff_message → publish_new_message/publish_read_receipt.

## Threat Flags

None — all surfaces covered by the plan threat model (T-93-06 … T-93-10). No new surfaces introduced beyond the plan.

## TDD Gate Compliance

- RED gate commit (test): `c5e5e5d3` (Task 1), `60a129d6` (Task 2)
- GREEN gate commit (feat): `a4ac0cf3` (Task 1), `bca43a87` (Task 2)
- REFACTOR: not needed — code is clean post-GREEN.

## Self-Check: PASSED
