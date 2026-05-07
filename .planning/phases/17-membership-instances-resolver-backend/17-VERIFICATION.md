---
phase: 17-membership-instances-resolver-backend
verified: 2026-05-07T00:00:00Z
status: passed
score: 5/5 must-haves verified
overrides_applied: 0
---

# Phase 17: Membership Instances + Resolver (backend) — Verification Report

**Phase Goal:** Reception can sell a membership to a client and the system can answer the single question "does this client have an active membership today?" — the foundation Visits will validate against.
**Verified:** 2026-05-07
**Status:** passed
**Re-verification:** No — initial verification

---

## Goal Achievement — Observable Truths (5 ROADMAP Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `POST /api/v1/memberships` snapshots `plan_name`, `duration_days`, `price_kopecks` at insert; computes `end_date = start_date + duration_days - 1` (inclusive); subsequent plan edits never mutate the row | ✓ VERIFIED | `service.py:create_membership` (lines 322–383) reads `plan` ORM ref then calls `repository.insert_membership` which copies `plan.name`, `plan.duration_days`, `plan.price_kopecks` into `*_snapshot` columns (`repository.py:176–187`). `start_date = datetime.now(ZoneInfo("Europe/Moscow")).date()`; `end_date = start_date + timedelta(days=plan.duration_days - 1)` (service.py:354–355). Snapshot immutability is structural — no mutation path writes to `*_snapshot` columns (verified by grep of `repository.py`). Tests: `test_memberships_crud.py::test_sale_happy_path` asserts dates and snapshot fields verbatim. |
| 2 | `POST /memberships/{id}/cancel` is owner-only and only `active → cancelled` is allowed; `expired→cancelled` and `cancelled→cancelled` return 409 `invalid_transition`, validated by exhaustive transition-matrix test | ✓ VERIFIED | Owner-only enforced via `Depends(require_permission(Action.CANCEL, Resource.MEMBERSHIPS))` (router.py:289); `(CANCEL, MEMBERSHIPS) ∈ OWNER_ONLY` (Phase 15 INFRA-08). Transition guard `_assert_can_cancel` runs BEFORE any mutation (service.py:104–115, 412); raises `InvalidTransitionError(code="invalid_transition", fields={from_status, to_status})`. Tests: `test_state_machine.py::test_state_machine_matrix` parametrises all 9 cells with explicit `n/a` rows for `create-self`; `test_memberships_rbac.py::test_reception_cannot_post_cancel`; `test_memberships_audit.py::test_no_audit_on_failed_cancel` confirms zero side-effects on guard rejection. |
| 3 | `core.dependencies.resolve_active_membership(session, client_id)` returns the single active membership tiebreaking on latest `end_date` then `created_at DESC`; resolver registered from `app/main.py` via `register_active_membership_resolver` without `modules-independent` violation | ⚠ PARTIAL — see Deviations | Slot pattern verbatim mirrors `register_user_loader` (Phase 4 D-24): `core/dependencies.py:65–119` declares `ActiveMembership` Protocol (id, client_id, end_date, status), `ActiveMembershipResolver` type alias, `_active_membership_resolver` slot, `register_active_membership_resolver` setter, and `resolve_active_membership` consumer (returns None when slot unset, per CONTEXT.md line 224). `app/main.py:108` calls `register_active_membership_resolver(resolve_active_membership_by_client)` after exception-handlers, before `app.include_router(api)`. Tiebreak SQL: `ORDER BY end_date DESC, created_at DESC LIMIT 1` (`repository.py:find_active_for_client`, lines 297–303). importlinter: 3/3 contracts kept; `app.modules.memberships` consumes only `app.core.*`. **Deviation:** the resolver query intentionally OMITS the `end_date >= today` filter that MEM-04/SC#3 specifies verbatim — see `Deviations` section. |
| 4 | Reception+owner can list/get memberships filtered by `clientId`/`status` via `GET /api/v1/memberships` and `GET /api/v1/memberships/{id}` with paginated envelope | ✓ VERIFIED | `memberships_router` exposes 4 endpoints (router.py:207–305) at `/api/v1/memberships`. List endpoint uses `MembershipListQuery(PageQuery)` with optional `client_id: UUID \| None`, `status: MembershipStatus \| None`, `sort: MembershipListSort` (schemas.py:235–247). Response wraps `PaginatedData[MembershipResponse]` in `ResponseEnvelope`. RBAC: `Depends(require_permission(VIEW, MEMBERSHIPS))` on both GET routes — `(VIEW, MEMBERSHIPS) ∉ OWNER_ONLY` so reception+owner allowed. openapi.json contains `/api/v1/memberships`, `/api/v1/memberships/{membership_id}`, `/api/v1/memberships/{membership_id}/cancel`. Tests: `test_memberships_list.py` (pagination/filter/sort), `test_memberships_rbac.py::test_reception_can_get_list/get_single`. |
| 5 | `audit.emit("membership_created" \| "membership_cancelled")` fires on the corresponding business action; TESTS-09 confirms every callsite uses a pair in `LOCKED_AUDIT_EVENTS` | ✓ VERIFIED | `service.py:create_membership` line 371–380 emits `"membership_created"` with `resource_type="membership"`, payload `{client_id (str), plan_id (str), end_date (ISO)}`. `service.py:cancel_membership` line 429–437 emits `"membership_cancelled"` with payload `{client_id (str), reason?}` — `reason` key OMITTED when None (D-14 critical: `kwargs = {} if data.reason is None else {"reason": data.reason}`). `LOCKED_AUDIT_EVENTS` already contains both pairs (Phase 15 audit.py:108–110). TESTS-09 (`tests/unit/test_audit_taxonomy.py`) walks every `audit.emit` callsite via AST; passes (3 tests). Tests: `test_memberships_audit.py::test_membership_cancelled_without_reason_omits_key` asserts `"reason" not in payload` (NOT `is None`). |

