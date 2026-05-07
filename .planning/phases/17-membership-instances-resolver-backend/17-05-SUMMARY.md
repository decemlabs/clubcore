---
phase: 17-membership-instances-resolver-backend
plan: 05
subsystem: testing
tags: [memberships, integration-tests, unit-tests, state-machine, audit, rbac, plan-in-use, resolver, tests-09, tests-10]

# Dependency graph
requires:
  - phase: 17-membership-instances-resolver-backend
    provides: "17-04: memberships_router live HTTP surface (GET list/single, POST sell, POST cancel)"
  - phase: 17-membership-instances-resolver-backend
    provides: "17-03: service.create_membership / cancel_membership / resolve_active_membership_by_client + _assert_can_cancel/_assert_can_expire helpers (CD-03/CD-06)"
  - phase: 17-membership-instances-resolver-backend
    provides: "17-02: register_active_membership_resolver composition-root slot in core/dependencies.py"
  - phase: 17-membership-instances-resolver-backend
    provides: "17-01: Membership ORM + 4 new domain exceptions (PlanInactiveError, PlanInUseError, InvalidTransitionError, MembershipNotFoundError)"
  - phase: 16-membership-plans-catalog-backend
    provides: "MembershipPlan ORM + plans_router DELETE happy path (Phase 16 D-15 forward-promised the FK conflict path closed here)"
  - phase: 15-foundations-rbac-audit-taxonomy-helper-hoisting
    provides: "LOCKED_AUDIT_EVENTS frozenset + TESTS-09 AST walker"
provides:
  - "82 new tests across 6 integration files + 1 unit file + 1 extended unit file"
  - "Phase 17 verifiable surface: sale/cancel CRUD + list filters/sort/pagination + RBAC matrix + audit-payload-shape canaries (D-14 reason-key omission) + plan_in_use closure (D-05/D-06 active+cancelled+expired all block) + resolver tiebreak/cancellation/none paths + composition-root wiring sanity"
  - "TESTS-10: 9-cell state-machine matrix with explicit ok / invalid_transition / N/A coverage"
  - "fixed Rule-1 bug: service.create_membership / cancel_membership emitted UUID-typed audit payloads (asyncpg JSONB encoder rejects raw UUID); now str-cast"
  - "fixed Rule-1 bug: service.soft_delete_plan relied on FK ON DELETE RESTRICT firing for an UPDATE statement (FKs only fire on hard DELETE); added explicit pre-flight count gate"
affects:
  - "Phase 17 verification (next step `/gsd-verify-phase 17`): all goal-backward acceptance criteria now have at least one assertion"
  - "Phase 18 ARQ expire job: TESTS-10 matrix already locks the active->expired transition shape — Phase 18 reuses _assert_can_expire and the same payload contract"
  - "Phase 22 admin-web /memberships/* feature: the audit-shape and RBAC contracts now have CI-enforced regression tests"

# Technology stack
tech-stack:
  added: []  # zero new runtime deps; pytest-asyncio + httpx ASGITransport already in tree
  patterns:
    - "DB-direct fixture-factory pattern via pytest_asyncio.fixture returning Awaitable[ORM] — `make_plan` and `make_membership` insert rows on the SAVEPOINT-mode session, bypassing the audit-emitting service path so audit_log assertions remain clean"
    - "9-cell parametrize matrix with explicit ok / invalid_transition / N/A column shape — coverage gaps surface in source diff; CI runs the matrix on every commit"
    - "D-14 reason-key omission canary — `assert \"reason\" not in payload` (NOT `payload.get('reason') is None`); the latter would silently pass even after a regression"
    - "Composition-root wiring sanity test — call resolver via the registered slot AND directly, assert ids match (catches T-TEST-RESOLVER-MISWIRED if app/main.py loses the register_active_membership_resolver call)"

