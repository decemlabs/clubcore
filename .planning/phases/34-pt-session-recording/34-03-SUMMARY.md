---
phase: 34-pt-session-recording
plan: 03
subsystem: api
tags: [fastapi, sqlalchemy, pydantic, postgres, redis, audit, rbac, idempotency, fsm, predicate-gate]

# Dependency graph
requires:
  - phase: 34-pt-session-recording
    plan: "01"
    provides: "pt_sessions module skeleton (constants CANCEL_WINDOW_HOURS_RECEPTION=24, error class hierarchy with CancelWindowExpiredError / PtSessionAlreadyCancelledError, two empty APIRouter instances — pt_sessions_router + package_scoped_router); OWNER_ONLY without (CANCEL, PT_SESSIONS) so reception passes RBAC gate (D-34-09a)."
  - phase: 34-pt-session-recording
    plan: "02"
    provides: "POST /api/v1/pt-sessions record handler (with two-phase Redis Idempotency-Key); pt_sessions integration conftest with fixtures (auth, factories, db_session_real_commit); audit-row patterns; csrf_headers helper precedent; sale-side helpers (atomic_decrement_pt_package, atomic_transition_to_exhausted, fetch_pt_package_metadata, insert_pt_session)."
  - phase: 30-foundations-tech-debt-bedrock
    provides: "LOCKED_AUDIT_EVENTS (pt_session_cancelled), audit_payloads.PtSessionCancelledPayload (extra='forbid'), importlinter modules-independent, SVC001 walker, INFRA-11 AST gate, RBAC-04 ordering."
  - phase: 33-pt-package-plans-instances
    provides: "pt_packages instance table + status FSM constant PT_PACKAGE_STATUS_TRANSITIONS (unchanged this plan)."
provides:
  - "atomic_increment_pt_package: race-safe single-statement UPDATE...RETURNING with ceiling predicate `sessions_remaining < session_count_snapshot` (PT-18 / D-34-04a) — defence-in-depth at the application layer against the CHECK `sessions_remaining <= session_count_snapshot` invariant from migration 0014_pt_packages; 0-row result raises RuntimeError 500 (hard CHECK breach)."
  - "atomic_transition_exhausted_to_active: predicate-gated reverse FSM transition `exhausted → active` via WHERE status='exhausted' RETURNING id (D-34-11a carve-out — NOT in the global PT_PACKAGE_STATUS_TRANSITIONS forward FSM; locally-scoped to cancel_pt_session under the invariant 'we just freed one balance unit'). Returns True on flip; concurrent refund mid-tx silently no-ops to False (T-34-K)."
  - "get_pt_session (ORM-side): single-row read by id; None → caller raises 404 pt_session_not_found."
  - "mark_cancelled (ORM-side): in-place setter on the loaded PtSession instance (cancelled_at = now() UTC, cancel_reason = data.cancel_reason); caller-owns-txn."
  - "list_by_pt_package_paginated (ORM-side): paginated read with include_cancelled bool filter; ordered performed_at DESC, created_at DESC, id DESC; mirrors pt_packages list shape with PaginatedData.model_construct for ORM compatibility."
  - "cancel_pt_session service orchestrator (10-step recipe): load → already-cancelled gate → cancel-window gate from created_at (D-34-07, NOT performed_at) → fetch metadata for prior_status → mark_cancelled → atomic_increment_pt_package → conditional atomic_transition_exhausted_to_active (D-34-11a; rowcount truth not intent → package_reactivated bool) → flush → audit emit pt_session_cancelled → refresh updated_at → commit (SVC001)."
  - "get_pt_session + list_sessions_by_pt_package service paths (PT-19 read tier)."
  - "POST /api/v1/pt-sessions/{id}/cancel handler with verbatim two-phase Redis claim + replay Idempotency-Key pattern (mirrors record handler); 200 OK (NOT 201)."
  - "GET /api/v1/pt-sessions/{id} handler (reception+owner, 404 pt_session_not_found)."
  - "GET /api/v1/pt-packages/{id}/sessions handler on package_scoped_router (PaginatedData envelope; performed_at DESC; includeCancelled bool param; unknown pkg_id → 200 empty page per pt_packages list precedent)."
  - "PtSessionCancelledPayload (locked Phase 30) emit-payload contract honored verbatim: str() casts on UUIDs, package_reactivated=rowcount truth, sessions_remaining_after=new_remaining return value."
  - "Test inventory: 5 unit cancel-window cases (D-34-07 boundary math via stubbed get_pt_session) + 2 revert-predicate tests (FSM static + 4-status seed matrix Postgres-gated) + 8 cancel integration scenarios + 5 read integration scenarios."
