---
phase: 38-schedule-module-booking-core
plan: 02
subsystem: bookings
tags: [fastapi, sqlalchemy, alembic, postgres, partial-unique, race-guard, bookings, schedule, audit, rbac, idempotency, moscow-tz]

# Dependency graph
requires:
  - phase: 37-foundations-bedrock
    provides: BOOKING_STATUS_TRANSITIONS, SlotById Protocol slot, BookingCompleter Protocol slot, BookingCreatedPayload audit schema, BOOKINGS RBAC pairs, ActivePtPackageResolver Phase 33 slot
  - phase: 38-schedule-module-booking-core/38-01-PLAN.md
    provides: trainer_availability_slots table (Alembic 0016), TrainerAvailabilitySlot ORM model satisfying SlotById Protocol, real schedule.service.resolve_slot_by_id body, schedule slot status FSM enforcement (active → booked/cancelled)
provides:
  - bookings table (Alembic 0017) — TIMESTAMPTZ columns, status CHECK ('confirmed','cancelled','no_show','completed'), 4 NOT NULL FK columns (slot, client, pt_package, created_by_user) ON DELETE RESTRICT, named partial UNIQUE uq_bookings_slot_confirmed on (slot_id) WHERE status='confirmed' (BOOK-01 / C-02 / Pitfall 1)
  - Booking ORM model — UUIDPkMixin + TimestampMixin, no SoftDeleteMixin (D-38-04 mirror), no snapshot columns (D-38-08); __table_args__ mirrors migration 0017 byte-for-byte
  - bookings.repository — async helpers (get_booking_by_id, insert_booking, update_slot_status_predicate_gated cross-module raw text() UPDATE with TABLE_REF noqa marker per D-38-11)
  - bookings.schemas — BookingStatus StrEnum, BookingCreateRequest (3 required fields incl. pt_package_id per D-38-02), BookingResponse with full attribute set
  - bookings.router mounted at /api/v1/bookings — POST create with verbatim two-phase Redis claim+replay block from pt_sessions/router.py:116-157 (D-38-14 / Pitfall 14 / CR-02)
  - bookings.service.create_booking — 10-step atomic UoW (resolve slot → validate pt_package + Moscow-TZ validity window + trainer match → flip slot active→booked via cross-module raw UPDATE → INSERT booking → flush + IntegrityError race-translation → emit booking_created → commit)
  - bookings.service.complete_booking — Phase 37 stub body REPLACED with predicate-gated raw UPDATE (confirmed→completed) inside caller's UoW (D-38-13 / PKG-05 — pt_sessions.service.record_pt_session is the future caller in plan 38-05); 0-row → InvalidBookingTransitionError
  - 8 error classes (SlotNotFound, SlotNotAvailable, SlotAlreadyBooked, TrainerMismatch, PtPackageExhausted, PtPackageNotActive, PtPackageExpiredBeforeSlot, InvalidBookingTransition, BookingNotFound)
  - BOOK-TEST-01 race test against real Postgres via db_session_real_commit fixture (asyncio.gather + 2 distinct Idempotency-Keys → 1x201 + 1x409 slot_already_booked)
affects: [38-03, 38-04, 38-05, 39-NN, 40-NN]

# Tech tracking
tech-stack:
  added: [Postgres partial UNIQUE Index with postgresql_where on bookings.slot_id, IntegrityError constraint-name discriminator pattern for booking race translation, cross-module raw sa.text() UPDATE on trainer_availability_slots with TABLE_REF noqa marker]
  patterns: [SVC001 caller-owns-txn maintained, Moscow-TZ business-date comparison via .astimezone(MOSCOW_TZ).date() (Pitfall 18 / D-38-12), unified slot_already_booked vs slot_not_available discrimination via post-UPDATE refresh, idempotency-aware concurrent POSTs using DISTINCT Idempotency-Keys for race tests]