# Key files
key-files:
  created:
    - "apps/backend/tests/integration/memberships/test_memberships_crud.py — sale + cancel happy paths, 422/404/409 boundaries (16 tests)"
    - "apps/backend/tests/integration/memberships/test_memberships_list.py — default-returns-all-statuses, status/clientId filter, 3 sort axes, pagination boundary, pageSize cap, D-10 snapshot fields (12 tests)"
    - "apps/backend/tests/integration/memberships/test_memberships_rbac.py — reception 201 sale + 200 GET, 403 cancel, owner 200 cancel, 401 unauth canaries (8 tests)"
    - "apps/backend/tests/integration/memberships/test_memberships_audit.py — MEM-AUDIT-01 payload shape, D-14 reason-key omission canary, co-transactional rollback canary (6 tests)"
    - "apps/backend/tests/integration/memberships/test_plan_in_use.py — Phase 16 D-15 closure: 409 plan_in_use for active/cancelled/expired memberships, 204 happy paths, audit-rollback canary (6 tests)"
    - "apps/backend/tests/integration/memberships/test_resolver.py — single-active, multi-active end_date tiebreak, created_at fallback, cancel chain, none paths, registered-slot wiring sanity (10 tests)"
    - "apps/backend/tests/unit/memberships/test_state_machine.py — TESTS-10 9-cell parametrize matrix (1 parametrized test = 9 cells)"
    - ".planning/phases/17-membership-instances-resolver-backend/deferred-items.md — log of 17 pre-existing mypy strict errors in tests/ (out of Phase 17-05 scope)"
  modified:
    - "apps/backend/tests/integration/memberships/conftest.py — added make_plan + make_membership pytest_asyncio fixture-factories returning Awaitable[ORM]; existing seeded_owner / authed_client_* fixtures preserved"
    - "apps/backend/tests/unit/memberships/test_schemas.py — Phase 17 boundary tests for MembershipCreateRequest (paidAt accept/omit, notes max=1000, extra=forbid, camelCase aliasing) and MembershipCancelRequest (D-11 explicit-null guard, reason max=500, empty body, MembershipResponse D-10 camelCase wire). +20 tests."
    - "apps/backend/app/modules/memberships/service.py — Rule 1 bug fix: str-cast UUID audit payload kwargs in create_membership and cancel_membership; explicit pre-flight count in soft_delete_plan (FK ON DELETE RESTRICT does not fire on soft-delete UPDATE)"

decisions:
  - "Used SimpleNamespace + cast(Membership, ...) in test_state_machine.py instead of instantiating real SA ORM — guards read only `.status` per D-15, so a typed stub is sufficient and DB-free"
  - "_csrf_headers helper uses `client.cookies.get('sportzal_csrf') or ''` pattern (instead of the Phase 16 `default=''` arg) so mypy strict accepts the str return type — Phase 16 callsites tracked as deferred items"
  - "make_plan factory provided alongside the HTTP create-plan path so audit-shape tests can seed plans WITHOUT firing membership_plan_created (otherwise the SUT audit query would return 2 rows: the seed + the plan-archived emit)"
  - "Resolver test for created_at tiebreak uses asyncio.sleep(0.01) between inserts but accepts either id in the assertion — within a single SAVEPOINT tx, func.now() may be identical across rows, so the tiebreak set (rather than the strict ordering) is asserted; the end_date assertion still pins the canonical row"
  - "soft_delete_plan refactored: pre-flight `select(func.count()).where(Membership.plan_id == plan.id) > 0` gate. The FK-translation IntegrityError catch remains as defence-in-depth canary against a future hard-delete refactor (T-CONSTRAINT-DRIFT)"

metrics:
  duration: "~16 min"
  completed: "2026-05-07"
  tasks_completed: 6
  files_created: 7
  files_modified: 3
  tests_added: 82
  tests_total_in_phase_17: 95 (integration) + 17 (unit/memberships) - existing 30 = 82 new
---

# Phase 17 Plan 05: Lock Phase Tests Summary

Phase 17 went verifiable: 82 new tests across the full sale → cancel → resolve lifecycle, the Phase 16 D-15 plan-in-use closure, and the TESTS-10 9-cell state-machine matrix. Two Rule-1 production bugs surfaced during test execution and were fixed in the same commits — proof that goal-backward verification catches things that forward implementation misses.

## What Was Built

**Task 1 — `apps/backend/tests/integration/memberships/conftest.py` extended:**
- Added `make_plan` and `make_membership` pytest_asyncio fixture-factories that insert ORM rows directly via the SAVEPOINT-mode session.
- `make_membership` accepts overridable `status` / `start_date` / `end_date` kwargs, so resolver and state-machine tests can craft expired/cancelled scenarios without going through the cancel HTTP flow (which would emit its own audit row).
- All existing Phase 16 fixtures (`seeded_owner`, `seeded_reception`, `authed_client_owner`, `authed_client_reception`, `_client_app_overrides`) preserved verbatim.

