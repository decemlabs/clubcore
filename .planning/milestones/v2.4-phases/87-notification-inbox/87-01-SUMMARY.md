---
phase: 87-notification-inbox
plan: "01"
subsystem: backend/notifications
tags: [notifications, inbox, push-tokens, alembic, tdd, idor-safe]
dependency_graph:
  requires: []
  provides:
    - app.modules.notifications.service.create_notification
    - app.modules.notifications.service.list_client_notifications
    - app.modules.notifications.service.mark_notification_read
    - app.modules.notifications.service.mark_all_notifications_read
    - app.modules.notifications.service.register_push_token
  affects:
    - alembic migrations chain (0059 → 0060 → 0061 → head)
    - alembic/env.py (model registration for autogenerate)
tech_stack:
  added: []
  patterns:
    - pg_insert ON CONFLICT DO NOTHING on named UNIQUE constraint (SAVEPOINT-safe dedup)
    - UPDATE-first + INSERT-fallback for push token upsert (partial-index revival)
    - Raw SQL text() for all reads (D-54-08); ORM add+flush for own-module inserts
key_files:
  created:
    - apps/backend/app/modules/notifications/models.py
    - apps/backend/app/modules/notifications/schemas.py
    - apps/backend/app/modules/notifications/repository.py
    - apps/backend/app/modules/notifications/service.py
    - apps/backend/alembic/versions/0060_in_app_notifications.py
    - apps/backend/alembic/versions/0061_client_push_tokens.py
    - apps/backend/tests/notifications/__init__.py
    - apps/backend/tests/notifications/conftest.py
    - apps/backend/tests/notifications/test_notifications_service.py
  modified:
    - apps/backend/alembic/env.py (model registration import)
    - apps/backend/app/modules/notifications/__init__.py (module docstring)
decisions:
  - "D-87-01-DEDUP-ON-CONFLICT: Used pg_insert ON CONFLICT DO NOTHING on named UNIQUE constraint (not IntegrityError + rollback) — SAVEPOINT-safe within the test harness and production webhook context; mirrors D-82 welcome-bonus approach"
  - "D-87-02-PUSH-TOKEN-UPDATE-FIRST: register_push_token uses UPDATE-first + INSERT-fallback pattern instead of ON CONFLICT with partial index — partial index WHERE predicate excludes unregistered rows, making ON CONFLICT unable to revive them; UPDATE-first covers both alive-idempotent and unregistered-revival paths in one round-trip"
  - "D-87-03-ORDERING-TEST-RAW-SQL: test_list_client_notifications_returns_newest_first forces distinct created_at via raw SQL (now() - interval '10 seconds') to avoid non-deterministic ordering when both inserts land in the same transaction microsecond"
metrics:
  duration: "~25 min"
  completed_date: "2026-06-06"
  tasks_completed: 2
  files_created: 9
  files_modified: 2
---

# Phase 87 Plan 01: Notification Inbox Data Layer Summary

In-app notification inbox + push-token registration backend data layer: two new tables, a 5-function service contract with IDOR-safe scoping, idempotent dedup, and full test coverage.

## What Was Built

### Task 1: Models + Migrations (0060/0061)

Two ORM models on `Base, UUIDPkMixin, TimestampMixin`:

**InAppNotification** (`in_app_notifications`):
- Columns: `client_id` (FK clients.id RESTRICT), `source_type`, `source_id` (UUID), `kind`, `title`, `body`, `read_at` (nullable)
- `CheckConstraint` on `kind IN (booking_confirmed, booking_cancelled_by_client, booking_cancelled_by_owner, booking_rescheduled, payment_succeeded, autopay_charge_succeeded, autopay_charge_failed)` — name `ck_in_app_notifications_kind`
- `UniqueConstraint(client_id, source_type, source_id, kind)` — name `uq_in_app_notifications_client_source_kind` (idempotent dedup guard)
- `Index ix_in_app_notifications_client_id`

