---
phase: 87-notification-inbox
plan: "02"
subsystem: backend/notifications
tags: [notifications, inbox, push-tokens, endpoints, idor-safe, csrf, integration-tests]
dependency_graph:
  requires:
    - app.modules.notifications.service.list_client_notifications
    - app.modules.notifications.service.mark_notification_read
    - app.modules.notifications.service.mark_all_notifications_read
    - app.modules.notifications.service.register_push_token
  provides:
    - GET /api/v1/client/notifications (operation_id: client_list_notifications)
    - PATCH /api/v1/client/notifications/read-all (operation_id: client_mark_all_notifications_read)
    - PATCH /api/v1/client/notifications/{notification_id}/read (operation_id: client_mark_notification_read)
    - POST /api/v1/client/push-tokens (operation_id: client_register_push_token)
  affects:
    - apps/backend/app/api/v1/router.py (notifications_router mounted at /client)
tech_stack:
  added: []
  patterns:
    - RBAC-04 dep ordering on mutations (require_client → verify_client_csrf → get_db)
    - Literal[web,android,ios] on platform field (Pydantic-layer validation before DB)
    - 404-collapse IDOR pattern (mark_read scoped by principal client_id)
    - Deferred import at v1/router.py bottom block (D-20-MODULE separation)
key_files:
  created:
    - apps/backend/app/modules/notifications/router.py
    - apps/backend/tests/notifications/test_notifications_endpoints.py
  modified:
    - apps/backend/app/api/v1/router.py (notifications_router registration)
    - apps/backend/app/modules/notifications/schemas.py (Literal platform field)
decisions:
  - "D-87-02-PLATFORM-LITERAL: Added Literal['web','android','ios'] on ClientPushTokenRegisterRequest.platform — Pydantic layer returns 422 before the DB CheckConstraint fires; DB constraint is defence-in-depth. Without this, invalid platform triggers unhandled IntegrityError/500 through ASGITransport tests."
metrics:
  duration: "~14 min"
  completed_date: "2026-06-06"
  tasks_completed: 2
  files_created: 2
  files_modified: 2
---

# Phase 87 Plan 02: Notification Inbox HTTP Endpoints Summary

Four client-facing notification endpoints with IDOR-safe scoping, CSRF protection on mutations, and 15-test integration suite proving all security properties.

## What Was Built

### Task 1: notifications/router.py — 4 handlers

`app/modules/notifications/router.py` with `router = APIRouter(tags=["Client-Portal"])`:

**GET `/notifications`** (operation_id: `client_list_notifications`):
- `ResponseEnvelope[ClientNotificationsListResponse]`
- Deps: `query: PageQuery`, `client: ClientPrincipal = Depends(require_client())`, `session = Depends(get_db)`
- No CSRF dep — safe method per RBAC-04
- Wire shape: `{ items: [...], total: N, page: P, pageSize: S, unreadCount: N }`

**PATCH `/notifications/read-all`** (operation_id: `client_mark_all_notifications_read`):
- Status 204 No Content
- RBAC-04 deps: `require_client() → verify_client_csrf → get_db`
- Bulk mark-read scoped to principal client_id; session.commit() in handler

**PATCH `/notifications/{notification_id}/read`** (operation_id: `client_mark_notification_read`):
- `ResponseEnvelope[ClientNotificationItem]`
- RBAC-04 deps: `require_client() → verify_client_csrf → get_db`
- `notification_id` from path param only; `client_id` from principal ONLY (IDOR-safe)
- 404-collapse: NotFoundError raised by service when id not owned or already read
- Route declared AFTER `/read-all` to prevent path-param capture

**POST `/push-tokens`** (operation_id: `client_register_push_token`):
- Status 204 No Content; response body has no token (T-87-08)
- `payload: ClientPushTokenRegisterRequest` (extra='forbid' + Literal platform)
- RBAC-04 deps: `require_client() → verify_client_csrf → get_db`

Route order: `/notifications/read-all` declared before `/notifications/{notification_id}/read` (literal-before-param guard).

### Task 2: v1 router registration + 15 endpoint integration tests

**v1/router.py** additions:
```python
# Phase 87 INBOX-01/INBOX-02 — notification inbox + push-token registration.
from app.modules.notifications.router import router as notifications_router  # noqa: E402
v1.include_router(notifications_router, prefix="/client")
```
Separate router avoids a client_portal→notifications cross-module edge (D-20-MODULE).

**schemas.py** — added `Literal["web", "android", "ios"]` on `platform` field (see Deviations).

