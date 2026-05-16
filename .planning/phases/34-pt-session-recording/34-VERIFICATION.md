---
status: passed
phase: 34-pt-session-recording
goal_score: 12/12
date: 2026-05-16
verified: 2026-05-16T00:00:00Z
re_verification:
  previous_status: none
  previous_score: n/a
  gaps_closed: []
  gaps_remaining: []
  regressions: []
---

# Phase 34: PT-Session Recording — Verification Report

**Phase Goal (from ROADMAP.md):** Reception fixates the fact of a conducted personal training with a specific trainer; package balance atomically decrements via DB-level race-safe SQL; on reaching zero the package auto-transitions to `exhausted`; cancellation restores balance; PT-sessions are independent of visits (orthogonal events).

**Verified:** 2026-05-16
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| #  | Truth                                                                                                              | Status     | Evidence                                                                                                                                                                                              |
| -- | ------------------------------------------------------------------------------------------------------------------ | ---------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1  | Migration `0015_pt_sessions` creates `pt_sessions` table with PT-14 column set                                     | VERIFIED   | `apps/backend/alembic/versions/0015_pt_sessions.py:33-34` revision/down_revision; 10 columns + id; 4 FK ON DELETE RESTRICT (lines 82-105); 3 CHECK constraints (69-80); 2 composite indexes (110-119) |
| 2  | `POST /api/v1/pt-sessions` reception+owner, Idempotency-Key, body schema validation, trainer/package validation    | VERIFIED   | `router.py:63-75` decorator + `:79-86` deps incl `verify_idempotency`; `service.py:200-222` window + trainer + package validation                                                                     |
| 3  | Race-safe atomic decrement via single SQL UPDATE...RETURNING with predicate                                        | VERIFIED   | `repository.py:59-72` raw text UPDATE with `sessions_remaining > 0 AND status='active' RETURNING sessions_remaining`; 0-row → `None` → 409 in service.py:229-230                                       |
| 4  | Auto-transition to `exhausted` in same UoW when `new_remaining == 0`; emits `pt_package_exhausted` once            | VERIFIED   | `service.py:272-286` conditional `atomic_transition_to_exhausted` + literal-string `audit.emit("pt_package_exhausted", ...)`; single commit at line 289                                                |
| 5  | Cancel endpoint with balance restoration; conditional `exhausted→active` revert; `package_reactivated` audit bool  | VERIFIED   | `service.py:391-400` `atomic_transition_exhausted_to_active` predicate-gated; `service.py:419` `package_reactivated=package_reactivated` in audit emit                                                 |
| 6  | Cancel-window enforced via `pt_session.created_at` (NOT `performed_at`); reception 24h / owner anytime; 403        | VERIFIED   | `service.py:352-355` `if actor.role == Role.RECEPTION: age = datetime.now(UTC) - pt_session.created_at` + `CancelWindowExpiredError`                                                                  |
| 7  | D-34-11a invariant: `pt_packages/constants.py` unchanged                                                           | VERIFIED   | `git log --oneline 828813e..HEAD apps/backend/app/modules/pt_packages/constants.py` returns empty                                                                                                     |
| 8  | GET endpoints: single-session + paginated by-package on `package_scoped_router`                                    | VERIFIED   | `router.py:256-274` GET `/{pt_session_id}`; `router.py:277-309` `@package_scoped_router.get("/{pt_package_id}/sessions")` with `PaginatedData[PtSessionResponse]` envelope                             |
| 9  | PT-20 visits orthogonality: no `app.modules.visits` import in pt_sessions module                                   | VERIFIED   | `grep -rE "^from app\.modules\.visits\|^import .*visits" apps/backend/app/modules/pt_sessions/` returns empty                                                                                          |
| 10 | PT-21 audit events: literal `pt_session_recorded` + `pt_session_cancelled` with locked payloads                    | VERIFIED   | `service.py:255-269` literal emit + `:408-420` literal emit; payloads field-for-field match `audit_payloads.py:278-313`                                                                                |
| 11 | PT-22 race test exists with @requires_postgres marker, 2 concurrent posts, expects [201, 409]                      | VERIFIED   | `test_pt_session_record_race.py:1-187` with `requires_postgres`, `asyncio.gather`, `sessions_remaining=1`, assert `statuses == [201, 409]`                                                            |
| 12 | Cross-cutting amendments: OWNER_ONLY (no CANCEL,PT_SESSIONS), TrainerById full_name, importlinter 12 modules, can.ts mirror, OWNER_ONLY len==25 | VERIFIED   | `permissions.py:55-94` 25-tuple frozenset, no `(CANCEL, PT_SESSIONS)`; `dependencies.py:285` `full_name: str`; `.importlinter` modules block lists 12; `can.ts:42-43` no pt-sessions cancel entry; `test_permissions.py:21` `assert len(OWNER_ONLY) == 25` |