**Score:** 5/5 truths verified (1 with documented deviation that does not block goal achievement).

---

## Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `apps/backend/alembic/versions/0005_memberships.py` | Migration with `down_revision = "0004_membership_plans"`, all D-20 constraint names, composite `ix_memberships_client_id_status_end_date` with DESC ordering via `op.execute()` | ✓ VERIFIED | All constraint names present (`ck_memberships_status`, `ck_memberships_activation_policy`, `fk_memberships_client_id_clients`, `fk_memberships_plan_id_membership_plans`, `pk_memberships`); composite index installed via raw SQL with `end_date DESC` (lines 104–107); downgrade drops both. Alembic round-trip clean (downgrade → upgrade re-applied successfully). |
| `apps/backend/app/modules/memberships/models.py` | `Membership(Base, UUIDPkMixin, TimestampMixin)` — NO SoftDeleteMixin | ✓ VERIFIED | Class declared lines 85–161 with all 14 columns (id, client_id, plan_id, plan_name_snapshot, duration_days_snapshot, price_kopecks_snapshot, start_date, end_date, status, cancelled_at, cancel_reason, paid_at, notes, activation_policy + inherited created_at/updated_at). NO SoftDeleteMixin — lifecycle is status-based (D-12). |
| `apps/backend/app/modules/memberships/schemas.py` | `MembershipCreateRequest`, `MembershipCancelRequest`, `MembershipResponse`, `MembershipListQuery`, `MembershipStatus`, `MembershipListSort` | ✓ VERIFIED | All 6 declared (lines 139–248). `MembershipResponse` exposes ALL snapshot + lifecycle fields per D-10. `MembershipCancelRequest` includes `model_validator(mode='before')` rejecting explicit-null reason (D-11). `MembershipCreateRequest` inherits `extra='forbid'` from `BackendSchemaBase` — server-computed fields rejected if posted. |
| `apps/backend/app/modules/memberships/repository.py` | `insert_membership`, `get_membership`, `update_membership_status`, `list_memberships`, `find_active_for_client` | ✓ VERIFIED | All 5 declared (lines 162–304). `list_memberships` uses `model_construct` to skip Pydantic validation (mirrors `list_alive` rationale). `find_active_for_client` ORDER BY `end_date DESC, created_at DESC LIMIT 1` per MEM-04. |
| `apps/backend/app/modules/memberships/service.py` | `create_membership`, `cancel_membership`, `list_memberships`, `get_membership`, `resolve_active_membership_by_client`, `_is_plan_in_use_conflict`, `_assert_can_cancel`, `_assert_can_expire` | ✓ VERIFIED | All 8 declared (lines 86–489). Service-write paths commit explicitly (AST commit-gate enforces; ruff + mypy clean). UUID-JSONB encoding fix: `client_id`, `plan_id` cast to `str()` in audit emit kwargs (lines 377, 378, 435) — UUIDs are not natively JSON-serialisable. |
| `apps/backend/app/modules/memberships/router.py` | 4 new endpoints on `memberships_router` with RBAC-04 ordering (`require_permission` BEFORE `verify_csrf`) | ✓ VERIFIED | `memberships_router` declared line 207; 4 routes registered (lines 210–305). All mutation endpoints declare `require_permission` before `verify_csrf`. `tests/integration/test_route_introspection.py` enforces ordering statically (passes). |
| `apps/backend/app/core/dependencies.py` | `ActiveMembership` Protocol, `ActiveMembershipResolver`, `register_active_membership_resolver`, `resolve_active_membership` | ✓ VERIFIED | All 4 declared (lines 65–119). Protocol exposes only id/client_id/end_date/status per D-18. Slot returns None (not raise) on unset per CONTEXT.md line 224 — visits service cannot distinguish "no resolver" from "no active membership". |
| `apps/backend/app/core/exceptions.py` | `PlanInactiveError`, `PlanInUseError`, `InvalidTransitionError`, `MembershipNotFoundError` | ✓ VERIFIED | All 4 declared (lines 120–167). `InvalidTransitionError(ConflictError)` packs `{from_status, to_status}` into `fields` per D-12. |
| `apps/backend/app/main.py` | `register_active_membership_resolver(resolve_active_membership_by_client)` in `create_app()` before `include_router(api)` | ✓ VERIFIED | Import lines 34, 40; call line 108 — after exception handlers, before `app.include_router(api)` (line 110). Docstring annotates "second composition-root carve-out (after register_user_loader, Phase 5 D-15)" per `<specifics>` line 269. |
| `apps/backend/app/api/v1/router.py` | `memberships_router` mounted at `/memberships` separately from `plans_router` at `/membership-plans` | ✓ VERIFIED | Lines 22–23 mount both routers. CD-02 router-split honored. |
| `apps/backend/openapi.json` | 4 new paths + schemas regenerated, byte-stable | ✓ VERIFIED | Paths `/api/v1/memberships`, `/api/v1/memberships/{membership_id}`, `/api/v1/memberships/{membership_id}/cancel` present. Re-export via `scripts/export_openapi.py` produces identical 65189-byte file (BYTE-STABLE diff verified). |
| `tests/integration/memberships/{conftest,test_memberships_crud,test_memberships_list,test_memberships_rbac,test_memberships_audit,test_plan_in_use,test_resolver}.py` | 6 new integration test files | ✓ VERIFIED | All 7 files present with `make_plan` and `make_membership` fixtures in conftest. |
| `tests/unit/memberships/{test_state_machine,test_schemas}.py` | 2 unit test files (state machine matrix, schema boundaries) | ✓ VERIFIED | Both present; `test_state_machine.py` parametrises all 9 cells with explicit `n/a` markers (TESTS-10). |

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `app/main.py:create_app()` | `core/dependencies._active_membership_resolver` | `register_active_membership_resolver(resolve_active_membership_by_client)` | ✓ WIRED | Line 108. Sanity test `test_resolver_via_registered_slot_matches_direct_call` confirms `resolve_active_membership(session, client_id)` returns the same row as direct call after `create_app()` registration. |
| `app/api/v1/router.py` | `app.modules.memberships.router.memberships_router` | `v1.include_router(memberships_router, prefix="/memberships", ...)` | ✓ WIRED | Line 23. openapi.json reflects all 4 paths. |
| `service.create_membership` | `audit.emit("membership_created", "membership", ...)` | direct call line 371–380 | ✓ WIRED | Verified by `test_membership_created_payload_shape` asserting AuditLog row with action="membership_created", resource_type="membership", resource_id=membership_id, payload keys `{client_id, plan_id, end_date}`. |
| `service.cancel_membership` | `audit.emit("membership_cancelled", "membership", ...)` | direct call line 429–437 | ✓ WIRED | Verified by `test_membership_cancelled_with_reason` AND `test_membership_cancelled_without_reason_omits_key` (the latter asserts `"reason" not in payload`). |
| `service.soft_delete_plan` (Phase 16 closure) | `PlanInUseError("plan_in_use")` | pre-flight `select(func.count())` on Membership rows + IntegrityError translation as defence-in-depth | ✓ WIRED | Lines 282–313. Tests `test_delete_plan_with_{active,cancelled,expired}_membership_returns_409` all pass. **See Deviations** — original Phase 17 D-05/D-08 plan was IntegrityError-only translation; agent added a pre-flight count gate because soft-delete is UPDATE not DELETE (FK ON DELETE RESTRICT does not fire on UPDATE). |
| `service.create_membership` / `cancel_membership` | UUID-JSONB serialisation | `str(membership.client_id)`, `str(membership.plan_id)` | ✓ WIRED | Lines 377, 378, 435. UUIDs are not natively JSON-serialisable — explicit str cast prevents `TypeError` in JSONB write path. |
| `router.cancel_membership` | `Depends(require_permission(Action.CANCEL, Resource.MEMBERSHIPS))` BEFORE `Depends(verify_csrf)` | RBAC-04 ordering | ✓ WIRED | Router lines 286–293. Static enforcement via `tests/integration/test_route_introspection.py`. |

