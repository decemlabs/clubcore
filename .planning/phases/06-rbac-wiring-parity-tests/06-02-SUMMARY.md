---
phase: 06-rbac-wiring-parity-tests
plan: 02
subsystem: backend/core
tags:
  - rbac
  - csrf
  - dependencies
  - audit
requirements:
  - RBAC-02
  - RBAC-04
  - CSRF-02
dependency_graph:
  requires:
    - app.core.dependencies (existing — Phase 4 D-24, Phase 5 D-15)
    - app.core.audit.emit (Phase 5)
    - app.core.exceptions.CsrfMismatch (Plan 06-01 — added defensively here as Rule 3 fix; see Deviations)
    - app.core.permissions.{Action, Resource, Role, can}
  provides:
    - app.core.dependencies.require_authenticated (D-01)
    - app.core.dependencies.verify_csrf (D-05..D-08)
    - app.core.dependencies._SAFE_METHODS (D-06)
    - require_permission emits event=rbac_forbidden before raise (D-23)
  affects:
    - Plan 06-03 will wire require_authenticated + verify_csrf into auth router
    - Plan 06-05 TEST-07 introspection relies on __qualname__ shape locked here
    - Phase 8 audit_log DB writer will latch on event=rbac_forbidden / event=csrf_mismatch
tech_stack:
  added: []
  patterns:
    - Sibling factory shape (require_authenticated alongside require_permission, NEITHER nested in the other)
    - structlog.testing.capture_logs for audit-emit assertions in unit tests
    - SimpleNamespace request stub for dependency-level testing without Starlette TestClient
key_files:
  created:
    - apps/backend/tests/unit/test_dependencies_require_authenticated.py
    - apps/backend/tests/unit/test_dependencies_verify_csrf.py
  modified:
    - apps/backend/app/core/dependencies.py
    - apps/backend/app/core/exceptions.py (Rule 3 — see Deviations)
decisions:
  - "Added Request parameter to require_permission._checker so the audit emit can read request.url.path and request.client.host (FastAPI auto-injects; route-level callers unchanged)"
  - "_SAFE_METHODS exposed as module-level constant (with leading underscore) so unit tests can pin it as the architectural anchor for D-06"
  - "Audit emit uses has_cookie/has_header booleans only — never the raw token strings (T-06-09 mitigation)"
metrics:
  duration_seconds: 261
  duration_human: "~4m"
  tasks_completed: 2
  commits: 4
  files_created: 2
  files_modified: 2
  tests_added: 19
  completed_date: "2026-05-02"
---

# Phase 6 Plan 02: Authentication & CSRF Dependency Surface — Summary

**One-liner:** Added `require_authenticated()` factory + `verify_csrf` double-submit dependency to `app.core.dependencies`, plus `event=rbac_forbidden` audit emit inside `require_permission._checker`, with full unit-test coverage (19 tests across 2 files).

## Final Shapes

### `require_authenticated()` — sibling, NOT nested

```python
def require_authenticated() -> Callable[..., Awaitable[CurrentUser]]:
    async def _checker(
        user: Annotated[CurrentUser, Depends(get_current_user)],
    ) -> CurrentUser:
        return user

    return _checker
```

The closure `_checker.__qualname__` is `require_authenticated.<locals>._checker`, which Plan 06-05 TEST-07 discriminates via `startswith('require_authenticated.')`. The factory wraps `get_current_user` directly — it is NOT nested inside `require_permission`. This is locked by D-01 and asserted in `test_require_authenticated_qualname_distinct_from_require_permission`.

### `require_permission(action, resource)` — now with audit emit

The body now accepts `request: Request` (auto-injected by FastAPI; route-level callers are unchanged) and emits `event=rbac_forbidden` BEFORE raising `ForbiddenError`:

```python
async def _checker(
    request: Request,
    user: Annotated[CurrentUser, Depends(get_current_user)],
) -> CurrentUser:
    if not can(user.role, action, resource):
        emit(
            "rbac_forbidden",
            user_id=str(user.id),
            role=user.role.value,
            action=action.value,
            resource=resource.value,
            path=request.url.path,
            ip=request.client.host if request.client is not None else None,
        )
        raise ForbiddenError(f"forbidden:{action.value}:{resource.value}")
    return user
```

Locked emit kwargs per D-23: `user_id, role, action, resource, path, ip`. Phase 8's audit_log DB writer (INFRA-04) latches on this event name without renaming.

### `verify_csrf(request)` — double-submit with safe-method short-circuit

```python
_SAFE_METHODS: frozenset[str] = frozenset({"GET", "HEAD", "OPTIONS", "TRACE"})


async def verify_csrf(request: Request) -> None:
    if request.method in _SAFE_METHODS:
        return
    cookie_val = request.cookies.get("sportzal_csrf")
    header_val = request.headers.get("x-csrf-token")
    if (
        cookie_val is None
        or header_val is None
        or not secrets.compare_digest(cookie_val, header_val)
    ):
        emit(
            "csrf_mismatch",
            user_id=None,
            path=request.url.path,
            method=request.method,
            ip=request.client.host if request.client is not None else None,
            has_cookie=cookie_val is not None,
            has_header=header_val is not None,
        )
        raise CsrfMismatch("csrf_mismatch")
```

**T-06-09 mitigation:** the emit kwargs include only `has_cookie` / `has_header` booleans — never the raw token strings. Test `test_post_with_missing_header_raises_and_emits` asserts the emitted event's payload includes booleans, not the literal "abc" cookie value passed to the stub request.

**T-06-05 mitigation:** `secrets.compare_digest` is the constant-time compare. Test `test_post_uses_secrets_compare_digest` patches `app.core.dependencies.secrets.compare_digest` with a wrap-spy and asserts it was called when both cookie and header are present.

**D-21 envelope locked:** raising `CsrfMismatch("csrf_mismatch")` produces `{code: "csrf_mismatch", message: "csrf_mismatch", fields: null}` via the existing `_app_error_handler` — asserted by `test_csrf_mismatch_message_is_locked_code`.

## Test Counts

| File | Tests | Coverage |
|------|-------|----------|
| `tests/unit/test_dependencies_require_authenticated.py` | 7 | qualname discriminator, user pass-through, owner short-circuit (no emit), reception forbidden (emit + raise), ip=None branch |
| `tests/unit/test_dependencies_verify_csrf.py` | 12 | safe-method short-circuit (4 parametrized), match returns None, missing header / missing cookie / mismatch (3 raise+emit branches), constant-time compare spy, ip=None branch, D-21 envelope assertion |
| **Total** | **19** | — |

All 19 tests pass; full backend `pytest` suite reports 139 passed (the 12 errors in `tests/integration/auth/test_refresh.py` are pre-existing infrastructure failures — `asyncpg` cannot connect to a Postgres test DB locally — and predate this plan; they are out of scope per the executor scope-boundary rule).

## TDD Gate Compliance

| Gate | Commit | Status |
|------|--------|--------|
| RED (Task 1) | `3aa1ff2` `test(06-02): add failing tests for require_authenticated factory and rbac_forbidden audit emit` | ImportError confirmed |
| GREEN (Task 1) | `9514d0c` `feat(06-02): add require_authenticated factory and rbac_forbidden audit emit` | 7/7 tests pass |
| RED (Task 2) | `4bf6b83` `test(06-02): add failing tests for verify_csrf dependency` | ImportError confirmed |
| GREEN (Task 2) | `9138579` `feat(06-02): add verify_csrf double-submit dependency with audit emit` | 12/12 tests pass |

## Decisions Made

1. **`Request` parameter added to `require_permission._checker`.** The plan required this for the audit emit (so we can read `request.url.path` and `request.client.host`). FastAPI auto-injects `Request` into dependency callables, so existing route-level callers like `Depends(require_permission(Action.DELETE, Resource.CLIENTS))` continue to work without changes — the dependency graph fills both `request` and `user` automatically. Documented in the docstring.

