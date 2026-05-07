# Phase 16: Membership Plans Catalog (backend) - Context

**Gathered:** 2026-05-07
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 16 ships the **owner-only plan catalog** — the SKU table that reception will sell from in Phase 17. It is the **first business-surface phase of v1.2**: one new ORM model, one Alembic migration, one fully-fledged module (`router/service/repository/schemas/models`), 4 endpoints, 3 audit events.

In scope:
- Alembic migration `0004_membership_plans.py` (down_revision = `0002_clients`, the current head) — `membership_plans` table per MEM-PLAN-01: `id` UUID PK (gen_random_uuid), `name` VARCHAR(120) NOT NULL, `duration_days` INT NOT NULL CHECK > 0, `price_kopecks` BIGINT NOT NULL CHECK >= 0, `active` BOOL NOT NULL DEFAULT TRUE, TimestampMixin, SoftDeleteMixin. Partial unique index `uq_membership_plans_name_alive` on `lower(name) WHERE deleted_at IS NULL` (expression index → installed via `op.execute(...)`, NOT autogenerable; Phase 8 `include_object` env.py filter pattern applies).
- New module `app/modules/memberships/` (replaces the single-line placeholder `__init__.py`) following the validated `clients` template: `models.py`, `schemas.py`, `repository.py`, `service.py`, `router.py`. Service uses the Phase 15 `BusinessService` template — every write path commits explicitly (AST gate enforces).
- 4 endpoints under `/api/v1/membership-plans` mounted in `app/api/v1/router.py`:
  - `GET    /api/v1/membership-plans` — list, paginated `{items,total,page,pageSize}` (MEM-PLAN-EP-01)
  - `POST   /api/v1/membership-plans` — create, 201 (MEM-PLAN-EP-02)
  - `PATCH  /api/v1/membership-plans/{id}` — partial update; `duration_days` immutable (MEM-PLAN-EP-03)
  - `DELETE /api/v1/membership-plans/{id}` — soft-delete, 204 (MEM-PLAN-EP-04)
- All 4 endpoints owner-only via `Depends(require_permission(Action.<X>, Resource.MEMBERSHIP_PLANS))`. The `(VIEW|EDIT|CREATE|DELETE, MEMBERSHIP_PLANS)` pairs are already in `OWNER_ONLY` (Phase 15). CSRF dependency on POST/PATCH/DELETE.
- 3 audit events emitted via `app.core.audit.emit()`, all already in `LOCKED_AUDIT_EVENTS` (Phase 15):
  - `membership_plan_created` on POST.
  - `membership_plan_updated` on PATCH (when fields actually change — D-09 no-op skip from clients applies).
  - `membership_plan_archived` on DELETE.
- OpenAPI byte-stable regeneration: `apps/backend/openapi.json` rewritten as part of the phase (new endpoints land), CI drift gate will require committing the regenerated spec. Phase 21 will refresh the FE `schema.d.ts`; Phase 16 does NOT touch the FE api-client package.
- Tests: full integration coverage mirroring `tests/integration/clients/`:
  - `tests/integration/memberships/test_plans_crud.py` — happy paths for all 4 endpoints + 422 boundaries.
  - `tests/integration/memberships/test_plans_list.py` — pagination, sort, `?active` filter.
  - `tests/integration/memberships/test_plans_rbac.py` — reception receives 403 on all 4 endpoints.
  - `tests/integration/memberships/test_audit_writes.py` — 3 audit events visible after success; co-transactional rollback masks them on failure.
  - `tests/unit/memberships/test_schemas.py` — Pydantic boundary tests (extra='forbid' on PATCH rejects `durationDays`; explicit-null rejection; bounds).
- `.importlinter` contracts unchanged — `app.modules.memberships` consumes only `app.core.*` symbols (no cross-module imports). The placeholder `app/modules/memberships/__init__.py` docstring is replaced with module-real content.

Out of scope (locked to later phases):
- `memberships` table (instances) and FK `plan_id ON DELETE RESTRICT` — **Phase 17**. Phase 16's DELETE ships **soft-delete only**; the `409 plan_in_use` IntegrityError-translation path is added in Phase 17 alongside the FK creation.
- Snapshot pricing (`plan_name_snapshot`, `duration_days_snapshot`, `price_kopecks_snapshot`) — Phase 17 — but Phase 16's `duration_days` immutability is a forward-promise to those snapshots.
- ARQ `expire_memberships` — Phase 18.
- Active-membership resolver (`register_active_membership_resolver`) — Phase 17.
- admin-web wiring of `/membership-plans` route + features/memberships — Phase 22.
- FE `schema.d.ts` regeneration via api-client codegen — Phase 21.
- Hygiene fix for `apps/backend/app/modules/auth/service.py:88` (login_failed audit-row loss; recorded in Phase 15 deferred-items.md) — explicitly **Phase 23** (Hygiene + active sessions backend).

