---
phase: 34-pt-session-recording
plan: 01
subsystem: api
tags: [fastapi, sqlalchemy, alembic, pydantic, postgres, importlinter, rbac]

# Dependency graph
requires:
  - phase: 30-foundations-tech-debt-bedrock
    provides: "LOCKED_AUDIT_EVENTS (pt_session_recorded / pt_session_cancelled / pt_package_exhausted), audit_payloads.py Pydantic schemas, Resource.PT_SESSIONS + OWNER_ONLY matrix, importlinter modules-independent contract, SVC001 walker glob"
  - phase: 31-trainers-module
    provides: "trainers table + TrainerById Protocol + register_trainer_by_id_resolver"
  - phase: 33-pt-package-plans-instances
    provides: "pt_packages instance table + ActivePtPackage Protocol + PT_PACKAGE_STATUS_TRANSITIONS FSM (Phase 34 D-34-11a preserves it unchanged; reverse exhausted→active flip is locally-scoped predicate-gated)"
provides:
  - "Migration 0015_pt_sessions creating pt_sessions table with PT-14 columns (4 FK ON DELETE RESTRICT, 3 CHECK constraints, 2 composite indexes performed_at DESC)"
  - "app.modules.pt_sessions module skeleton (8 files: __init__/constants/models/schemas/repository-header/service-header/router-stub/permissions-stub) — importable, mypy-clean"
  - "TrainerById Protocol extended with full_name: str (D-34-12a additive — B-05 trainer_name_snapshot capture)"
  - "OWNER_ONLY frozenset shrunk 26→25: (CANCEL, PT_SESSIONS) removed (D-34-09a — B-12 24h reception cancel-window enforced application-layer in 34-03)"
  - ".importlinter modules-independent contract extended to 12 modules (app.modules.pt_sessions added)"
  - "v1 aggregator wired: pt_sessions_router at /pt-sessions, package_scoped_router at /pt-packages for GET /pt-packages/{id}/sessions"
  - "admin-web can.ts byte-parity update + can.test.ts assertion shift (size 25, cancel:pt-sessions reception-retained)"
affects: ["34-02 (record_pt_session — needs migration + TrainerById.full_name + module skeleton)", "34-03 (cancel/get/list — needs OWNER_ONLY removal + module skeleton)"]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Cross-module SQL via raw sa.text() with `# noqa: TABLE_REF cross-module SQL per D-34-04a` marker (header docstring documents this convention; helpers filled in 34-02/34-03)"
    - "Protocol additive extension (TrainerById gains full_name: str) — structurally satisfied by existing Trainer ORM, zero resolver-wiring change"
    - "OWNER_ONLY mirror across backend (frozenset) + admin-web (array literal) — byte-parity test (Phase 30 INFRA-19 + can.test.ts size assertion) is the trust gate"
    - "Module-shape parity: pt_sessions follows pt_packages 7-file shape (constants/models/schemas/repository/service/router/permissions) + empty test __init__.py markers"