**ClientPushToken** (`client_push_tokens`):
- Columns: `client_id` (FK clients.id RESTRICT), `token`, `platform`, `unregistered_at` (nullable soft-delete)
- `CheckConstraint("platform IN ('web','android','ios')")` — name `ck_client_push_tokens_platform`
- Partial UNIQUE index `uq_client_push_tokens_client_token_alive` on (client_id, token) WHERE unregistered_at IS NULL
- `Index ix_client_push_tokens_client_id`

Migration chain: `0059_seed_gym_info → 0060_in_app_notifications → 0061_client_push_tokens` (head).

### Task 2: Schemas + Repository + Service

**Schemas:**
- `ClientNotificationItem(ResponseData)`: id, kind, title, body, read_at (nullable), created_at
- `ClientNotificationsListResponse(ResponseData)`: items, total, page, page_size, unread_count — custom DTO embedding unread_count alongside standard pagination fields
- `ClientPushTokenRegisterRequest(BackendSchemaBase)`: token, platform — extra='forbid' (T-87-04)

**Repository** (caller-owns-txn, no session.commit):
- `insert_notification`: `pg_insert ON CONFLICT DO NOTHING` on named UNIQUE constraint (SAVEPOINT-safe)
- `count_notifications`: single SQL with COUNT(*) FILTER for total + unread_count
- `list_notifications`: raw SQL ORDER BY created_at DESC LIMIT/OFFSET
- `mark_read`: UPDATE + RETURNING id → scalar_one_or_none (mypy-clean)
- `fetch_one_owned`: SELECT WHERE id AND client_id (IDOR-safe)
- `mark_all_read`: UPDATE WHERE client_id AND read_at IS NULL
- `upsert_push_token`: UPDATE-first (revives unregistered tokens) + INSERT-fallback

**Service:**
- `create_notification(session, *, client_id, source_type, source_id, kind, title, body) -> None`
- `list_client_notifications(session, client_id, query: PageQuery) -> ClientNotificationsListResponse`
- `mark_notification_read(session, *, client_id, notification_id) -> ClientNotificationItem`
- `mark_all_notifications_read(session, *, client_id) -> None`
- `register_push_token(session, *, client_id, payload: ClientPushTokenRegisterRequest) -> None`

## Verification Results

- `alembic upgrade head` → clean to 0061_client_push_tokens
- `alembic current` → `0061_client_push_tokens (head)`
- `alembic check` → `No new upgrade operations detected.`
- `pytest tests/notifications/ -q` → 11 passed
- `mypy app/modules/notifications/` → `Success: no issues found in 5 source files`
- `lint-imports` → `Contracts: 3 kept, 0 broken`
- `grep session.commit app/modules/notifications/{repository,service}.py` → 0 actual calls (only docstring mentions)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] SAVEPOINT-safe dedup — replaced IntegrityError + rollback with ON CONFLICT DO NOTHING**
- **Found during:** Task 2 TDD RED → GREEN
- **Issue:** Plan specified `IntegrityError → await session.rollback()` for dedup. In SAVEPOINT-mode test sessions (join_transaction_mode='create_savepoint'), `session.rollback()` rolls back to the beginning of the savepoint, invalidating all ORM objects (including `client.id`) and breaking subsequent test statements
- **Fix:** Used `pg_insert ON CONFLICT DO NOTHING` on the named UNIQUE constraint `uq_in_app_notifications_client_source_kind` — SAVEPOINT-safe (no rollback needed), same approach as loyalty's `accrue_welcome_bonus`. Service logs INFO `notification_dedup_conflict` when ON CONFLICT fires
- **Files modified:** `repository.py`, `service.py`
- **Commit:** 776b4d94

**2. [Rule 1 - Bug] Push token revival — replaced ON CONFLICT partial-index with UPDATE-first pattern**
- **Found during:** Task 2 TDD GREEN (test_register_push_token_revives_unregistered failing)
- **Issue:** Plan's `ON CONFLICT DO UPDATE ... index_where="unregistered_at IS NULL"` only fires when the partial index matches (i.e., the existing row is alive). A previously unregistered token has `unregistered_at IS NOT NULL`, so the partial index arbiter excludes it — no conflict fires, and a second row is inserted instead of reviving the original
- **Fix:** UPDATE-first (set `unregistered_at = NULL, platform = :platform`) for any (client_id, token) row regardless of unregistered_at state; INSERT-fallback if no row found. One round-trip, handles both cases
- **Files modified:** `repository.py`
- **Commit:** 776b4d94