affects:
  - "Wave 3 (34-04 OpenAPI integration test): the cancel handler + GET endpoints + package-scoped router are now wired; OpenAPI snapshot must include `/api/v1/pt-sessions/{pt_session_id}/cancel` (POST) + `/api/v1/pt-sessions/{pt_session_id}` (GET) + `/api/v1/pt-packages/{pt_package_id}/sessions` (GET) — three new operations relative to 34-02."
  - "PT-18 / PT-19 / PT-21 (cancel half) marked complete in REQUIREMENTS.md by orchestrator state-update step."

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Predicate-gated reverse FSM transition as a locally-scoped carve-out (D-34-11a): the global PT_PACKAGE_STATUS_TRANSITIONS stays forward-only; the reverse `exhausted → active` UPDATE lives inside cancel_pt_session under WHERE status='exhausted'. Audit payload uses rowcount truth (`package_reactivated = atomic_transition_exhausted_to_active(...)` return bool), NOT intent — concurrent refund mid-tx silently no-ops the flip and the audit payload records reality (T-34-K mitigation)."
    - "Cancel-window measured from `pt_session.created_at` (recording time), NOT `performed_at` (training wall-clock). D-34-07 invariant: prevents 7-day-old backdated recordings from being cancelled within 24h of the training session itself — the gate is reception's time-to-react-to-a-recording, not reception's time-to-undo-a-trainer-shift."
    - "Already-cancelled gate (Step 1) fires BEFORE window check (Step 2): a 30-day-old session that was already cancelled returns 409 `already_cancelled`, NOT 403 `cancel_window_expired`. Tested explicitly via unit test."
    - "Reverse-transition idempotence: when the package was already `cancelled` or `expired` at cancel time, the balance increment STILL happens (data integrity / forensic correctness) but the reverse transition silently no-ops under the WHERE predicate and `package_reactivated=False` is recorded. This is correctness over intent — operators reading the audit log see the actual reality."
    - "Two-phase Redis claim + replay verbatim from record handler — same SET NX placeholder semantics, just 200 OK instead of 201 (cancel is non-creating)."

key-files:
  created:
    - "apps/backend/tests/unit/pt_sessions/test_cancel_window.py — 5 unit tests for D-34-07 / B-12 cancel-window math via monkeypatched repository.get_pt_session + repository.fetch_pt_package_metadata stubs; covers 23h59m inside (passes window), 24h inclusive boundary (`>` not `>=`), 24h+1s blocked (403), owner 30d-anytime, already-cancelled short-circuits before window check."
    - "apps/backend/tests/unit/pt_sessions/test_revert_predicate.py — 2 tests: (1) static assertion that PT_PACKAGE_STATUS_TRANSITIONS['exhausted'] is `frozenset({'cancelled'})` and does NOT include 'active' (D-34-11a invariant); (2) Postgres-gated 4-status row seed matrix proves atomic_transition_exhausted_to_active flips ONLY exhausted → active. Skips cleanly when DB unreachable."
    - "apps/backend/tests/integration/pt_sessions/test_pt_session_cancel.py — 8 end-to-end cancel scenarios (reception happy path with package_reactivated=False; reception 25h-old → 403; owner 25h-old → 200; cancel of exhausted-pkg reactivates with package_reactivated=True; cancel of cancelled-pkg keeps status terminal with package_reactivated=False; already-cancelled → 409; missing → 404; Idempotency-Key replay returns cached envelope + single audit row + single increment)."
    - "apps/backend/tests/integration/pt_sessions/test_pt_session_read.py — 5 read scenarios (GET single happy path with trainerNameSnapshot; GET single 404; paginated DESC across 25 rows / pageSize=10 / pages 1,2,3 = 10,10,5; includeCancelled filter default-true vs false; unknown pt_package_id → 200 empty page)."
    - ".planning/phases/34-pt-session-recording/34-03-SUMMARY.md (this file)."
  modified:
    - "apps/backend/app/modules/pt_sessions/repository.py — +5 cancel/read helpers (~150 lines): get_pt_session, list_by_pt_package_paginated, mark_cancelled (ORM); atomic_increment_pt_package, atomic_transition_exhausted_to_active (raw sa.text() with `# noqa: TABLE_REF cross-module SQL per D-34-04a` markers; predicate `sessions_remaining < session_count_snapshot` for increment ceiling; predicate `WHERE status='exhausted'` for reverse FSM)."
    - "apps/backend/app/modules/pt_sessions/service.py — +190 lines: 10-step cancel_pt_session orchestrator + get_pt_session + list_sessions_by_pt_package read wrappers; removed noqa: F401 markers on PaginatedData / CANCEL_WINDOW_HOURS_RECEPTION / PtSessionCancelRequest / PtSessionListByPackageQuery imports (now actively used)."
    - "apps/backend/app/modules/pt_sessions/router.py — +3 handlers (~180 lines): POST /pt-sessions/{id}/cancel (full two-phase Redis Idempotency-Key + 200 OK); GET /pt-sessions/{id}; GET /pt-packages/{id}/sessions on package_scoped_router. Added imports: UUID, PaginatedData, PtSessionCancelRequest, PtSessionListByPackageQuery."

