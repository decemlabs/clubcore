---
phase: 116-chat-inbox-exports
reviewed: 2026-06-15T00:00:00Z
depth: standard
files_reviewed: 27
files_reviewed_list:
  - apps/admin-app/src/features/messages/api.ts
  - apps/admin-app/src/features/messages/types.ts
  - apps/admin-app/src/pages/attendance/AttendancePage.tsx
  - apps/admin-app/src/pages/attendance/components/AttendancePageHead.tsx
  - apps/admin-app/src/pages/cashbox/CashboxPage.tsx
  - apps/admin-app/src/pages/cashbox/components/CashboxPageHead.tsx
  - apps/admin-app/src/pages/finance/FinancePage.tsx
  - apps/admin-app/src/pages/messages/MessagesPage.tsx
  - apps/admin-app/src/pages/messages/components/ThreadPane.tsx
  - apps/admin-app/src/shared/session/can.test.ts
  - apps/admin-app/src/shared/session/can.ts
  - apps/admin-app/src/shared/session/registry.ts
  - apps/backend/alembic/versions/0073_message_thread_staff_last_read_at.py
  - apps/backend/app/api/v1/router.py
  - apps/backend/app/core/permissions.py
  - apps/backend/app/modules/messaging/models.py
  - apps/backend/app/modules/messaging/repository.py
  - apps/backend/app/modules/messaging/schemas.py
  - apps/backend/app/modules/messaging/service.py
  - apps/backend/app/modules/messaging/staff_router.py
  - apps/backend/app/modules/reports/constants.py
  - apps/backend/app/modules/reports/repository.py
  - apps/backend/app/modules/reports/router.py
  - apps/backend/app/modules/reports/service.py
  - apps/backend/tests/integration/messaging/test_staff_messaging.py
  - apps/backend/tests/integration/reports/test_csv_export.py
  - apps/backend/tests/integration/test_rbac_parity.py
  - apps/backend/tests/unit/test_permissions.py
findings:
  critical: 1
  warning: 6
  info: 4
  total: 11
status: issues_found
---

# Phase 116: Code Review Report

**Reviewed:** 2026-06-15
**Depth:** standard
**Files Reviewed:** 27
**Status:** issues_found

## Summary

Phase 116 adds staff messaging REST endpoints (inbox, thread history, owner-only reply, mark-read), an owner-only payments CSV export, and the FE wiring for both. The backend RBAC, thread isolation, SQL parameter binding, CSV BOM/RFC-4180/formula-guard, date-range validation, and the migration are all implemented correctly and have solid test coverage. RBAC parity at 46 is consistent across all six sources (permissions.py, can.ts, registry.ts, test_rbac_parity.py, test_permissions.py, can.test.ts).

The one BLOCKER is a thread-isolation / data-loss defect in the staff reply path: `send_staff_reply` resolves the client by thread but then routes the write through `record_staff_message(client_id=...)`, whose `mark_client_messages_read` and `get_or_create_thread` operate **per-client**, not per the requested `thread_id`. This is currently safe only because of the 1:1 client↔thread invariant, but the reply path also marks the *client's* prior messages read and emits a read-receipt that the requested-thread contract never asked for — and the reply's durable thread is resolved a **second time** independently of the `thread_id` the caller validated and later uses for `publish_new_message`. Combined with several correctness/UX warnings (FE mark-read does not invalidate the inbox, inbox-side unread can transiently mis-derive, composer "note"/"resolve" modes silently send a plain reply), these should be addressed before ship.

## Critical Issues

### CR-01: Staff reply re-resolves the thread independently of the validated `thread_id` and triggers client-side read-receipt side effects

**File:** `apps/backend/app/modules/messaging/service.py:635-677` (`send_staff_reply`) → `apps/backend/app/modules/messaging/service.py:227-328` (`record_staff_message`); router at `apps/backend/app/modules/messaging/staff_router.py:104-144`