key-files:
  created:
    - "apps/backend/alembic/versions/0015_pt_sessions.py — DDL: 4 FK ON DELETE RESTRICT (pt_package_id / trainer_id / client_id / performed_by_user_id), 3 CHECK constraints (cancel_reason_requires_cancelled_at / cancel_reason_length / notes_length), 2 composite indexes (pt_package_id + trainer_id with performed_at DESC), NO partial UNIQUE per D-34-02"
    - "apps/backend/app/modules/pt_sessions/__init__.py — module marker; no public re-exports (D-34-13a zero new Protocol slots)"
    - "apps/backend/app/modules/pt_sessions/constants.py — BACKDATING_WINDOW_DAYS_RECEPTION=7 (B-11), CANCEL_WINDOW_HOURS_RECEPTION=24 (B-12), MAX_NOTES_CHARS=500, MAX_CANCEL_REASON_CHARS=200 (D-34-02)"
    - "apps/backend/app/modules/pt_sessions/models.py — PtSession(Base, UUIDPkMixin, TimestampMixin) with PT-14 columns + 3 CheckConstraint + 2 Index entries; no cross-module ORM imports"
    - "apps/backend/app/modules/pt_sessions/schemas.py — PtSessionCreateRequest / PtSessionCancelRequest / PtSessionListByPackageQuery / PtSessionResponse"
    - "apps/backend/app/modules/pt_sessions/repository.py — header + import surface (sale-side helpers filled in 34-02, cancel/read-side in 34-03); documents D-34-04a raw text() escape hatch"
    - "apps/backend/app/modules/pt_sessions/service.py — module docstring (PT-20 orthogonality to visits, D-34-11a FSM carve-out, D-34-04a, SVC001/INFRA-11/audit_payloads invariants) + 10 error classes (D-34-18 catalogue)"
    - "apps/backend/app/modules/pt_sessions/router.py — pt_sessions_router + package_scoped_router APIRouter instances (handlers attached in 34-02/34-03)"
    - "apps/backend/app/modules/pt_sessions/permissions.py — empty stub for module-shape parity (D-34-03)"
    - "apps/backend/tests/unit/pt_sessions/__init__.py — empty test marker"
    - "apps/backend/tests/integration/pt_sessions/__init__.py — empty test marker"
  modified:
    - "apps/backend/app/core/dependencies.py — TrainerById Protocol gains full_name: str (D-34-12a); docstring updated"
    - "apps/backend/app/core/permissions.py — OWNER_ONLY frozenset shrinks 26→25 (removed (Action.CANCEL, Resource.PT_SESSIONS) per D-34-09a); comment block updated; ruff format reflowed the literal"
    - "apps/backend/.importlinter — modules-independent contract extended with app.modules.pt_sessions (12th module per D-34-14)"
    - "apps/backend/app/api/v1/router.py — include_router(pt_sessions_router, prefix='/pt-sessions') + include_router(package_scoped_router, prefix='/pt-packages')"
    - "apps/admin-web/src/shared/session/can.ts — removed { action: 'cancel', resource: 'pt-sessions' } entry (byte-parity with backend OWNER_ONLY; D-34-09a)"
    - "apps/admin-web/src/shared/session/can.test.ts — OWNER_ONLY size assertion 26→25; 'cancel:pt-sessions' reclassified from covered-set to reception-retained-set"

key-decisions:
  - "Followed plan exactly — no scope creep. All five amendments (migration, Protocol, OWNER_ONLY, importlinter, admin-web mirror) landed in Wave 1 so Wave 2 plans 34-02 + 34-03 can run in parallel without shared-file conflicts."
  - "Rule 1 auto-fix: updated can.test.ts assertions (size 26→25, reclassified cancel:pt-sessions) — the test was asserting pre-D-34-09a state and would have failed once the byte-parity amendment landed. The plan's verify gate (admin-web shared/session) caught this before merge."

patterns-established:
  - "Protocol additive extension: extending an existing Protocol (TrainerById) with a structural attribute (full_name: str) is the preferred shape for cross-module data-capture needs — over introducing a new resolver slot. The ORM already exposes the attribute so the resolver wiring is unchanged; only the Protocol surface widens. Mirror future when cross-module reads need additional fields without expanding the slot count."
  - "Module-skeleton-first plan in multi-wave phases: landing the migration + the empty-but-wired module skeleton + cross-cutting amendments (Protocol + RBAC + importlinter + admin-web mirror) in a single Wave-1 plan lets the implementation plans run in parallel in later waves without competing for shared files (core/permissions.py, .importlinter, can.ts, v1 aggregator)."

requirements-completed: [PT-14, PT-20, PT-21]

# Metrics
duration: ~20min
completed: 2026-05-16
---

# Phase 34 Plan 01: PT-Session Recording Foundations Summary

**Migration 0015_pt_sessions + pt_sessions module skeleton + 4 cross-cutting amendments (TrainerById.full_name, OWNER_ONLY -1, importlinter +pt_sessions, admin-web byte-parity)**

