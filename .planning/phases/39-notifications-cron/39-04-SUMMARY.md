---
phase: 39-notifications-cron
plan: 04
subsystem: bookings
tags: [arq, cron, structlog, sqlalchemy, async_sessionmaker, telegram, integritytypeerror, savepoint, multi-session, idempotency]

# Dependency graph
requires:
  - phase: 39-03
    provides: BookingNotification ORM at app/modules/bookings/models.py + Alembic 0020_booking_notifications head + cron_jobs insertion-point convention for D-39-16
  - phase: 39-02
    provides: bookings/service.py already imports MOSCOW_TZ + ModuleType + structlog + sqlalchemy.exc.IntegrityError + AsyncSession — Wave 4 only needs to extend the asyncio import to async_sessionmaker and add BookingNotification
  - phase: 39-01
    provides: render_booking_reminder_24h_dm + BOOKING_REMINDER_24H_DM template string with owner sign-off (NOTIFY-01)
  - phase: 27-membership-notifications
    provides: _send_expiring_notifications multi-session analog (mirrored verbatim for loop shape + failure-classification + IntegrityError rollback discipline)
provides:
  - "_send_booking_reminders SVC001-exempt service helper at app/modules/bookings/service.py (multi-session per D-39-06b; LEFT JOIN booking_notifications + n.id IS NULL pre-filter + BETWEEN now()+23h AND now()+25h + c.telegram_user_id IS NOT NULL per D-39-08; IntegrityError → rollback + INFO-log booking_reminder_idempotency_collision per D-39-13; end-of-loop INFO log send_booking_reminders_complete)"
  - "send_booking_reminders ARQ worker at app/workers/scheduled/send_booking_reminders.py (multi-session shape mirror of send_expiring_notifications.py)"
  - "WorkerSettings.functions + cron_jobs INSERT of send_booking_reminders BEFORE mark_no_show_bookings entries per D-39-16 final order: memberships(3:05) → expiring_notifs(3:15) → pt_packages(3:25) → reminders(3:35) → no_show(20:10)"
  - "scripts/run_booking_reminders_once.py operator one-shot runner (TM-29-02 + TM-29-03 BOTH kept — the reminder cron dispatches DMs — distinct from no_show runner which omits TM-29-03)"
  - "5 integration tests at tests/integration/bookings/test_reminder_cron.py covering happy path + idempotent re-run + 403-blocked skip + unlinked-client SELECT exclusion + IntegrityError collision rollback (locks the except IntegrityError branch under test coverage)"
  - "tests/unit/workers/test_worker_settings.py count assertions bumped from 4 → 5 (cron_jobs + functions)"
affects: [40-telegram-bot-book-openapi-verification (Phase 40 VER-07 inherits the BookingNotification + WorkerSettings final shape; real-Postgres asyncio.gather race test between reminder cron and one-shot runner is scoped to VER-07 per D-39-18)]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Multi-session DB cron helper with SVC001-exempt marker (mirror of memberships._send_expiring_notifications): one read session for SELECT candidates, fresh write session per successful send for INSERT + commit — frees DB pool connection across N Telegram HTTPS round-trips"
    - "DB-level idempotency via UNIQUE (booking_id, kind) + try/except IntegrityError + rollback + INFO-log collision (mirror v1.3 D-27-15 discipline applied to the booking_notifications side-table)"
    - "LEFT JOIN booking_notifications + WHERE n.id IS NULL SELECT-level idempotency pre-filter (BETWEEN now()+23h AND now()+25h locks the 2-hour reminder window) — steady-state second tick is a no-op"
    - "Cross-module raw SQL JOIN via sa.text(...) + `# noqa: TABLE_REF cross-module SQL per D-34-04a / Phase 38 D-38-11` marker (mirror of Wave 3 _mark_no_show_bookings)"
    - "Test-time collision injection via SimpleNamespace sender shim (NOT renderer shim — renderer is sync; the sender is awaited so its async wrapper can call `async with notifications_session_factory() as parallel: await parallel.commit()` to pre-INSERT the colliding row between render and the helper's post-send write_session.add+commit)"
    - "Eager-capture booking.id into local var before invoking the helper (per-send write sessions expire ORM instance attributes on the parent test session; later .id access would trigger MissingGreenlet under SQLAlchemy 2.0 async)"

