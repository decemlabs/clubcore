---
phase: 06-rbac-wiring-parity-tests
reviewed: 2026-05-02T00:00:00Z
depth: standard
files_reviewed: 14
files_reviewed_list:
  - apps/backend/app/core/dependencies.py
  - apps/backend/app/core/exceptions.py
  - apps/backend/app/modules/auth/router.py
  - apps/backend/tests/_fixtures/__init__.py
  - apps/backend/tests/_fixtures/owner_routes.py
  - apps/backend/tests/integration/auth/test_logout.py
  - apps/backend/tests/integration/rbac/__init__.py
  - apps/backend/tests/integration/rbac/conftest.py
  - apps/backend/tests/integration/rbac/test_owner_only.py
  - apps/backend/tests/integration/test_rbac_parity.py
  - apps/backend/tests/integration/test_route_introspection.py
  - apps/backend/tests/unit/test_dependencies_require_authenticated.py
  - apps/backend/tests/unit/test_dependencies_verify_csrf.py
  - apps/backend/tests/unit/test_exceptions_csrf.py
findings:
  blocker: 1
  warning: 7
  info: 4
  total: 12
status: issues_found
---

# Phase 6: Code Review Report

**Reviewed:** 2026-05-02
**Depth:** standard
**Files Reviewed:** 14
**Status:** issues_found

## Summary

Phase 6 wires `require_authenticated()` and `verify_csrf` onto the auth-meta routes,
introduces the `CsrfMismatch` typed exception, and stands up the RBAC test matrix
(TEST-05/06/07) with a test-only fixture router. Overall, the architectural intent is
sound: the `core ⊥ modules` boundary holds (`dependencies.py` imports only from
`app.core.*`); CSRF check uses `secrets.compare_digest` for constant-time comparison;
the audit-event emission shape is correct and does not log raw token values; and the
fixture router is mounted only by the RBAC conftest, not by `create_app()`.

However, there is one **blocker**: the RBAC-04 invariant (401 before 403) is **broken
on every business route gated by `require_permission`** because `verify_csrf` is not
declared on those routes. Phase 6 wiring only covers the three auth-meta endpoints
(`/me`, `/logout`, `/logout-all`); the test-only fixture router used by TEST-05 also
omits `verify_csrf`. As a result, `test_unauthenticated_returns_401_before_403` only
validates the 401-vs-403 ordering for routes with no CSRF dep — it does not catch the
case where a real business route bolts on `verify_csrf` in the wrong dependency order.
Since Phase 7+ business routes will need to apply both dependencies, the invariant is
effectively untested for the surface that will actually use it. See BL-01 for details.

Several quality issues around fixture isolation, documentation drift, and minor type
correctness are also flagged.

## Blocker Issues

### BL-01: RBAC-04 (401-before-403) ordering invariant is not exercised on a route that combines `verify_csrf` + `require_permission`

**File:** `apps/backend/tests/_fixtures/owner_routes.py:29-34` and `apps/backend/tests/integration/rbac/test_owner_only.py:50-59`
**Issue:**
The fixture router stub endpoints use `@router.get(...)` (a safe HTTP method) and declare
ONLY `Depends(require_permission(a, r))`. `verify_csrf` short-circuits on GET (per
`_SAFE_METHODS`), so the test `test_unauthenticated_returns_401_before_403` exercises
401-before-403 *only* through the `require_permission → get_current_user` chain — it
NEVER exercises 401-vs-403 ordering when `verify_csrf` is also on the signature.

This is the exact failure mode RBAC-04 / D-22 is meant to catch:
- `/api/v1/auth/logout` (POST) declares the deps in the correct order
  (`require_authenticated` first, then `verify_csrf`), and `test_logout.py` covers this
  pair correctly.
- BUT the contract `require_permission` + `verify_csrf` (the shape every Phase 7+
  business mutation will use) is **never tested**. A future route that writes:

  ```python
  @router.delete("/clients/{id}")
  async def delete_client(
      _csrf: Annotated[None, Depends(verify_csrf)],          # WRONG — runs first
      user: Annotated[CurrentUser, Depends(require_permission(Action.DELETE, Resource.CLIENTS))],
      ...
  ): ...
  ```

  will return 403 `csrf_mismatch` for unauthenticated callers, silently violating
  D-22, and TEST-05 will not catch it because the fixture router uses GET.