key-files:
  created:
    - apps/backend/alembic/versions/0017_bookings.py
    - apps/backend/app/modules/bookings/models.py
    - apps/backend/app/modules/bookings/repository.py
    - apps/backend/app/modules/bookings/schemas.py
    - apps/backend/app/modules/bookings/router.py
    - apps/backend/tests/integration/bookings/__init__.py
    - apps/backend/tests/integration/bookings/conftest.py
    - apps/backend/tests/integration/bookings/test_bookings_router_smoke.py
    - apps/backend/tests/integration/bookings/test_bookings_create.py
    - apps/backend/tests/integration/bookings/test_booking_race.py
  modified:
    - apps/backend/alembic/env.py (register app.modules.bookings.models for autogenerate)
    - apps/backend/app/api/v1/router.py (mount bookings_router at /bookings)
    - apps/backend/app/modules/bookings/service.py (full rewrite — real create_booking + complete_booking body replacing Phase 37 stubs)

key-decisions:
  - "Bookings router mounted in app/api/v1/router.py rather than literally in app/main.py per the existing v1 aggregator convention (deviation Rule 3 — schedule precedent set in plan 38-01). main.py already imports `from app.modules.bookings import service as bookings_service` for the Phase 37 register_booking_completer wiring, so the acceptance grep `from app.modules.bookings` in app/main.py is satisfied without further main.py edits."
  - "Unified race-loser code via post-UPDATE refresh discriminator: when bookings.repository.update_slot_status_predicate_gated returns 0 rows in create_booking Step 5, we refresh the slot ORM instance and surface SlotAlreadyBookedError when slot.status == 'booked' (someone else booked it) vs SlotNotAvailableError when status is 'cancelled' or other unbookable values. This matches BOOK-TEST-01 / D-38-15 expectation that the race-loser sees `slot_already_booked` consistently — the partial UNIQUE remains the defense-in-depth at Step 7 but the predicate-gated UPDATE row-lock is the primary race arbiter in our flow."
  - "Trainer-mismatch guard uses `getattr(pt_package, 'trainer_id', None)` because PtPackage.trainer_id is added by plan 38-04 (Alembic 0018); until then the column does not exist on the ActivePtPackage Protocol and the getattr safely short-circuits to the NULL='any trainer' branch per C-08. The TrainerMismatchError class is shipped now so plan 38-04 only needs to add the column + a test, not modify the orchestrator."
  - "Defensive `datetime.now(UTC)` request-time freshness check at create_booking entry — surfaces past-slot rejections as SlotNotAvailableError. The schedule service guarantees future-only at publish time (D-38-16) but clock advances between publish and book; this check is Rule 2 missing-critical (correctness) per the deviation rules."

patterns-established:
  - "Pattern: Cross-module raw sa.text() UPDATE in repository layer with `# noqa: TABLE_REF cross-module SQL per D-34-04a / Phase 38 D-38-11` marker — establishes the canonical bookings → schedule boundary crossing (NEVER a direct ORM import). Future modules (e.g., 38-05 pt_sessions → bookings) reuse this exact shape."
  - "Pattern: post-UPDATE refresh discriminator — when a cross-module predicate-gated raw UPDATE returns 0 rows in the service layer, refresh the ORM instance for the target table and use the actual current status to discriminate error codes (slot_already_booked vs slot_not_available). Solves the ORM identity-map cache invalidation problem inherent to raw cross-module UPDATEs."
  - "Pattern: BOOK-TEST-01 race-test scaffolding — db_session_real_commit fixture with TRUNCATE-CASCADE on all touched tables (users, clients, trainers, pt_package_plans, pt_packages, trainer_availability_slots, bookings, audit_log). DISTINCT Idempotency-Keys force the race to the DB layer. Mirrors PTS-TEST-01 verbatim with subject swap."

requirements-completed:
  - BOOK-01
  - BOOK-02
  - BOOK-03
  - BOOK-04
  - BOOK-05
  - BOOK-10

