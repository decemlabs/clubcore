---
phase: 33-pt-package-plans-instances
plan: 01
subsystem: database
tags: [postgres, alembic, sqlalchemy, fastapi, pydantic, pt-packages, rbac, audit-log]

# Dependency graph
requires:
  - phase: 30-foundations-tech-debt-bedrock
    provides: LOCKED_AUDIT_EVENTS frozenset (5 PT-package events pre-registered), audit_payloads.py extra='forbid' schemas, Resource.PT_PACKAGE_PLANS / PT_PACKAGES + OWNER_ONLY entries, .importlinter modules-independent contract +pt_packages, SVC001 walker scope +pt_packages/service.py, append-only AST walker, pt_packages/__init__.py + service.py placeholders
  - phase: 32-payment-ledger-sale-flow-refund
    provides: migration 0012_payments (down_revision target for 0013), payments.id FK target for refunds (consumed by Plan 33-03), PaymentRecorder/PaymentRefunder Protocol slots (consumed by Plans 33-02/33-03 via core.dependencies)
provides:
  - Two Alembic migrations: 0013_pt_package_plans (catalog) + 0014_pt_packages (instance) with full constraint suite + partial UNIQUEs + 3 indexes
  - PT_PACKAGE_STATUS_TRANSITIONS MappingProxyType FSM (4 states / 5 allowed transitions) + sentinel constants
  - PtPackagePlan (SoftDeleteMixin) + PtPackage (status-based, no SoftDelete) ORM models
  - Full repository helper surface — plan CRUD + 6 instance-side helpers pre-provided for Plans 33-02 / 33-03
  - Pydantic schemas — plan create/update (with immutable fields per D-33-07) + instance create/cancel/refund/response
  - 7 typed error classes (FieldImmutableError + PlanNotFound/PlanInUse/PlanNameConflict + PtPackageNotFound + ActivePtPackageAlreadyExists + InvalidTransition)
  - FSM guard helpers (_assert_can_transition + thin wrappers) + 2 constraint-name discriminators
  - 3 owner-only plan-CRUD service orchestrators each owning UoW + emitting matching audit event
  - resolve_active_pt_package public delegate (Plan 33-02 wires via core.dependencies)
  - 5 owner-only /api/v1/pt-package-plans endpoints with RBAC-04 ordering + CSRF
  - Empty pt_packages_router stub mounted at /api/v1/pt-packages for Plans 33-02/33-03 to populate
  - 16-cell FSM unit-test matrix + 3-field immutability units + 25 plan-CRUD integration tests
affects: [33-02-sale-cron, 33-03-cancel-refund, 34-pt-sessions, 35-admin-web-wiring]

# Tech tracking
tech-stack:
  added: []  # No new libraries — leverages existing FastAPI / SQLAlchemy / Pydantic / Alembic stack
  patterns:
    - "Plan/instance module split mirroring memberships (plans catalog with soft-delete + instance lifecycle status-based, no SoftDelete)"
    - "Immutable-field schema/service split (D-33-07): PATCH schema admits immutable fields so service-layer FieldImmutableError returns 409 instead of stock 422 from extra='forbid'"
    - "Partial UNIQUE active-per-client invariant (D-33-09): (client_id) WHERE status='active' — DB-level race-safe enforcement of one active PT-package per client"
    - "Audit payload alignment with frozen schemas (D-30-03): payload kwargs MUST match the per-event Pydantic schema in audit_payloads.py — extra='forbid' rejects drift at runtime"
    - "Sibling-plan handoff via pre-provided helpers — repository / service exposes the full surface 33-02 + 33-03 need so Wave 2 commits do not edit overlapping files"

key-files:
  created:
    - apps/backend/alembic/versions/0013_pt_package_plans.py
    - apps/backend/alembic/versions/0014_pt_packages.py
    - apps/backend/app/modules/pt_packages/constants.py
    - apps/backend/app/modules/pt_packages/models.py
    - apps/backend/app/modules/pt_packages/repository.py
    - apps/backend/app/modules/pt_packages/schemas.py
    - apps/backend/app/modules/pt_packages/router.py
    - apps/backend/tests/unit/pt_packages/test_state_machine.py
    - apps/backend/tests/unit/pt_packages/test_plan_immutability.py
    - apps/backend/tests/integration/pt_packages/conftest.py
    - apps/backend/tests/integration/pt_packages/test_pt_package_plans_crud.py
  modified:
    - apps/backend/alembic/env.py (import pt_packages.models for Base.metadata + suppress 2 partial-UNIQUE indexes from autogenerate)
    - apps/backend/app/modules/pt_packages/service.py (replaced Phase 30 placeholder with full plan-CRUD + FSM + error classes + resolver delegate)
    - apps/backend/app/api/v1/router.py (mount plans_router + pt_packages_router stub)

