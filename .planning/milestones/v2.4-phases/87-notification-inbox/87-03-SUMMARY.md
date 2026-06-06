---
phase: 87-notification-inbox
plan: "03"
subsystem: backend/notifications/event-hooks
tags: [notifications, inbox, bookings, yookassa, autopay, event-hooks, inbox-03]
dependency_graph:
  requires:
    - app.modules.notifications.service.create_notification  # 87-01
    - app.modules.bookings.service  # existing
    - app.api.v1._internal.yookassa.handlers  # existing
    - app.modules.autopay_charges.service  # existing
  provides:
    - 5 booking inbox hooks (confirmed, cancelled_by_owner, cancelled_by_client×2, rescheduled)
    - 1 payment_succeeded / autopay_charge_succeeded hook in yookassa handler
    - 1 autopay_charge_failed hook in autopay_charges service
    - test_notifications_event_hooks.py (9 tests)
  affects:
    - apps/backend/app/modules/bookings/service.py
    - apps/backend/app/api/v1/_internal/yookassa/handlers.py
    - apps/backend/app/modules/autopay_charges/service.py
    - apps/backend/.importlinter (2 new ignore edges)
tech_stack:
  added: []
  patterns:
    - co-transactional inbox insert (caller-owns-txn, BEFORE session.commit)
    - raw SQL trainer name lookup (_fetch_trainer_full_name via sa.text SELECT trainers)
    - UNIQUE(client_id, source_type, source_id, kind) dedup covers replay/retry
    - importlinter narrowly scoped service→service ignore edges (D-87-03-IMPORTLINTER)
key_files:
  created:
    - apps/backend/tests/notifications/test_notifications_event_hooks.py
  modified:
    - apps/backend/app/modules/bookings/service.py
    - apps/backend/app/api/v1/_internal/yookassa/handlers.py
    - apps/backend/app/modules/autopay_charges/service.py
    - apps/backend/.importlinter
decisions:
  - "D-87-03-IMPORTLINTER: two narrow ignore_imports edges added — bookings.service -> notifications.service (5 booking hooks) + autopay_charges.service -> notifications.service (failure hook). Service-function import only (no ORM/repository cross-module access). Mirrors D-84-11 single-edge precedent."
  - "D-87-03-TRAINER-FETCH: _fetch_trainer_full_name helper uses raw sa.text() SELECT trainers WHERE id (D-54-08) to obtain trainer.full_name at hook site — ORM joinedload chain not available pre-commit in create_booking / cancel_booking (loaded slot has trainer_id but not trainer relationship at that point)."
  - "D-87-03-ANTI-ORACLE: payment_canceled handler (handle_payment_canceled) has NO create_notification call — only handle_payment_succeeded fires the hook. Anti-oracle test asserts 0 rows on cancellation path."
  - "D-87-03-PLAN-NAME-SQL: payment hook fetches plan name via raw SQL SELECT name FROM membership_plans/pt_package_plans for notification body; subject_kind already resolved at that scope."
metrics:
  duration: "~35 min"
  completed_date: "2026-06-06"
  tasks_completed: 2
  files_created: 1
  files_modified: 4
---

# Phase 87 Plan 03: Notification Inbox Event Hooks Summary

Seven system events wired to `create_notification()` co-transactionally: 5 booking lifecycle hooks in bookings/service.py, 1 payment-succeeded hook in yookassa handlers, 1 autopay permanent-failure hook in autopay_charges/service.py. All hooks placed PRE-COMMIT. Anti-oracle (D-52-08) and webhook replay dedup proven by tests.

## What Was Built

### Task 1: bookings/service.py — 5 Co-transactional Booking Hooks

Added `from app.modules.notifications.service import create_notification` import.

Added `_fetch_trainer_full_name(session, trainer_id) -> str` helper — raw SQL `SELECT full_name FROM trainers WHERE id = :trainer_id` (D-54-08 pattern). Used at each hook site where the ORM joinedload chain does not include the trainer relationship pre-commit.

**Five hooks, all PRE-COMMIT (Step 8.5 in the 10-step recipe):**

| Hook | Function | Kind | Placement | Source ID |
|------|----------|------|-----------|-----------|
| 1 | create_booking | booking_confirmed | after audit.emit, before session.commit (~line 1136) | booking.id |
| 2 | cancel_booking (owner) | booking_cancelled_by_owner | after audit.emit, before session.commit, if actor.role is OWNER | booking.id |
| 3 | cancel_booking (reception) | booking_cancelled_by_client | after audit.emit, before session.commit, elif actor.role is RECEPTION | booking.id |
| 4 | cancel_booking_for_client | booking_cancelled_by_client | after audit.emit, before session.commit | booking.id |
| 5 | reschedule_booking_for_client | booking_rescheduled | after audit.emit, before session.commit (Step 10.5) | new_booking.id |

**Copy templates rendered at event time (UI-SPEC Copywriting Contract):**
- booking_confirmed: title="Бронь подтверждена", body="{дд.мм.гггг чч:мм} — {trainer_name}"
- booking_cancelled_by_client: title="Бронь отменена", body="{дд.мм.гггг чч:мм} — {trainer_name}"
- booking_cancelled_by_owner: title="Бронь отменена залом", body="{дд.мм.гггг чч:мм} — {trainer_name}"
- booking_rescheduled: title="Бронь перенесена", body="{дд.мм.гггг чч:мм} — {trainer_name}"

None placed in the post-commit fire-and-forget DM try/except blocks (correct per plan).

importlinter: added `app.modules.bookings.service -> app.modules.notifications.service` edge (D-87-03-IMPORTLINTER).