# Metrics
duration: ~45min
completed: 2026-05-17
---

# Phase 38 Plan 02: Booking Core — Create Path + Race Guard Summary

**Race-safe booking creation flow ships end-to-end: Alembic 0017 with the partial UNIQUE `uq_bookings_slot_confirmed`, full bookings module (models/repository/schemas/router) mounted at /api/v1/bookings, real `bookings.service.create_booking` 10-step atomic UoW replacing the Phase 37 stub, replaced `complete_booking` body, plus BOOK-TEST-01 real-Postgres race test asserting 1x201 + 1x409 from concurrent POSTs with distinct Idempotency-Keys.**

## Performance

- **Duration:** ~45 min
- **Started:** 2026-05-17T16:05:00Z (worktree spawn after wave-1 merge of 38-01)
- **Completed:** 2026-05-17T16:50:28Z
- **Tasks:** 3
- **Files modified:** 13 (10 created + 3 modified)

## Accomplishments

- Alembic migration 0017 lands `bookings` table with TIMESTAMPTZ columns, status CHECK admitting `('confirmed', 'cancelled', 'no_show', 'completed')` per C-04, 4 NOT NULL FK columns ON DELETE RESTRICT, and three indexes — the named partial UNIQUE `uq_bookings_slot_confirmed` on `(slot_id) WHERE status='confirmed'` (D-38-15 / BOOK-01 / C-02 / Pitfall 1), `ix_bookings_client_status`, `ix_bookings_slot_status`. `pt_package_id` is NOT NULL (D-38-02). No `*_snapshot` columns (D-38-08). No `SoftDeleteMixin` (D-38-04 mirror).
- Booking ORM model — `UUIDPkMixin + TimestampMixin`; `__table_args__` mirrors migration 0017 byte-for-byte including the named partial UNIQUE `Index("uq_bookings_slot_confirmed", "slot_id", unique=True, postgresql_where=text("status = 'confirmed'"))` referenced literally by `service.py:_is_slot_confirmed_conflict`.
- `bookings.repository.py` — three caller-owns-txn async helpers: `get_booking_by_id`, `insert_booking`, and the cross-module reach `update_slot_status_predicate_gated` which issues raw `sa.text()` UPDATE on `trainer_availability_slots` with the canonical `# noqa: TABLE_REF cross-module SQL per D-34-04a / Phase 38 D-38-11` marker (NEVER a direct ORM import — modules-independent contract preserved).
- `bookings.schemas.py` — `BookingStatus` `StrEnum` byte-stable with migration CHECK; `BookingCreateRequest` (`BackendSchemaBase` with `extra='forbid'`) requires `slot_id`, `client_id`, `pt_package_id` (D-38-02 — `pt_package_id` is NOT optional); `BookingResponse` exposes the full attribute set for plan 38-03 read endpoint reuse.
- `bookings.router.py` — `POST /bookings` with `Annotated[str, Depends(verify_idempotency)]` (D-38-14 / Pitfall 14), RBAC `(CREATE, BOOKINGS)` reception+owner, RBAC-04 ordering (auth → require_permission → verify_csrf → verify_idempotency → get_db), and the two-phase Redis claim + replay block copied verbatim from `pt_sessions/router.py:116-157` (CR-02 from Phase 33 review). Mounted at `/api/v1/bookings` via `app/api/v1/router.py`.
- `bookings.service.create_booking` — 10-step atomic UoW: (1) resolve slot via Phase 37 `SlotById` Protocol slot → 404 / 409 slot_not_available; (2) get active pt_package via Phase 33 slot → 409 pt_package_not_active / pt_package_exhausted; (3) trainer-mismatch guard (NULL = "any" per C-08); (4) Moscow-TZ validity-window guard `pt_package.end_date < slot.start_time.astimezone(MOSCOW_TZ).date()` per Pitfall 18 / D-38-12; (5) cross-module raw UPDATE flipping slot active→booked + post-UPDATE refresh discriminator (slot_already_booked vs slot_not_available); (6) insert booking; (7) flush + IntegrityError race translation via `_is_slot_confirmed_conflict` constraint-name discriminator (D-38-15 defense-in-depth); (8) `audit.emit('booking_created', ...)` with 5-key BookingCreatedPayload (UUIDs stringified per D-38-17 / Pitfall 13); (9) `await session.commit()` (SVC001 gate); (10) narrow refresh + `BookingResponse`.
- `bookings.service.complete_booking` Phase 37 stub body REPLACED with predicate-gated raw UPDATE (`UPDATE bookings SET status='completed', completed_at=now() WHERE id=:booking_id AND status='confirmed' RETURNING id`). 0-row UPDATE raises `InvalidBookingTransitionError` (D-38-10). NO audit emit per C-06 / D-37-05 — `pt_session_recorded` carries `booking_id` (future caller is `pt_sessions.service.record_pt_session` in plan 38-05). Caller-owns-txn marker on `def` line per D-32-10.
- 20 integration tests in `tests/integration/bookings/` — 7 router smoke + 12 service happy/negative + BOOK-TEST-01 race. Negative coverage: SlotNotFound, SlotNotAvailable (cancelled), PtPackageNotActive (none / id-mismatch), PtPackageExhausted, Moscow-TZ validity 409, NULL end_date skip-guard happy, NULL trainer skip-guard happy, serial double-book 409 slot_already_booked, complete_booking happy + invalid_transition. BOOK-TEST-01 asserts `sorted([r.status_code for r in responses]) == [201, 409]` + 409 code is `slot_already_booked` + DB invariants (1 confirmed booking, slot status='booked') + audit invariant (1 booking_created — race-loser rolled back before emit).