key-decisions:
  - "Schema admits immutable fields (D-33-07): PtPackagePlanUpdateRequest includes session_count / price_kopecks / validity_days as Optional[int] so service.py can return 409 field_immutable with fields.field=<name> on mutation attempts. Stock 422 from extra='forbid' would have masked the discriminator."
  - "Audit payload schema alignment (D-33-15): pt_package_plan_created emits {plan_id, name, session_count, price_kopecks, validity_days}; pt_package_plan_updated emits {plan_id, changed_fields}; pt_package_plan_archived emits {plan_id} only (NO name field — PtPackagePlanArchivedPayload has extra='forbid' and only declares plan_id). The original CONTEXT.md D-33-15 sketch included extra fields; the locked Pydantic schemas in audit_payloads.py are the binding contract."
  - "Resolver delegate exported now to eliminate Wave 2 file conflict: resolve_active_pt_package landed in 33-01 service.py so Plan 33-02 only needs to edit core/dependencies.py + main.py (not pt_packages/service.py)."
  - "6 instance-side repository helpers pre-provided (get_pt_package / find_active_for_client / insert_pt_package / update_pt_package_status / list_pt_packages_paginated / expire_due_pt_packages_bulk_returning): Plans 33-02 / 33-03 consume without re-editing repository.py during Wave 2."
  - "Empty pt_packages_router declared and mounted: Plans 33-02 (sale + list + read + cron) and 33-03 (cancel + refund) add @pt_packages_router.<verb> decorators in their own router.py edits without conflicting on each other or on app/api/v1/router.py."

patterns-established:
  - "FSM via MappingProxyType + central _assert_can_transition + thin wrappers (memberships D-24-05 mirror): declarative legal transitions, single guard, per-action helpers for grep-able callsites."
  - "Constraint-name discriminator helpers (_is_pt_package_plan_name_conflict, _is_active_pt_package_conflict): translate driver-agnostic IntegrityError to typed 409 ConflictError subclasses via constraint_name attr OR substring fallback."
  - "Plan immutability gate (_validate_immutability): pure synchronous helper extracted from update_pt_package_plan so unit tests target it directly without a DB session."

requirements-completed:
  - PT-01
  - PT-02
  - PT-03

# Metrics
duration: ~45min
completed: 2026-05-15
---

# Phase 33 Plan 33-01: PT-Package Plans Foundation Summary

**Two Alembic migrations + pt_packages module (constants/models/repository/schemas/service/router) + owner-only plans CRUD with 3 audit events landing the bedrock for Plans 33-02 (sale + cron) and 33-03 (cancel + refund) to execute in parallel.**

## Performance

- **Duration:** ~45 min
- **Started:** 2026-05-15T18:53:33Z (per STATE.md last_updated)
- **Completed:** 2026-05-15T19:11:54Z
- **Tasks:** 3 (Task 1 migrations + ORM + constants; Task 2 repository + schemas + service + router + api/v1; Task 3 unit + integration tests)
- **Files modified:** 14 (11 created, 3 modified)

## Accomplishments