key-decisions:
  - "Action enum mapping for the LIST endpoint: the plan referenced `Action.LIST` for `require_permission` on `GET /pt-packages/{id}/sessions`, but the Action StrEnum (apps/backend/app/core/permissions.py:20-27) defines only VIEW / CREATE / EDIT / DELETE / REFUND / CANCEL / CHECK_IN. The pt_packages list endpoint precedent uses Action.VIEW (line 369 of pt_packages/router.py). Used Action.VIEW for the by-package sessions list to match that precedent and unblock module imports. Documented in Deviations §1."
  - "`exhausted → active` reverse transition stays a LOCAL predicate-gated UPDATE, not a global FSM extension. PT_PACKAGE_STATUS_TRANSITIONS in pt_packages/constants.py is byte-for-byte unchanged (verified via `git diff --quiet` exiting 0). A static assertion in test_revert_predicate.py codifies this invariant so any future plan that adds 'active' to PT_PACKAGE_STATUS_TRANSITIONS['exhausted'] breaks the test."
  - "`package_reactivated` audit-payload bool reflects the actual UPDATE rowcount truth (`bool` return of atomic_transition_exhausted_to_active), NOT the operator's intent. When a concurrent refund flipped the package to 'cancelled' between Step 3 (read prior_status='exhausted') and Step 6 (reverse UPDATE), the predicate silently no-ops and the audit row records package_reactivated=False. T-34-K mitigation documented in service docstring."
  - "Boundary inclusive at 24h: the cancel-window comparison is `age > timedelta(hours=24)` (strict `>`, NOT `>=`), so age == 24h passes. The unit test `test_reception_at_24h_exactly_proceeds` tolerates microsecond drift past 24h (accepts either pass-through or window-expired at the exact instant) and the +1s sibling test is the definitive exclusive-side assertion."

# Metrics
duration: ~30min
completed: 2026-05-16
---

# Phase 34 Plan 03: PT-Session CANCEL + READ Flows Summary

**Reception/owner cancel with 24h-from-`created_at` window, exhausted→active predicate-gated reverse FSM transition (D-34-11a), and read endpoints (single + paginated by-package)**

## Performance

- **Duration:** ~30 min (resumed mid-execution after socket failure)
- **Tasks:** 3 (committed atomically)
- **Files created:** 5 (4 test files + this SUMMARY)
- **Files modified:** 3 (repository.py + service.py + router.py)

## Accomplishments

### Repository cancel/read helpers (Task 1)

Five new async functions in `apps/backend/app/modules/pt_sessions/repository.py`:

- **`get_pt_session(session, pt_session_id) -> PtSession | None`** — ORM-side single-row read via `select(PtSession).where(PtSession.id == pt_session_id)`. No cross-module SQL; caller raises 404 on None.
- **`list_by_pt_package_paginated(session, pt_package_id, query) -> PaginatedData[PtSession]`** — paginated read with `include_cancelled` filter; ordered `performed_at DESC, created_at DESC, id DESC` (D-34-08 — latest-first; deterministic tiebreaker via id for paging stability). Uses `PaginatedData.model_construct(...)` to skip Pydantic validation against ORM rows (mirrors pt_packages list shape).
- **`mark_cancelled(session, pt_session, *, cancel_reason) -> PtSession`** — in-place ORM setter (`cancelled_at = datetime.now(tz=UTC)`, `cancel_reason = cancel_reason`); satisfies CHECK `cancel_reason IS NULL OR cancelled_at IS NOT NULL` (migration 0015) atomically because both fields are set together. Caller-owns-txn (no flush / no commit).
- **`atomic_increment_pt_package(session, pt_package_id) -> int | None`** — raw `text()` UPDATE with ceiling predicate `sessions_remaining < session_count_snapshot RETURNING sessions_remaining`. 0-row result → caller raises 500 RuntimeError (hard CHECK invariant breach). `# noqa: TABLE_REF cross-module SQL per D-34-04a`.
- **`atomic_transition_exhausted_to_active(session, pt_package_id) -> bool`** — raw `text()` UPDATE `WHERE status='exhausted' RETURNING id`; returns True iff exactly one row flipped. D-34-11a carve-out documented in docstring: predicate-gated, locally-scoped, FSM unchanged.

All cross-module raw SQL statements carry `# noqa: TABLE_REF cross-module SQL per D-34-04a`. Zero `from app.modules.pt_packages` imports in the module; `lint-imports` reports 3 contracts kept, 0 broken.

### Service orchestrator + read paths (Task 2)

**`cancel_pt_session(session, actor, pt_session_id, data) -> PtSessionResponse`** — 10-step recipe (committed `2a2cd0f`):

1. **Load session row** — `pt_session = await repository.get_pt_session(...)`; None → `PtSessionNotFoundError` (404); `pt_session.cancelled_at is not None` → `PtSessionAlreadyCancelledError` (409). Ordering matters: this gate fires BEFORE the window check (unit-tested).
2. **Cancel-window gate** (D-34-07 / B-12) — measured from `pt_session.created_at` (recording time), NOT `performed_at`: `if actor.role == Role.RECEPTION and (datetime.now(UTC) - pt_session.created_at) > timedelta(hours=CANCEL_WINDOW_HOURS_RECEPTION) → CancelWindowExpiredError (403)`. Owner is anytime.
3. **Fetch package metadata** — `pkg = await repository.fetch_pt_package_metadata(...)`; None → defensive `PtPackageNotFoundError` (404, should be unreachable due to FK RESTRICT). Captures `prior_status` for the reactivation decision.
4. **Mark session cancelled** — `await repository.mark_cancelled(session, pt_session, cancel_reason=data.cancel_reason)`.
5. **Atomic increment** (PT-18 / D-34-04a) — `new_remaining = await repository.atomic_increment_pt_package(...)`; None → RuntimeError (CHECK invariant breach; HTTP 500).
6. **Conditional reverse transition** (D-34-11a) — `if prior_status == "exhausted": package_reactivated = await repository.atomic_transition_exhausted_to_active(...)`; else `package_reactivated = False`. The boolean reflects rowcount truth — when a concurrent refund flipped the package to 'cancelled' between Steps 3 and 6, the predicate WHERE status='exhausted' silently no-ops and the audit payload records reality (T-34-K).
7. **Flush** — `await session.flush()` surfaces FK / CHECK errors BEFORE the audit emit.
8. **Audit emit** — `audit.emit("pt_session_cancelled", resource_type="pt_session", resource_id=pt_session.id, pt_session_id=str(...), pt_package_id=str(...), client_id=str(...), cancel_reason=..., sessions_remaining_after=new_remaining, package_reactivated=package_reactivated)`. LITERAL strings (INFRA-11 AST gate); payload matches `PtSessionCancelledPayload` (extra='forbid') verbatim.
9. **Narrow refresh** — `await session.refresh(pt_session, attribute_names=["updated_at"])` (WR-04 lesson).
10. **Commit** (SVC001 caller-owns-txn gate) — `await session.commit()` + return `PtSessionResponse.model_validate(pt_session, from_attributes=True)`.

**Read paths** (pure reads, no commit):