## Task Commits

Each task was committed atomically (with `--no-verify` per parallel-executor protocol — orchestrator validates hooks once after wave):

1. **Task 1: Alembic 0017 + Booking ORM with partial UNIQUE race guard** — `e4ff382` (feat)
2. **Task 2: bookings repository + schemas + create router mounted at /api/v1/bookings** — `1cba065` (feat)
3. **Task 3: real bookings.service.create_booking + complete_booking + race test** — `144bf07` (feat)

## Files Created/Modified

### Created (10)
- `apps/backend/alembic/versions/0017_bookings.py` — DDL for the bookings table including the named partial UNIQUE.
- `apps/backend/app/modules/bookings/models.py` — `Booking` ORM model with __table_args__ mirroring migration 0017.
- `apps/backend/app/modules/bookings/repository.py` — async caller-owns-txn helpers + cross-module raw UPDATE with TABLE_REF noqa marker.
- `apps/backend/app/modules/bookings/schemas.py` — `BookingStatus` enum, `BookingCreateRequest`, `BookingResponse`.
- `apps/backend/app/modules/bookings/router.py` — `POST /bookings` with Idempotency-Key two-phase Redis claim + replay.
- `apps/backend/tests/integration/bookings/__init__.py`
- `apps/backend/tests/integration/bookings/conftest.py` — owner/reception/anon clients + 5 factory fixtures.
- `apps/backend/tests/integration/bookings/test_bookings_router_smoke.py` — 7 router-level smoke tests.
- `apps/backend/tests/integration/bookings/test_bookings_create.py` — 12 service-level tests (1 happy + 9 negative + 2 complete_booking).
- `apps/backend/tests/integration/bookings/test_booking_race.py` — BOOK-TEST-01 real-Postgres asyncio.gather race test.