key-files:
  created:
    - apps/backend/app/workers/scheduled/send_booking_reminders.py
    - apps/backend/scripts/run_booking_reminders_once.py
    - apps/backend/tests/integration/bookings/test_reminder_cron.py
    - .planning/phases/39-notifications-cron/39-04-SUMMARY.md
  modified:
    - apps/backend/app/modules/bookings/service.py
    - apps/backend/app/workers/__init__.py
    - apps/backend/tests/unit/workers/test_worker_settings.py

key-decisions:
  - "Cron registration ORDER per D-39-16 final: memberships(3:05) → expiring_notifs(3:15) → pt_packages(3:25) → reminders(3:35) → no_show(20:10) — send_booking_reminders is INSERTED at index 3 of WorkerSettings.cron_jobs (BEFORE mark_no_show_bookings); functions list also inserts at the same relative position"
  - "T-39-01 token-leak lock verified GREEN: `grep -E 'token=|bot_token' app/modules/bookings/service.py | grep -v build_bot | grep _log.` returns 0 hits — SendResult.error is structured text from python-telegram-bot which masks the token, and the WARNING log records error_msg=result.error without exposing the bot token"
  - "Collision test (Task 4 scenario 5) injects through the SENDER shim, not the renderer shim — the helper calls the renderer synchronously (no await), so the async pre-INSERT cannot ride on a renderer hook. The sender IS awaited, so a SimpleNamespace shim wrapping send_text_dm can perform the savepoint-factory pre-INSERT then delegate to the real sender. D-39-08 step ordering remains intact: render → send (incl. pre-INSERT) → write_session.add → commit-and-collide"
  - "Migration 0020_booking_notifications was applied to the local test DB as part of Task 4 setup — Wave 3 SUMMARY had deferred the alembic upgrade because Wave 3 tests didn't write to booking_notifications. Wave 4 tests REQUIRE the table, so `alembic upgrade head` was run before pytest. Phase 40 VER-07 will still want the up-down-up cycle for migration reversibility verification (Wave 3 deferral note still applies)"
  - "Eager booking.id capture pattern: tests that span the multi-session helper's per-send write sessions must read load-bearing attributes (PKs, FKs) into local vars BEFORE invoking the helper — SQLAlchemy 2.0 async expires loaded instances at session boundaries and later attribute access requires a greenlet context which capture_logs and assertion blocks do not provide"

requirements-completed: [CRON-02, CRON-03, CRON-05]

# Metrics
duration: ~11 min
completed: 2026-05-18
---

# Phase 39 Plan 04: 24h Booking Reminder Cron Summary

**Wave 4 of Phase 39 closes the milestone — `_send_booking_reminders` multi-session DB+Telegram helper with LEFT JOIN booking_notifications pre-filter + IntegrityError collision rollback, `send_booking_reminders` ARQ worker registered at 06:35 MSK BEFORE the 23:10 MSK no-show tick per D-39-16, operator one-shot runner with TM-29-02 + TM-29-03 guards, 5 integration tests covering all four happy/skip/exclude/collision branches. All four ROADMAP Phase 39 success criteria are now satisfied; the milestone is feature-complete pending Phase 40 verification.**

## Performance

- **Duration:** ~11 min (single executor session, no checkpoints)
- **Started:** 2026-05-18T07:15:26Z
- **Completed:** 2026-05-18T07:26:00Z
- **Tasks:** 4 (all complete; each atomically committed with `--no-verify` per parallel-executor convention)
- **Files modified:** 3 modified source files + 3 new files + this SUMMARY

