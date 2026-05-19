---
phase: 43-multi-user-admin-module
plan: 06
subsystem: backend / users module / HTTP boundary
tags: [router, fastapi, rbac, csrf, users, http]
requires:
  - 43-02 (users/schemas — UserCreateRequest, UserListQuery, UserListItemResponse, UserCreateResponse, InvitationRevokeRequest)
  - 43-05 (users/service — list_users, create_user, deactivate_user, reactivate_user, soft_delete_user, revoke_invitation)
  - core/permissions (Action.LIST/CREATE/UPDATE/DELETE; Resource.USERS; OWNER_ONLY pairs)
  - core/dependencies (CurrentUser, require_permission, verify_csrf, get_db)
  - core/exceptions (global AppError → JSONResponse handler)
  - core/schemas (ResponseEnvelope, envelope, PaginatedData)
provides:
  - 6 endpoints under `/api/v1/users/*` (GET, POST, PATCH ×2, DELETE, POST /invitations/.../revoke)
  - users_router import + include_router mount in api/v1 aggregator
affects:
  - apps/backend/app/api/v1/router.py (1 import + 1 include_router line)
tech_stack_added: []
tech_stack_patterns:
  - "Annotated[T, Depends(...)] dependency declaration (D-43-29 ordering invariant)"
  - "Global AppError handler dispatch — no per-endpoint try/except (mirrors clients/router.py)"
key_files_created:
  - apps/backend/app/modules/users/router.py
key_files_modified:
  - apps/backend/app/api/v1/router.py
decisions:
  - "Per-endpoint try/except deliberately omitted — all service-layer exceptions extend AppError (NotFoundError/ConflictError) and are mapped to JSONResponse by the global handler registered in core/exceptions.register_exception_handlers (line 399). Mirrors clients/router.py which lets ClientNotFoundError / PhoneExistsError flow uncaught."
  - "include_invite_link declared as a FastAPI Query parameter (default False) with description text — kept simple Boolean to match D-43-14 audit-emit semantics (link_copied bool, never URL in payload)."
  - "Route mounted under prefix='/users' tag='users' between trainers and visits (alphabetical) — matches existing module-grouping convention (clients, trainers, visits all on one line each)."
metrics:
  duration_seconds: 226
  duration_human: "3m 46s"
  tasks_completed: 2
  files_created: 1
  files_modified: 1
  completed_date: 2026-05-19
---

# Phase 43 Plan 06: Users Module Router Summary

**One-liner:** Wires the 6 USERS-01..05 HTTP endpoints to `users.service` under `/api/v1/users/*` with D-43-29 dependency order (auth → RBAC → CSRF → session) and the global `AppError` exception mapping.

## Tasks Completed

| Task | Name                                                     | Commit  | Files                                              |
| ---- | -------------------------------------------------------- | ------- | -------------------------------------------------- |
| 1    | Create users/router.py with 6 endpoints                  | b9cdbf0 | apps/backend/app/modules/users/router.py (new)     |
| 2    | Mount users_router under /api/v1/users                   | 98e06fc | apps/backend/app/api/v1/router.py (1 import + 1 include) |

## Endpoint Surface (Route Introspection Verified)

| Verb   | Path (relative to `/api/v1/users`)        | Status | Permission                              | CSRF | Service call             |
| ------ | ------------------------------------------ | ------ | --------------------------------------- | ---- | ------------------------ |
| GET    | `` (collection root)                       | 200    | `LIST, USERS`                            | no   | `service.list_users`     |
| POST   | `` (collection root)                       | 201    | `CREATE, USERS`                          | yes  | `service.create_user`    |
| PATCH  | `/{user_id}/deactivate`                    | 204    | `UPDATE, USERS`                          | yes  | `service.deactivate_user`|
| PATCH  | `/{user_id}/reactivate`                    | 204    | `UPDATE, USERS`                          | yes  | `service.reactivate_user`|
| DELETE | `/{user_id}`                               | 204    | `DELETE, USERS`                          | yes  | `service.soft_delete_user`|
| POST   | `/invitations/{token_id}/revoke`           | 204    | `UPDATE, USERS`                          | yes  | `service.revoke_invitation`|

Programmatic introspection (`v1.routes` filtered to `/users` prefix) confirmed all 5 unique paths register under the aggregator.

## D-43-29 Dependency Order (verified per endpoint)

Every mutation endpoint declares deps in this signature order:

1. body / path / query parameters
2. `actor: Annotated[CurrentUser, Depends(require_permission(Action.X, Resource.USERS))]`  — fires 401 if unauthenticated, 403 if reception (all `(Action.{LIST,CREATE,UPDATE,DELETE}, Resource.USERS)` pairs are in `OWNER_ONLY`)
3. `_csrf: Annotated[None, Depends(verify_csrf)]` — fires 403 on missing/invalid token
4. `session: Annotated[AsyncSession, Depends(get_db)]`