**Fix:**
Either (a) make the test-only fixture router emit POST endpoints with `verify_csrf` as a
second signature dep, mirroring the production `/logout` shape, or (b) add a dedicated
matrix in TEST-05 for the combined case. Option (a) is preferable because it keeps the
fixture router as the single source of truth for the gate contract. Concretely:

```python
# tests/_fixtures/owner_routes.py
from app.core.dependencies import require_permission, verify_csrf

def _make_endpoint(a: Action, r: Resource) -> None:
    @router.post(  # POST so verify_csrf runs (not short-circuited)
        f"/{a.value}/{r.value}",
        dependencies=[
            Depends(require_permission(a, r)),  # auth/RBAC first
            Depends(verify_csrf),               # CSRF second
        ],
    )
    async def _stub() -> dict[str, bool]:
        return {"ok": True}
    _stub.__name__ = f"stub_{a.value}_{r.value}"
```

And update test_owner_only.py to send POST with the CSRF header (the owner_client/
reception_client fixtures already mint sportzal_csrf in their cookie jars). The
unauthenticated case becomes the actual RBAC-04 canary: with no auth and no CSRF
header, the response MUST be 401 (not 403 csrf_mismatch).

If Phase 6 deliberately scopes the fixture router to GET (per CONTEXT.md), then at
minimum add ONE explicit integration test at the auth-meta layer that asserts
unauthenticated + missing CSRF header on a `require_permission`-protected POST
returns 401 — `test_logout_unauthenticated_returns_401_even_without_csrf` only
covers `require_authenticated`, not `require_permission`.

## Warnings

### WR-01: `_logout_all` revokes-all logic invokes `revoke_all_sessions` BEFORE clearing cookies, but unauth-without-CSRF case is untested

**File:** `apps/backend/tests/integration/auth/test_logout.py` (missing test)
**Issue:**
There is no test mirroring `test_logout_unauthenticated_returns_401` for `/logout-all`.
The wiring is identical (both declare `require_authenticated` then `verify_csrf`), but
absence of a parallel test means a future refactor that swaps the dep order on
`/logout-all` (only) would not be caught.

**Fix:** Add a one-liner test:
```python
async def test_logout_all_unauthenticated_returns_401(async_client: AsyncClient) -> None:
    r = await async_client.post("/api/v1/auth/logout-all")
    assert r.status_code == 401
    assert r.json()["code"] == "invalid_token"
```

### WR-02: `seeded_owner` fixture depends on `redis_clean`, but `redis_clean` flushes the entire DB

**File:** `apps/backend/tests/integration/auth/test_logout.py:42-52`
**Issue:**
`seeded_owner` is declared as `async def seeded_owner(db_session, redis_clean)`. Pytest
resolves `redis_clean` first (which calls `flushdb()`), then executes the seed body.
This is fine in isolation, BUT note the dependency direction: `redis_clean` does
`await client.flushdb()` against the SHARED `app.state.redis` singleton (one client per
test app, but per-process Redis DB). If a future test forgets to depend on
`redis_clean` and runs in parallel (`pytest-xdist`) or after another test that wrote
session keys, the assertion `assert await redis_clean.exists(...) == 0` becomes flaky.
The current tests are sequential and OK, but the pattern is fragile.

**Fix:**
Either (a) document explicitly that these tests must run serially (no `pytest-xdist`),
or (b) namespace Redis keys per-test (e.g., prefix with the worker id). At minimum, add
a `pytest.mark.serial` or similar marker so future contributors are warned.

### WR-03: `test_logout_revokes_family_and_clears_cookies` asserts cookie deletion via raw header substring matching, missing edge cases

**File:** `apps/backend/tests/integration/auth/test_logout.py:118-126`
**Issue:**
The test detects deletion headers by matching `"expires="` or `"max-age=0"` substrings
in `Set-Cookie`. This works for the current `clear_session_cookies` implementation,
but:
1. A buggy implementation that sets `Max-Age=1` (one second) would still fail
   `"max-age=0"` match — but a buggy implementation that sets only an `Expires=`
   attribute pointing to a *future* date would FALSELY pass the `"expires="` check.
2. The header check is case-insensitive (`h.lower()`) but `h.startswith("sz_access=")`
   uses the raw string — works because Set-Cookie names are case-preserved, but
   inconsistent with the lowercase comparison just above.

