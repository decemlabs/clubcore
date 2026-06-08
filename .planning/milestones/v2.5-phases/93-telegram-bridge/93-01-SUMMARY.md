---
phase: 93-telegram-bridge
plan: "01"
subsystem: integrations/telegram + workers + messaging
tags: [telegram, arq, bridge, forward, redis, idor, config]
dependency_graph:
  requires:
    - app.integrations.storage (Phase 92 — Storage.open_stream for photo bytes)
    - migration-0066 (message_attachments — get_owned_attachment IDOR row)
    - app.modules.messaging.service.send_client_message / publish_new_message (Phase 90)
  provides:
    - settings.staff_telegram_chat_id (int | None — bridge enable flag)
    - app.integrations.telegram.sender.send_photo (+ SendResult.message_id)
    - app.workers.tasks.forward_to_staff (ARQ task; writes cc:messaging:tg_msg:{id})
    - repository.get_client_display (raw-SQL client identity for staff DM)
    - POST /client/messages post-commit forward_to_staff enqueue
  affects:
    - apps/backend/app/core/config.py
    - apps/backend/app/integrations/telegram/sender.py
    - apps/backend/app/workers/__init__.py
    - apps/backend/app/modules/messaging/router.py
    - apps/backend/app/modules/messaging/repository.py
tech_stack:
  added: []
  patterns:
    - "Worker→modules relaxation (D-06/D-10): forward_to_staff lives in app.workers, imports app.integrations.* only; no module import edge"
    - "Post-commit ARQ enqueue (never in-transaction) — dispatch_email precedent (D-42-13); _max_tries=2 / _expires=20 bounded retry"
    - "Raw-SQL cross-module read (D-54-08): repository.get_client_display via text() — zero new ignore_imports edge"
    - "Redis routing anchor cc:messaging:tg_msg:{tg_message_id} → {thread_id, client_id}, TTL 604800s, written only on successful staff send"
key_files:
  created: []
  modified:
    - apps/backend/app/core/config.py (staff_telegram_chat_id: int | None = None)
    - apps/backend/app/integrations/telegram/sender.py (send_photo + SendResult.message_id)
    - apps/backend/app/workers/tasks/forward_to_staff.py (new ARQ task)
    - apps/backend/app/workers/__init__.py (register forward_to_staff + ctx storage/bot wiring)
    - apps/backend/app/modules/messaging/router.py (post-commit enqueue)
    - apps/backend/app/modules/messaging/repository.py (get_client_display)
    - apps/backend/tests/integration/telegram_bot/test_forward_to_staff.py (RED→GREEN tests)
decisions:
  - "Staff DM target is ALWAYS settings.staff_telegram_chat_id (server config), never payload-derived (T-93-01)"
  - "object_key resolved from the IDOR-gated owned attachment row, never from user input (T-93-02)"
  - "Forward enqueued strictly post-commit; client send returns regardless of forward outcome (T-93-03)"
  - "Redis anchor written ONLY when send ok AND staff-side message_id returned — failed send leaves no stale anchor (T-93-05)"
  - "Client identity (name+phone) read via raw SQL text() instead of clients-service get_client — avoids a cross-module import edge (deviation from plan action text; D-54-08)"
  - "Enqueue kept inside _runner so idempotent replay (cache hit short-circuits before _runner) never re-enqueues"
metrics:
  duration: "~2 sessions (interrupted; closed out manually)"
  completed: "2026-06-08"
  tasks_completed: 3
  files_created: 1
  files_modified: 6
---

# Phase 93 Plan 01: Telegram Bridge Outbound (client→staff) Summary

**One-liner:** Client messages forward to the configured staff Telegram chat via a post-commit ARQ task (`forward_to_staff`) — text via `send_text_dm`, photos as inline images streamed from S3 via `send_photo` — writing a `cc:messaging:tg_msg:{id}` routing anchor for the Plan 02 reply path; no-op when `STAFF_TELEGRAM_CHAT_ID` is unset.

## Tasks Completed

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| 1 | staff_telegram_chat_id config + sender.send_photo + SendResult.message_id | `c527daee` | core/config.py + integrations/telegram/sender.py |
| 2 | forward_to_staff ARQ task + WorkerSettings registration + ctx wiring | `be9746e2` | workers/tasks/forward_to_staff.py + workers/__init__.py |
| 3 | Post-commit forward enqueue in messaging router | `e9097791` | messaging/router.py + messaging/repository.py + test_forward_to_staff.py |

(RED tests: `e4d4001d`.)

## What Was Built

