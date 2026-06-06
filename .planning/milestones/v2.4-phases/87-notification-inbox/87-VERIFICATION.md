---
phase: 87-notification-inbox
verified: 2026-06-06T09:00:00Z
status: human_needed
score: 4/4
overrides_applied: 0
human_verification:
  - test: "Open NotificationsSheet in a live browser against a running docker stack"
    expected: "GET /client/notifications is called; the sheet renders inbox rows (or empty state on first use); no console errors; skeleton shows during loading"
    why_human: "Client-PWA SPA + backend both required; cannot verify HTTP round-trip with grep"
  - test: "Create a booking as a client, then open the sheet"
    expected: "A 'Бронь подтверждена' row appears in the inbox with the correct date/time and trainer name"
    why_human: "End-to-end event→inbox round-trip; requires a live stack and seeded data (FIT15 subscription)"
  - test: "Tap 'Всё прочитано' when unread notifications exist"
    expected: "Unread dots disappear optimistically; PATCH /client/notifications/read-all is called; the bell badge on Home drops to zero on next GET"
    why_human: "Optimistic UI + mutation chain requires live browser interaction to verify"
  - test: "Trigger an autopay permanent-failure event (or seed a failed row manually)"
    expected: "An 'Автоплатёж не прошёл' row appears in the client's inbox; the bell badge reflects the unread count"
    why_human: "Requires live YooKassa test creds or manual DB seed; cannot verify event flow with grep"
---

# Phase 87: Notification Inbox — Verification Report