</domain>

<decisions>
## Implementation Decisions

### Plan name validation + 409 conflict UX

- **D-01:** **Schema-level normalization is trim-only**. `MembershipPlanCreateRequest.name` and `MembershipPlanUpdateRequest.name` apply `value.strip()` via a `field_validator(mode='before')`. Original casing is preserved on storage; the DB partial-unique on `lower(name)` catches case-variant duplicates ("Базовый" vs "базовый"). Min length: 1 after strip; max 120 (DB column width). Internal whitespace runs are NOT collapsed — this is a display field owned by the operator. Mirrors clients pattern (no aggressive normalization).
- **D-02:** **409 `plan_name_exists` is raised by IntegrityError translation on POST and PATCH**. Direct mirror of clients D-11 / `PhoneExistsError`:
  - Service inserts/updates → `await session.flush()` → catches `IntegrityError`.
  - Helper `_is_plan_name_conflict(exc)` checks `exc.orig.constraint_name == "uq_membership_plans_name_alive"` (or substring fallback for drivers that don't expose `constraint_name`).
  - On match: `await session.rollback()` then raise `PlanNameExistsError(409, code='plan_name_exists')`.
  - **No pre-flight SELECT.** Pre-checking is race-prone and the IntegrityError path already gives the right answer; saves a query.
  - PATCH applies the same translation only when `name` is in the changed-fields set (early flush, like clients D-11).
- **D-03:** **`PlanNameExistsError` lives in `app/core/exceptions.py`** alongside `PhoneExistsError`. Class shape: `class PlanNameExistsError(ConflictError): code = "plan_name_exists"; status_code = 409`. Naming follows the precedent set by `PhoneExistsError` (Phase 8 D-11) — domain errors aggregate in `core/exceptions.py`, not per-module.

### `duration_days` immutability + PATCH semantics

- **D-04:** **`MembershipPlanUpdateRequest` does NOT declare `duration_days`**. Pydantic 2 + `extra='forbid'` (inherited from `BackendSchemaBase`) makes any payload containing `durationDays` (or `duration_days`) fail validation with the standard 422 "Extra inputs are not permitted". No custom error code — Pydantic's stock error message is sufficient and self-documenting (the rejected key is named in the response). Cleaner than an explicit field-with-validator that always raises.
- **D-05:** **Explicit null is rejected on all PATCH fields** — mirror of clients D-01. `MembershipPlanUpdateRequest` declares a `model_validator(mode='before')` that walks the inbound dict and raises `ValueError(f"Explicit null not supported for: {sorted(null_keys)}. Omit the key to leave the field unchanged.")` if any value is `None`. Practical effect lands on `name` / `price_kopecks` / `active` (all non-nullable in the DB anyway, but the schema-layer guard gives a consistent, explicit error message instead of relying on Pydantic's per-field type errors).
- **D-06:** **Pydantic-layer bounds at POST**, defence-in-depth atop the DB CHECKs:
  - `duration_days: int = Field(ge=1, le=3650)` — DB CHECK is `> 0`; 3650 is the absurd-but-not-impossible upper bound (10 years).
  - `price_kopecks: int = Field(ge=0, le=10**11)` — DB CHECK is `>= 0`; `10**11` kopecks = 1 billion ₽; anything above this is a typo, not a price.
  - `name: str = Field(min_length=1, max_length=120)` — applied AFTER the trim validator. Min 1 means a single non-whitespace char is the minimum.
  - `active: bool = Field(default=True)` — POST defaults to active=True (matches DB `DEFAULT TRUE`).
- **D-07:** **PATCH-able fields:** only `name`, `price_kopecks`, `active`. The PATCH DTO uses `Optional[...] = None` for each (to implement "omit-key = no change") with the D-05 explicit-null guard rejecting `null` values. The `model_dump(exclude_unset=True)` pattern from clients applies — service computes the actually-changed-fields set in the repository (mirror of `clients/repository.update_client` returning `changed_previous: dict[str, Any]`).

### List endpoint shape

- **D-08:** **Default list query = alive only + sort=created_at_desc + page-based pagination**:
  - Default WHERE: `deleted_at IS NULL` (clients pattern).
  - `?active=true|false` is an optional filter (omit = include both active and inactive); when present it adds `AND active = :active`.
  - `?sort` is an enum `MembershipPlanSort = {created_at_desc, name_asc}` (Pydantic `StrEnum`); default = `created_at_desc`.
  - Pagination via `PageQuery` (page=1, page_size=20, max 100) — locked.
  - **No `?includeArchived` flag in Phase 16.** Soft-deleted plans are simply not visible; if a future phase needs an owner archive view, add it then. Reception cannot see soft-deleted regardless (whole route is owner-only in Phase 16).
- **D-09:** **No name search (`?q=`) in Phase 16.** A single zal will have ≤5–20 plans; pagination at 20/page covers the whole catalog without a search box. `core/sql.py:escape_like_pattern` stays unused for plans. If Phase 22's owner UI surfaces a search affordance, revisit then; do not pre-emptively add it.
- **D-10:** **No btree index on `lower(name)`.** The partial-unique `uq_membership_plans_name_alive` (which IS on `lower(name) WHERE deleted_at IS NULL`) doubles as the lookup index for case-insensitive equality. Sequential scan on a ≤20-row catalog is faster than an index seek anyway. Reconsider if `?q=` ships in a later phase.

### Audit payload shapes

- **D-11:** **`membership_plan_created` payload** = `{plan_id, name, duration_days, price_kopecks}`. Verbatim from the audit.py docstring (Phase 15 LOCKED). All fields are non-PII operator-owned data.
- **D-12:** **`membership_plan_updated` payload** = `{plan_id, changed_fields}` only — direct mirror of clients D-08 (`{client_id, changed_fields}`). `changed_fields` is a sorted list of field names from `model_dump(exclude_unset=True)` ∩ actually-different-from-current. **No before/after values** for any field including `price_kopecks`. Rationale: the audit log is for forensics, not full state history; if price-history matters we should ship a separate `membership_plan_price_history` table later, not bloat audit payloads. Consistency with clients pattern wins.
- **D-13:** **`membership_plan_archived` payload** = `{plan_id}` only. Verbatim from the audit.py docstring (Phase 15 LOCKED). Captured BEFORE `deleted_at` is set (clients D-08 `client_soft_deleted` pattern — though for plans the only field beyond `plan_id` would be `name`, and the audit row's `resource_id` already pins it; no name capture needed).
- **D-14:** **Audit-emit ordering** — mirrors clients/service.py per-operation choice:
  - `create_plan`: insert → `flush()` (surface `IntegrityError` → 409) → `audit.emit(plan_created)` → `commit()`.
  - `update_plan`: get → mutate → if changed_previous empty: return early (no emit, no flush, no commit — matches clients D-09 idempotent no-op); else: `flush()` (surface name-conflict on rename) → `audit.emit(plan_updated)` → `refresh(updated_at)` → `commit()`.
  - `soft_delete_plan`: get → mutate (set `deleted_at = now()`) → `audit.emit(plan_archived)` → `flush()` → `commit()`.

### DELETE 409 plan_in_use scope (locked default, not interactively discussed)

- **D-15:** **Phase 16 ships soft-delete only — no in-use check, no 409 `plan_in_use`**. The `memberships` table and the `FK plan_id ON DELETE RESTRICT` are introduced in **Phase 17**. The `409 plan_in_use` IntegrityError-translation lives in the **Phase 17** plan_id FK migration's companion service update — `_is_plan_in_use_conflict(exc)` checks `exc.orig.constraint_name == "fk_memberships_plan_id_membership_plans"`. ROADMAP.md Phase 16 SC#4 ("DELETE returns 409 plan_in_use when any non-cancelled Membership references it") is therefore **partially satisfied in Phase 16** (the SC is structurally a Phase 17 concern; Phase 16 verifies that DELETE soft-deletes a plan with no FK references). Phase 17's plan must include a regression test that creates a plan + sells a membership + attempts DELETE → 409 `plan_in_use`.
- **D-16:** **Phase 16 success criteria for DELETE**: 204 on first delete, 404 on second (already soft-deleted), partial-unique `uq_membership_plans_name_alive` is freed (a new plan can be created with the same name after the delete). The latter is a meaningful behavioral guarantee — call it out explicitly in the verification step.

### DELETE vs PATCH active=false (locked default, not interactively discussed)

- **D-17:** **Two distinct archive paths, distinct audit events**:
  - `DELETE /membership-plans/{id}` → sets `deleted_at = now()`, frees the unique-name slot, emits `membership_plan_archived`. Permanent (within the v1.2 surface — no undelete endpoint).
  - `PATCH /membership-plans/{id} {active:false}` → keeps the row alive (visible to owner queries with `?active=false`), emits `membership_plan_updated` with `changed_fields=['active']`. Reversible by `PATCH {active:true}`.
  - Reception's sell screen (Phase 17 / Phase 22) lists `?active=true` → only sees active alive plans.
  - Forensic answer to "who archived plan X?" follows DELETE → `membership_plan_archived`. "Who deactivated plan Y?" follows PATCH → `membership_plan_updated` with `changed_fields=['active']`. Two distinct queries against the audit_log; intentional.

### Claude's Discretion

- **CD-01:** Exact wording of `PlanNameExistsError` message strings, FastAPI route summaries/descriptions, and OpenAPI examples. Goal: consistency with the clients module (planner reads `apps/backend/app/modules/clients/router.py` and adapts).
- **CD-02:** Test file granularity within `tests/integration/memberships/` — whether `test_plans_crud.py` is a single 200-line file or split into `test_plans_create.py` / `test_plans_update.py` / `test_plans_delete.py`. Mirror clients (single `test_clients_crud.py`) unless the file exceeds ~300 lines.
- **CD-03:** Migration file ordering inside `0004_membership_plans.py.upgrade()`: by current convention (`clients` migration as reference) — table → CHECK constraints (in `__table_args__` if SA-friendly, else raw `op.execute`) → partial-unique index via `op.execute`. Planner picks the cleanest layout.
- **CD-04:** Choice of `MembershipPlanSort` location — local to `app/modules/memberships/schemas.py` (mirrors `ClientSort` in `clients/schemas.py`) vs lifted to `core/`. Default to module-local.
- **CD-05:** Whether to add a single `tests/unit/memberships/test_audit_payloads.py` AST/integration test that pins the 3 audit payload shapes (D-11/D-12/D-13), or fold the assertions into `test_audit_writes.py`. Either is fine; planner decides.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project context (read first)
- `.planning/PROJECT.md` — project description, Constraints, Key Decisions table (including the 3 v1.2 decisions added in Phase 15: inclusive end_date, gym_date, residual fraud risk).
- `.planning/REQUIREMENTS.md` — Phase 16 owns MEM-PLAN-01, MEM-PLAN-02, MEM-PLAN-EP-01..04, MEM-PLAN-AUDIT-01.
- `.planning/ROADMAP.md` §"Phase 16: Membership Plans Catalog (backend)" — phase goal + Success Criteria 1-5 + dependency note (depends on Phase 15).
- `.planning/STATE.md` §"Decisions" — accumulated v1.2 decisions including Phase 15 contract surface lock.

### Phase 15 outputs (foundation contract — strict prerequisite)
- `.planning/phases/15-foundations-rbac-audit-taxonomy-helper-hoisting/15-CONTEXT.md` — Phase 15's full decision set; D-01..D-12 lock the runtime contracts Phase 16 inherits (audit taxonomy, BusinessService template, BackendSchemaBase, AST commit gate).
- `.planning/phases/15-foundations-rbac-audit-taxonomy-helper-hoisting/15-VERIFICATION.md` — confirms Phase 15 success criteria pass (read to verify the foundation actually shipped before planning Phase 16).
- `.planning/phases/15-foundations-rbac-audit-taxonomy-helper-hoisting/deferred-items.md` — `auth/service.py` write-path deferral (D-15 / Phase 23 routing confirmed).

### Research outputs (v1.2 — global)
- `.planning/research/SUMMARY.md` §"Pitfalls (BLOCKER ranks)" #1 — service-write commit discipline (the rationale Phase 15's AST gate enforces; Phase 16 service.py inherits).
- `.planning/research/PITFALLS.md` — full pitfall catalogue; BLOCKER #1 (commit discipline) directly applies to Phase 16's create/update/soft-delete paths.
- `.planning/research/ARCHITECTURE.md` — `register_user_loader` precedent (Phase 17 will mirror as `register_active_membership_resolver`; Phase 16 does NOT touch this but is the runway for it).
- `.planning/research/STACK.md` — confirms zero new runtime deps for v1.2 (no new pip install in Phase 16).

### Backend codebase — direct templates (clients module is the reference implementation)
- `apps/backend/app/modules/clients/models.py` — ORM template: `Base + UUIDPkMixin + TimestampMixin + SoftDeleteMixin` composition; `__table_args__` shape; partial-unique index declaration via `Index(..., postgresql_where=text("deleted_at IS NULL"))`.
- `apps/backend/app/modules/clients/repository.py` — repository pattern: `list_alive`, `get_alive`, `insert_<entity>`, `update_<entity>` (returning `changed_previous: dict`), `soft_delete_<entity>`. Phase 16 mirrors this shape for `MembershipPlan`.
- `apps/backend/app/modules/clients/service.py` — service template post-Phase-12.1 fix: `await session.commit()` in every write path; audit emit ordering per operation; IntegrityError → domain error translation (D-11 phone_exists). Phase 16's `service.py` follows this verbatim, with `phone_exists` → `plan_name_exists`.
- `apps/backend/app/modules/clients/schemas.py` — DTO template: `<X>CreateRequest(BackendSchemaBase)`, `<X>UpdateRequest(BackendSchemaBase)` with `model_validator(mode='before')` for explicit-null rejection, `<X>Response(ResponseData)`, `<X>ListQuery(PageQuery)` with sort enum.
- `apps/backend/app/modules/clients/router.py` — endpoint template: `Depends(require_permission(...))` BEFORE `Depends(verify_csrf)` (RBAC-04 ordering, D-22); `response_model=ResponseEnvelope[T]`; 201/204 status codes.
- `apps/backend/alembic/versions/0002_clients.py` — migration template: pg_trgm extension precedent (Phase 16 needs none), `op.create_table` shape, partial-unique index via `op.execute(...)` for expression indexes, `include_object` filter rationale (Phase 16 inherits — its `lower(name)` partial-unique is also an expression index).

### Backend codebase — Phase 15 contract surface (consumed, not extended)
- `apps/backend/app/core/permissions.py` — `OWNER_ONLY` includes the 4 `(VIEW|EDIT|CREATE|DELETE, MEMBERSHIP_PLANS)` pairs Phase 16 depends on. **Read but do NOT modify.**
- `apps/backend/app/core/audit.py` — `LOCKED_AUDIT_EVENTS` includes `("membership_plan_created", "membership_plan")`, `("membership_plan_updated", "membership_plan")`, `("membership_plan_archived", "membership_plan")`. `audit.emit()` raises `AuditEventNotLockedError` on any unlocked pair — typos in event-name strings fail at runtime AND at AST-walk time (`tests/unit/test_audit_taxonomy.py`). Phase 16's 3 emit callsites pass literal strings only (D-11 step 3 from Phase 15).
- `apps/backend/app/core/schemas.py` — `BackendSchemaBase` (`alias_generator=to_camel + extra='forbid'`) is the parent of `MembershipPlanCreateRequest` / `MembershipPlanUpdateRequest`. `ResponseData` is the parent of `MembershipPlanResponse`. `ResponseEnvelope[T]` wraps every 2xx body.
- `apps/backend/app/core/services.py` — docstring-only `BusinessService` template (Phase 15 D-01..D-05). Read once; the `service.py` write paths follow this contract verbatim.
- `apps/backend/app/core/sql.py` — `escape_like_pattern`. **Not used in Phase 16** (D-09: no name search). Reserved for future-phase ILIKE search.
- `apps/backend/app/core/pagination.py` — `PageQuery` (page=1, page_size=20, max 100); `PaginatedData[T]`. Phase 16 list query inherits `PageQuery`.
- `apps/backend/app/core/exceptions.py` — `ConflictError(AppError, status=409)`; Phase 16 adds `PlanNameExistsError(ConflictError)` here (D-03), alongside `PhoneExistsError`.
- `apps/backend/app/core/database.py` — `Base + UUIDPkMixin + TimestampMixin + SoftDeleteMixin` (composed by every business model); `NAMING_CONVENTION` produces deterministic constraint names.
- `apps/backend/app/core/dependencies.py` — `CurrentUser`, `require_permission`, `verify_csrf`, `get_db`. Endpoint signature template.

### Backend codebase — wiring touch-points
- `apps/backend/app/api/v1/router.py` — Phase 16 adds `from app.modules.memberships.router import router as plans_router; v1.include_router(plans_router, prefix='/membership-plans', tags=['membership-plans'])`. NO change to `app/main.py` (Phase 17 will register the active-membership resolver there; Phase 16 does not).
- `apps/backend/app/modules/memberships/__init__.py` — currently a single-line placeholder docstring; Phase 16 replaces it with the real module surface.
- `apps/backend/openapi.json` — regenerated by `scripts/export_openapi.py` after Phase 16 lands. Phase 21 handles the `schema.d.ts` regen via api-client codegen.
- `apps/backend/.importlinter` — three contracts (`core ⊥ modules`, `modules independent`, `integrations ⊥ modules`); `app.modules.memberships` consumes only `app.core.*` symbols and adds no cross-module imports → contracts pass without modification.

### Frontend codebase (NOT touched in Phase 16; mirrored in Phase 22)
- `apps/admin-web/src/shared/session/registry.ts` — already declares `Resource.MEMBERSHIP_PLANS` (Phase 15 byte-paritetic mirror); Phase 22 will add the `/membership-plans` route entry.
- `apps/admin-web/src/shared/session/can.ts` — already declares the 4 owner-only `MEMBERSHIP_PLANS` pairs (Phase 15).
- `packages/api-client/` — Phase 21 regenerates `src/schema.d.ts`; Phase 16 does not touch.

### Tests (Phase 16 adds; Phase 15 enforces)
- `apps/backend/tests/integration/test_rbac_parity.py` — TEST-06 already covers MEMBERSHIP_PLANS pairs (Phase 15 TESTS-08). Phase 16 does NOT modify; verifies it stays green after the new module wires up.
- `apps/backend/tests/unit/test_audit_taxonomy.py` — Phase 15's static AST walker already validates the 3 `membership_plan_*` event names against `LOCKED_AUDIT_EVENTS`. Phase 16 service callsites must use literal strings (D-11 step 3 from Phase 15) — typos fail this test in CI.
- `apps/backend/tests/unit/test_service_commit_gate.py` — Phase 15 INFRA-13's AST commit-gate. Phase 16 adds `app.modules.memberships.service` to the gate's scope (`_INSPECTED_MODULES` or equivalent — confirm Phase 15 plan's `_CLIENTS_SERVICE` extension hook).
- `apps/backend/tests/integration/clients/conftest.py` — fixture pattern (auth headers, owner/reception bearer fixtures, db_session SAVEPOINT mode). Phase 16's `tests/integration/memberships/conftest.py` mirrors this.

### Conventions (read for style consistency)
- `.planning/codebase/CONVENTIONS.md` — repo conventions.
- `.planning/codebase/STRUCTURE.md` — module layout.
- `.planning/codebase/TESTING.md` — test fixture patterns.
- `apps/backend/docs/conventions.md` — backend-specific conventions (camelCase wire / snake_case Python; ResponseEnvelope; pagination contract).
- `apps/backend/docs/architecture.md` — modular monolith doc; D-09/D-10 architectural exceptions are documented for v1.2.
- `apps/backend/docs/adr/0001-modular-monolith.md` — ADR for the import-linter contracts.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- **Module template** (`apps/backend/app/modules/clients/`) — full-fidelity template: `models.py` (ORM with mixin composition), `repository.py` (CRUD primitives, soft-delete-aware), `service.py` (orchestration + audit + commit), `schemas.py` (Create/Update/Response/ListQuery DTOs), `router.py` (endpoint signatures with RBAC + CSRF). Phase 16 produces a structurally-identical module with `Membership Plan` substituted for `Client`. ~85% of the file shape transfers directly.
- **`PhoneExistsError` IntegrityError translation** (`apps/backend/app/modules/clients/service.py:99-126`) — `_is_phone_conflict` helper + try/except IntegrityError → rollback → raise translated error. Phase 16 produces `_is_plan_name_conflict` + `PlanNameExistsError` with the same control flow. Constraint name target: `uq_membership_plans_name_alive`.
- **PATCH explicit-null guard** (`apps/backend/app/modules/clients/schemas.py:152-163`) — `model_validator(mode='before')` rejecting `{key: None}` payloads. Phase 16 ports verbatim into `MembershipPlanUpdateRequest`.
- **Idempotent no-op PATCH** (`apps/backend/app/modules/clients/service.py:162-166`) — when `repository.update_<entity>` returns empty `changed_previous`, service returns the current state without emitting audit or flushing. Phase 16's `update_plan` follows this exact shape.
- **Partial-unique expression index** — `apps/backend/alembic/versions/0002_clients.py` ships `Index('uq_clients_phone_alive', 'phone', unique=True, postgresql_where=text('deleted_at IS NULL'))` — declared in `__table_args__` AND in the migration. The `lower(name)` form in Phase 16 is a true expression index that SA cannot autogenerate; it lives in `__table_args__` for ORM awareness AND the migration uses raw `op.execute(...)` to install it. The Phase 8 `include_object` env.py filter (suppresses pg_trgm autogenerate drift) needs to be extended to suppress drift on `uq_membership_plans_name_alive` too — confirm in plan-phase.
- **Test fixture chain** (`apps/backend/tests/integration/conftest.py` + `clients/conftest.py`) — `db_session` SAVEPOINT-mode fixture, `app` factory, `async_client` with `httpx.ASGITransport`, owner/reception bearer fixtures. Reused as-is via `tests/integration/memberships/conftest.py`.
- **`PageQuery` + `PaginatedData[T]`** — already used by `clients`; Phase 16 uses identically.
- **`Action.CREATE` / `Action.EDIT` / `Action.DELETE` / `Action.VIEW` × `Resource.MEMBERSHIP_PLANS`** — already in Phase 15 `OWNER_ONLY` frozenset; `require_permission` dispatches verbatim.

### Established Patterns

- **Module layout: `router/service/repository/schemas/models` (free functions, no classes)** — locked in Phase 15 `core/services.py` docstring; Phase 16 follows it verbatim.
- **Service write paths commit explicitly** — `await session.commit()` is mandatory (Phase 12.1 incident). The Phase 15 AST gate enforces it; Phase 16 must add `app.modules.memberships.service` to the gate's inspected-modules list.
- **`audit.emit()` is co-transactional** — same session, no commit/flush inside emit. Caller commits AFTER emit succeeds. Phase 16's 3 emit callsites + commits follow this contract.
- **`audit.emit(event, resource_type=...)` uses literal strings only** — Phase 15 D-11 step 3 enforces via AST walker. Phase 16 callsites: `audit.emit(session, "membership_plan_created", ..., resource_type="membership_plan")` — both strings literal.
- **PATCH explicit-null reject + `model_dump(exclude_unset=True)`** — clients D-01 + D-09. Phase 16 mirrors verbatim.
- **Domain errors aggregate in `core/exceptions.py`, NOT per-module** — `PhoneExistsError`, `ClientNotFoundError`, `InvalidPhoneError` all live in `core/exceptions.py`. Phase 16 adds `PlanNameExistsError` and `PlanNotFoundError` there too.
- **OWNER_ONLY pair lookup is the gate; the service never re-checks RBAC** — clients service has no RBAC code. Phase 16 service does NOT either.
- **Pagination envelope `{items, total, page, pageSize}` ALWAYS via `ResponseEnvelope[PaginatedData[T]]`** — locked in v1.1; Phase 16 inherits.
- **`from __future__ import annotations` in repository modules** — required by Pydantic generic-resolution edge case (see `clients/repository.py:18-23`); Phase 16's `repository.py` includes it.
- **Sort enum lives in module schemas** — `ClientSort` in `clients/schemas.py`; Phase 16 ships `MembershipPlanSort` in `memberships/schemas.py`.

### Integration Points

- **`app/api/v1/router.py`** — Phase 16's only wiring touch-point besides the module itself. Adds `include_router(plans_router, prefix='/membership-plans', tags=['membership-plans'])`. Verify the prefix matches the kebab-case URL path (resource is `membership-plans` on the wire, mirroring `Resource.MEMBERSHIP_PLANS = "membership-plans"` in `permissions.py`).
- **`apps/backend/openapi.json`** — regenerated by `scripts/export_openapi.py`. Phase 16 commits the regenerated spec; CI gate compares to committed file (`git diff --exit-code`). Phase 21 will then refresh `packages/api-client/src/schema.d.ts` against this updated openapi.json.
- **Alembic chain** — current head is `0002_clients` (down: `0003_telegram_username`, down: `0001_auth`, down: None). New revision `0004_membership_plans` has `down_revision = "0002_clients"`. The `Base.metadata.naming_convention` is unchanged.
- **`alembic/env.py:include_object` filter** — currently suppresses pg_trgm GIN expression indexes from autogenerate drift. Phase 16's `uq_membership_plans_name_alive` partial-unique on `lower(name)` is also an expression index that SA autogenerate cannot represent; the include_object filter list must extend to skip this index name. Confirm in plan-phase.
- **`tests/unit/test_service_commit_gate.py`** — Phase 15 INFRA-13's AST commit-gate. Inspect file and extend the inspected-modules list to include `app.modules.memberships.service` (the actual hook may be `_INSPECTED_MODULES` or a glob pattern; planner reads the file).
- **`tests/integration/test_rbac_parity.py`** — Phase 15 TESTS-08 already covers the 4 MEMBERSHIP_PLANS pairs. Phase 16 verifies it stays green after `/api/v1/membership-plans` mounts (the test only validates `permissions.py` ↔ `can.ts` set equality; it does NOT exercise routes — but a route-introspection guard might).
- **`tests/integration/test_route_introspection.py`** — Phase 6 introspection guard ensures every business route declares `Depends(require_permission(...))`. Phase 16's 4 new routes must pass this guard. Read the test before writing the router.

</code_context>

<specifics>
## Specific Ideas

- **Migration revision chain anchor**: down_revision = `"0002_clients"`. Filename = `0004_membership_plans.py`. Confirm by running `alembic heads` against the dev DB before authoring the migration.
- **Constraint name pinning** (Phase 15 `NAMING_CONVENTION` makes these deterministic, but the partial-unique uses raw `op.execute` so the name must be set explicitly): `uq_membership_plans_name_alive` is the canonical name (referenced by `_is_plan_name_conflict` in service). Document in migration comment.
- **Phase 16 must NOT prematurely add the `memberships` table or its FK** — even as a stub. ROADMAP gives Phase 17 ownership; pre-empting causes ordering ambiguity in audit/AST gates.
- **Audit gate test typo defence**: `audit.emit("membership_plan_created", ...)` is correct. `audit.emit("membership_plans_created", ...)` (plural) and `audit.emit("memberhsip_plan_created", ...)` (typo) BOTH fail the Phase 15 AST walker — this is the safety net we want.
- **`active=True` on POST default** — DTO declares `active: bool = Field(default=True)`. The DB column has `DEFAULT TRUE` too, so omitting the field works at both layers.
- **Trim happens before length check** — order in the field validator: `value.strip()` first, then min/max length validation. A payload `name="   "` after trim is empty → reject with min_length=1 message.
- **`_full_name`-style helper not needed for plans** — plans have a single `name` field. Audit payloads reference it directly; no string concatenation helper required.
- **Test for "delete frees unique-name slot"**: in `test_plans_crud.py`, create plan "Базовый" → DELETE → create plan "Базовый" again → 201 Created. Verifies partial-unique-on-alive semantics.
- **Test for "duration_days extra field rejected"**: PATCH with body `{"durationDays": 90}` → 422 with body containing reference to `durationDays` (Pydantic stock error). Verifies D-04.

</specifics>

<deferred>
## Deferred Ideas

- **`409 plan_in_use` IntegrityError translation** — Phase 17 (alongside the `memberships` FK migration). Phase 17 plan must include: (a) a regression test covering plan→membership→DELETE-plan→409 path, and (b) `_is_plan_in_use_conflict(exc)` helper checking `constraint_name == "fk_memberships_plan_id_membership_plans"`.
- **`?includeArchived=true` owner archive view** — speculative; defer until a real owner UX need surfaces in Phase 22 or later.
- **Name ILIKE search (`?q=`)** — Phase 22 if owner UI surfaces it; uses `core/sql.py:escape_like_pattern` (already exists). Would also require a btree index on `lower(name)`.
- **Membership plan price-history table** — out of scope for v1.2; the audit log captures the fact-of-change but not before/after values. Reconsider if billing reports need diff-replay.
- **`DELETE` with cascade-cancel of dependent active memberships** — owner cannot delete a plan with active memberships; Phase 17 returns 409 `plan_in_use`. There is NO cascade-cancel-and-delete shortcut. Owner must manually cancel each membership first. Acceptable trade-off for v1.2 single-zal scale.
- **Plan reactivation endpoint after soft-delete** — no `POST /membership-plans/{id}/restore`. Soft-delete is permanent at the API surface. If owner needs the same plan back, they POST a new one (the old name slot is freed by the partial-unique-on-alive). Reconsider in v1.3+ if operator feedback demands it.
- **Phase 15 deferred `auth/service.py` write-path bug** — confirmed routing to **Phase 23** (Hygiene + active sessions backend). Not absorbed into Phase 16. The full deferred-items.md for Phase 15 records the symptom, severity (medium), and recommended fix steps.
- **Per-event audit payload schema validation registry** — Phase 15 D-09 noted the additional idea of registering `(event, payload_schema)` pairs to validate kwargs. Out of scope; revisit when audit log read-side API ships in v1.3+.

</deferred>

---

*Phase: 16-Membership Plans Catalog (backend)*
*Context gathered: 2026-05-07*