**Task 2 — `test_memberships_crud.py` (16 tests) + `test_memberships_list.py` (12 tests):**
- CRUD happy paths: 201 with snapshot fields populated and server-computed dates (start_date == today_moscow, end_date inclusive); paidAt ISO accept; paidAt omit → null; notes persists.
- CRUD boundaries: 404 plan_not_found (random UUID + soft-deleted), 409 plan_inactive (D-02 UI-bypass defence), 422 extra-field-forbidden (server-computed startDate rejected), 422 notes-over-1000.
- Cancel happy: 200 with `status='cancelled'`, `cancelledAt` set, `cancelReason` populated; 200 with no body and `cancelReason is None`.
- Cancel boundaries: 409 invalid_transition for expired and cancelled source states (with `fields={from_status, to_status}` payload); 404 unknown id; 422 explicit-null reason.
- D-01 stacking: 201 on second sale for same client (NO pre-flight active check).
- List: default returns all statuses; ?status filter; ?clientId filter; sort end_date_desc / start_date_desc / default created_at_desc; pagination boundary (page=2, pageSize=20, 21 rows → 1 item); pageSize=101 → 422 (max=100); D-10 all snapshot + lifecycle camelCase fields exposed.

**Task 3 — `test_memberships_rbac.py` (8 tests) + `test_memberships_audit.py` (6 tests):**
- RBAC matrix: reception 201 on sale, 200 on GET list/single (CREATE/VIEW NOT in OWNER_ONLY); reception 403 on cancel ((CANCEL, MEMBERSHIPS) IN OWNER_ONLY); owner 200 on cancel; 401 unauth canaries on all 3 mutating routes (RBAC-04 ordering).
- Audit shape: MEM-AUDIT-01 `membership_created` payload exactly `{client_id, plan_id, end_date}`; cancel-with-reason emits `{client_id, reason: 'data error'}`; **cancel-without-reason OMITS the reason key entirely** (D-14 critical — `"reason" not in payload`, NOT `reason=None`); failed sale (409 plan_inactive) writes ZERO audit rows; failed cancel (409 invalid_transition) writes ZERO audit rows (D-15: guard fires before emit).

