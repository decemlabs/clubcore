---
phase: 25-memberships-freeze-backend
verified: 2026-05-09T00:00:00Z
status: passed
score: 14/14 must-haves verified
overrides_applied: 0
---

# Phase 25: Memberships — Freeze (backend) Verification Report

**Phase Goal:** Reception/owner может бесплатно заморозить и разморозить membership; `end_date` сдвигается на использованные дни; resolver не отдаёт frozen membership; cancel-during-freeze работает корректно.

**Verified:** 2026-05-09
**Status:** PASSED
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (from ROADMAP Success Criteria + REQUIREMENTS)

| #  | Truth                                                                                                                                                                                | Status      | Evidence                                                                                                                                                                                                                  |
| -- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ----------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1  | Migration `0008_freeze.py` adds `freeze_days_limit` (immutable) on `membership_plans`, `freeze_days_limit_snapshot` on `memberships`, and `membership_freeze_periods` table with partial unique index `WHERE ended_at IS NULL` | VERIFIED    | `alembic/versions/0008_freeze.py` lines 38–125: `add_column freeze_days_limit` w/ DEFAULT-then-DROP-default + CHECK > 0; `freeze_days_limit_snapshot` add+backfill+SET NOT NULL; `CREATE TABLE membership_freeze_periods` + `CREATE UNIQUE INDEX uq_membership_freeze_periods_active_per_membership ... WHERE ended_at IS NULL` |
| 2  | `POST /api/v1/memberships/{id}/freeze` (CSRF, reception+owner) transitions active→frozen; `/unfreeze` closes period, shifts `end_date += use_days` (half-day rounds up), transitions frozen→active | VERIFIED    | `router.py:324–383` both endpoints with `(CREATE, MEMBERSHIPS)` + `verify_csrf`; `service.py:608–688 freeze_membership`, `service.py:691–758 unfreeze_membership` with `days_added = max(1, math.ceil(delta_seconds / 86400))` (line 738) |
| 3  | Membership detail responses include `freezeDaysLimitSnapshot`, `freezeDaysUsed`, `freezeDaysRemaining`, `currentFreezePeriod`                                                       | VERIFIED    | `schemas.py:251–254` (4 fields on `MembershipResponse`); `service.py:_build_membership_response` projects all 4; `tests/integration/memberships/test_freeze_endpoints.py:153–207` asserts 4 camelCase keys + object shape |
| 4  | Frozen membership doesn't pass check-in (reception + Telegram both return `no_active_membership` 409 without oracle leak); cancel-from-frozen owner-only and closes freeze period without extension; cumulative > limit → 409 `freeze_limit_exceeded`; concurrent freeze → 409 `already_frozen` | VERIFIED    | `test_freeze_resolver.py` (3 tests: resolver returns None, visits 409 no_active_membership, Telegram generic DM); `test_cancel_during_freeze.py` (cancel closes period, end_date unchanged, reception forbidden); `test_freeze_limit.py` (3 boundary tests); `test_freeze_race.py` (5 concurrent freezes → exactly 1×200 + 4×409 already_frozen, 1 open period, 1 audit row) |
| 5  | Each freeze/unfreeze emits `audit.emit("membership_frozen"/"membership_unfrozen", ...)` (literal); integration tests cover full freeze cycle, limit-exceeded, concurrent freeze | VERIFIED    | `service.py:674–683 audit.emit("membership_frozen", ...)` literal; `service.py:744–753 audit.emit("membership_unfrozen", ...)` literal; cancel-during-freeze emits unfrozen-then-cancelled at `service.py:558–567` then `584–592`; `test_freeze_cycle.py`, `test_freeze_limit.py`, `test_freeze_race.py` all pass |
| 6  | MEM-FRZ-04 — preventive limit guard before insert                                                                                                                                  | VERIFIED    | `service.py:643–654` checks `days_used >= freeze_days_limit_snapshot` → `FreezeLimitExceededError(fields={limit, used})`                                                                                                |
| 7  | MEM-FRZ-07 — `cancel_membership` accepts `frozen → cancelled`, closes period, emits unfrozen (days_added=0) BEFORE cancelled                                                       | VERIFIED    | `service.py:543 _assert_can_cancel` (delegates to central guard with `frozen→cancelled` admitted via `MEMBERSHIP_STATUS_TRANSITIONS`); `service.py:551–567` close period + emit unfrozen w/ days_added=0; `service.py:584–592` emit cancelled; lexical order in same UoW |
| 8  | MEM-FRZ-AUDIT-01 — payloads include `freeze_period_id`, `started_at` (frozen) / `days_added` (unfrozen)                                                                            | VERIFIED    | `service.py:680–682` (frozen: `freeze_period_id`, `started_at` ISO); `service.py:751–752` (unfrozen: `freeze_period_id`, `days_added`)                                                                                  |
| 9  | MEM-FRZ-EP-01 — POST /freeze (CSRF, CREATE/MEMBERSHIPS), empty body, returns currentFreezePeriod                                                                                  | VERIFIED    | `router.py:324–355` summary lists 3 expected 409 codes; RBAC-04 ordering verified (`require_permission` declared at 337, `verify_csrf` at 339); `test_freeze_endpoints.py` (12 tests) |
| 10 | MEM-FRZ-EP-02 — POST /unfreeze (CSRF, CREATE/MEMBERSHIPS), empty body, returns updated endDate/freezeDaysUsed/Remaining                                                            | VERIFIED    | `router.py:358–383`; same RBAC-04 ordering; `test_freeze_cycle.py` end-to-end                                                                                                                                          |
| 11 | MEM-FRZ-EP-03 — list + GET responses include freeze projection fields with no N+1                                                                                                  | VERIFIED    | `service.py:761–879 list_memberships` uses 3 queries total (outer list + days_used GROUP BY + open periods IN-list); `_build_membership_response` for single-row paths                                                  |
| 12 | MEM-FRZ-TEST-01 — full freeze cycle test (sell 30d → freeze 5d → unfreeze → end_date+5)                                                                                            | VERIFIED    | `test_freeze_cycle.py:50 test_freeze_cycle_extends_end_date_by_used_days` — passes                                                                                                                                       |
| 13 | MEM-FRZ-TEST-02 — limit-exceeded test                                                                                                                                              | VERIFIED    | `test_freeze_limit.py` 3 tests (at-limit, above-limit, below-limit) — all pass                                                                                                                                          |
| 14 | MEM-FRZ-TEST-03 — concurrent freeze race test                                                                                                                                      | VERIFIED    | `test_freeze_race.py:53 test_concurrent_freeze_race_serialised_by_partial_unique_index` — passes (5 parallel POSTs, 1×200 + 4×409 already_frozen, 1 open period, 1 audit row)                                          |