**3. [Rule 1 - Bug] mypy: Result[Any].rowcount not accessible**
- **Found during:** Task 2 GREEN mypy run
- **Issue:** `result.rowcount` on `await session.execute(text(...))` return value is not visible to mypy's async SQLAlchemy stubs — `Result[Any]` has no `rowcount` attribute at type-check time
- **Fix:** Switched `mark_read` and `upsert_push_token` to use `RETURNING id + .scalar_one_or_none()` instead of `.rowcount` for detecting whether rows were updated
- **Files modified:** `repository.py`
- **Commit:** 776b4d94

**4. [Rule 1 - Bug] Non-deterministic ordering test**
- **Found during:** Task 2 TDD GREEN
- **Issue:** `test_list_client_notifications_returns_newest_first` originally inserted both rows via `service.create_notification` within the same test transaction, resulting in identical `created_at` timestamps and non-deterministic ORDER BY
- **Fix:** Test now inserts the older row via raw SQL with `now() - interval '10 seconds'` to force a distinct earlier timestamp
- **Files modified:** `tests/notifications/test_notifications_service.py`
- **Commit:** 776b4d94

## Service Contract (for Plan 02/03/04 consumers)

```python
# create_notification — co-transactional inbox insert (caller-owns-txn)
async def create_notification(
    session: AsyncSession,
    *,
    client_id: UUID,
    source_type: str,   # e.g. "booking", "online_payment"
    source_id: UUID,    # the source entity id
    kind: str,          # one of 7 valid kinds (CheckConstraint enforced)
    title: str,         # server-rendered Russian string
    body: str,          # server-rendered Russian string
) -> None: ...

# list_client_notifications — paginated inbox read
async def list_client_notifications(
    session: AsyncSession,
    client_id: UUID,
    query: PageQuery,
) -> ClientNotificationsListResponse: ...
# Returns: { items: [...], total: int, page: int, page_size: int, unread_count: int }

# mark_notification_read — IDOR-safe (404-collapse)
async def mark_notification_read(
    session: AsyncSession,
    *,
    client_id: UUID,
    notification_id: UUID,
) -> ClientNotificationItem: ...  # raises NotFoundError if not owned / already read

# mark_all_notifications_read
async def mark_all_notifications_read(
    session: AsyncSession,
    *,
    client_id: UUID,
) -> None: ...

# register_push_token — idempotent upsert
async def register_push_token(
    session: AsyncSession,
    *,
    client_id: UUID,
    payload: ClientPushTokenRegisterRequest,  # { token: str, platform: str }
) -> None: ...
```

**Final migration revision:** `0061_client_push_tokens`
**Wire shape of `ClientNotificationsListResponse`:** `{ items: [...], total: N, page: P, pageSize: S, unreadCount: N }` (camelCase via `alias_generator=to_camel`)

## TDD Gate Compliance

- RED commit: `04111241` — test(87-01): add failing tests for notifications service (TDD RED)
- GREEN commit: `776b4d94` — feat(87-01): implement notifications schemas, repository, service (TDD GREEN)

## Self-Check: PASSED

Files created/exist:
- [x] apps/backend/app/modules/notifications/models.py
- [x] apps/backend/app/modules/notifications/schemas.py
- [x] apps/backend/app/modules/notifications/repository.py
- [x] apps/backend/app/modules/notifications/service.py
- [x] apps/backend/alembic/versions/0060_in_app_notifications.py
- [x] apps/backend/alembic/versions/0061_client_push_tokens.py
- [x] apps/backend/tests/notifications/test_notifications_service.py

Commits exist:
- [x] 26b79225 — models + migrations Task 1
- [x] 04111241 — TDD RED test commit
- [x] 776b4d94 — TDD GREEN implementation + test fix
