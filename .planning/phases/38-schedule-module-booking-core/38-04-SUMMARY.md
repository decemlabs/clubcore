---
phase: 38-schedule-module-booking-core
plan: 04
subsystem: pt_packages
tags: [fastapi, sqlalchemy, alembic, postgres, cross-module-raw-sql, refund-guard, trainer-binding, audit, rbac, modules-independent]

# Dependency graph
requires:
  - phase: 37-foundations-bedrock
    provides: TrainerById Protocol slot (resolve_trainer_by_id), modules-independent import-linter contract, PtPackageSoldPayload locked schema
  - phase: 38-schedule-module-booking-core/38-02-PLAN.md
    provides: bookings table (Alembic 0017) — the refund-guard cross-module count query targets this table; alembic chain anchor for down_revision = "0017_bookings"
provides:
  - Alembic 0018_pt_packages_trainer_id — ADD COLUMN pt_packages.trainer_id UUID NULL, FK fk_pt_packages_trainer_id_trainers → trainers(id) ON DELETE RESTRICT, btree ix_pt_packages_trainer_id
  - PtPackage.trainer_id Mapped[UUID | None] column + Index entry in __table_args__
  - PtPackageCreateRequest.trainer_id optional UUID field (back-compat — defaults to None)
  - PtPackageResponse.trainer_id surface (nullable; serialised as `trainerId` via BackendSchemaBase camelCase mapping)
  - 3 new error classes in pt_packages.service — TrainerNotFoundError (404 trainer_not_found), TrainerInactiveError (422 trainer_inactive), OutstandingBookingsExistError (409 outstanding_bookings_exist) — codes byte-stable with pt_sessions module per D-34-12a
  - create_pt_package trainer-active validation (Step 2b) — resolves via TrainerById Protocol slot, rejects unknown/inactive trainers BEFORE pre-flight active-per-client check
  - refund_pt_package outstanding-bookings guard (Step 1b) — cross-module raw `sa.text()` count, fires BEFORE FSM `_assert_can_transition('cancelled')` so the friendly 409 code surfaces
  - 4 integration tests in tests/integration/pt_packages/test_pt_packages_trainer_id.py (PKG-01 / PKG-02)
  - 6 integration tests in tests/integration/pt_packages/test_pt_packages_refund_guard.py (PKG-03 — refund 409, multi-booking 409, cancelled-allows-200, no-bookings-200, non-confirmed statuses ignored, guard-ordering proof)
affects: [38-05, 39-NN, 40-NN]

