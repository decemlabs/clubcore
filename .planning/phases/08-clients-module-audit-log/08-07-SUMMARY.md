---
phase: 08-clients-module-audit-log
plan: 07
subsystem: api
tags: [fastapi, router, rbac, csrf, clients, d-21]

requires:
  - phase: 08-clients-module-audit-log
    provides: [Plan 03 — ClientCreateRequest/UpdateRequest/Response/ListQuery DTOs]
  - phase: 08-clients-module-audit-log
    provides: [Plan 06 — service.py with list_clients/get_client/create_client/update_client/soft_delete_client (sibling Wave 3 worktree, merged separately)]
  - phase: 06-rbac-csrf
    provides: [require_permission, verify_csrf, CurrentUser, OWNER_ONLY matrix with (DELETE, CLIENTS)]
  - phase: 04-contracts-and-pagination
    provides: [ResponseEnvelope, envelope, PaginatedData]
provides:
  - "5-endpoint clients API surface mounted at /api/v1/clients"
  - "GET /api/v1/clients (list) — VIEW gated"
  - "GET /api/v1/clients/{client_id} (read-one) — VIEW gated"
  - "POST /api/v1/clients (create) — EDIT + CSRF gated, 201 Created"
  - "PATCH /api/v1/clients/{client_id} (partial update) — EDIT + CSRF gated"
  - "DELETE /api/v1/clients/{client_id} (soft-delete) — DELETE + CSRF gated, owner-only via OWNER_ONLY"
affects: [08-08 tests + parity/introspection enforcement]

tech-stack:
  added: []
  patterns:
    - "RBAC-04 ordering: require_permission Depends declared BEFORE verify_csrf in every mutation signature (auth → 401 fires before CSRF → 403)"
    - "ClientListQuery as Annotated[..., Depends()] binds query-string parameters into a Pydantic model with camelCase aliases"
    - "DELETE returns None with status_code=status.HTTP_204_NO_CONTENT — FastAPI emits empty body"

key-files:
  created:
    - "apps/backend/app/modules/clients/router.py — 5 endpoints, 144 lines"
  modified:
    - "apps/backend/app/api/v1/router.py — include_router(clients_router, prefix='/clients')"

key-decisions:
  - "Used envelope() helper (not ResponseEnvelope(data=…)) on success returns to keep route bodies compact and consistent with auth router"
  - "DELETE handler returns explicit None instead of Response(status_code=204) — FastAPI infers 204 from status_code=…NO_CONTENT and emits empty body without manual response object construction"
  - "Mutation signatures order: payload → actor (require_permission) → _csrf (verify_csrf) → session — preserves RBAC-04 (401 before 403) per FastAPI's left-to-right signature dep resolution"

patterns-established:
  - "Module-scoped APIRouter() + 5 declarative @router.<verb> handlers; the router is mounted with a prefix at app/api/v1/router.py rather than declaring prefix on the APIRouter itself — matches auth pattern"
  - "Service-layer call sites use `service.<fn>(session, ...)` (not direct dotted import of each function) so mocking + introspection see the function via the module namespace"

requirements-completed: [CLIENTS-03, CLIENTS-05, CLIENTS-06, CLIENTS-07, CLIENTS-08]

metrics:
  duration: ~2min
  started: 2026-05-03T12:24:15Z
  completed: 2026-05-03T12:25:49Z
  tasks: 2
  files_created: 1
  files_modified: 1
---

# Phase 08 Plan 07: Clients Router (5 endpoints, RBAC + CSRF) Summary

**Five-endpoint clients API surface created with the D-21 permission mapping locked into every signature (VIEW for reads, EDIT+CSRF for writes, DELETE+CSRF owner-only for soft-delete), mounted at `/api/v1/clients` via `app/api/v1/router.py`.**

## Performance

- **Duration:** ~2 min
- **Started:** 2026-05-03T12:24:15Z
- **Tasks:** 2
- **Files created:** 1 (`apps/backend/app/modules/clients/router.py`)
- **Files modified:** 1 (`apps/backend/app/api/v1/router.py`)

## Accomplishments

