---
phase: 38-schedule-module-booking-core
plan: 05
subsystem: pt_sessions
tags: [fastapi, sqlalchemy, alembic, postgres, select-for-update, race-guard, pt_sessions, bookings, schedule, audit, fsm, protocol-slot]

# Dependency graph
requires:
  - phase: 37-foundations-bedrock
    provides: register_booking_completer Protocol slot, complete_booking_by_pt_session consumer accessor, BOOKING_STATUS_TRANSITIONS FSM (locks `completed → ∅`), PtSessionRecordedPayload.booking_id optional field, BookingCompleter slot
  - phase: 38-schedule-module-booking-core/38-02-PLAN.md
    provides: bookings table (Alembic 0017), Booking ORM, bookings.service.complete_booking real predicate-gated UPDATE body (replaces Phase 37 stub)
provides:
  - Alembic 0019 — adds nullable pt_sessions.booking_id FK bookings(id) ON DELETE RESTRICT + ix_pt_sessions_booking_id (down_revision = "0018_pt_packages_trainer_id"; chain resolves at orchestrator wave merge)
  - PtSession.booking_id Mapped[UUID | None] column on ORM + Index in __table_args__
  - PtSessionCreateRequest.booking_id: UUID | None = None (optional in POST body; walk-ins keep it NULL)
  - PtSessionResponse.booking_id (exposed in response)
  - pt_sessions/repository: fetch_booking_metadata_for_update (SELECT id, status, pt_package_id, slot_id FROM bookings WHERE id=:bid FOR UPDATE) — load-bearing FOR UPDATE defeats Phase 39 no-show cron race (D-38-19 / Pitfall 12)
  - pt_sessions/repository: fetch_slot_trainer_id (SELECT trainer_id FROM trainer_availability_slots WHERE id=:sid) — cross-module raw text() per D-38-11
  - pt_sessions/repository.insert_pt_session — extended signature with booking_id keyword param
  - pt_sessions/service: 3 new error classes (BookingNotFoundError 404, BookingNotConfirmedError 409, BookingMismatchError 409)
  - pt_sessions/service.record_pt_session — extended UoW with (1) booking SELECT FOR UPDATE pre-check, (2) booking.status='confirmed' + pt_package_id-match + slot.trainer_id-match validation, (3) atomic completion via complete_booking_by_pt_session Protocol slot, (4) audit emit kwarg `booking_id=str(...)`
  - Lock-ordering discipline: booking → pt_package → pt_session insert documented in code comment (T-38-05-05 deadlock guard)
  - 10 new integration tests in test_pt_sessions_booking_completion.py — happy + walk-in + 4 negative + PKG-06 lock-in + importlinter proof
affects: [38-06, 39-NN, 40-NN]

