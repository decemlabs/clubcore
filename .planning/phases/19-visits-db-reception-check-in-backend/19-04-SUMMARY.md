---
phase: 19-visits-db-reception-check-in-backend
plan: "04"
subsystem: backend-visits-router
tags:
  - rbac-04-ordering
  - visit-endpoints
  - openapi-regen
  - check-in-http
  - csrf-mutation
dependency_graph:
  requires:
    - 19-01 (Visit ORM, schemas, exceptions, gym_hours config)
    - 19-02 (ClientByTelegram resolver slot)
    - 19-03 (visits service — create_visit_reception, list_visits, get_visit)
  provides:
    - visits/router.py — single APIRouter with 3 endpoints for /api/v1/visits
    - app/api/v1/router.py — visits_router mounted LAST (5th) on the v1 router
    - openapi.json — regenerated with 3 new operations + schema components
  affects:
    - 19-05 (integration tests wire against these endpoints)
    - Phase 21 (FE api-client codegen reads updated openapi.json)
tech_stack:
  added: []
  patterns:
    - RBAC-04 ordering: require_permission BEFORE verify_csrf in mutation signature
    - mount-LAST: visits is 5th mount on v1 router (auth, clients, plans, memberships, visits)
    - ResponseEnvelope[T] wrapping via envelope() for all 3 endpoints
    - 201 on POST, 200 on GET (memberships/router.py precedent)
key_files:
  created:
    - apps/backend/app/modules/visits/router.py
  modified:
    - apps/backend/app/api/v1/router.py
    - apps/backend/openapi.json
decisions:
  - "mount-LAST in v1/router.py: preserves existing operationId order for byte-stable openapi.json diff"
  - "RBAC-04 ordering: require_permission(CHECK_IN, VISITS) declared BEFORE verify_csrf in POST handler signature"
  - "(CHECK_IN, VISITS) NOT in OWNER_ONLY: reception receives 201 on success (Phase 15 INFRA-08 lock confirmed)"
  - "openapi.json regenerated via scripts/export_openapi.py: additive diff only, byte-stable on repeated runs"
metrics:
  duration: "~8 minutes"
  completed: "2026-05-07"
  tasks_completed: 2
  files_changed: 3
---

# Phase 19 Plan 04: Visits Router + OpenAPI Regen Summary

**One-liner:** 3 HTTP endpoints under /api/v1/visits wired to the 19-03 service, mounted LAST on the v1 router with RBAC-04 ordering enforced, openapi.json regenerated with additive-only diff (74702 bytes, byte-stable).

## What Was Built

### Task 1: visits/router.py — 3 endpoints with RBAC-04 ordering

Single `APIRouter` with exactly 3 endpoints. Mirrors `memberships/router.py` pattern verbatim.

**Endpoint surface:**

| Method | Path | Permission | CSRF | Status |
|--------|------|------------|------|--------|
| GET | /api/v1/visits | (VIEW, VISITS) | No | 200 |
| GET | /api/v1/visits/{visit_id} | (VIEW, VISITS) | No | 200 |
| POST | /api/v1/visits | (CHECK_IN, VISITS) | Yes (RBAC-04) | 201 |

**RBAC-04 ordering (critical invariant):**

In the POST handler (`create_visit`), the function signature declares:
1. `actor: Annotated[CurrentUser, Depends(require_permission(Action.CHECK_IN, Resource.VISITS))]` — line 88
2. `_csrf: Annotated[None, Depends(verify_csrf)]` — line 90

`require_permission` (RBAC gate) fires BEFORE `verify_csrf` (CSRF gate). FastAPI resolves dependencies in declaration order. This means unauthenticated callers see 401, never a CSRF error. Enforced statically by `tests/integration/test_route_introspection.py`.

**Reception access confirmed:** `(CHECK_IN, VISITS)` is NOT in `OWNER_ONLY` (Phase 15 INFRA-08). Reception receives 201 on success, not 403. Verified by reading `app/core/permissions.py:OWNER_ONLY` frozenset.

**Service wire:** All 3 endpoints delegate to Plan 19-03 service functions:
- `list_visits` → `service.list_visits(session, query)`
- `get_visit` → `service.get_visit(session, visit_id)` (raises `VisitNotFoundError` on None → 404)
- `create_visit` → `service.create_visit_reception(session, actor, payload)` (sealed body: only `clientId`)