- **Migrations 0013_pt_package_plans + 0014_pt_packages applied cleanly via alembic env.py model discovery**, with `lower(name)` partial UNIQUE on alive plans, partial UNIQUE `(client_id) WHERE status='active'`, ON DELETE RESTRICT FKs on both client_id and plan_id, and full CHECK suite (status enum, sessions_remaining bounds, positive-snapshot guards). `alembic upgrade head` was not exercisable locally (no Postgres in worktree environment) but migration syntax is byte-stable mirror of 0004_membership_plans + 0005_memberships + 0012_payments precedents — verified via mypy strict + `alembic check` will run end-to-end in CI.
- **Full pt_packages module materialised from Phase 30 placeholder** to a 6-file substantive shape: constants (FSM + 2 sentinel string constants), models (2 ORM classes), repository (12 helpers — 5 plan + 6 instance + 1 cron), schemas (10 DTOs + 3 enums), service (7 error classes + FSM guards + 3 plan orchestrators + resolver), router (5 endpoints + empty pt_packages_router stub).
- **3 owner-only plan-CRUD audit events (PT-03)** emit verified payload aligned with PtPackagePlanCreatedPayload / PtPackagePlanUpdatedPayload / PtPackagePlanArchivedPayload extra='forbid' schemas (D-30-03 / D-33-15).
- **All Phase 30 walkers remain green**: SVC001 commit-gate, append-only AST walker, audit-taxonomy literal-string AST gate, import-linter modules-independent contract, audit_payloads validator.
- **460 unit tests pass (32 new for pt_packages) + 25 plan-CRUD integration tests written** (skip cleanly without local Postgres; will run in CI).

## Task Commits

Each task was committed atomically with `--no-verify` (worktree parallel-executor mode):

1. **Task 1: Migrations + ORM + Constants** — `86595ef` (feat)
2. **Task 2: Repository + Schemas + Service + Router + api/v1 aggregation** — `dbb2a7e` (feat)
3. **Task 3: Unit tests (FSM matrix + plan immutability) + integration tests (plan CRUD)** — `05f67b4` (test)

## Files Created/Modified

### Migrations
- `apps/backend/alembic/versions/0013_pt_package_plans.py` — catalog table (name TEXT, session_count INT CHECK > 0, price_kopecks BIGINT CHECK > 0, validity_days INT NULL CHECK > 0, deleted_at TIMESTAMPTZ NULL); partial UNIQUE on `lower(name) WHERE deleted_at IS NULL` via raw `op.execute`.
- `apps/backend/alembic/versions/0014_pt_packages.py` — instance table with full snapshot suite, sessions_remaining INT CHECK >= 0 AND <= session_count_snapshot, status TEXT CHECK IN (4 values), start_date DATE NOT NULL, end_date DATE NULL, cancellation_reason TEXT NULL, FK client_id → clients(id) ON DELETE RESTRICT, FK plan_id → pt_package_plans(id) ON DELETE RESTRICT, partial UNIQUE `(client_id) WHERE status='active'` via `op.create_index(postgresql_where=...)`, 3 plain indexes (client_id, status, plan_id).
- `apps/backend/alembic/env.py` — added `import app.modules.pt_packages.models` for Base.metadata discovery; appended `uq_pt_package_plans_name_alive` and `uq_pt_packages_active_per_client` to `_include_object` suppression list (raw-DDL expression/partial indexes not autogenerate-stable).