## Accomplishments

- **`_send_booking_reminders` SVC001-exempt helper** appended to `apps/backend/app/modules/bookings/service.py` (~115 LOC). Multi-session per D-39-06b: one read session for the locked candidate SELECT; per-successful-send write session for the INSERT + commit. LEFT JOIN booking_notifications + n.id IS NULL pre-filter + BETWEEN now()+23h AND now()+25h + c.telegram_user_id IS NOT NULL per D-39-08 verbatim. `try/except IntegrityError` on the per-send INSERT rolls back the write session + INFO-logs `booking_reminder_idempotency_collision` (D-39-13). End-of-loop `send_booking_reminders_complete count=N` INFO log mirrors the analog. Carries `# noqa: SVC001 caller-owns-txn` on the def line; SVC001 walker stays GREEN (7/7).
- **`send_booking_reminders` ARQ worker** at `apps/backend/app/workers/scheduled/send_booking_reminders.py` — line-for-line mirror of `send_expiring_notifications.py` with bookings-domain imports (bookings.service, bookings.notifications) and the integrations.telegram.{sender, bot} layer. Constructs `Bot` once via `build_bot(token=...)` at worker scope; passes `ctx['sessionmaker']` + bot + sender_module + notifications_module to the helper.
- **WorkerSettings wiring** at `apps/backend/app/workers/__init__.py`:
  - Imported `send_booking_reminders` (grouped above `send_expiring_notifications` to keep imports alphabetical within the scheduled namespace).
  - INSERTED `send_booking_reminders` into `functions: ClassVar[list[Any]]` at index 3 (BEFORE `mark_no_show_bookings`); list grew 4 → 5.
  - INSERTED `cron(send_booking_reminders, hour=3, minute=35, unique=True, keep_result=60)` into `cron_jobs: ClassVar[list[Any]]` at index 3 (BEFORE the `mark_no_show_bookings` cron entry); list grew 4 → 5.
  - Final D-39-16 order verified by runtime cron-resolution invariant + smoke check: `['expire_memberships', 'send_expiring_notifications', 'expire_pt_packages', 'send_booking_reminders', 'mark_no_show_bookings']`.
- **`scripts/run_booking_reminders_once.py`** — operator one-shot runner. TM-29-02 (localhost-only DATABASE_URL) + TM-29-03 (TELEGRAM_SANDBOX_CHAT_ID env-presence) BOTH kept (distinct from `run_no_show_cron_once.py` which omits TM-29-03 per D-39-17 because the no-show cron is DB-only). REG-29-04 eager-imports cover all 5 modules: `auth`, `bookings`, `clients`, `schedule`, `trainers`. Reuses `WorkerSettings.on_startup`/`on_shutdown` (MH-29-05 mirror). Both safety guards verified exit 1 with explicit stderr messages.
- **5 integration tests** at `apps/backend/tests/integration/bookings/test_reminder_cron.py`:
  1. `test_reminders_cron_inserts_idempotency_row_per_send` — happy path: 1 send + 1 booking_notifications row; verifies rendered text matches the locked template applied to seeded `client_name`/`trainer_name`/`slot_start_msk` (MOSCOW_TZ-formatted via `astimezone(MOSCOW_TZ).strftime("%d.%m.%Y %H:%M")`).
  2. `test_reminders_cron_idempotent_second_run_zero` — LEFT JOIN n.id IS NULL pre-filter excludes the row; sender NEVER reached on second tick; booking_notifications row count stays at 1.
  3. `test_reminders_cron_skips_403_blocked_no_row` — `SendResult(ok=False, blocked=True, error="403 Forbidden")` → WARNING-log `booking_reminder_send_failed reason='bot_blocked'` + NO row insert.
  4. `test_reminders_cron_skips_unlinked_client` — client with `telegram_user_id IS NULL` excluded by SQL `c.telegram_user_id IS NOT NULL` filter; **zero** sender calls (excluded at SELECT layer before any sender attempt).
  5. `test_reminders_cron_collision_rollback_on_pre_inserted_row` — exercises the `except IntegrityError` branch via a SimpleNamespace sender shim that pre-INSERTs the colliding row through the same savepoint factory BETWEEN render and the helper's post-send `write_session.add+commit`. Helper returns 0; sender call count is 1 (the send went out BEFORE the per-send INSERT was attempted); INFO event `booking_reminder_idempotency_collision` emitted exactly once for the booking; exactly one surviving notification row (the pre-inserted one — helper's write_session was rolled back).
