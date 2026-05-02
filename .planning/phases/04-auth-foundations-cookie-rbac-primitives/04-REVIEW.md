---
phase: 04-auth-foundations-cookie-rbac-primitives
reviewed: 2026-05-02T00:00:00Z
depth: standard
files_reviewed: 18
files_reviewed_list:
  - apps/backend/.env.example
  - apps/backend/.importlinter
  - apps/backend/app/core/config.py
  - apps/backend/app/core/database.py
  - apps/backend/app/core/dependencies.py
  - apps/backend/app/core/exceptions.py
  - apps/backend/app/core/pagination.py
  - apps/backend/app/core/permissions.py
  - apps/backend/app/core/schemas.py
  - apps/backend/app/core/security.py
  - apps/backend/app/modules/__init__.py
  - apps/backend/app/modules/clients/__init__.py
  - apps/backend/pyproject.toml
  - apps/backend/tests/integration/test_alembic_clean.py
  - apps/backend/tests/unit/test_pagination.py
  - apps/backend/tests/unit/test_permissions.py
  - apps/backend/tests/unit/test_schemas.py
  - apps/backend/tests/unit/test_security.py
findings:
  critical: 2
  warning: 4
  info: 2
  total: 8
status: issues_found
---

# Phase 04: Code Review Report

**Reviewed:** 2026-05-02T00:00:00Z
**Depth:** standard
**Files Reviewed:** 18
**Status:** issues_found

## Summary

Phase 4 delivers JWT encoding/decoding, Argon2id password hashing, token generators, cookie matrix, RBAC primitives, pagination contract, ORM base mixins, and a FastAPI dependency slot for user loading. The overall architecture is sound and the import-linter boundaries are correctly enforced. Two critical bugs were found: an unhandled exception in `verify_password` that causes a 500 on a legitimate (non-attack) error path, and an unhandled `ValueError` in `get_current_user` that allows a crafted JWT to trigger a 500 instead of a 401. Four warnings cover a test isolation gap for module-level global state, a test correctness risk in the Alembic integration test, `httpx` being listed as a production dependency, and a design gap in cookie security enforcement.

---

## Critical Issues

### CR-01: `verify_password` does not catch `argon2.VerificationError` — unhandled exception on non-mismatch failures

**File:** `apps/backend/app/core/security.py:135-145`

**Issue:** `argon2.PasswordHasher.verify()` raises three distinct exceptions per its documented contract:
1. `VerifyMismatchError` — password does not match (caught)
2. `InvalidHashError` — hash is so malformed it cannot be passed to Argon2 (caught)
3. `VerificationError` — verification failed for **other reasons** (e.g. internal Argon2 error, unsupported parameters on the platform) — **not caught**

`VerifyMismatchError` is a subclass of `VerificationError`, but `VerificationError` can also be raised directly for non-mismatch Argon2-level failures. When this occurs the exception propagates out of `asyncio.to_thread` into the FastAPI request handler as an unhandled exception, causing a 500 response with a full traceback potentially leaked in structured logs. The Phase 5 login flow's timing-equivalence guarantee (sentinel hash for unknown users) also breaks if `VerificationError` surfaces differently.

**Fix:**
```python
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

def _do() -> bool:
    try:
        _ph.verify(encoded_hash, plain)
        return True
    except VerifyMismatchError as exc:
        raise InvalidPassword("invalid_credentials") from exc
    except (VerificationError, InvalidHashError) as exc:
        # VerificationError: internal Argon2 failure (not a mismatch).
        # InvalidHashError: hash too malformed to pass to Argon2.
        # Both surface as auth failure, not a 500.
        raise InvalidPassword("invalid_credentials") from exc
```

---

### CR-02: `UUID(claims.sub)` in `get_current_user` raises unhandled `ValueError` — crafted JWT causes a 500

**File:** `apps/backend/app/core/dependencies.py:89`

