---
phase: 91-read-receipts-typing-indicators
verified: 2026-06-07T00:00:00Z
status: passed
score: 9/9 must-haves verified
overrides_applied: 0
re_verification: false
---

# Phase 91: Read Receipts + Typing Indicators Verification Report

**Phase Goal:** Клиент видит статус своих сообщений («прочитано») и индикатор набора от зала; оба события доставляются через уже существующий WS-канал без сохранения в БД (typing — эфемерный)
**Verified:** 2026-06-07
**Status:** PASSED
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| #  | Truth                                                                                                           | Status     | Evidence                                                                                                       |
|----|-----------------------------------------------------------------------------------------------------------------|------------|----------------------------------------------------------------------------------------------------------------|
| 1  | Staff reply sets read_at=now() on prior unread role='client' rows in the same thread                            | ✓ VERIFIED | `repository.mark_client_messages_read` WHERE `role = 'client' AND read_at IS NULL`; test_reply_as_read.py 5 tests PASS |
| 2  | reply-as-read returns max sent_at of marked rows to drive thread-level readAt                                   | ✓ VERIFIED | `repository.py:301` `max_sent_at = max(row[0] for row in updated)`; test_mark_client_messages_read_returns_max_sent_at PASS |
| 3  | message_read audit event emitted when reply-as-read marks at least one client message                           | ✓ VERIFIED | `service.py:232-240` audit.emit("message_read") when reply_read_at is not None; test_record_staff_message_emits_message_read_audit PASS |
| 4  | WS event union has ReadReceiptEvent {type:"read_receipt", readAt} and TypingEvent {type:"typing", actor:"staff"} | ✓ VERIFIED | `schemas.py:136-185`; both Literal discriminators confirmed; TestReadReceiptEventCamelCase + TestTypingEventCamelCase 8 tests PASS |
| 5  | publish_read_receipt publishes read_receipt frame to cc:messaging:client:{client_id} (post-commit, DB-first)    | ✓ VERIFIED | `service.py:78-97` Redis publish with f"cc:messaging:client:{client_id}"; test_ws_read_receipt_fanout PASS     |
| 6  | publish_typing publishes {type:'typing', actor:'staff'} with no DB access and no session param                  | ✓ VERIFIED | `service.py:100-119` no session param; TypingEvent has exactly 2 keys; test_ws_typing_fanout PASS + T-91-LEAK guard |
| 7  | IDOR isolation: client A's WS never receives client B's read_receipt or typing frame                            | ✓ VERIFIED | test_ws_idor_client_a_does_not_receive_client_b_receipt_or_typing PASS; channel derives from client_id only   |
| 8  | End-to-end: record_staff_message → commit → publish_read_receipt delivers read_receipt frame; client messages carry non-null readAt | ✓ VERIFIED | test_ws_reply_as_read_e2e PASS; REST GET confirms readAt on 2 client messages                    |
| 9  | PATCH /client/messages/read polling fallback persists read state (RCPT-03)                                      | ✓ VERIFIED | test_patch_read_polling_fallback_persists PASS; unreadCount 1→0 via PATCH, no WS required                     |

**Score:** 9/9 truths verified

### Required Artifacts

| Artifact                                                         | Expected                                          | Status     | Details                                                                                         |
|------------------------------------------------------------------|---------------------------------------------------|------------|-------------------------------------------------------------------------------------------------|
| `apps/backend/app/modules/messaging/schemas.py`                  | ReadReceiptEvent + TypingEvent schema variants    | ✓ VERIFIED | Lines 136-185: both classes with Literal discriminators and correct fields                       |
| `apps/backend/app/modules/messaging/repository.py`               | mark_client_messages_read targeting role='client' | ✓ VERIFIED | Lines 227-302: WHERE clause includes `role = 'client'`; distinct from mark_thread_read          |
| `apps/backend/app/modules/messaging/service.py`                  | publish_read_receipt + publish_typing + wiring    | ✓ VERIFIED | Lines 78-119: both publish helpers; lines 226-228: mark_client_messages_read called in record_staff_message |
| `apps/backend/tests/messaging/test_reply_as_read.py`             | 5 reply-as-read service tests                     | ✓ VERIFIED | All 5 tests PASS (SAVEPOINT db_session harness, no WS)                                          |
| `apps/backend/tests/messaging/test_ws_receipts_typing.py`        | 5 WS tests for fan-out, IDOR, e2e, fallback       | ✓ VERIFIED | All 5 tests PASS; uses TestClient.websocket_connect(); no asyncio.run()                         |

### Key Link Verification

| From                                             | To                                          | Via                          | Status     | Details                                                                  |
|--------------------------------------------------|---------------------------------------------|------------------------------|------------|--------------------------------------------------------------------------|
| service.record_staff_message                     | repository.mark_client_messages_read        | call at line 226             | ✓ WIRED    | Direct call before insert_message; thread_id pre-resolved (WR-01 fix)   |
| service.publish_read_receipt                     | cc:messaging:client:{client_id}             | redis.publish at line 94-95  | ✓ WIRED    | Channel derived from client_id only (T-91-IDOR)                         |
| service.publish_typing                           | cc:messaging:client:{client_id}             | redis.publish at line 117    | ✓ WIRED    | Ephemeral; no session param; no DB access                                |
| test_ws_reply_as_read_e2e                        | service.publish_read_receipt                | _portal_call post-commit     | ✓ WIRED    | commit() strictly before publish_read_receipt (CR-02 / T-91-PHANTOM)    |

### Data-Flow Trace (Level 4)