**Score:** 14/14 truths verified

### Required Artifacts

| Artifact                                                                                  | Expected                                                          | Status      | Details                                                                                          |
| ----------------------------------------------------------------------------------------- | ----------------------------------------------------------------- | ----------- | ------------------------------------------------------------------------------------------------ |
| `apps/backend/alembic/versions/0008_freeze.py`                                            | Freeze migration revising 0007                                    | VERIFIED    | down_revision = `0007_status_taxonomy`; upgrade adds 3 columns/tables; downgrade reverses        |
| `apps/backend/app/modules/memberships/models.py`                                          | `MembershipFreezePeriod` ORM + `freeze_days_limit*` columns       | VERIFIED    | lines 61, 78, 124, 168–239 — Plan + Membership extended; new ORM model w/ partial unique index   |
| `apps/backend/app/modules/memberships/constants.py`                                       | Populated transition map                                          | VERIFIED    | `active: {expired, cancelled, frozen}`, `frozen: {active, cancelled}`                            |
| `apps/backend/app/modules/memberships/repository.py`                                      | 5 freeze helpers + resolver UNTOUCHED                             | VERIFIED    | `insert_freeze_period`, `get_open_freeze_period`, `get_freeze_period_by_id`, `compute_freeze_days_used`, `_freeze_days_used_subquery` (lines 406–518); `find_active_for_client` byte-identical at line 318 |
| `apps/backend/app/modules/memberships/service.py`                                         | `freeze_membership`, `unfreeze_membership`, cancel ext, projector | VERIFIED    | `_assert_can_freeze`, `_assert_can_unfreeze`, `_is_already_frozen_conflict`, `_build_membership_response`, `freeze_membership`, `unfreeze_membership`, extended `cancel_membership`, rewritten `list_memberships` |
| `apps/backend/app/modules/memberships/schemas.py`                                         | `FROZEN`, `FreezePeriodResponse`, 4 freeze fields                 | VERIFIED    | line 164 (FROZEN), 125 (FreezePeriodResponse), 251–254 (4 freeze fields), 57 (`freeze_days_limit` on plan create) |
| `apps/backend/app/modules/memberships/router.py`                                          | `/freeze` + `/unfreeze` endpoints; no Wave 4 markers              | VERIFIED    | lines 324–383; zero `# type: ignore[attr-defined].*Wave 4` markers (grep returns 0 matches)      |
| `apps/backend/app/core/exceptions.py`                                                     | `FreezeLimitExceededError`, `AlreadyFrozenError`                  | VERIFIED    | lines 176–201 — both ConflictError, 409                                                          |
| `apps/backend/alembic/env.py`                                                             | Autogenerate suppression for partial unique index                 | VERIFIED    | line 67 includes `uq_membership_freeze_periods_active_per_membership`; `alembic check` reports zero drift |
| `tests/unit/memberships/test_state_machine.py`                                            | 16-cell matrix                                                    | VERIFIED    | All 16 cells covered; 9 invalid + 5 valid + 2 contents tests; passes                             |
| `tests/unit/memberships/test_freeze_days_computation.py`                                  | Pure-helper ceil tests                                            | VERIFIED    | 9 cases (zero, exact, fractional, just-over, multi-period, etc.); passes                         |
| `tests/integration/memberships/test_freeze_cycle.py`                                      | MEM-FRZ-TEST-01                                                   | VERIFIED    | passes                                                                                            |
| `tests/integration/memberships/test_freeze_limit.py`                                      | MEM-FRZ-TEST-02 (3 boundary tests)                                | VERIFIED    | passes                                                                                            |
| `tests/integration/memberships/test_freeze_race.py`                                       | MEM-FRZ-TEST-03                                                   | VERIFIED    | passes                                                                                            |
| `tests/integration/memberships/test_freeze_resolver.py`                                   | MEM-FRZ-06 (resolver + visits + Telegram)                         | VERIFIED    | 3 tests pass — resolver None, visits 409, Telegram generic oracle-safe DM                        |
| `tests/integration/memberships/test_cancel_during_freeze.py`                              | MEM-FRZ-07                                                        | VERIFIED    | 2 tests pass — both audit rows present, end_date unchanged, reception forbidden                  |
| `tests/integration/memberships/test_freeze_endpoints.py`                                  | MEM-FRZ-EP-01..03 RBAC + shape                                    | VERIFIED    | 12 tests pass (RBAC matrix, CSRF, response shape, currentFreezePeriod object)                    |
| `tests/integration/memberships/test_freeze_helpers.py`                                    | repository aggregate sanity                                       | VERIFIED    | 2 tests pass                                                                                      |

