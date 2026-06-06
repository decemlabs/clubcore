---
status: partial
phase: 87-notification-inbox
source: [87-VERIFICATION.md]
started: 2026-06-06
updated: 2026-06-06
---

## Current Test

[awaiting human testing — deferred during autonomous run per operator-pending-verify-autodefer]

## Tests

### 1. Live feed rendering
steps: Open NotificationsSheet in client-pwa (feature flag on); observe GET /client/notifications
expected: Sheet renders paginated feed (or empty state "Нет уведомлений"); no console errors; unread dot logic correct
result: [pending]

### 2. Booking event → inbox round-trip
steps: Create/confirm a booking for a client (staff, client self-service, or bot path); open the client's inbox
expected: A booking_confirmed row appears with correct Russian copy and timestamp; cancel/reschedule produce matching rows
result: [pending]

### 3. Mark-all → bell badge
steps: With unread notifications, tap "mark all read"; re-fetch
expected: PATCH /client/notifications/read-all called; unread bell badge drops to 0; optimistic update + rollback on error
result: [pending]

### 4. Autopay failure notification
steps: Trigger autopay_charge_failed (real cron event or DB-seeded); open inbox
expected: An autopay_charge_failed row appears for the affected client; payment_canceled produces ZERO client rows (anti-oracle)
result: [pending]

## Summary

total: 4
passed: 0
issues: 0
pending: 4
skipped: 0
blocked: 0

## Gaps