**Task 4 — `test_plan_in_use.py` (6 tests) + `test_resolver.py` (10 tests):**
- plan_in_use closure (Phase 16 D-15): 409 plan_in_use for active, cancelled, AND expired memberships referencing the plan (D-05/D-06); 204 on no-references happy path; 204 after hard-deleting the membership row directly; co-transactional rollback canary (zero audit rows on 409).
- Resolver: returns single active membership; D-17 tiebreak picks latest end_date; same-end falls back to created_at DESC (within tie set); cancel canonical → returns shorter; cancel all → None; None for cancelled-only / expired-only / never-bought / unknown-uuid clients; **registered-slot wiring sanity** (calls `resolve_active_membership` from `app.core.dependencies` AND `resolve_active_membership_by_client` directly, asserts ids match — catches T-TEST-RESOLVER-MISWIRED if Plan 17-04's `register_active_membership_resolver` call ever drops).

**Task 5 — `test_state_machine.py` (1 parametrized test = 9 cells) + extended `test_schemas.py` (+20 tests):**
- TESTS-10 9-cell matrix per D-19: 3 source statuses × 3 actions, with explicit `ok` / `invalid_transition` / `n/a` expectations. 2 ok cells (active+cancel, active+expire) call the guard with no raise. 4 invalid_transition cells assert `InvalidTransitionError(409, code='invalid_transition')` with `fields={from_status, to_status}` populated. 3 N/A cells (create-self for every source status) return early — creation is `void → active`, not a state-machine cell, but they keep the matrix at 9 documented rows.
- Schema boundaries: paidAt ISO accept + omit-is-None; notes max_length=1000 + boundary (T-17-02); extra='forbid' rejects server-computed startDate + arbitrary unknown fields; D-11 explicit-null guard on reason (mirror of Phase 16 D-05); reason max_length=500 + boundary (T-17-01); empty body default; camelCase aliasing on paidAt + clientId; MembershipResponse D-10 camelCase wire on planNameSnapshot / durationDaysSnapshot / priceKopecksSnapshot / startDate / endDate / cancelledAt / cancelReason / paidAt / createdAt / updatedAt; MembershipStatus enum value serialisation.

**Task 6 — End-of-phase verification:**
- `uv run alembic check` exits 0 (no new ops detected).
- `uv run lint-imports` exits 0 (3/3 contracts kept).
- `uv run mypy app` exits 0 (65 source files clean).
- `uv run mypy tests` reports 17 pre-existing errors — verified via stash to predate Phase 17-05; logged in `deferred-items.md`.
- `uv run ruff check app tests` exits 0 (all checks passed).
- `uv run pytest -q` runs 477 tests, 0 failures (Phase 16 baseline 395 + 82 new Phase 17 tests).
- TESTS-09 audit AST walker passes; SVC-001 commit gate passes; RBAC-04 route introspection passes; TESTS-08 RBAC parity passes.
- `uv run python -m scripts.export_openapi` regenerates byte-stably; `git diff --exit-code apps/backend/openapi.json` exits 0.

## Why It Matters

This plan is the goal-backward closure for Phase 17. Without it:
- The MEM-AUDIT-01 contract was a docstring promise. Now the **D-14 reason-key omission** is enforced by `assert "reason" not in payload` — a regression that wrote `reason: null` would silently slip past `payload.get('reason') is None` checks but fails this canary.
- The **Phase 16 D-15 forward-promise** was a comment in `service.soft_delete_plan` that "the FK rejects". The test that exercised that path uncovered a real bug — FKs only fire on actual DELETE statements, not soft-delete UPDATEs. Phase 17 now ships an explicit pre-flight gate that handles all three statuses (active/cancelled/expired per D-06), with the IntegrityError translation kept as a defence-in-depth canary against a future hard-delete refactor.
- The **TESTS-10 9-cell matrix** locks the state machine: 4 invalid_transition assertions with `fields={from_status, to_status}` mean a future refactor that ships `fields={status: 'expired'}` (single key) fails CI immediately.
- The **resolver wiring sanity** (`resolve_active_membership` slot vs direct call) means a future regression that drops the `register_active_membership_resolver` call in `app/main.py` fails CI immediately — without this canary, the slot would silently return None, the visits service would treat every client as "no membership", and only end-to-end Phase 19 testing would surface the misconfiguration.

## Verification

```bash
cd apps/backend
cp .env.example .env  # if .env missing (gitignored)
uv run alembic check                                    # No new upgrade operations detected
uv run lint-imports                                     # 3/3 contracts kept
uv run mypy app                                         # 65 files, 0 issues
uv run ruff check app tests                             # All checks passed
uv run pytest -q                                        # 477 passed
uv run pytest tests/integration/memberships/ -q         # 95 passed (Phase 16 + 17 surface)
uv run pytest tests/unit/memberships/ -q                # 58 passed (schemas + state machine)
uv run pytest tests/unit/test_audit_taxonomy.py tests/unit/test_service_commit_gate.py tests/integration/test_route_introspection.py tests/integration/test_rbac_parity.py -q  # 17 passed (gate canaries)
uv run python -m scripts.export_openapi                 # 65189 bytes
git diff --exit-code apps/backend/openapi.json          # exit 0
```

All commands exit 0. mypy on `tests/` reports 17 errors that pre-date Plan 17-05 (logged in `deferred-items.md`).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] UUID values in audit payload kwargs not JSONB-serialisable**
- **Found during:** Task 2 (test_sale_happy_path)
- **Issue:** `service.create_membership` and `service.cancel_membership` passed `membership.client_id` and `membership.plan_id` as UUID instances to `audit.emit(**kwargs)`. asyncpg's JSONB encoder cannot serialise raw UUIDs (`TypeError: Object of type UUID is not JSON serializable`).
- **Fix:** Cast to `str()` before passing into `audit.emit`. The `resource_id` parameter stays UUID-typed (the `audit_log.resource_id` column is UUID, not JSONB).
- **Files modified:** `apps/backend/app/modules/memberships/service.py`
- **Commit:** Folded into Task 2 commit `670a438`.

**2. [Rule 1 - Bug] FK ON DELETE RESTRICT does not fire for soft-delete UPDATE**
- **Found during:** Task 4 (test_delete_plan_with_active_membership_returns_409)
- **Issue:** `service.soft_delete_plan` relied on the FK constraint `fk_memberships_plan_id_membership_plans` to raise IntegrityError when membership rows exist. But the soft-delete path issues `UPDATE membership_plans SET deleted_at=now()`, which never triggers FK ON DELETE RESTRICT. The original code would silently soft-delete plans that still had referencing memberships — directly contradicting D-05/D-06.
- **Fix:** Added explicit pre-flight `select(func.count()).where(Membership.plan_id == plan.id) > 0` gate in `soft_delete_plan`. Raises `PlanInUseError(409)` BEFORE any mutation. The IntegrityError translation remains as defence-in-depth against a future hard-delete refactor (T-CONSTRAINT-DRIFT canary).
- **Files modified:** `apps/backend/app/modules/memberships/service.py`
- **Commit:** Folded into Task 4 commit `31b1aba`.