## Performance

- **Duration:** ~20 min
- **Started:** 2026-05-16T12:53Z (approx — captured at task 1 commit time)
- **Completed:** 2026-05-16T13:00Z
- **Tasks:** 3
- **Files modified:** 16 (10 created + 6 modified)

## Accomplishments

- Migration 0015_pt_sessions creates pt_sessions with full PT-14 column set, 4 ON DELETE RESTRICT FKs, 3 CHECK constraints (cancel-consistency, cancel_reason ≤200, notes ≤500), 2 composite indexes with performed_at DESC, and ZERO partial UNIQUE constraints per D-34-02.
- pt_sessions module skeleton (8 files) is fully importable and mypy --strict clean. Module enforces D-34-04a (NO `from app.modules.pt_packages` imports — cross-module SQL goes through raw `sa.text()` in repository helpers added by 34-02/34-03).
- TrainerById Protocol additively extended with `full_name: str` (D-34-12a) — Trainer ORM satisfies structurally; resolver wiring unchanged.
- OWNER_ONLY frozenset reduced 26→25 entries: `(CANCEL, PT_SESSIONS)` removed per D-34-09a. Reception now passes the RBAC gate; the application layer enforces the B-12 24h cancel window via `cancel_window_expired` 403 in 34-03 service.
- `.importlinter` modules-independent contract extended to 12 modules. `lint-imports` reports `3 contracts kept, 0 broken`.
- v1 aggregator mounts both routers: `/pt-sessions` (record + cancel + GET-by-id from 34-02/34-03) and `/pt-packages` (GET `/pt-packages/{id}/sessions` from 34-03, subject-side ownership per D-33-18 / D-34-08).
- admin-web byte-parity: `can.ts` mirror dropped the `{cancel, pt-sessions}` entry; `can.test.ts` assertions updated to 25 entries + reception-retained reclassification. All 12 admin-web `shared/session` vitest cases pass.

## Task Commits

Each task was committed atomically:

1. **Task 1: Migration + cross-cutting amendments** — `8bc15a5` (feat)
2. **Task 2: pt_sessions module skeleton + v1 aggregator wiring** — `52796d8` (feat)
3. **Task 3: Quality gates + ruff format + can.test.ts byte-parity update** — `430f348` (chore)

## Files Created/Modified

### Created
- `apps/backend/alembic/versions/0015_pt_sessions.py` — migration DDL
- `apps/backend/app/modules/pt_sessions/__init__.py` — module marker
- `apps/backend/app/modules/pt_sessions/constants.py` — window constants (B-11/B-12)
- `apps/backend/app/modules/pt_sessions/models.py` — PtSession ORM
- `apps/backend/app/modules/pt_sessions/schemas.py` — 4 Pydantic DTOs
- `apps/backend/app/modules/pt_sessions/repository.py` — header + import surface
- `apps/backend/app/modules/pt_sessions/service.py` — header + 10 error classes
- `apps/backend/app/modules/pt_sessions/router.py` — 2 empty APIRouter instances
- `apps/backend/app/modules/pt_sessions/permissions.py` — empty stub
- `apps/backend/tests/unit/pt_sessions/__init__.py` — empty test marker
- `apps/backend/tests/integration/pt_sessions/__init__.py` — empty test marker
- `.planning/phases/34-pt-session-recording/34-01-SUMMARY.md` (this file)

### Modified
- `apps/backend/app/core/dependencies.py` — TrainerById Protocol +`full_name: str` (D-34-12a)
- `apps/backend/app/core/permissions.py` — OWNER_ONLY −1 entry (D-34-09a)
- `apps/backend/.importlinter` — +`app.modules.pt_sessions` (D-34-14)
- `apps/backend/app/api/v1/router.py` — mount both pt_sessions routers
- `apps/admin-web/src/shared/session/can.ts` — −`{cancel, pt-sessions}` (D-34-09a mirror)
- `apps/admin-web/src/shared/session/can.test.ts` — assertions shifted to post-D-34-09a state