# Tech tracking
tech-stack:
  added:
    - Cross-module raw `sa.text()` count query from pt_packages.service against the bookings table with the `# noqa: TABLE_REF cross-module SQL per D-34-04a / Phase 38 D-38-11` marker — establishes the canonical pt_packages → bookings boundary crossing pattern (NEVER a direct ORM import)
    - Optional FK column added to a v1.4 table via Alembic ALTER ADD COLUMN with 3-step migration (column → FK → index) mirroring 0009_renewal.py
  patterns:
    - Trainer-active validation reused verbatim from pt_sessions.service.record_pt_session — wire codes (trainer_not_found / trainer_inactive) and HTTP statuses (404 / 422) are byte-stable across pt_packages + pt_sessions so admin-web can share error-display logic
    - Pre-FSM guard ordering — friendly cross-module domain guards fire BEFORE the central FSM `_assert_can_transition` so users see the precise failure cause (outstanding_bookings_exist) instead of stock invalid_transition
    - Direct-SQL test seeding for cross-module guards — refund-guard tests INSERT bookings via raw SQL (matching production guard's read pattern), keeping the test decoupled from bookings.service internals

key-files:
  created:
    - apps/backend/alembic/versions/0018_pt_packages_trainer_id.py
    - apps/backend/tests/integration/pt_packages/test_pt_packages_trainer_id.py
    - apps/backend/tests/integration/pt_packages/test_pt_packages_refund_guard.py
    - .planning/phases/38-schedule-module-booking-core/deferred-items.md (1 entry — pre-existing pt_sessions.booking_id DB drift, NOT caused by 38-04; 38-05 owns it)
  modified:
    - apps/backend/app/modules/pt_packages/models.py (trainer_id column + Index)
    - apps/backend/app/modules/pt_packages/schemas.py (optional trainer_id on Create + Response)
    - apps/backend/app/modules/pt_packages/repository.py (insert_pt_package persists trainer_id)
    - apps/backend/app/modules/pt_packages/service.py (Step 2b trainer-active validation in create_pt_package; Step 1b outstanding-bookings guard in refund_pt_package; 3 new error classes; import resolve_trainer_by_id + sqlalchemy as sa)

key-decisions:
  - "TrainerInactiveError uses 422 (not 409) per Phase 31 / Phase 34 D-34-12a convention — semantic-validation failure, not state-conflict. Mirrors pt_sessions.service.TrainerInactiveError exactly so admin-web can route both modules through the same code path."
  - "Audit emit for pt_package_sold is intentionally NOT extended with trainer_id — PtPackageSoldPayload schema is locked at Phase 33 (10 keys, extra='forbid'). Adding trainer_id would require a schema migration coordinated across audit tests; the column is queryable from DB without audit, so trainer_id forensics work without the extension. Defer schema extension to Phase 39 if audit consumers actually need it."
  - "Refund-guard ordering: PKG-03 fires BEFORE the FSM `_assert_can_transition('cancelled')`. Rationale — when both would block, outstanding_bookings_exist is more actionable to the operator (they know what to do: cancel the bookings first) than stock invalid_transition (which implies a generic FSM problem). For terminal-source refund attempts (cancelled package) the booking-count is 0 by definition (cancelled packages have no confirmed bookings), so the new guard is a no-op in that branch and the FSM guard still surfaces invalid_transition — no behavior regression for the existing FSM test."
  - "Test seeding uses direct-SQL INSERT for bookings (not bookings.service.create_booking). Rationale per plan 38-04 Task 3 NOTE — keeps the test self-contained, decoupled from booking-service internals (which would add transitive surface for trainer/slot validation), and exercises the SAME code path (raw SQL count against the bookings table) that production uses. The test thus also documents the canonical cross-module SQL contract."
  - "Migration down_revision = '0017_bookings' (not '0015_pt_sessions' as an earlier draft considered). Wave-3 placement per checker BLOCKER means 38-02 ships bookings table first; this plan's Alembic chain follows after. Refund-guard test infrastructure depends on the bookings table physically existing."

patterns-established:
  - "Pattern: trainer-active validation in pt_packages.create_pt_package — copy-paste from pt_sessions.service:210-215 with identical error classes (TrainerNotFoundError / TrainerInactiveError) and identical HTTP statuses (404 / 422). Future modules that bind to trainer_id can reuse this 4-line block verbatim."
  - "Pattern: cross-module count guard via raw `sa.text()` from pt_packages → bookings — applicable to any v1.5+ cross-module integrity check (e.g., 'does dependent data exist before this terminal action?'). The `# noqa: TABLE_REF cross-module SQL per D-34-04a / Phase 38 D-38-11` marker is the documentation contract; `lint-imports` modules-independent stays green."
  - "Pattern: pre-FSM friendly guard insertion — when a cross-module domain guard would block a state transition, insert it BEFORE the central FSM `_assert_can_transition` so users see the precise actionable failure cause instead of stock invalid_transition. Sequencing: (1) load, (1b) cross-module domain guard(s), (2) FSM transition guard, (3) ... downstream actions. Applied to refund_pt_package; the pt_packages.cancel_pt_package + pt_packages.create_pt_package follow the same sequencing in their own structure."

requirements-completed:
  - PKG-01
  - PKG-02
  - PKG-03

# Metrics
duration: ~40min
completed: 2026-05-17
---

# Phase 38 Plan 04: PT-Package Trainer Binding + Refund Guard Summary

**Alembic 0018 lands `pt_packages.trainer_id` nullable FK; create_pt_package validates trainer-active when provided (404/422); refund_pt_package gains a cross-module raw-SQL guard against outstanding confirmed bookings (409 outstanding_bookings_exist) that fires BEFORE the FSM transition so the friendly code surfaces. modules-independent contract preserved — no direct bookings ORM import; raw `sa.text()` count with the canonical `# noqa: TABLE_REF` marker. All 3 PKG requirements satisfied; refund-guard portion of ROADMAP SC #4 closed.**

## Performance

- **Duration:** ~40 min
- **Started:** 2026-05-17T16:30:00Z (worktree spawn after wave-3 fan-out)
- **Completed:** 2026-05-17T17:10:43Z
- **Tasks:** 3 (1 migration + ORM/schema, 1 service guard + tests, 1 service guard + tests)
- **Files changed:** 7 (3 created + 4 modified; +119 / +243 / +394 net = ~756 insertions, 2 deletions)

## What Shipped

### Task 1 — Alembic 0018 + ORM column + schema field (commit 59a3830)

- **Migration `0018_pt_packages_trainer_id.py`** mirroring the 3-step `0009_renewal.py` template:
  - `op.add_column('pt_packages', sa.Column('trainer_id', sa.UUID(), nullable=True))`
  - `op.create_foreign_key(op.f('fk_pt_packages_trainer_id_trainers'), ..., ondelete='RESTRICT')` — RESTRICT chosen over SET NULL because trainers are soft-deleted via `is_active` (Phase 31 TRN-04), never hard-deleted; RESTRICT is the safer floor against out-of-band DBA surgery.
  - `op.create_index(op.f('ix_pt_packages_trainer_id'), ['trainer_id'])` — non-partial btree for forensic lookup.
- **`down_revision = "0017_bookings"`** — Wave-3 placement per checker BLOCKER (38-02 ships bookings table first).
- **Downgrade** reverses cleanly: drop_index → drop_constraint(type_=foreignkey) → drop_column.
- **PtPackage model** — `trainer_id: Mapped[UUIDType | None]` with named FK; Index entry in `__table_args__`.
- **Schema** — `PtPackageCreateRequest.trainer_id: UUID | None = None` (back-compat default; existing clients posting without trainerId still pass); `PtPackageResponse.trainer_id` exposed as `trainerId` via the BackendSchemaBase camelCase mapping.
- **Round-trip verified on Postgres 16:** upgrade → downgrade -1 → upgrade head. DB-level column present, nullable=YES, FK confdeltype='r' (RESTRICT), index present.

### Task 2 — `create_pt_package` trainer-active validation (commit c16a94d)

- **New Step 2b** inserted between snapshot symmetry (Step 2) and pre-flight active-per-client (Step 3): when `data.trainer_id is not None`, call `resolve_trainer_by_id(session, data.trainer_id)` via the Phase 31 TrainerById Protocol slot. None → 404 `trainer_not_found`. `is_active=False` → 422 `trainer_inactive`. Mirrors `pt_sessions.service.record_pt_session:210-215` verbatim — wire codes byte-stable across modules.
- **`insert_pt_package` repository helper** updated to persist `trainer_id` on the new row.
- **3 new error classes** added to `pt_packages.service` for stable wire-code parity with `pt_sessions.service`:
  - `TrainerNotFoundError` (404 `trainer_not_found`)
  - `TrainerInactiveError` (422 `trainer_inactive`)
  - `OutstandingBookingsExistError` (409 `outstanding_bookings_exist`) — used by Task 3
- **Audit emit untouched** — `PtPackageSoldPayload` schema is locked at Phase 33; adding `trainer_id` would require a coordinated schema migration. The column is queryable from DB without audit.
- **4 integration tests** in `test_pt_packages_trainer_id.py`:
  - Active trainer accepted (201, column persisted, response surfaces `trainerId`)
  - Omitted trainer_id back-compat (201, column NULL, response `trainerId: null`)
  - Inactive trainer → 422 `trainer_inactive` (no pt_package row created)
  - Unknown trainer_id → 404 `trainer_not_found` (no pt_package row created)

### Task 3 — `refund_pt_package` outstanding-bookings guard (commit 88b3bce)

- **New Step 1b** inserted between load and FSM transition guard:
  ```python
  result = await session.execute(
      sa.text(
          "SELECT count(*) FROM bookings "
          "WHERE pt_package_id = :pkg_id AND status = 'confirmed'"
      ),  # noqa: TABLE_REF cross-module SQL per D-34-04a / Phase 38 D-38-11
      {"pkg_id": str(pt_package_id)},
  )
  if result.scalar_one() > 0:
      raise OutstandingBookingsExistError("outstanding_bookings_exist")
  ```
- **Guard ordering:** fires BEFORE `_assert_can_transition(target="cancelled")` so the friendly 409 `outstanding_bookings_exist` surfaces instead of stock `invalid_transition` when both would apply.
- **Cross-module discipline preserved:** no direct ORM import of `app.modules.bookings`; raw `sa.text()` with the canonical TABLE_REF noqa marker. `lint-imports` modules-independent contract green.
- **Operator workflow:** cancel outstanding bookings first, then refund. No automatic cascade per C-09 — refund is a terminal lifecycle event so silent cascade would orphan PT-session expectations the client arranged.
- **6 integration tests** in `test_pt_packages_refund_guard.py`:
  - Single confirmed booking → 409 `outstanding_bookings_exist`
  - Two confirmed bookings → still single 409 (count > 0 is the gate)
  - Cancelled booking → guard count = 0 → 200 refund proceeds
  - No bookings at all → 200 refund (Task 2 happy-path regression)
  - completed / no_show / cancelled bookings → all invisible to `WHERE status='confirmed'` filter → 200
  - Guard ordering proof: 409 returned with `code='outstanding_bookings_exist'`, NOT `'invalid_transition'`
- **Test seeding** uses direct SQL INSERT for bookings + slots (not `bookings.service.create_booking`), per plan 38-04 Task 3 NOTE — keeps the test decoupled from booking-service internals and exercises the same raw-SQL path production uses.

## Verification

| Check | Result |
|---|---|
| `alembic upgrade head` (with 0018 applied) | PASSED |
| `alembic downgrade -1` → `upgrade head` round-trip | PASSED |
| `pytest tests/integration/pt_packages/test_pt_packages_trainer_id.py` (4 new tests) | 4/4 PASSED |
| `pytest tests/integration/pt_packages/test_pt_packages_refund_guard.py` (6 new tests) | 6/6 PASSED |
| `pytest tests/integration/pt_packages/test_pt_package_refund.py` (regression) | 13/13 PASSED |
| `pytest tests/integration/pt_packages/test_pt_package_sale.py` (regression) | 7/10 PASSED (3 pre-existing DEFER-36-04-A failures — NOT caused by 38-04) |
| `pytest tests/unit/test_service_commit_gate.py` (SVC001 walker) | 7/7 PASSED |
| `pytest tests/unit/test_audit_taxonomy.py tests/unit/test_audit_payloads.py` | 26/26 PASSED |
| `ruff check app/modules/pt_packages/ alembic/versions/0018_pt_packages_trainer_id.py` | PASSED (single pre-existing TABLE_REF noqa "warning" — documentation marker, not a real ruff rule, established by pt_sessions/repository.py before this plan) |
| `mypy --strict app/modules/pt_packages/` | PASSED (7 source files) |
| `lint-imports` (modules-independent contract) | PASSED (3 contracts kept, 0 broken) |
| Acceptance grep: `class OutstandingBookingsExistError` | FOUND (1 occurrence) |
| Acceptance grep: `outstanding_bookings_exist` | FOUND (3 occurrences) |
| Acceptance grep: `SELECT count(*) FROM bookings` | FOUND (1 occurrence) |
| Acceptance grep: `noqa: TABLE_REF` | FOUND (1 occurrence) |
| Acceptance grep: `from app.modules.bookings` (must be 0) | 0 occurrences |
| Acceptance grep: `data.trainer_id is not None` | FOUND |
| Acceptance grep: `resolve_trainer_by_id` (in service.py) | FOUND |

## Deviations from Plan

### Auto-fixed Issues

**None.** Plan 38-04 executed exactly as written — all 3 tasks landed with the structure, error codes, HTTP statuses, and cross-module discipline specified in the plan.

### Auth Gates

**None encountered.** Task 1 migration ran against the local Postgres docker-compose stack (already running); Tasks 2-3 used the existing authed test client fixtures (`authed_client_owner` / `authed_client_reception`) seeded via the standard pt_packages conftest.

### Pre-Existing Out-of-Scope Issues (not addressed)

1. **`alembic check` reports drift on `pt_sessions.booking_id`** — the local DB has a leftover `booking_id` column from a prior 38-05 experiment. This is NOT caused by 38-04 (plan 38-05 has not shipped its ORM column yet). Logged to `.planning/phases/38-schedule-module-booking-core/deferred-items.md`; 38-05's executor (or a fresh DB) will reconcile.
2. **3 pre-existing failures in `test_pt_package_sale.py`** (`amount_mismatch_422`, `idempotency_key_replay`, `missing_idempotency_key_422`) — explicitly listed in 38-CONTEXT.md as "11 remaining DEFER-36-04-A pytest failures: 3 pt_packages envelope drift". Pre-existing; 38-06 owns the parallel sweep. NOT caused by 38-04 (verified by examining git blame on the assertions).
3. **Ruff "warning" on `noqa: TABLE_REF` marker** — the canonical D-34-04a documentation marker is not a real ruff rule code; ruff emits a warning that the directive format is non-standard. Pre-existing convention from `pt_sessions/repository.py` (4 occurrences there, 1 added here). Locked across the codebase as the cross-module SQL boundary marker.

## Self-Check: PASSED

- File `apps/backend/alembic/versions/0018_pt_packages_trainer_id.py` exists: **FOUND**
- File `apps/backend/tests/integration/pt_packages/test_pt_packages_trainer_id.py` exists: **FOUND**
- File `apps/backend/tests/integration/pt_packages/test_pt_packages_refund_guard.py` exists: **FOUND**
- Commit `59a3830` (Task 1) in git log: **FOUND**
- Commit `c16a94d` (Task 2) in git log: **FOUND**
- Commit `88b3bce` (Task 3) in git log: **FOUND**
- `lint-imports` modules-independent contract: **GREEN**
- `ruff check` on pt_packages module: **PASSED** (with pre-existing TABLE_REF noqa documentation warning)
- `mypy --strict` on pt_packages module: **PASSED**
- Alembic round-trip on Postgres 16: **PASSED**
- 10 new integration tests (4 + 6): **10/10 PASSED**
- SVC001 walker + audit taxonomy/payloads walkers: **33/33 PASSED**
