---
phase: 87-notification-inbox
reviewed: 2026-06-06T14:00:00Z
depth: standard
files_reviewed: 9
files_reviewed_list:
  - apps/client-pwa/src/screens/sheets/NotificationsSheet.jsx
  - apps/backend/app/modules/notifications/service.py
  - apps/backend/app/modules/notifications/repository.py
  - apps/backend/app/modules/notifications/schemas.py
  - apps/backend/app/modules/notifications/router.py
  - apps/backend/app/modules/bookings/service.py
  - apps/backend/alembic/versions/0061_client_push_tokens.py
  - packages/api-client/src/schema.d.ts
  - apps/backend/tests/notifications/test_notifications_endpoints.py
  - apps/backend/tests/notifications/test_notifications_event_hooks.py
findings:
  critical: 0
  warning: 1
  info: 2
  total: 3
status: issues_found
---

# Phase 87: Code Review Report (Iteration 2 — Re-review)

**Reviewed:** 2026-06-06T14:00:00Z
**Depth:** standard
**Files Reviewed:** 9
**Status:** issues_found

## Summary

All 8 prior findings (3 critical, 5 warnings) from the first review have been genuinely resolved. The re-review confirms:

- **CR-01 resolved.** `handleMarkAll` rollback logic is now correct. `prevItems` and `prevReadIds` are captured before any `setState` call (lines 213–214). The optimistic `setOptimisticReadIds` at line 222 filters `allItems` (the raw backing store) rather than `effectiveItems`, so already-read server-confirmed items are not added to the optimistic set. Rollback in `onError` restores both to their pre-call values. Items that were already optimistically marked via individual `markRead.mutate` calls have `readAt === null` in the raw `allItems` store (tracked separately via `optimisticReadIds`) so they are correctly included in the new set after mark-all, and the rollback restores them to the pre-handleMarkAll `optimisticReadIds` value.
- **CR-02 resolved.** `schema.d.ts` now contains both the path entry `/api/v1/client/push-tokens` (lines 947–963) and the `client_register_push_token` operation (lines 10237–10270) with correct request/response shape.
- **CR-03 resolved.** Migration 0061 creates the partial unique index on `(token)` alone (not `(client_id, token)`). `upsert_push_token` Step 1 soft-deletes any other client's alive row before proceeding. Same-client re-registration is handled by Step 2 UPDATE (idempotent no-op). The DB partial unique index provides defence-in-depth.
- **WR-01 resolved.** `cancel_booking` now has an `else` branch (lines 1619–1626) that logs `cancel_booking_notification_unexpected_role` for any actor role that is neither OWNER nor RECEPTION.
- **WR-02 resolved.** `mark_notification_read` now uses a two-phase approach: attempt UPDATE (no-op if already read), then fetch the owned row. Returns 200 with current state for own already-read notifications; 404 only for absent or cross-client IDs. Confirmed by test at lines 416–453 (idempotent 200) and 456–481 (cross-client 404).
- **WR-03 resolved.** `create_booking_via_bot` has Step 8.5 at lines 1309–1323 inserting `booking_confirmed` co-transactionally.
- **WR-04 resolved.** `create_booking_for_client` has Step 8.5 at lines 1464–1478 inserting `booking_confirmed` co-transactionally.
- **WR-05 resolved.** `ClientPushTokenRegisterRequest.token` is `Annotated[str, Field(min_length=1, max_length=512)]`.

One new warning was introduced by the CR-03 fix and two pre-existing info items are documented.

---

## Warnings

### WR-01: `upsert_push_token` Step 3 INSERT is not guarded against the concurrent cross-client registration race

**File:** `apps/backend/app/modules/notifications/repository.py:252–260`