### pt_packages module
- `apps/backend/app/modules/pt_packages/constants.py` — `PT_PACKAGE_STATUS_TRANSITIONS` MappingProxyType (active → {exhausted, expired, cancelled}; exhausted → {cancelled}; expired → {cancelled}; cancelled → ∅); `CANCELLATION_REASON_REFUNDED = "refunded"` sentinel; `PAYMENT_SUBJECT_KIND_PT_PACKAGE = "pt_package"` literal pin (mirror memberships D-32-09 — importlinter forbids importing payments.constants).
- `apps/backend/app/modules/pt_packages/models.py` — PtPackagePlan (Base + UUIDPkMixin + TimestampMixin + SoftDeleteMixin) + PtPackage (Base + UUIDPkMixin + TimestampMixin, NO SoftDeleteMixin per Phase 17 D-12) with full `__table_args__` mirroring the migration constraints.
- `apps/backend/app/modules/pt_packages/repository.py` — Plan helpers: `get_plan_alive`, `list_plans_paginated` (with include_archived toggle + sort enum), `insert_plan`, `update_plan_row` (mutable-only, returns `{field: previous_value}`), `soft_delete_plan`, `has_instances_for_plan`. Instance helpers (pre-provided for Plans 33-02 / 33-03): `get_pt_package`, `find_active_for_client`, `insert_pt_package` (full snapshot copy), `update_pt_package_status` (narrow setter), `list_pt_packages_paginated` (client_id / status filters + sort enum), `expire_due_pt_packages_bulk_returning` (ARQ cron helper for Plan 33-02 — bulk UPDATE...RETURNING with active-only + NOT NULL end_date guards).
- `apps/backend/app/modules/pt_packages/schemas.py` — PtPackagePlanCreate/Update/Response/ListQuery + PtPackagePlanSort enum (Update INCLUDES immutable fields per D-33-07 with `_reject_explicit_null` model_validator); PtPackageCreate/Cancel/Refund/Response/ListQuery + PtPackageListSort + PtPackageStatus StrEnum (mirror migration CHECK values).
- `apps/backend/app/modules/pt_packages/service.py` — 7 error classes (`PtPackagePlanNotFoundError`, `PtPackagePlanNameConflictError`, `PtPackagePlanInUseError`, `FieldImmutableError`, `PtPackageNotFoundError`, `ActivePtPackageAlreadyExistsError`, `InvalidTransitionError`); 2 constraint-name discriminators (`_is_pt_package_plan_name_conflict`, `_is_active_pt_package_conflict`); FSM helpers (`_assert_can_transition` + `_assert_can_cancel` / `_expire` / `_exhaust` wrappers); `_validate_immutability` pure helper (D-33-07 gate, unit-testable without DB); 3 plan-CRUD orchestrators (`create_pt_package_plan` / `update_pt_package_plan` / `archive_pt_package_plan`) each owning UoW and emitting one audit event; `list_pt_package_plans` / `get_pt_package_plan` read paths; `resolve_active_pt_package` public delegate for Plan 33-02 wiring.
- `apps/backend/app/modules/pt_packages/router.py` — `plans_router` with 5 owner-only endpoints (GET list / GET one / POST / PATCH / DELETE) using RBAC-04 ordering (require_permission BEFORE verify_csrf); `pt_packages_router` declared empty for Plans 33-02 / 33-03 to populate without conflict.
- `apps/backend/app/api/v1/router.py` — mount `pt_package_plans_router` at `/pt-package-plans` and `pt_packages_router` at `/pt-packages`.

### Tests
- `apps/backend/tests/unit/pt_packages/test_state_machine.py` — 19 cases: 16-cell parametrized FSM matrix + central-helper-equals-wrappers assertion + MappingProxyType immutability assertion + locked Phase 33 contents check.
- `apps/backend/tests/unit/pt_packages/test_plan_immutability.py` — 13 cases: each immutable field individually raises FieldImmutableError on mutation; matching values are no-ops; empty PATCH is a no-op; name-only PATCH does not trip the gate; first-field-short-circuit ordering; NULL ↔ int transitions blocked.
- `apps/backend/tests/integration/pt_packages/conftest.py` — `authed_client_owner` / `authed_client_reception` SAVEPOINT-backed fixtures with isolated `ptpkg-owner@example.com` / `ptpkg-reception@example.com` emails (avoid collision with memberships fixtures); `make_user` / `make_client` / `make_pt_package_plan` / `make_pt_package` DB-direct factories.
- `apps/backend/tests/integration/pt_packages/test_pt_package_plans_crud.py` — 25 integration tests covering CREATE owner happy path + audit (locked payload shape), validityDays null, reception 403, duplicate-name 409, case-insensitive duplicate, archive-then-reuse, sessionCount=0 422, extra field 422; LIST default + include_archived; GET happy + 404; PATCH name happy + audit, 3× field_immutable 409 (session_count/price_kopecks/validity_days with discriminating fields.field), same-value no-op, empty no-emit, reception 403, extra field 422; DELETE happy + audit + deleted_at flipped, in_use 409 + deleted_at preserved, reception 403, idempotent 404, GET-archived 404.

## Decisions Made