**Issue:**
`send_staff_reply` resolves `client_id` from the requested `thread_id` (`get_thread_client_id`), then delegates the write to `record_staff_message(client_id=...)`. That function calls `get_or_create_thread(client_id)` **again** to obtain the thread it actually writes into, and `mark_client_messages_read(client_id, thread_id=<re-resolved>)`. So the thread the reply lands in is derived from `client_id`, **not** from the `thread_id` the endpoint validated and which the router subsequently re-resolves a third time for `publish_new_message`:

- The endpoint validates `thread_id` exists (`get_thread_client_id` → 404 if missing).
- `record_staff_message` independently does `get_or_create_thread(client_id)` — a write that can *create* a thread if one does not exist for that client.
- The router (`staff_router.py:132`) calls `get_thread_client_id(session, thread_id)` a third time for the publish channel.

Today this is masked by the `UNIQUE(client_id)` 1:1 invariant, so all three resolutions coincide. But the contract under review is "scope strictly to the requested thread." Routing the write through the per-client path means:
1. The reply path additionally executes reply-as-read (`mark_client_messages_read`) and *would* require a `publish_read_receipt` after commit per the documented CR-02 contract (`service.py:259-261`, `record_staff_message` docstring). The staff reply router **never publishes the read receipt** even though `record_staff_message` produces `reply_read_at` — the client's ✓✓ display will silently never update from a staff reply, contradicting the function's own invariant.
2. If the 1:1 invariant ever changes (soft-delete + recreate, multi-thread), the staff reply silently lands in a different thread than the one requested — a cross-thread write — with no test guarding it.

**Fix:**
Either (a) make the staff reply write strictly thread-scoped by passing the validated `thread_id` straight through to an insert that does not re-resolve via `client_id`, and resolve `client_id` once and reuse it for the publish channel; or (b) if reply-as-read is intended, wire the missing `publish_read_receipt` after commit so the documented CR-02 contract holds:

```python
result = await record_staff_message(session, client_id=client_id, body=payload.body)
client_id_for_publish = client_id  # already resolved — do not re-resolve in the router
await session.commit()
await service.publish_new_message(redis, client_id=client_id, message_id=result.id)
if result.reply_read_at is not None:
    await service.publish_read_receipt(redis, client_id=client_id, read_at=result.reply_read_at)
```

Minimum acceptable fix: resolve `client_id` exactly once in the router, drop the redundant `get_thread_client_id` re-resolve at `staff_router.py:132`, and either publish the read receipt or document explicitly (and add a test) that staff-reply reply-as-read is intentionally WS-silent.

## Warnings

### WR-01: FE mark-read does not invalidate the inbox query — unread badge persists until the 15 s poll

**File:** `apps/admin-app/src/features/messages/api.ts:142-151` (`useMarkThreadRead`)

**Issue:**
`useMarkThreadRead` has no `onSuccess`/`onSettled` invalidation. When a staff user opens a thread (`MessagesPage.onSelect` → `markRead.mutate(id)`, `MessagesPage.tsx:126-129`), the backend resets `staff_last_read_at`, but the cached `messages/threads` query is not invalidated. The unread count and bold/unread styling stay stale until the next 15 s `refetchInterval` fires. Worse, `staffThreadToConversation` derives `unread` directly from `t.staffUnreadCount` and `MessagesPage` passes `read={new Set<string>()}` (always empty, `MessagesPage.tsx:142`), so there is no client-side optimistic clear either.

**Fix:** Invalidate (or optimistically update) the threads query on mark-read success:

```ts
export function useMarkThreadRead() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (threadId: string) =>
      staffRequest('post', `/api/v1/messages/threads/${threadId}/read` as never, { body: {} }),
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: messagesKeys.threads() })
    },
  })
}
```

### WR-02: Composer "Заметка"/"Решить" modes silently send a plain staff reply

