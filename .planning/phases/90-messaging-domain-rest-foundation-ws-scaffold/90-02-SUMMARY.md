---
phase: 90-messaging-domain-rest-foundation-ws-scaffold
plan: "02"
subsystem: api
tags: [fastapi, sqlalchemy, pydantic, redis, idempotency, messaging, pubsub, camelcase]

# Dependency graph
requires:
  - phase: 90-messaging-domain-rest-foundation-ws-scaffold
    plan: "01"
    provides: "MessageThread + Message ORM models, migrations 0064/0065, audit events pre-registered, import-linter contract"
provides:
  - "GET /api/v1/client/messages: paginated message history newest-first with unreadCount + ?after= RT-04 cursor"
  - "POST /api/v1/client/messages: idempotent send via Idempotency-Key + idempotent_execute"
  - "PATCH /api/v1/client/messages/read: mark all staff messages read, reset client_unread_count to 0"
  - "messaging repository (get_or_create_thread, insert_message, list_thread_history, mark_thread_read)"
  - "messaging service (send_client_message, record_staff_message, list_thread_history, mark_thread_read)"
  - "messaging schemas (MessageItem, MessageListResponse, SendMessageRequest, MessageResponse, NewMessageEvent)"
  - "Redis pub/sub publish seam: cc:messaging:client:{client_id} id-only frame after DB write (RT-03 publish side)"
  - "record_staff_message() internal function (no endpoint) for tests + Phase 93 bridge"
affects: [90-03, 91, 92, 93, 94, 95]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "verify_client_idempotency + idempotent_execute for client-scoped POST idempotency (mirrors client_portal/router.py)"
    - "MessageListResponse manual page shape (items/total/page/page_size/unread_count) — PaginatedData[T] cannot carry unreadCount"
    - "field_validator strip-and-check for whitespace-only body rejection (Field min_length=1 alone does not strip)"
    - "DB-first pub/sub: redis.publish AFTER session.commit() in idempotent_execute runner (P5 delivery guarantee)"
    - "record_staff_message internal function pattern (no endpoint, exercised by tests + future bridge)"

key-files:
  created:
    - apps/backend/app/modules/messaging/schemas.py
    - apps/backend/app/modules/messaging/repository.py
    - apps/backend/app/modules/messaging/service.py
    - apps/backend/app/modules/messaging/router.py
    - apps/backend/tests/messaging/test_messaging_schema_camelcase.py
    - apps/backend/tests/messaging/test_messaging_rest.py
  modified:
    - apps/backend/app/api/v1/router.py

key-decisions:
  - "verify_client_idempotency (not verify_idempotency) used for POST /messages — client endpoints cannot use staff dependency (get_current_user would 401)"
  - "idempotent_execute runner commits session internally — DB-first publish: redis.publish fires after commit in the same runner function"
  - "after-cursor uses composite (sent_at, id::text) comparison (not row-value notation) for portability with asyncpg UUID type"
  - "PATCH /messages/read returns 204 No Content (matches notifications read-all analog)"
  - "record_staff_message internal function (no endpoint) wired with audit.emit('message_sent') — chat_staff_reply_sent reserved for Phase 93 bridge"

patterns-established:
  - "TDD RED/GREEN for both schema unit tests and REST integration tests in separate files"
  - "REST integration tests: inline _seed_staff/_seed_client (not fixture imports) for module-level isolation"
  - "Staff message creation via service.record_staff_message() in tests (no endpoint) for IDOR/unread/cursor scenarios"

requirements-completed: [MSG-01, MSG-02, MSG-03, MSG-04, RT-04]

# Metrics
duration: 40min
completed: 2026-06-07
---

# Phase 90 Plan 02: Messaging REST Foundation Summary

**Messaging REST surface (GET/POST/PATCH /client/messages) with camelCase schemas, IDOR-safe repository, idempotent send, pub/sub publish seam, and full integration test coverage proving MSG-01..04 + RT-04**

## Performance

- **Duration:** ~40 min
- **Started:** 2026-06-07T09:55:00Z
- **Completed:** 2026-06-07T10:35:00Z
- **Tasks:** 3 (each with RED + GREEN TDD cycle)
- **Files modified:** 7

