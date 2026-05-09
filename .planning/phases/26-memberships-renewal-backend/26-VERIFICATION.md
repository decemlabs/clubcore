---
phase: 26-memberships-renewal-backend
verified: 2026-05-09T00:00:00Z
status: passed
score: 14/14 must-haves verified
overrides_applied: 0
re_verification: null
---

# Phase 26: Memberships — Renewal (backend) Verification Report

**Phase Goal:** Reception/owner может продлить membership одной кнопкой — backend создаёт follow-up row со snapshot текущей цены плана, резолвер корректно отдаёт текущий membership пока он жив и переключается на renewal только после `end_date`.
**Verified:** 2026-05-09
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### ROADMAP Success Criteria (5/5)

| # | Success Criterion | Status | Evidence |
|---|-------------------|--------|----------|
| SC1 | Migration adds `previous_membership_id` UUID NULL FK ON DELETE SET NULL | VERIFIED | `apps/backend/alembic/versions/0009_renewal.py:38-86` — revision `0009_renewal`, `down_revision=0008_freeze`, `add_column(previous_membership_id, sa.UUID(), nullable=True)`, `create_foreign_key(...ondelete="SET NULL")`, `create_index(ix_memberships_previous_membership_id)`. Alembic current head = `0009_renewal`. |
| SC2 | `POST /api/v1/memberships/{id}/renew` (CSRF, reception+owner); allowed sources active/frozen/expired; cancelled → 409 cannot_renew_cancelled; archived plan → 409 plan_archived | VERIFIED | `router.py:389-426` — `@memberships_router.post("/{membership_id}/renew", status_code=201)` with `Depends(require_permission(Action.CREATE, Resource.MEMBERSHIPS))` BEFORE `Depends(verify_csrf)`. `service.py:842-861` raises `CannotRenewCancelledError("cannot_renew_cancelled")` and `PlanArchivedError("plan_archived")`. Tests at `test_renewal_archived_plan.py:98,149` and `test_renewal_endpoint.py:175,194` lock both 409 paths. |
| SC3 | Date strategy: active/frozen → start_date = source.end_date + 1; expired → start_date = today (Europe/Moscow); audit payload includes `start_date_strategy` | VERIFIED | `service.py:863-871` — `if source.status == "expired": start_date = datetime.now(ZoneInfo("Europe/Moscow")).date(); strategy = RENEWAL_STRATEGY_FROM_TODAY_EXPIRED_SOURCE; else: start_date = source.end_date + timedelta(days=1); strategy = RENEWAL_STRATEGY_FROM_SOURCE_END_DATE`. Strategy passed to audit at line 894. Tests `test_renewal_expired_source.py` + `test_renewal_endpoint.py:220,254`. |
| SC4 | Resolver tiebreak: ORDER BY start_date ASC, created_at DESC LIMIT 1 | VERIFIED | `repository.py:396` — `.order_by(Membership.start_date.asc(), Membership.created_at.desc())`. Docstring at `repository.py:344-388` explicitly cites Phase 26 D-26-17. Tests `test_renewal_resolver_tiebreak.py:37,86,135,189` lock all 4 cases. |
| SC5 | `audit.emit("membership_renewed", actor, source_membership_id, new_membership_id, source_plan_id, current_price_kopecks, start_date_strategy)` on each renewal; tests cover active, price-change, expired-from-today, rejection paths | VERIFIED | `service.py:884-895` emits literal `"membership_renewed"` + `resource_type="membership"` with payload `client_id, source_membership_id, source_plan_id, current_price_kopecks=plan.price_kopecks, start_date_strategy`. Pair `("membership_renewed", "membership")` registered in `LOCKED_AUDIT_EVENTS` at `audit.py:146`. Tests cover all 4 paths (TEST-01..04). |

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `apps/backend/alembic/versions/0009_renewal.py` | Migration: column + self-FK + index | VERIFIED | revision="0009_renewal", down_revision="0008_freeze", correct upgrade/downgrade order |
| `apps/backend/app/modules/memberships/models.py` | ORM `Membership.previous_membership_id` Mapped[UUIDType \| None] + Index | VERIFIED | `models.py:153-160` mapped column with self-FK ON DELETE SET NULL; `models.py:181-184` Index in `__table_args__` |
| `apps/backend/app/modules/memberships/schemas.py` | `MembershipResponse.previous_membership_id: UUID \| None = None` | VERIFIED | `schemas.py:256` declares the field |
| `apps/backend/app/modules/memberships/constants.py` | `RENEWAL_STRATEGY_*` literal constants | VERIFIED | `constants.py:34-35` literal values + `__all__` export at lines 37-41 |
| `apps/backend/app/core/exceptions.py` | `CannotRenewCancelledError` + `PlanArchivedError` (ConflictError 409) | VERIFIED | `exceptions.py:158-183` — both subclass `ConflictError`, `code="cannot_renew_cancelled"`/`"plan_archived"`, `status_code=409` |
| `apps/backend/app/modules/memberships/repository.py` | `get_plan_for_renewal` + `insert_renewal_membership` + new ORDER BY | VERIFIED | `repository.py:61` (helper), `:572-605` (insert helper snapshots from CURRENT plan), `:396` (start_date.asc()) |
| `apps/backend/app/modules/memberships/service.py` | `renew_membership` public function: load → guard → date → insert → flush → audit → refresh → commit | VERIFIED | `service.py:785-903` follows full pattern; explicit `await session.commit()` at line 903 satisfies SVC001 gate |
| `apps/backend/app/modules/memberships/router.py` | `POST /{membership_id}/renew` route, 201 Created, CREATE+CSRF | VERIFIED | `router.py:389-426` declares route exactly per spec |
| `apps/backend/app/core/audit.py` | `("membership_renewed", "membership")` in LOCKED_AUDIT_EVENTS; docstring updated to actual payload | VERIFIED | `audit.py:146` registered; `audit.py:61` docstring shows `{client_id, source_membership_id, source_plan_id, current_price_kopecks, start_date_strategy}` |
| Test files: 4 MEM-REN-TEST-01..04 | All required test files present | VERIFIED | TEST-01: `test_renewal_active.py`; TEST-02: `test_renewal_price_change.py`; TEST-03: `test_renewal_archived_plan.py`; TEST-04: `test_renewal_expired_source.py`; +supporting `test_renewal_endpoint.py`, `test_renewal_from_frozen.py`, `test_renewal_resolver_tiebreak.py`, `test_renewal_repository.py`, `test_renewal_constants.py`, `test_renewal_schema_foundation.py` |

