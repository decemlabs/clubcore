---
phase: 87-notification-inbox
reviewed: 2026-06-06T12:00:00Z
depth: standard
files_reviewed: 20
files_reviewed_list:
  - apps/backend/app/modules/notifications/models.py
  - apps/backend/app/modules/notifications/schemas.py
  - apps/backend/app/modules/notifications/repository.py
  - apps/backend/app/modules/notifications/service.py
  - apps/backend/app/modules/notifications/router.py
  - apps/backend/app/api/v1/router.py
  - apps/backend/app/api/v1/_internal/yookassa/handlers.py
  - apps/backend/app/modules/bookings/service.py
  - apps/backend/app/modules/autopay_charges/service.py
  - apps/backend/alembic/versions/0060_in_app_notifications.py
  - apps/backend/alembic/versions/0061_client_push_tokens.py
  - apps/backend/tests/notifications/test_notifications_endpoints.py
  - apps/backend/tests/notifications/test_notifications_event_hooks.py
  - apps/client-pwa/src/lib/clientQueries.ts
  - apps/client-pwa/src/data/index.js
  - apps/client-pwa/src/screens/sheets/NotificationsSheet.jsx
  - apps/client-pwa/src/screens/HomeScreen.jsx
  - apps/client-pwa/eslint.config.js
  - packages/api-client/src/schema.d.ts
findings:
  critical: 3
  warning: 5
  info: 3
  total: 11
status: issues_found
---

# Phase 87: Code Review Report

**Reviewed:** 2026-06-06T12:00:00Z
**Depth:** standard
**Files Reviewed:** 20
**Status:** issues_found

## Summary

Phase 87 delivers an in-app notification inbox (INBOX-01/02/03) and push-token registration (INBOX-02). The core security properties are well-designed: client_id is sourced exclusively from `ClientPrincipal` across all endpoints, 404-collapse is correctly implemented for cross-client mark-read attempts, the anti-oracle property for `payment_canceled` is maintained (zero inbox rows), and the `ON CONFLICT DO NOTHING` dedup strategy is SAVEPOINT-safe. Migration chain is clean and the partial-unique-index pattern for push tokens mirrors the established precedent in migration 0052.

Three critical issues were found: a semantic bug in the optimistic rollback for mark-all-read in the PWA, the absence of the `/api/v1/client/push-tokens` endpoint from `schema.d.ts`, and a broken idempotency guarantee for the push-token upsert when the token has a concurrent live row from a different client. Five warnings address real-but-non-crashing defects.

---

## Critical Issues

### CR-01: PWA optimistic rollback for mark-all-read captures stale closure values

**File:** `apps/client-pwa/src/screens/sheets/NotificationsSheet.jsx:217-224`

**Issue:** The `handleMarkAll` function captures `allItems` and `optimisticReadIds` in a closure at call time (via `markAllRead.mutate(..., { onError: ... })`). The `onError` rollback callback reads these captured values:

```js
markAllRead.mutate(undefined, {
  onError: () => {
    setAllItems(allItems)             // <-- stale closure
    setOptimisticReadIds(optimisticReadIds)  // <-- stale closure
  },
})
```

However, at the top of `handleMarkAll`, the optimistic update runs `setAllItems(snapshot)` and `setOptimisticReadIds(...)` first, which schedules React state updates. The closure variables `allItems` and `optimisticReadIds` that `onError` closes over are the **pre-snapshot** values at the time `mutate` is called — which is the correct pre-mutation state. This appears correct at first glance, but there is a subtlety: if the component re-renders between the `mutate` call and the `onError` callback (e.g. background refetch triggered by `onSettled` invalidation), a load-more or auto-mark-on-open event may have updated `allItems` in the interim. Rolling back to the version captured at `handleMarkAll` call time would then discard those new items. The pattern used by the background auto-mark effect (`markedOnOpenRef`, `markRead.mutate`) has no rollback at all; if that interleaves with `handleMarkAll` and `handleMarkAll` then errors, the rolled-back `allItems` loses those intermediate mark-read changes.

The correct fix is to use the functional updater form of `setAllItems` in `onError`, restoring by diff rather than full replace, or to snapshot inside the `mutate` callback after `setAllItems` and `setOptimisticReadIds` have been applied:

```js
const handleMarkAll = () => {
  const prevItems = allItems           // capture BEFORE setState
  const prevReadIds = optimisticReadIds

  const now = new Date().toISOString()
  setAllItems(prev => prev.map(item => ({ ...item, readAt: now })))
  setOptimisticReadIds(new Set(allItems.map(i => i.id)))

  markAllRead.mutate(undefined, {
    onError: () => {
      setAllItems(prevItems)
      setOptimisticReadIds(prevReadIds)
      showToast('Не удалось отметить прочитанными')
    },
  })
}
```