**File:** `apps/admin-app/src/pages/messages/components/ThreadPane.tsx:216,225-231,330-350`

**Issue:**
`LoadedThreadPane` tracks `mode: 'reply' | 'note' | 'resolve'` and renders three mode tabs, but `send()` always calls `sendReply.mutate(value)` regardless of `mode`. A staff user who selects "Заметка" (internal note) and types text will have that "internal note" delivered to the client as a normal chat message (`POST .../reply` → `role='staff'` → published to the client WS). Internal-note semantics are not implemented, so the mode toggle is actively misleading and can leak internal commentary to the client.

**Fix:** Either remove the `note`/`resolve` tabs until they are backed by real endpoints, or hard-block `send()` when `mode !== 'reply'` (e.g. toast "Внутренние заметки появятся позже") so nothing is sent to the client under a false label.

### WR-03: Inbox `staffUnreadCount` can transiently over/under-count under same-second sends (watermark granularity)

**File:** `apps/backend/app/modules/messaging/repository.py:442-482` (`list_all_threads_with_unread`) + `apps/backend/app/modules/messaging/repository.py:507-526` (`mark_staff_thread_read`)

**Issue:**
Staff-side unread is derived as `COUNT(*) WHERE role='client' AND sent_at > staff_last_read_at`, and mark-read sets `staff_last_read_at = now()`. Because this is a strict `>` on a timestamp watermark (not a per-message read flag), a client message whose `sent_at` equals the mark-read `now()` to the timestamp resolution — or one that commits with an earlier `sent_at` but after the mark-read snapshot — will be incorrectly counted as read (hidden) or unread. The client-direction code (`mark_client_messages_read`, `repository.py:356-365`) explicitly documents and accepts the analogous race; the staff-side watermark introduces the same tradeoff but it is **undocumented** here, and there is no test pinning the boundary behavior.

**Fix:** This is acceptable as a thread-level marker if intentional, but document the watermark tradeoff in `mark_staff_thread_read`/`list_all_threads_with_unread` (mirroring the WR-03 note at `repository.py:357-365`) and add a boundary test, so a future maintainer does not "tighten" it into a per-message guarantee or treat the count as exact.

### WR-04: `threadDay` collapses all older threads into "yesterday"

**File:** `apps/admin-app/src/pages/messages/MessagesPage.tsx:33-40`

**Issue:**
`threadDay` returns `'yesterday'` for any thread older than yesterday (`return 'yesterday' // older threads still shown in yesterday group`). A thread whose last message was weeks ago is grouped under the "Вчера" (Yesterday) header in `ConversationList`, which is factually wrong and will confuse staff triaging the inbox. The `Conversation.day` type only allows `'today' | 'yesterday'`, so the data model cannot express "older".

**Fix:** Either widen the grouping model to include an "earlier" bucket, or drop date-bucketing for the real inbox and group by nothing / by absolute date. At minimum the misleading hard-coded `'yesterday'` for ancient threads should not be presented under a "Вчера" label.

### WR-05: Reply request lacks the whitespace-only guard the client send path enforces

**File:** `apps/backend/app/modules/messaging/schemas.py:234-242` (`StaffReplyRequest`)

**Issue:**
`StaffReplyRequest.body` uses `Field(min_length=1, max_length=4000)` only. `min_length=1` does not reject whitespace-only input (`"   "` has length 3 and passes). The client-side `SendMessageRequest` explicitly added a whitespace-only guard (`schemas.py:114-127`, "preserves T-90-09"). The staff path can therefore persist and broadcast an all-whitespace message to the client. The FE `ThreadPane.send()` trims before sending (`ThreadPane.tsx:226`), but the backend is the trust boundary and an API caller can bypass the FE.

**Fix:** Add a `model_validator(mode="after")` (or `field_validator`) rejecting whitespace-only `body`, mirroring `SendMessageRequest.body_or_attachment_required`:

