---
phase: "52"
plan: "52-06"
subsystem: online_payments / notifications
tags: [tests, integration, arq, dispatch_payment_notification, notify05, regression]
dependency_graph:
  requires: [52-05, 50-07, 50-08]
  provides: [52-06-coverage]
  affects: [online_payments/tasks.py, online_payments/repository.py]
tech_stack:
  added: []
  patterns:
    - real-commit engine fixture for ARQ task tests (D-13)
    - _SettingsStub to bypass @lru_cache on get_settings()
    - monkeypatch.setattr on module reference for cached singletons
    - arq_pool stub injected via app.state on ASGITransport.app
key_files:
  created:
    - apps/backend/tests/integration/online_payments/test_payment_notifications_e2e.py
    - apps/backend/tests/integration/online_payments/test_notify05_cancellation_regression.py
  modified:
    - apps/backend/tests/integration/online_payments/conftest.py
decisions:
  - _SettingsStub inherits telegram_bot_token from real settings to avoid empty-token errors while overriding owner_alert fields
  - Webhook fixture re-exports moved to conftest.py (not test file) to avoid ruff F811 redefinition errors
  - payment_canceled task test seeds real Membership row (not MembershipPlan) so _resolve_client_row query succeeds
metrics:
  duration: "~45 minutes (continuation session)"
  completed: "2026-05-23T17:34:25Z"
  tasks_completed: 2
  files_changed: 3
---

# Phase 52 Plan 52-06: dispatch_payment_notification E2E + NOTIFY-05 Regression Tests Summary

**One-liner:** E2E behavioral tests for `dispatch_payment_notification` ARQ task (6 coverage areas) plus NOTIFY-05 regression lock (no client DM on cancel, audit field carry-through).

## Tasks Completed

| Task | Description | Commit | Files |
|------|-------------|--------|-------|
| 1 | E2E tests for dispatch_payment_notification (6 tests) + conftest fixture re-exports | 614acd3 | test_payment_notifications_e2e.py, conftest.py |
| 2 | NOTIFY-05 cancellation regression tests (2 tests) | 6ca1939 | test_notify05_cancellation_regression.py |

## What Was Built

### Task 1: `test_payment_notifications_e2e.py` (6 tests)

Six behavioral integration tests directly invoke `dispatch_payment_notification(ctx, payment_id=..., kind=...)` with a real-commit engine. Coverage areas:

1. **`test_payment_succeeded_dual_channel_then_restart_no_duplicate`** — Verifies both Telegram DM and email send on `payment_succeeded`; second call (simulating ARQ restart) produces no duplicate `payment_notifications` rows and no additional sends.

2. **`test_refund_succeeded_dual_channel`** — Verifies both channels fire on `refund_succeeded`.

3. **`test_channel_skipped_when_recipient_null`** — When owner has `telegram_chat_id=None` and `email=None`, the task claims the notification rows but sends nothing.

4. **`test_fiscal_failed_routes_owner_alert_and_is_idempotent_across_restart`** — `fiscal_failed` (owner-alert kind) sends to `owner_alert_telegram_chat_id`; restart produces no duplicate (WARNING-fix: idempotency confirmed).

5. **`test_owner_alert_unset_logs_only`** — When `owner_alert_telegram_chat_id=None` and `owner_alert_email=None`, the task completes without error and sends nothing.

6. **`test_payment_canceled_owner_alert_db_claim_no_fk_violation_idempotent`** — BLOCKER-fix: `payment_canceled` uses `online_payment_id` (not ledger `payment_id`). Test seeds a real `OnlinePayment` row, calls task, verifies the claim row exists, verifies no FK violation, and confirms restart is idempotent.

### Task 2: `test_notify05_cancellation_regression.py` (2 tests)

1. **`test_cancellation_audit_carries_party_and_reason`** — Drives real webhook endpoint; asserts `online_payment_canceled` audit row JSONB payload contains `cancellation_party` and `cancellation_reason` (D-52-12 regression lock).