**Fix:**
Parse the `Set-Cookie` header properly (e.g., via `http.cookies.SimpleCookie`) and assert
that `Max-Age == 0` AND `Expires` is in the past (or assert via the httpx cookie jar
state directly: `assert "sz_access" not in async_client.cookies` after the response
is processed).

### WR-04: `cast(User, user)` in `/me` route bypasses Protocol boundary on hot path

**File:** `apps/backend/app/modules/auth/router.py:160-170`
**Issue:**
`u = cast(User, user)` is a runtime no-op type assertion. If `register_user_loader` is
ever called with a loader that returns a non-`User` shape (e.g., a stub in a test that
inherits from a different model), the cast silently passes mypy and the attribute
access (`u.email`, `u.full_name`, `u.telegram_chat_id`) will raise `AttributeError` at
runtime — surfaced as 500 to the client.

The Protocol itself is the right boundary, but the route punches through it. The
docstring acknowledges this ("we cast for access to email / full_name / ..."), but the
contract should be lifted — either expand `CurrentUser` to include `email`,
`full_name`, `telegram_chat_id` (then `MeResponse` becomes a pure mapping), or add
a runtime `isinstance(user, User)` guard.

**Fix:**
Prefer expanding the Protocol (it stays minimal — three additional fields) so the
route does not need to cast:

```python
class CurrentUser(Protocol):
    id: UUID
    role: Role
    email: str
    full_name: str
    telegram_chat_id: int | None  # or whatever the actual type is
```

Or, if the Protocol must stay narrow, do `assert isinstance(user, User)` before the
cast so misregistration surfaces immediately with a clear error.

### WR-05: `verify_csrf` audit event omits `user_id` even when one is trivially derivable, contradicting D-23 intent

**File:** `apps/backend/app/core/dependencies.py:196-204`
**Issue:**
The CSRF audit event hard-codes `user_id=None`. The docstring justifies this as
"verify_csrf runs BEFORE get_current_user", but on the `/logout` route, the production
ordering is the OPPOSITE — `require_authenticated` is declared FIRST per Phase 6 D-22.
By the time `verify_csrf` fires, the access cookie has already been validated and the
`sz_access` JWT claim could be decoded again (cheaply) to bind a `user_id` to the audit
record.

The current implementation produces audit records with `user_id=None` for CSRF
mismatches by *authenticated* callers — the highest-signal case (e.g., a CSRF token
race during a session refresh, or a legitimate XSS attempt). This degrades the audit
trail's forensic value.

