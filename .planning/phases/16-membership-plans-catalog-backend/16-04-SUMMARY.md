---
phase: 16-membership-plans-catalog-backend
plan: "04"
subsystem: backend/memberships
tags: [backend, fastapi, openapi, rbac, csrf, router]
dependency_graph:
  requires:
    - "apps/backend/app/modules/memberships/service.py (Plan 03 — list_plans, get_plan, create_plan, update_plan, soft_delete_plan)"
    - "apps/backend/app/modules/memberships/schemas.py (Plan 02 — MembershipPlanCreateRequest, MembershipPlanUpdateRequest, MembershipPlanResponse, MembershipPlanListQuery)"
    - "apps/backend/app/core/permissions.py (Phase 15 INFRA-08 — OWNER_ONLY includes all 4 MEMBERSHIP_PLANS pairs)"
    - "apps/backend/app/core/dependencies.py (Phase 15 — require_permission, verify_csrf, get_db, CurrentUser)"
    - "apps/backend/app/core/schemas.py (Phase 4 — ResponseEnvelope, envelope)"
  provides:
    - "MEM-PLAN-EP-01: GET /api/v1/membership-plans (list, paginated, owner-only)"
    - "GET /api/v1/membership-plans/{plan_id} (single read, owner-only)"
    - "MEM-PLAN-EP-02: POST /api/v1/membership-plans (create, 201, owner-only, CSRF)"
    - "MEM-PLAN-EP-03: PATCH /api/v1/membership-plans/{plan_id} (partial update, owner-only, CSRF)"
    - "MEM-PLAN-EP-04: DELETE /api/v1/membership-plans/{plan_id} (soft-delete 204, owner-only, CSRF, D-15)"
    - "apps/backend/openapi.json frozen wire contract with 5 new operations and 4 new component schemas"
  affects:
    - "16-05 (integration tests — drives HTTP -> router -> service -> repository -> DB path)"
    - "Phase 21 (FE api-client schema.d.ts regeneration from openapi.json)"
tech-stack:
  added: []
  patterns:
    - "5-endpoint router pattern: 2 GET (no CSRF) + 1 POST + 1 PATCH + 1 DELETE (all with CSRF)"
    - "RBAC-04 ordering invariant: require_permission BEFORE verify_csrf in every mutation signature"
    - "v1 router extension: single import + single include_router line"
    - "OpenAPI byte-stable export: json.dumps(sort_keys=True, indent=2) + trailing newline"
key-files:
  created:
    - apps/backend/app/modules/memberships/router.py
  modified:
    - apps/backend/app/api/v1/router.py
    - apps/backend/openapi.json
key-decisions:
  - "RBAC-04 ordering: require_permission before verify_csrf in all 3 mutation signatures — enforced by test_route_introspection.py"
  - "D-15: DELETE is soft-delete only — no 409 plan_in_use in Phase 16; memberships FK arrives in Phase 17"
  - "MembershipPlanListQuery NOT a named component schema in OpenAPI (FastAPI Depends() inlines query params instead)"
  - "import get_db from app.core.database (not app.core.dependencies) — mirrors clients/router.py template exactly"
metrics:
  duration: 4min
  completed: "2026-05-07"
  tasks_completed: 2
  tasks_total: 2
  files_created: 1
  files_modified: 2
---

# Phase 16 Plan 04: HTTP Edge — Membership Plans Router and OpenAPI Spec Summary

**5 FastAPI endpoints mounted at /api/v1/membership-plans with owner-only RBAC, CSRF on mutations, RBAC-04 ordering invariant, and byte-stable openapi.json regenerated with 5 new operations and 4 new component schemas**

## Performance

- **Duration:** 4 min
- **Started:** 2026-05-07T13:45:28Z
- **Completed:** 2026-05-07T13:49:30Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- Created `apps/backend/app/modules/memberships/router.py` with 5 endpoints mirroring clients/router.py exactly:
  - GET /api/v1/membership-plans — list alive plans (MEM-PLAN-EP-01), no CSRF
  - GET /api/v1/membership-plans/{plan_id} — read single plan, no CSRF
  - POST /api/v1/membership-plans — create plan, 201 (MEM-PLAN-EP-02), CSRF required
  - PATCH /api/v1/membership-plans/{plan_id} — partial update (MEM-PLAN-EP-03), CSRF required
  - DELETE /api/v1/membership-plans/{plan_id} — soft-delete, 204 (MEM-PLAN-EP-04, D-15), CSRF required
- Extended `apps/backend/app/api/v1/router.py` with `plans_router` import + `include_router(plans_router, prefix="/membership-plans", tags=["membership-plans"])`
- Regenerated `apps/backend/openapi.json` (50189 bytes): 5 new operations, 4 new component schemas; byte-stable on second run (identical output)
- All tests pass: route introspection (7), RBAC parity (7), mypy strict (65 files), ruff, lint-imports (3 contracts KEPT)

## Task Commits

1. **Task 1: Create memberships/router.py + extend v1 wiring** - `b448130` (feat)
2. **Task 2: Regenerate openapi.json** - `55dd7ec` (chore)

## Files Created/Modified

- `apps/backend/app/modules/memberships/router.py` — 5 endpoints; RBAC-04 ordering invariant; D-15 soft-delete annotation; mirrors clients/router.py template exactly
- `apps/backend/app/api/v1/router.py` — +2 lines: import plans_router + include_router at /membership-plans
- `apps/backend/openapi.json` — +445 lines: 5 operations, 4 schemas, byte-stable

## Route Surface