## Decisions Made

Followed the plan as specified — all five amendments and the module skeleton landed exactly per `34-01-PLAN.md`. No architectural changes; no scope creep.

The only judgement call was the precise wording of the new comment block in `apps/backend/app/core/permissions.py` (above the frozenset) — I added an inline rationale referencing D-34-09a, the B-12 24h window, and the new application-layer enforcement site (`pt_sessions.service.cancel_pt_session`) so future readers see the rationale at the deletion site, not just in the SUMMARY.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 — Bug] Updated admin-web `can.test.ts` assertions to track D-34-09a byte-parity update**

- **Found during:** Task 3 (quality gates — `pnpm test shared/session`)
- **Issue:** Two existing tests in `apps/admin-web/src/shared/session/can.test.ts` asserted the pre-Phase-34 state: `OWNER_ONLY` size 26 and the inclusion of `'cancel:pt-sessions'` in the OWNER_ONLY pairs set. After D-34-09a removed the entry from `can.ts` (per the plan), these tests failed.
- **Fix:** Updated three assertions in `can.test.ts`:
  - Test name + assertion: "OWNER_ONLY has exactly 26 entries (Phase 30 INFRA-19)" → "OWNER_ONLY has exactly 25 entries (Phase 34 D-34-09a removed cancel:pt-sessions)".
  - Removed `expect(pairs).toContain('cancel:pt-sessions')` from the OWNER_ONLY-coverage test.
  - Added `expect(pairs).not.toContain('cancel:pt-sessions')` to the reception-retained-rights test, with a clarifying comment about the 24h server-side window.
- **Files modified:** `apps/admin-web/src/shared/session/can.test.ts`
- **Verification:** `pnpm test shared/session` → 12 passed (2 files, 12 tests).
- **Committed in:** `430f348` (Task 3 commit)

**Rationale (in-scope per Rule 1):** The test failure was directly caused by Task 1's `can.ts` amendment (mandated by the plan). The plan's verification step explicitly required `admin-web shared/session vitest` to pass, so updating the assertion in lockstep with the source change is the correct fix. The test continues to enforce byte-parity — it now enforces the new size and the new reception-retained pair instead of the old ones.

**2. [Rule 1 — Bug] ruff format reformatting of touched files**

- **Found during:** Task 3 (ruff format --check on amendment files)
- **Issue:** `ruff format --check` reported `apps/backend/app/core/dependencies.py` and `apps/backend/app/core/permissions.py` as "would reformat" — pre-existing tiny formatting drifts (function-signature reflow on `get_active_pt_package`; `ClientByTelegramResolver` type alias single-line; frozenset literal nesting in OWNER_ONLY) plus a blank-line trim in the newly-created `pt_sessions/service.py`.
- **Fix:** Ran `ruff format` on `app/core/dependencies.py`, `app/core/permissions.py`, and `app/modules/pt_sessions/service.py` (auto-fix). Pure whitespace/wrapping — no behaviour change.
- **Files modified:** `apps/backend/app/core/dependencies.py`, `apps/backend/app/core/permissions.py`, `apps/backend/app/modules/pt_sessions/service.py`
- **Verification:** `ruff format --check` → "11 files already formatted"; `ruff check` → "All checks passed!"; `mypy --strict` → "Success: no issues found in 8 source files".
- **Committed in:** `430f348` (Task 3 commit)

---