- `apps/backend/app/modules/clients/router.py` declares exactly 5 routes (`list`, `get`, `create`, `update`, `soft_delete`) with the D-21 permission map applied verbatim per endpoint.
- Mutation endpoints (POST, PATCH, DELETE) all carry `Depends(verify_csrf)` AFTER their `require_permission(...)` dep so RBAC-04 (401 before 403) is preserved.
- `app/api/v1/router.py` now mounts the new router at `/clients`, yielding final URLs `/api/v1/clients` and `/api/v1/clients/{client_id}`.
- `ruff check` exits 0 on both touched files.

## Task Commits

Each task was committed atomically (with `--no-verify` per parallel-executor protocol):

1. **Task 1: clients/router.py — 5 endpoints with RBAC + CSRF (D-21)** — `df0087b` (feat)
2. **Task 2: Mount router in app/api/v1/router.py** — `ece2fb2` (feat)

## Endpoint Matrix

| Method | Path                            | require_permission       | verify_csrf | Status | Response model                                  |
| ------ | ------------------------------- | ------------------------ | ----------- | ------ | ----------------------------------------------- |
| GET    | /api/v1/clients                 | (VIEW, CLIENTS)          | —           | 200    | ResponseEnvelope[PaginatedData[ClientResponse]] |
| GET    | /api/v1/clients/{client_id}     | (VIEW, CLIENTS)          | —           | 200    | ResponseEnvelope[ClientResponse]                |
| POST   | /api/v1/clients                 | (EDIT, CLIENTS)          | yes         | 201    | ResponseEnvelope[ClientResponse]                |
| PATCH  | /api/v1/clients/{client_id}     | (EDIT, CLIENTS)          | yes         | 200    | ResponseEnvelope[ClientResponse]                |
| DELETE | /api/v1/clients/{client_id}     | (DELETE, CLIENTS) ⚠ owner | yes         | 204    | — (empty body)                                  |

⚠ `(DELETE, CLIENTS)` is in `OWNER_ONLY`. Reception calls hit `require_permission` → 403 forbidden before reaching the handler. Backed by Phase 6 RBAC-05 + parity-test (TEST-06) + frontend `can.ts` mirror.

## RBAC-04 Ordering (D-22)

In every mutation endpoint, the parameter order is `payload → actor (require_permission) → _csrf (verify_csrf) → session`. FastAPI resolves signature dependencies left-to-right, so:

1. `require_permission(...)` runs first → calls `get_current_user` → 401 invalid_token if cookie missing/invalid; else checks RBAC → 403 forbidden if owner-only matrix denies.
2. `verify_csrf` runs only after auth + RBAC pass → 403 csrf_mismatch on header/cookie mismatch.

This preserves the invariant that an unauthenticated caller never sees a CSRF error (would otherwise leak that the user is at least authenticated).

## Deviations from Plan

None — plan executed exactly as written.

## Deferred Verifications (sibling worktree dependency)

The plan listed automated verifications that import `app.modules.clients.router` or `app.main.create_app()`. These run Python at the verification step and require `app/modules/clients/service.py` to be present.

`service.py` is the artifact of **Plan 08-06** (sibling Wave 3 worktree). Per the parallel-executor protocol, this worktree's base (`4360346`) does not include Plan 06's commits. The Python imports therefore fail at the verification step in this worktree but will resolve cleanly post-merge when the orchestrator combines Wave 3 outputs.

The static (grep + ruff) verifications passed in this worktree:

- ✅ `grep -q "@router.get(\"\""` — list endpoint
- ✅ `grep -q "@router.get(\"/{client_id}\""` — read-one endpoint
- ✅ `grep -q "@router.post(\"\""` — create endpoint
- ✅ `grep -q "@router.patch(\"/{client_id}\""` — update endpoint
- ✅ `grep -q "@router.delete(\"/{client_id}\""` — delete endpoint
- ✅ `grep -c "Depends(require_permission(Action.VIEW, Resource.CLIENTS))"` = 2
- ✅ `grep -c "Depends(require_permission(Action.EDIT, Resource.CLIENTS))"` = 2
- ✅ `grep -c "Depends(require_permission(Action.DELETE, Resource.CLIENTS))"` = 1
- ✅ `grep -c "Depends(verify_csrf)"` = 3 (POST, PATCH, DELETE handlers; +1 docstring mention is non-functional)
- ✅ `grep -q "status_code=status.HTTP_201_CREATED"` (POST)
- ✅ `grep -q "status_code=status.HTTP_204_NO_CONTENT"` (DELETE)
- ✅ `uv run ruff check app/modules/clients/router.py` — All checks passed
- ✅ `uv run ruff check app/api/v1/router.py` — All checks passed
- ✅ `grep -q "from app.modules.clients.router import router as clients_router"` (v1/router.py)
- ✅ `grep -q 'v1.include_router(clients_router, prefix="/clients", tags=\["clients"\])'` (v1/router.py)