### Key Link Verification

| From | To | Via | Status |
|------|-----|-----|--------|
| `router.renew_membership` | `service.renew_membership` | `await service.renew_membership(session, actor, membership_id)` at router.py:425 | WIRED |
| `service.renew_membership` | `repository.insert_renewal_membership` | snapshots from CURRENT plan; `previous_membership_id=source.id` at service.py:874 | WIRED |
| `service.renew_membership` | `audit.emit("membership_renewed", ...)` | LITERAL strings at service.py:884-895 | WIRED |
| `repository.find_active_for_client` | resolver dispatch | `core.dependencies.get_active_membership_for_request` (signature unchanged) | WIRED |
| `MembershipResponse.previous_membership_id` | wire format `previousMembershipId` | BackendSchemaBase alias_generator camelCase | WIRED |
| Migration `0009_renewal` | chain | `down_revision="0008_freeze"`; alembic current head = `0009_renewal` | WIRED |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Renewal test suite (51 tests) | `pytest tests/{unit,integration}/memberships/test_renewal_*.py` | 51 passed in 3.93s | PASS |
| Audit AST literal-string gate | `pytest tests/unit/test_audit_taxonomy.py` | 4 passed | PASS |
| SVC001 commit-gate (covers `renew_membership`) | `pytest tests/unit/test_service_commit_gate.py` | 7 passed | PASS |
| RBAC-04 route introspection (covers `/renew`) | `pytest tests/integration/test_route_introspection.py` | 3 passed | PASS |
| Full backend pytest | `cd apps/backend && uv run pytest` | 709 passed in 45.17s | PASS |
| ruff check entire backend | `uv run ruff check .` | All checks passed | PASS |
| mypy --strict on changed modules | `uv run mypy --strict app/modules/memberships/ app/core/exceptions.py app/core/audit.py` | Success: no issues found in 9 source files | PASS |
| import-linter | `uv run lint-imports` | 3 contracts kept, 0 broken | PASS |
| Alembic head after upgrade | `uv run alembic current` | `0009_renewal (head)` | PASS |

### Requirements Coverage (10/10)

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| MEM-REN-01 | 26-01 | Migration adds `previous_membership_id` UUID NULL FK ON DELETE SET NULL | SATISFIED | `0009_renewal.py:38-86`; ORM mirrored at `models.py:153-184` |
| MEM-REN-02 | 26-03 | `service.renew_membership` reads CURRENT plan; snapshots; status='active'; rejects cancelled | SATISFIED | `service.py:785-903`; `repository.insert_renewal_membership:572-605` snapshots from `plan.{name,duration_days,price_kopecks,freeze_days_limit}` |
| MEM-REN-03 | 26-02 | Resolver tiebreak ORDER BY start_date ASC, created_at DESC | SATISFIED | `repository.py:396` + `test_renewal_resolver_tiebreak.py` |
| MEM-REN-04 | 26-03 | Renewal of expired source → start_date = today; audit `start_date_strategy='from_today_expired_source'` | SATISFIED | `service.py:864-866`; constant at `constants.py:35`; test at `test_renewal_expired_source.py:60` |
| MEM-REN-EP-01 | 26-03 | `POST /api/v1/memberships/{id}/renew` (CSRF, CREATE→reception+owner, 201) | SATISFIED | `router.py:389-426` |
| MEM-REN-AUDIT-01 | 26-03 | `audit.emit("membership_renewed", actor, source_membership_id, new_membership_id, source_plan_id, current_price_kopecks, start_date_strategy)` | SATISFIED | `service.py:884-895` (literal event/resource_type per AST gate; pre-registered `audit.py:146`) |
| MEM-REN-TEST-01 | 26-04 | Renewal of active membership; snapshot from current plan | SATISFIED | `test_renewal_active.py` 2 tests + `test_renewal_endpoint.py` matrix |
| MEM-REN-TEST-02 | 26-04 | Plan price change between sale and renewal: snapshot uses CURRENT price | SATISFIED | `test_renewal_price_change.py:56` + `test_renewal_endpoint.py:343` |
| MEM-REN-TEST-03 | 26-04 | Archived plan → 409 plan_archived; cancelled source → 409 cannot_renew_cancelled | SATISFIED | `test_renewal_archived_plan.py:98,149` + endpoint matrix |
| MEM-REN-TEST-04 | 26-04 | Expired-source renewal: start_date = today, not source.end_date+1 | SATISFIED | `test_renewal_expired_source.py:60` + `test_renewal_endpoint.py:254` |