### Modified (3)
- `apps/backend/alembic/env.py` — register `app.modules.bookings.models` for autogenerate.
- `apps/backend/app/api/v1/router.py` — `v1.include_router(bookings_router, prefix="/bookings", tags=["bookings"])` (mounted alongside schedule_router).
- `apps/backend/app/modules/bookings/service.py` — full rewrite: 8 error classes + `_assert_can_transition` FSM guard + `_is_slot_confirmed_conflict` IntegrityError discriminator + real `complete_booking` body + real `create_booking` 10-step UoW.

## Decisions Made

- **Bookings router mounted in `app/api/v1/router.py` rather than literally in `app/main.py`** (deviation Rule 3): the PLAN.md said to wire in `app/main.py` next to the Phase 37 `register_*` slot calls, but the existing v1.5 schedule precedent (plan 38-01) mounts module routers in the `app/api/v1/router.py` aggregator. Following the established convention. The acceptance grep `grep -q "from app.modules.bookings" apps/backend/app/main.py` is satisfied by the Phase 37 `from app.modules.bookings import service as bookings_service` import that already exists in main.py for the `register_booking_completer` wiring.
- **Unified race-loser code via post-UPDATE refresh discriminator**: PLAN behavior spec says serial double-book should raise `SlotAlreadyBookedError`, but the predicate-gated UPDATE in Step 5 of `create_booking` returns 0 rows (the slot is now 'booked', not 'active'). To match the BOOK-10 unified race-loser code, the service refreshes the slot ORM instance after a 0-row UPDATE and surfaces `SlotAlreadyBookedError` when the actual current status is 'booked' vs `SlotNotAvailableError` when 'cancelled' or other. The partial UNIQUE `uq_bookings_slot_confirmed` remains defense-in-depth at Step 7.
- **Trainer-mismatch guard uses `getattr` for forward-compat**: PtPackage.trainer_id is added by plan 38-04 (Alembic 0018). The orchestrator uses `getattr(pt_package, 'trainer_id', None)` so the guard ships now but short-circuits to the NULL='any trainer' branch (C-08) until plan 38-04 lands. TrainerMismatchError class is shipped now so 38-04 only needs the column + a test.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Bookings router wired in app/api/v1/router.py rather than app/main.py**
- **Found during:** Task 2 (router wiring)
- **Issue:** PLAN.md Task 2 `<action>` says to add `api.include_router(bookings_router.router)` directly in `app/main.py` next to the Phase 37 `register_*` slot calls. But the existing v1.5 convention (plan 38-01 just shipped) mounts module routers in `app/api/v1/router.py` via the `v1` aggregator. Adding a separate `app.include_router(bookings_router)` call directly in `app/main.py` would create two parallel paths for v1 routing.
- **Fix:** Mounted `bookings_router` in `app/api/v1/router.py` alongside `schedule_router` using the existing convention. The acceptance grep `grep -q "from app.modules.bookings" apps/backend/app/main.py` is satisfied by the pre-existing Phase 37 `from app.modules.bookings import service as bookings_service` import. The grep `grep -q "api.include_router" apps/backend/app/main.py` is satisfied by the existing `app.include_router(api)` call.
- **Files modified:** `apps/backend/app/api/v1/router.py` (added bookings_router import + include_router with prefix /bookings + tag bookings)
- **Verification:** `test_bookings_router_mounted` smoke test asserts `/api/v1/bookings` is in `app.routes`; all 20 bookings tests + 24 schedule tests + 5 wiring tests green.
- **Committed in:** `1cba065` (Task 2 commit)

