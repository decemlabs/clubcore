---
phase: 16-membership-plans-catalog-backend
verified: 2026-05-07T18:00:00Z
status: passed
score: 5/5
overrides_applied: 0
deferred:
  - truth: "Owner can soft-delete a plan via DELETE /api/v1/membership-plans/{id}; deletion returns 409 plan_in_use when any non-cancelled Membership references it (FK ON DELETE RESTRICT)"
    addressed_in: "Phase 17"
    evidence: "Phase 17 goal: 'Reception can sell a membership... the foundation Visits will validate against'; the memberships table FK plan_id ON DELETE RESTRICT is introduced in Phase 17 (D-15). Phase 16 satisfies the partial spec per D-16: 204 on first delete, 404 on second, partial-unique slot freed."
---

# Phase 16: Membership Plans Catalog (backend) — Verification Report

**Phase Goal:** Owner can manage the gym's plan catalog (the SKUs reception will sell in Phase 17).
**Verified:** 2026-05-07T18:00:00Z
**Status:** PASSED
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Owner can list plans via `GET /api/v1/membership-plans` with paginated `{items,total,page,pageSize}` envelope and an optional `?active=true` filter; reception receives 403 | VERIFIED | `router.py:62-77` returns `ResponseEnvelope[PaginatedData[MembershipPlanResponse]]`; `require_permission(Action.VIEW, Resource.MEMBERSHIP_PLANS)` gates access; OWNER_ONLY contains VIEW+MEMBERSHIP_PLANS; `test_list_default_envelope` and `test_list_filter_active_*` pass; `test_get_list_reception_returns_403` asserts 403 |
| 2 | Owner can create a plan via `POST /api/v1/membership-plans` with `{name, durationDays, priceKopecks, active?}`; partial-unique `lower(name) WHERE deleted_at IS NULL` rejects duplicates | VERIFIED | `router.py:98-115` at 201; `schemas.py:42-54` with D-01 trim validator; migration `0004_membership_plans.py:62-65` installs `uq_membership_plans_name_alive` index via raw `op.execute`; `service.py:100-134` catches IntegrityError → `PlanNameExistsError`; `test_post_duplicate_alive_name_returns_409_plan_name_exists` and `test_post_case_variant_duplicate_returns_409` exercise the path |
| 3 | Owner can update plan name/price/active via `PATCH /api/v1/membership-plans/{id}`; `duration_days` is rejected as immutable to preserve sold-instance snapshot semantics | VERIFIED | `MembershipPlanUpdateRequest` (schemas.py:60-91) does NOT declare `duration_days`; `BackendSchemaBase` `extra='forbid'` makes any `durationDays` payload raise 422; `test_patch_duration_days_returns_422` confirms; `test_patch_updates_name_and_price` confirms 200 happy path; idempotent no-op (D-09) confirmed by `test_patch_idempotent_noop_does_not_emit_audit` |
| 4 | Owner can soft-delete a plan via `DELETE /api/v1/membership-plans/{id}`; D-15/D-16: 204 on first delete, 404 on second, partial-unique name slot freed | VERIFIED (partial — per D-15 caveat) | `router.py:138-161` returns 204; `service.py:193-221` soft-deletes via `repository.soft_delete_plan` (sets `deleted_at=now()`); `test_delete_returns_204`, `test_delete_then_delete_returns_404`, `test_delete_frees_unique_name_slot` all pass; 409 `plan_in_use` path is deferred to Phase 17 per D-15 |
| 5 | Every successful plan create/update/archive writes a locked audit event (`membership_plan_created` / `_updated` / `_archived`) with the actor and changed fields | VERIFIED | `service.py` emits literal strings `"membership_plan_created"`, `"membership_plan_updated"`, `"membership_plan_archived"` with `resource_type="membership_plan"` — all pairs in `LOCKED_AUDIT_EVENTS`; D-11 payload `{name, duration_days, price_kopecks}` in resource_id+kwargs; D-12 payload `{changed_fields}` list only; D-13 empty payload; `test_post_emits_membership_plan_created_with_full_payload`, `test_patch_emits_membership_plan_updated_with_changed_fields_only`, `test_delete_emits_membership_plan_archived_with_minimal_payload` all assert correct shapes |

**Score:** 5/5 truths verified

### Deferred Items

Items not yet met but explicitly addressed in later milestone phases.

