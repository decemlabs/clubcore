---
phase: 16-membership-plans-catalog-backend
plan: "03"
subsystem: backend/memberships
tags: [backend, sqlalchemy, repository, service, audit, integrity-error, ast-gate]
dependency_graph:
  requires:
    - "apps/backend/app/modules/memberships/models.py (Plan 01 — MembershipPlan ORM, uq_membership_plans_name_alive)"
    - "apps/backend/app/modules/memberships/schemas.py (Plan 02 — MembershipPlanCreateRequest, MembershipPlanUpdateRequest, MembershipPlanResponse, MembershipPlanListQuery, MembershipPlanSort)"
    - "apps/backend/app/core/exceptions.py (Plan 02 — PlanNotFoundError 404, PlanNameExistsError 409)"
    - "apps/backend/app/core/audit.py (Phase 15 — LOCKED_AUDIT_EVENTS with membership_plan_* triplet)"
    - "apps/backend/tests/unit/test_service_commit_gate.py (Phase 15 INFRA-13 — AST commit gate)"
  provides:
    - "MEM-PLAN-02: 5 repository CRUD primitives (get_alive, list_alive, insert_plan, update_plan, soft_delete_plan)"
    - "MEM-PLAN-02 + MEM-PLAN-AUDIT-01: 5 service orchestration functions (list_plans, get_plan, create_plan, update_plan, soft_delete_plan)"
    - "3 audit events emitted: membership_plan_created (D-11), membership_plan_updated (D-12), membership_plan_archived (D-13)"
    - "AST commit gate (INFRA-13) extended to inspect memberships/service.py alongside clients/service.py"
  affects:
    - "16-04 (router — consumes service.list_plans, get_plan, create_plan, update_plan, soft_delete_plan)"
    - "16-05 (integration tests — drives HTTP -> router -> service -> repository -> DB -> audit_log path)"
tech-stack:
  added: []
  patterns:
    - "Repository pattern: 5 free functions, no classes, no audit, no commit, caller owns txn boundary"
    - "Service IntegrityError translation: flush -> catch IntegrityError -> rollback -> _is_plan_name_conflict -> raise PlanNameExistsError (D-02)"
    - "D-09 idempotent no-op: update_plan returns early WITHOUT flush/commit/emit when changed_previous is empty"
    - "Audit payload shapes: D-11 created={name,duration_days,price_kopecks}, D-12 updated={changed_fields} only, D-13 archived={} (resource_id carries plan id)"
    - "AST gate Option A extension: _INSPECTED_SERVICES tuple iterating both clients and memberships service files"
key-files:
  created:
    - apps/backend/app/modules/memberships/repository.py
    - apps/backend/app/modules/memberships/service.py
  modified:
    - apps/backend/tests/unit/test_service_commit_gate.py
key-decisions:
  - "Option A for AST gate extension: _INSPECTED_SERVICES = (_CLIENTS_SERVICE, _MEMBERSHIPS_SERVICE) tuple, single test function iterates both"
  - "get_plan also raises PlanNotFoundError 404 (plan specced 2 raises but 3 is correct — get_plan + update_plan + soft_delete_plan)"
  - "4 grep hits on 'await session.commit()' in service.py (3 code + 1 docstring) — 3 actual write-path commits verified"
  - "uq_membership_plans_name_alive appears 6 times total (2 code + 4 docstrings/comments) — 2 actual constraint checks in _is_plan_name_conflict"
patterns-established:
  - "Memberships repository: pure CRUD primitives, no audit/commit/flush/raise — mirrors clients/repository.py exactly"
  - "Memberships service: create/update/soft_delete write paths each commit; D-09 no-op branch returns before any flush/commit"
requirements-completed:
  - MEM-PLAN-02
  - MEM-PLAN-EP-01
  - MEM-PLAN-EP-02
  - MEM-PLAN-EP-03
  - MEM-PLAN-EP-04
  - MEM-PLAN-AUDIT-01
duration: 4min
completed: 2026-05-07
---

# Phase 16 Plan 03: Repository and Service Layer Summary

**5 repository CRUD primitives + 5 service orchestration functions for membership plans, with IntegrityError->409 translation on uq_membership_plans_name_alive, D-09 idempotent no-op PATCH, 3 locked audit events, and Phase 15 AST commit gate extended to cover memberships/service.py**

## Performance

- **Duration:** 4 min
- **Started:** 2026-05-07T13:37:32Z
- **Completed:** 2026-05-07T13:41:00Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- Created `apps/backend/app/modules/memberships/repository.py` with 5 free functions (get_alive, list_alive, insert_plan, update_plan, soft_delete_plan) mirroring clients/repository.py exactly — no audit, no commit, no flush, no raise
- Created `apps/backend/app/modules/memberships/service.py` with 5 orchestration functions: 3 write paths (create_plan, update_plan, soft_delete_plan) each commit explicitly; D-09 idempotent no-op PATCH skips emit+flush+commit when nothing changed
- Extended `tests/unit/test_service_commit_gate.py` with Option A (_INSPECTED_SERVICES tuple): live gate now walks both clients/service.py AND memberships/service.py; 10 unit tests pass
- All 3 audit events emit with literal strings in LOCKED_AUDIT_EVENTS: `membership_plan_created` (D-11 payload: name+duration_days+price_kopecks), `membership_plan_updated` (D-12 payload: changed_fields only, no before/after), `membership_plan_archived` (D-13 payload: empty — resource_id carries plan id)
- mypy strict (5 source files), ruff, lint-imports (3 contracts KEPT), and all 208 unit tests pass