As written the rollback uses `allItems` and `optimisticReadIds` from the closure, but `setAllItems(snapshot)` was already called — these are the pre-snapshot values (correct), BUT because `setAllItems(snapshot)` and `setOptimisticReadIds(...)` are called before `mutate`, the closure in `onError` must close over the *original* pre-handleMarkAll values. In the current code, `snapshot` is derived from `effectiveItems.map(...)` (line 213) and `allItems` is the pre-optimistic state — so the rollback does restore to the correct pre-call state. The actual bug is that `snapshot` is derived from `effectiveItems` (which already incorporates `optimisticReadIds`), but `setOptimisticReadIds` is then set to `new Set(snapshot.map(i => i.id))` which over-counts because already-read items in `effectiveItems` get their ids added to `optimisticReadIds` unnecessarily. This means after a successful `handleMarkAll`, rolling back from a subsequent error elsewhere still has an inflated `optimisticReadIds` set. More concretely: items that were already read (non-null `readAt`) should not be added to `optimisticReadIds`, but line 215 adds all snapshot IDs unconditionally.

**Fix:**
```js
// Line 215: only add IDs of items that were unread before the mark-all
setOptimisticReadIds(new Set(allItems.filter(i => i.readAt === null).map(i => i.id)))
```

---

### CR-02: `/api/v1/client/push-tokens` endpoint absent from `schema.d.ts`

**File:** `packages/api-client/src/schema.d.ts` (entire file; verified by grep)

**Issue:** The `POST /api/v1/client/push-tokens` endpoint (`client_register_push_token`, operation ID defined in `router.py:128`) is not present in `schema.d.ts`. The three notification endpoints (`client_list_notifications`, `client_mark_notification_read`, `client_mark_all_notifications_read`) are present (lines 892–944, 10131–10219), but `client_register_push_token` is missing entirely.

The TypeScript API client is hand-maintained (not generated) and this omission means:
1. The push-token registration endpoint is not type-checked when used from TypeScript consumers.
2. The schema contract is inconsistent: three of four Phase 87 endpoints are described; one is silently absent.
3. Any future TypeScript consumer that navigates the schema types for completeness will miss this endpoint.

**Fix:** Add the following entry to `schema.d.ts` in the `paths` section and corresponding operation in the `operations` section:

```typescript
// paths block
"/api/v1/client/push-tokens": {
  post: operations["client_register_push_token"];
};

// operations block
client_register_push_token: {
  parameters: {
    query?: never;
    header?: never;
    path?: never;
    cookie?: never;
  };
  requestBody: {
    content: {
      "application/json": {
        token: string;
        platform: "web" | "android" | "ios";
      };
    };
  };
  responses: {
    /** @description Successful Response — 204 No Content */
    204: {
      headers: { [name: string]: unknown };
      content?: never;
    };
    /** @description Validation Error */
    422: {
      headers: { [name: string]: unknown };
      content: {
        "application/json": components["schemas"]["HTTPValidationError"];
      };
    };
  };
};
```

---

### CR-03: Push-token upsert UPDATE-first strategy has a TOCTOU window that breaks the partial-unique guarantee for cross-client token reuse

**File:** `apps/backend/app/modules/notifications/repository.py:228-245`

**Issue:** The `upsert_push_token` function uses an UPDATE-first strategy: it issues an `UPDATE … WHERE client_id = :cid AND token = :tok` and, if no row was updated, falls through to an ORM INSERT. The partial unique index `uq_client_push_tokens_client_token_alive` only covers `(client_id, token) WHERE unregistered_at IS NULL`.

The problem: if Client A previously registered token T (now alive), and Client B registers the same token T, the UPDATE step runs `WHERE client_id = B.id AND token = T` — no row matches, so it proceeds to INSERT. The INSERT then violates no unique constraint because the partial index is scoped to `client_id` (A's row does not block B's row since they have different `client_id`). The result is **two alive rows for the same physical device token** owned by different clients. When a notification dispatch worker later sends to token T, it would fan out to both clients — a privacy leak where Client A (who no longer owns the device) receives Client B's notifications or vice-versa.

The issue is in the schema design: the partial unique index on `(client_id, token)` only prevents one client from registering the same token twice, but does not prevent two clients from owning the same token simultaneously.

**Fix (two options):**

Option A (preferred, schema-level): Change the partial unique index to cover `(token)` alone `WHERE unregistered_at IS NULL`, not `(client_id, token)`. This prevents any two alive rows from sharing the same token regardless of client. When Client B registers token T, the upsert must first soft-delete any existing alive row for T (owned by A), then INSERT for B.

Option B (service-level, no schema change): Before the INSERT in `upsert_push_token`, add a step that `UPDATE … SET unregistered_at = now() WHERE token = :tok AND client_id != :cid AND unregistered_at IS NULL`, revoking any other client's ownership of the same token before inserting for the new owner.