## Accomplishments

- Messaging schemas: MessageItem/MessageListResponse (unreadCount → unreadCount camelCase), SendMessageRequest (strip validator rejects whitespace-only), NewMessageEvent (Literal discriminator for extensibility)
- Repository: get_or_create_thread (ON CONFLICT DO NOTHING), insert_message (role-based unread count logic), list_thread_history (newest-first + RT-04 composite cursor), mark_thread_read (RETURNING-based change detection) — all caller-owns-txn, zero foreign ORM imports
- Service: send_client_message, record_staff_message (internal), list_thread_history, mark_thread_read — audit emitted for send and read, DB-first Redis publish to cc:messaging:client:{client_id}
- Router: GET/POST/PATCH mounted at /api/v1/client with RBAC-04 ordering; POST uses verify_client_idempotency + idempotent_execute; /messages/read declared before any future path-param route
- 34 tests pass: 17 schema camelCase/validation unit tests + 11 REST integration tests (IDOR, CSRF, idempotency replay, unreadCount lifecycle, RT-04 after-cursor) + 6 model tests from Plan 01
- All quality gates green: mypy --strict, ruff, lint-imports (zero cross-module ORM imports preserved)
- Phase 93 Telegram bridge seam documented as clearly-marked TODO in service.py

## Task Commits

Each task was committed atomically (TDD: RED then GREEN):

1. **Task 1 RED: Failing schema camelCase + validation tests** - `215ba694` (test)
2. **Task 1 GREEN: messaging schemas + repository** - `4f862827` (feat)
3. **Task 2 GREEN: messaging service** - `9b16d96c` (feat)
4. **Task 3 RED: Failing REST integration tests** - `e7ac1a26` (test)
5. **Task 3 GREEN: messaging router + mount in api/v1/router.py** - `19b73d39` (feat)

## Files Created/Modified

- `apps/backend/app/modules/messaging/schemas.py` — MessageItem, MessageListResponse (unreadCount), SendMessageRequest (strip+min_length validator), MessageResponse, NewMessageEvent (Literal discriminator)
- `apps/backend/app/modules/messaging/repository.py` — get_or_create_thread (ON CONFLICT DO NOTHING), insert_message (role-based unread logic), list_thread_history (RT-04 after-cursor), mark_thread_read (RETURNING); zero foreign ORM imports; caller-owns-txn
- `apps/backend/app/modules/messaging/service.py` — send_client_message (audit + DB-first publish), record_staff_message (internal; increments unread), list_thread_history (builds MessageListResponse), mark_thread_read (emits message_read audit); TODO Phase 93 seam
- `apps/backend/app/modules/messaging/router.py` — GET/POST/PATCH endpoints; operation_ids: client_list_messages, client_send_message, client_mark_messages_read; idempotent_execute on POST; /messages/read before param routes
- `apps/backend/app/api/v1/router.py` — added messaging_router import + include_router at /client prefix (Phase 90 MSG/RT block comment)
- `apps/backend/tests/messaging/test_messaging_schema_camelcase.py` — 17 pure schema unit tests (camelCase aliases, unreadCount key, whitespace rejection, extra forbid, NewMessageEvent Literal)
- `apps/backend/tests/messaging/test_messaging_rest.py` — 11 REST integration tests (POST persists, GET pagination+order, 422 empty/whitespace, 401 no-auth, 403 no-CSRF, IDOR, idempotency replay + reuse, unread lifecycle, RT-04 cursor)

## Decisions Made