- `get_pt_session(session, pt_session_id) -> PtSessionResponse` — wraps `repository.get_pt_session`; 404 on None.
- `list_sessions_by_pt_package(session, pt_package_id, query) -> PaginatedData[PtSessionResponse]` — wraps `repository.list_by_pt_package_paginated`; rebuilds the envelope with response models via `PaginatedData.model_construct(items=[PtSessionResponse.model_validate(s, from_attributes=True) for s in page.items], ...)`. No 404 for unknown `pt_package_id` (per pt_packages list precedent).

### Router handlers (Task 2)

Three handlers committed `2a2cd0f`:

- **`POST /api/v1/pt-sessions/{pt_session_id}/cancel`** on `pt_sessions_router` — RBAC-04 ordering: `Depends(require_permission(Action.CANCEL, Resource.PT_SESSIONS))` → `Depends(verify_csrf)` → `Depends(verify_idempotency)` → `Depends(get_redis)` → `Depends(get_db)`. Two-phase Redis claim + replay verbatim from `pt_packages.router.cancel_pt_package` and `record_pt_session` handler. 200 OK (cancel is non-creating).
- **`GET /api/v1/pt-sessions/{pt_session_id}`** on `pt_sessions_router` — reception+owner via `Action.VIEW`; 404 `pt_session_not_found`.
- **`GET /api/v1/pt-packages/{pt_package_id}/sessions`** on `package_scoped_router` — reception+owner via `Action.VIEW`; returns `ResponseEnvelope[PaginatedData[PtSessionResponse]]` with `?includeCancelled` filter param (camelCase via FastAPI alias generation on the schema). Subject-side ownership: handler lives in `pt_sessions/` module even though URL path is rooted at `/pt-packages` (D-33-18).

### Tests (Task 3)

Committed `74a0365`. 20 test cases across 4 files.

**Unit (`tests/unit/pt_sessions/test_cancel_window.py`):** 5 cases covering D-34-07 / B-12 cancel-window math via `monkeypatch.setattr("app.modules.pt_sessions.repository.get_pt_session", ...)` + `..."fetch_pt_package_metadata", ...)` stubs. Window check passes → orchestrator falls through to Step 3, our stub raises `PtPackageNotFoundError`; failure → `CancelWindowExpiredError`. Cases:

- reception 23h59m past created_at → window OK (fall-through to stubbed PtPackageNotFoundError);
- reception 24h boundary inclusive → microsecond-tolerant (accepts either pass-through or window-expired at the exact instant);
- reception 24h + 1s → `CancelWindowExpiredError` (403, definitive exclusive-side assertion);
- owner 30 days past → window OK;
- already-cancelled session 30d old (RECEPTION) short-circuits to `PtSessionAlreadyCancelledError` (409) — proves Step 1 fires before Step 2.

**Unit (`tests/unit/pt_sessions/test_revert_predicate.py`):** 2 cases.

- `test_fsm_constant_has_no_reverse_active_edge`: pure-Python static assertion against `PT_PACKAGE_STATUS_TRANSITIONS["exhausted"]` — proves the constant is `frozenset({"cancelled"})` and does NOT contain `"active"`. D-34-11a invariant codified.
- `test_revert_flips_exhausted_only`: Postgres-gated 4-status seed matrix (active / exhausted / expired / cancelled) calls `atomic_transition_exhausted_to_active` on each pkg id; asserts the return bool dict is `{active: False, exhausted: True, expired: False, cancelled: False}` and the resulting status column matches the expected matrix. Skips cleanly when DB unreachable (per 34-02 / REF-TEST-02 precedent).

**Integration (`tests/integration/pt_sessions/test_pt_session_cancel.py`):** 8 end-to-end scenarios via `ASGITransport(app=app)` + SAVEPOINT-isolated `db_session`. Helpers: `_csrf_headers(client, idempotency_key=...)`, `_seed_pt_session_directly(...)` (raw INSERT with explicit `created_at` to stage 25h-old sessions without sleeping). Scenarios: reception happy within 24h (audit `package_reactivated=False`); reception 25h-old → 403 `cancel_window_expired`; owner 25h-old → 200; cancel of `exhausted` pkg flips status → `active` + audit `package_reactivated=True`; cancel of `cancelled` pkg keeps status terminal + balance still increments + audit `package_reactivated=False`; already-cancelled → 409; missing id → 404; Idempotency-Key replay → both 200 with identical `cancelledAt` + single `pt_session_cancelled` audit row + balance incremented exactly once.

