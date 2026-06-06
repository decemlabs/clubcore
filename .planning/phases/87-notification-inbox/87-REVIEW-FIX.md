---
phase: 87-notification-inbox
fixed_at: 2026-06-06T12:10:00Z
review_path: .planning/phases/87-notification-inbox/87-REVIEW.md
iteration: 1
findings_in_scope: 8
fixed: 8
skipped: 0
status: all_fixed
---

# Phase 87: Code Review Fix Report

**Fixed at:** 2026-06-06T12:10:00Z
**Source review:** .planning/phases/87-notification-inbox/87-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 8 (3 Critical + 5 Warning)
- Fixed: 8
- Skipped: 0

## Fixed Issues

### CR-01: PWA optimistic mark-all rollback inflated optimisticReadIds

**Files modified:** `apps/client-pwa/src/screens/sheets/NotificationsSheet.jsx`, `apps/client-pwa/src/screens/sheets/NotificationsSheet.test.jsx`
**Commit:** `046860c8`, `1485ea76`
**Applied fix:**
- Capture `prevItems`/`prevReadIds` before any `setState` calls so the `onError` closure closes over the correct pre-mutation state
- Build the new optimistic set from `allItems.filter(i => i.readAt === null)` instead of from `snapshot` derived from `effectiveItems` (which already had `optimisticReadIds` applied, causing already-read item IDs to be added to the set unconditionally)
- Use functional updater `setAllItems(prev => prev.map(...))` to avoid stale-closure issues
- Added vitest `CR-01: onError rollback restores only items that were unread before mark-all` covering the over-count regression

### CR-02: `/api/v1/client/push-tokens` absent from `schema.d.ts`

**Files modified:** `packages/api-client/src/schema.d.ts`
**Commit:** `d69070ba`
**Applied fix:** Added the `/api/v1/client/push-tokens` path entry (POST operation only) and the `client_register_push_token` operation definition to the hand-maintained TypeScript API schema, consistent with the three notification endpoints already present. Response is 204 No Content (matching the router), with a 422 Validation Error entry. Platform constrained to `"web" | "android" | "ios"`.

### CR-03: Push-token uniqueness — global-per-token, not per-client

**Files modified:** `apps/backend/alembic/versions/0061_client_push_tokens.py`, `apps/backend/app/modules/notifications/models.py`, `apps/backend/app/modules/notifications/repository.py`, `apps/backend/app/modules/notifications/service.py`, `apps/backend/tests/notifications/test_notifications_endpoints.py`
**Commit:** `e92b4721`
**Applied fix:**
- Migration 0061 amended in-place (not yet deployed, single-dev project): replaced `uq_client_push_tokens_client_token_alive` on `(client_id, token)` with `uq_client_push_tokens_token_alive` on `(token)` alone WHERE unregistered_at IS NULL
- DB patched directly (drop old index, create new index) and `alembic upgrade head && alembic check` verified clean
- Model `ClientPushToken.__table_args__`: updated Index definition and docstring to reflect global uniqueness semantics
- Repository `upsert_push_token`: added Step 1 that soft-deletes any OTHER client's alive row for the same token (UPDATE SET unregistered_at=now() WHERE token=:tok AND client_id != :cid AND unregistered_at IS NULL) before the existing UPDATE-or-INSERT path
- Service `register_push_token`: updated docstring describing new semantics
- Test added: `test_post_push_token_cross_client_reuse_leaves_only_one_alive_row` asserting client B registering client A's still-alive token leaves exactly one alive row globally, owned by client B

### WR-02: `mark_notification_read` idempotency for own already-read notifications

**Files modified:** `apps/backend/app/modules/notifications/service.py`, `apps/backend/tests/notifications/test_notifications_endpoints.py`, `apps/backend/tests/notifications/test_notifications_service.py`
**Commit:** `d4686bc4`, `2dbfb608`
**Applied fix:**
- Changed `mark_notification_read` to always call `repository.mark_read` (no-op if already read), then unconditionally fetch the row via `repository.fetch_one_owned`. If fetch returns None → 404 (genuinely absent or cross-client). If found → 200 with current state. IDOR-collapse (T-87-01) is preserved because `fetch_one_owned` is scoped by `client_id`.
- Test added: `test_patch_mark_read_already_read_own_notification_returns_200` (endpoint test)
- Updated `test_mark_notification_read_idempotent` (service unit test) to assert the new idempotent contract instead of the old broken `NotFoundError` behavior

### WR-03: `create_booking_via_bot` missing `booking_confirmed` inbox hook

**Files modified:** `apps/backend/app/modules/bookings/service.py`, `apps/backend/tests/notifications/test_notifications_event_hooks.py`
**Commit:** `25a43408`
**Applied fix:** Added Step 8.5 to `create_booking_via_bot` between audit.emit (Step 8) and session.commit (Step 9), co-transactionally inserting a `booking_confirmed` inbox row using `create_notification`. Mirrors the existing Step 8.5 in `create_booking` (lines 1139-1153). Test added: `test_create_booking_via_bot_creates_booking_confirmed_row`.

### WR-04: `create_booking_for_client` missing `booking_confirmed` inbox hook

**Files modified:** `apps/backend/app/modules/bookings/service.py`, `apps/backend/tests/notifications/test_notifications_event_hooks.py`
**Commit:** `25a43408` (same commit as WR-03)
**Applied fix:** Added Step 8.5 to `create_booking_for_client` with identical placement and template. Test added: `test_create_booking_for_client_creates_booking_confirmed_row`.

### WR-01: `cancel_booking` notification hook missing else branch for unexpected actor role

**Files modified:** `apps/backend/app/modules/bookings/service.py`
**Commit:** `d3610d5f`
**Applied fix:** Added an `else` branch after the `elif actor.role is Role.RECEPTION` block at Step 8.5 that calls `_log.warning("cancel_booking_notification_unexpected_role", booking_id=..., role=...)`. Mirrors the existing `else` at Step 9.5 DM dispatch path (`cancel_booking_dm_unexpected_role`). Kept minimal per the finding.

### WR-05: Token length not validated in `ClientPushTokenRegisterRequest`

**Files modified:** `apps/backend/app/modules/notifications/schemas.py`
**Commit:** `42140c64`
**Applied fix:** Changed `token: str` to `token: Annotated[str, Field(min_length=1, max_length=512)]`. Added `from typing import Annotated` and `from pydantic import Field` imports. Empty strings and tokens >512 chars are now rejected with 422 at the Pydantic layer before reaching the service or DB.

---

_Fixed: 2026-06-06T12:10:00Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