| Method | Path | Action | CSRF | Status |
|--------|------|--------|------|--------|
| GET | /api/v1/membership-plans | VIEW x MEMBERSHIP_PLANS | No | 200 |
| GET | /api/v1/membership-plans/{plan_id} | VIEW x MEMBERSHIP_PLANS | No | 200 |
| POST | /api/v1/membership-plans | CREATE x MEMBERSHIP_PLANS | Yes | 201 |
| PATCH | /api/v1/membership-plans/{plan_id} | EDIT x MEMBERSHIP_PLANS | Yes | 200 |
| DELETE | /api/v1/membership-plans/{plan_id} | DELETE x MEMBERSHIP_PLANS | Yes | 204 |

All 5 endpoints are owner-only — all 4 action x MEMBERSHIP_PLANS pairs are in OWNER_ONLY (Phase 15 INFRA-08); reception receives 403 on every endpoint.

## OpenAPI operationIds

| Method | Path | operationId |
|--------|------|-------------|
| GET | /api/v1/membership-plans | `list_plans_api_v1_membership_plans_get` |
| POST | /api/v1/membership-plans | `create_plan_api_v1_membership_plans_post` |
| GET | /api/v1/membership-plans/{plan_id} | `get_plan_api_v1_membership_plans__plan_id__get` |
| PATCH | /api/v1/membership-plans/{plan_id} | `update_plan_api_v1_membership_plans__plan_id__patch` |
| DELETE | /api/v1/membership-plans/{plan_id} | `soft_delete_plan_api_v1_membership_plans__plan_id__delete` |

## OpenAPI Component Schemas

| Schema Name | Role |
|-------------|------|
| `MembershipPlanCreateRequest` | POST request body |
| `MembershipPlanUpdateRequest` | PATCH request body |
| `MembershipPlanResponse` | 200/201 response data |
| `MembershipPlanSort` | sort enum (created_at_desc, name_asc) |
| `PaginatedData_MembershipPlanResponse_` | GET list envelope data |
| `ResponseEnvelope_MembershipPlanResponse_` | single-item 200/201 envelope |
| `ResponseEnvelope_PaginatedData_MembershipPlanResponse__` | list 200 envelope |

Note: `MembershipPlanListQuery` does NOT appear as a named component schema — FastAPI inlines query parameters from `Depends()` models directly into the operation's `parameters` array (`page`, `pageSize`, `active`, `sort` are all there).

## Byte-Stability Confirmation

Re-running `uv run python -m scripts.export_openapi` after committing produces zero diff:
`git diff --exit-code openapi.json` exits 0. CI drift gate passes.

## Wiring Location

`apps/backend/app/api/v1/router.py`:
- Import: `from app.modules.memberships.router import router as plans_router`
- Mount: `v1.include_router(plans_router, prefix="/membership-plans", tags=["membership-plans"])`

Prefix `/membership-plans` matches `Resource.MEMBERSHIP_PLANS = "membership-plans"` (kebab-case wire path, mirrors OWNER_AREA pattern).

## RBAC-04 Ordering Invariant

In every mutation endpoint, `Depends(require_permission(...))` is declared **before** `Depends(verify_csrf)` in the function signature. This ensures 401 (unauthenticated) fires before 403 (CSRF/RBAC), so an unauthenticated caller never sees a CSRF error. `tests/integration/test_route_introspection.py` enforces this statically.

## D-15 Note

Phase 16 DELETE is soft-delete only — no 409 `plan_in_use` check. The `memberships` table FK `plan_id ON DELETE RESTRICT` arrives in Phase 17. Phase 17 must add `_is_plan_in_use_conflict(exc)` helper checking `constraint_name == "fk_memberships_plan_id_membership_plans"` and a regression test (create plan + sell membership + DELETE plan -> 409).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Ruff lint errors in router.py docstring**
- **Found during:** Task 1 verification
- **Issue:** Line 7 of router.py docstring exceeded 100 chars (E501); line 16 used Unicode MULTIPLICATION SIGN character (RUF002 ambiguous character)
- **Fix:** Wrapped line 7 at 100 chars; replaced multiplication sign with `x` in the docstring
- **Files modified:** `apps/backend/app/modules/memberships/router.py`
- **Commit:** `b448130` (fix applied within task before commit)

**2. [Observation - Not a bug] get_db import path**
- The plan's action block showed a single combined import from app.core.dependencies. The actual clients/router.py template uses `from app.core.database import get_db` separately from `from app.core.dependencies import CurrentUser, require_permission, verify_csrf`. Followed the template.

## Known Stubs

None — all 5 endpoints are fully wired and delegate to the Plan 03 service layer.

## Threat Flags

None. All 7 threats from the plan's threat model are mitigated:
- T-16-04-01: All 5 endpoints declare require_permission; (VIEW|CREATE|EDIT|DELETE, MEMBERSHIP_PLANS) in OWNER_ONLY
- T-16-04-02: POST/PATCH/DELETE declare Depends(verify_csrf); ordered AFTER require_permission per RBAC-04
- T-16-04-03: Path params are UUID (122 bits entropy); route is owner-only anyway
- T-16-04-04: MembershipPlanUpdateRequest extra='forbid' rejects durationDays with 422
- T-16-04-05: Repository get_alive/list_alive filter deleted_at IS NULL; deleted_at omitted from response
- T-16-04-06: Audit is co-transactional in service layer; router is a passthrough
- T-16-04-07: Byte-stability verified by two consecutive export runs producing identical output

## Self-Check: PASSED

- FOUND: apps/backend/app/modules/memberships/router.py
- FOUND: apps/backend/app/api/v1/router.py (modified)
- FOUND: apps/backend/openapi.json (regenerated)
- FOUND: commit b448130 (Task 1 — router)
- FOUND: commit 55dd7ec (Task 2 — openapi.json)

---
*Phase: 16-membership-plans-catalog-backend*
*Completed: 2026-05-07*
