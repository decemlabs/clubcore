---
phase: 26-memberships-renewal-backend
plan: 01
subsystem: database
tags: [postgres, alembic, sqlalchemy, pydantic, fastapi, memberships, renewal]

# Dependency graph
requires:
  - phase: 25-memberships-freeze-backend
    provides: |
      Alembic head 0008_freeze; freeze_days_limit_snapshot NOT NULL;
      MEMBERSHIP_STATUS_TRANSITIONS includes frozen edges;
      MembershipResponse projection helper _build_membership_response.
  - phase: 24-foundations-tech-debt-bedrock
    provides: |
      LOCKED_AUDIT_EVENTS pre-registration of ('membership_renewed','membership');
      MEMBERSHIP_STATUS_TRANSITIONS shape; resolver `today` injection pattern.
provides:
  - Alembic migration 0009_renewal — self-FK column previous_membership_id
  - ORM Membership.previous_membership_id Mapped[UUID | None]
  - Index ix_memberships_previous_membership_id (non-partial)
  - MembershipResponse.previous_membership_id (camelCase wire previousMembershipId)
  - RENEWAL_STRATEGY_FROM_SOURCE_END_DATE / RENEWAL_STRATEGY_FROM_TODAY_EXPIRED_SOURCE constants
  - CannotRenewCancelledError (409 cannot_renew_cancelled)
  - PlanArchivedError (409 plan_archived)
affects:
  - 26-02 (resolver tiebreak + repo helpers — consume new column / new exceptions)
  - 26-03 (service.renew_membership + endpoint — consume constants + exceptions)
  - 26-04 (integration tests — assert wire field + audit payload literals)
  - 27-notifications-arq (chain head 0009_renewal → 0010_notifications)
  - 28-frontend-renewal-wiring (regenerate openapi.json against new schema field)

# Tech tracking
tech-stack:
  added: []  # No new libraries — extends existing SQLAlchemy + Alembic + Pydantic stack
  patterns:
    - Postgres-native self-FK with ON DELETE SET NULL for chain attribution
    - Module-level audit-payload literal constants (RENEWAL_STRATEGY_*) for AST clarity
    - ConflictError 409 subclasses for renewal rejection semantics
    - Source-text inspection of Alembic migration files in unit tests (no DB roundtrip required)

key-files:
  created:
    - apps/backend/alembic/versions/0009_renewal.py
    - apps/backend/tests/unit/memberships/test_renewal_schema_foundation.py
    - apps/backend/tests/unit/memberships/test_renewal_constants.py
  modified:
    - apps/backend/app/modules/memberships/models.py
    - apps/backend/app/modules/memberships/schemas.py
    - apps/backend/app/modules/memberships/constants.py
    - apps/backend/app/core/exceptions.py

key-decisions:
  - "Non-partial index on previous_membership_id — partial WHERE NOT NULL deferred to backlog (D-26-02 step 3)"
  - "ON DELETE SET NULL preserves renewal-row data when source is hard-deleted (D-26-05); chain attribution recoverable via audit_log payload"
  - "Self-FK constraint name not added to alembic/env.py:_include_object — not literal-ref'd from runtime (matches Phase 25 D-25-22 convention)"
  - "MEMBERSHIP_STATUS_TRANSITIONS untouched — renewal is INSERT, not transition (D-26-24)"
  - "PlanArchivedError distinct from PlanInactiveError — archived = soft-deleted, inactive = active=False but alive (D-26-08 + D-26-09)"

patterns-established:
  - "Self-referential FK on memberships table — first instance in the codebase; future chains (e.g. plan price-history) can mirror"
  - "Module-level constants for audit payload string literals — tests assert exact match to detect drift in forensic SQL"
  - "Source-text grep tests for Alembic migrations — light-weight RED gate without DB"

requirements-completed:
  - MEM-REN-01

# Metrics
duration: 14min
completed: 2026-05-09
---

# Phase 26 Plan 01: Renewal Schema Foundation Summary

**Self-FK `previous_membership_id` column on memberships table + Pydantic / exception / constants surface required by Phase 26 service-layer waves.**

## Performance