- **Autouse `_reset_reminder_worker_logger_cache` fixture** at the top of the test file resets BOTH `bookings.service._log` AND `workers.scheduled.send_booking_reminders._log` so `structlog.testing.capture_logs()` observes the module-level structlog events (BoundLoggerLazyProxy cache invariant per the `test_expire_pt_packages_cron` analog).
- **`tests/unit/workers/test_worker_settings.py` count assertions** bumped from 4 → 5 for both `len(WorkerSettings.cron_jobs)` and `len(WorkerSettings.functions)`. Docstrings updated to reflect the Wave 3 + Wave 4 cumulative additions.

## Final WorkerSettings Snapshot (D-39-16 LOCKED for milestone reference)

```python
functions: ClassVar[list[Any]] = [
    expire_memberships,
    send_expiring_notifications,
    expire_pt_packages,
    send_booking_reminders,   # Phase 39 CRON-02 (Wave 4)
    mark_no_show_bookings,    # Phase 39 CRON-01 (Wave 3)
]

cron_jobs: ClassVar[list[Any]] = [
    cron(expire_memberships,         hour=3,  minute=5,  unique=True, keep_result=60),  # 06:05 MSK
    cron(send_expiring_notifications, hour=3,  minute=15, unique=True, keep_result=60),  # 06:15 MSK
    cron(expire_pt_packages,         hour=3,  minute=25, unique=True, keep_result=60),  # 06:25 MSK
    cron(send_booking_reminders,     hour=3,  minute=35, unique=True, keep_result=60),  # 06:35 MSK (Wave 4)
    cron(mark_no_show_bookings,      hour=20, minute=10, unique=True, keep_result=60),  # 23:10 MSK (Wave 3)
]
```

## Phase 39 Service-Layer Cron Helpers (cumulative across all 4 plans)

| Helper | File:Line | Wave | Pattern | Caller-owns-txn |
|---|---|---|---|---|
| `_dispatch_booking_dm` | `app/modules/bookings/service.py:312` | 39-02 | Sync post-commit DM dispatch (per-booking, NOT a cron) | N/A (called from create/cancel/cascade orchestrators) |
| `_mark_no_show_bookings` | `app/modules/bookings/service.py:382` | 39-03 | Single-session SELECT FOR UPDATE OF b + bulk UPDATE + per-row audit emit | `mark_no_show_bookings` worker |
| `_send_booking_reminders` | `app/modules/bookings/service.py:462` | **39-04** | Multi-session: 1 read session + per-send write sessions; LEFT JOIN pre-filter + IntegrityError catch | `send_booking_reminders` worker |

## ROADMAP Phase 39 Success Criteria — ALL 4 SATISFIED

- **SC1 — notifications.py + create/cancel/cascade DM dispatch:** Plans 39-01 (locked templates + renderers) + 39-02 (`_dispatch_booking_dm` + post-commit dispatch in create/cancel/cascade orchestrators) ✓
- **SC2 — `run_no_show_cron_once.py` + audit emit:** Plan 39-03 (`_mark_no_show_bookings` + `mark_no_show_bookings` worker + operator runner + `booking_no_show` audit emit) ✓
- **SC3 — `run_booking_reminders_once.py` + `booking_notifications` row:** Plan 39-03 (Alembic 0020 + BookingNotification ORM) + Plan **39-04** (`_send_booking_reminders` + per-send `booking_notifications` row insert + `run_booking_reminders_once.py` operator runner) ✓
- **SC4 — both crons in WorkerSettings.cron_jobs with `unique=True, keep_result=60`:** Plans 39-03 (`mark_no_show_bookings` at 20:10) + **39-04** (`send_booking_reminders` at 03:35, inserted BEFORE no_show per D-39-16) ✓