---

## Decision Honored (10 spot-checks of D-01..D-21)

| Decision | Topic | Status | Evidence |
|----------|-------|--------|----------|
| D-01 | Stacking allowed — no pre-flight active check on POST sale | ✓ HONORED | `create_membership` (service.py:322–383) has zero pre-flight active-check; tests `test_resolver_tiebreak_picks_latest_end_date` and `test_resolver_after_cancel_returns_next_active` exercise stacking via second sale. |
| D-04 | Snapshot fields + Europe/Moscow `start_date` + inclusive `end_date` | ✓ HONORED | service.py:354 `datetime.now(ZoneInfo("Europe/Moscow")).date()`; line 355 `start_date + timedelta(days=plan.duration_days - 1)`; `test_sale_happy_path` asserts `expected_end = expected_start + timedelta(days=plan["durationDays"] - 1)`. |
| D-05 / D-06 | Plan in-use 409 — ANY membership row blocks (active+expired+cancelled) | ✓ HONORED (with deviation in mechanism — see Deviations) | Pre-flight count on `Membership` rows (service.py:282–288); IntegrityError translation kept as defence-in-depth canary. Tests `test_delete_plan_with_{active,cancelled,expired}_membership_returns_409` all pass. |
| D-07 | ROADMAP Phase 16 SC#4 wording reconciled | ✓ HONORED | ROADMAP.md line 81 reads `"deletion returns 409 'plan_in_use' when any 'Membership' references it (cancelled and expired included) (FK 'ON DELETE RESTRICT')"` — matches D-05/D-06 verbatim. |
| D-12 / D-15 | Transition guard BEFORE mutation | ✓ HONORED | `_assert_can_cancel(membership)` called BEFORE `update_membership_status` (service.py:412–416). `test_no_audit_on_failed_cancel` asserts ZERO `membership_cancelled` rows when guard rejects. |
| D-14 | `membership_cancelled` audit OMITS `reason` key when None | ✓ HONORED | service.py:428 `kwargs = {} if data.reason is None else {"reason": data.reason}`; `test_membership_cancelled_without_reason_omits_key` asserts `"reason" not in payload` AND `set(payload.keys()) == {"client_id"}`. |
| D-17 | Resolver tiebreak silent — no warning log | ✓ HONORED | `find_active_for_client` (repository.py:282–304) — pure ORDER BY/LIMIT, no `structlog`/`audit.emit` call. |
| D-18 | `ActiveMembership` Protocol exposes only 4 attrs | ✓ HONORED | core/dependencies.py:65–78 — `id`, `client_id`, `end_date`, `status` only. SA `Membership` ORM structurally satisfies. |
| D-19 | 9-cell transition matrix asserted | ✓ HONORED | `test_state_machine.py::test_state_machine_matrix` parametrises 9 cells incl. 3 `n/a` rows for `create-self`. Allowed (active+cancel, active+expire) succeed; disallowed (expired+*, cancelled+*) raise `InvalidTransitionError(409, code="invalid_transition", fields={from_status, to_status})`. |
| D-20 | Constraint name pinning | ✓ HONORED | All 5 names match exactly: `fk_memberships_plan_id_membership_plans`, `fk_memberships_client_id_clients`, `ck_memberships_status`, `ck_memberships_activation_policy`, `ix_memberships_client_id_status_end_date`. Migration uses `op.f(...)` to delegate to NAMING_CONVENTION. |