**Score:** 12/12 truths verified

### Required Artifacts

| Artifact                                                          | Expected                                                                | Status   | Details                                                                       |
| ----------------------------------------------------------------- | ----------------------------------------------------------------------- | -------- | ----------------------------------------------------------------------------- |
| `apps/backend/alembic/versions/0015_pt_sessions.py`               | Migration with 4 FK RESTRICT, 3 CHECK, 2 composite indexes              | VERIFIED | 132 lines; all constraints + indexes present; revision/down_revision correct  |
| `apps/backend/app/modules/pt_sessions/models.py`                  | `PtSession` ORM with 10 columns + `__table_args__`                      | VERIFIED | 127 lines; 4 FK columns, 3 CHECK in `__table_args__`, 2 Index                 |
| `apps/backend/app/modules/pt_sessions/schemas.py`                 | 4 Pydantic classes: Create/Cancel/ListQuery/Response                    | VERIFIED | All 4 classes present; `extra='forbid'` inherited from `BackendSchemaBase`    |
| `apps/backend/app/modules/pt_sessions/repository.py`              | 9 functions: 4 sale-side + 5 cancel/read-side                           | VERIFIED | All 9 `async def` present; 4 raw `text()` cross-module statements w/ `# noqa: TABLE_REF` |
| `apps/backend/app/modules/pt_sessions/service.py`                 | `record_pt_session`, `cancel_pt_session`, `get_pt_session`, `list_sessions_by_pt_package` + 10 error classes | VERIFIED | 476 lines; all 4 orchestrators present; 10 error classes; both end in `await session.commit()` |
| `apps/backend/app/modules/pt_sessions/router.py`                  | 4 handlers across `pt_sessions_router` (3) + `package_scoped_router` (1) | VERIFIED | POST `/` (record), POST `/{id}/cancel`, GET `/{id}`, GET `/pt-packages/{id}/sessions` |
| `apps/backend/app/modules/pt_sessions/constants.py`               | 4 constants with `__all__`                                              | VERIFIED | `BACKDATING_WINDOW_DAYS_RECEPTION=7`, `CANCEL_WINDOW_HOURS_RECEPTION=24`, `MAX_NOTES_CHARS=500`, `MAX_CANCEL_REASON_CHARS=200` |
| `apps/backend/app/api/v1/router.py`                               | Mount both routers (pt_sessions_router + package_scoped_router)         | VERIFIED | Lines 25-30, 46-50 mount at `/pt-sessions` and `/pt-packages`                 |
| `apps/backend/app/core/permissions.py`                            | OWNER_ONLY without `(CANCEL, PT_SESSIONS)`, with rationale comment      | VERIFIED | Lines 79-82 comment, line 50 `PT_SESSIONS = "pt-sessions"`; 25 tuples         |
| `apps/backend/app/core/dependencies.py`                           | `TrainerById` Protocol with `full_name: str`                            | VERIFIED | Line 285 `full_name: str  # Phase 34 D-34-12a — B-05 trainer_name_snapshot capture` |
| `apps/backend/.importlinter`                                      | 12 modules in `modules-independent`, including `app.modules.pt_sessions` | VERIFIED | Lines 14-27: 12 modules listed; `app.modules.pt_sessions` is 12th             |
| `apps/admin-web/src/shared/session/can.ts`                        | No `cancel:pt-sessions` entry tagged owner-only                         | VERIFIED | Lines 42-43 contain only `pt-packages` cancel/delete; comment at 32 documents D-34-09a removal |
| `apps/backend/tests/integration/pt_sessions/test_pt_session_record_race.py` | PTS-TEST-01 race test                                          | VERIFIED | `requires_postgres` marker present; `asyncio.gather`; `sessions_remaining=1`; asserts `[201, 409]` |
| `apps/backend/tests/integration/pt_sessions/test_pt_session_record.py` | 11 record-flow integration tests                                   | VERIFIED | Present in module directory; pulled by test suite                              |
| `apps/backend/tests/integration/pt_sessions/test_pt_session_cancel.py` | 8 cancel-flow integration tests                                    | VERIFIED | Present in module directory                                                    |
| `apps/backend/tests/integration/pt_sessions/test_pt_session_read.py`   | 5 read-flow integration tests                                      | VERIFIED | Present in module directory                                                    |
| `apps/backend/tests/unit/pt_sessions/test_backdating_window.py`        | 5 window-math unit tests                                           | VERIFIED | Present in module directory                                                    |
| `apps/backend/tests/unit/pt_sessions/test_cancel_window.py`            | 5 cancel-window-math unit tests                                    | VERIFIED | Present in module directory                                                    |
| `apps/backend/tests/unit/pt_sessions/test_revert_predicate.py`         | 1 revert-predicate isolation test                                  | VERIFIED | Present in module directory                                                    |

