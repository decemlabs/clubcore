---
phase: 39-notifications-cron
plan: 03
subsystem: bookings
tags: [alembic, sqlalchemy, arq, cron, structlog, audit, import-linter, modules-independent, pytest-asyncio, savepoint]

# Dependency graph
requires:
  - phase: 39-02
    provides: bookings/service.py with _dispatch_booking_dm + post-commit DM dispatch (this plan APPENDS _mark_no_show_bookings near the existing private helpers; serial after 39-02 per the 2026-05-17 revised wave layout)
  - phase: 38-schedule-module-booking-core
    provides: bookings.status FSM, trainer_availability_slots schema, record_pt_session D-38-19 booking row-lock (partner-side serialization target for D-39-07 SELECT FOR UPDATE OF b)
  - phase: 37-foundations-bedrock
    provides: BookingNoShowPayload audit schema (audit_payloads.py:410-424) + LOCKED_AUDIT_EVENTS registration ('booking_no_show', 'booking')
provides:
  - "Alembic 0020_booking_notifications head (revision id '0020_booking_notifications', down_revision '0019_pt_sessions_booking_id') — 4-business-column idempotency table consumed by plan 39-04's reminder cron"
  - "BookingNotification ORM class at app/modules/bookings/models.py (write-once, NO SoftDeleteMixin, NO telegram_chat_id snapshot per D-39-03, NO Booking.notifications back-relationship)"
  - "_mark_no_show_bookings SVC001-exempt service helper (D-39-06 single-session, D-39-07 SELECT FOR UPDATE OF b serializes against record_pt_session's D-38-19 lock)"
  - "mark_no_show_bookings ARQ worker (single-session shape mirror of expire_pt_packages.py)"
  - "WorkerSettings.functions + cron_jobs APPEND with cron(mark_no_show_bookings, hour=20, minute=10, unique=True, keep_result=60) — 23:10 MSK evening tick"
  - "scripts/run_no_show_cron_once.py operator one-shot runner (TM-29-02 KEPT, TM-29-03 OMITTED per D-39-17 — explicit docstring)"
  - "3 integration tests covering happy path + idempotent re-run + worker e2e summary log"
  - "make_future_slot factory contract widened to accept negative start_offset (cron-test convenience; existing default unchanged)"
affects: [39-04-reminder-cron (consumes BookingNotification ORM + 0020 head + insertion-point convention for the second cron entry per D-39-16)]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Single-session DB-only cron helper with SVC001-exempt marker (mirror of pt_packages._expire_due_pt_packages + memberships._expire_due_memberships); worker function owns commit"
    - "SELECT FOR UPDATE OF b (Postgres row lock on the bookings table only — not the joined slot) for cross-cron serialization against pt_sessions.record_pt_session's D-38-19 booking row-lock"
    - "Cross-module raw SQL JOIN via sa.text(...) + `# noqa: TABLE_REF cross-module SQL per D-34-04a / Phase 38 D-38-11` marker — keeps modules-independent import-linter contract green while reading trainer_availability_slots from inside bookings.service"
    - "Operator one-shot runner with TM-29-02 (localhost-only DATABASE_URL guard) but WITHOUT TM-29-03 (TELEGRAM_SANDBOX_CHAT_ID) — DB-only cron has no Telegram I/O; documented per D-39-17"
    - "Autouse logger-cache reset fixture invalidating BoundLoggerLazyProxy bind cache (BOTH worker module AND bookings.service) so structlog.testing.capture_logs() observes module-level _log events"
    - "Factory contract widening (make_future_slot accepts negative start_offset) with bypassed service-layer publish guard — direct ORM insert only validates DB-level CHECK constraints"

