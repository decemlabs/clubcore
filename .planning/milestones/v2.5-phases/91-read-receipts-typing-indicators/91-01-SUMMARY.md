---
phase: 91-read-receipts-typing-indicators
plan: "01"
subsystem: messaging
tags: [read-receipts, typing-indicators, reply-as-read, websocket, redis-pubsub]
dependency_graph:
  requires: [90-03]
  provides: [mark_client_messages_read, publish_read_receipt, publish_typing, ReadReceiptEvent, TypingEvent, StaffMessageResult]
  affects: [messaging.repository, messaging.service, messaging.schemas]
tech_stack:
  added: []
  patterns: [reply-as-read, post-commit-publish, ephemeral-pubsub, tdd-red-green]
key_files:
  created:
    - apps/backend/tests/messaging/test_reply_as_read.py
  modified:
    - apps/backend/app/modules/messaging/schemas.py
    - apps/backend/app/modules/messaging/repository.py
    - apps/backend/app/modules/messaging/service.py
    - apps/backend/tests/messaging/test_messaging_schema_camelcase.py
decisions:
  - "StaffMessageResult dataclass extends MessageResponse fields with reply_read_at to preserve .id access for Phase 90 callers"
  - "mark_client_messages_read returns max sent_at (not DB now()) for thread-level readAt semantic"
  - "publish_typing has no session param — emphasizes ephemeral nature and no DB dependency"
metrics:
  duration: "~8 minutes"
  completed_date: "2026-06-07"
  tasks_completed: 2
  files_modified: 5
---

# Phase 91 Plan 01: Read Receipts + Typing Indicators (Service Layer) Summary

**One-liner:** Reply-as-read (role='client') + WS ReadReceiptEvent/TypingEvent schemas + publish helpers wired into record_staff_message with message_read audit emission.

## What Was Built

### Task 1: ReadReceiptEvent + TypingEvent WS schema variants (TDD)

Extended `schemas.py` with two new `ResponseData` subclasses completing the Phase 91 WS event discriminated union:

- `ReadReceiptEvent`: `Literal["read_receipt"]` discriminator + `read_at: datetime` field (→ `readAt` camelCase). Thread-level marker: client marks all its sent messages with `sent_at <= readAt` as ✓✓. Published post-commit (CR-02/T-91-PHANTOM).
- `TypingEvent`: `Literal["typing"]` discriminator + `actor: str = "staff"` field. Carries **exactly two keys** (`type`, `actor`) — no body, preview, or message id (T-91-LEAK). Ephemeral, never persisted.
- Updated module docstring to reflect all three WS event types (new_message, read_receipt, typing).

Extended `test_messaging_schema_camelcase.py` with `TestReadReceiptEventCamelCase` (4 assertions) and `TestTypingEventCamelCase` (4 assertions including exact-key-count guard for T-91-LEAK).

### Task 2: reply-as-read repository fn + service wiring + publish helpers (TDD)

**`repository.mark_client_messages_read`** (new function):
- Mirrors `mark_thread_read` but targets `role='client'` rows
- `UPDATE messages SET read_at=now(), updated_at=now() WHERE thread_id=:tid AND role='client' AND read_at IS NULL RETURNING sent_at`
- Returns `max(sent_at)` of marked rows (thread-level readAt), or `None` if nothing to mark
- T-91-XTHREAD: WHERE clause scoped to `thread_id = get_or_create_thread(client_id)` — cross-client marking impossible
- No `session.commit()` (caller-owns-txn)

**`service.record_staff_message`** (extended return type `StaffMessageResult`):
- Before staff insert: calls `repository.mark_client_messages_read`
- If `reply_read_at is not None`: emits `message_read` audit event (pre-registered, reuses mark_thread_read pattern)
- Returns `StaffMessageResult` (superset of MessageResponse adding `reply_read_at: datetime | None`)
- Existing callers using `.id` are unaffected

**`schemas.StaffMessageResult`** (new):
- MessageResponse field set + `reply_read_at: datetime | None = None` (→ `replyReadAt` camelCase)