2. **`_SAFE_METHODS` is module-private (leading underscore) but unit-tested.** The leading underscore signals "module-private", but `test_safe_methods_constant_is_locked` asserts the exact set so any future contributor mutating it trips a test. The coupling is intentional — this is the architectural anchor for D-06.

3. **Audit emit kwargs are deliberately minimal.** Per T-06-09 mitigation, the `csrf_mismatch` event includes only `has_cookie` / `has_header` booleans — never raw token values. Same principle for `rbac_forbidden`: includes `user_id` (a UUID, safe to log) and `role`/`action`/`resource` (StrEnum values, low-cardinality), but does NOT echo any request body.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 — Blocking] Added `CsrfMismatch` to `app/core/exceptions.py`**

- **Found during:** Task 2 RED gate (test imports `CsrfMismatch`, plan imports it in dependency module).
- **Issue:** Plan 06-02 imports `CsrfMismatch` from `app.core.exceptions`, but the class is owned by Plan 06-01. Both plans are in wave 1 with `depends_on: []` and run in parallel worktrees — at execution time, `CsrfMismatch` did not exist on master.
- **Fix:** Added `CsrfMismatch(AppError)` between `ForbiddenError` and `ConflictError` with `code = "csrf_mismatch"`, `status_code = 403`, and `# noqa: N818` (matching the convention used by `InvalidAccessToken` / `InvalidPassword`). The shape is byte-for-byte identical to the spec in `06-PATTERNS.md` lines 156–160 and the contract baked into Plan 06-01's frontmatter, so the merge with the parallel 06-01 worktree will deduplicate cleanly.
- **Files modified:** `apps/backend/app/core/exceptions.py` (one new class, 11 lines incl. docstring)
- **Commit:** `4bf6b83`
- **Why this is Rule 3 (not Rule 4):** the change is a known pre-existing dependency required to unblock the current task; it does not change architecture or introduce any new design decision — it materializes a class whose shape is already locked in 06-01's spec.

**2. [Rule 1 — Lint] Resolved 5 ruff lint errors in newly-created test files**

- E501 (line too long) on the test module's docstring — split into a two-paragraph docstring.
- 2× SIM117 (nested `with` statements) — combined `with capture_logs() as captured, pytest.raises(...)`.
- RUF015 (single-element slice) — replaced `[c for c in captured if ...][0]` with `next(c for c in captured if ...)`.
- SIM300 (Yoda condition) — flipped operands in `_SAFE_METHODS` equality assertion.

All fixed inline; no behavioral change to tests.

### Auth Gates

None.

## Threat Flags

None — no new security surface beyond what `<threat_model>` already enumerates. `verify_csrf` and `require_authenticated` are exactly the gates the threat model assigns to the new mutating routes; `core ⊥ modules` boundary verified by `lint-imports` (3 contracts kept, 0 broken).

## Self-Check: PASSED

- File `apps/backend/app/core/dependencies.py` exists — FOUND
- File `apps/backend/app/core/exceptions.py` exists — FOUND
- File `apps/backend/tests/unit/test_dependencies_require_authenticated.py` exists — FOUND
- File `apps/backend/tests/unit/test_dependencies_verify_csrf.py` exists — FOUND
- Commit `3aa1ff2` exists in git log — FOUND
- Commit `9514d0c` exists in git log — FOUND
- Commit `4bf6b83` exists in git log — FOUND
- Commit `9138579` exists in git log — FOUND
- `from app.core.dependencies import require_authenticated, verify_csrf` succeeds — VERIFIED
- `require_authenticated().__qualname__.startswith("require_authenticated.")` is True — VERIFIED
- `cd apps/backend && uv run pytest tests/unit/test_dependencies_require_authenticated.py tests/unit/test_dependencies_verify_csrf.py` exits 0 with 19 passed — VERIFIED
- `cd apps/backend && uv run mypy app && uv run ruff check && uv run lint-imports` all exit 0 — VERIFIED