- **Duration:** ~14 min
- **Started:** 2026-05-09 (worktree session)
- **Completed:** 2026-05-09
- **Tasks:** 2 (TDD: 4 commits — 2× RED + 2× GREEN)
- **Files modified:** 7 (4 source, 3 test/migration)

## Accomplishments
- Alembic migration `0009_renewal.py` lands with clean upgrade + downgrade + re-upgrade round-trip against `backend-postgres-1` (Postgres 16). Column / FK (`confdeltype='n'` = SET NULL) / index verified directly via `information_schema` and `pg_constraint`.
- ORM `Membership` exposes `previous_membership_id: Mapped[UUIDType | None]` plus matching `Index` in `__table_args__`; class docstring extended with the Phase 26 note.
- `MembershipResponse` extended with `previous_membership_id: UUID | None = None`; `BackendSchemaBase` alias_generator converts to `previousMembershipId` on the wire (verified via `model_dump(by_alias=True, mode="json")`).
- Two new module-level constants in `constants.py` (`RENEWAL_STRATEGY_FROM_SOURCE_END_DATE`, `RENEWAL_STRATEGY_FROM_TODAY_EXPIRED_SOURCE`) with `__all__` updated; module docstring re-flowed for Phase 26 narrative.
- Two new `ConflictError` subclasses in `core/exceptions.py` (`CannotRenewCancelledError` 409 `cannot_renew_cancelled`, `PlanArchivedError` 409 `plan_archived`); `register_exception_handlers` already serialises both via the existing `JSONResponse({code, message, fields})` shape — no new handler required.
- 18 new unit tests added (8 schema-foundation + 10 constants/exceptions/schema). All 85 unit tests in `tests/unit/memberships/` pass.

## Task Commits

Each task was executed TDD (RED then GREEN), committed atomically:

1. **Task 1 RED — schema-foundation tests (failing)** — `8769e3c` (test)
2. **Task 1 GREEN — migration 0009_renewal.py + ORM column + Index** — `d9b8013` (feat)
3. **Task 2 RED — constants/exceptions/schema tests (failing)** — `aa5ab73` (test)
4. **Task 2 GREEN — constants + exceptions + MembershipResponse field** — `345f33d` (feat)

_TDD gate compliance: both tasks shipped a `test(...)` commit before the corresponding `feat(...)` commit; no REFACTOR commit was needed (initial GREEN code passed all gates without restructuring)._

## Files Created/Modified

### Created
- `apps/backend/alembic/versions/0009_renewal.py` — Alembic migration adding `previous_membership_id` column + self-FK + index. Module docstring documents the chain (`0007 → 0008 → 0009 → 0010`), the SET-NULL rationale, the deferred partial-index optimization, and lossless-data downgrade semantics.
- `apps/backend/tests/unit/memberships/test_renewal_schema_foundation.py` — 8 unit tests covering ORM column metadata + migration source-text grep assertions (revision header, upgrade/downgrade ordering).
- `apps/backend/tests/unit/memberships/test_renewal_constants.py` — 10 unit tests covering constants literals, exception class hierarchy / status_code / code, MembershipResponse field registration + camelCase serialization, and that `MEMBERSHIP_STATUS_TRANSITIONS` is unchanged in Phase 26.

### Modified
- `apps/backend/app/modules/memberships/models.py` — Added `previous_membership_id` mapped column after `activation_policy`; added forensic `Index` to `__table_args__`; extended `Membership` class docstring with Phase 26 note.
- `apps/backend/app/modules/memberships/schemas.py` — Appended `previous_membership_id: UUID | None = None` as the LAST field on `MembershipResponse` (after `current_freeze_period`). `UUID` was already imported.
- `apps/backend/app/modules/memberships/constants.py` — Appended the two `RENEWAL_STRATEGY_*` literals after `MEMBERSHIP_STATUS_TRANSITIONS`; updated `__all__`; rewrote the second paragraph of the module docstring to capture Phase 26 framing per 26-PATTERNS.md.
- `apps/backend/app/core/exceptions.py` — Inserted `CannotRenewCancelledError` and `PlanArchivedError` between `PlanInUseError` and `InvalidTransitionError`. Both subclass `ConflictError`; docstrings call out the renewal-specific rationale and the discrimination from `PlanInactiveError`.