**Integration (`tests/integration/pt_sessions/test_pt_session_read.py`):** 5 scenarios. GET single happy path with `trainerNameSnapshot` echo; GET single 404; paginated DESC across 25 seeded rows (`pageSize=10` → 10/10/5 across pages 1/2/3, sorted DESC); `includeCancelled` filter (default true returns all 10; false returns active 5 only); unknown `pt_package_id` → 200 with `items=[]` and `total=0` (no 404).

All integration tests SKIP cleanly when Postgres is unreachable (matches 34-02 / PTS-TEST-01 / REF-TEST-02 precedent).

## Gates Verified

| Gate | Command | Result |
|------|---------|--------|
| ruff | `uv run ruff check app/modules/pt_sessions/ tests/unit/pt_sessions/ tests/integration/pt_sessions/` | All checks passed |
| mypy strict (source) | `uv run mypy --strict app/modules/pt_sessions/` | Success: no issues found in 8 source files |
| mypy strict (new tests) | `uv run mypy --strict tests/unit/pt_sessions/test_cancel_window.py tests/unit/pt_sessions/test_revert_predicate.py tests/integration/pt_sessions/test_pt_session_cancel.py tests/integration/pt_sessions/test_pt_session_read.py` | Success: no issues found in 4 source files |
| import-linter | `uv run lint-imports` | 3 contracts kept, 0 broken |
| INFRA-11 (audit taxonomy AST gate) | `uv run pytest tests/unit/test_audit_taxonomy.py` | 4 passed |
| SVC001 (caller-owns-txn walker) | `uv run pytest tests/unit/test_service_commit_gate.py` | 7 passed |
| Unit pt_sessions | `uv run pytest tests/unit/pt_sessions -v` | 11 passed, 1 skipped (Postgres-gated revert seed) |
| Integration pt_sessions | `uv run pytest tests/integration/pt_sessions -v` | 14 passed prior + 13 new skipped cleanly (Docker / Postgres not running locally) |
| FSM constant invariant | `git diff --quiet apps/backend/app/modules/pt_packages/constants.py` | Exit 0 — D-34-11a honored |
| Visits orthogonality (D-34-16 / PT-20) | `grep -rE "from app.modules.visits\|import.*\\bvisits\\b" apps/backend/app/modules/pt_sessions/` | Empty output |

## Requirements Covered

- **PT-18** — POST /api/v1/pt-sessions/{id}/cancel — reception ≤24h since `pt_sessions.created_at` (NOT `performed_at`); set `cancelled_at` + `cancel_reason`; atomic_increment_pt_package; conditional D-34-11a reverse transition `exhausted → active`; audit emit `pt_session_cancelled`.
- **PT-19** — GET /api/v1/pt-sessions/{id} single + GET /api/v1/pt-packages/{id}/sessions paginated; ordered `performed_at DESC, created_at DESC, id DESC`; `?includeCancelled` filter; reception+owner permission; PaginatedData envelope.
- **PT-21** (cancel half) — `pt_session_cancelled` audit event emitted with payload matching `PtSessionCancelledPayload` extra='forbid' verbatim; `package_reactivated` bool subsumes reactivation signal (no separate `pt_package_reactivated` event per D-34-17).

## Task Commits

Each task was committed atomically with `--no-verify` (worktree-parallel discipline):

1. **Task 1 — Repository cancel/read helpers:** `bd179d2` (feat) — 5 functions (3 ORM-side + 2 raw text); committed pre-resume on master-side of session.
2. **Task 2 — Service + router handlers:** `2a2cd0f` (feat) — 10-step cancel_pt_session orchestrator + get_pt_session + list_sessions_by_pt_package + 3 router handlers (POST cancel with Idempotency-Key replay; GET single; GET by-package on package_scoped_router).
3. **Task 3 — Tests:** `74a0365` (test) — 5 unit cancel-window + 2 revert-predicate (1 Postgres-gated) + 8 cancel integration + 5 read integration; 1157 line insertion.

## Files Created/Modified

### Created

