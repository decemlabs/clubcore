---
phase: 46-openapi-handoff-milestone-verification
plan: 09
subsystem: notifications / verification
tags: [VER-10, race-test, real-postgres, asyncio-gather, expiring-cron, email-fallback, D-45-01, D-45-04, D-46-14]
requires:
  - alembic/0024 — UNIQUE (membership_id, kind, channel) on membership_notifications (Phase 41 D-41-15)
  - app/modules/memberships/service.py::_send_expiring_notifications — D-45-01 synthesised-blocked branch + D-45-04 race-duplicate IntegrityError guard
  - app/core/dependencies.register_email_dispatcher — Phase 41 D-41-24 slot
provides:
  - VER-10 race test #5 — concurrent cron double-pings race
affects:
  - apps/backend/tests/integration/ — adds one new file; touches nothing else
tech-stack:
  added: []
  patterns:
    - real_commit_engine pattern (own copy; mirrors Phase 45 D-45-28 test_payment_receipt_race.py shape)
    - asyncio.gather of in-process helper invocations sharing one async_sessionmaker
    - D-45-01 synthesised-blocked Telegram path (chat_id IS NULL) for deterministic email-fallback reach without telegram mocks
    - per-test EmailDispatcher registration with prior-slot save/restore (Phase 41 D-41-24)
key-files:
  created:
    - apps/backend/tests/integration/test_concurrent_expiring_cron_double_pings_race.py
  modified: []
decisions:
  - >-
    Reached the email-fallback INSERT via the Phase 45 D-45-01 synthesised-blocked
    branch (client.telegram_user_id IS NULL) rather than mocking sender.send_text_dm
    to return SendResult(ok=False, blocked=True). The synthesised branch is fully
    deterministic, requires zero Telegram object surface, and matches the production
    code path Phase 45 ships for email-only clients.
  - >-
    Used the helper's existing D-45-04 race-duplicate IntegrityError handler as the
    test's correctness assertion (sum of return values across both gather arms == 1;
    DB row count == 1). The helper does NOT re-raise on the UNIQUE conflict — it
    rolls back the loser's session and emits a structlog warning
    "expiring_email_idempotency_conflict reason=duplicate_row". The test asserts the
    surviving-row invariant rather than the loser's exception type, mirroring how
    production code observes the race.
  - >-
    EmailDispatcher recorder asserted ≥1 invocation (not exactly 2) because the
    loser's enqueue may legitimately complete BEFORE its INSERT fails (the dispatch
    runs before commit). The DB-row invariant (count==1) is the canonical race
    assertion; the dispatcher count is a secondary sanity check on the literal
    template_id branch.
metrics:
  duration: ~3 min
  completed: 2026-05-20
---

# Phase 46 Plan 09: Concurrent Expiring-Cron Double-Pings Race (VER-10 #5) Summary

Authored one new real-Postgres integration test that races two concurrent
in-process invocations of `_send_expiring_notifications` against the same
membership via `asyncio.gather`, asserting the UNIQUE
`(membership_id, kind, channel)` constraint (Alembic 0024 + Phase 41 D-41-15)
keeps exactly one `channel='email'` row in `membership_notifications`.

## What was built

- **`apps/backend/tests/integration/test_concurrent_expiring_cron_double_pings_race.py`**
  - 1 test function: `test_concurrent_expiring_cron_double_pings_race`
  - Local `real_commit_engine` async fixture (probe-then-skip on
    unreachable Postgres; TRUNCATE
    `membership_notifications, audit_log, memberships, membership_plans,
    clients, users RESTART IDENTITY CASCADE` at teardown).
  - Local `email_recorder` fixture registering a `_RecordingEmailDispatcher`
    spy with prior-slot save/restore.
  - Seeds one owner + one plan + one client (`telegram_user_id=NULL`,
    `email='race-cron+…@local.dev'`) + one membership ending exactly 7
    days from `today=2026-06-01`.
  - Races: `await asyncio.gather(_invoke(), _invoke())` where each
    `_invoke` calls `memberships_service._send_expiring_notifications`
    sharing one `async_sessionmaker(real_commit_engine, expire_on_commit=False)`.
  - Asserts:
    1. `sum(results) == 1` — exactly one gather arm reports
       `sent_count == 1`.
    2. `SELECT count(*) FROM membership_notifications WHERE
       membership_id = :mid AND channel = 'email'` returns `1`.
    3. Zero `channel='telegram'` rows (chat_id was NULL).
    4. `email_recorder.calls` has ≥ 1 invocation, each with
       `template_id` starting with `EMAIL_EXPIRING_7D_` and recipient
       starting with `race-cron+`.

## How the race fires

1. Both gather arms run `find_expiring_candidates` independently;
   the NOT-EXISTS predicate passes for both because neither has
   inserted yet (the helper's pattern reads candidates in a separate
   read session that closes before the write phase — D-27-07).
2. Both arms enter the email-fallback branch because `chat_id IS NULL`
   triggers the D-45-01 synthesised
   `SendResult(ok=False, blocked=True)` and the candidate has
   `client_email` set.
3. One arm INSERTs into `membership_notifications` first and commits.
4. The other arm's INSERT raises `IntegrityError` on
   `uq_membership_notifications_membership_kind_channel`; the helper's
   inline `except IntegrityError` (service.py:1753-1763) rolls back
   and logs `"expiring_email_idempotency_conflict"
   reason=duplicate_row`.
5. Verified via `pytest -s` output:

   ```text
   expiring_notification_email_fanout_sent
       audit_correlation_id=… membership_id=… kind=expiring_7d
   expiring_email_idempotency_conflict
       kind=expiring_7d membership_id=… reason=duplicate_row
   ```

## Verification

- `pytest tests/integration/test_concurrent_expiring_cron_double_pings_race.py -v`
  → `1 passed in 0.26s` (Postgres reachable).
- Grep gates:
  - `grep -c asyncio.gather …` → **4**
  - `grep -cE 'subprocess|Popen|run_cron_once\.py' …` → **0** (HARD CONSTRAINT met)
  - `grep -c real_commit_engine …` → **3**
  - `grep -cE "channel\s*=\s*'email'" …` → **5**
  - `grep -c 'TRUNCATE membership_notifications' …` → **1**

## Deviations from Plan

None — plan executed exactly as written. The plan's strawman SQL seed
(raw `INSERT INTO` with plan-snapshot columns) was used verbatim;
the only adaptation was to also seed a `users` row and a
`membership_plans` row in the same setup session (the plan flagged
this in step 4 — "the FK chain requires a user row first or reference
an existing one; plan_id requires a membership_plans row"). No
auto-fixes, no architectural changes.

## Commits

- `d13c8e8` — `test(46-09): concurrent expiring-cron double-pings race (VER-10 #5)`

## Self-Check: PASSED

- File exists: `apps/backend/tests/integration/test_concurrent_expiring_cron_double_pings_race.py` — **FOUND**
- Commit `d13c8e8` — **FOUND** in git log
- All acceptance criteria green (see Verification section)
- No STATE.md / ROADMAP.md changes (orchestrator owns those)