## Decisions Made

All decisions followed CONTEXT.md (D-26-01..D-26-13, D-26-21, D-26-24). No new decisions surfaced during execution — the planner had front-loaded everything.

Notable pattern choices already captured in CONTEXT.md but worth restating:
- Used `sa.UUID()` (declarative dialect-portable form) rather than `postgresql.UUID(as_uuid=True)` in the migration, matching the Phase 25 `0008_freeze.py:78,82,85,86` precedent.
- Used `op.f(...)` for both the FK and the index name so that `NAMING_CONVENTION` resolves them deterministically.

## Deviations from Plan

None - plan executed exactly as written.

The only deviations from the verbatim text in the plan body were minor style adjustments required by ruff:
- Two exception-class docstring lines exceeded the 100-char limit; reformatted to multi-line wrapping while preserving every fact (Phase tag, decision references, rationale).
- One unicode `×` (multiplication sign) in a test docstring was flagged by ruff RUF002 — replaced with ASCII `x`.

These are formatter-driven, not behavioural changes.

## Issues Encountered

- `uv run alembic current` initially failed with a `Settings` validation error because the worktree had no `.env` file. Created one by copying `.env.example` (which holds dev-safe placeholders); it's already in `apps/backend/.gitignore` and is not committed. This is a worktree bootstrap concern only — outside the scope of the plan.

## User Setup Required

None - no external service configuration required.

## Verification Results

| Gate | Command | Result |
|------|---------|--------|
| Alembic upgrade | `uv run alembic upgrade head` | reaches `0009_renewal (head)` |
| Alembic downgrade | `uv run alembic downgrade -1` | clean back to `0008_freeze` |
| Alembic re-upgrade | `uv run alembic upgrade head` | clean round-trip |
| Postgres column | `SELECT column_name, is_nullable, data_type FROM information_schema.columns WHERE column_name='previous_membership_id'` | `previous_membership_id\|YES\|uuid` |
| Postgres FK | `SELECT conname, contype, confdeltype FROM pg_constraint WHERE conname='fk_memberships_previous_membership_id_memberships'` | `f\|n` (foreign key, ON DELETE SET NULL) |
| Postgres index | `SELECT indexname FROM pg_indexes WHERE indexname='ix_memberships_previous_membership_id'` | row returned |
| ruff | `uv run ruff check app/modules/memberships/ app/core/exceptions.py alembic/versions/0009_renewal.py` | All checks passed |
| mypy --strict | `uv run mypy --strict app/modules/memberships/ app/core/exceptions.py` | Success: no issues found in 8 source files |
| import-linter | `uv run lint-imports` | 3 contracts kept, 0 broken |
| Unit tests | `uv run pytest tests/unit/memberships/` | 85 passed (75 pre-existing + 10 new constants + 8 new schema-foundation, of which 8+10=18 are new this plan) |

## Next Phase Readiness

Wave 2 (`26-02-PLAN.md`) can now:
- `from app.core.exceptions import CannotRenewCancelledError, PlanArchivedError`
- `from app.modules.memberships.constants import RENEWAL_STRATEGY_FROM_SOURCE_END_DATE, RENEWAL_STRATEGY_FROM_TODAY_EXPIRED_SOURCE`
- `from app.modules.memberships.models import Membership` and access `Membership.previous_membership_id`
- Instantiate `MembershipResponse(..., previous_membership_id=uuid)` without import or schema errors.

The resolver tiebreak swap (D-26-17) is intentionally NOT in this plan — it's wave 2 / 26-02. The migration shipped is purely additive: existing memberships rows have `previous_membership_id IS NULL`, fully backwards compatible.

## Self-Check: PASSED

- `apps/backend/alembic/versions/0009_renewal.py` — FOUND
- `apps/backend/tests/unit/memberships/test_renewal_schema_foundation.py` — FOUND
- `apps/backend/tests/unit/memberships/test_renewal_constants.py` — FOUND
- Commit `8769e3c` — FOUND in git log
- Commit `d9b8013` — FOUND in git log
- Commit `aa5ab73` — FOUND in git log
- Commit `345f33d` — FOUND in git log

---
*Phase: 26-memberships-renewal-backend*
*Completed: 2026-05-09*