**Fix:**
Either (a) accept this as a deliberate trade-off and update the docstring to remove the
"runs BEFORE" justification (the real reason is "we don't want to re-decode the JWT
inside a CSRF dep"), or (b) parse `request.cookies.get("sz_access")` non-strictly
(catching all errors → `user_id=None`) and bind the user_id when available:

```python
user_id: str | None = None
access_cookie = request.cookies.get("sz_access")
if access_cookie is not None:
    try:
        user_id = decode_access_token(access_cookie).sub
    except AppError:
        pass  # best-effort — CSRF check stands regardless
emit("csrf_mismatch", user_id=user_id, ...)
```

### WR-06: `test_post_uses_secrets_compare_digest` does not actually verify constant-time semantics

**File:** `apps/backend/tests/unit/test_dependencies_verify_csrf.py:87-93`
**Issue:**
The test patches `secrets.compare_digest` with a wrapped reference and asserts
`spy.called`. This proves the function was *invoked*, but not that the comparison is
constant-time — a regression that swaps `secrets.compare_digest(a, b)` for
`a == b` would fail the spy, but a regression that does `secrets.compare_digest(a, a)`
followed by `if a != b` would still pass the spy.

The test is named `test_post_uses_secrets_compare_digest` and that's what it tests — but
the docstring should clarify it's a "called" check, not a timing check. T-06-05
mitigation requires constant-time comparison, and currently nothing in the suite
proves the comparison's *result* drives the branch.

**Fix:**
Add an assertion that the spy was called WITH the cookie + header values, AND that the
return value of the spy determined the branch:

```python
async def test_post_uses_secrets_compare_digest() -> None:
    with patch(
        "app.core.dependencies.secrets.compare_digest",
        wraps=secrets_mod.compare_digest,
    ) as spy:
        await verify_csrf(_req(method="POST", cookie="x", header="x"))
        spy.assert_called_once_with("x", "x")
```

### WR-07: `_parse_ts_union` regex `r"'([^']+)'"` matches ANY single-quoted literal, including those in adjacent comments or unrelated code

**File:** `apps/backend/tests/integration/test_rbac_parity.py:97`
**Issue:**
The literal-extraction regex collects every `'...'` substring on every line in the
window between the anchor and the next top-level decl. If a comment, a JSDoc
`@example`, or a non-union string literal appears in that window, it would be folded
into the parsed set. Currently `registry.ts` is clean, but this is fragile under
benign edits (e.g., adding `// example: 'foo'` between the lines of the Resource union).

The current `_DECL_PREFIXES` heuristic uses lstrip(), so a comment line like
`  // example: 'foo'` does NOT match any prefix and would not stop iteration;
the literal `'foo'` would be added to the set, breaking `test_resource_values_match`.

**Fix:**
Tighten the regex anchor to require the line to START with a `|` (continuation) or be
the anchor line itself. Skip lines that start with `//`, `/*`, or `*` (TS comment
prefixes). For example:

```python
for offset, ln in enumerate(lines[start:]):
    stripped = ln.lstrip()
    if offset > 0 and stripped.startswith(_DECL_PREFIXES):
        break
    if stripped.startswith(("//", "/*", "*")):
        continue  # skip comments
    if offset > 0 and not stripped.startswith("|"):
        # Inside a multi-line union, every literal-bearing line starts with `|`.
        # The anchor line (offset 0) is exempt because single-line unions sit on it.
        continue
    for match in re.finditer(r"'([^']+)'", ln):
        collected.add(match.group(1))
```

## Info

### IN-01: `_user_loader` uses module-global mutable state without thread-safety annotation

**File:** `apps/backend/app/core/dependencies.py:51, 60-61`
**Issue:**
`_user_loader: UserLoader | None = None` is a module-global, mutated by
`register_user_loader` via `global _user_loader`. In FastAPI's single-process async model
this is fine, but multi-worker uvicorn deployments (gunicorn + uvicorn workers) will
have one slot per worker, set at startup. Worth noting in the docstring that the slot
is a per-process singleton, not a global one — and that re-registration in a running
process is intentionally not synchronized (composition root only).

**Fix:** One-line docstring addition:

```python
_user_loader: UserLoader | None = None
"""Per-process singleton; set once by `app.main.create_app()` at startup.

Not synchronized — re-registration is only safe before the first request flow."""
```

### IN-02: `tests/_fixtures/__init__.py` docstring claims fixtures are "not collected by pytest" but does not enforce it

**File:** `apps/backend/tests/_fixtures/__init__.py:1`
**Issue:**
The docstring says "Test-only fixtures, not collected by pytest." But `pytest`'s default
collection is filename-based (`test_*.py`); since the directory does not contain any
`test_*.py`, nothing IS collected — but that's a side-effect of naming, not an
enforced contract. If someone adds `tests/_fixtures/test_helper.py`, pytest will
collect it.

**Fix:** Add `collect_ignore = ["__init__.py", "owner_routes.py"]` or a
`conftest.py`-level `collect_ignore_glob = ["_fixtures/*"]` at the parent level if you
want to harden the boundary. (Low priority — mostly a documentation hygiene matter.)

### IN-03: Test password literal is reused across files with `# noqa: S105` — could be centralized

**File:** `apps/backend/tests/integration/auth/test_logout.py:32`,
`apps/backend/tests/integration/rbac/conftest.py:41,43`
**Issue:**
The same test password (`"hunter22hunter22"`) is duplicated across three files with
identical `# noqa: S105` annotations. Centralizing it (e.g., in a `tests/_fixtures/
constants.py`) would reduce duplication and make future password-strength changes a
one-line update.

**Fix:** Optional; current state is acceptable.

### IN-04: `_make_endpoint` returns `None` but its sole side-effect is registering a route — name + return type could signal intent better

**File:** `apps/backend/tests/_fixtures/owner_routes.py:22-37`
**Issue:**
`_make_endpoint(a, r) -> None` is a side-effect-only registrar. Renaming to
`_register_endpoint` (or having it return the function it registered, for symmetry with
the FastAPI decorator pattern) would improve readability.

**Fix:** Optional cosmetic change.

---

_Reviewed: 2026-05-02_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
