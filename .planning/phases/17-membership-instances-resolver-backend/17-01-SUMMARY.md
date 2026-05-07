---
phase: 17-membership-instances-resolver-backend
plan: 01
subsystem: backend/memberships
tags: [migration, orm, schemas, exceptions, declarative-half]
requires:
  - Phase 16 complete (membership_plans table, MembershipPlan ORM, plan service+router)
  - alembic head = 0004_membership_plans before this plan
provides:
  - memberships table (16 columns, 2 FKs ON DELETE RESTRICT, 2 CHECK constraints, composite DESC index)
  - app.modules.memberships.models.Membership ORM class
  - 6 new schema symbols (MembershipCreateRequest, MembershipCancelRequest, MembershipResponse, MembershipListQuery, MembershipStatus, MembershipListSort)
  - 4 new domain errors (PlanInactiveError, PlanInUseError, InvalidTransitionError, MembershipNotFoundError)
affects:
  - Plan 17-02 (resolver scaffolding) — consumes Membership ORM via ActiveMembership Protocol
  - Plan 17-03 (service layer) — consumes schemas + exceptions
  - Plan 17-04 (router + migration apply) — applies migration, wires endpoints
tech-stack:
  added: []  # zero new runtime deps
  patterns:
    - "FK constraint name pinning via op.f() in migration AND ForeignKey(name=...) in ORM"
    - "Composite index DESC ordering installed via raw op.execute() (CD-04)"
    - "Pydantic explicit-null guard ported verbatim from Phase 16 D-05"
    - "Domain errors aggregated in core/exceptions.py (vs per-module)"
key-files:
  created:
    - apps/backend/alembic/versions/0005_memberships.py
  modified:
    - apps/backend/app/modules/memberships/models.py
    - apps/backend/app/modules/memberships/schemas.py
    - apps/backend/app/core/exceptions.py
decisions:
  - "Migration NOT applied in this plan — Plan 17-04 [BLOCKING] task owns the apply step (per phase_specific_notes)"
  - "All FK names pinned with name=op.f(...) in migration and matching ForeignKey(name=...) in ORM"
  - "MembershipResponse exposes all 13 listed snapshot+lifecycle fields (D-10) — no PII concerns per T-17-03"
metrics:
  duration: "~15 minutes"
  completed: 2026-05-07
  tasks: 4
  files: 4
  commits: 4
  unit_tests_passing: 229
---

# Phase 17 Plan 01: Membership Schema Foundation Summary

Shipped the declarative half of Phase 17 — Alembic migration 0005, the `Membership` ORM class, all 6 membership-instance Pydantic schemas, and 4 new domain error classes — so Plans 17-02/17-03/17-04 can author the resolver, service, and router without forward-reference gymnastics.

## What Was Built

### Task 1: Alembic migration `0005_memberships.py` (commit `36d66f7`)

New migration creates the `memberships` table with:

- **17 columns total** — 13 declared + 3 from mixins (`id`, `created_at`, `updated_at`):
  - `id`, `client_id`, `plan_id` UUIDs
  - Snapshot fields: `plan_name_snapshot` `VARCHAR(120)`, `duration_days_snapshot` `INTEGER`, `price_kopecks_snapshot` `BIGINT`
  - Date fields: `start_date`, `end_date` (`DATE`, inclusive)
  - Lifecycle: `status` `VARCHAR(16) DEFAULT 'active'`, `cancelled_at` `TIMESTAMPTZ`, `cancel_reason` `TEXT`
  - Payment: `paid_at` `TIMESTAMPTZ`, `notes` `TEXT`
  - `activation_policy` `VARCHAR(32) DEFAULT 'purchase_date'`
- **Two CHECK constraints** (named `ck_memberships_status` and `ck_memberships_activation_policy` via NAMING_CONVENTION).
- **Two FKs ON DELETE RESTRICT** to `clients.id` and `membership_plans.id`. The `fk_memberships_plan_id_membership_plans` constraint name is the canonical literal that Plan 17-03's `_is_plan_in_use_conflict` will match against (D-05).
- **Composite resolver index** `ix_memberships_client_id_status_end_date` on `(client_id, status, end_date DESC)` installed via raw `op.execute()` to keep the DESC qualifier explicit.
- **No `deleted_at`** — lifecycle is purely status-based per D-12.
- **No partial-unique on (client_id, status)** — D-01 stacking is intentional.

`down_revision = "0004_membership_plans"` chains correctly. Migration `--sql` dry run produces clean DDL with all constraints named per NAMING_CONVENTION. Per phase_specific_notes, the migration was NOT applied in this plan; Plan 17-04 owns the apply step.

### Task 2: `Membership` ORM class in `models.py` (commit `bc14244`)

Added `class Membership(Base, UUIDPkMixin, TimestampMixin)` alongside the existing `MembershipPlan` class — both coexist in the same file (Phase 17 EXTENDS the module, does not split it). Key points:

- **No `SoftDeleteMixin`** — Membership lifecycle is purely status-based. Cancelled rows keep their FK reference and block plan deletion (D-06).
- All 13 declared columns match the migration column-for-column with appropriate `Mapped[...]` types (`UUIDType`, `str`, `int`, `date`, `datetime | None`, etc.).
- `ForeignKey(name="fk_memberships_plan_id_membership_plans")` and `ForeignKey(name="fk_memberships_client_id_clients")` pin the FK names defensively — service.py:_is_plan_in_use_conflict will match the first as a literal (D-05).
- `__table_args__` declares both CHECK constraints (using NAMING_CONVENTION-friendly short names) plus the composite index with `text("end_date DESC")` for DESC ordering.
- Class structurally satisfies the future `ActiveMembership` Protocol (D-18) — `id`, `client_id`, `end_date`, `status` are all mapped attributes.