**Verification:** `grep -c "create_notification(" bookings/service.py` = 5; mypy clean.

### Task 2: yookassa handlers.py + autopay_charges/service.py + importlinter + tests

**handlers.py** — inside `async with session.begin():` in `handle_payment_succeeded`, after `record_loyalty_redemption` call, before audit.emit:
- Fetches plan name via raw SQL `SELECT name FROM {membership_plans|pt_package_plans} WHERE id = :id`
- Formats amount: kopecks → "N ₽" (or "N,KK ₽" for non-zero remainder)
- if is_autopay: kind="autopay_charge_succeeded", title="Автоплатёж прошёл", body="{plan}, {amount} — автопродление активировано"
- else: kind="payment_succeeded", title="Оплата прошла", body="{plan}, {amount}"
- Anti-oracle: NO hook in `handle_payment_canceled` (D-52-08)

**autopay_charges/service.py** — in permanent-failure else-branch, BEFORE `declined_charge_ids.append(claim_id)`:
- kind="autopay_charge_failed", title="Автоплатёж не прошёл", body="Не удалось списать оплату. Проверьте привязанную карту."
- source_type="autopay_charge", source_id=claim_id

importlinter: added `app.modules.autopay_charges.service -> app.modules.notifications.service` edge.

**tests/notifications/test_notifications_event_hooks.py** — 9 tests:
1. `test_create_booking_creates_booking_confirmed_row` — booking_confirmed row created
2. `test_cancel_booking_owner_creates_cancelled_by_owner_row` — owner cancel creates cancelled_by_owner; no cancelled_by_client (anti-oracle)
3. `test_cancel_booking_reception_creates_cancelled_by_client_row` — STAFF-cancel-client test: reception cancel creates cancelled_by_client for AFFECTED CLIENT (INBOX-03); no cancelled_by_owner
4. `test_cancel_booking_for_client_creates_cancelled_by_client_row` — self-cancel creates cancelled_by_client
5. `test_reschedule_booking_for_client_creates_booking_rescheduled_row` — rescheduled with source_id=new_booking.id
6. `test_payment_succeeded_creates_payment_succeeded_row` — payment_succeeded via webhook
7. `test_payment_succeeded_webhook_replay_creates_exactly_one_row` — DEDUP: second webhook call creates 0 extra rows (total = 1)
8. `test_payment_canceled_creates_zero_inbox_rows` — ANTI-ORACLE: payment_canceled = 0 rows (D-52-08)
9. `test_autopay_charge_failed_creates_inbox_row` — autopay permanent failure creates autopay_charge_failed row

## Verification Results

- `grep -c "create_notification(" bookings/service.py` → 5
- `uv run mypy app/modules/bookings/service.py app/api/v1/_internal/yookassa/handlers.py app/modules/autopay_charges/service.py` → `Success: no issues found in 3 source files`
- `uv run lint-imports` → `Contracts: 3 kept, 0 broken`
- `uv run pytest tests/notifications/test_notifications_event_hooks.py -q` → 9 passed
- `uv run pytest tests/notifications/ tests/integration/bookings/ tests/integration/webhook_yookassa/ tests/integration/autopay_charges/ -q` → 215 passed

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing functionality] _fetch_trainer_full_name raw SQL helper added**
- **Found during:** Task 1 design
- **Issue:** Plan assumed `slot.trainer.full_name` and `booking.slot.trainer.full_name` would be available pre-commit at hook sites. However, `create_booking` receives `slot` as `SlotById` Protocol (no trainer relationship) and `cancel_booking` loads `booking.slot` without the trainer joinedload. ORM joinedload chain not available at these hook sites.
- **Fix:** Added `_fetch_trainer_full_name(session, trainer_id)` — raw `sa.text("SELECT full_name FROM trainers WHERE id = :trainer_id")` query, consistent with D-54-08 pattern. Minimal round-trip, returns empty string on missing row (defensive).
- **Files modified:** `apps/backend/app/modules/bookings/service.py`

**2. [Rule 1 - Bug] importlinter two edges needed (not zero)**
- **Found during:** Task 1 + Task 2 lint-imports run
- **Issue:** Plan stated "Prefer zero new edges if the existing module-independence contract allows." However, both `bookings.service → notifications.service` and `autopay_charges.service → notifications.service` are direct cross-module service imports that grimp catches correctly.
- **Fix:** Added two narrowly scoped edges per D-87-03-IMPORTLINTER decision. Service-function import only (not ORM/repository/models). Mirrors D-84-11 single-edge precedent.

**3. [Rule 1 - Bug] Test seed — memberships table snapshot fields**
- **Found during:** Task 2 test execution
- **Issue:** Direct raw SQL INSERT into `memberships` missing `plan_name_snapshot`, `duration_days_snapshot`, `price_kopecks_snapshot`, `freeze_days_limit_snapshot` NOT NULL columns.
- **Fix:** Added all 4 snapshot fields to the raw SQL INSERT in the autopay_charge_failed test.
- **Files modified:** `tests/notifications/test_notifications_event_hooks.py`

## Known Stubs

None — all 7 event hooks fully wired, all 9 tests proving correct behavior.

## Threat Flags

None — all STRIDE mitigations from the plan's threat model are implemented:
- T-87-10 (anti-oracle): payment_canceled has no hook; test proves 0 rows
- T-87-11 (replay): UNIQUE dedup in create_notification; replay test proves 1 row
- T-87-12 (co-transactional): all hooks are pre-commit (none in post-commit try/except blocks)
- T-87-13 (importlinter): two narrow edges added; lint-imports green
- T-87-14 (staff-cancel): both cancel_booking role branches hook; staff-cancel test proves client receives row

## Self-Check: PASSED