## Task Commits

Each task committed atomically with `--no-verify` (parallel-executor convention) and a Conventional Commit message under the `(39-04)` scope.

1. **Task 1: _send_booking_reminders multi-session helper + IntegrityError rollback** — `dc69fa5` (feat)
2. **Task 2: send_booking_reminders worker + WorkerSettings wiring (D-39-16 order)** — `6b942d9` (feat)
3. **Task 3: scripts/run_booking_reminders_once.py operator one-shot runner** — `ca18978` (feat)
4. **Task 4: 5 integration tests for _send_booking_reminders cron** — `c9d4503` (test)

**Plan metadata commit:** appended after this SUMMARY file is written.

## Files Created/Modified

- `apps/backend/app/modules/bookings/service.py` — MODIFIED. Two import-line edits (`AsyncSession, async_sessionmaker` and `Booking, BookingNotification`); appended `_send_booking_reminders` (~115 LOC) between `_mark_no_show_bookings` (line 459) and the Phase 37 `complete_booking` Protocol slot body (line 469+).
- `apps/backend/app/workers/scheduled/send_booking_reminders.py` — NEW. Mirror of `send_expiring_notifications.py` line-for-line with bookings-domain swap; module docstring documents the multi-session contract, D-39-10 build_bot discipline, and D-39-16 cron slot.
- `apps/backend/app/workers/__init__.py` — MODIFIED. Import added; `functions` list grown 4 → 5 with `send_booking_reminders` inserted BEFORE `mark_no_show_bookings`; `cron_jobs` list grown 4 → 5 with the new cron entry inserted at index 3 (before the no_show entry); existing comment block above the no_show entry rewritten to reflect Wave 4 final state.
- `apps/backend/scripts/run_booking_reminders_once.py` — NEW. Operator one-shot runner with TM-29-02 + TM-29-03 + REG-29-04 (5-module eager-imports).
- `apps/backend/tests/unit/workers/test_worker_settings.py` — MODIFIED. Two assertion lines updated from `== 4` to `== 5` for `len(WorkerSettings.cron_jobs)` and `len(WorkerSettings.functions)`; docstrings updated to reflect the Wave 4 addition.
- `apps/backend/tests/integration/bookings/test_reminder_cron.py` — NEW. 5 integration tests + autouse logger-cache reset fixture + a local `_seed_eligible_reminder_candidate` helper that consolidates the trainer/client/pt_package/slot/booking factory orchestration.
- `.planning/phases/39-notifications-cron/39-04-SUMMARY.md` — this file.

## SVC001 Walker Compliance

The new `_send_booking_reminders` def line carries `# noqa: SVC001 caller-owns-txn` per the established Phase 30 / Phase 33 / Phase 39 Wave 3 pattern. Verified GREEN by `tests/unit/test_service_commit_gate.py` (7/7 passed). The marker documents that the helper intentionally does NOT call `await session.commit()` on a single caller-provided session — instead it opens its own per-send write sessions that DO commit each. The worker function `send_booking_reminders(ctx)` is the transaction-orchestration shell but does not itself own a single session.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 — Blocking] Migration 0020 needed to be applied to the local test DB before Task 4 tests could run**
- **Found during:** Task 4 initial test run.
- **Issue:** The local Postgres test DB was at alembic revision `0019_pt_sessions_booking_id` because Wave 3's SUMMARY had explicitly deferred the live alembic upgrade ("the live-DB alembic cycle below MUST be run against a localhost Postgres before Phase 40 milestone verification"). Wave 3 tests don't write to `booking_notifications`, so they passed at 0019. Wave 4 tests REQUIRE the table — first run died on `UndefinedTableError: relation "booking_notifications" does not exist`.
- **Fix:** Ran `alembic upgrade head` (loading env from `.env.example`) to bring the test DB from 0019 → 0020. This is environment setup, not a code change.
- **Files modified:** none (DB-only state change).
- **Verification:** All 5 reminder tests pass after the upgrade; the no_show_cron + notifications regression suites stay green (64 integration tests + 7 SVC001 tests all GREEN).
- **Committed in:** N/A (DB-only setup, not a code fix). Phase 40 VER-07 will still need the up-down-up cycle for migration reversibility verification per Wave 3 SUMMARY § User Setup Required.