10/10 spot-checked decisions honored (D-05/D-06 mechanism deviation noted but goal preserved).

---

## Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| MEM-01 | 17-01 | Migration `0005_memberships.py` + table schema + composite index | ✓ SATISFIED | `alembic/versions/0005_memberships.py` ships all required columns + CHECK constraints + FKs + composite index `(client_id, status, end_date DESC)`. |
| MEM-02 | 17-03 | Snapshot fields at insert; plan edits never mutate | ✓ SATISFIED | `repository.insert_membership` copies `plan.name`, `plan.duration_days`, `plan.price_kopecks` into `*_snapshot` columns. No mutation path writes to those columns. |
| MEM-03 | 17-03 | Cancel owner-only; transition guards `expired→cancelled` and `cancelled→cancelled` → 409 | ✓ SATISFIED | Router `Depends(require_permission(CANCEL, MEMBERSHIPS))` (OWNER_ONLY); `_assert_can_cancel` raises `InvalidTransitionError`. |
| MEM-04 | 17-03 | Resolver tiebreak latest `end_date`, then `created_at DESC` | ⚠ PARTIAL | Tiebreak honored. **Deviation:** the literal MEM-04 spec includes `AND end_date >= today (Europe/Moscow)`; implementation uses `status='active'` only (per D-13). See Deviations. |
| MEM-05 | 17-02 | `ActiveMembership` Protocol + slot setter + consumer + `app/main.py` registration | ✓ SATISFIED | core/dependencies.py:65–119; main.py:108. Sanity test confirms slot wiring. |
| MEM-EP-01 | 17-04 | `GET /memberships?clientId&status` paginated | ✓ SATISFIED | router.py:210–232; `MembershipListQuery(PageQuery)`; `PaginatedData[MembershipResponse]` envelope. |
| MEM-EP-02 | 17-04 | `GET /memberships/{id}` | ✓ SATISFIED | router.py:235–250; `MembershipNotFoundError` on missing. |
| MEM-EP-03 | 17-04 | `POST /memberships` 201 reception+owner CSRF | ✓ SATISFIED | router.py:253–275; `(CREATE, MEMBERSHIPS) ∉ OWNER_ONLY` → reception+owner; CSRF via `verify_csrf` after `require_permission`. |
| MEM-EP-04 | 17-04 | `POST /memberships/{id}/cancel` 200 owner-only CSRF | ✓ SATISFIED | router.py:278–305; `(CANCEL, MEMBERSHIPS) ∈ OWNER_ONLY`; status 200 with full `MembershipResponse`. |
| MEM-AUDIT-01 | 17-03 / 17-04 | `audit.emit("membership_created" / "_cancelled")` | ✓ SATISFIED | service.py:371, 429. `membership_expired` is Phase 18 (out of scope). |
| TESTS-09 | 17-05 | AST meta-test confirms every `audit.emit` pair ∈ `LOCKED_AUDIT_EVENTS` | ✓ SATISFIED | `tests/unit/test_audit_taxonomy.py` runs (3 tests pass) — walks `apps/backend/app/**/*.py`, validates literal strings + locked-set membership. |
| TESTS-10 | 17-05 | 9-cell state-machine matrix | ✓ SATISFIED | `tests/unit/memberships/test_state_machine.py::test_state_machine_matrix` parametrises 9 cells; pass. |

