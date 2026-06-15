---
phase: 116-chat-inbox-exports
plan: "01"
subsystem: backend-messaging
tags: [messaging, rbac, migration, staff-inbox, rest-api]
dependency_graph:
  requires: []
  provides:
    - staff-messaging-rest-endpoints
    - resource-messages-rbac
    - migration-0073-staff-last-read-at
  affects:
    - apps/backend/app/modules/messaging/
    - apps/backend/app/core/permissions.py
    - apps/admin-app/src/shared/session/can.ts
    - apps/admin-app/src/shared/session/registry.ts
tech_stack:
  added:
    - "Resource.MESSAGES StrEnum member in permissions.py"
    - "StaffReplyRequest / StaffThreadItem / StaffInboxResponse / StaffMessageItem / StaffThreadHistoryResponse Pydantic schemas"
    - "staff_last_read_at TIMESTAMPTZ column on message_threads (migration 0073)"
  patterns:
    - "RBAC-04 ordering: require_permission BEFORE verify_csrf on mutation endpoints"
    - "CR-02 / DB-first: commit then publish_new_message post-commit"
    - "D-54-08: raw SQL text() + :name bind params + str(UUID) casts in all new repository functions"
    - "caller-owns-txn: no session.commit() in repository or service functions (D-32-10/D-49-19)"
key_files:
  created:
    - apps/backend/app/modules/messaging/staff_router.py
    - apps/backend/alembic/versions/0073_message_thread_staff_last_read_at.py
    - apps/backend/tests/integration/messaging/test_staff_messaging.py
    - apps/backend/tests/integration/messaging/__init__.py
  modified:
    - apps/backend/app/core/permissions.py
    - apps/backend/app/modules/messaging/repository.py
    - apps/backend/app/modules/messaging/service.py
    - apps/backend/app/modules/messaging/schemas.py
    - apps/backend/app/modules/messaging/models.py
    - apps/backend/app/api/v1/router.py
    - apps/admin-app/src/shared/session/can.ts
    - apps/admin-app/src/shared/session/registry.ts
    - apps/backend/tests/unit/test_permissions.py
    - apps/backend/tests/integration/test_rbac_parity.py
decisions:
  - "staff_last_read_at watermark chosen over counter column: simpler, correct (NULL = never read = all client msgs unread), no backfill needed"
  - "StaffThreadHistoryResponse uses full chronological list (not paginated) per v1 scope"
  - "send_staff_reply reuses existing record_staff_message (audit, reply-as-read, insert_message(role='staff'))"
  - "No forward_to_staff ARQ enqueue on staff reply — that bridge is client→staff only; staff→client uses WS + Telegram via publish_new_message"
  - "OWNER_ONLY count grows 45 → 46 with single new pair (CREATE, MESSAGES)"
metrics:
  duration: "~590 seconds"
  completed: "2026-06-15"
  tasks_completed: 3
  files_modified: 14
---

# Phase 116 Plan 01: Staff Messaging REST + RBAC + Migration Summary

Staff-side inbox REST API over the existing `messaging` module. Owner and reception can list
all client threads and read history; only owner can send (CREATE, MESSAGES in OWNER_ONLY).
RBAC parity updated atomically (46 entries). Migration 0073 adds `staff_last_read_at` column.

## Tasks Completed

| Task | Commit | Files |
|------|--------|-------|
| 1: RBAC Resource.MESSAGES + migration 0073 | 9669f81b | permissions.py, can.ts, registry.ts, test_permissions.py, test_rbac_parity.py, 0073 migration, models.py |
| 2: Staff repository + service + schemas | 83b471d6 | repository.py, service.py, schemas.py |
| 3: Staff router + v1 registration + tests | b8c2536e | staff_router.py, v1/router.py, test_staff_messaging.py |

## Wire Shapes (Final camelCase — FE Plan 116-03 Reference)

### GET /api/v1/messages/threads → ResponseEnvelope[StaffInboxResponse]

```json
{
  "data": {
    "items": [
      {
        "id": "uuid",
        "clientId": "uuid",
        "clientName": "Иван Тестов",
        "clientInitials": "ИТ",
        "lastMessageAt": "2026-06-15T12:47:00Z",
        "lastMessageBody": "Привет, хочу записаться",
        "lastMessageRole": "client",
        "staffUnreadCount": 3
      }
    ],
    "total": 1
  }
}
```

Field notes:
- `lastMessageAt`, `lastMessageBody`, `lastMessageRole` are `null` if the thread has no messages yet
- `staffUnreadCount`: derived from `COUNT(*) WHERE role='client' AND (staff_last_read_at IS NULL OR sent_at > staff_last_read_at)` — watermark-based
- camelCase wire via `alias_generator=to_camel` on `ResponseData` base