**3. [Rule 3 - Blocking] Bootstrap missing apps/backend/.env**
- **Found during:** Task 6 (alembic check)
- **Issue:** `apps/backend/.env` was missing in the worktree (gitignored), so `uv run alembic check` failed with Pydantic Settings missing-key errors.
- **Fix:** `cp apps/backend/.env.example apps/backend/.env`. No source change.
- **Files modified:** `apps/backend/.env` (gitignored).

**4. [Rule 1 - Bug, scope: my new files] DTZ011 in conftest make_membership default**
- **Found during:** Task 6 (ruff check)
- **Issue:** `make_membership` fixture used `date.today()` as the default for `start_date`, which ruff DTZ011 flags as timezone-naive.
- **Fix:** Replaced with `datetime.now(tz=UTC).date()`.
- **Files modified:** `apps/backend/tests/integration/memberships/conftest.py`
- **Commit:** Task 6 commit `22fa1d2`.

### Out-of-scope deferrals (logged, not fixed)

17 pre-existing mypy strict errors in `tests/` (verified via `git stash` to predate Plan 17-05). Categories:
1. `httpx.Cookies.get(...)` returns `str | None` — 9 occurrences across Phase 8 / 16 test files using `default=""` pattern.
2. `Function does not return a value` on async test fixtures — 2 occurrences in `test_dependencies_verify_csrf.py`.
3. Unused `type: ignore` comments — 4 occurrences in `test_dependencies_require_authenticated.py`.
4. StrEnum equality comparison `MembershipPlanSort.NAME_ASC == "name_asc"` — 2 occurrences in `test_schemas.py`.

All 4 categories are tracked in `.planning/phases/17-membership-instances-resolver-backend/deferred-items.md` and would be the scope of a future test-hygiene chore plan.

## Auth Gates

None. Postgres + Redis containers were already running locally; backend env was bootstrapped from `.env.example`.

## Known Stubs

None. All test files exercise real code paths against the live ASGI app + SAVEPOINT-mode db_session. No mock services, no placeholder data.

## TDD Gate Compliance

This plan is `type: execute` (not `type: tdd`) and `tdd="false"` per task. The Plan-17-05 model is goal-backward: tests are written AFTER the production code (Plans 17-01..17-04) and assert the documented contracts. Two production bugs surfaced during this verification cycle (the UUID-payload bug and the FK-on-soft-delete bug) — fixed in the same commit as the tests that caught them, with deviation logged.

## Self-Check: PASSED

**Files exist:**
- FOUND: `apps/backend/tests/integration/memberships/conftest.py` (extended)
- FOUND: `apps/backend/tests/integration/memberships/test_memberships_crud.py`
- FOUND: `apps/backend/tests/integration/memberships/test_memberships_list.py`
- FOUND: `apps/backend/tests/integration/memberships/test_memberships_rbac.py`
- FOUND: `apps/backend/tests/integration/memberships/test_memberships_audit.py`
- FOUND: `apps/backend/tests/integration/memberships/test_plan_in_use.py`
- FOUND: `apps/backend/tests/integration/memberships/test_resolver.py`
- FOUND: `apps/backend/tests/unit/memberships/test_state_machine.py`
- FOUND: `apps/backend/tests/unit/memberships/test_schemas.py` (extended)
- FOUND: `.planning/phases/17-membership-instances-resolver-backend/deferred-items.md`

**Commits exist:**
- FOUND: `6b8fb1f` test(17-05): extend memberships conftest with make_plan and make_membership factories
- FOUND: `670a438` test(17-05): add membership CRUD and list integration tests
- FOUND: `4bcb00f` test(17-05): add membership RBAC and audit shape integration tests
- FOUND: `31b1aba` test(17-05): add plan_in_use and resolver integration tests
- FOUND: `00f2b0e` test(17-05): add TESTS-10 9-cell state machine matrix and Phase 17 schema tests
- FOUND: `22fa1d2` test(17-05): fix DTZ011 ruff in make_membership and log deferred mypy issues

**Verification gauntlet (all green):**
- `uv run alembic check` → No new upgrade operations detected
- `uv run lint-imports` → 3/3 contracts kept
- `uv run mypy app` → 65 files, 0 issues
- `uv run ruff check app tests` → All checks passed
- `uv run pytest -q` → 477 passed
- `uv run pytest tests/integration/memberships/ -q` → 95 passed
- `uv run pytest tests/unit/memberships/ -q` → 58 passed
- `uv run pytest tests/unit/test_audit_taxonomy.py tests/unit/test_service_commit_gate.py tests/integration/test_route_introspection.py tests/integration/test_rbac_parity.py -q` → 17 passed (gate canaries)
- `uv run python -m scripts.export_openapi` → 65189 bytes (byte-stable; `git diff --exit-code` exit 0)