### Key Link Verification

| From                              | To                                              | Via                                                        | Status   | Details                                                                                                            |
| --------------------------------- | ----------------------------------------------- | ---------------------------------------------------------- | -------- | ------------------------------------------------------------------------------------------------------------------ |
| router.freeze_membership          | service.freeze_membership                       | direct call line 354                                       | WIRED    | Plain call (Wave 4 markers removed); request body empty; returns envelope                                          |
| router.unfreeze_membership        | service.unfreeze_membership                     | direct call line 382                                       | WIRED    | Same shape                                                                                                          |
| service.freeze_membership         | repository.insert_freeze_period                 | line 657                                                    | WIRED    | session.add via repository helper                                                                                  |
| service.freeze_membership         | repository.compute_freeze_days_used             | line 644                                                    | WIRED    | Preventive limit guard fed by aggregate                                                                            |
| service.freeze_membership         | IntegrityError → AlreadyFrozenError             | `_is_already_frozen_conflict` line 666                     | WIRED    | constraint name match → 409 already_frozen                                                                          |
| service.unfreeze_membership       | repository.get_open_freeze_period               | line 726                                                    | WIRED    | Defence-in-depth raise on None                                                                                     |
| service.cancel_membership         | repository.get_open_freeze_period (frozen path) | line 552                                                    | WIRED    | closes period, emits unfrozen (days_added=0) before cancelled                                                      |
| service freeze/unfreeze           | audit.emit (literal strings)                    | lines 674, 744                                              | WIRED    | Literal `"membership_frozen"`/`"membership_unfrozen"`; AST gate satisfied (`tests/unit/test_audit_taxonomy.py` passes) |
| router /freeze, /unfreeze         | RBAC `require_permission(CREATE, MEMBERSHIPS)`  | lines 337, 368                                              | WIRED    | Reception+owner; CSRF after permission (RBAC-04 ordering)                                                          |
| Resolver `find_active_for_client` | UNTOUCHED                                       | git log shows no resolver line modifications in Phase 25   | WIRED    | D-25-17 invariant preserved (frozen rows naturally excluded by `status='active'` filter)                           |