GET omits CSRF (read-only). Order preserves the invariant that unauthenticated callers never see a CSRF error.

## Exception-Handling Strategy

**Decision: per-endpoint try/except OMITTED.** Project-wide convention is a single global handler:

- `apps/backend/app/core/exceptions.py:399` — `register_exception_handlers(app)` attaches `@app.exception_handler(AppError)` returning `JSONResponse(status_code=exc.status_code, content={"code": exc.code, "message": exc.message, "fields": exc.fields})`.
- All Phase 43 user-domain exceptions extend `NotFoundError` (404) or `ConflictError` (409) which extend `AppError` — they propagate uncaught from service and are mapped uniformly.
- Mirrors `apps/backend/app/modules/clients/router.py` which lets `ClientNotFoundError` / `PhoneExistsError` flow without per-endpoint handling.

Exception → HTTP map (handled centrally):

| Exception                              | Code                          | Status |
| -------------------------------------- | ----------------------------- | ------ |
| UserNotFoundError                      | `user_not_found`              | 404    |
| InvitationNotFoundError                | `invitation_not_found`        | 404    |
| EmailAlreadyActiveError                | `email_already_active`        | 409    |
| UserAlreadyInactiveError               | `user_already_inactive`       | 409    |
| UserNotInactiveError                   | `user_not_inactive`           | 409    |
| CannotDeactivateSelfError              | `cannot_deactivate_self`      | 409    |
| CannotDeleteSelfError                  | `cannot_delete_self`          | 409    |
| CannotDeactivateLastOwnerError         | `cannot_deactivate_last_owner`| 409    |
| CannotDeleteLastOwnerError             | `cannot_delete_last_owner`    | 409    |
| InvitationAlreadyAcceptedError         | `invitation_already_accepted` | 409    |

## Tag & Prefix Decisions

- **Prefix:** `/users` (lowercase, plural-collection) — matches `/clients`, `/trainers`, `/visits` convention.
- **Tag:** `["users"]` for OpenAPI grouping — matches the lowercase-plural convention used by every other business module aggregate (clients, trainers, visits, memberships, …).
- **Mount position:** Between `trainers_router` and `visits_router` (alphabetical) — preserves existing ordering. The `_internal/email` block below remains untouched.

## include_invite_link Query Parameter (D-43-14)

Declared on POST `/` as:

```python
include_invite_link: Annotated[
    bool,
    Query(
        description=(
            "When true, the response carries the raw invitation URL "
            "(D-43-14). Audited via link_copied=true."
        ),
    ),
] = False
```

Threaded directly to `service.create_user(session, actor, payload, include_invite_link)`. Audit emit at the service layer captures only the `link_copied` boolean — the raw URL never lands in audit payloads (Pitfall 4).

## Deviations from Plan

None — plan executed exactly as written. Notable choices already documented inline:

- Plan offered two exception-handling shapes (per-endpoint try/except vs global handler) and explicitly asked us to mirror the project convention. Verified `clients/router.py` + `core/exceptions.py:399` → chose global handler.
- Plan acceptance criterion stated `grep -c 'Depends(verify_csrf)' === 5` (mutations) but counts 6 because the file's module docstring (line 20) mentions `Depends(verify_csrf)`. All 5 mutation endpoints carry the dependency; docstring count is incidental.

## Verification Results

- ✅ `ruff check apps/backend/app/modules/users/router.py` — clean
- ✅ `ruff check apps/backend/app/api/v1/router.py` — clean
- ✅ `mypy --strict apps/backend/app/modules/users/router.py` — clean
- ✅ `mypy --strict apps/backend/app/api/v1/router.py` — no NEW errors (4 pre-existing errors in `app/modules/auth/*` are unrelated to this plan; confirmed by stashing edits and re-running mypy on the same file).
- ✅ Route introspection on `users.router` → all 6 expected (verb, path) tuples present.
- ✅ Route introspection on `api.v1.router.v1` → all 5 unique users paths (`/users`, `/users/{user_id}`, `/users/{user_id}/deactivate`, `/users/{user_id}/reactivate`, `/users/invitations/{token_id}/revoke`) registered.

## Success Criteria

- [x] USERS-01/02/03/04/05 endpoint surface complete and routed under `/api/v1/users/*`.
- [x] D-43-29 dependency order (auth → RBAC → CSRF → session) enforced in every mutation.
- [x] Wave 3+4 tests can exercise the full HTTP surface via authenticated AsyncClient.

## Self-Check: PASSED

- ✅ `apps/backend/app/modules/users/router.py` exists.
- ✅ `apps/backend/app/api/v1/router.py` contains `users_router` import + include.
- ✅ Commits `b9cdbf0` and `98e06fc` exist in `git log`.