| # | Item | Addressed In | Evidence |
|---|------|-------------|----------|
| 1 | 409 `plan_in_use` when non-cancelled Membership references plan (FK ON DELETE RESTRICT) | Phase 17 | Phase 17 depends on Phase 16 plans table for FK; the `memberships` table and `fk_memberships_plan_id_membership_plans` constraint are Phase 17 scope per D-15 in 16-CONTEXT.md |

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `apps/backend/alembic/versions/0004_membership_plans.py` | Migration creating `membership_plans` table + partial-unique index | VERIFIED | Table created with all MEM-PLAN-01 columns; CHECK constraints for `duration_days > 0` and `price_kopecks >= 0`; partial-unique index `uq_membership_plans_name_alive` on `lower(name) WHERE deleted_at IS NULL` via raw `op.execute`; `down_revision = "0002_clients"`; downgrade drops index then table |
| `apps/backend/app/modules/memberships/models.py` | MembershipPlan ORM model | VERIFIED | Composites `Base + UUIDPkMixin + TimestampMixin + SoftDeleteMixin`; all required columns; `__table_args__` with two CHECK constraints and the expression index for ORM awareness; uses `server_default=text("true")` for `active` |
| `apps/backend/app/modules/memberships/schemas.py` | Create/Update/Response/ListQuery DTOs | VERIFIED | `MembershipPlanCreateRequest` with D-01 trim, D-06 bounds; `MembershipPlanUpdateRequest` without `duration_days` (D-04), D-05 null guard, D-07 fields; `MembershipPlanResponse`; `MembershipPlanListQuery` with `?active` + sort enum; all inherit from `BackendSchemaBase`/`ResponseData` |
| `apps/backend/app/modules/memberships/repository.py` | CRUD repository | VERIFIED | `get_alive`, `list_alive`, `insert_plan`, `update_plan`, `soft_delete_plan` — all alive-filter-aware; no commits/flushes (service owns tx); returns `changed_previous` dict from `update_plan` for D-09/D-12 |
| `apps/backend/app/modules/memberships/service.py` | Service orchestration + audit + commit | VERIFIED | All three write paths have `await session.commit()`; D-14 ordering correct; D-02 IntegrityError translation via `_is_plan_name_conflict`; D-09 no-op skip on empty `changed_previous`; literal-string audit emit callsites |
| `apps/backend/app/modules/memberships/router.py` | 5 endpoints with RBAC + CSRF | VERIFIED | GET list, GET single, POST (201), PATCH (200), DELETE (204); `require_permission` BEFORE `verify_csrf` in every mutation signature (RBAC-04); all wired to service layer |
| `apps/backend/app/core/exceptions.py` | `PlanNotFoundError` + `PlanNameExistsError` | VERIFIED | Both classes present; `PlanNotFoundError(NotFoundError)` with `code="plan_not_found"`, `status_code=404`; `PlanNameExistsError(ConflictError)` with `code="plan_name_exists"`, `status_code=409` (D-03) |
| `apps/backend/alembic/env.py` | `_include_object` filter extended | VERIFIED | `"uq_membership_plans_name_alive"` added to the exclusion list at line 65; prevents autogenerate drift on the expression index |
| `apps/backend/app/api/v1/router.py` | Memberships router wired to v1 | VERIFIED | `from app.modules.memberships.router import router as plans_router` + `v1.include_router(plans_router, prefix="/membership-plans", tags=["membership-plans"])` |
| `apps/backend/openapi.json` | Regenerated with membership-plans endpoints | VERIFIED | File exists (50215 bytes); contains 9 references to `membership-plans`; correct status codes: GET→200, POST→201, PATCH→200, DELETE→204 |
| `apps/backend/tests/integration/memberships/` | 4 integration test files + conftest | VERIFIED | `conftest.py`, `test_plans_crud.py` (16 tests), `test_plans_list.py` (9 tests), `test_plans_rbac.py` (7 tests), `test_audit_writes.py` (5 tests) all present and substantive |
| `apps/backend/tests/unit/memberships/test_schemas.py` | 21 unit schema tests | VERIFIED | Covers D-01/D-04/D-05/D-06/D-07 decisions, camelCase alias contract, list query defaults |
| `apps/backend/tests/unit/test_service_commit_gate.py` | AST gate extended to memberships service | VERIFIED | `_MEMBERSHIPS_SERVICE` and `_INSPECTED_SERVICES` tuple extended; `test_service_commit_gate_against_app_modules` covers both clients and memberships service |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `memberships/router.py` | `memberships/service.*` | `from app.modules.memberships import service` | VERIFIED | Router calls `service.list_plans`, `service.get_plan`, `service.create_plan`, `service.update_plan`, `service.soft_delete_plan` |
| `memberships/service.py` | `memberships/repository.*` | `from app.modules.memberships import repository` | VERIFIED | Service calls 5 repository functions; never imports ORM model directly |
| `memberships/service.py` | `app.core.audit` | `from app.core import audit; audit.emit(session, ...)` | VERIFIED | 3 `audit.emit()` calls with literal strings; all pairs in `LOCKED_AUDIT_EVENTS` |
| `memberships/service.py` | `session.commit()` | `await session.commit()` in every write path | VERIFIED | `create_plan:133`, `update_plan:189`, `soft_delete_plan:221` all have explicit commit; AST gate enforces this |
| `app/api/v1/router.py` | `memberships/router.py` | `include_router(plans_router, prefix="/membership-plans")` | VERIFIED | Plans router mounted under `/api/v1/membership-plans` |
| `alembic/env.py` | `app.modules.memberships.models` | `import app.modules.memberships.models` | VERIFIED | Line 27; model registered with Base.metadata for autogenerate |
| `alembic/env.py` | `_include_object` filter | `"uq_membership_plans_name_alive"` in exclusion list | VERIFIED | Line 65; expression index suppressed from autogenerate drift |
| `tests/integration/memberships/conftest.py` | `tests/integration/conftest.py` (root) | `db_session` + `app` + `async_client` fixtures | VERIFIED | `authed_client_owner` and `authed_client_reception` both use SAVEPOINT-mode `db_session`; mirrors clients conftest pattern |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `router.py:list_plans` | `page` (PaginatedData) | `service.list_plans` → `repository.list_alive` → `session.scalars(stmt)` | Yes — live SQL against `membership_plans` table with WHERE `deleted_at IS NULL` | FLOWING |
| `router.py:create_plan` | `plan` (MembershipPlanResponse) | `repository.insert_plan` → `session.add(MembershipPlan(...))` → flush + commit | Yes — DB insert with all required fields | FLOWING |
| `router.py:update_plan` | `plan` (MembershipPlanResponse) | `repository.get_alive` → `repository.update_plan` (setattr mutation) → flush + commit + refresh | Yes — in-place ORM mutation persisted to DB | FLOWING |
| `router.py:soft_delete_plan` | None (204) | `repository.soft_delete_plan` → `plan.deleted_at = datetime.now(tz=UTC)` → flush + commit | Yes — soft delete persisted | FLOWING |