**409 handling:** Exceptions `OutsideGymHoursError` / `NoActiveMembershipError` / `DuplicateCheckinError` are raised in the service layer with `code` discriminators. The core exception-to-HTTP-envelope mapping (established Phase 8/16/17) translates them to 409 JSON envelopes with the literal `code` string. No router-level try/except needed.

### Task 2: Mount visits_router on v1 + regenerate openapi.json

**Step A — app/api/v1/router.py:**

Added exactly ONE import and ONE include_router call at the END of the mount block:

```python
from app.modules.visits.router import router as visits_router
# ...
v1.include_router(visits_router, prefix="/visits", tags=["visits"])
```

Mount order preserved: auth → clients → membership-plans → memberships → **visits** (5th, LAST).

**Step B — openapi.json regeneration:**

Run via `uv run python -m scripts.export_openapi` from `apps/backend/`. The script calls `create_app().openapi()` without touching DB or Redis (lifespan-safe, D-05/D-06 from Phase 9).

New entries in the spec:
- `paths['/api/v1/visits']` — GET (list) + POST (create)
- `paths['/api/v1/visits/{visit_id}']` — GET (get one)
- `components.schemas.VisitCreateRequest` — sealed POST body (`clientId` UUID only)
- `components.schemas.VisitResponse` — full response shape (8 fields)
- `components.schemas.PaginatedData_VisitResponse_` — paginated list wrapper
- `components.schemas.ResponseEnvelope_VisitResponse_` — envelope wrapper
- `components.schemas.ResponseEnvelope_PaginatedData_VisitResponse__` — paginated envelope wrapper

Diff is ADDITIVE ONLY — the 4 pre-existing top-level path groups (auth, clients, membership-plans, memberships) are untouched. The mount-LAST decision preserves their operationId order.

Byte stability: two consecutive runs produce identical 74702-byte output on macOS.

## Migration 0006_visits — BLOCKING-MIGRATION note

The orchestrator (`/gsd-execute-phase`) applied `uv run alembic upgrade head` to the dev DB BEFORE dispatching this plan (BLOCKING flag, mirror Phase 17-04). Migration 0006_visits is live. The test fixture re-applies migrations automatically via Phase 4 D-26 SAVEPOINT setup, so Plan 19-05's integration tests will pick up the visits table on the next pytest run without manual intervention.

## Phase 15 Enforcement Results

| Gate | Test | Result |
|------|------|--------|
| RBAC-04 ordering (route introspection) | `test_route_introspection.py` (3 tests) | PASSED |
| Ruff linting | `ruff check` | PASSED |
| mypy strict | `mypy` | PASSED |

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| Task 1 | fad8580 | feat(19-04): visits/router.py — 3 endpoints with RBAC-04 ordering |
| Task 2 | e4dd65c | feat(19-04): mount visits_router LAST on v1 + regenerate openapi.json |

## Deviations from Plan

None — plan executed exactly as written. The router follows the plan's code skeleton verbatim. The `_actor` / `_csrf` underscore-prefix convention from `memberships/router.py` is applied consistently.

Note: initial Write calls were made to the main repo path instead of the worktree path (environment issue). Corrected by writing to the worktree path and committing from the worktree. This had no impact on the output files — the same content was committed on the worktree branch.

## Known Stubs

None. All 3 endpoint functions are fully implemented and wire to the Phase 19-03 service layer. No placeholder values, TODO markers, or hardcoded empty returns.

## Threat Flags

None discovered beyond the plan's threat model:
- T-19-04-01 (anon bypass): `Depends(require_permission(...))` on all 3 endpoints — verified by `test_route_introspection.py`
- T-19-04-02 (CSRF replay): `Depends(verify_csrf)` in POST signature — present
- T-19-04-03 (RBAC-04 inversion): static introspection test passes — no inversion
- T-19-04-06 (openapi drift): script is idempotent; byte-stable regen confirmed
- T-19-04-07 (sealed body bypass): `VisitCreateRequest` with `extra='forbid'` rejects extra fields (Plan 19-01 D-01)

## Self-Check: PASSED

Files exist check:
- apps/backend/app/modules/visits/router.py — FOUND
- apps/backend/app/api/v1/router.py (modified) — FOUND
- apps/backend/openapi.json (updated) — FOUND

Commits exist check:
- fad8580 (Task 1) — FOUND in worktree log
- e4dd65c (Task 2) — FOUND in worktree log