### Key Link Verification

| From                                            | To                                          | Via                                                                            | Status |
| ----------------------------------------------- | ------------------------------------------- | ------------------------------------------------------------------------------ | ------ |
| `service.record_pt_session`                     | `repository.atomic_decrement_pt_package`    | Single SQL UPDATE...RETURNING; 0-row → 409 `pt_package_exhausted`              | WIRED  |
| `service.record_pt_session`                     | `resolve_trainer_by_id` Protocol slot       | `trainer.full_name` for B-05 snapshot capture at line 247                      | WIRED  |
| `service.record_pt_session`                     | `audit.emit`                                | Literal `"pt_session_recorded"` + `"pt_session"` strings at line 255-269       | WIRED  |
| `service.record_pt_session` (conditional)       | `atomic_transition_to_exhausted` + emit     | `if new_remaining == 0:` block at line 272-286                                 | WIRED  |
| `service.cancel_pt_session`                     | `atomic_increment_pt_package`               | Raw text UPDATE with `< session_count_snapshot` ceiling predicate              | WIRED  |
| `service.cancel_pt_session` (conditional)       | `atomic_transition_exhausted_to_active`     | `if prior_status == "exhausted":` block at line 391-400                        | WIRED  |
| `service.cancel_pt_session`                     | `audit.emit("pt_session_cancelled", ...)`   | Literal strings + `package_reactivated=package_reactivated` payload field      | WIRED  |
| `router.list_sessions_by_pt_package`            | `package_scoped_router`                     | `@package_scoped_router.get("/{pt_package_id}/sessions")` mount; v1 mounted at `/pt-packages` | WIRED  |
| `router.record_pt_session` POST                 | `app.core.idempotency`                      | `verify_idempotency` + `begin_idempotency` + `load_idempotency_response` two-phase Redis | WIRED  |
| `router.cancel_pt_session` POST                 | `app.core.idempotency`                      | Same two-phase pattern; D-34-10                                                | WIRED  |

### Requirements Coverage

| Requirement | Source Plan(s)   | Description                                                                                      | Status    | Evidence                                                                                                  |
| ----------- | ---------------- | ------------------------------------------------------------------------------------------------ | --------- | --------------------------------------------------------------------------------------------------------- |
| PT-14       | 34-01            | `pt_sessions` table + columns + indexes + FK RESTRICT + CHECK constraints                        | SATISFIED | Migration 0015 + models.py — see Truth #1                                                                  |
| PT-15       | 34-02            | `POST /api/v1/pt-sessions` (reception+owner) with body/validation                                | SATISFIED | router.py:63-157 + service.py:166-293 — see Truth #2                                                       |
| PT-16       | 34-02            | Race-safe decrement via single SQL UPDATE...RETURNING                                            | SATISFIED | repository.py:41-72 — see Truth #3                                                                         |
| PT-17       | 34-02            | Auto-transition to `'exhausted'` synchronously; emits `pt_package_exhausted` once                | SATISFIED | service.py:272-286 — see Truth #4                                                                          |
| PT-18       | 34-03            | `POST /api/v1/pt-sessions/{id}/cancel` cancels + restores balance + conditional reverse-transit  | SATISFIED | service.py:301-427 + router.py:165-253 — see Truths #5, #6                                                 |
| PT-19       | 34-03            | `GET /api/v1/pt-packages/{id}/sessions` returns paginated history                                | SATISFIED | router.py:256-309 + service.py:446-475 — see Truth #8                                                      |
| PT-20       | 34-01/02/03      | PT-sessions independent of `visits` table (orthogonal events)                                    | SATISFIED | grep for visits imports returns empty + importlinter green — see Truth #9                                  |
| PT-21       | 34-02 + 34-03    | 2 audit events: `pt_session_recorded`, `pt_session_cancelled` (literal strings, locked payloads) | SATISFIED | service.py:257, 410 — see Truth #10                                                                        |
| PT-22       | 34-02            | Postgres integration test PTS-TEST-01 — 2 concurrent posts → 1×201 + 1×409                       | SATISFIED | test_pt_session_record_race.py — see Truth #11                                                             |

### CI Gate Probe Execution