| Artifact                          | Data Variable   | Source                                                 | Produces Real Data | Status      |
|-----------------------------------|-----------------|--------------------------------------------------------|--------------------|-------------|
| ReadReceiptEvent                  | read_at         | repository.mark_client_messages_read RETURNING sent_at | Yes — DB rows      | ✓ FLOWING   |
| TypingEvent                       | actor           | Default literal "staff" — no DB (ephemeral by design)  | N/A — ephemeral    | ✓ FLOWING   |
| record_staff_message return       | reply_read_at   | max(sent_at) of updated role='client' rows from DB     | Yes — DB rows      | ✓ FLOWING   |

### Behavioral Spot-Checks

| Behavior                                              | Command                                                                      | Result      | Status   |
|-------------------------------------------------------|------------------------------------------------------------------------------|-------------|----------|
| Full messaging suite (64 tests)                       | `uv run pytest tests/messaging/ -q`                                          | 64 passed   | ✓ PASS   |
| mypy strict on messaging module                       | `uv run mypy --strict app/modules/messaging/`                                | 0 issues    | ✓ PASS   |
| ruff on messaging module                              | `uv run ruff check app/modules/messaging/`                                   | All passed  | ✓ PASS   |
| import-linter                                         | `uv run lint-imports`                                                        | 3 kept, 0 broken | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description                                                                       | Status      | Evidence                                                                                          |
|-------------|-------------|-----------------------------------------------------------------------------------|-------------|---------------------------------------------------------------------------------------------------|
| RCPT-01     | 91-01, 91-02 | Клиент видит статус «✓/✓✓» для своих сообщений                                   | ✓ SATISFIED | ReadReceiptEvent schema + reply-as-read sets read_at; e2e test confirms readAt on client messages |
| RCPT-02     | 91-02        | Клиент видит индикатор «печатает…» от зала                                        | ✓ SATISFIED | TypingEvent + publish_typing + test_ws_typing_fanout; T-91-LEAK guard (no content keys)          |
| RCPT-03     | 91-01, 91-02 | Ответ staff помечает клиентские сообщения прочитанными + WS read-receipt событие | ✓ SATISFIED | mark_client_messages_read in record_staff_message; PATCH polling-fallback regression test PASS    |

REQUIREMENTS.md confirms all three are marked `[x]` Complete for Phase 91.

### Anti-Patterns Found

| File                                               | Line | Pattern               | Severity  | Impact                                                                            |
|----------------------------------------------------|------|-----------------------|-----------|-----------------------------------------------------------------------------------|
| `apps/backend/app/modules/messaging/service.py`    | 164  | `TODO Phase 93:`      | ℹ️ Info   | Intentional forward seam for Telegram bridge; references Phase 93 explicitly — NOT a debt marker |
| `apps/backend/app/modules/messaging/service.py`    | 195  | Phase 93 comment      | ℹ️ Info   | Intentional scope boundary documentation                                          |

No `TBD`, `FIXME`, or `XXX` markers found. The `TODO Phase 93:` comment references formal follow-up work (Phase 93) — satisfies the debt marker gate. No stubs, no empty implementations, no hardcoded empty arrays in non-test code.

### Zero-Migration Confirmation

Highest migration remains `0065_messaging_messages.py`. No new migration files created. The `messages.read_at` column exists since 0065. Typing events are never persisted to DB (confirmed: `publish_typing` has no session parameter and no DB call path).

### Deferred Items (Intentional Scope Boundary)

Phase 91 correctly defers the following to later phases — these are NOT gaps:

| Item                                             | Deferred To | Evidence                                                            |
|--------------------------------------------------|-------------|---------------------------------------------------------------------|
| Telegram-reply trigger for reply-as-read         | Phase 93    | ROADMAP Phase 93 SC #2; service.py TODO seam documented at line 164 |
| Telegram `sendChatAction` → typing trigger        | Phase 93    | 91-CONTEXT.md "Out of scope" section; RCPT-02 service seam is the deliverable |
| PWA ChatScreen display of ✓/✓✓ and typing indicator | Phase 94  | ROADMAP Phase 94 goal; D-71-09 placeholder still in place           |

Phase 91 delivers the **service seam + WS receive path only** — the Telegram triggers and PWA display are Phase 93/94 responsibilities as documented in ROADMAP.

### Review Findings Status

The code review (91-REVIEW.md) identified 3 warnings and 2 info items. Status as of this verification:

| Finding | Category | Disposition in Code                                                                       |
|---------|----------|-------------------------------------------------------------------------------------------|
| WR-01: Double get_or_create_thread round-trip | Warning | **FIXED** — service.py pre-resolves thread_id once and passes to mark_client_messages_read (thread_id param added per fix suggestion) |
| WR-02: read_at field carries sent_at semantics | Warning | **DOCUMENTED** — inline field comment + docstring added to ReadReceiptEvent (schemas.py:144-158); field name locked per WR-02 decision |
| WR-03: Concurrent send watermark over-cover     | Warning | **DOCUMENTED** — repository.py:275-283 acknowledges the tradeoff and REST-refetch self-heal |
| IN-01: IDOR enforcement not yet wired in router | Info | **NOTED** — no Phase 91 code change needed; wiring deferred to Phase 93/94 per scope boundary |
| IN-02: TypingEvent.actor typed as bare str       | Info | **FIXED** — actor: Literal["staff"] = "staff" in schemas.py:185                          |

No critical or blocker-tier defects.

### Human Verification Required

None. All phase-91 must-haves are verified programmatically via the running test suite and static analysis tools.

---

_Verified: 2026-06-07_
_Verifier: Claude (gsd-verifier)_