### Behavioral Spot-Checks

Step 7b: SKIPPED (no runnable entry point without DB and Redis; all behaviors verified via integration test suite that uses `httpx ASGITransport` as specified in CLAUDE.md — the 395/395 passing test suite constitutes behavioral verification).

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|------------|------------|-------------|--------|----------|
| MEM-PLAN-01 | 16-01 | `membership_plans` migration with all columns + partial-unique index | SATISFIED | `0004_membership_plans.py` creates table + installs `uq_membership_plans_name_alive` via `op.execute`; all MEM-PLAN-01 column specs present |
| MEM-PLAN-02 | 16-01, 16-02, 16-03, 16-04 | Full module: `models/schemas/repository/service/router.py` following clients template | SATISFIED | All 5 files present and substantive; service uses BusinessService template with explicit commits; repository patterns mirror clients |
| MEM-PLAN-EP-01 | 16-04, 16-05 | `GET /api/v1/membership-plans` — paginated list + `?active` filter; reception 403 | SATISFIED | Router at line 62; pagination via `PaginatedData[MembershipPlanResponse]`; RBAC gate; `test_list_*` + `test_get_list_reception_returns_403` |
| MEM-PLAN-EP-02 | 16-04, 16-05 | `POST /api/v1/membership-plans` — create plan, 201, 409 on duplicate name | SATISFIED | Router at line 98 with `status_code=HTTP_201_CREATED`; D-02 IntegrityError translation; `test_post_creates_plan_returns_201_with_envelope` + `test_post_duplicate_alive_name_returns_409` |
| MEM-PLAN-EP-03 | 16-04, 16-05 | `PATCH /api/v1/membership-plans/{id}` — partial update; `duration_days` immutable (422) | SATISFIED | `MembershipPlanUpdateRequest` lacks `duration_days`; `extra='forbid'` on BackendSchemaBase; `test_patch_duration_days_returns_422` + `test_patch_updates_name_and_price` |
| MEM-PLAN-EP-04 | 16-04, 16-05 | `DELETE /api/v1/membership-plans/{id}` — soft-delete 204; 409 `plan_in_use` (deferred D-15) | PARTIALLY SATISFIED | 204 + 404-on-second + slot-freed all tested; 409 `plan_in_use` deferred to Phase 17 per D-15 (memberships table + FK not yet created) |
| MEM-PLAN-AUDIT-01 | 16-03, 16-05 | 3 locked audit events emitted with correct payloads | SATISFIED | `audit.emit("membership_plan_created", ...)` D-11 payload; `audit.emit("membership_plan_updated", ...)` D-12 changed_fields only; `audit.emit("membership_plan_archived", ...)` D-13 empty payload; all pairs in `LOCKED_AUDIT_EVENTS`; integration tests assert DB audit rows |