2. **`test_cancellation_enqueues_owner_alert_only_no_client_dm`** — Stubs `app.state.arq_pool`; asserts exactly one `dispatch_payment_notification` enqueue with `kind=payment_canceled`; asserts NEVER `payment_succeeded` or `refund_succeeded` (NOT-05 hard contract).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Seed used MembershipPlan.id as payment.subject_id**
- **Found during:** Task 1 implementation
- **Issue:** `_resolve_client_row` in `tasks.py` queries `memberships.client_id WHERE memberships.id = payment.subject_id`. Tests initially seeded `subject_id = plan.id` (a `MembershipPlan` row), causing `payment_notification_subject_not_found` error.
- **Fix:** Added `_seed_membership()` helper that inserts a real `Membership` row; payment seeded with `subject_id = membership.id`.
- **Files modified:** `test_payment_notifications_e2e.py`

**2. [Rule 1 - Bug] `monkeypatch.setenv` ineffective for @lru_cache settings**
- **Found during:** Task 1 implementation
- **Issue:** `get_settings()` is decorated `@lru_cache` and returns the same cached `Settings` object. Patching `os.environ` after the first call has no effect.
- **Fix:** Created `_SettingsStub` class that inherits `telegram_bot_token` from real settings but overrides `owner_alert_telegram_chat_id` and `owner_alert_email`. Injected via `monkeypatch.setattr(tasks_mod, "get_settings", lambda: stub)`.
- **Files modified:** `test_payment_notifications_e2e.py`

**3. [Rule 1 - Bug] Wrong stub parameter name for send_text_dm**
- **Found during:** Task 1 test execution
- **Issue:** Stub used `text_` as positional parameter but the task calls `send_text_dm(bot, chat_id=chat_id, text=text)` — `text` is a keyword arg by name.
- **Fix:** Renamed `text_` to `text` in stub signature.
- **Files modified:** `test_payment_notifications_e2e.py`

**4. [Rule 1 - Bug] F811 ruff errors from fixture re-exports in test file**
- **Found during:** Task 2 linting
- **Issue:** Re-exporting webhook fixtures at module level in the test file AND using them as function parameters causes ruff F811 (redefinition of unused name).
- **Fix:** Moved all webhook fixture re-exports from the test file into `conftest.py`; test file has no module-level imports of those names.
- **Files modified:** `conftest.py`, `test_notify05_cancellation_regression.py`

**5. [Rule 1 - Bug] mypy strict: unused `type: ignore[attr-defined]` comments**
- **Found during:** mypy --strict run on Task 2
- **Issue:** After typing `raw_transport: Any`, the `# type: ignore[attr-defined]` became unused (Any already suppresses attribute errors).
- **Fix:** Removed the now-unused `type: ignore` comment.
- **Files modified:** `test_notify05_cancellation_regression.py`

## Known Stubs

None — all tests wire real data paths. The `_fake_send_text_dm` and `_fake_send_email` are intentional test stubs for external I/O (Telegram bot, email), not production stubs.

## Threat Flags

None — test-only files; no new production endpoints, auth paths, or schema changes.

## Self-Check: PASSED

Files exist:
- FOUND: apps/backend/tests/integration/online_payments/test_payment_notifications_e2e.py
- FOUND: apps/backend/tests/integration/online_payments/test_notify05_cancellation_regression.py
- FOUND: apps/backend/tests/integration/online_payments/conftest.py (modified)

Commits exist:
- 614acd3: test(52-06): add E2E behavioral tests for dispatch_payment_notification
- 6ca1939: test(52-06): add NOTIFY-05 cancellation regression tests

Test results: 29 passed in tests/integration/online_payments/ (0 failures)
mypy --strict: Success: no issues found in 2 source files
ruff check (new/modified files): All checks passed!