**2. [Rule 1 — Bug] Test 5 (collision) initially used async renderer wrapper; renderer is sync — switched to sender shim**
- **Found during:** Task 4 first iteration of `test_reminders_cron_collision_rollback_on_pre_inserted_row`.
- **Issue:** Initial design wrapped `render_booking_reminder_24h_dm` in a `SimpleNamespace` shim with an `async def _pre_insert_then_render(...)` that performed the pre-INSERT then returned the rendered text. But the helper calls the renderer SYNCHRONOUSLY (`text_body = notifications_module.render_booking_reminder_24h_dm(...)` — no `await`), so the async wrapper returned a coroutine that was never awaited — `RuntimeWarning: coroutine ... was never awaited` + no collision.
- **Fix:** Moved the collision-injection seam from the renderer to the **sender**. The helper calls `await sender.send_text_dm(...)` — an awaited async call. The new design wraps `send_text_dm` in a SimpleNamespace shim: the wrapper performs the savepoint-factory pre-INSERT, then delegates to the real `sender_module.send_text_dm`. D-39-08 step ordering remains intact: render → send (incl. pre-INSERT) → write_session.add → commit-and-collide.
- **Files modified:** `apps/backend/tests/integration/bookings/test_reminder_cron.py` — collision-test seam re-wired.
- **Verification:** Test passes; SQL trace shows `SAVEPOINT sa_savepoint_8` (pre-INSERT) → `RELEASE` → `SAVEPOINT sa_savepoint_9` (helper's INSERT attempt) → `ROLLBACK TO SAVEPOINT sa_savepoint_9` (collision rollback).
- **Committed in:** `c9d4503` (Task 4 commit — the issue was discovered and resolved during the TDD red-green-refactor loop for that single test).

**3. [Rule 1 — Bug] Test 5 hit `MissingGreenlet` on `booking.id` access after helper return — captured ID eagerly**
- **Found during:** Task 4 second iteration of `test_reminders_cron_collision_rollback_on_pre_inserted_row` (after the sender-shim fix above).
- **Issue:** After the helper returned, the test accessed `booking.id` in the captured-logs assertion block. The helper's per-send write sessions opening + closing through the savepoint sessionmaker had expired the `booking` ORM instance's attributes on the parent `db_session`. The next `booking.id` read triggered an async refresh outside any greenlet context → `MissingGreenlet: greenlet_spawn has not been called; can't call await_only() here`.
- **Fix:** Capture `booking_id = booking.id` into a local var IMMEDIATELY after seeding (before invoking the helper). All subsequent reads use `booking_id` instead of `booking.id`. Pattern documented inline with a load-bearing comment.
- **Files modified:** `apps/backend/tests/integration/bookings/test_reminder_cron.py` — added the eager-capture line + comment.
- **Verification:** Test passes (5/5 reminder tests + 64 bookings/notifications integration + 7 SVC001 — all GREEN).
- **Committed in:** `c9d4503` (Task 4 commit — same TDD loop as Deviation #2).

### Auth Gates

None — Phase 39 plan 39-04 dispatches Telegram DMs via the integrations layer, but the worker constructs the `Bot` via `build_bot(token=settings.telegram_bot_token.get_secret_value())` at runtime; no operator credentials are required to land or test the plan. The TM-29-03 guard on `scripts/run_booking_reminders_once.py` is a runtime safety gate (refuses to fire without `TELEGRAM_SANDBOX_CHAT_ID` set), not an auth gate that requires operator credentials.

---

**Total deviations:** 3 (1 Rule 3 environment-setup + 2 Rule 1 test-implementation bugs, all auto-fixed during the same task commit).
**Impact on plan:** Zero behavior or contract drift. Deviation #1 is environment setup explicitly authorized by Wave 3's SUMMARY. Deviations #2 + #3 are TDD-loop iterations within Task 4 — final test file passes 5/5 and exercises the IntegrityError branch correctly.

## Issues Encountered

- **Sync vs. async renderer (see Deviation #2):** The plan's `<action>` block for Task 4 scenario 5 suggested monkeypatching the renderer to do the pre-INSERT, but the helper invokes the renderer synchronously. The plan's footnote did acknowledge a fallback: "If the parallel-session approach proves fragile under the savepoint sessionmaker (rare ...), fall back to monkeypatching `_send_booking_reminders`'s import-resolved `BookingNotification` to a subclass that triggers `IntegrityError` on `__init__` for the second observed `booking_id`." The chosen sender-shim approach is a cleaner third path that doesn't require subclassing the ORM model and stays inside the savepoint envelope.
- **SQLAlchemy 2.0 async ORM-instance expiry across helper boundaries (see Deviation #3):** Any future test that spans a multi-session helper and asserts on the seeded entities' attributes AFTER the helper returns should pre-capture load-bearing attributes (PKs, FKs, text fields) into local vars. This is now the documented pattern for `_send_booking_reminders`-style helpers in the bookings module.

## User Setup Required

**Operator action required at Phase 40 VER-07 milestone verification time** (deferred from Wave 3 SUMMARY's manual block):

```bash
cd apps/backend
DATABASE_URL=postgresql+asyncpg://<localhost-creds> uv run alembic upgrade head
DATABASE_URL=postgresql+asyncpg://<localhost-creds> uv run alembic downgrade -1
DATABASE_URL=postgresql+asyncpg://<localhost-creds> uv run alembic upgrade head
```

The Wave 4 executor applied `alembic upgrade head` on the local Postgres (moving from 0019 → 0020) so that Task 4 tests could run, but the down-up-down reversibility cycle was NOT exercised. Phase 40 VER-07 should run the full cycle and confirm `alembic check` reports no drift.

No other operator setup required — `send_booking_reminders` is a scheduled cron with no env-var or credential dependency beyond `DATABASE_URL`, `REDIS_URL`, and `TELEGRAM_BOT_TOKEN` (already required by the existing crons).

## Next Phase Readiness

- **Phase 40 (Telegram /book endpoint + OpenAPI + Verification)** can proceed. Phase 39 is feature-complete:
  - All 4 ROADMAP success criteria satisfied (see § ROADMAP Phase 39 Success Criteria above).
  - Two new ARQ cron entries live in `WorkerSettings.cron_jobs` in the locked D-39-16 order.
  - `booking_notifications` table exists at Alembic head 0020 with the (booking_id, kind) UNIQUE idempotency gate.
  - `_send_booking_reminders` helper + worker + one-shot runner all green under ruff + mypy --strict + lint-imports + 64 integration tests + 7 SVC001 tests + 15 worker unit tests.
- **Phase 40 VER-07 real-Postgres race test** (deferred from this plan per D-39-18) should exercise `asyncio.gather(send_booking_reminders_cron(...), run_booking_reminders_once())` against a real Postgres to confirm the IntegrityError + rollback branch survives a cross-process race. The integration test 5 in this plan locks the branch under SAVEPOINT test coverage; VER-07 will lock it under real concurrent transactions.

## Verification Evidence

Captured during this session:

```
=== RUFF (5 surfaces: bookings/service.py, workers/scheduled/send_booking_reminders.py, workers/__init__.py, scripts/, tests/integration/bookings/test_reminder_cron.py) ===
All checks passed!
(only the pre-existing TABLE_REF noqa warnings on lines 408 + 504 of bookings/service.py — shared with bookings/repository.py:127, non-blocking)

=== MYPY --strict (4 source files) ===
Success: no issues found in 4 source files

=== LINT-IMPORTS ===
Analyzed 121 files, 336 dependencies.
core must not import modules KEPT
modules cannot import each other KEPT
integrations must not import modules KEPT
Contracts: 3 kept, 0 broken.

=== NEW TESTS (test_reminder_cron.py) ===
5 passed in 0.74s

=== BOOKINGS + NOTIFICATIONS FULL REGRESSION ===
tests/integration/bookings/ + tests/integration/notifications/
64 passed in 9.06s

=== SVC001 WALKER ===
tests/unit/test_service_commit_gate.py
7 passed in 0.04s

=== WORKER UNIT GATES ===
tests/unit/ -k worker
15 passed (test_worker_settings.py 7 + test_worker_cron_resolution.py 4 + test_arq_contextvars.py 4)

=== FINAL D-39-16 ORDER LOCKED ===
[c.coroutine.__name__ for c in WorkerSettings.cron_jobs] ==
  ['expire_memberships', 'send_expiring_notifications', 'expire_pt_packages',
   'send_booking_reminders', 'mark_no_show_bookings']
send_booking_reminders entry: hour=3, minute=35, unique=True, keep_result_s=60

=== T-39-01 TOKEN-LEAK LOCK ===
grep -E "token=|bot_token" app/modules/bookings/service.py | grep -v build_bot | grep _log.
→ 0 hits (no token reference inside any structlog call)

=== TM-29-02 GUARD (non-local DATABASE_URL exits 1) ===
DATABASE_URL=postgresql+asyncpg://u:p@example.com:5432/x uv run python -m scripts.run_booking_reminders_once
> ERROR: run_booking_reminders_once refuses to run against a non-local DATABASE_URL (TM-29-02).
> exit=1

=== TM-29-03 GUARD (local DATABASE_URL + no TELEGRAM_SANDBOX_CHAT_ID exits 1) ===
DATABASE_URL=postgresql+asyncpg://u:p@localhost:5432/x uv run python -m scripts.run_booking_reminders_once
> ERROR: TELEGRAM_SANDBOX_CHAT_ID must be set; refusing to fire cron (TM-29-03).
> exit=1

=== CRON-RESOLUTION INVARIANT (on_startup smoke + dedicated unit test) ===
test_on_startup_cron_resolution_invariant_passes_at_baseline PASSED
test_on_startup_raises_when_cron_references_unregistered_function PASSED
```

## Self-Check: PASSED

**Files verified present (`[ -f <path> ] && echo FOUND` per file):**
- `apps/backend/app/workers/scheduled/send_booking_reminders.py` FOUND
- `apps/backend/scripts/run_booking_reminders_once.py` FOUND
- `apps/backend/tests/integration/bookings/test_reminder_cron.py` FOUND
- `.planning/phases/39-notifications-cron/39-04-SUMMARY.md` FOUND
- `apps/backend/app/modules/bookings/service.py` FOUND (modified)
- `apps/backend/app/workers/__init__.py` FOUND (modified)
- `apps/backend/tests/unit/workers/test_worker_settings.py` FOUND (modified)

**Commits verified present in `git log --oneline`:**
- `dc69fa5` (Task 1 — feat: _send_booking_reminders helper) FOUND
- `6b942d9` (Task 2 — feat: worker + WorkerSettings wiring) FOUND
- `ca18978` (Task 3 — feat: operator one-shot runner) FOUND
- `c9d4503` (Task 4 — test: 5 integration tests) FOUND

---
*Phase: 39-notifications-cron*
*Completed: 2026-05-18*