Note: This is a design-level gap; the migration 0061 and model are consistent with each other (both define `(client_id, token)`) but the semantics are weaker than required for a push-notification system where device tokens are globally unique.

---

## Warnings

### WR-01: `cancel_booking` notification hook fires for OWNER only — no notification when actor role is neither OWNER nor RECEPTION

**File:** `apps/backend/app/modules/bookings/service.py:1567-1586`

**Issue:** The notification hook in `cancel_booking` (Step 8.5) uses an `if/elif` with no `else` branch:

```python
if actor.role is Role.OWNER:
    await create_notification(..., kind="booking_cancelled_by_owner", ...)
elif actor.role is Role.RECEPTION:
    await create_notification(..., kind="booking_cancelled_by_client", ...)
```

If a future caller passes a role that is neither `OWNER` nor `RECEPTION` (e.g. a new role or a system actor), no inbox notification is created and no log is emitted. This is inconsistent with the existing `else` branch at line 1627 for the DM dispatch path which at least logs `cancel_booking_dm_unexpected_role`. The affected client would never receive an inbox notification for their cancelled booking.

**Fix:** Add an else branch that either raises (loud failure during development) or logs a warning for an unexpected actor role:

```python
else:
    _log.warning(
        "cancel_booking_notification_unexpected_role",
        booking_id=str(booking.id),
        role=str(actor.role),
    )
```

---

### WR-02: `mark_notification_read` service returns 404 on already-read notifications — leaks read-state

**File:** `apps/backend/app/modules/notifications/service.py:133-134`

**Issue:** The UPDATE predicate is `WHERE id = :id AND client_id = :cid AND read_at IS NULL`. When a notification is already read, `mark_read` returns `False`, and the service raises `NotFoundError("notification_not_found")`. The router comment and docstring say "404-collapse on non-owned or already-read rows" and describes this as the intended IDOR-safe behavior.

However, this conflates two distinct cases: (1) the ID does not exist or belongs to another client (genuine 404), and (2) the notification exists and belongs to the caller but is already read (idempotent operation on own resource). A PWA client that fires an optimistic mark-read request and then retries on network error will receive a 404 on the retry, which the client must handle as an error rather than a success — breaking the idempotent-retry contract. The comment explicitly warns about this but frames it as intentional.

The correct behavior for a PATCH that is semantically idempotent (marking an already-read notification as read again is a no-op) is to return 200 with the existing read item, not 404. The IDOR collapse should only apply to the case where `client_id` does not match.

**Fix:** Split the two cases in `mark_notification_read`:
```python
# Try to update (only updates if unread)
updated = await repository.mark_read(session, client_id=client_id, notification_id=notification_id)
# Either way, fetch the row owned by this client
row = await repository.fetch_one_owned(session, client_id=client_id, notification_id=notification_id)
if row is None:
    raise NotFoundError("notification_not_found")  # genuinely not found or not owned
return ClientNotificationItem(...)  # return current state whether read or not
```

---

### WR-03: `create_booking_via_bot` does not insert a `booking_confirmed` inbox notification

**File:** `apps/backend/app/modules/bookings/service.py:1194-1319`

**Issue:** The `create_booking_via_bot` function mirrors `create_booking` but the Phase 87 INBOX-03 hook (Step 8.5) added to `create_booking` at line 1139 is missing from `create_booking_via_bot`. The bot booking path correctly emits the `booking_created` audit, commits, and dispatches the Telegram DM — but no `booking_confirmed` inbox row is created for the client. A client who books via the Telegram bot will not see the confirmation in their notification inbox, while a client who books via the staff portal or via the PWA (`create_booking_for_client`) does receive one.

**Fix:** Insert the notification hook between Step 8 (audit emit) and Step 9 (commit) in `create_booking_via_bot`, mirroring `create_booking` lines 1139-1153:

```python
# Step 8.5 — Phase 87 INBOX-03 — in-app inbox row
_trainer_name = await _fetch_trainer_full_name(session, slot.trainer_id)
_slot_start_msk = slot.start_time.astimezone(MOSCOW_TZ).strftime("%d.%m.%Y %H:%M")
await create_notification(
    session,
    client_id=client_id,
    source_type="booking",
    source_id=booking.id,
    kind="booking_confirmed",
    title="Бронь подтверждена",
    body=f"{_slot_start_msk} — {_trainer_name}",
)
```

---

### WR-04: `create_booking_for_client` does not insert a `booking_confirmed` inbox notification

**File:** `apps/backend/app/modules/bookings/service.py:1327-1456`