### GET /api/v1/messages/threads/{thread_id} → ResponseEnvelope[StaffThreadHistoryResponse]

```json
{
  "data": {
    "threadId": "uuid",
    "messages": [
      {
        "id": "uuid",
        "role": "client",
        "body": "Привет, хочу записаться",
        "sentAt": "2026-06-15T12:47:00Z"
      },
      {
        "id": "uuid",
        "role": "staff",
        "body": "Привет! Запись возможна.",
        "sentAt": "2026-06-15T12:48:00Z"
      }
    ]
  }
}
```

Field notes:
- `messages` is chronological (oldest first), full history (no pagination in v1)
- `role` is `"client"` or `"staff"` (open string, not enum, for forward compat)

### POST /api/v1/messages/threads/{thread_id}/reply

Request body:
```json
{ "body": "Привет! Запись возможна." }
```
- `body`: required string, 1–4000 chars, non-whitespace-only (`min_length=1, max_length=4000`)

Response → `ResponseEnvelope[StaffMessageItem]`:
```json
{
  "data": {
    "id": "uuid",
    "role": "staff",
    "body": "Привет! Запись возможна.",
    "sentAt": "2026-06-15T12:48:00Z"
  }
}
```

### POST /api/v1/messages/threads/{thread_id}/read → 204 No Content

No request body. No response body. Both roles allowed.

## Staff Unread Derivation

`staff_last_read_at` column on `message_threads` (TIMESTAMPTZ, nullable):
- `NULL` = staff has never read this thread → all client messages are unread
- Set to `now()` when `POST /threads/{id}/read` is called
- `staffUnreadCount` derived on every inbox fetch: `COUNT(*) WHERE role='client' AND (mt.staff_last_read_at IS NULL OR m.sent_at > mt.staff_last_read_at)`

Rationale: watermark avoids a separate counter column and is always consistent with the actual message set — no chance of getting out of sync with concurrent inserts.

## RBAC Summary

| Permission | Owner | Reception |
|------------|-------|-----------|
| (LIST, MESSAGES) — GET /threads | allowed | allowed |
| (VIEW, MESSAGES) — GET /threads/{id} | allowed | allowed |
| (VIEW, MESSAGES) — POST /threads/{id}/read | allowed | allowed |
| (CREATE, MESSAGES) — POST /threads/{id}/reply | allowed | **403 forbidden** |

OWNER_ONLY count: **46** (was 45 after Phase 113, +1 for (CREATE, MESSAGES)).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Migration revision ID format required full filename**
- **Found during:** Task 1
- **Issue:** Alembic migration file used `down_revision = "0072"` but Alembic requires the full revision ID string matching the file's `revision =` field (`"0072_promo_codes_description"`)
- **Fix:** Updated both `revision` and `down_revision` in 0073 migration to use full filename-based IDs matching the project's convention
- **Files modified:** `alembic/versions/0073_message_thread_staff_last_read_at.py`
- **Commit:** 9669f81b

**2. [Rule 2 - Missing critical functionality] ORM model missing staff_last_read_at column**
- **Found during:** Task 1 (alembic check)
- **Issue:** `alembic check` detected the column in the DB (applied migration) but not in the ORM model `MessageThread`, producing a drift warning
- **Fix:** Added `staff_last_read_at` column to `MessageThread` ORM model
- **Files modified:** `apps/backend/app/modules/messaging/models.py`
- **Commit:** 9669f81b

**3. [Rule 1 - Bug] Test CSRF tokens required on POST endpoints**
- **Found during:** Task 3 test run
- **Issue:** Integration test POST requests for /reply and /read returned 403 csrf_mismatch because tests were not sending the `X-CSRF-Token` header
- **Fix:** Added `_csrf(client)` helper that reads `clubcore_csrf` cookie, applied to all POST calls in the test (mirrors test_loyalty_grant.py pattern)
- **Files modified:** `tests/integration/messaging/test_staff_messaging.py`
- **Commit:** b8c2536e

## Known Stubs

None. All staff inbox endpoints are fully wired to real DB queries with no placeholder data.

## Threat Flags

None. All threat register entries (T-116-01 through T-116-06, T-116-SC) were addressed:
- T-116-01: RBAC enforced — reception → 403 on POST /reply (integration test verifies)
- T-116-02: CSRF on writes, require_permission declared BEFORE verify_csrf (RBAC-04)
- T-116-03: thread_id resolved server-side via get_thread_client_id; no client-supplied client_id
- T-116-04: All new SQL via text() + :name bind params + str(UUID) casts
- T-116-05: record_staff_message emits message_sent audit co-transactionally
- T-116-06: accepted (single-club scale)

## Self-Check: PASSED