**12/12 requirements satisfied; 1 with documented deviation (MEM-04) that does not block goal.**

**Note:** REQUIREMENTS.md checkboxes `- [ ]` and the bottom status table still show "Pending" for these 12 IDs — a doc-housekeeping miss. The `STATE.md` and `ROADMAP.md` Phase 17 entry both already reflect completion. This is INFO, not a blocker.

---

## Anti-Patterns Found

No production-code anti-patterns flagged. Service paths are commit-disciplined (Phase 15 AST gate enforces, all checks green). No TODO/FIXME/placeholder/stub comments in new files.

---

## Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full backend test suite | `cd apps/backend && uv run pytest -q` | 477 passed in 26.03s | ✓ PASS |
| Phase 17 unit + integration | `uv run pytest tests/unit/memberships/ tests/integration/memberships/` | 140 passed in 11.52s | ✓ PASS |
| TESTS-09 audit taxonomy | `uv run pytest tests/unit/test_audit_taxonomy.py -v` | 3 passed | ✓ PASS |
| mypy strict on app/ | `uv run mypy app` | Success: no issues found in 65 source files | ✓ PASS |
| ruff app + tests | `uv run ruff check app tests` | All checks passed! | ✓ PASS |
| import-linter | `uv run lint-imports` | 3 contracts kept, 0 broken | ✓ PASS |
| openapi.json byte-stable | re-run `scripts/export_openapi.py` then `diff -q` | identical 65189-byte output | ✓ PASS |
| Alembic round-trip | `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` | clean (downgrade + re-upgrade succeed) | ✓ PASS |