**Issue:** Same gap as WR-03 but for the client self-service booking path `create_booking_for_client`. The Phase 87 INBOX-03 hook is present in `create_booking` (Step 8.5, line 1139) and in `cancel_booking_for_client` (Step 8.5, line 1734), but `create_booking_for_client` has no INBOX-03 hook. A client booking via the PWA's `/api/v1/client/booking` endpoint (`create_booking_for_client`) will not receive a `booking_confirmed` inbox notification.

The test file `test_notifications_event_hooks.py` tests `bookings_service.create_booking` (the staff-facing orchestrator, Hook 1), not `create_booking_for_client`. This gap means both the implementation and the test coverage are missing for the client self-service booking confirmation inbox row.

**Fix:** Same as WR-03 — add the notification hook between Step 8 (audit emit) and Step 9 (commit) in `create_booking_for_client`.

---

### WR-05: Token value not validated for minimum/maximum length in `ClientPushTokenRegisterRequest`

**File:** `apps/backend/app/modules/notifications/schemas.py:59`

**Issue:** The `token: str` field in `ClientPushTokenRegisterRequest` has no length constraints. A client can submit an arbitrarily long string (megabytes) as a push token, which will be stored in the `client_push_tokens.token` column (unbounded `Text` type) and echoed back through the UPDATE-first upsert without any server-side length gate. This is a mild denial-of-storage vector and also means invalid/garbage tokens (empty string, whitespace-only) are accepted without error.

`BackendSchemaBase` provides `extra='forbid'` but no implicit length validation. Pydantic v2 requires explicit `Annotated[str, Field(min_length=1, max_length=4096)]` for string field constraints.

**Fix:**
```python
from pydantic import Field
from typing import Annotated

token: Annotated[str, Field(min_length=1, max_length=4096)]
```

---

## Info

### IN-01: `NotificationsSheet` auto-mark-on-open fires for page 1 items only, no rollback on individual `markRead` errors

**File:** `apps/client-pwa/src/screens/sheets/NotificationsSheet.jsx:171-191`

**Issue:** The auto-mark effect fires `markRead.mutate(item.id)` for each unread item on page 1 without registering an `onError` callback. Individual mark-read failures are silently ignored — the optimistic `setOptimisticReadIds` has already been applied, so the item appears as read locally even if the server call failed. If load-more is subsequently called, page 2+ items never receive the auto-mark treatment (the `markedOnOpenRef.current = true` guard fires on page 1 data only). This asymmetry is intentional per the comment `// eslint-disable-next-line react-hooks/exhaustive-deps` but should be documented. The lack of rollback on individual `markRead` errors means the local read-count badge may show 0 while the server still has unread rows.

**Fix (suggestion):** Either accept this as a fire-and-forget UX policy (document it explicitly), or use `useMarkAllNotificationsRead` in the auto-open path instead of firing N individual mutations.

---

### IN-02: `test_post_push_token_invalid_platform_returns_error` asserts `!= 204` instead of a specific status code

**File:** `apps/backend/tests/notifications/test_notifications_endpoints.py:645-648`

**Issue:** The test for invalid platform asserts `resp.status_code != 204` and notes in the comment that "FastAPI turns the DB error into 500 unless the service validates." This assertion is too weak: a 500 satisfies `!= 204` and would pass the test, but a 500 is a defect — the Pydantic `Literal["web", "android", "ios"]` validation in `ClientPushTokenRegisterRequest` should reject `"windows-phone"` with 422 **before** it reaches the DB. The test should assert `resp.status_code == 422` to prove that Pydantic layer validation fires (not the DB constraint).

**Fix:**
```python
assert resp.status_code == 422, (
    f"Expected 422 from Pydantic Literal validation for invalid platform, got {resp.status_code}"
)
```

---

### IN-03: `formatRelativeTime` in `NotificationsSheet` has a dead path for `diffD === 1` returning `'вчера'` but uses `new Date(isoString).getTime()` which is DST-unsafe for date-only strings

**File:** `apps/client-pwa/src/screens/sheets/NotificationsSheet.jsx:31-45`

**Issue:** The function `formatRelativeTime` receives `isoString` which is always a full ISO-8601 datetime (with time and timezone, from `createdAt` on the backend's `InAppNotification.created_at` column with `timezone=True`). The `new Date(isoString).getTime()` call is safe for full ISO timestamps. However, the function returns `'вчера'` when `diffD === 1`, which is based on elapsed milliseconds, not calendar day. A notification created at 23:58 yesterday would have `diffH < 24` and return the `diffH` branch, while a notification created at 00:01 yesterday (over 24h ago but still "yesterday") returns the `diffD === 1` path. This is a known UX quirk with elapsed-time-based "yesterday" labels but is not a security or data-correctness issue.

**Fix (suggestion):** Accept the approximation or switch to calendar-day comparison using Moscow TZ, consistent with CLAUDE.md's `Europe/Moscow` TZ convention. Low priority.

---

_Reviewed: 2026-06-06T12:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