```python
@model_validator(mode="after")
def body_not_whitespace(self) -> Self:
    if not self.body.strip():
        raise ValueError("body must not be whitespace-only")
    return self
```

### WR-06: CSV export RBAC gate uses `(VIEW, FINANCE)`/`(VIEW, REPORTS)` while the endpoint enforces `(VIEW, REPORTS)` — gating coupled by coincidence, not contract

**File:** `apps/admin-app/src/pages/cashbox/CashboxPage.tsx:93` (`can(role,'view','finance')`); `apps/admin-app/src/pages/finance/FinancePage.tsx:129` (`can(role,'view','finance')`); backend `apps/backend/app/modules/reports/router.py:220-241` enforces `require_permission(Action.VIEW, Resource.REPORTS)`

**Issue:**
The payments.csv endpoint is gated server-side on `(VIEW, REPORTS)`. Two of the three FE export buttons gate on `(VIEW, FINANCE)` (Cashbox, Finance) and one on `(VIEW, REPORTS)` (Attendance, which actually hits visits.csv). All four pairs are owner-only today, so the behavior is currently correct (reception sees no button and would get 403 anyway). However, the FE button visibility for a payments.csv export keys on a *different* permission pair than the endpoint actually checks. If `(VIEW, FINANCE)` and `(VIEW, REPORTS)` ever diverge (e.g. a future "finance-viewer" sub-role), reception/limited users could see an export button that 403s, or be hidden from an export they are entitled to. The gate should reflect the resource the endpoint protects.

**Fix:** Gate the payments.csv export buttons on `can(role, 'view', 'reports')` (the resource the `payments.csv` route enforces) in both `CashboxPage.tsx:93` and `FinancePage.tsx:129`, so FE visibility and BE authorization key off the same pair.

## Info

### IN-01: `useThreads` polls every 15 s with `refetchOnWindowFocus: true` but `useThread` history is not refreshed by the same signal

**File:** `apps/admin-app/src/features/messages/api.ts:76-107`

**Issue:** The inbox polls every 15 s, but `useThread(id)` has `staleTime: 30_000` and no `refetchInterval`. An open thread will not show a newly-arrived client message for up to 30 s (or until a reply is sent, which invalidates it). For a "near-realtime inbox" this is a noticeable lag. Consider a short `refetchInterval` on the active thread or wiring the existing WS frame.

### IN-02: `clientName` built with naive `first_name + ' ' + last_name` ordering vs at-risk report uses `last_name + ' ' + first_name`

**File:** `apps/backend/app/modules/reports/repository.py:331-337` (payments CSV) vs `repository.py:665` (at-risk uses `last_name || ' ' || first_name`); also `service.py:590` inbox uses `first_name last_name`

**Issue:** Name-ordering is inconsistent across reports (some `first last`, some `last first`). Not a defect, but worth normalizing for export consistency, since payments.csv is an owner-facing financial artifact.

### IN-03: `_make_initials` returns literal `"?"` for clients with empty/whitespace names

**File:** `apps/backend/app/modules/messaging/service.py:568-572`

**Issue:** A client whose first and last names are both empty/whitespace yields initials `"?"`. Harmless but surfaces directly in the staff inbox avatar. Acceptable fallback; flagging for visibility.

### IN-04: Placeholder header actions in `ThreadPane` (reassign / snooze / archive / block) are toast-only stubs

**File:** `apps/admin-app/src/pages/messages/components/ThreadPane.tsx:249-296`

**Issue:** The thread header buttons ("Маша К." reassign, snooze, archive, mark-unread, block) only fire Sonner toasts (`toast.success('Диалог архивирован')` etc.) with no backend effect. They imply functionality that does not exist and could mislead staff into believing a dialog was archived/blocked. Consider hiding these until backed, or labeling them clearly as not-yet-available. (Carried over from the template; not introduced as new wiring this phase, but now sits on a live data screen.)

---

_Reviewed: 2026-06-15_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