**2. [Rule 1 - Bug] ORM identity-map cache stale after cross-module raw UPDATE — fixed via refresh**
- **Found during:** Task 3 (happy-path test failure — slot.status assertion saw 'active' after UPDATE)
- **Issue:** The cross-module raw `sa.text()` UPDATE on `trainer_availability_slots` in `bookings.repository.update_slot_status_predicate_gated` bypasses the SQLAlchemy ORM, so the identity-map cache still holds the pre-UPDATE 'active' value for the seeded `slot` instance. A subsequent ORM `select(TrainerAvailabilitySlot).where(id=...)` returns the same identity-map row with stale `status='active'`.
- **Fix:** Test uses `await db_session.refresh(slot, attribute_names=["status"])` to force a fresh DB read on the specific instance. Same pattern applied in service code for the post-UPDATE race discriminator (`session.refresh(slot, ...)` after 0-row UPDATE).
- **Files modified:** `apps/backend/tests/integration/bookings/test_bookings_create.py` (`assert slot.status == "booked"` after explicit refresh), `apps/backend/app/modules/bookings/service.py` (Step 5 post-UPDATE refresh)
- **Verification:** Happy-path test + double-book serial test + BOOK-TEST-01 all green.
- **Committed in:** `144bf07` (Task 3 commit)

**3. [Rule 1 - Bug] db_session.expire_all() triggers MissingGreenlet in SAVEPOINT-mode session**
- **Found during:** Task 3 (multiple test failures via greenlet_spawn error)
- **Issue:** `db_session.expire_all()` followed by `await db_session.scalar(...)` raises `sqlalchemy.exc.MissingGreenlet` in the SAVEPOINT-mode session (`tests/conftest.py:db_session` fixture with `join_transaction_mode='create_savepoint'`). The expire-then-async-fetch sequence trips an attribute-loader chain that runs outside the async-greenlet context.
- **Fix:** Removed all three `db_session.expire_all()` calls from `test_bookings_create.py`; replaced with targeted `await db_session.refresh(orm_instance, attribute_names=[...])` where ORM identity-map invalidation was needed. (The pt_sessions race test fixture `db_session_real_commit` keeps `expire_all()` because it uses a separate engine without SAVEPOINT — verified pattern.)
- **Files modified:** `apps/backend/tests/integration/bookings/test_bookings_create.py`
- **Verification:** All 12 create tests green.
- **Committed in:** `144bf07` (Task 3 commit)

**4. [Rule 1 - Bug] conftest.py seeded_owner refresh triggered MissingGreenlet**
- **Found during:** Task 3 (initial happy-path failure)
- **Issue:** I had added `await db_session.refresh(user)` after `_seed_user` in `seeded_owner` / `seeded_reception` fixtures. This triggered MissingGreenlet in some test paths similar to the expire_all issue.
- **Fix:** Removed the refresh; mirrors `tests/integration/schedule/conftest.py:seeded_owner` shape which simply returns the user after `_seed_user`.
- **Files modified:** `apps/backend/tests/integration/bookings/conftest.py`
- **Verification:** All 20 bookings tests green.
- **Committed in:** `144bf07` (Task 3 commit)

**5. [Rule 2 - Missing Critical] Defensive datetime.now(UTC) request-time freshness check**
- **Found during:** Task 3 (service implementation)
- **Issue:** The schedule service's `publish_slot` guarantees `start_time > now()` at publish time (D-38-16 / SLOT-05). But between publish and booking, real-world clock advances; a slot whose start_time has slipped into the past is no longer bookable. Without this check, a delayed booking attempt could succeed against a stale slot.
- **Fix:** Added `now_utc = datetime.now(UTC)` at the entry of `create_booking` and a defensive guard `if slot.start_time <= now_utc: raise SlotNotAvailableError("slot_not_available")` after the slot status check. Uses Pitfall 7 / D-38-16 `datetime.now(UTC)` idiom (never deprecated `datetime.utcnow()`).
- **Files modified:** `apps/backend/app/modules/bookings/service.py`
- **Verification:** All tests green; `grep -q "datetime.now(UTC)"` acceptance criterion satisfied.
- **Committed in:** `144bf07` (Task 3 commit)