**`service.publish_read_receipt`** (new):
- Post-commit helper: publishes `ReadReceiptEvent(read_at=read_at).model_dump_json(by_alias=True)` to `cc:messaging:client:{client_id}`
- Documented CR-02 / DB-first constraint (T-91-PHANTOM)
- Channel derived from `client_id` only (T-91-IDOR)

**`service.publish_typing`** (new):
- Ephemeral helper: publishes `TypingEvent().model_dump_json(by_alias=True)` to `cc:messaging:client:{client_id}`
- No `session` parameter — no DB, no commit dependency
- Channel derived from `client_id` only (T-91-IDOR)

**`tests/messaging/test_reply_as_read.py`** (new, 5 tests):
- `test_record_staff_message_marks_client_messages_read`: seeds 2 client messages, staff reply marks both read
- `test_record_staff_message_emits_message_read_audit`: verifies `audit_log` row for `message_read`
- `test_record_staff_message_does_not_remark_already_read_messages`: idempotency on `read_at IS NULL` filter
- `test_mark_client_messages_read_returns_none_when_nothing_to_mark`: no unread client msgs → `None`
- `test_mark_client_messages_read_returns_max_sent_at`: verifies `datetime` return on mark

## Verification Results

```
uv run pytest tests/messaging/ -q         → 59 passed (41 pre-existing + 18 new)
uv run mypy --strict app/modules/messaging/ → Success: no issues found in 7 source files
uv run ruff check app/modules/messaging/   → All checks passed
uv run lint-imports                        → 0 broken contracts (3 kept)
```

No Alembic migrations created (read_at column already exists from migration 0065).

## Acceptance Criteria Status

- [x] `schemas.py` defines `ReadReceiptEvent` with `Literal["read_receipt"]` + `read_at` field
- [x] `schemas.py` defines `TypingEvent` with `Literal["typing"]` + `actor` default `"staff"`
- [x] `grep -E "Literal\[.(read_receipt|typing)"` returns 2 matches
- [x] `TypingEvent` JSON has exactly 2 keys (asserted in `TestTypingEventCamelCase`)
- [x] `repository.py` defines `mark_client_messages_read` targeting `role = 'client'`
- [x] `service.record_staff_message` calls `repository.mark_client_messages_read`
- [x] `service.py` defines `publish_read_receipt` and `publish_typing`
- [x] `publish_typing` signature has no `session` parameter
- [x] `uv run pytest tests/messaging/test_reply_as_read.py -q` → 5 passed
- [x] `uv run mypy --strict app/modules/messaging/` → Success
- [x] `uv run ruff check app/modules/messaging/` → All checks passed
- [x] `uv run lint-imports` → 0 broken
- [x] No new `session.commit()` in repository.py or service.py

## Threat Model Coverage

| Threat | Status |
|--------|--------|
| T-91-IDOR | Mitigated — channel derived from function's `client_id` arg only |
| T-91-LEAK | Mitigated — `TypingEvent` has exactly 2 keys; asserted in test |
| T-91-XTHREAD | Mitigated — WHERE scoped to `thread_id` from `get_or_create_thread(client_id)` |
| T-91-PHANTOM | Mitigated — `publish_read_receipt` documented as post-commit only; no publish inside service |

## Deviations from Plan

None — plan executed exactly as written.

`StaffMessageResult` schema approach was chosen as the "least-invasive shape" as directed by the plan: existing Phase 90 callers that use `.id` continue to work; `reply_read_at` is the new field.

## Self-Check: PASSED

Created files:
- FOUND: apps/backend/tests/messaging/test_reply_as_read.py
- FOUND: apps/backend/app/modules/messaging/schemas.py (ReadReceiptEvent, TypingEvent, StaffMessageResult classes present)
- FOUND: apps/backend/app/modules/messaging/repository.py (mark_client_messages_read present)
- FOUND: apps/backend/app/modules/messaging/service.py (publish_read_receipt, publish_typing present)

Commits:
- 24c5df9d: test(91-01): add failing tests for ReadReceiptEvent + TypingEvent schema variants
- 8edf3f82: feat(91-01): add ReadReceiptEvent + TypingEvent WS event-union schema variants
- 3e36afbf: test(91-01): add failing reply-as-read service tests (TDD RED)
- dd578999: feat(91-01): reply-as-read repo fn + service wiring + publish helpers