The deferred (post-merge) verifications:

- ⏭ `uv run python -c "from app.modules.clients.router import router; print(len(router.routes))"` — needs service.py from Plan 06.
- ⏭ `uv run python -c "from app.main import create_app; app = create_app(); ..."` — needs service.py from Plan 06.
- ⏭ `uv run mypy --strict app/modules/clients/router.py` — currently fails on `Module "app.modules.clients" has no attribute "service"`; will pass post-merge.

These will be re-run automatically when Plan 08-08 (route-introspection / parity tests) executes after Wave 3 merges.

## Architectural Notes

- **D-02 boundary preserved transitively.** `router.py` does not import `app.modules.clients.models.Client` directly; it goes through `service.list_clients(...)` etc. Only `service.py` and `repository.py` are allowed to touch the ORM model. The `ResponseData`-derived `ClientResponse` DTO crossing the wire is a Pydantic model, not an ORM model — safe to expose.
- **CSRF-02 (Phase 6 D-09).** `verify_csrf` is declared as a SIGNATURE dep rather than via `dependencies=[Depends(verify_csrf)]` on the route decorator. The signature path lets FastAPI resolve auth (`require_permission`) FIRST in declaration order, so RBAC-04 (401 before 403) is preserved. The decorator-style `dependencies=[...]` would run those deps BEFORE signature deps, inverting the order and leaking CSRF errors to unauth callers.
- **Module call sites for `service.*`.** Calls are `service.list_clients(session, query)` (module attribute access) rather than `from app.modules.clients.service import list_clients` (direct import). The plan calls this out: it lets monkey-patching tests target `app.modules.clients.router.service.list_clients` and gives static introspection a single namespace per module to follow.

## Threat Surface (mitigation map per plan threat_model)

| Threat ID | Status     | Mitigation in router.py                                                                              |
| --------- | ---------- | ---------------------------------------------------------------------------------------------------- |
| T-08-37   | mitigated  | All 5 endpoints declare `require_permission(...)` → unauth → 401 from get_current_user.              |
| T-08-38   | mitigated  | DELETE declares `require_permission(Action.DELETE, Resource.CLIENTS)` → reception → 403 (OWNER_ONLY).|
| T-08-39   | mitigated  | POST/PATCH/DELETE all carry `Depends(verify_csrf)` after the auth dep.                               |
| T-08-40   | accepted   | Read endpoints rely on service-layer 404 for soft-deleted rows; reception has VIEW so no ambiguity.  |
| T-08-41   | mitigated  | `ClientListQuery` extends `PageQuery` with `page_size: Field(le=100)` (Phase 4); 422 on overflow.    |
| T-08-42   | mitigated  | Query string is bound into `ClientListQuery` Pydantic model — type validation rejects malformed.     |
| T-08-43   | accepted   | OpenAPI lists owner-only routes; runtime gating is the contract. Future work in v1.2.                |

No new threats discovered during execution.

## Threat Flags

None — no new security surface introduced beyond what the plan's threat_model registered.

## Self-Check: PASSED

- File `apps/backend/app/modules/clients/router.py` — present (5 endpoints, RBAC + CSRF gates).
- File `apps/backend/app/api/v1/router.py` — modified (clients_router import + include_router line).
- Commit `df0087b` (feat: clients router with 5 endpoints) — present in `git log`.
- Commit `ece2fb2` (feat: mount clients router at /api/v1/clients) — present in `git log`.
- All static verifications (grep, ruff) green; runtime verifications deferred to post-merge per parallel-executor protocol.