**Phase Goal:** Клиент видит in-app ленту уведомлений, генерируемых системными событиями, и управляет статусом прочтения
**Verified:** 2026-06-06T09:00:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (Roadmap Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| SC-1 | After booking/payment/autopay events, a record appears in `GET /client/notifications` for the affected client | VERIFIED | 7 co-transactional `create_notification` call sites in `bookings/service.py` (lines 1145, 1315, 1470, 1600, 1610, 1783, 2018); 2 in `yookassa/handlers.py` (lines 651, 661); 1 in `autopay_charges/service.py` (line 441); all placed before `await session.commit()` in their enclosing functions; 39 backend tests (service + endpoints + event-hooks) |
| SC-2 | Client marks notifications read (single + all) and unread badge decreases | VERIFIED | PATCH `/notifications/read-all` (204) and PATCH `/notifications/{id}/read` (200) endpoints in `router.py`; `HomeScreen.jsx:268-269` replaces hardcoded `unread = 0` with `useClientNotifications(1).unreadCount ?? 0`; both HomeHeroCard and HomeNewbie render unread dot conditionally |
| SC-3 | Client registers push token via API; 204, stored; no real delivery required | VERIFIED | POST `/push-tokens` endpoint returns 204, no token in response body; `repository.upsert_push_token` is idempotent (UPDATE-first + INSERT-fallback); `ClientPushTokenRegisterRequest` uses Literal platform type + max_length=512 validation |
| SC-4 | Notifications screen in PWA loads real data behind feature flag | VERIFIED | `NotificationsSheet.jsx` is a full paginated implementation (not a ComingSoon stub); `NOTIFICATIONS_FEATURE_FLAGS.notificationsInbox = true`; all hooks imported via `@/data` (swap seam enforced, D-71-09 de-list confirmed by 0 grep count) |

**Score:** 4/4 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `apps/backend/app/modules/notifications/models.py` | InAppNotification + ClientPushToken ORM models | VERIFIED | Both models present with correct constraints; `InAppNotification.__tablename__ = "in_app_notifications"`, `ClientPushToken.__tablename__ = "client_push_tokens"` |
| `apps/backend/alembic/versions/0060_in_app_notifications.py` | in_app_notifications table DDL | VERIFIED | down_revision="0059_seed_gym_info", creates table with 7-kind CheckConstraint and UNIQUE dedup guard |
| `apps/backend/alembic/versions/0061_client_push_tokens.py` | client_push_tokens table DDL | VERIFIED | down_revision="0060_in_app_notifications"; partial UNIQUE index on (token) WHERE unregistered_at IS NULL |
| `apps/backend/app/modules/notifications/service.py` | 5-function service contract | VERIFIED | All 5 functions present: `create_notification`, `list_client_notifications`, `mark_notification_read`, `mark_all_notifications_read`, `register_push_token`; no `session.commit()` in service or repository |
| `apps/backend/app/modules/notifications/router.py` | 4 client endpoints | VERIFIED | GET /notifications, PATCH /notifications/read-all, PATCH /notifications/{id}/read, POST /push-tokens; route ordering correct (read-all before {id}); RBAC-04 dep ordering on all mutations |
| `apps/backend/app/api/v1/router.py` | notifications_router mounted at /client | VERIFIED | Line 129-131: deferred import + `v1.include_router(notifications_router, prefix="/client")` |
| `apps/backend/app/modules/bookings/service.py` | 5+ co-transactional booking hooks | VERIFIED | 7 call sites (WR-03/WR-04 extended to via_bot and for_client creation paths); all placed before `await session.commit()` in each enclosing function |
| `apps/backend/app/api/v1/_internal/yookassa/handlers.py` | payment-succeeded inbox hook | VERIFIED | Lines 651/661 inside `async with session.begin()` block; discriminates `is_autopay` for kind |
| `apps/backend/app/modules/autopay_charges/service.py` | autopay-failure inbox hook | VERIFIED | Line 441 in permanent-failure branch, before `declined_charge_ids.append(claim_id)` |
| `apps/backend/tests/notifications/test_notifications_service.py` | Service behavior tests | VERIFIED | 11 test functions; covers dedup (UNIQUE conflict single-row), IDOR 404-collapse, mark-all scope, push-token revival |
| `apps/backend/tests/notifications/test_notifications_endpoints.py` | Endpoint integration tests | VERIFIED | 17 test functions; covers IDOR cross-client 404, CSRF rejection, idempotent push-token, no-token-leakage |
| `apps/backend/tests/notifications/test_notifications_event_hooks.py` | Event hook tests | VERIFIED | 11 test functions; covers all 7 booking kinds including staff-cancels-client-booking, anti-oracle (payment_canceled → 0 rows), webhook-replay dedup |
| `apps/client-pwa/src/screens/sheets/NotificationsSheet.jsx` | Real data-backed notifications sheet | VERIFIED | Full implementation with pagination accumulation, pull-to-refresh, mark-all/mark-single optimistic updates, skeleton/empty/error states; imports hooks from `@/data` |
| `apps/client-pwa/src/lib/clientQueries.ts` | 3 notification hooks + clientPortalKeys.notifications | VERIFIED | `useClientNotifications`, `useMarkNotificationRead`, `useMarkAllNotificationsRead` exported; `clientPortalKeys.notifications(page)` key factory at line 44 |
| `apps/client-pwa/src/data/index.js` | swap-seam exports for 3 notification hooks | VERIFIED | Lines 61-63 export all 3 hooks with `// Phase-87 INBOX-05` comment |
| `apps/client-pwa/src/screens/sheets/NotificationsSheet.test.jsx` | Vitest suite (10 tests) | VERIFIED | 10 test cases: row render, unread dot conditional, empty state, mark-all visibility, mark-all optimistic+rollback (CR-01), mark-single debounce, no-mark-for-read, error state |
| `apps/client-pwa/src/screens/HomeScreen.jsx` | Bell badge reflects server unreadCount | VERIFIED | Line 268-269: `useClientNotifications(1)` replaces hardcoded `unread = 0`; both HomeHeroCard (line 147) and HomeNewbie (line 881) render conditional unread dot |
| `packages/api-client/src/schema.d.ts` | Notification paths in schema | VERIFIED | 4 paths present: `/api/v1/client/notifications`, `/{notification_id}/read`, `/read-all`, `/push-tokens`; all 3 operations typed |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `notifications/service.py` | `notifications/repository.py` | repository function calls | WIRED | `from app.modules.notifications import repository`; all 5 service functions delegate to repository |
| `alembic/env.py` | `app.modules.notifications.models` | model registration import | WIRED | Line 47: `import app.modules.notifications.models  # Phase 87 INBOX-01/INBOX-02 / 0060+0061` |
| `notifications/router.py` | `notifications/service.py` | service function calls | WIRED | `from app.modules.notifications import service`; all 4 handlers call service functions |
| `app/api/v1/router.py` | `notifications/router.py` | include_router prefix=/client | WIRED | Lines 129-131 in v1/router.py |
| `bookings/service.py` | `app.modules.notifications.service.create_notification` | cross-module import | WIRED | Line 92: `from app.modules.notifications.service import create_notification` |
| `yookassa/handlers.py` | `create_notification` | co-transactional call inside `async with session.begin()` | WIRED | Lines 651/661 inside the `session.begin()` context manager |
| `NotificationsSheet.jsx` | `@/data` | swap-seam hook import | WIRED | Lines 19-22: all 3 hooks imported from `@/data` (not `@/lib/clientQueries` directly) |
| `HomeScreen.jsx` | `useClientNotifications(1).unreadCount` | bell badge prop | WIRED | Line 268-269: `useClientNotifications(1)` at component level; `unread` threaded through all 3 Home variants |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `NotificationsSheet.jsx` | `data` (from `useClientNotifications`) | `clientRequest('get', '/api/v1/client/notifications', ...)` → backend `GET /client/notifications` → `service.list_client_notifications` → raw SQL `SELECT ... ORDER BY created_at DESC` | Yes — DB query with LIMIT/OFFSET, unread COUNT | FLOWING |
| `HomeScreen.jsx` unread badge | `notificationsData?.unreadCount ?? 0` | same `useClientNotifications(1)` query | Yes — unread_count computed in `count_notifications` via `COUNT(*) FILTER (WHERE read_at IS NULL)` | FLOWING |

### Behavioral Spot-Checks

Step 7b: SKIPPED — requires live docker stack + running backend (ASGITransport tests need DB). CLI/file checks used instead.

### Probe Execution

Step 7c: No probe-*.sh files exist for this phase. Conventional probe directory not present.

### Requirements Coverage

| Requirement | Source Plans | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| INBOX-01 | 87-01, 87-02 | Client sees own feed newest-first paginated GET /client/notifications | SATISFIED | `list_notifications` ORDER BY created_at DESC; `list_client_notifications` returns `ClientNotificationsListResponse` with items/total/page/pageSize/unreadCount |
| INBOX-02 | 87-01, 87-02 | Mark read single+all via PATCH + unread count for badge | SATISFIED | PATCH endpoints implemented and tested; `unread_count` field in list response |
| INBOX-03 | 87-01, 87-03 | 6 system events auto-create feed rows for affected client | SATISFIED | 7 booking hooks (WR-03/WR-04 extended plan's 5 to cover all booking creation paths) + payment-succeeded + autopay-failure; all co-transactional; 11 event-hook tests |
| INBOX-04 | 87-01, 87-02 | Client registers push-token via API (storage only, delivery deferred) | SATISFIED | POST /client/push-tokens → 204; `ClientPushToken` table; idempotent upsert; no token in response |
| INBOX-05 | 87-04 | PWA feed wired to real endpoints behind feature flag | SATISFIED | `NotificationsSheet.jsx` fully implemented; `NOTIFICATIONS_FEATURE_FLAGS.notificationsInbox = true`; D-71-09 de-listed (grep count = 0) |

All 5 INBOX-* requirements satisfied. No orphaned requirements.

### Anti-Patterns Found

| File | Pattern | Severity | Impact |
|------|---------|----------|--------|
| `apps/backend/app/modules/notifications/__init__.py:9` | `TODO Phase B+: event-bus outbox pattern` | INFO | Intentional plan-documented deferral (Plan 01 action explicitly instructs keeping this TODO); scoped to a future milestone, not missing Phase 87 work |

No `TBD`, `FIXME`, or `XXX` markers found in any Phase 87 modified files. No stub return patterns. No hardcoded empty data in rendering paths.

### Human Verification Required

#### 1. Live Feed Rendering

**Test:** Open a running docker stack, log in as a test client, navigate to the Home screen, then open the notifications sheet.
**Expected:** The sheet renders correctly (either skeleton → data or empty state); GET /client/notifications is called; no JS console errors.
**Why human:** SPA + backend stack required; no runnable entry point to verify without docker.

#### 2. Booking Event → Inbox Round-Trip

**Test:** As an owner, confirm a booking for a test client (or have the client create one via `create_booking_for_client`). Then open the notifications sheet as the client.
**Expected:** A "Бронь подтверждена" row appears with the correct date/time and trainer name; unread dot is visible; opening the sheet triggers the 800ms mark-on-open debounce.
**Why human:** End-to-end event→inbox flow requires a live DB, seeded FIT15 subscription, and browser interaction.

#### 3. Mark-All → Bell Badge

**Test:** With at least one unread notification, tap "Всё прочитано" in the sheet. Return to Home.
**Expected:** Unread dots disappear immediately (optimistic); PATCH /notifications/read-all is called; the bell badge count on Home drops to zero after the next GET poll.
**Why human:** Optimistic mutation + server-invalidation cycle requires live browser interaction.

#### 4. Autopay Failure Notification

**Test:** Trigger an autopay permanent-failure event, or seed a row directly via `INSERT INTO in_app_notifications (client_id, source_type, source_id, kind, title, body) VALUES (...)` with `kind='autopay_charge_failed'`.
**Expected:** "Автоплатёж не прошёл" row appears in the inbox; the bell badge reflects the unread count.
**Why human:** Live YooKassa test creds required for the real event path; DB seed requires operator access to the running container.

### Gaps Summary

No gaps identified. All 4 roadmap success criteria verified against the codebase. All 5 INBOX-* requirements have implementation evidence. The phase is technically complete; the 4 human verification items above require a live running stack to confirm end-to-end behavior.

**Note on 7 booking hooks vs. plan's 5:** The plan specified 5 hooks for 5 booking functions. The codebase has 7 call sites because WR-03/WR-04 fix commits added `booking_confirmed` hooks to `create_booking_via_bot` and `create_booking_for_client` (two previously missed confirmation paths). This is a superset of the plan requirement and satisfies SC-1 more completely — not a gap.

---

_Verified: 2026-06-06T09:00:00Z_
_Verifier: Claude (gsd-verifier)_