key-files:
  created:
    - apps/backend/alembic/versions/0020_booking_notifications.py
    - apps/backend/app/workers/scheduled/mark_no_show_bookings.py
    - apps/backend/scripts/run_no_show_cron_once.py
    - apps/backend/tests/integration/bookings/test_no_show_cron.py
    - .planning/phases/39-notifications-cron/39-03-SUMMARY.md
  modified:
    - apps/backend/app/modules/bookings/models.py
    - apps/backend/app/modules/bookings/service.py
    - apps/backend/app/workers/__init__.py
    - apps/backend/tests/integration/bookings/conftest.py

key-decisions:
  - "Alembic 0020 head revision id is '0020_booking_notifications' with down_revision='0019_pt_sessions_booking_id' — plan 39-04 imports BookingNotification ORM + writes to this table via the (booking_id, kind) UNIQUE idempotency gate"
  - "FK booking_notifications.booking_id ON DELETE RESTRICT (D-39-13 — deviation from v1.3 MembershipNotification CASCADE; bookings never hard-delete per Phase 38 D-38-04)"
  - "NO telegram_chat_id snapshot column on booking_notifications (D-39-03 — deviation from v1.3 MembershipNotification.telegram_chat_id); reminder cron resolves clients.telegram_user_id at send time via JOIN, always-current chat id, no future schema-debt cleanup"
  - "audit.emit kwargs for booking_no_show string-cast UUIDs (deviation from plan task instruction). The plan text claimed 'raw UUIDs work via Pydantic v2 coercion D-39-14' — true for schema validation, but emit then writes the kwargs dict DIRECTLY into JSONB; raw UUID objects raise json.dumps TypeError. The actual Phase 38 idiom for the partner-side booking_cancelled emit at bookings/service.py:709-713 also string-casts. Fix: pass `str(c.id)` etc. — Pydantic still accepts (D-39-14 schema accepts both str + UUID); JSONB write now works"
  - "Cron entry insertion point convention for plan 39-04: send_booking_reminders MUST go BEFORE the mark_no_show_bookings cron entry per D-39-16 final order (memberships -> expiring_notifs -> pt_packages -> reminders -> no_show). The functions list ordering should match. Until 39-04 lands, mark_no_show_bookings sits immediately after expire_pt_packages — acceptable interim state per the plan"
  - "SVC001 walker stays green with the new `# noqa: SVC001 caller-owns-txn` marker on `_mark_no_show_bookings` def line — verified by tests/unit/test_service_commit_gate.py (7 passed)"

requirements-completed: [NOTIFY-05, CRON-01, CRON-03, CRON-04]

# Metrics
duration: ~50 min
completed: 2026-05-18
---

# Phase 39 Plan 03: No-Show Cron + booking_notifications Table Summary

**Alembic 0020 + BookingNotification ORM + _mark_no_show_bookings SVC001-exempt service helper using SELECT FOR UPDATE OF b + mark_no_show_bookings ARQ worker registered at 23:10 MSK + operator one-shot runner with TM-29-02 guard + 3 integration tests — all gates green, all 4 ROADMAP success criteria for this slice satisfied (SC2 + table half of SC3 + first cron entry of SC4).**

## Performance

- **Duration:** ~50 min (single executor session)
- **Started:** 2026-05-18T09:35:00Z (approximate)
- **Completed:** 2026-05-18T10:25:00Z (approximate)
- **Tasks:** 4 (all complete; each atomically committed)
- **Files modified:** 4 modified source files + 4 new files + this SUMMARY

## Accomplishments