No orphaned requirements; all 10 IDs from REQUIREMENTS.md MEM-REN section accounted for in plans 26-01..26-04.

### Anti-Patterns Scan

| File | Severity | Notes |
|------|----------|-------|
| `service.py:846-852` | Info | Defence-in-depth `InvalidTransitionError("invalid_renewal_source", ...)` documented as currently unreachable (CHECK admits 4 known statuses). Intentional. |
| `constants.py:25` | Info | Comment "Phase 26 may extend for renewal mechanics" on `expired` transition entry — accurate; renewal is INSERT not transition, MEMBERSHIP_STATUS_TRANSITIONS verified UNCHANGED at `test_renewal_constants.py:63`. |

No blocker or warning anti-patterns detected.

### Critical Verification Targets (from request)

| # | Critical Check | Status | Evidence |
|---|----------------|--------|----------|
| 1 | Migration `0009_renewal.py` exists with `previous_membership_id` UUID NULL FK ON DELETE SET NULL | PASS | `0009_renewal.py:46-65` confirmed |
| 2 | `POST /api/v1/memberships/{id}/renew` registered with CSRF + (CREATE, MEMBERSHIPS) RBAC, 201 Created | PASS | `router.py:389-407` confirmed |
| 3 | `service.renew_membership` rejects cancelled (409 cannot_renew_cancelled) and archived plan (409 plan_archived); accepts active/frozen/expired | PASS | `service.py:842-861` confirmed |
| 4 | Snapshot from CURRENT plan in `repository.insert_renewal_membership` | PASS | `repository.py:594-597` uses `plan.name`, `plan.duration_days`, `plan.price_kopecks`, `plan.freeze_days_limit` (NOT source.*_snapshot) |
| 5 | Date strategy: active/frozen → end_date+1; expired → today; audit includes literal `start_date_strategy` | PASS | `service.py:863-871, 894` confirmed |
| 6 | Resolver tiebreak `ORDER BY start_date ASC, created_at DESC LIMIT 1` | PASS | `repository.py:396-397` confirmed |
| 7 | Audit event `("membership_renewed", "membership")` in LOCKED_AUDIT_EVENTS; literal callsite | PASS | `audit.py:146` registered; `service.py:886,888` literal strings |
| 8 | All 4 MEM-REN-TEST-XX requirements have implementing files | PASS | All 4 files present + supporting matrix |
| 9 | `MEMBERSHIP_STATUS_TRANSITIONS` UNCHANGED | PASS | `constants.py:22-29` unchanged from Phase 25; `test_renewal_constants.py:63` asserts unchanged |
| 10 | All backend gates green: ruff, mypy --strict, lint-imports, pytest (709 tests) | PASS | All gates passed; full pytest 709/709 |

### Gaps Summary

No gaps. Phase 26 delivers the goal completely:

- Migration `0009_renewal` lands the `previous_membership_id` self-FK column with proper ON DELETE SET NULL semantics; alembic head is `0009_renewal`.
- ORM, Pydantic schema, exceptions, and constants foundations all extend cleanly.
- `service.renew_membership` orchestrates load → guard → date-compute → insert (snapshots from CURRENT plan) → flush → audit emit (literal event with full Phase 26 payload) → refresh → commit, satisfying both SVC001 and AST literal-string gates.
- Resolver tiebreak inverted to `start_date ASC, created_at DESC LIMIT 1`; running source wins until `end_date` passes, then ARQ flip + status filter naturally promote the renewal — exactly the goal narrative.
- `MEMBERSHIP_STATUS_TRANSITIONS` correctly UNCHANGED — renewal is INSERT, not transition.
- 10/10 requirements satisfied with 51 dedicated renewal tests + full backend pytest 709/709 green; ruff, mypy --strict, and import-linter all clean.

---

_Verified: 2026-05-09_
_Verifier: Claude (gsd-verifier)_