**Issue:** The three-step `upsert_push_token` logic (soft-delete other client's row → UPDATE own row → INSERT if no row existed) has a narrow TOCTOU race when two different clients (B and C) register the same token T concurrently, and T is currently held by a third client A:

1. Both B and C execute Step 1 (soft-delete A's row). One of them updates A's row; the other's WHERE clause finds nothing (A's row already unregistered). Both continue.
2. Both execute Step 2 (`UPDATE WHERE client_id = B/C, token = T`). Neither has a row yet, so both get `updated_id = None`.
3. Both execute Step 3: `session.add(ClientPushToken(client_id=B/C, token=T)); await session.flush()`. One flush succeeds. The other violates the partial unique index `uq_client_push_tokens_token_alive` on `(token) WHERE unregistered_at IS NULL` and raises an unhandled `sqlalchemy.exc.IntegrityError` that propagates as HTTP 500.

The partial unique index correctly prevents the privacy-leak (two alive rows for the same device), but the unhandled `IntegrityError` produces a 500 rather than a clean 4xx response for the losing client. The router's "No try/except — AppError bubbles to _app_error_handler" comment applies to `AppError` subclasses; `IntegrityError` is not an `AppError` and is not handled by the global exception handler.

This race requires two different clients registering the same physical device token at the same millisecond — an unlikely real-world event (device tokens are OS/browser-assigned, not user-controlled) — but the 500 outcome is avoidable.

**Fix:** Catch `IntegrityError` from `session.flush()` in Step 3 and retry Step 2 (the concurrent winner has now inserted a row that Step 2 can UPDATE) or surface as a 409 conflict:

```python
if updated_id is None:
    new_token = ClientPushToken(
        client_id=client_id,
        token=token,
        platform=platform,
    )
    session.add(new_token)
    try:
        await session.flush()
    except IntegrityError:
        # Concurrent cross-client registration won the race — revoke their row
        # and retry the UPDATE for this client.
        await session.rollback()
        await session.execute(
            text(
                "UPDATE client_push_tokens "
                "SET unregistered_at = now(), updated_at = now() "
                "WHERE token = :tok AND client_id != :cid AND unregistered_at IS NULL"
            ),
            {"tok": token, "cid": str(client_id)},
        )
        new_token2 = ClientPushToken(
            client_id=client_id,
            token=token,
            platform=platform,
        )
        session.add(new_token2)
        await session.flush()
```

Alternatively, use a `pg_insert(...).on_conflict_do_update(...)` for Step 3 instead of the ORM add + flush, keying the conflict on the partial index.

---

## Info

### IN-01: `NotificationsSheet` calls hooks after a conditional early return — Rules of Hooks violation

**File:** `apps/client-pwa/src/screens/sheets/NotificationsSheet.jsx:127–137`

**Issue:** `useState`, `useRef`, `useEffect`, and the custom query hooks are all called after the feature-flag early return at lines 127–129:

```jsx
if (!NOTIFICATIONS_FEATURE_FLAGS.notificationsInbox) {
  return null  // ← early return
}

const [page, setPage] = React.useState(1)  // ← hooks after conditional return
```

React's Rules of Hooks forbid calling hooks after a conditional early return. The flag constant is `true` at this phase so the early return is dead code and no runtime error occurs, but:
1. ESLint `react-hooks/rules-of-hooks` will flag this.
2. If the flag is ever toggled to `false` at runtime (e.g. remote config), the component would throw "Invalid hook call" errors.

**Fix:** Move the feature-flag gate to wrap the rendered output, not the hooks:

```jsx
export function NotificationsSheet({ onClose }) {
  const [page, setPage] = React.useState(1)
  // ... all hooks ...

  if (!NOTIFICATIONS_FEATURE_FLAGS.notificationsInbox) {
    return null
  }

  return (/* JSX */)
}
```

---

### IN-02: `test_post_push_token_invalid_platform_returns_error` comment contradicts actual validation layer

**File:** `apps/backend/tests/notifications/test_notifications_endpoints.py:663–668`

**Issue:** The test comment states "service layer passes the value through without pre-validation so the DB constraint fires." This is factually wrong: `ClientPushTokenRegisterRequest.platform` is `Literal["web", "android", "ios"]`, so Pydantic rejects `"windows-phone"` with a 422 before the service layer is reached. The DB `CheckConstraint` is a defence-in-depth layer and is not the primary rejection path.

The test assertion `assert resp.status_code != 204` is too weak — a 500 (e.g. if a bypass path were introduced and the DB constraint were the only guard) would satisfy `!= 204` but represents a regression. Asserting the specific expected status code 422 would be stronger.

**Fix:** Update the assertion and comment:

```python
# Pydantic Literal validation rejects the unknown platform with 422
# before the request reaches the service or DB layer (T-87-09).
assert resp.status_code == 422, (
    f"Expected 422 for invalid platform 'windows-phone' (Pydantic Literal), "
    f"got {resp.status_code}: {resp.text}"
)
```

---

_Reviewed: 2026-06-06T14:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