- **Alembic 0020_booking_notifications** (`apps/backend/alembic/versions/0020_booking_notifications.py`) — creates `booking_notifications` with 4 business columns (`id`, `booking_id`, `kind`, `sent_at`) + 2 mixin columns (`created_at`, `updated_at`). Constraints (all matching the ORM letter-for-letter per Phase 30 INFRA-23): PK `pk_booking_notifications`, FK `fk_booking_notifications_booking_id_bookings` (ON DELETE RESTRICT per D-39-13), CHECK `ck_booking_notifications_kind` (`kind IN ('reminder_24h')`), UNIQUE `uq_booking_notifications_booking_kind` `(booking_id, kind)`, index `ix_booking_notifications_booking_id`. NO `telegram_chat_id` column (D-39-03).
- **BookingNotification ORM** at `apps/backend/app/modules/bookings/models.py` (appended after `Booking`) — Base + UUIDPkMixin + TimestampMixin composition, NO SoftDeleteMixin (write-once side-table), NO `Booking.notifications` back-relationship (raw SQL JOIN at cron read time per plan 39-04's contract).
- **`_mark_no_show_bookings` SVC001-exempt helper** at `apps/backend/app/modules/bookings/service.py:382-451` (line numbers post-Wave-2 baseline). `SELECT FOR UPDATE OF b` row-locks each candidate booking; cross-module SQL JOIN uses raw `sa.text(...)` + `# noqa: TABLE_REF cross-module SQL per D-34-04a / Phase 38 D-38-11`. Per-row `audit.emit("booking_no_show", ...)` with LITERAL strings; payload matches `BookingNoShowPayload(extra='forbid')` exactly. Caller (worker) owns commit.
- **`mark_no_show_bookings` ARQ worker** at `apps/backend/app/workers/scheduled/mark_no_show_bookings.py` — single-session per D-39-06, mirrors `expire_pt_packages.py` shape verbatim. Emits `mark_no_show_bookings_complete count=N` structlog INFO AFTER commit returns.
- **WorkerSettings wiring** at `apps/backend/app/workers/__init__.py` — imported the new function, appended to `functions` list (4th entry), appended `cron(mark_no_show_bookings, hour=20, minute=10, unique=True, keep_result=60)` at the END of `cron_jobs` list. Cron-resolution invariant in `on_startup` stays green (existing test_worker_cron_resolution.py 4/4 passed without modification — it reflectively reads both lists).
- **`scripts/run_no_show_cron_once.py`** operator one-shot runner with TM-29-02 DATABASE_URL substring guard ('localhost' / 'postgres:5432'), REG-29-04 eager-imports for 5 modules (auth, bookings, clients, schedule, trainers), and TM-29-03 INTENTIONALLY OMITTED — documented in module docstring + inline.
- **3 integration tests** at `apps/backend/tests/integration/bookings/test_no_show_cron.py`:
  - `test_no_show_cron_marks_overdue_and_emits_audit` — happy path with 3-row fixture (overdue / future / completed) + payload-shape assertion (set-equality on keys per INFRA-25).
  - `test_no_show_cron_idempotent_second_run_zero` — 2nd helper call returns 0, only 1 audit row exists.
  - `test_no_show_cron_worker_e2e_via_sessionmaker_emits_summary_log` — full worker path with savepoint-aware sessionmaker shim + structlog capture of the summary log line.

## Task Commits

Each task was committed atomically (no per-task TDD red/green; the helper-then-test ordering was sufficient because the inherited make_confirmed_booking factory from Wave 2 made the seed path trivial):

1. **Task 1: Alembic 0020 + BookingNotification ORM** — `6d44097` (feat)
2. **Task 2: _mark_no_show_bookings helper + worker + WorkerSettings wiring** — `4b9623b` (feat)
3. **Task 3: scripts/run_no_show_cron_once.py operator runner** — `e91420d` (feat)
4. **Task 4: Integration tests + UUID-string audit emit fix + conftest negative-offset contract widening** — `f8f692d` (test)

**Plan metadata commit:** appended after this SUMMARY file is written.

## Files Created/Modified

- `apps/backend/alembic/versions/0020_booking_notifications.py` — NEW (Task 1). Mirror of `0010_notifications.py` with D-39-13 + D-39-03 deviations applied; `down_revision = "0019_pt_sessions_booking_id"` verified against the file head.
- `apps/backend/app/modules/bookings/models.py` — MODIFIED (Task 1). Added `UniqueConstraint` to the SQLAlchemy import block; appended `BookingNotification` ORM class with constraints letter-for-letter matching migration 0020.
- `apps/backend/app/modules/bookings/service.py` — MODIFIED (Tasks 2 + 4). Appended `_mark_no_show_bookings` SVC001-exempt helper between the existing Phase 39 NOTIFY-03/04 DM dispatch helpers and the Phase 37 `complete_booking` Protocol slot body. UUID arguments to `audit.emit(...)` are stringified at the callsite — see Deviations § for the fix rationale.
- `apps/backend/app/workers/scheduled/mark_no_show_bookings.py` — NEW (Task 2). Mirror of `expire_pt_packages.py` with swapped names + 23:10-MSK note in the module docstring.
- `apps/backend/app/workers/__init__.py` — MODIFIED (Task 2). Imported the new worker; appended to `functions` and `cron_jobs` lists at the END (plan 39-04 will insert `send_booking_reminders` BEFORE these entries per D-39-16).
- `apps/backend/scripts/run_no_show_cron_once.py` — NEW (Task 3). Operator one-shot runner with TM-29-02 KEPT + TM-29-03 OMITTED + REG-29-04 5-module eager-imports.
- `apps/backend/tests/integration/bookings/conftest.py` — MODIFIED (Task 4). `make_future_slot` docstring widened to document the negative-`start_offset` contract; factory body unchanged (the direct ORM insert already supported any timedelta — the change is contract-level only, no behavior change for existing callers).
- `apps/backend/tests/integration/bookings/test_no_show_cron.py` — NEW (Task 4). 3 tests + autouse logger-cache reset fixture (covers BOTH the worker module's `_log` and `bookings.service._log` so capture_logs() observes both).
- `.planning/phases/39-notifications-cron/39-03-SUMMARY.md` — this file.

## Cron Insertion Point Convention for Plan 39-04

Plan 39-04 needs to insert two things into `apps/backend/app/workers/__init__.py`:

1. **functions list** (currently 4 entries): `[expire_memberships, send_expiring_notifications, expire_pt_packages, mark_no_show_bookings]`. Insert `send_booking_reminders` BEFORE `mark_no_show_bookings` per D-39-16 final order: `[..., expire_pt_packages, send_booking_reminders, mark_no_show_bookings]`.
2. **cron_jobs list** (currently 4 entries with hours/minutes locked at 03:05, 03:15, 03:25, 20:10). Insert `cron(send_booking_reminders, hour=3, minute=35, unique=True, keep_result=60)` BEFORE the `mark_no_show_bookings` cron entry, producing the final order:
   - `cron(expire_memberships, ..., hour=3, minute=5)`
   - `cron(send_expiring_notifications, ..., hour=3, minute=15)`
   - `cron(expire_pt_packages, ..., hour=3, minute=25)`
   - `cron(send_booking_reminders, ..., hour=3, minute=35)` ← NEW (plan 39-04)
   - `cron(mark_no_show_bookings, ..., hour=20, minute=10)`

The `cron_jobs` list comment block above the `mark_no_show_bookings` entry already documents this final ordering for the 39-04 executor.

`BookingNotification` ORM is importable as `from app.modules.bookings.models import BookingNotification`; plan 39-04 will INSERT one row per successful reminder DM and rely on the `uq_booking_notifications_booking_kind` UNIQUE for idempotency.

## SVC001 Walker Compliance

The new `_mark_no_show_bookings` def line carries `# noqa: SVC001 caller-owns-txn` per the established Phase 30 / Phase 33 pattern. Verified GREEN by `tests/unit/test_service_commit_gate.py` (7/7 passed). The marker documents that the function intentionally does NOT call `await session.commit()` — the worker function does (D-39-06 single-session, caller-owns-txn).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 — Bug] audit.emit must string-cast UUIDs for JSONB serialization**
- **Found during:** Task 2 implementation (when reading the existing booking_cancelled emit at bookings/service.py:709-713 to mirror the style).
- **Issue:** The plan's `<action>` STEP A step 5 for Task 2 said: "UUIDs are passed raw (per D-39-14 reconciliation — Pydantic v2 coerces)." This is true for the Pydantic schema validation step (`BookingNoShowPayload.model_validate(payload)`), but `audit.emit` (apps/backend/app/core/audit.py:296) then writes the kwargs dict DIRECTLY into the JSONB column via `AuditLog(payload=payload)`. Raw UUID objects are not JSON-serializable — `json.dumps({'x': uuid4()})` raises `TypeError: Object of type UUID is not JSON serializable`. The actual Phase 38 idiom at bookings/service.py:709-713 (and Phase 33's pt_package emits) string-casts every UUID.
- **Fix:** Pass `booking_id=str(c.id)`, `slot_id=str(c.slot_id)`, `client_id=str(c.client_id)` to `audit.emit(...)`. `resource_id` stays as the raw UUID because it's a typed PgUUID FK column on AuditLog, NOT in the JSONB payload. Pydantic schema still accepts both str + UUID per D-39-14 (verified: `BookingNoShowPayload.model_validate({'booking_id': str(uuid4()), ...})` works AND `BookingNoShowPayload.model_validate({'booking_id': uuid4(), ...})` works).
- **Files modified:** `apps/backend/app/modules/bookings/service.py` (helper body + inline comment block citing Pitfall 13 / D-38-17).
- **Verification:** 3 integration tests in `test_no_show_cron.py` pass with the JSONB row visible in the SQL trace: `audit_log payload = '{"booking_id": "...", "slot_id": "...", "client_id": "...", "no_show_at": "2026-05-18T...+03:00"}'`. Payload-keys set-equality assertion (extra='forbid') confirms the locked shape.
- **Committed in:** `f8f692d` (Task 4 commit). The fix landed in Task 4 commit because it was discovered while writing the integration test that exercises the JSONB write path end-to-end; the bug would have surfaced as a runtime TypeError at the audit.emit callsite during the first test run otherwise.