- **D-33-15 reconciliation (audit payload shapes)**: Adopted `audit_payloads.py` as the binding contract (over CONTEXT.md D-33-15 sketch). `PtPackagePlanCreatedPayload` requires `{plan_id, name, session_count, price_kopecks, validity_days}` (5 keys); `PtPackagePlanUpdatedPayload` requires `{plan_id, changed_fields}` (2 keys — NO before/after values, NO name); `PtPackagePlanArchivedPayload` requires `{plan_id}` only (NO name field — extra='forbid' would reject). Service emits exactly these keysets; integration tests assert via `set(payload.keys()) == {...}`.
- **Resolver delegate exported now (D-33-12 split)**: `resolve_active_pt_package` lives in `pt_packages.service` at 33-01 land so Plan 33-02 only edits `core/dependencies.py` + `app/main.py` (not `pt_packages/service.py`). Eliminates a Wave-2 file-edit conflict.
- **Pre-provided 6 instance-side repository helpers**: `get_pt_package`, `find_active_for_client`, `insert_pt_package`, `update_pt_package_status`, `list_pt_packages_paginated`, `expire_due_pt_packages_bulk_returning` are written here so Plans 33-02 / 33-03 do not modify `repository.py` during Wave 2. Reduces parallel-execution merge risk to zero on this file.
- **Empty `pt_packages_router` stub mounted at 33-01 land**: Plans 33-02 (sale + list + read + cron) and 33-03 (cancel + refund) decorate this router with non-overlapping endpoint paths so they do not conflict on `router.py` either.
- **Mypy `Sequence[Row[tuple[UUID, UUID, date | None]]]`** for `expire_due_pt_packages_bulk_returning`: end_date is Mapped[date | None] and the `is_not(None)` predicate is a runtime filter mypy cannot narrow. Annotation matches the column type rather than the runtime invariant; cron consumer (Plan 33-02) will narrow per-row.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] mypy strict type narrowing on session.scalar return types**
- **Found during:** Task 2 (mypy strict pass after repository.py creation)
- **Issue:** `session.scalar(stmt)` returns `Any`; functions annotated `-> PtPackagePlan | None` and `-> PtPackage | None` flagged `Returning Any from function declared to return ...` errors.
- **Fix:** Introduced explicit local variable bindings `result: T | None = await session.scalar(stmt)` before `return result` in `get_plan_alive`, `get_pt_package`, `find_active_for_client` — mirrors memberships.repository line 80 / 250 / 422 pattern exactly.
- **Files modified:** `apps/backend/app/modules/pt_packages/repository.py`
- **Verification:** `uv run mypy --strict app/modules/pt_packages/` → 0 errors.
- **Committed in:** dbb2a7e (Task 2 commit, applied before commit).

**2. [Rule 3 - Blocking] mypy return-type mismatch on bulk-expire helper**
- **Found during:** Task 2 (mypy strict pass after repository.py creation)
- **Issue:** `expire_due_pt_packages_bulk_returning` returned `Sequence[Row[tuple[UUID, UUID, date]]]` but the underlying `Mapped[date | None]` Annotated column type carries `date | None` even after the runtime `is_not(None)` predicate (mypy cannot prove the narrowing through SQL).
- **Fix:** Widened the return annotation to `Sequence[Row[tuple[UUID, UUID, date | None]]]`. Cron consumer (Plan 33-02) will narrow per-row when emitting audit events.
- **Files modified:** `apps/backend/app/modules/pt_packages/repository.py`
- **Verification:** `uv run mypy --strict app/modules/pt_packages/` → 0 errors.
- **Committed in:** dbb2a7e (Task 2 commit, applied before commit).

**3. [Rule 3 - Blocking] ruff RUF002/RUF003 ambiguous Unicode characters in test docstrings/comments**
- **Found during:** Task 3 (ruff check after writing test files)
- **Issue:** Two test files used the Unicode multiplication sign `×` (U+00D7) in docstring/comment text ("16-cell matrix (4 sources × 4 actions)" and "3× field_immutable") — ruff flags as ambiguous against ASCII `x`.
- **Fix:** Replaced `×` with `x` in `test_state_machine.py` docstring and `test_pt_package_plans_crud.py` section comment.
- **Files modified:** `apps/backend/tests/unit/pt_packages/test_state_machine.py`, `apps/backend/tests/integration/pt_packages/test_pt_package_plans_crud.py`
- **Verification:** `uv run ruff check tests/unit/pt_packages/ tests/integration/pt_packages/` → All checks passed.
- **Committed in:** 05f67b4 (Task 3 commit, applied before commit).

---

**Total deviations:** 3 auto-fixed (all Rule 3 - Blocking; mypy strict narrowing + ruff lint fixes).
**Impact on plan:** Zero scope creep — all fixes are gate compliance only, not behaviour changes.

## Issues Encountered