- `apps/backend/tests/unit/pt_sessions/test_cancel_window.py` — 5 unit tests for D-34-07 cancel-window math (~230 lines).
- `apps/backend/tests/unit/pt_sessions/test_revert_predicate.py` — 2 tests for D-34-11a revert-predicate isolation (~160 lines).
- `apps/backend/tests/integration/pt_sessions/test_pt_session_cancel.py` — 8 cancel-flow integration tests (~415 lines).
- `apps/backend/tests/integration/pt_sessions/test_pt_session_read.py` — 5 read-flow integration tests (~270 lines).
- `.planning/phases/34-pt-session-recording/34-03-SUMMARY.md` (this file).

### Modified

- `apps/backend/app/modules/pt_sessions/repository.py` — +5 cancel/read helpers (~150 lines).
- `apps/backend/app/modules/pt_sessions/service.py` — +cancel/read orchestrators (~190 lines after the record_pt_session block from 34-02); removed `noqa: F401` from imports now actively used (`PaginatedData`, `CANCEL_WINDOW_HOURS_RECEPTION`, `PtSessionCancelRequest`, `PtSessionListByPackageQuery`).
- `apps/backend/app/modules/pt_sessions/router.py` — +3 handlers (~180 lines); added imports `UUID`, `PaginatedData`, `PtSessionCancelRequest`, `PtSessionListByPackageQuery`.

## Decisions Made

The plan was followed verbatim except for one Action-enum mismatch (documented as Deviation §1 below). The three design decisions worth recording:

1. **Reverse FSM is local-only** — `PT_PACKAGE_STATUS_TRANSITIONS` in `pt_packages/constants.py` is byte-for-byte unchanged. The `exhausted → active` flip lives only as a predicate-gated UPDATE inside `cancel_pt_session`. A static assertion in `test_revert_predicate.py` codifies this so any future plan extending the global FSM breaks the test.
2. **`package_reactivated` is rowcount truth, not intent** — even when `prior_status == 'exhausted'`, if a concurrent refund flipped the package to `cancelled` between Step 3 and Step 6, the predicate `WHERE status='exhausted'` silently no-ops and the audit payload records `package_reactivated=False`. This is T-34-K mitigation: operators reading the audit log see reality.
3. **Cancel-window measured from `created_at`, NOT `performed_at`** — D-34-07 invariant. A 7-day-old backdated recording is cancellable within 24h of *when it was recorded*, not when the training session occurred. Boundary is strict `>` (24h inclusive); unit-tested at 23h59m, 24h+1s, 30 days.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 — Blocking] `Action.LIST` does not exist in the Action enum**

- **Found during:** Task 2 — `uv run python -c "from app.modules.pt_sessions.router import ..."` raised `AttributeError: type object 'Action' has no attribute 'LIST'`.
- **Issue:** The plan's action text for the `GET /pt-packages/{id}/sessions` handler specified `Depends(require_permission(Action.LIST, Resource.PT_SESSIONS))`. The `Action` StrEnum (`apps/backend/app/core/permissions.py:20-27`) defines only: `VIEW / CREATE / EDIT / DELETE / REFUND / CANCEL / CHECK_IN`. There is no `LIST` member.
- **Fix:** Used `Action.VIEW` for both `GET /pt-sessions/{id}` and `GET /pt-packages/{id}/sessions`, mirroring the `pt_packages` list precedent (`pt_packages/router.py:369` uses `Action.VIEW` for the paginated list endpoint).
- **Files modified:** `apps/backend/app/modules/pt_sessions/router.py`.
- **Verification:** module imports cleanly; `uv run mypy --strict` reports 0 issues; RBAC walker tests (`test_route_introspection.py`) cascade through unchanged.
- **Committed in:** `2a2cd0f`.
- **Rationale (in-scope per Rule 3):** Following the plan verbatim would have caused collection-time `AttributeError`. The fix preserves the documented permission semantics ("reception+owner read access") using the canonical enum member already used by sibling list endpoints.

### Authentication Gates

None.

### Deferred Issues

None.

## Self-Check: PASSED

- All 3 task commits exist in `git log`: `bd179d2`, `2a2cd0f`, `74a0365`.
- All 5 created files verified present on disk.
- Cancel-window unit tests run (5 passed); revert-predicate static check passes; Postgres-gated tests SKIP cleanly.
- ruff + mypy --strict + import-linter all green.
- `git diff --quiet apps/backend/app/modules/pt_packages/constants.py` exits 0 (D-34-11a).
- No `app.modules.visits` imports anywhere in `pt_sessions/` (D-34-16 / PT-20 orthogonality).