**2. [Documentation note — NOT a fix] Live alembic upgrade/downgrade cycle deferred to operator**
- **Found during:** Task 1 verification.
- **Issue:** Plan §Task 1 <verify> automated gate includes a conditional live-DB cycle: `if [ -n "$DATABASE_URL" ]; then ... uv run alembic upgrade head && downgrade -1 && upgrade head; fi`. DATABASE_URL is unset in the worktree-agent environment, so the cycle was skipped at automated-verify time.
- **Decision:** Acceptable per the plan's `<manual>` block which explicitly addresses this scenario: "the live-DB alembic cycle below MUST be run against a localhost Postgres before Phase 40 milestone verification (VER-07 / SC2 require it). ... If DATABASE_URL was set during the <automated> gate above, the cycle already ran — record that in the SUMMARY and skip the manual repeat." DATABASE_URL was NOT set, so the operator manual repeat is required at Phase 40 milestone verification time.
- **Files modified:** none.
- **Verification:** Migration text static-checked via ruff + ORM-shape smoke test (`assert BookingNotification.__tablename__ == 'booking_notifications'`; column set verified; UNIQUE constraint name verified; FK ondelete='RESTRICT' verified). The migration body mirrors `0010_notifications.py` letter-for-letter except for the three documented deviations (no telegram_chat_id; ondelete=RESTRICT; CHECK kind single-element), so the live-cycle confidence is anchored to that analog.
- **Committed in:** N/A (documentation deferral, not a code fix). Recorded here so the operator running Phase 40 VER-07 knows the live alembic cycle still needs a manual run.