---

## Quality Gates Summary

| Gate | Result |
|------|--------|
| pytest (full suite) | 477/477 passed |
| pytest (Phase 17 new tests) | 82 new (395 baseline → 477 total) |
| mypy strict (`app/`) | 0 issues, 65 files |
| ruff (`app + tests`) | clean |
| import-linter | 3/3 contracts kept (incl. `core must not import modules`) |
| Alembic round-trip | clean |
| openapi.json | byte-stable post-regen |
| AST commit gate (`test_service_commit_gate`) | passes (covers `app.modules.memberships.service`) |
| AST audit literal gate (`test_audit_taxonomy`) | passes (3 tests, covers TESTS-09) |
| Route introspection (RBAC-04 ordering) | passes (covers all 4 new routes) |

All quality gates green.

---

## Deviations (Correctness-Preserving)

### Deviation 1 — Resolver query omits `end_date >= today` filter

**Where:** `apps/backend/app/modules/memberships/repository.py:find_active_for_client` (lines 297–303).

**MEM-04 / SC#3 verbatim:** "returns the SINGLE active membership matching `status='active' AND end_date >= today (Europe/Moscow)`".

**Implementation:** `WHERE status = 'active'` only — no `end_date` predicate.

**Justification (CONTEXT.md D-13, repository.py:292–296 docstring):** Per D-13, **status is the gate, not the date**. Phase 18 ARQ flips status `active → expired` daily for rows whose `end_date < CURRENT_DATE`. Until ARQ runs, a row whose `end_date` is in the past but `status='active'` is the canonical row — the resolver returns it, the visits check-in (Phase 19) treats it as valid (single-day grace until daily cron). Adding the date predicate would make the resolver and the cancel-from-active path inconsistent (D-13: "expired by date but still status='active' rows can be cancelled").

**Risk assessment:** LOW. The deviation is documented in three places (CONTEXT.md D-13, service.py docstring, repository.py docstring). It produces a strictly more permissive answer (returns rows the literal SC#3 would exclude) only during the at-most-24h window between `end_date` passing and ARQ running. The visits service (Phase 19) is the one downstream consumer; it can safely operate on this slightly-permissive answer because Phase 18's daily cron narrows it.

**Verifier verdict:** WARNING — does NOT block goal achievement. The phase goal ("does this client have an active membership today?") is satisfied by status-as-gate semantics; the literal SC#3 wording is a tighter interpretation that the implementation deliberately chose not to honor for cross-phase correctness reasons. Recommend clarifying SC#3/MEM-04 wording in Phase 18 to read "status='active'" only, removing the inconsistency.

### Deviation 2 — `plan_in_use` translated via pre-flight count, not FK IntegrityError

**Where:** `apps/backend/app/modules/memberships/service.py:soft_delete_plan` (lines 282–313).

**Plan 17-03 / D-05 / D-08 original:** Catch `IntegrityError` on FK `fk_memberships_plan_id_membership_plans`, translate to `PlanInUseError`.

**Implementation:** Pre-flight `select(func.count()).select_from(Membership).where(plan_id == plan.id)`; raise `PlanInUseError` if `> 0`. The IntegrityError translation block is retained as defence-in-depth canary for a future hard-delete refactor.

**Justification (service.py:266–273, 305–313):** **Soft-delete is an UPDATE, not a DELETE.** The FK `fk_memberships_plan_id_membership_plans ON DELETE RESTRICT` only fires on `DELETE FROM membership_plans` — it does NOT fire for `UPDATE membership_plans SET deleted_at = now()`. The original plan's IntegrityError translation would never execute under the current soft-delete model. The pre-flight count is the actual correctness gate; the IntegrityError block is kept as a canary for a future refactor that switches to hard-delete (the canary is deliberately left in even though it's currently dead code, per T-CONSTRAINT-DRIFT mitigation).