**Issue:** `decode_access_token` validates that the `"sub"` claim exists and is a string (via PyJWT's `require` option), but it does not validate that the string is a well-formed UUID. A JWT crafted with `"sub": "not-a-uuid"` will pass `decode_access_token` and then cause `UUID(claims.sub)` to raise `ValueError: badly formed hexadecimal UUID string`. This propagates out of the FastAPI dependency chain as an unhandled exception, yielding a 500 response instead of the expected 401 `InvalidAccessToken`.

This is exploitable by any party that can forge or obtain a JWT signed with the application secret and populate `sub` with a non-UUID string. While key compromise is a prerequisite, the behavior is still wrong: the contract guarantees a 401 for all decode-path failures, and a 500 breaks that guarantee and may leak internals via structured logs.

**Fix:**
```python
from app.core.exceptions import ForbiddenError, InvalidAccessToken

# in get_current_user, replace:
user = await _user_loader(session, UUID(claims.sub))

# with:
try:
    user_id = UUID(claims.sub)
except ValueError as exc:
    raise InvalidAccessToken("invalid_token") from exc
user = await _user_loader(session, user_id)
```

---

## Warnings

### WR-01: `_user_loader` global state leaks between tests — no reset mechanism

**File:** `apps/backend/app/core/dependencies.py:49-59`

**Issue:** `_user_loader` is a module-level singleton set via `register_user_loader()`. Phase 4 has no caller, but the comment explicitly states that tests should inject a stub loader by calling `register_user_loader`. Because the global is never reset between tests (no fixture tears it down, no `autouse` cleanup), any test that calls `register_user_loader` with a stub will contaminate every subsequent test in the same process. This will become a concrete bug the moment Phase 5 adds tests for `get_current_user`.

The `register_user_loader` docstring calls this "idempotent" (re-registering replaces), which addresses the duplicate-call case but not cross-test contamination.

**Fix:** Provide a `reset_user_loader()` helper (or expose `_user_loader` reset to `None`) and call it from a `conftest.py` autouse fixture:
```python
# app/core/dependencies.py — add alongside register_user_loader:
def reset_user_loader() -> None:
    """Test teardown helper. Resets the loader slot to None."""
    global _user_loader
    _user_loader = None

# tests/conftest.py — add autouse fixture:
@pytest.fixture(autouse=True)
def _reset_user_loader() -> Generator[None, None, None]:
    yield
    from app.core.dependencies import reset_user_loader
    reset_user_loader()
```

---

### WR-02: Integration test asserts alembic success message in `stdout` — Alembic routes progress messages through its own `Config.stdout` channel which `subprocess.run` captures, but the test could silently pass if the message moves to stderr in a future Alembic version

**File:** `apps/backend/tests/integration/test_alembic_clean.py:67`

**Issue:** `assert "No new upgrade operations detected" in check.stdout` is fragile. Currently `alembic check` emits this string via `config.print_stdout()` which defaults to `sys.stdout` and is correctly captured. However:
1. The return-code assertion on line 64 (`assert check.returncode == 0`) already verifies success. The stdout string assertion adds no additional correctness guarantee — `alembic check` returns 0 if and only if there is no diff.
2. If a future Alembic version changes the message text or routing, the test will fail on a `False` assertion about the exact string rather than showing a meaningful diff error.

Also note: the test holds an open `db_session` (a live SQLAlchemy `AsyncSession` with an uncommitted transaction) while `alembic upgrade head` runs in a subprocess. If any future migration acquires an `AccessShareLock` or stronger on a table the open session has touched, this produces a deadlock. Phase 4 has no migrations so there is no current risk, but this pattern is unsafe as migrations accumulate.

**Fix:** Remove the brittle string assertion and rely solely on the exit-code check. Add a comment explaining why:
```python
assert check.returncode == 0, (
    f"alembic check detected drift:\nstdout:\n{check.stdout}\nstderr:\n{check.stderr}"
)
# Exit code 0 is the definitive success signal; do not assert on message text
# (Alembic message wording is not part of the public API).
```

For the open-session risk, add a comment warning that the fixture should not be used for DDL-heavy tests once real migrations exist.

---

### WR-03: `httpx` is listed as a production dependency, not a dev dependency

**File:** `apps/backend/pyproject.toml:12`

**Issue:** `httpx>=0.27` appears in `[project] dependencies`, not in `[dependency-groups] dev`. No production code under `app/` imports `httpx`; it is only used in `tests/conftest.py` (via `httpx.ASGITransport`, `httpx.AsyncClient`). Shipping `httpx` in the production image adds ~5 MB of unnecessary weight and a non-zero attack surface to the deployed artefact.

**Fix:** Move `httpx` to the `dev` dependency group:
```toml
[dependency-groups]
dev = [
    "ruff>=0.6",
    "mypy>=1.10",
    "import-linter>=2.0",
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "asgi-lifespan>=2.1",
    "httpx>=0.27",   # <-- moved here
]
```

---

### WR-04: `issue_session_cookies` accepts an explicit `secure` parameter that is fully decoupled from `settings.cookie_secure` — callers can silently pass the wrong value without any validation

**File:** `apps/backend/app/core/security.py:204-254`

**Issue:** The function accepts `secure: bool` from its caller rather than reading `settings.cookie_secure` itself. The docstring says "`secure` is env-driven via settings.cookie_secure" — but there is no enforcement of this: nothing prevents a caller from passing `secure=False` in production. The promised production assertion (`cookie_secure: bool = False # prod startup must ASSERT True`) is documented in `config.py` and `security.py` but is absent from `main.py:create_app()` where it would actually fire.

This is an incomplete implementation, not a future TODO: if `create_app()` is deployed without the assertion, `COOKIE_SECURE=false` in a prod environment will silently issue non-Secure cookies with no warning.

**Fix (two-part):**

1. Add the prod assertion to `create_app()` in `app/main.py`:
```python
def create_app() -> FastAPI:
    settings = get_settings()
    if settings.environment == "prod":
        assert settings.cookie_secure, (
            "COOKIE_SECURE must be True in production to prevent session cookies "
            "from being transmitted over HTTP."
        )
    ...
```

2. Consider reading `settings.cookie_secure` inside `issue_session_cookies` directly to remove the caller-side responsibility:
```python
def issue_session_cookies(
    response: Response,
    *,
    access_token: str,
    refresh_token: str,
    csrf_token: str,
) -> None:
    settings = get_settings()
    secure = settings.cookie_secure
    ...
```

---

## Info

### IN-01: `app.modules.members` directory exists on disk but is absent from `.importlinter` independence contract

**File:** `apps/backend/.importlinter:13-26`

**Issue:** `ls apps/backend/app/modules/` reveals a `members/` directory that is not listed under `[importlinter:contract:modules-independent]`. The directory contains only `__pycache__` (no `.py` files) so there is no immediate linting failure, but the import-linter contract will not catch future cross-imports involving `app.modules.members`. This appears to be a stale or accidental artefact from a branch — the business domain uses `memberships`, not `members`.

**Fix:** Either remove the empty `members/` directory, or if it is intentional, add `app.modules.members` to the independence contract in `.importlinter`.

---

### IN-02: `app.modules.__init__` docstring references `importlinter.ini` which does not exist — the file is `.importlinter`

**File:** `apps/backend/app/modules/__init__.py:7`

**Issue:** The module docstring says "enforced by import-linter's `modules-independent` contract (`apps/backend/importlinter.ini`)". The actual file is `apps/backend/.importlinter` (dot-prefixed, no `.ini` extension). This is a documentation inaccuracy that will mislead contributors looking for the contract file.

**Fix:**
```python
"""...enforced by import-linter's `modules-independent` contract (apps/backend/.importlinter)."""
```

---

_Reviewed: 2026-05-02T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