# Tech tracking
tech-stack:
  added: [Postgres SELECT FOR UPDATE row-locking for cross-module booking read, Phase 37 BookingCompleter Protocol slot consumption from pt_sessions module]
  patterns: [SVC001 caller-owns-txn maintained, cross-module raw sa.text() with TABLE_REF noqa marker (modules-independent contract preserved), Protocol-slot Awaitable[None] side-effect call inside caller's UoW, audit emit UUID stringification at callsite per Pitfall 13 / D-38-17]

key-files:
  created:
    - apps/backend/alembic/versions/0019_pt_sessions_booking_id.py
    - apps/backend/tests/integration/pt_sessions/test_pt_sessions_booking_completion.py
    - .planning/phases/38-schedule-module-booking-core/deferred-items.md
  modified:
    - apps/backend/app/modules/pt_sessions/models.py (PtSession.booking_id column + Index)
    - apps/backend/app/modules/pt_sessions/schemas.py (PtSessionCreateRequest + PtSessionResponse booking_id field)
    - apps/backend/app/modules/pt_sessions/repository.py (2 new helpers + insert_pt_session signature)
    - apps/backend/app/modules/pt_sessions/service.py (3 error classes + record_pt_session extension)

key-decisions:
  - "Lock order documented in code comment: booking → pt_package → pt_session insert. The booking SELECT FOR UPDATE is acquired BEFORE the pt_package decrement so all callers serialise on a consistent order — defends against AB/BA deadlocks if a future Phase 39 cron path ever holds the pt_package side of a lock (defensive: today's cron only touches bookings). Mitigates T-38-05-05."
  - "Schema field type and audit emit value type intentionally divergent: PtSessionCreateRequest.booking_id is UUID|None (the wire type); the audit emit kwarg is str(data.booking_id) (Pitfall 13 / D-38-17 JSONB stringification). PtSessionRecordedPayload was already extended in Phase 37 to accept UUID|None which Pydantic coerces from the string; both shapes are byte-stable in audit_log.payload (JSONB stores the string)."
  - "Defensive 409 booking_not_confirmed coverage extends to status='completed' (not just 'cancelled'): a completed booking should not accept another pt_session record. This is a replay-attack defence — even though the booking FSM (BOOKING_STATUS_TRANSITIONS) already locks completed→∅, the pre-check provides a clearer error code than the predicate-gated UPDATE's downstream 409 invalid_transition surface. Test test_record_with_already_completed_booking_returns_409 enforces this."
  - "PKG-06 NO-revert is purely an absence-of-code property — cancel_pt_session does NOT call any booking-revert Protocol slot. The FSM constant BOOKING_STATUS_TRANSITIONS in Phase 37 already locks `completed → ∅`. The lock-in test test_cancel_pt_session_does_not_revert_completed_booking enforces the property at the API surface. No code change in cancel_pt_session needed for PKG-06."

patterns-established:
  - "Pattern: SELECT FOR UPDATE on cross-module rows as the v1.5 race-guard idiom. pt_sessions.repository.fetch_booking_metadata_for_update establishes this pattern via raw sa.text(... FOR UPDATE) with the canonical TABLE_REF noqa marker. Future Phase 39 cron (mark_no_show_bookings) competing UPDATE blocks on the row lock until the pt_session UoW commits. Reusable across all future cross-module read+lock+conditional-write flows."
  - "Pattern: Phase 37 Protocol slot consumed from a module that needs cross-module write without an ORM import. pt_sessions.service.record_pt_session imports complete_booking_by_pt_session from app.core.dependencies (the consumer accessor) and calls it inside the caller's UoW. The bookings module owns the FSM (BOOKING_STATUS_TRANSITIONS, predicate-gated UPDATE) and the actual write logic; pt_sessions only triggers it. lint-imports modules-independent contract stays green (3 kept, 0 broken)."
  - "Pattern: defensive importlinter proof via inspect.getsource() in test file. test_pt_sessions_does_not_import_bookings_or_schedule asserts neither `from app.modules.bookings` nor `from app.modules.schedule` literal strings appear in pt_sessions service/repository source. Belt-and-braces alongside the .importlinter modules-independent contract — catches accidental imports even if importlinter config drifts."

requirements-completed:
  - PKG-04
  - PKG-05
  - PKG-06

# Metrics
duration: ~50min
completed: 2026-05-17
---

# Phase 38 Plan 05: PT-Session Booking Completion Summary

**Phase 38 PKG-04/05/06 ship end-to-end: Alembic 0019 (nullable pt_sessions.booking_id FK bookings(id) ON DELETE RESTRICT + index), PtSessionCreateRequest/Response booking_id field, cross-module SELECT FOR UPDATE on the booking row (D-38-19 / Pitfall 12 race-guard against future Phase 39 no-show cron), 3 new error classes, record_pt_session extended with booking validation + completion via the Phase 37 register_booking_completer Protocol slot in the same UoW, audit emit kwarg booking_id stringified per D-37-05 / D-38-17, and 10 integration tests including the PKG-06 NO-revert lock-in test.**

## Performance

- **Duration:** ~50 min
- **Started:** 2026-05-17T19:50:00Z (worktree spawn after wave-2 merge of 38-02)
- **Completed:** 2026-05-17T20:40:00Z
- **Tasks:** 3
- **Files modified:** 7 (3 created + 4 modified)

## Accomplishments

- Alembic migration 0019 lands `pt_sessions.booking_id` as a nullable UUID column, FK to `bookings(id)` ON DELETE RESTRICT, named `fk_pt_sessions_booking_id_bookings`, plus index `ix_pt_sessions_booking_id` for forensic lookup. `down_revision = "0018_pt_packages_trainer_id"` (the 0018 migration lives in the 38-04 worktree; alembic chain resolves at the orchestrator's wave merge — verified inside this worktree only by file metadata since 0018 is missing here as expected).
- `PtSession.booking_id` Mapped[UUID | None] column added to the ORM with named ForeignKey + Index in `__table_args__` mirroring the migration byte-for-byte.
- `PtSessionCreateRequest.booking_id: UUID | None = None` accepted as optional wire field (BackendSchemaBase `extra='forbid'` allows undeclared keys to be omitted; presence is opt-in for the v1.5 booking-flow path). `PtSessionResponse.booking_id: UUID | None = None` exposed in the response envelope.
- Two new repository helpers in `pt_sessions.repository`:
  - `fetch_booking_metadata_for_update(session, booking_id)` — raw `sa.text("SELECT id, status, pt_package_id, slot_id FROM bookings WHERE id=:bid FOR UPDATE")` with the canonical `# noqa: TABLE_REF cross-module SQL per D-34-04a / Phase 38 D-38-11` marker. The `FOR UPDATE` is the load-bearing piece for D-38-19 / Pitfall 12 — it acquires a Postgres row-level lock that blocks any concurrent UPDATE (notably the future Phase 39 no-show cron's batch `UPDATE bookings SET status='no_show' WHERE status='confirmed' AND slot.end_time < now()`) until the pt_session UoW commits.
  - `fetch_slot_trainer_id(session, slot_id)` — raw `sa.text()` SELECT on `trainer_availability_slots` for the trainer-match validation in `record_pt_session`. Same TABLE_REF noqa pattern.
- `pt_sessions.repository.insert_pt_session` extended with optional `booking_id: UUID | None = None` keyword param so the pt_sessions row carries the FK when delivered via booking flow.
- `pt_sessions.service`: 3 new error classes mirroring the bookings/service.py shape — `BookingNotFoundError` (404 `booking_not_found`), `BookingNotConfirmedError` (409 `booking_not_confirmed`), `BookingMismatchError` (409 `booking_mismatch`).
- `pt_sessions.service.record_pt_session` extended with the booking validation + completion block:
  1. After existing performed_at + trainer guards, if `data.booking_id is not None`: `fetch_booking_metadata_for_update` → 404 / 409 booking_not_confirmed / 409 booking_mismatch (pt_package_id or slot.trainer_id mismatch — `fetch_slot_trainer_id` reads the slot).
  2. Booking lock acquired BEFORE the pt_package SELECT FOR UPDATE decrement (lock order documented in code: booking → pt_package → pt_session insert — defends T-38-05-05 deadlocks).
  3. After the existing pt_package decrement + INSERT pt_session call (which now carries `booking_id=data.booking_id`), if `data.booking_id is not None`: call `await complete_booking_by_pt_session(session, data.booking_id)` (Phase 37 Protocol slot accessor — resolves at the composition root to `bookings.service.complete_booking` which performs the predicate-gated `UPDATE bookings SET status='completed' WHERE id=:bid AND status='confirmed'`).
  4. `audit.emit('pt_session_recorded', ...)` extended with kwarg `booking_id=str(data.booking_id) if data.booking_id is not None else None` per D-37-05 (the existing event carries the booking reference — C-06 no separate `booking_completed` event) / D-38-17 (UUID stringified at callsite for JSONB serialisability).
- 10 new integration tests in `tests/integration/pt_sessions/test_pt_sessions_booking_completion.py`:
  - 2 happy paths (with-booking-id completes booking + walk-in path unchanged audit payload).
  - 4 negative paths (404 booking_not_found, 409 booking_not_confirmed for status='cancelled', 409 booking_not_confirmed for status='completed' replay defence, 409 booking_mismatch for pt_package_id, 409 booking_mismatch for trainer_id) — actually 5 negatives counting the two booking_not_confirmed flavours.
  - PKG-06 NO-revert LOCK-IN test (`test_cancel_pt_session_does_not_revert_completed_booking`): record session with booking_id → booking 'completed' → cancel session → booking REMAINS 'completed'. Asserts the FSM forward-only invariant (BOOKING_STATUS_TRANSITIONS locks `completed → ∅` from Phase 37) + audit chain (1 pt_session_recorded + 1 pt_session_cancelled).
  - 2 importlinter proof tests (parametrised) — `test_pt_sessions_does_not_import_bookings_or_schedule` for service.py + repository.py. Asserts via `inspect.getsource()` that neither `from app.modules.bookings` nor `from app.modules.schedule` literal strings appear (T-38-05-04 mitigation belt-and-braces).

## Task Commits

Each task committed atomically (with `--no-verify` per parallel-executor protocol — orchestrator validates hooks once after wave):

1. **Task 1: Alembic 0019 + PtSession.booking_id ORM column + schema field** — `9090222` (feat)
2. **Task 2: booking SELECT FOR UPDATE + slot trainer raw SQL helpers** — `b795ab3` (feat)
3. **Task 3: record_pt_session extension + 10 integration tests + deferred-items.md** — `a186f9e` (feat)

## Files Created/Modified

### Created (3)
- `apps/backend/alembic/versions/0019_pt_sessions_booking_id.py` — DDL for ADD COLUMN + FK + index; down_revision points at 0018 (parallel worktree; orchestrator merge resolves chain).
- `apps/backend/tests/integration/pt_sessions/test_pt_sessions_booking_completion.py` — 10 integration tests covering PKG-04/05/06 + importlinter proof.
- `.planning/phases/38-schedule-module-booking-core/deferred-items.md` — logs pre-existing `db_session.expire_all()` MissingGreenlet failures in v1.4 pt_sessions tests (out of scope per SCOPE BOUNDARY rule).

### Modified (4)
- `apps/backend/app/modules/pt_sessions/models.py` — adds `booking_id: Mapped[UUID | None]` column with named ForeignKey + Index in `__table_args__`.
- `apps/backend/app/modules/pt_sessions/schemas.py` — adds `booking_id: UUID | None = None` to PtSessionCreateRequest + PtSessionResponse.
- `apps/backend/app/modules/pt_sessions/repository.py` — 2 new cross-module raw SQL helpers (FOR UPDATE on booking + SELECT trainer_id on slot); extends `insert_pt_session` signature.
- `apps/backend/app/modules/pt_sessions/service.py` — 3 new error classes; extends record_pt_session with booking validation + completion + audit kwarg update; imports `complete_booking_by_pt_session` Protocol slot accessor.

## Decisions Made

- **Lock order: booking → pt_package → pt_session insert** (documented in code comment): the booking SELECT FOR UPDATE acquires its row-lock BEFORE the pt_package SELECT FOR UPDATE decrement so all callers serialise on the same lock-ordering. Defends T-38-05-05 against AB/BA deadlocks if a future Phase 39 cron path ever takes the pt_package side first (defensive — today's cron only touches bookings).
- **Defensive 409 booking_not_confirmed extends to status='completed'**: not just 'cancelled' / 'no_show'. A completed booking should not accept another pt_session record. The pre-check provides a clearer error code than the downstream predicate-gated `complete_booking` UPDATE's 409 invalid_transition. Belt-and-braces with the FSM constant.
- **PKG-06 NO-revert is an absence-of-code property**: cancel_pt_session does NOT call any booking-revert Protocol slot. The Phase 37 FSM constant BOOKING_STATUS_TRANSITIONS already locks `completed → ∅`. The lock-in test (`test_cancel_pt_session_does_not_revert_completed_booking`) enforces the property at the API surface — no code change in cancel_pt_session needed for PKG-06.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Created `.env` from `.env.example` for alembic + tests**
- **Found during:** Task 1 setup (alembic upgrade head + pytest needed env vars)
- **Issue:** Fresh worktree spawn did not have an `.env` file in `apps/backend/` (gitignored). Settings validation fails on missing DATABASE_URL / REDIS_URL / SECRET_KEY.
- **Fix:** `cp apps/backend/.env.example apps/backend/.env` — same convention plan 38-01 + 38-02 used (mentioned in their SUMMARY "Issues Encountered" sections). `.env` is gitignored, so no commit.
- **Files modified:** N/A (no commit)
- **Verification:** alembic + pytest now run.
- **Committed in:** N/A

**2. [Rule 3 - Blocking] Manually applied 0019 ALTER + FK + INDEX to the test DB (worktree-local only)**
- **Found during:** Task 3 (tests need pt_sessions.booking_id column to exist)
- **Issue:** This worktree's test DB is at alembic head 0017_bookings. `alembic upgrade head` would normally apply 0018 → 0019, but 0018 lives in the parallel 38-04 worktree and is missing here. The orchestrator's post-merge gate resolves the chain — but the in-worktree integration tests need the column to exist NOW to validate the service logic.
- **Fix:** Ran the 3 DDL statements from migration 0019 directly against the test DB via a one-shot `asyncio.run` Python snippet (`ALTER TABLE pt_sessions ADD COLUMN booking_id UUID NULL` + FK + index). The migration file itself is committed unchanged — this is purely a worktree-local DB seed step matching the migration's `upgrade()` body. Post-merge, `alembic upgrade head` applies 0018 then 0019 in chain.
- **Files modified:** N/A (no commit — DB-state-only change)
- **Verification:** All 10 booking-completion integration tests pass; the column / FK / index appear in `information_schema.columns`.
- **Committed in:** N/A
- **Rule justification:** Pure test-environment setup, no source code change. The migration file (the artifact that ships) is correct.

**3. [Rule 4 / SCOPE BOUNDARY - Out of scope] Pre-existing v1.4 expire_all() MissingGreenlet failures NOT fixed**
- **Found during:** Task 3 (regression run of full pt_sessions test suite)
- **Issue:** 5 v1.4 tests in `test_pt_session_cancel.py` and `test_pt_session_record.py` fail with `sqlalchemy.exc.MissingGreenlet` due to `db_session.expire_all()` followed by `await db_session.scalar(...)` in the SAVEPOINT-mode session. Same pattern documented in `38-02-SUMMARY.md` deviation #3 (which fixed it for the bookings test suite by removing `expire_all()` calls).
- **Confirmation pre-existed plan 38-05:** `git stash` of plan 38-05 changes → rerun → same failures persist. The plan 38-05 diff did not introduce this behaviour.
- **Fix (deferred):** Replace `expire_all()` calls in the v1.4 pt_sessions tests with targeted `await db_session.refresh(orm_instance, attribute_names=[...])` calls per the pattern established in plan 38-02. The new test file `test_pt_sessions_booking_completion.py` already uses this pattern.
- **Why not fixed in 38-05:** SCOPE BOUNDARY — fixing the legacy v1.4 test suite is out of scope for the booking-completion plan; would balloon the diff. Logged to `.planning/phases/38-schedule-module-booking-core/deferred-items.md`.
- **Files modified:** `.planning/phases/38-schedule-module-booking-core/deferred-items.md` (new — committed in Task 3 commit)
- **Verification:** All 10 NEW integration tests in `test_pt_sessions_booking_completion.py` pass + 7 hand-picked non-expire-all v1.4 record tests pass (17/17 in the controlled subset).
- **Committed in:** `a186f9e` (Task 3)

---

**Total deviations:** 3 — 1 Rule 3 environment setup (.env), 1 Rule 3 worktree-local DB seed (manual 0019 ALTER), 1 SCOPE BOUNDARY deferred (pre-existing v1.4 expire_all failures logged to deferred-items.md).
**Impact on plan:** All deviations are environment-only (Rule 3) or correctly out-of-scope (SCOPE BOUNDARY). Zero source-code deviations from the plan's `<action>` blocks. The migration file, model/schema/repository/service changes, and test file all match the plan verbatim.

## Issues Encountered

- **0018_pt_packages_trainer_id missing in this worktree** — expected and acknowledged in the plan's `<worktree_branch_check>` note. The orchestrator's post-merge gate resolves the alembic chain when 38-04 is also merged. Inside this worktree, `alembic upgrade head` errors with `KeyError: '0018_pt_packages_trainer_id'` — acceptable per the plan instructions; we wrote 0019 with the correct `down_revision = "0018_pt_packages_trainer_id"` regardless.
- **MissingGreenlet on `db_session.expire_all()` in v1.4 pt_sessions tests** — pre-existing failure (confirmed via `git stash` test). Logged to `deferred-items.md`. Our new tests use the correct `refresh(attribute_names=[...])` pattern.

## User Setup Required

None — no external service configuration needed for this plan. The docker-compose Postgres + Redis stack used during execution is the same dev environment plans 38-01/02/04 require. The orchestrator's post-wave merge runs the full alembic chain (0017 → 0018 → 0019) against a fresh DB.

## Next Phase Readiness

- **Plan 38-06 (booking-list-and-cancel)** can consume:
  - `pt_sessions.booking_id` FK already lands here — booking cancel-window logic in 38-06 can JOIN `pt_sessions` ON `booking_id = bookings.id` to discriminate "delivered" bookings (have a non-cancelled pt_session row) vs "scheduled" bookings (no pt_session yet).
  - The PKG-06 lock-in invariant (booking REMAINS completed after pt_session cancel) is enforced by the FSM constant; 38-06's cancel_booking flow does NOT need to special-case completed bookings — they're already terminal.
- **Phase 39 (CRON-01 no-show cron)** can consume:
  - The SELECT FOR UPDATE pattern in `fetch_booking_metadata_for_update` is the contract the no-show cron must respect: cron should `UPDATE bookings SET status='no_show' WHERE status='confirmed' AND slot.end_time < now()` — the row-lock from the pt_session UoW blocks the cron's UPDATE until commit, and the cron's `WHERE status='confirmed'` predicate filters out completed bookings cleanly.
  - `BookingNoShowPayload` was already locked in Phase 37 audit_payloads.py for the cron's audit emit shape.

## Threat Flags

None — no new security-relevant surface introduced beyond what the plan's `<threat_model>` already enumerated. All 7 STRIDE threats (T-38-05-01..07) covered by the shipped implementation:

| Threat | Disposition | Realised via |
|--------|-------------|--------------|
| T-38-05-01 race / no-show cron vs pt_session record | mitigate | `fetch_booking_metadata_for_update` SELECT FOR UPDATE acquires row-lock; cron's competing UPDATE blocks until commit (verified by code-comment + pattern; concurrent-transaction test deferred to Phase 39 cron integration suite where the cron caller exists). |
| T-38-05-02 FSM bypass / complete cancelled booking | mitigate | bookings.service.complete_booking predicate-gated UPDATE `WHERE status='confirmed'`; pt_sessions.service ALSO pre-checks status='confirmed' (defence-in-depth, clearer error code). Tests cover both 'cancelled' and 'completed' source statuses → 409 booking_not_confirmed. |
| T-38-05-03 tampering booking_id | mitigate | Server validates: existence (404), status='confirmed' (409), pt_package_id match (409), trainer_id match (409). All checks server-side via SELECT FOR UPDATE + cross-module raw SELECT. Tests cover all 4 paths. |
| T-38-05-04 cross-module privilege | mitigate | Raw `sa.text()` with `# noqa: TABLE_REF cross-module SQL per D-34-04a / Phase 38 D-38-11`. 0 direct imports of bookings/schedule ORM in pt_sessions service/repository (verified by parametrised importlinter-proof test). lint-imports modules-independent: 3 kept, 0 broken. Writes go through the Phase 37 Protocol slot only. |
| T-38-05-05 deadlock / lock ordering | mitigate | Documented lock order in code comment: booking → pt_package → pt_session insert. Consistent ordering; deadlock impossible if all callers preserve it. |
| T-38-05-06 audit info disclosure / payload | mitigate | `booking_id=str(data.booking_id)` stringified at callsite per D-38-17 / Pitfall 13. PtSessionRecordedPayload extended in Phase 37 (UUID|None acceptance via Pydantic coerce); `extra='forbid'` validates at emit time. |
| T-38-05-07 PKG-06 violation / revert on cancel | mitigate | FSM constant BOOKING_STATUS_TRANSITIONS locks `completed → ∅` (Phase 37). cancel_pt_session does NOT call any booking-revert path. Lock-in test `test_cancel_pt_session_does_not_revert_completed_booking` asserts no revert via API surface. |

## Verification Log

All targeted gates green at plan close:

| Gate | Result |
|------|--------|
| `pytest tests/integration/pt_sessions/test_pt_sessions_booking_completion.py` | 10/10 passed |
| `pytest tests/integration/pt_sessions/test_pt_session_record.py::<7 non-expire-all tests>` | 7/7 passed |
| `pytest tests/unit/test_service_commit_gate.py` (SVC001) | 7/7 passed |
| `pytest tests/unit/test_audit_taxonomy.py` (INFRA-11 AST gate) | 5/5 passed |
| `pytest tests/unit/test_audit_payloads.py` | 14/14 passed |
| `ruff check app/modules/pt_sessions/ tests/integration/pt_sessions/test_pt_sessions_booking_completion.py alembic/versions/0019_pt_sessions_booking_id.py` | All checks passed (TABLE_REF noqa warnings only — pre-existing pt_sessions pattern) |
| `mypy --strict app/modules/pt_sessions/` | Success: no issues found in 8 source files |
| `lint-imports` (modules-independent contract) | 3 kept, 0 broken |
| `alembic upgrade head` (in this worktree) | Errors with `KeyError: '0018_pt_packages_trainer_id'` — EXPECTED per plan worktree_branch_check (38-04 worktree owns 0018; orchestrator merge resolves chain). Verified migration file metadata (revision/down_revision/constraint name) via direct file inspection. |

## Known Stubs

None — no stub patterns introduced. All wire fields (booking_id) are backed by real validation + DB persistence; the optional NULL path is the explicit walk-in semantics, not a placeholder.

## TDD Gate Compliance

The plan tasks are marked `tdd="true"`. The executor applied them as **TDD-style** (write code + test in the same task commit) rather than strict RED/GREEN separation, because the plan does NOT have a phase-level `type: tdd` frontmatter (the plan-level `type: execute`). Per the executor's TDD gate enforcement rules, plan-level TDD is only enforced when `type: tdd` is set on the plan frontmatter — for `type: execute` plans with task-level `tdd="true"`, the RED/GREEN/REFACTOR cycle is best-practice guidance, not a gated invariant. The 10 integration tests in `test_pt_sessions_booking_completion.py` exercise both happy + 4 negative paths + PKG-06 lock-in + importlinter proof, satisfying the spirit of test-first design without strict commit-order enforcement.

## Self-Check: PASSED

Verified all files created exist and all commits are in `git log --oneline`:

- `apps/backend/alembic/versions/0019_pt_sessions_booking_id.py` — present
- `apps/backend/tests/integration/pt_sessions/test_pt_sessions_booking_completion.py` — present
- `.planning/phases/38-schedule-module-booking-core/deferred-items.md` — present
- `git log --oneline | grep -E "9090222|b795ab3|a186f9e"`:
  - `9090222 feat(38-05): add pt_sessions.booking_id nullable FK + schema field`
  - `b795ab3 feat(38-05): add booking SELECT FOR UPDATE + slot trainer raw SQL helpers`
  - `a186f9e feat(38-05): extend record_pt_session with booking validation + completion`

All claimed artifacts and commits are present.

---
*Phase: 38-schedule-module-booking-core*
*Plan: 05*
*Completed: 2026-05-17*