### Data-Flow Trace (Level 4)

| Artifact                       | Data Variable                                                  | Source                                               | Produces Real Data | Status   |
| ------------------------------ | -------------------------------------------------------------- | ---------------------------------------------------- | ------------------ | -------- |
| `_build_membership_response`   | `freeze_days_used`                                             | `repository.compute_freeze_days_used` (real SQL)    | Yes                | FLOWING  |
| `_build_membership_response`   | `current_freeze_period`                                        | `repository.get_open_freeze_period` (real SELECT)   | Yes                | FLOWING  |
| `list_memberships`             | `days_used_map`                                                | bulk GROUP BY aggregate (real SQL on freeze table)   | Yes                | FLOWING  |
| `list_memberships`             | `open_period_map`                                              | bulk IN-list SELECT (real ORM)                       | Yes                | FLOWING  |
| `freeze_membership` audit      | `period.id`, `period.started_at`                               | actual ORM instance from `insert_freeze_period`      | Yes                | FLOWING  |
| `unfreeze_membership` audit    | `days_added`                                                   | computed from period close timestamps                | Yes                | FLOWING  |

### Behavioral Spot-Checks

| Behavior                              | Command                                                                                              | Result      | Status |
| ------------------------------------- | ---------------------------------------------------------------------------------------------------- | ----------- | ------ |
| Full backend test suite               | `uv run pytest tests/`                                                                              | 658 passed  | PASS   |
| Phase 25 unit tests                   | `uv run pytest tests/unit/memberships/test_state_machine.py tests/unit/memberships/test_freeze_days_computation.py` | 31 passed   | PASS   |
| Phase 25 integration tests (7 files)  | `uv run pytest tests/integration/memberships/test_freeze_*.py tests/integration/memberships/test_cancel_during_freeze.py` | 24 passed   | PASS   |
| Static type-check                     | `uv run mypy app/`                                                                                  | 71 files clean | PASS |
| Lint                                  | `uv run ruff check`                                                                                 | All checks passed | PASS |
| Alembic drift gate                    | `uv run alembic check`                                                                              | No new ops detected | PASS |
| Architecture                          | `uv run lint-imports`                                                                               | 3 contracts kept, 0 broken | PASS |

### Requirements Coverage