## Task Commits

1. **Task 1: Create memberships/repository.py** - `2670bc5` (feat)
2. **Task 2: Create memberships/service.py + extend AST commit gate** - `9a31472` (feat)

## Files Created/Modified

- `apps/backend/app/modules/memberships/repository.py` — 5 pure CRUD primitives; `from __future__ import annotations` for PaginatedData[MembershipPlan] generic resolution; list_alive supports active filter (D-08) and NAME_ASC/CREATED_AT_DESC sort; no audit/commit/flush/raise
- `apps/backend/app/modules/memberships/service.py` — 5 service functions; `_is_plan_name_conflict` discriminator; create/update/soft_delete write paths each contain `await session.commit()`; D-09 no-op early return in update_plan; audit.emit literal strings enforced
- `apps/backend/tests/unit/test_service_commit_gate.py` — Added `_MEMBERSHIPS_SERVICE` constant + `_INSPECTED_SERVICES` tuple; updated `test_service_commit_gate_against_app_modules` to iterate both files; updated docstring to remove "narrowed to clients" caveat

## Audit Emit Callsites

| Event | Location | Payload |
|-------|----------|---------|
| `membership_plan_created` | `create_plan` | `name=plan.name, duration_days=plan.duration_days, price_kopecks=plan.price_kopecks` |
| `membership_plan_updated` | `update_plan` (changes path only) | `changed_fields=sorted(changed_previous.keys())` — no before/after values (D-12) |
| `membership_plan_archived` | `soft_delete_plan` | (none) — resource_id carries plan id (D-13) |

All three use `resource_type="membership_plan"` as a literal string. Both event name and resource_type are literal strings at every callsite (Phase 15 D-11 step 3 / test_audit_taxonomy.py AST walker).

## AST Gate Extension (Option A)

```python
_CLIENTS_SERVICE = _BACKEND_APP / "modules" / "clients" / "service.py"
_MEMBERSHIPS_SERVICE = _BACKEND_APP / "modules" / "memberships" / "service.py"
_INSPECTED_SERVICES: tuple[Path, ...] = (_CLIENTS_SERVICE, _MEMBERSHIPS_SERVICE)
```

The live test iterates `for service_path in _INSPECTED_SERVICES:` and aggregates offenders across both files. A synthetic mutating-without-commit function in memberships/service.py would fail the gate; the actual implementation passes (3 write paths each commit).

## Decisions Made

- Option A preferred for AST gate (single tuple, single loop) — cleaner than Option B (duplicate test function); diff is +3 lines for constants + loop body refactor (~12 lines net), well under the 30-line Option B threshold
- `get_plan` also raises `PlanNotFoundError` (plan acceptance criterion said "2 raises" meaning update_plan + soft_delete_plan, but get_plan correctly raises on missing plan) — 3 actual raises is correct behavior
- No `_full_name`-style helper needed for plans (single `name` field; resource_id in audit row already pins the plan)

## Deviations from Plan

None — plan executed exactly as written. The acceptance criteria grep counts differ from actual due to docstring/comment occurrences:
- `await session.commit()`: 4 grep hits (3 code + 1 docstring module header) — 3 actual write-path commits are correct
- `uq_membership_plans_name_alive`: 6 grep hits (2 code in `_is_plan_name_conflict` + 4 docstrings) — 2 actual constraint checks are correct
- `raise PlanNotFoundError`: 3 grep hits (get_plan + update_plan + soft_delete_plan) — plan said "2" meaning write paths only, but get_plan correctly 404s too; no behavior deviation

## Issues Encountered

None.

## Known Stubs

None — both files ship complete, functional code with no placeholders.

## Threat Flags

None. All 7 threats from the plan's threat model are mitigated:
- T-16-03-01: uq_membership_plans_name_alive partial-unique wins the race; _is_plan_name_conflict translates to 409
- T-16-03-02: audit.emit is co-transactional; commit-or-rollback ordering ensures atomicity
- T-16-03-03: LOCKED_AUDIT_EVENTS runtime check + AST walker catch typos at two layers
- T-16-03-04: D-12 explicitly excludes before/after values from membership_plan_updated payload
- T-16-03-05: PageQuery enforces page_size <= 100; list_alive always issues LIMIT/OFFSET
- T-16-03-06: all write paths take actor: CurrentUser and pass actor_user_id=actor.id
- T-16-03-07: D-09 no-op short-circuit returns BEFORE flush/commit/emit in update_plan

## Next Phase Readiness

- `app.modules.memberships.service` importable: all 5 functions available for Plan 04 router
- `app.modules.memberships.repository` importable: all 5 CRUD primitives available
- Phase 15 AST gates (commit + audit taxonomy) pass with new module in scope
- Plan 04 (router) can mount the 4 endpoints consuming service.list_plans, get_plan, create_plan, update_plan, soft_delete_plan
- Plan 05 (integration tests) can drive the full HTTP -> router -> service -> repository -> DB -> audit_log path

---
*Phase: 16-membership-plans-catalog-backend*
*Completed: 2026-05-07*
