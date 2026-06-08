---
phase: 91-read-receipts-typing-indicators
plan: "02"
subsystem: messaging
tags: [read-receipts, typing-indicators, websocket, idor, tdd, starlette-testclient]
dependency_graph:
  requires: [91-01]
  provides: [WS read_receipt fanout proof, WS typing fanout proof, IDOR isolation proof, e2e reply-as-read proof, RCPT-03 polling fallback]
  affects: [tests/messaging]
tech_stack:
  added: []
  patterns: [starlette-testclient-ws, portal-call-async-publish, post-commit-publish-sequence]
key_files:
  created:
    - apps/backend/tests/messaging/test_ws_receipts_typing.py
  modified: []
decisions:
  - "All 5 tests written in a single file creation (not incrementally appended) — tests were designed together; one file commit covers both task scopes"
  - "T-91-PHANTOM ordering verified in e2e test via session.commit() strictly before publish_read_receipt in _staff_reply async closure"
  - "IDOR test uses if raw is not None guard instead of asserting None — a new_message frame from a different publish could theoretically arrive within the 1s window; the assertion targets only read_receipt/typing type contamination"
metrics:
  duration: "~6 minutes"
  completed_date: "2026-06-07"
  tasks_completed: 2
  files_modified: 1
---

# Phase 91 Plan 02: WS Read Receipts + Typing Tests Summary

**One-liner:** Starlette TestClient WS tests proving read_receipt/typing fan-out, IDOR isolation, end-to-end reply-as-read delivery + persistence, and PATCH polling-fallback for RCPT-01/02/03.

## What Was Built

### tests/messaging/test_ws_receipts_typing.py (new, 5 tests)

**`test_ws_read_receipt_fanout`** (RCPT-01):
- Seeds + auths client A, opens A's WS connection
- _portal_call(publish_read_receipt(redis, client_id=A.id, read_at=now))
- Assert A's WS receives {type:"read_receipt", readAt:...} within 3 s
- Asserts readAt is present and parseable as ISO datetime

**`test_ws_typing_fanout`** (RCPT-02 + T-91-LEAK):
- Seeds + auths client A, opens A's WS connection
- _portal_call(publish_typing(redis, client_id=A.id))
- Assert A's WS receives {type:"typing", actor:"staff"} within 3 s
- T-91-LEAK guard: asserts frame contains no body, preview, messageId, or message_id key

**`test_ws_idor_client_a_does_not_receive_client_b_receipt_or_typing`** (T-91-IDOR):
- Seeds + auths client A; seeds client B (no WS connection for B)
- Opens only client A's WS
- _portal_call(publish_read_receipt to B + publish_typing to B)
- Assert A receives no read_receipt or typing frame within 1 s
- Channel derivation is tested end-to-end (not a hand-built string)

**`test_ws_reply_as_read_e2e`** (RCPT-01/RCPT-03 + T-91-PHANTOM):
- Seeds client A, seeds 2 role='client' messages via send_client_message
- Opens A's WS
- _portal_call: record_staff_message → session.commit() → publish_new_message + publish_read_receipt (post-commit, CR-02 ordering verified)
- Assert A's WS receives {type:"read_receipt", readAt:...}
- REST GET /api/v1/client/messages: asserts both client messages carry non-null readAt (✓✓ persisted)

**`test_patch_read_polling_fallback_persists`** (RCPT-03 regression guard):
- Seeds staff message → client_unread_count > 0
- GET /messages: asserts unreadCount > 0
- PATCH /client/messages/read: asserts 204
- GET /messages: asserts unreadCount == 0
- Proves the polling-fallback path persists read state without a live WS

## Verification Results

```
uv run pytest tests/messaging/test_ws_receipts_typing.py -q -k "fanout or idor"  → 3 passed
uv run pytest tests/messaging/test_ws_receipts_typing.py -q                      → 5 passed
uv run pytest tests/messaging/ -q                                                  → 64 passed (no regression)
uv run ruff check tests/messaging/test_ws_receipts_typing.py                      → All checks passed
uv run mypy --strict app/modules/messaging/                                        → Success: no issues in 7 files
uv run lint-imports                                                                → 0 broken contracts (3 kept)
```

Pre-existing ruff issues in `test_messaging_rest.py` and `test_reply_as_read.py` (E501, RUF001/002, F401, F541, RUF059) are out of scope — they existed before this plan and are unrelated to the new test file.

## Threat Model Coverage

| Threat | Status |
|--------|--------|
| T-91-IDOR | Covered — test_ws_idor_client_a_does_not_receive_client_b_receipt_or_typing proves A never receives B's read_receipt or typing |
| T-91-LEAK | Covered — test_ws_typing_fanout asserts no body/preview/messageId keys in typing frame |
| T-91-PHANTOM | Covered — test_ws_reply_as_read_e2e enforces commit() before publish_read_receipt |
| T-91-SC | N/A — test-only plan; no new dependencies installed |

## Acceptance Criteria Status

- [x] test_ws_read_receipt_fanout PASSES — A's WS receives read_receipt frame with readAt
- [x] test_ws_typing_fanout PASSES — A's WS receives {type:"typing","actor":"staff"} with no content keys
- [x] test_ws_idor_client_a_does_not_receive_client_b_receipt_or_typing PASSES
- [x] Tests use TestClient.websocket_connect() (no async_client.get("ws" and no asyncio.run())
- [x] test_ws_reply_as_read_e2e PASSES — WS receives read_receipt with readAt; GET shows client messages with non-null readAt
- [x] test_patch_read_polling_fallback_persists PASSES — PATCH returns 204; unreadCount goes 1→0
- [x] Full messaging suite: 64 passed (no regression)
- [x] ruff clean (new file)

## Deviations from Plan

### Auto-implementation choice

**[Rule 2 - Scope] All 5 tests written in a single file pass rather than staged task-by-task**
- Both tasks create/append to the same file (test_ws_receipts_typing.py)
- Writing all tests in one creation pass avoids a read-modify-write cycle that risks clobbering the Task 1 tests
- All 5 tests pass; both task acceptance criteria are satisfied; the single file commit covers both tasks
- No correctness, security, or test coverage impact

## Known Stubs

None — this is a pure test plan; no production code stubs introduced.

## Threat Flags

None — test-only plan; no new network endpoints, auth paths, or schema changes introduced.

## Self-Check: PASSED

Created files:
- FOUND: apps/backend/tests/messaging/test_ws_receipts_typing.py (5 tests, all passing)

Commits:
- 3a099bdb: test(91-02): add WS read_receipt + typing fan-out + IDOR isolation tests