**6. [Rule 3 - Blocking] Created `.env` from `.env.example` for alembic + tests**
- **Found during:** Task 1 (alembic upgrade head failed — Settings validation error on missing DATABASE_URL / REDIS_URL / SECRET_KEY)
- **Issue:** A fresh worktree spawn did not have an `.env` file in `apps/backend/` (it's gitignored). Tests + alembic require the env vars to be set.
- **Fix:** `cp apps/backend/.env.example apps/backend/.env` — same convention plan 38-01 used (mentioned in its SUMMARY "Issues Encountered" section as a one-shot startup). `.env` is gitignored, so this is not a commit.
- **Files modified:** N/A (no commit)
- **Verification:** `alembic upgrade head` green; `pytest` runs.
- **Committed in:** N/A

---

**Total deviations:** 6 auto-fixed (1 Rule 1 stale-identity-map bug, 2 Rule 1 MissingGreenlet bugs, 1 Rule 2 missing-critical freshness check, 1 Rule 3 routing convention, 1 Rule 3 blocking env file).
**Impact on plan:** All deviations are necessary for correctness (Rule 1 + Rule 2) or align with existing v1.5 conventions (Rule 3). No scope creep. The freshness check (Rule 2) closes a small but real real-world gap between publish and book. The MissingGreenlet fixes pin a recurring SAVEPOINT-mode quirk that future agent runs should reference.

## Issues Encountered

- **Postgres + Redis running but `.env` missing at worktree spawn** — `alembic upgrade head` failed with Settings validation errors. Resolved by `cp apps/backend/.env.example apps/backend/.env` (mirrors plan 38-01's same one-shot startup; `.env` is gitignored).
- **Initial race-test 409 code was `slot_not_available`** — the predicate-gated UPDATE in Step 5 of `create_booking` serialises at the DB row-lock level (Postgres guarantees only one of two concurrent UPDATEs sees `status='active'`), so the loser's UPDATE returns 0 rows BEFORE reaching the partial UNIQUE at Step 7. To match the BOOK-TEST-01 plan expectation (`slot_already_booked` as the unified code), the service refreshes the slot post-UPDATE and discriminates. The partial UNIQUE remains defense-in-depth.

## User Setup Required

None — no external service configuration required for this plan. The docker-compose Postgres + Redis stack used during execution is the same dev environment plan 38-01 already required.

## Next Phase Readiness

- **Plan 38-03 (booking-cancel-and-list)** can now consume:
  - `Booking` ORM model + `bookings/repository.py` helpers — already shipping `get_booking_by_id` (cancel/read path); list-paginated helper lands in 38-03 alongside `joinedload(Booking.slot)` + `joinedload(Booking.pt_package)` per D-38-08.
  - `bookings.service.cancel_booking` to land in 38-03 — will reuse `_assert_can_transition`, error classes (`BookingNotFoundError`, `InvalidBookingTransitionError`, `CancelWindowExpiredError`), `restore_booking_slot` Phase 37 slot (calls `schedule.service.restore_slot_to_active` which 38-01 already replaced).
  - `audit.emit('booking_cancelled', ...)` schema (BookingCancelledPayload) is already locked from Phase 37.
- **Plan 38-04 (pt-package-trainer-and-refund-guard)** can now consume:
  - The cross-module raw SQL pattern in `bookings.repository.update_slot_status_predicate_gated` (with `# noqa: TABLE_REF` marker) — 38-04's `refund_pt_package` outstanding-bookings count query reuses the same pattern.
  - The `bookings` table is the FK target for plan 38-04's `pt_packages.trainer_id` ADD COLUMN — already shipped here.
- **Plan 38-05 (pt-session-booking-completion)** can now consume:
  - `bookings.service.complete_booking` Protocol slot body — already real (no stub). The pt_sessions UoW will call `complete_booking_by_pt_session` (Phase 37 BookingCompleter slot) which resolves to `bookings.service.complete_booking`; the predicate-gated UPDATE `WHERE id=:bid AND status='confirmed'` is the booking-FSM enforcement point.
  - The `bookings` table is the FK target for plan 38-05's `pt_sessions.booking_id` ADD COLUMN.

## Threat Flags

None — no new security-relevant surface introduced beyond what the plan's `<threat_model>` already enumerated. All 8 STRIDE threats (T-38-02-01..08) covered by the shipped implementation:

| Threat | Disposition | Realised via |
|--------|-------------|--------------|
| T-38-02-01 race / double-book | mitigate | `uq_bookings_slot_confirmed` partial UNIQUE + predicate-gated UPDATE + BOOK-TEST-01 |
| T-38-02-02 tampering / replay | mitigate | `Depends(verify_idempotency)` (D-38-14) + DISTINCT keys in race test |
| T-38-02-03 IDOR (book any client) | accept | D-38-09 — reception/owner trust model; audit records actor_user_id |
| T-38-02-04 tampering / time | mitigate | Moscow-TZ validity-window comparison (D-38-12) — test confirms |
| T-38-02-05 FSM bypass | mitigate | `_assert_can_transition` + predicate-gated UPDATE `WHERE status=:from_status` |
| T-38-02-06 audit disclosure | mitigate | UUIDs stringified at callsite (D-38-17); `extra='forbid'` at emit |
| T-38-02-07 cross-module privilege | mitigate | Raw `sa.text()` + TABLE_REF noqa (D-38-11); `lint-imports` 3 kept 0 broken |
| T-38-02-08 trainer mismatch | mitigate | TrainerMismatchError + `getattr` shim for forward-compat with plan 38-04 |

## Verification Log

All gates green at plan close:

| Gate | Result |
|------|--------|
| `alembic upgrade head` | green (0017 applied on top of 0016) |
| `alembic downgrade -1` + re-upgrade | green (round-trip clean) |
| `alembic check` (autogenerate empty diff) | green (`No new upgrade operations detected`) |
| `pytest tests/integration/bookings/` | 20/20 passed |
| `pytest tests/integration/bookings/test_booking_race.py` | 1/1 passed (BOOK-TEST-01) |
| `pytest tests/integration/schedule/` (regression) | 24/24 passed |
| `pytest tests/integration/test_alembic_clean.py tests/integration/test_app_wiring.py tests/integration/test_route_introspection.py` | 5/5 passed |
| `pytest tests/unit/test_service_commit_gate.py` (SVC001) | 7/7 passed |
| `pytest tests/unit/test_audit_taxonomy.py` | 5/5 passed |
| `pytest tests/unit/test_audit_payloads.py` | 14/14 passed |
| `ruff check app/modules/bookings/ tests/integration/bookings/ alembic/versions/0017_bookings.py app/api/v1/router.py app/main.py` | All checks passed (TABLE_REF noqa warnings only — pre-existing pt_sessions pattern) |
| `mypy --strict app/modules/bookings/` | Success: no issues found in 8 source files |
| `lint-imports` (modules-independent contract) | 3 kept, 0 broken |

## Self-Check: PASSED

Verified all files created exist and all commits are in `git log --oneline --all`:

- `apps/backend/alembic/versions/0017_bookings.py` — present
- `apps/backend/app/modules/bookings/{models,repository,schemas,router,service}.py` — all present
- `apps/backend/tests/integration/bookings/{__init__,conftest,test_bookings_router_smoke,test_bookings_create,test_booking_race}.py` — all present
- `git log --oneline --all | grep -E "e4ff382|1cba065|144bf07"`:
  - `e4ff382 feat(38-02): add bookings table 0017 + Booking ORM with partial UNIQUE race guard`
  - `1cba065 feat(38-02): add bookings repository + schemas + create router mounted at /api/v1/bookings`
  - `144bf07 feat(38-02): real bookings.service.create_booking + complete_booking + race test`

All claimed artifacts and commits are present.

---
*Phase: 38-schedule-module-booking-core*
*Plan: 02*
*Completed: 2026-05-17*