| Requirement       | Source Plan        | Description                                              | Status     | Evidence                                                                                              |
| ----------------- | ------------------ | -------------------------------------------------------- | ---------- | ----------------------------------------------------------------------------------------------------- |
| MEM-FRZ-01        | 25-01, 25-04       | freeze_days_limit on plans, immutable, w/ schemas       | SATISFIED  | migration 0008_freeze; schemas.py:57 `Field(ge=1, le=365)`; PATCH rejects via inherited `extra='forbid'` (D-25-11) |
| MEM-FRZ-02        | 25-01, 25-02       | membership_freeze_periods table + partial unique index  | SATISFIED  | migration lines 74–125; ORM model lines 168–239; partial unique index name literal-pinned             |
| MEM-FRZ-03        | 25-01, 25-02       | freeze_days_limit_snapshot column + backfill            | SATISFIED  | migration lines 59–71 with `COALESCE(plan.freeze_days_limit, 14)`                                     |
| MEM-FRZ-04        | 25-03              | service.freeze_membership w/ preventive limit + 409s    | SATISFIED  | service.py:608–688 (10-step UoW); guards: invalid_transition, freeze_limit_exceeded, already_frozen   |
| MEM-FRZ-05        | 25-03              | service.unfreeze_membership w/ ceil rounding            | SATISFIED  | service.py:691–758; `days_added = max(1, math.ceil(delta_seconds / 86400))`                           |
| MEM-FRZ-06        | 25-04, 25-05       | resolver excludes frozen; oracle-safe DMs               | SATISFIED  | D-25-17 (resolver untouched); test_freeze_resolver.py 3 tests pass                                    |
| MEM-FRZ-07        | 25-03, 25-05       | cancel from frozen closes period w/o extension          | SATISFIED  | service.py:551–567 + 584–592; test_cancel_during_freeze.py 2 tests pass                               |
| MEM-FRZ-EP-01     | 25-04              | POST /freeze (CSRF, CREATE/MEMBERSHIPS)                 | SATISFIED  | router.py:324–355; RBAC-04 ordering enforced statically                                               |
| MEM-FRZ-EP-02     | 25-04              | POST /unfreeze                                           | SATISFIED  | router.py:358–383                                                                                      |
| MEM-FRZ-EP-03     | 25-02, 25-03, 25-04| GET/list responses include 4 freeze fields              | SATISFIED  | schemas.py:251–254; service.py projects with no N+1                                                   |
| MEM-FRZ-AUDIT-01  | 25-03              | audit.emit literal strings + payloads                   | SATISFIED  | service.py:674, 744 (LITERAL); cancel-during-freeze adds days_added=0 sentinel emit                   |
| MEM-FRZ-TEST-01   | 25-05              | full freeze cycle integration test                      | SATISFIED  | test_freeze_cycle.py passes                                                                           |
| MEM-FRZ-TEST-02   | 25-05              | limit-exceeded integration test                         | SATISFIED  | test_freeze_limit.py 3 tests pass                                                                     |
| MEM-FRZ-TEST-03   | 25-05              | concurrent freeze race integration test                 | SATISFIED  | test_freeze_race.py passes                                                                            |

All 14 requirement IDs satisfied. Zero orphaned requirements; the requirement table in REQUIREMENTS.md and the success-criteria block in ROADMAP.md fully align with delivered code.

**Note on REQUIREMENTS.md MEM-FRZ-01 wording (`0007_freeze.py`):** The verbatim REQ text says migration `0007_freeze.py`, but Phase 24 took `0007_status_taxonomy` first; D-25-01 in CONTEXT.md explicitly resolves this to `0008_freeze.py` (rename only — semantics preserved). Acceptable: filename is implementation detail, not a contract item.

### Anti-Patterns Found

| File                                              | Line | Pattern                            | Severity | Impact                                                                                                  |
| ------------------------------------------------- | ---- | ---------------------------------- | -------- | ------------------------------------------------------------------------------------------------------- |
| (none)                                            | —    | —                                  | —        | grep for `# type: ignore.*Wave 4` and `raise NotImplementedError.*Phase 25` returns 0 matches in router.py + service.py |

No blockers, warnings, or info-level anti-patterns detected. The Wave 3 transient `# type: ignore[attr-defined]  # Wave 4` markers have been removed (CONTEXT invariant). The `# noqa: SVC001` markers on `_build_membership_response` and `_expire_due_memberships` are documented opt-outs (read-only projector + ARQ caller-owns-txn helper).

### Critical Invariants — Codebase Confirmation