**Total deviations:** 2 auto-fixed (both Rule 1 — directly caused by the plan's mandated source amendments).
**Impact on plan:** Both auto-fixes are byte-parity / formatting tidy-ups in scope of Task 3's quality-gates checklist. No scope creep, no architectural change.

## Issues Encountered

- **alembic upgrade head / downgrade -1 / upgrade head sequence (Task 3 gate #5) skipped — Postgres unreachable in this execution sandbox.** Docker daemon was not running in the worktree environment; `asyncpg` connect to `localhost:5432` returned `[Errno 61] Connect call failed`. Mitigation: `alembic history` confirms the revision chain is parseable (`0014_pt_packages -> 0015_pt_sessions (head)`); ruff + mypy --strict + lint-imports + Phase 30 walkers + admin-web byte-parity all green. The DB-roundtrip gate (apply + revert + re-apply) should be re-run before Wave 2 starts when Postgres is available — this is the only verification step from Task 3 that did not execute locally.

## User Setup Required

None — no external service configuration required.

## Deferred Verification

- **alembic upgrade head / downgrade -1 / upgrade head against a live Postgres 16 instance.** Required to confirm DDL applies cleanly + the index expression `performed_at DESC` is accepted + the 3 CHECK constraint syntaxes parse. The orchestrator should re-run this gate before spawning 34-02 / 34-03 in Wave 2, or 34-02's first action can re-run it as a precondition (it is idempotent — if the migration already applied cleanly, `alembic upgrade head` is a no-op).

## Next Phase Readiness

- **34-02 (record_pt_session) is unblocked:** the `pt_sessions_router` exists at `/pt-sessions`; `service.py` has all 10 error classes pre-declared (including `PtPackageExhaustedError`, `TrainerInactiveError`, `PerformedAtInFutureError`, `PerformedAtOutOfWindowError`); the migration is in place so the table is creatable; `TrainerById.full_name` is exposed for B-05 snapshot capture; `repository.py` is importable so the sale-side helpers (`atomic_decrement_pt_package`, `atomic_transition_to_exhausted`, `fetch_pt_package_metadata`, `insert_pt_session`) can be added directly without re-touching the module top-doc.
- **34-03 (cancel + GET endpoints) is unblocked:** the `package_scoped_router` exists at `/pt-packages`; the OWNER_ONLY matrix permits reception to call `POST /pt-sessions/{id}/cancel`; `service.py` has `CancelWindowExpiredError`, `PtSessionAlreadyCancelledError`, `PtSessionNotFoundError` pre-declared; `repository.py` is importable so the cancel-side helpers (`atomic_increment_pt_package`, `atomic_transition_exhausted_to_active`, `mark_cancelled`, `get_pt_session`, `list_by_pt_package_paginated`) can be added without shared-file conflicts.
- **No blockers** for Wave 2 parallel execution. The only outstanding item is the deferred alembic-roundtrip verification (see above).

## Self-Check: PASSED

Verified each claim before marking the plan complete:

```
$ ls apps/backend/alembic/versions/0015_pt_sessions.py                    -> FOUND
$ ls apps/backend/app/modules/pt_sessions/{__init__,constants,models,schemas,repository,service,router,permissions}.py
                                                                          -> all 8 FOUND
$ ls apps/backend/tests/{unit,integration}/pt_sessions/__init__.py        -> both FOUND
$ git log --all --oneline | grep -E "^(8bc15a5|52796d8|430f348)"
8bc15a5 feat(34-01): add 0015_pt_sessions migration + cross-cutting amendments
52796d8 feat(34-01): scaffold pt_sessions module skeleton + v1 aggregator wiring
430f348 chore(34-01): apply ruff format + update byte-parity vitest for D-34-09a
                                                                          -> all 3 commits FOUND
$ uv run python -c "from app.modules.pt_sessions import models, schemas, repository, service, router, constants, permissions; print('IMPORT OK')"
IMPORT OK                                                                 -> PASS
$ uv run lint-imports                                                     -> Contracts: 3 kept, 0 broken
$ uv run mypy --strict app/modules/pt_sessions/                           -> Success: no issues found in 8 source files
$ uv run pytest tests/unit/test_audit_taxonomy.py test_service_commit_gate.py test_payments_appendonly.py
                                                                          -> 18 passed
$ pnpm test -- --run shared/session (admin-web)                           -> 12 passed (2 files)
```

The only "not-passed" item is the alembic DB-roundtrip (deferred — see Issues Encountered + Deferred Verification sections).

---
*Phase: 34-pt-session-recording*
*Completed: 2026-05-16*
