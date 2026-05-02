---
phase: 04-auth-foundations-cookie-rbac-primitives
plan: 08
subsystem: auth
tags: [fastapi, rbac, protocol, dependency-injection, jwt, importlinter]

# Dependency graph
requires:
  - phase: 04-04
    provides: "Role, Action, Resource StrEnums + OWNER_ONLY matrix + can() in app.core.permissions"
  - phase: 04-07
    provides: "decode_access_token + AccessTokenClaims in app.core.security"
  - phase: 04-04
    provides: "InvalidAccessToken + ForbiddenError in app.core.exceptions"
provides:
  - "CurrentUser Protocol (structural type: id: UUID, role: Role)"
  - "UserLoader type alias Callable[[AsyncSession, UUID], Awaitable[CurrentUser | None]]"
  - "_user_loader module-level slot for composition-root injection"
  - "register_user_loader(loader) — idempotent composition-root setter"
  - "get_current_user FastAPI dependency reading sz_access cookie, 4 distinct 401 paths"
  - "require_permission(action, resource) closure factory returning FastAPI dependency"
affects:
  - phase-05-user-schema-email-password-auth
  - phase-06-rbac-wiring

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Protocol-based loader slot (D-24): core module stays decoupled from app.modules via structural typing + composition-root registration"
    - "Closure factory for FastAPI dependencies: require_permission captures action/resource at wiring time, returns _checker coroutine"

key-files:
  created: []
  modified:
    - apps/backend/app/core/dependencies.py

key-decisions:
  - "CurrentUser is a Protocol (not ABC/dataclass) — structural typing means Phase 5 User SQLAlchemy model satisfies it without any import from core"
  - "ForbiddenError message format: 'forbidden:{action.value}:{resource.value}' — short, machine-readable, no user input"
  - "_user_loader is None guard raises InvalidAccessToken (401) not 500 — composition-root misconfiguration surfaces as same shape client handles"
  - "register_user_loader is idempotent to support test stub injection without module reload"

patterns-established:
  - "Protocol-based loader: app.core.dependencies._user_loader slot filled by app.main.create_app via register_user_loader; preserves core-not-depend-on-modules importlinter contract"
  - "require_permission factory: Depends(require_permission(Action.X, Resource.Y)) on route signatures in Phase 6"

requirements-completed: [RBAC-01]

# Metrics
duration: 10min
completed: 2026-05-02
---

# Phase 04 Plan 08: RBAC Dependency Scaffold Summary

**Protocol-based CurrentUser slot + get_current_user/require_permission FastAPI dependency factories; core stays free of app.modules imports via D-24 loader registration pattern**

## Performance

- **Duration:** ~10 min
- **Started:** 2026-05-02T06:45:00Z
- **Completed:** 2026-05-02T06:55:35Z
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments

- Replaced 6-line placeholder `app/core/dependencies.py` with complete 124-line Protocol scaffold
- `CurrentUser(Protocol)` declares `id: UUID, role: Role` — Phase 5 SQLAlchemy User model will satisfy it structurally with zero core imports
- `get_current_user` dependency exposes four distinct `InvalidAccessToken` 401 paths: `missing_access_cookie`, `user_loader_not_registered`, `user_not_found`, plus decode paths (`token_expired`/`invalid_token`/`wrong_token_type`/`unknown_role`) delegated to `decode_access_token`
- `require_permission(action, resource)` closure factory ready for Phase 6 route wiring via `Depends(require_permission(Action.X, Resource.Y))`
- importlinter `core-not-depend-on-modules` contract stays GREEN (3/3 contracts kept)

## Task Commits

Each task was committed atomically:

1. **Task 1: FILL app/core/dependencies.py** - `9698c58` (feat)

**Plan metadata:** (committed after SUMMARY creation)

## Files Created/Modified

- `apps/backend/app/core/dependencies.py` — Replaced placeholder; CurrentUser Protocol + UserLoader type alias + _user_loader slot + register_user_loader + get_current_user + require_permission (121 lines)

## Decisions Made

- Protocol over ABC/dataclass: structural typing means Phase 5's User SA model satisfies CurrentUser without `app.core` ever importing `app.modules`
- `_user_loader is None` guard raises `InvalidAccessToken("user_loader_not_registered")` rather than letting Python raise `TypeError` as 500 — defensive 401 keeps response shape consistent
- `ForbiddenError` message uses `f"forbidden:{action.value}:{resource.value}"` — short, debuggable, machine-readable

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed ruff E501 line-too-long in docstring example**
- **Found during:** Task 1 verification (ruff check)
- **Issue:** Docstring example showing `Annotated[CurrentUser, Depends(require_permission(...))]` was 103 chars (limit 100)
- **Fix:** Reformatted `Annotated[...]` across two lines in the docstring example
- **Files modified:** `apps/backend/app/core/dependencies.py`
- **Verification:** `uv run ruff check app/core/dependencies.py` exits 0
- **Committed in:** `9698c58` (included in same task commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - docstring formatting)
**Impact on plan:** Trivial cosmetic fix; no behavior change.

## Issues Encountered

- The plan's automated verification Python script checked `'app.modules' not in src` — this was a broader check that would catch docstring references. The actual acceptance criterion correctly uses `grep -E "from app\.modules"` which checks only import statements. The `lint-imports` contract verification is the load-bearing check and passed cleanly (3/3 contracts KEPT).

## Threat Surface Scan

No new network endpoints, auth paths, or file access patterns introduced. This plan ships only FastAPI dependency factories (no routes registered). The `_user_loader` slot is the composition boundary — no actual user loading occurs in Phase 4 since `register_user_loader` has no caller yet.

Threat mitigations from the plan's STRIDE register all accounted for:
- T-04-38 (500 on unregistered loader): mitigated — defensive 401 on `_user_loader is None`
- T-04-39 (core/modules invariant): mitigated — `lint-imports` GREEN, zero `from app.modules` imports

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Phase 5 `create_app()` has a documented composition-root contract: call `register_user_loader(app.modules.auth.service.load_user_by_id)` once during startup — slot is ready
- Phase 6 can wire `Depends(require_permission(Action.X, Resource.Y))` onto every business route signature — factory is ready
- `core ⊥ modules` invariant preserved for all future module additions

---
*Phase: 04-auth-foundations-cookie-rbac-primitives*
*Completed: 2026-05-02*