| Invariant                                                                                                                  | Confirmed                              | Evidence                                                                                                       |
| -------------------------------------------------------------------------------------------------------------------------- | -------------------------------------- | -------------------------------------------------------------------------------------------------------------- |
| Resolver `find_active_for_client` / `resolve_active_membership_by_client` UNTOUCHED (D-25-17)                              | YES                                    | git log Phase 25 commits show no resolver-line modifications; resolver code lines 318–354 (repo) + 899–927 (svc) byte-identical to Phase 24 |
| SVC001 commit-gate: public `freeze_membership` + `unfreeze_membership` end with `await session.commit()`                   | YES                                    | service.py:686 + 756 (`await session.commit()` before return)                                                   |
| AST literal-string audit gate: `audit.emit("membership_frozen"/"membership_unfrozen", ...)` use string literals             | YES                                    | service.py:676, 560, 746 — all literal strings; `tests/unit/test_audit_taxonomy.py` passes                      |
| RBAC-04 ordering: `Depends(require_permission(...))` BEFORE `Depends(verify_csrf)` in /freeze + /unfreeze                  | YES                                    | router.py:337/339 + 368/370; `tests/integration/test_route_introspection.py` passes (3/3)                       |
| Cancel-during-freeze: `membership_unfrozen (days_added=0)` BEFORE `membership_cancelled` in same UoW                       | YES                                    | service.py:558 emits unfrozen, service.py:584 emits cancelled — both before single terminal commit at 595       |
| Half-day rounds up: `max(1, math.ceil(delta_seconds / 86400))`                                                             | YES                                    | service.py:738 — exact pattern verified                                                                         |
| State-machine: 16-cell matrix populated                                                                                    | YES                                    | constants.py:20–27 (4×4); test_state_machine.py extends matrix; 11 invalid + 5 valid cells                      |
| No Wave 3 transient `# type: ignore[attr-defined]  # Wave 4` markers remain in router.py                                   | YES                                    | grep returns 0 matches                                                                                          |
| Migration chain: `0008_freeze.py` revises from `0007_status_taxonomy`; no `previous_membership_id` (Phase 26 owns)         | YES                                    | down_revision = `"0007_status_taxonomy"` line 33; grep `previous_membership_id` returns 0 matches               |

All 9 critical invariants intact.

### Human Verification Required

None. Phase 25 is backend-only with deterministic, fully-automated verification:
- All success criteria are programmatically testable.
- No UI/UX changes (admin-web FE wiring is Phase 28 per D-25-26).
- No external service integration (no Telegram DM body changes — frozen path inherits Phase 20 oracle-safe DM verbatim).
- No real-time/visual behaviour outside of asserted test outputs.

### Gaps Summary

No gaps. Phase 25 fully delivers the freeze cycle backend:

1. Schema foundation (migration 0008_freeze, ORM model, populated transition map, exception classes) is correct and reversible (with documented data-loss caveat).
2. Repository helpers (5 functions including SQL-aggregate `compute_freeze_days_used`) preserve caller-owns-txn invariant; resolver is byte-identical (D-25-17 critical invariant honoured).
3. Service layer implements the 10-step freeze + 12-step unfreeze flows with preventive limit guard, IntegrityError translation, central transition guard reuse, and the cancel-during-freeze branch emitting `unfrozen` (days_added=0) BEFORE `cancelled` in the same UoW — all with literal-string audit payloads.
4. Schema/router contract exposes the 4 projection fields (camelCase via `BackendSchemaBase.alias_generator`) and 2 new endpoints with `(CREATE, MEMBERSHIPS)` permission + CSRF in RBAC-04 order; `MembershipPlanUpdateRequest` correctly relies on inherited `extra='forbid'` for `freeze_days_limit` immutability.
5. Test coverage: 16-cell state-machine matrix + pure ceil unit test + 6 integration tests covering full cycle, limit (3 boundaries), race (concurrent INSERT), resolver (visits + Telegram oracle-safe), cancel-during-freeze, and endpoint RBAC/shape (12 cases).

Verification gates: 658/658 tests pass, mypy clean, ruff clean, alembic drift-free, lint-imports 3/3 contracts kept.

---

## VERIFICATION PASSED

_Verified: 2026-05-09_
_Verifier: Claude (gsd-verifier)_