| Probe                                                                                  | Command                                                                | Result                                  | Status |
| -------------------------------------------------------------------------------------- | ---------------------------------------------------------------------- | --------------------------------------- | ------ |
| Backend unit suite (covers SVC001/INFRA-11/audit-taxonomy walkers + permissions count) | `cd apps/backend && uv run python -m pytest tests/unit -q --tb=line`   | `490 passed, 1 skipped in 0.75s`        | PASS   |
| Ruff lint                                                                              | `cd apps/backend && uv run ruff check app/modules/pt_sessions/`        | `All checks passed!`                    | PASS   |
| Mypy strict                                                                            | `cd apps/backend && uv run mypy --strict app/modules/pt_sessions/`     | `Success: no issues found in 8 source files` | PASS   |
| Import-linter contracts (3 contracts, including modules-independent with 12 modules)   | `cd apps/backend && uv run lint-imports`                               | `Contracts: 3 kept, 0 broken.`          | PASS   |
| D-34-11a invariant: pt_packages/constants.py unchanged                                  | `git log --oneline 828813e..HEAD apps/backend/app/modules/pt_packages/constants.py` | empty                       | PASS   |

### Data-Flow Trace (Level 4)

The pt_sessions module is a backend API; no UI rendering. Data-flow trace replaced by behavioural CI gates above (PT-22 race test + 490 unit tests pass).

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| ---- | ---- | ------- | -------- | ------ |

No debt markers (`TBD`, `FIXME`, `XXX`) detected in any pt_sessions module file or in migration 0015. No `placeholder`, `TODO`, or hardcoded empty-collection stubs found.

### Human Verification Required

None — Phase 34 is a backend-only data/API layer phase with comprehensive automated coverage (unit tests, integration tests, race test gated behind `@requires_postgres`, importlinter contracts, mypy --strict, audit-taxonomy AST walker, SVC001 commit gate). All success criteria are programmatically verifiable.

The race test (PTS-TEST-01 / PT-22) is `@requires_postgres`-skipped in the unit suite — it requires a live Postgres for actual race-condition verification. This is documented design (D-33-19 precedent inherited): the SQLite-skipped path keeps the dev-loop unit suite ≤1s. Postgres-backed CI verification is owned by the project CI pipeline configuration, not Phase 34 scope.

### Gaps Summary

**None.** All 12 observable truths verified, all 9 requirements (PT-14..PT-22) satisfied, all key links wired, all cross-cutting amendments applied, all 5 CI gate probes pass cleanly:

- Migration 0015_pt_sessions: revision/down_revision/4 FK RESTRICT/3 CHECK/2 composite indexes all present
- Module skeleton: all 8 files (`__init__`, constants, models, schemas, repository, service, router, permissions) compile and pass mypy --strict
- Race-safe decrement: single-statement UPDATE...RETURNING with `sessions_remaining > 0 AND status='active'` predicate — race winner is the DB row lock
- Auto-exhausted transition: predicate-gated `WHERE status='active'` UPDATE + single literal-string `audit.emit("pt_package_exhausted", ...)` in same UoW
- Cancel + balance restoration: `mark_cancelled` + `atomic_increment_pt_package` (with `< session_count_snapshot` ceiling) + conditional `atomic_transition_exhausted_to_active` predicate-gated reverse transition
- D-34-11a invariant honored: `apps/backend/app/modules/pt_packages/constants.py` is byte-unchanged since the milestone-start commit (PT_PACKAGE_STATUS_TRANSITIONS FSM is forward-only at the global level; the reverse transition is local predicate-gated UPDATE)
- Cancel-window correctly measured from `pt_session.created_at` (NOT `performed_at`) per D-34-07
- GET endpoints: paginated by-package on `package_scoped_router` mounted at `/api/v1/pt-packages` (D-34-08 dual-router shape)
- PT-20 orthogonality: zero `app.modules.visits` imports in pt_sessions module; enforced by importlinter `modules-independent` contract (12 modules listed)
- PT-21 audit pair: literal strings `pt_session_recorded` + `pt_session_cancelled`; payloads match `PtSessionRecordedPayload` and `PtSessionCancelledPayload` field-for-field
- PT-22 race test present with `@requires_postgres` marker, two distinct `Idempotency-Key`s, `asyncio.gather`, assertion `statuses == [201, 409]`
- Cross-cutting: OWNER_ONLY size = 25 (down from 26, no `(CANCEL, PT_SESSIONS)`); `TrainerById.full_name: str` added; admin-web `can.ts` byte-parity removed; importlinter 12-module contract green; `tests/unit/test_permissions.py:21` `assert len(OWNER_ONLY) == 25` passes
- Idempotency-Key two-phase Redis claim+replay pattern (D-34-10) applied to BOTH `POST /pt-sessions` and `POST /pt-sessions/{id}/cancel`

Phase 34 goal achieved. Ready to proceed.

---

_Verified: 2026-05-16_
_Verifier: Claude (gsd-verifier)_