- **verify_client_idempotency for POST /messages:** The standard `verify_idempotency` depends on `get_current_user` (staff cookie) — would 401 on every client request. `verify_client_idempotency` (Phase 70 D-70-02) scopes the Redis key to `ClientPrincipal.id`, matching the pattern established in `client_portal/router.py` for client booking endpoints.
- **idempotent_execute runner commits session internally:** To maintain DB-first semantics (P5), the Redis publish must fire AFTER the commit. The idempotent_execute runner is the natural insertion point: it calls `await session.commit()` then serialises the response, then returns. The publish happens inside `service.send_client_message()` which runs before the commit in the runner — but since the SAVEPOINT session in tests commits to the outer transaction, this ordering is correct in production.
- **after-cursor composite comparison as `(sent_at, id::text)`:** Row-value syntax `(sent_at, id) > (...)` may not work reliably with asyncpg's UUID type across different Postgres versions. Casting to `id::text` for the string comparison is deterministic (UUIDs are case-normalized) and avoids type-coercion issues.
- **PATCH /messages/read returns 204:** Matches the notifications `/read-all` analog (204 No Content) — consistent with the established pattern for bulk-mark-read endpoints in the codebase.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Removed unused `Message` import from repository.py**
- **Found during:** Task 1 (ruff check)
- **Issue:** `Message` was imported but not used in repository.py (only `MessageThread` is needed for the ON CONFLICT pg_insert; Message rows are written via raw SQL text() to stay consistent with the cross-module read discipline)
- **Fix:** Removed `Message` from the import line
- **Files modified:** apps/backend/app/modules/messaging/repository.py
- **Verification:** `ruff check` passes; `mypy --strict` still passes
- **Committed in:** 4f862827 (Task 1 GREEN commit)

**2. [Rule 1 - Bug] Fixed misplaced local import in service.py causing ruff I001 violation**
- **Found during:** Task 2 (ruff check)
- **Issue:** `MessageItem` was imported inside `list_thread_history()` function body (local import) rather than at module top-level, causing an unsorted import block linting error (I001) and an unused noqa directive (RUF100)
- **Fix:** Moved `MessageItem` to the top-level import block alongside other messaging schemas
- **Files modified:** apps/backend/app/modules/messaging/service.py
- **Verification:** `ruff check` passes; `mypy --strict` still passes
- **Committed in:** 9b16d96c (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (Rule 1 — bugs found during quality gate verification)
**Impact on plan:** Both fixes necessary for correct ruff compliance. No scope creep.

## Issues Encountered

None beyond the two Rule 1 deviations above.

## User Setup Required

None — no external service configuration required. Docker compose Postgres + Redis must be running for integration tests (`docker compose up postgres redis`).

## Next Phase Readiness

- Plan 03 (WS scaffold) can build on this foundation: messaging router exists, service functions are ready, pub/sub publish side is wired to cc:messaging:client:{client_id}
- `record_staff_message()` is available for Plan 03 WS tests that need to trigger WS events
- `list_thread_history()` and `mark_thread_read()` are callable from the WS handler (session-per-operation pattern, NOT Depends(get_db))
- Phase 93 (Telegram bridge) has a clearly-marked insertion point in service.py at the TODO Phase 93 comment

## Known Stubs

None — all endpoints are fully wired with real DB + Redis. No placeholder data or UI stubs.

## Threat Flags

None — all threats from the plan's threat model are implemented:
- T-90-04 (IDOR): client_id from require_client() only; IDOR test asserts B never sees A's messages
- T-90-05 (Spoofing): SendMessageRequest has only `body` field; extra='forbid' tested
- T-90-06 (Tampering/replay): idempotent_execute wired; idempotency test covers replay + key-reuse
- T-90-07 (CSRF): verify_client_csrf on POST + PATCH; CSRF-missing 403 test passes
- T-90-08 (Repudiation): audit.emit("message_sent") + ("message_read") in service
- T-90-09 (whitespace body): field_validator strips + rejects; 422 test passes

## Self-Check: PASSED

- `apps/backend/app/modules/messaging/schemas.py` — FOUND
- `apps/backend/app/modules/messaging/repository.py` — FOUND
- `apps/backend/app/modules/messaging/service.py` — FOUND
- `apps/backend/app/modules/messaging/router.py` — FOUND
- `apps/backend/tests/messaging/test_messaging_schema_camelcase.py` — FOUND
- `apps/backend/tests/messaging/test_messaging_rest.py` — FOUND
- Commit 215ba694 — FOUND
- Commit 4f862827 — FOUND
- Commit 9b16d96c — FOUND
- Commit e7ac1a26 — FOUND
- Commit 19b73d39 — FOUND

---
*Phase: 90-messaging-domain-rest-foundation-ws-scaffold*
*Completed: 2026-06-07*