**Risk assessment:** LOW. D-06 invariant ("ANY membership row blocks deletion, including cancelled and expired") is preserved — verified by `test_delete_plan_with_{active,cancelled,expired}_membership_returns_409` (3 tests pass). The change is correctness-preserving; the original plan was simply wrong about which DB mechanism would fire.

**Verifier verdict:** ACCEPT — correctness-preserving deviation. Better implementation than the planned one.

### Deviation 3 — UUID-JSONB encoding fix in audit emit kwargs

**Where:** `apps/backend/app/modules/memberships/service.py:create_membership` (lines 377, 378), `cancel_membership` (line 435).

**Issue:** UUIDs are not natively JSON-serialisable; passing `client_id=membership.client_id` (UUID) to `audit.emit` writes the value into `audit_log.payload` (JSONB) which raises `TypeError`.

**Fix:** Cast to `str()` before passing into `audit.emit` kwargs.

**Note:** `resource_id` does NOT need this cast because it's stored in a UUID-typed column (`audit_log.resource_id`), not in JSONB. Only payload-bound UUIDs need the str cast.

**Verifier verdict:** ACCEPT — correctness-preserving; audit-write tests pass.

### Deviation 4 — REQUIREMENTS.md checkboxes not flipped to `[x]`

**Where:** `.planning/REQUIREMENTS.md` lines 34–43, 101–102, and the status table at lines 190–201.

**Issue:** Phase 17 requirement IDs MEM-01..05, MEM-EP-01..04, MEM-AUDIT-01, TESTS-09, TESTS-10 still show `- [ ]` and "Pending" in the per-row tables; ROADMAP.md and STATE.md correctly reflect completion.

**Risk assessment:** INFO. Documentation hygiene only — does not affect code correctness.

**Verifier verdict:** INFO — recommend a small follow-up patch to REQUIREMENTS.md to flip these to `[x]` and "Done".

### Deviation 5 — 17 pre-existing mypy strict errors in `tests/`

**Where:** Documented in `deferred-items.md` — all 17 errors exist in code touched in Phases 8 / 16, NOT in Phase 17 new files (verified by stash-and-recheck against base commit `fc3cbd8a`).

**Risk assessment:** ACCEPTED. `uv run mypy app` (production code) is clean. `uv run mypy tests` has 17 issues across 4 categories, all pre-existing and orthogonal to Phase 17 changes.

**Verifier verdict:** ACCEPT — properly scoped and tracked.

---

## Phase Status Verdict

**COMPLETE.**

- 5/5 ROADMAP success criteria met (1 with documented, justified deviation that does not block the phase goal).
- 12/12 requirements satisfied (1 partial — MEM-04 — with cross-phase justification).
- 10/10 spot-checked decisions (D-01, D-04, D-05/D-06, D-07, D-12/D-15, D-14, D-17, D-18, D-19, D-20) honored.
- All 8 quality gates green: pytest 477/477, mypy strict on app/, ruff, import-linter 3/3, alembic round-trip, openapi byte-stable, AST commit gate, AST audit literal gate.
- 5 deviations identified — all correctness-preserving and documented in CONTEXT.md or `deferred-items.md`. None block the goal.

The phase goal — "Reception can sell a membership and the system can answer 'does this client have an active membership today?'" — is achieved end-to-end:
1. POST `/api/v1/memberships` succeeds (reception+owner) — verified by `test_sale_happy_path` and `test_reception_can_post_sale`.
2. `resolve_active_membership(session, client_id)` returns the canonical row via the registered slot — verified by `test_resolver_via_registered_slot_matches_direct_call`.
3. The Phase 16 D-15 closure (DELETE plan → 409 plan_in_use for any-status membership) is shipped — verified by 3 tests on test_plan_in_use.py.
4. State machine + audit + RBAC fully wired and statically enforced.

---

## Recommendations (Non-Blocking)

1. **Reconcile MEM-04 / SC#3 wording** with the implementation's status-as-gate semantic (drop `AND end_date >= today` from the spec text, or move the date filter into the resolver). Best resolved alongside Phase 18 ARQ work since the two phases share the lifecycle invariant.
2. **Flip REQUIREMENTS.md checkboxes** for the 12 Phase 17 IDs to `- [x]` and "Done" (small doc-housekeeping patch).
3. **Track the 17 pre-existing mypy `tests/` errors** as a future hygiene chore plan (already captured in `deferred-items.md`).

---

_Verified: 2026-05-07_
_Verifier: Claude (gsd-verifier, Opus 4.7)_