**test_notifications_endpoints.py** (15 tests, ASGITransport + SAVEPOINT harness):
- GET 200 with items + unreadCount
- GET newest-first ordering (raw SQL offset for deterministic timestamps)
- GET pagination honored (pageSize=1)
- GET 401 without auth
- IDOR: client A's GET returns only A's rows (B's notifications absent, total=0)
- PATCH /{id}/read: marks read, unreadCount drops by 1
- PATCH /{id}/read cross-client → 404 (IDOR-collapse, T-87-07)
- PATCH /{id}/read no CSRF → 403
- PATCH /read-all → 204, unreadCount=0 on next GET
- POST /push-tokens valid → 204
- POST /push-tokens idempotent (2 POSTs → exactly 1 alive row, DB-asserted)
- POST /push-tokens no token in response (T-87-08)
- POST /push-tokens extra field → 422 (extra='forbid', T-87-09)
- POST /push-tokens invalid platform → 422 (Literal validation, T-87-09)
- POST /push-tokens no CSRF → 403

## Verification Results

- `pytest tests/notifications/ -q` → 26 passed (11 service + 15 endpoint tests)
- `mypy app/modules/notifications/ app/api/v1/router.py` → Success: no issues found in 7 source files
- `lint-imports` → Contracts: 3 kept, 0 broken

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] asyncpg returns native UUID from raw SQL; UUID(native_uuid) raises AttributeError**
- **Found during:** Task 2 (first test run)
- **Issue:** `_create_notif` helper retrieved the inserted notification id via `row.scalar_one()` and passed it to `UUID(...)`. asyncpg's native UUID object doesn't have a `.replace` attribute so Python's `uuid.UUID.__init__` raises `AttributeError: 'asyncpg.pgproto.pgproto.UUID' object has no attribute 'replace'`
- **Fix:** `UUID(str(raw))` — `str()` works for both `str` and native UUID inputs
- **Files modified:** `tests/notifications/test_notifications_endpoints.py`
- **Commit:** f3dbd85c

**2. [Rule 2 - Missing Critical Functionality] Platform allow-list validation must be at Pydantic layer, not only DB**
- **Found during:** Task 2 (test for invalid platform)
- **Issue:** `ClientPushTokenRegisterRequest.platform` was typed as `str`. When an invalid platform (e.g. `"windows-phone"`) is submitted, the `upsert_push_token` INSERT fires the DB `CheckConstraint`, which propagates as `asyncpg.CheckViolationError → sqlalchemy.IntegrityError` — an unhandled exception that crashes the test via ASGITransport and would return 500 in production
- **Fix:** Changed `platform: str` to `platform: Literal["web", "android", "ios"]` in `ClientPushTokenRegisterRequest`. Pydantic validates before any service/DB call → returns 422. DB constraint retained as defence-in-depth (T-87-09)
- **Files modified:** `apps/backend/app/modules/notifications/schemas.py`
- **Commit:** f3dbd85c

## Service Contract (for Plan 04 PWA consumer)

### Wire paths

```
GET  /api/v1/client/notifications?page=1&pageSize=20
→ 200 { data: { items: [...], total: N, page: 1, pageSize: 20, unreadCount: N } }

PATCH /api/v1/client/notifications/read-all        [X-CSRF-Token required]
→ 204

PATCH /api/v1/client/notifications/{id}/read       [X-CSRF-Token required]
→ 200 { data: { id, kind, title, body, readAt, createdAt } }
→ 404 if id not owned by caller (IDOR-collapse)

POST  /api/v1/client/push-tokens                   [X-CSRF-Token required]
body: { token: string, platform: "web"|"android"|"ios" }
→ 204 (no body — T-87-08)
```

### Response envelope shape for GET /notifications

```json
{
  "data": {
    "items": [
      { "id": "uuid", "kind": "booking_confirmed", "title": "...", "body": "...",
        "readAt": null, "createdAt": "2026-06-06T08:00:00Z" }
    ],
    "total": 5,
    "page": 1,
    "pageSize": 20,
    "unreadCount": 3
  }
}
```

CSRF cookie key: `clubcore_client_csrf` (read from cookie jar after OTP verify).

## Threat Coverage

| Threat ID | Mitigated | How |
|-----------|-----------|-----|
| T-87-06 | Yes | require_client() on all handlers; verify_client_csrf on PATCH/POST (RBAC-04) |
| T-87-07 | Yes | list scoped by principal client_id; cross-client id → 404 (IDOR-collapse test present) |
| T-87-08 | Yes | 204 No Content on POST /push-tokens; no-leakage test asserts body empty |
| T-87-09 | Yes | extra='forbid' → 422 (test); Literal platform → 422 (test + schema) |
| T-87-SC | N/A | No new package installs in this plan |

## Self-Check: PASSED

Files created/exist:
- [x] apps/backend/app/modules/notifications/router.py
- [x] apps/backend/tests/notifications/test_notifications_endpoints.py

Files modified:
- [x] apps/backend/app/api/v1/router.py
- [x] apps/backend/app/modules/notifications/schemas.py

Commits exist:
- [x] 9ac09518 — feat(87-02): notifications router with 4 RBAC-04-ordered handlers
- [x] f3dbd85c — feat(87-02): v1 registration + endpoint test suite