### Auth Gates

None — Phase 39 plan 39-03 is DB-only (no Telegram, no external service auth). The TM-29-02 guard on `scripts/run_no_show_cron_once.py` is a runtime safety gate (refuses to run against non-localhost DATABASE_URL), not an auth gate that requires operator credentials.

---

**Total deviations:** 2 (1 auto-fixed Rule 1 bug + 1 documentation-only operator deferral).
**Impact on plan:** Zero behavior or contract drift. The Rule 1 fix is a JSONB-serialization correctness requirement that the plan text didn't account for; the operator deferral is explicitly authorized by the plan's `<manual>` block.

## Issues Encountered

- **JSONB UUID serialization gap (see Deviation #1):** The plan text and CONTEXT.md D-39-14 both correctly state that Pydantic v2 coerces raw UUIDs in the schema validation step. Neither anchor noted that `audit.emit` writes the kwargs dict directly into the JSONB column AFTER validation — bypassing the validated Pydantic instance. Future cron-emitter plans should always inspect `audit.emit`'s implementation (apps/backend/app/core/audit.py:286-298) before assuming a payload type-coercion contract.
- **`# noqa: TABLE_REF cross-module SQL` ruff warning:** ruff emits a benign warning ("Invalid `# noqa` directive ... expected a comma-separated list of codes") on this project-specific marker because `TABLE_REF` is not a real ruff rule code. The marker is grep-discoverable for the import-linter conversation but bypasses ruff's rule registry. Identical pre-existing warnings exist at `apps/backend/app/modules/bookings/repository.py:127` and `apps/backend/app/modules/schedule/service.py:430` from earlier Phase 38 work — the pattern is established. ruff treats it as a warning, not an error; `ruff check` exits 0 / "All checks passed!".

## User Setup Required

**Operator action required at Phase 40 VER-07 milestone verification time** (deferred from Task 1 per plan `<manual>` authorization):

```bash
cd apps/backend
DATABASE_URL=postgresql+asyncpg://<localhost-creds> uv run alembic upgrade head
DATABASE_URL=postgresql+asyncpg://<localhost-creds> uv run alembic downgrade -1
DATABASE_URL=postgresql+asyncpg://<localhost-creds> uv run alembic upgrade head
```

Expected: each command exits 0; final state leaves the DB at head with the `booking_notifications` table present. The `alembic check` autogenerate-diff command (if configured by the project — check `apps/backend/CLAUDE.md` for the project's idiom) should report no drift.

No other operator setup required — `mark_no_show_bookings` is a scheduled cron with no env-var or credential dependency beyond the DB.

## Next Phase Readiness

- **Plan 39-04 (24h reminder cron)** can proceed. It will:
  1. Import `BookingNotification` from `app.modules.bookings.models` (now exists).
  2. Add `_send_booking_reminders(session_factory, *, bot, sender, notifications_module)` to `bookings/service.py` (multi-session per D-39-06 pattern b).
  3. Create `app/workers/scheduled/send_booking_reminders.py` (multi-session worker, mirrors `send_expiring_notifications.py`).
  4. INSERT `send_booking_reminders` import + functions entry + cron entry BEFORE the `mark_no_show_bookings` entries in `app/workers/__init__.py` per D-39-16 final order — see § Cron Insertion Point Convention above for exact positions.
  5. Add `scripts/run_booking_reminders_once.py` (mirror of `run_expiring_cron_once.py` INCLUDING TM-29-03 because reminder cron dispatches DMs).
  6. Add 4 integration tests covering the happy-path send + idempotency + 403-blocked skip + unlinked-client skip.
- The `BookingNoShowPayload` audit emit pattern (with string-cast UUIDs) is the canonical template for any future booking-domain cron emit Plan 39-04 might add (though currently the reminder cron does NOT emit audit — the `booking_notifications` row IS the audit per D-39-14).
- The `_reset_no_show_worker_logger_cache` autouse-fixture pattern (resetting BOTH the worker module's `_log` AND `bookings.service._log`) is the established template for any future cron-test that asserts on module-level structlog events from the bookings domain.

## Verification Evidence

Captured during this session:

```
=== RUFF (8 surfaces: alembic/, bookings/models.py + service.py, workers/__init__.py + scheduled/mark_no_show_bookings.py, scripts/, tests/integration/bookings/) ===
All checks passed!
(only the pre-existing TABLE_REF noqa warning shared with bookings/repository.py:127 — non-blocking)

=== MYPY --strict (5 source files) ===
Success: no issues found in 5 source files

=== LINT-IMPORTS ===
Analyzed 120 files, 330 dependencies.
core must not import modules KEPT
modules cannot import each other KEPT
integrations must not import modules KEPT
Contracts: 3 kept, 0 broken.

=== NEW TESTS (test_no_show_cron.py) ===
3 passed in 0.54s

=== FULL BOOKINGS REGRESSION + UNIT GATES ===
tests/integration/bookings/ + test_service_commit_gate.py + test_worker_cron_resolution.py
61 passed in 7.15s

=== DM-SIDE REGRESSION (Wave-2 surfaces unchanged) ===
tests/integration/bookings/test_cancel_sends_dm.py + test_create_sends_dm.py + tests/integration/schedule/
38 passed in 4.77s

=== Plan verification grep gates ===
telegram_chat_id occurrences in bookings/models.py:    1 (docstring "NO telegram_chat_id" anti-mention — column verified absent via ORM smoke)
FOR UPDATE OF b in bookings/service.py:                3 (docstring + SQL string + comment)
mark_no_show_bookings in workers/__init__.py:          3 (import + functions entry + cron_jobs entry)
audit.emit literal "booking_no_show":                  1 (INFRA-11 AST gate satisfied)
TM-29-03 OMITTED docstring note:                       2 (module docstring + inline comment)

=== TM-29-02 guard (non-local DATABASE_URL exits 1) ===
DATABASE_URL=postgresql+asyncpg://u:p@example.com:5432/x uv run python -m scripts.run_no_show_cron_once
> ERROR: run_no_show_cron_once refuses to run against a non-local DATABASE_URL (TM-29-02).
> EXIT=1

=== WorkerSettings registration smoke ===
mark_no_show_bookings registered at hour=20, minute=10, unique=True, keep_result_s=60
Cron-resolution invariant: {c.coroutine.__name__ for c in cron_jobs} ⊆ {f.__name__ for f in functions} — TRUE

=== BookingNoShowPayload extra='forbid' verified ===
audit_log payload = '{"booking_id": "...", "slot_id": "...", "client_id": "...", "no_show_at": "2026-05-18T...+03:00"}'
set(payload.keys()) == {"booking_id", "slot_id", "client_id", "no_show_at"} — TRUE
```

## Self-Check: PASSED

**Files verified present (`[ -f <path> ] && echo FOUND` per file):**
- `apps/backend/alembic/versions/0020_booking_notifications.py` FOUND
- `apps/backend/app/workers/scheduled/mark_no_show_bookings.py` FOUND
- `apps/backend/scripts/run_no_show_cron_once.py` FOUND
- `apps/backend/tests/integration/bookings/test_no_show_cron.py` FOUND
- `.planning/phases/39-notifications-cron/39-03-SUMMARY.md` FOUND
- `apps/backend/app/modules/bookings/models.py` FOUND (modified)
- `apps/backend/app/modules/bookings/service.py` FOUND (modified)
- `apps/backend/app/workers/__init__.py` FOUND (modified)
- `apps/backend/tests/integration/bookings/conftest.py` FOUND (modified)

**Commits verified present in `git log --oneline`:**
- `6d44097` (Task 1 — feat: Alembic 0020 + ORM) FOUND
- `4b9623b` (Task 2 — feat: helper + worker + wiring) FOUND
- `e91420d` (Task 3 — feat: operator runner) FOUND
- `f8f692d` (Task 4 — test: integration tests + UUID-string emit fix) FOUND

---
*Phase: 39-notifications-cron*
*Completed: 2026-05-18*