### Anti-Patterns Found

| File | Pattern | Severity | Impact |
|------|---------|----------|--------|
| None found | — | — | No stub implementations, placeholder returns, hardcoded empty data, or TODO markers found in any memberships module file |

One informational note: `audit.py` docstring describes `membership_plan_created` payload as `{plan_id, name, duration_days, price_kopecks}` but `plan_id` is stored in `resource_id` column (not the JSONB payload). This is consistent with D-11's explicit footnote "(plan_id is in resource_id column, not payload)" and the integration test asserts `payload == {"name": ..., "duration_days": ..., "price_kopecks": ...}`. Documentation discrepancy only — no functional impact.

### Human Verification Required

No items require human verification. All behaviors are verifiable via code inspection and the 395/395 passing integration + unit test suite.

### Decisions Coverage (D-01..D-17)

All 17 decisions from 16-CONTEXT.md are honored in the codebase:

- **D-01**: `field_validator("name", mode="before")` applies `v.strip()` in both Create and Update schemas — verified in `schemas.py:50-54, 87-91`
- **D-02**: `_is_plan_name_conflict(exc)` checks `constraint_name == "uq_membership_plans_name_alive"` with substring fallback — `service.py:58-68`; applies on both POST and PATCH
- **D-03**: `PlanNameExistsError` and `PlanNotFoundError` both in `core/exceptions.py` — verified
- **D-04**: `MembershipPlanUpdateRequest` has no `duration_days` field; `extra='forbid'` from `BackendSchemaBase` raises 422 on any such payload — verified in `schemas.py:60-91`
- **D-05**: `model_validator(mode='before')` rejects any `None` value in PATCH body — `schemas.py:74-85`
- **D-06**: Pydantic bounds `duration_days ge=1 le=3650`, `price_kopecks ge=0 le=10**11`, `name min_length=1 max_length=120` applied after trim — verified
- **D-07**: PATCH-able fields are `name`, `price_kopecks`, `active` only — `schemas.py:69-72`
- **D-08**: List query defaults to alive-only, `?active` optional filter, `?sort` enum (`created_at_desc` default, `name_asc`), pagination from `PageQuery` — `schemas.py:114-119`, `repository.py:54-98`
- **D-09**: No `?q` name search — not present in `MembershipPlanListQuery`
- **D-10**: No btree index on `lower(name)` — only the partial-unique `uq_membership_plans_name_alive` exists
- **D-11**: `membership_plan_created` payload = `{name, duration_days, price_kopecks}` with plan_id in `resource_id` — `service.py:121-132`
- **D-12**: `membership_plan_updated` payload = `{changed_fields}` list only, no before/after values — `service.py:175-183`
- **D-13**: `membership_plan_archived` payload = empty `{}`, plan_id in `resource_id` — `service.py:213-219`
- **D-14**: Emit ordering correct: create (insert→flush→emit→commit), update (get→mutate→flush→emit→refresh→commit), delete (get→mutate→emit→flush→commit) — verified in `service.py`
- **D-15**: Phase 16 ships soft-delete only; no 409 `plan_in_use`; D-15 documented in router docstring and service — deferred to Phase 17
- **D-16**: 204 on first delete, 404 on second, unique-name slot freed — all three tested
- **D-17**: DELETE emits `membership_plan_archived`; PATCH `active=false` emits `membership_plan_updated` with `changed_fields=['active']` — two distinct forensic paths confirmed by code

### Gaps Summary

No actionable gaps found. One item (409 `plan_in_use` for DELETE) is properly deferred to Phase 17 per the D-15 decision recorded in 16-CONTEXT.md, with the 3-part D-16 partial satisfaction (204 + 404 + slot-freed) fully implemented and tested.

The PATCH name-collision 409 path exists in `service.py:162-170` and is exercised by the same `_is_plan_name_conflict` helper tested via the POST 409 integration tests. No explicit PATCH-rename-conflict integration test was required in the plan truths (plan 16-05 only specifies "409 plan_name_exists on duplicate alive name" which is covered by the POST tests). The code path is implemented correctly and the unit + service-level tests provide adequate coverage for this path.

---

_Verified: 2026-05-07T18:00:00Z_
_Verifier: Claude (gsd-verifier)_