### Task 3: 6 new schema symbols in `schemas.py` (commit `b574902`)

Appended to the existing Phase 16 plan-DTO file:

| Symbol | Type | Purpose |
|--------|------|---------|
| `MembershipStatus` | StrEnum | `active`/`expired`/`cancelled` |
| `MembershipListSort` | StrEnum | `created_at_desc` (default), `end_date_desc`, `start_date_desc` |
| `MembershipCreateRequest` | BackendSchemaBase | POST body `{clientId, planId, paidAt?, notes?(<=1000)}` (D-03) |
| `MembershipCancelRequest` | BackendSchemaBase | POST cancel body `{reason?(<=500)}` with verbatim Phase 16 D-05 explicit-null guard (D-11) |
| `MembershipResponse` | ResponseData | All 15 fields (id, clientId, planId, 3 snapshot fields, 2 dates, status, 4 lifecycle nullable fields, createdAt, updatedAt) (D-10) |
| `MembershipListQuery` | PageQuery | `clientId?`, `status?`, `sort` (D-09) |

Pydantic boundary validated end-to-end: explicit-null on `{reason: null}` rejected; camelCase `paidAt` ↔ `paid_at` aliasing works; max_length caps enforced; `extra='forbid'` rejects server-computed fields like `startDate` if smuggled in.

### Task 4: 4 new domain errors in `core/exceptions.py` (commit `077ad87`)

| Class | Parent | code | status_code |
|-------|--------|------|-------------|
| `PlanInactiveError` | ConflictError | `plan_inactive` | 409 |
| `PlanInUseError` | ConflictError | `plan_in_use` | 409 |
| `InvalidTransitionError` | ConflictError | `invalid_transition` | 409 |
| `MembershipNotFoundError` | NotFoundError | `membership_not_found` | 404 |

`InvalidTransitionError` accepts `fields={"from_status": ..., "to_status": ...}` via the inherited `AppError.__init__(message, *, fields=...)` signature — verified.

## Verification Results

| Check | Result |
|-------|--------|
| `uv run mypy app/modules/memberships/models.py app/modules/memberships/schemas.py app/core/exceptions.py` | Success, 0 issues |
| `uv run ruff check` (4 files) | All checks passed |
| `uv run lint-imports` | 3 contracts kept, 0 broken |
| `uv run alembic upgrade head --sql` | Generates correct DDL (all constraints, composite DESC index) |
| `uv run pytest tests/unit/ -q -x` | 229 passed in 0.37s |
| Pydantic boundary script (camelCase, explicit-null, max_length, extra='forbid') | OK |
| Membership ORM has all 16 expected column names | OK |
| All 4 errors importable + correct parent + code/status_code attrs | OK |

## Deviations from Plan

### Adjustment to verification scope (deferred apply)

**[Adjustment - Phase Notes Override] Migration apply deferred to Plan 17-04**

- **Why:** The plan's `<verify><automated>` block called for `uv run alembic upgrade head` after Task 1, but the phase-level `phase_specific_notes` explicitly state: "Don't APPLY the migration here — Plan 17-04 [BLOCKING] task does the apply." Applying after Task 1 (before Task 2 declares the ORM) would also cause `alembic check` to flag a spurious drop-table drift because the ORM lacks the matching `Membership` class.
- **Decision:** Followed phase_specific_notes. Used `alembic upgrade head --sql` to validate the migration produces correct DDL without applying. Final unit-test suite (`pytest tests/unit/`) was used for plan-level verification instead of integration tests (which require the migration applied).
- **Risk:** None. The migration round-trip will be verified when Plan 17-04 applies it. The DDL preview shows all 16 columns, both FKs ON DELETE RESTRICT with correct names, both CHECK constraints, and the composite DESC index.

No code-level Rule 1/2/3 deviations occurred. Plan executed as written within the apply-deferral boundary.

## Threat Model Coverage

All applicable mitigations from the plan's `<threat_model>` are present:

| Threat ID | Mitigation Present | Where |
|-----------|---------------------|-------|
| T-17-01 (cancel reason tampering) | Yes | `MembershipCancelRequest`: `Field(max_length=500)` + explicit-null guard |
| T-17-02 (notes tampering) | Yes | `MembershipCreateRequest`: `Field(max_length=1000)` |
| T-17-03 (snapshot disclosure) | Accepted | No PII in snapshots (plan name only) |
| T-17-04 (resolver DoS) | Yes | Composite `(client_id, status, end_date DESC)` index in migration + ORM |
| T-CONSTRAINT-DRIFT | Yes | FK name pinned via `op.f(...)` in migration AND `ForeignKey(name=...)` in ORM |
| T-PYDANTIC-NULL | Yes | Verbatim port of Phase 16 D-05 `_reject_explicit_null` validator |

## Commits

| # | Hash | Subject |
|---|------|---------|
| 1 | `36d66f7` | feat(17-01): add Alembic migration 0005_memberships |
| 2 | `bc14244` | feat(17-01): add Membership ORM class to memberships/models.py |
| 3 | `b574902` | feat(17-01): add Membership Pydantic schemas + enums |
| 4 | `077ad87` | feat(17-01): add 4 Phase 17 domain errors to core/exceptions |

## Self-Check: PASSED

Verified existence of all created/modified files and all 4 commits.

- `apps/backend/alembic/versions/0005_memberships.py` — FOUND
- `apps/backend/app/modules/memberships/models.py` — FOUND (modified)
- `apps/backend/app/modules/memberships/schemas.py` — FOUND (modified)
- `apps/backend/app/core/exceptions.py` — FOUND (modified)
- Commit `36d66f7` — FOUND in git log
- Commit `bc14244` — FOUND in git log
- Commit `b574902` — FOUND in git log
- Commit `077ad87` — FOUND in git log