### Config (`app/core/config.py`)
- `staff_telegram_chat_id: int | None = None` — the bridge enable flag. When `None`, the forward path is a logged no-op.

### Telegram sender (`app/integrations/telegram/sender.py`)
- `send_photo(bot, chat_id, photo, caption)` → `SendResult`; maps `Forbidden` and `BadRequest("chat not found")` to `blocked=True`, other `BadRequest`/generic exceptions to `error`.
- `SendResult.message_id` field populated from the Telegram return value (needed to key the Redis anchor).

### ARQ task (`app/workers/tasks/forward_to_staff.py`)
- New task (workers⊥modules; imports `app.integrations.*` only).
- Text-only forward via `sender.send_text_dm`; photo via streaming S3 bytes (`ctx["storage"].open_stream`) → `sender.send_photo`.
- Writes `cc:messaging:tg_msg:{tg_message_id} → {thread_id, client_id}` with 604800s TTL, **only** on a successful send with a returned `message_id`.
- No-op (returns `"skipped"`) with a structured log when `staff_telegram_chat_id` is `None`; no Redis write on failed send (returns `"failed"`).
- `workers/__init__.py`: registered in `WorkerSettings.functions`; `on_startup` wires `ctx["storage"]` and `ctx["bot"]`.

### Messaging router (`app/modules/messaging/router.py`)
- Inside `client_send_message._runner()`, after `session.commit()` + `publish_new_message`, when `get_settings().staff_telegram_chat_id is not None`, enqueues `forward_to_staff` with primitive kwargs (`client_id/message_id/thread_id/body/client_name/client_phone/attachment_id/object_key`), `_max_tries=2`, `_expires=20`.
- Client name/phone via `repository.get_client_display`; `object_key` via the IDOR-gated `repository.get_owned_attachment` when the message carries an attachment.

### Repository (`app/modules/messaging/repository.py`)
- `get_client_display(session, client_id)` → `{first_name, last_name, phone}` via raw SQL `text()` (no cross-module import edge); returns `None` for missing/soft-deleted client.

## Verification Results

All gates green:

| Gate | Result |
|------|--------|
| `uv run pytest tests/integration/telegram_bot/test_forward_to_staff.py` | 12/12 PASSED |
| `uv run pytest tests/integration/telegram_bot/test_forward_to_staff.py tests/messaging` | 118/118 PASSED (no regression) |
| `uv run mypy app/workers/tasks/forward_to_staff.py app/workers/__init__.py app/modules/messaging/router.py app/modules/messaging/repository.py app/integrations/telegram/sender.py app/core/config.py` | Success: no issues in 6 source files |
| `uv run ruff check` (changed files) | All checks passed |
| `uv run lint-imports` | 3 kept, 0 broken |

## Deviations from Plan

**1. [Rule 2 - Better approach] Client identity via raw SQL instead of clients-service call**
- **Plan action text** said: resolve client name+phone via `clients.service.get_client(session, client_id)`.
- **Implemented:** `repository.get_client_display` using raw SQL `text()`. The clients-service call would have created a new `messaging → clients` import edge; raw SQL keeps the modules-independent contract clean (D-54-08 discipline, already used elsewhere in this repository). Behaviour identical (first_name/last_name/phone).
- **Files:** `app/modules/messaging/repository.py`, `app/modules/messaging/router.py`.

**2. [Rule 1 - Bug] Redundant module-level asyncio pytestmark broke the sync config test**
- **Found during:** close-out test run.
- **Issue:** a `pytestmark = pytest.mark.asyncio(loop_scope="function")` left in the test header marked the synchronous `test_staff_telegram_chat_id_default_none` as asyncio → PytestWarning failure under strict mode.
- **Fix:** removed the redundant module-level mark (all async tests already carry explicit `@pytest.mark.asyncio`); cleaned pre-existing ruff nits in the Task 1/2 stubs (unused imports, dead nested funcs in `_stub_bot`, long docstrings).
- **Commit:** `e9097791`.

## Execution Note

Plan 93-01 execution was interrupted mid-Task-3 (router enqueue code + `get_client_display` written but uncommitted; the two router-enqueue tests not yet authored). Closed out manually under `/gsd:autonomous`: finished the Task 3 tests, ran the full verification gate, committed (`e9097791`), and wrote this SUMMARY so the phase resumes cleanly at Plan 02.

## Known Stubs

None — Plan 02 (inbound reply routing) consumes the `cc:messaging:tg_msg:{id}` anchor written here.

## Threat Flags

None — all surfaces covered by the plan threat model (T-93-01 … T-93-05).

## Self-Check: PASSED