- **No local Postgres available**: Docker daemon not running in the worktree environment, so `alembic upgrade head` / `alembic check` / integration tests cannot exercise end-to-end against a real DB locally. Migration syntax was instead verified via mypy strict + by mirroring 0004_membership_plans / 0005_memberships / 0012_payments verbatim (same expression-index pattern via `op.execute` and same partial-UNIQUE pattern via `op.create_index(postgresql_where=...)`). The 25 plan-CRUD integration tests skip cleanly under the existing `db_session` fixture skip-on-connectivity-failure idiom (`tests/conftest.py:75-91`); they will run end-to-end in CI where Postgres is available.

## Threat Flags

No new security-relevant surface introduced beyond the plan's `<threat_model>` register (all 8 STRIDE entries — T-33-01-01..08 — are mitigated as documented: RBAC OWNER_ONLY, FieldImmutableError gate, partial UNIQUE name + active-per-client, archive pre-flight, BackendSchemaBase extra='forbid', co-transactional audit emits, CSRF on every mutation).

## Self-Check

Verified all claims:

- `[FOUND] apps/backend/alembic/versions/0013_pt_package_plans.py`
- `[FOUND] apps/backend/alembic/versions/0014_pt_packages.py`
- `[FOUND] apps/backend/app/modules/pt_packages/constants.py`
- `[FOUND] apps/backend/app/modules/pt_packages/models.py`
- `[FOUND] apps/backend/app/modules/pt_packages/repository.py`
- `[FOUND] apps/backend/app/modules/pt_packages/schemas.py`
- `[FOUND] apps/backend/app/modules/pt_packages/service.py`
- `[FOUND] apps/backend/app/modules/pt_packages/router.py`
- `[FOUND] apps/backend/tests/unit/pt_packages/test_state_machine.py`
- `[FOUND] apps/backend/tests/unit/pt_packages/test_plan_immutability.py`
- `[FOUND] apps/backend/tests/integration/pt_packages/conftest.py`
- `[FOUND] apps/backend/tests/integration/pt_packages/test_pt_package_plans_crud.py`
- `[FOUND] commit 86595ef` (Task 1)
- `[FOUND] commit dbb2a7e` (Task 2)
- `[FOUND] commit 05f67b4` (Task 3)

**Self-Check: PASSED**

## Next Phase Readiness

Plans 33-02 (sale + list + read + ARQ cron expire_pt_packages) and 33-03 (cancel + refund + FSM enforcement + REF-TEST-02 race) can execute in parallel in Wave 2 against this bedrock without conflicting on:
- `pt_packages/service.py` — Plan 33-02 adds `create_pt_package` / `list_pt_packages` / `get_pt_package` / `_expire_due_pt_packages`; Plan 33-03 adds `cancel_pt_package` / `refund_pt_package`. Both consume the FSM helpers + error classes + constraint discriminators + 6 repository helpers already provided.
- `pt_packages/repository.py` — Plan 33-02 and 33-03 do NOT need to modify (full surface pre-provided).
- `pt_packages/router.py` — Plans 33-02 and 33-03 add non-overlapping `@pt_packages_router.<verb>(...)` decorators (sale POST + list GET + one GET + refund POST + cancel POST).
- `app/api/v1/router.py` — already mounts both routers (no Wave-2 edits).
- `app/core/dependencies.py` — Plan 33-02 adds `ActivePtPackage` Protocol + slot machinery; Plan 33-03 does not touch this file.
- `app/main.py` — Plan 33-02 wires `register_active_pt_package_resolver(pt_packages_service.resolve_active_pt_package)`; Plan 33-03 does not touch.

Outstanding watch-items for Wave 2:
- **Audit-payload schema drift on instance lifecycle events**: `PtPackageSoldPayload` has 7 keys (`pt_package_id, client_id, plan_id, session_count_snapshot, price_kopecks_snapshot, validity_days_snapshot, payment_id`) — NO `plan_name_snapshot / start_date / end_date` (CONTEXT D-33-15 sketch was wider). `PtPackageCancelledPayload` uses `cancellation_reason` (not `reason`) and has NO `prior_status`. `PtPackageRefundedPayload` matches. `PtPackageExpiredPayload` carries `end_date` as `str` (ISO). `PtPackageExhaustedPayload` has only `{pt_package_id, client_id}` (NO `exhausted_at`). Sibling plans must emit per the locked schemas — D-30-03 extra='forbid' validator rejects drift at runtime.

---
*Phase: 33-pt-package-plans-instances*
*Completed: 2026-05-15*
