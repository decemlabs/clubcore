# Phase 6: RBAC Wiring + Parity Tests — Pattern Map

**Mapped:** 2026-05-02
**Files analyzed:** 10 (3 MODIFIED, 7 NEW)
**Analogs found:** 9 / 10 (TEST-07 introspection has no direct analog — sketch supplied)

---

## File Classification

| File | Status | Role | Data Flow | Closest Analog | Match Quality |
|------|--------|------|-----------|----------------|---------------|
| `apps/backend/app/core/dependencies.py` | MODIFIED | FastAPI dependency factory | request-response | self (`require_permission`) | exact |
| `apps/backend/app/core/exceptions.py` | MODIFIED | AppError subclass | request-response | self (`ForbiddenError`) | exact |
| `apps/backend/app/modules/auth/router.py` | MODIFIED | FastAPI router endpoints | request-response | self (`/me`, `/logout`, `/logout-all`) | exact |
| `apps/backend/tests/_fixtures/owner_routes.py` | NEW | dynamic APIRouter builder | request-response | `apps/backend/app/api/v1/router.py` + `app/modules/auth/router.py` | role-match |
| `apps/backend/tests/integration/rbac/__init__.py` | NEW | empty package marker | n/a | `tests/integration/auth/__init__.py` | exact |
| `apps/backend/tests/integration/rbac/conftest.py` | NEW | pytest fixture module | n/a | `tests/conftest.py` + `tests/integration/auth/test_login.py` (`seeded_owner`) | role-match |
| `apps/backend/tests/integration/rbac/test_owner_only.py` | NEW | parametrized HTTP integration test | request-response | `tests/integration/auth/test_login.py` + `test_logout.py` | exact |
| `apps/backend/tests/integration/test_rbac_parity.py` | NEW | static-analysis / file-parsing test | file-I/O | `tests/unit/test_permissions.py` (set-equality body) — no FS analog | partial |
| `apps/backend/tests/integration/test_route_introspection.py` | NEW | route-introspection test | n/a (no HTTP) | none — sketch grounded in `app.routes` walk | NO ANALOG |
| `apps/backend/tests/integration/auth/test_logout.py` | MODIFIED | one-line update per logout call | request-response | self | exact (mechanical edit) |

---

## Pattern Assignments

### `apps/backend/app/core/dependencies.py` (MODIFIED)

**Analog:** SAME FILE — sibling to `require_permission` factory at lines 95–123.

**Imports already present** (lines 17–27 — extend this block, do NOT duplicate):
```python
from collections.abc import Awaitable, Callable
from typing import Annotated, Protocol
from uuid import UUID

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import ForbiddenError, InvalidAccessToken
from app.core.permissions import Action, Resource, Role, can
from app.core.security import decode_access_token
```

**Additions for Phase 6:**
- `import secrets` (stdlib)
- `from app.core.exceptions import CsrfMismatch` (after Phase 6 adds the class)
- `from app.core.audit import emit` (Phase 5 helper used by D-23 emit sites)

**`require_authenticated()` — copy-and-adapt from `require_permission` (lines 95–123)**:

`require_permission` factory shape to mirror exactly so TEST-07's `__qualname__.startswith('require_authenticated.')` discriminator works (D-01, D-18):

```python
def require_permission(
    action: Action,
    resource: Resource,
) -> Callable[..., Awaitable[CurrentUser]]:
    async def _checker(
        user: Annotated[CurrentUser, Depends(get_current_user)],
    ) -> CurrentUser:
        if not can(user.role, action, resource):
            raise ForbiddenError(f"forbidden:{action.value}:{resource.value}")
        return user

    return _checker
```

**Phase 6 `require_authenticated` per D-01 (sibling, NOT nested — see specifics):**

```python
def require_authenticated() -> Callable[..., Awaitable[CurrentUser]]:
    async def _checker(
        user: Annotated[CurrentUser, Depends(get_current_user)],
    ) -> CurrentUser:
        return user

    return _checker
```

**Audit-emit pattern to copy into `require_permission` body (D-23) — call BEFORE `raise ForbiddenError`:**

```python
emit(
    "rbac_forbidden",
    user_id=str(user.id),
    role=user.role.value,
    action=action.value,
    resource=resource.value,
    path=request.url.path,
    ip=request.client.host if request.client is not None else None,
)
```

Note: this requires injecting `request: Request` into `_checker`. Pattern for that already exists at `app/core/dependencies.py:62-65` (`get_current_user(request: Request, ...)`).

**`verify_csrf` — NEW, no in-file analog. Compose from existing primitives (D-05..D-08):**

```python
_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "TRACE"})


async def verify_csrf(request: Request) -> None:
    """Double-submit CSRF check (D-07). Short-circuits on safe methods (D-06)."""
    if request.method in _SAFE_METHODS:
        return
    cookie_val = request.cookies.get("sportzal_csrf")
    header_val = request.headers.get("x-csrf-token")
    if cookie_val is None or header_val is None or not secrets.compare_digest(
        cookie_val, header_val
    ):
        emit(
            "csrf_mismatch",
            user_id=None,  # verify_csrf runs before get_current_user; best-effort None
            path=request.url.path,
            method=request.method,
            ip=request.client.host if request.client is not None else None,
            has_cookie=cookie_val is not None,
            has_header=header_val is not None,
        )
        raise CsrfMismatch("csrf_mismatch")
```

`Request` import already in line 21. `request.cookies.get("sportzal_csrf")` mirrors the pattern in `app/modules/auth/router.py:86, 116` (`request.cookies.get("sz_refresh")`).

**Boundary constraint (`core ⊥ modules`):** the entire file MUST NOT import from `app.modules.*`. Both new symbols satisfy this — `require_authenticated` reuses `get_current_user` (already in core), `verify_csrf` only touches `request` + raises `CsrfMismatch` (also core).

---

### `apps/backend/app/core/exceptions.py` (MODIFIED)

**Analog:** SAME FILE — `ForbiddenError` at lines 24–26.

**Existing AppError subclass shape (lines 19–32):**

```python
class NotFoundError(AppError):
    code = "not_found"
    status_code = 404


class ForbiddenError(AppError):
    code = "forbidden"
    status_code = 403


class ConflictError(AppError):
    code = "conflict"
    status_code = 409
```

**Phase 6 addition (D-08, D-21) — slot it between `ForbiddenError` and `ConflictError`:**

```python
class CsrfMismatch(AppError):  # noqa: N818
    code = "csrf_mismatch"
    status_code = 403
```

**Handler — UNCHANGED** (lines 67–79 already produce the locked envelope shape):

```python
def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "code": exc.code,
                "message": exc.message,
                "fields": exc.fields,
            },
        )
```

`CsrfMismatch` rides this handler unchanged because it inherits `AppError`. Phase 6 does not touch `register_exception_handlers`.

**Naming convention (`# noqa: N818`):** mirror `InvalidAccessToken` (line 39) and `InvalidPassword` (line 46). The class name does NOT end in `Error` because it names a domain condition, not an exception verb — ruff would otherwise complain.

---

### `apps/backend/app/modules/auth/router.py` (MODIFIED)

**Analog:** SAME FILE — existing `/me`, `/logout`, `/logout-all` signatures.

**Imports to add** (extend the line 22 import — `get_current_user` removed once all migrations land, IF nothing else in the file still calls it):

```python
from app.core.dependencies import CurrentUser, require_authenticated, verify_csrf
```

Note: `get_current_user` may still be imported transitively for type hinting; check final usage and drop only if zero references remain.

**Existing `/logout` endpoint (lines 101–120) — pattern to migrate:**

```python
@router.post("/logout", response_model=ResponseEnvelope[None])
async def logout(
    request: Request,
    response: Response,
    # CurrentUser ensures the access cookie is valid; otherwise 401 short-circuits.
    _user: Annotated[CurrentUser, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[Redis, Depends(get_redis)],
) -> ResponseEnvelope[None]:
    ...
```

**Phase 6 migration (D-02, D-09) — change `Depends(get_current_user)` → `Depends(require_authenticated())` AND add `dependencies=[Depends(verify_csrf)]` to the decorator:**

```python
@router.post(
    "/logout",
    response_model=ResponseEnvelope[None],
    dependencies=[Depends(verify_csrf)],
)
async def logout(
    request: Request,
    response: Response,
    _user: Annotated[CurrentUser, Depends(require_authenticated())],
    session: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[Redis, Depends(get_redis)],
) -> ResponseEnvelope[None]:
    ...  # body unchanged
```

**Per-route table (D-09):**

| Route | `Depends(...)` for current user | Per-route `dependencies=[...]` |
|-------|---------------------------------|--------------------------------|
| `/login` | none (body carries credentials) | none (CSRF-exempt) |
| `/refresh` | none (reads `sz_refresh` cookie directly — line 86) | none (CSRF-exempt) |
| `/logout` | `Depends(require_authenticated())` | `[Depends(verify_csrf)]` |
| `/logout-all` | `Depends(require_authenticated())` | `[Depends(verify_csrf)]` |
| `/me` | `Depends(require_authenticated())` | none (GET — verify_csrf would short-circuit anyway, omit for clarity) |

The handler bodies are byte-identical (`require_authenticated()` returns the same `CurrentUser` instance). Only signatures + decorator change.

---

### `apps/backend/tests/_fixtures/owner_routes.py` (NEW)

**Analog:** `apps/backend/app/api/v1/router.py` (lines 1–13) + `apps/backend/app/modules/auth/router.py` (decorator-style mounting).

**Pattern from `app/api/v1/router.py`** (APIRouter construction):

```python
from fastapi import APIRouter
from app.modules.auth.router import router as auth_router

v1 = APIRouter()
v1.include_router(auth_router, prefix="/auth", tags=["auth"])
```

**Phase 6 — dynamic builder per D-10 (the `_make` closure factory binds `a` and `r` per iteration to defeat Python's late-binding gotcha):**

```python
"""Test-only fixture router built dynamically from OWNER_ONLY (D-10).

NOT mounted by app.main.create_app(). Mounted only by the test app fixture in
tests/integration/rbac/conftest.py. The /_t prefix is deliberately ugly — it
signals "not real" at a glance in any route enumeration.
"""

from fastapi import APIRouter, Depends

from app.core.dependencies import require_permission
from app.core.permissions import OWNER_ONLY, Action, Resource

router = APIRouter(prefix="/_t", tags=["_test_only"])


def _make_endpoint(a: Action, r: Resource) -> None:
    """Closure factory — binds (a, r) per iteration."""

    @router.get(
        f"/{a.value}/{r.value}",
        dependencies=[Depends(require_permission(a, r))],
    )
    async def _stub() -> dict[str, bool]:
        return {"ok": True}

    _stub.__name__ = f"stub_{a.value}_{r.value}"


for _action, _resource in sorted(OWNER_ONLY):
    _make_endpoint(_action, _resource)
```

**Critical correctness notes:**
- `sorted(OWNER_ONLY)` works because `Action` and `Resource` are `StrEnum` — comparison falls back to the underlying string (`"delete" < "edit" < "refund" < "view"`). Verified by `tests/unit/test_permissions.py:62-63` which uses the same `sorted(...)` pattern.
- `Resource.OWNER_AREA.value == "owner-area"` — the URL contains a hyphen, which is path-safe; FastAPI accepts it.
- The `_make_endpoint` closure indirection is mandatory; without it, every iteration would close over the same `_action`/`_resource` cell and all endpoints would resolve to the last pair (Python late-binding gotcha — see comment in D-10 example).

---

### `apps/backend/tests/integration/rbac/__init__.py` (NEW)

Empty file. Mirror `apps/backend/tests/integration/auth/__init__.py`.

---

### `apps/backend/tests/integration/rbac/conftest.py` (NEW)

**Analog:** `apps/backend/tests/conftest.py` (root `app` fixture, lines 47–52) + `apps/backend/tests/integration/auth/test_login.py` (`seeded_owner` fixture, lines 33–44).

**Root `app` fixture pattern (from `tests/conftest.py:47-52`):**

```python
@pytest_asyncio.fixture
async def app() -> AsyncIterator[FastAPI]:
    """Per-test FastAPI instance with lifespan fired (engine + sessionmaker bound)."""
    _app = create_app()
    async with LifespanManager(_app):
        yield _app
```

**`seeded_owner` pattern (from `tests/integration/auth/test_login.py:33-44`):**

```python
@pytest_asyncio.fixture
async def seeded_owner(db_session: AsyncSession, redis_clean: Redis) -> User:
    user = User(
        email=OWNER_EMAIL,
        password_hash=await hash_password(OWNER_PASSWORD),
        role=Role.OWNER,
        full_name="Login Owner",
    )
    db_session.add(user)
    await db_session.commit()  # SAVEPOINT — outer rollback wipes
    return user
```

**`redis_clean` pattern (from `test_login.py:25-31`):**

```python
@pytest_asyncio.fixture
async def redis_clean(app: FastAPI) -> Redis:
    client: Redis = app.state.redis
    await client.flushdb()
    return client
```

**Login-then-cookie pattern (from `test_login.py:140-158` and `test_logout.py:51-56`):**

```python
async def _login(client: AsyncClient) -> None:
    r = await client.post(
        "/api/v1/auth/login",
        json={"email": OWNER_EMAIL, "password": OWNER_PASSWORD},
    )
    assert r.status_code == 200, r.text
# AsyncClient.cookies is preserved across calls — sz_access + sz_refresh + sportzal_csrf land in the jar
```

**Phase 6 conftest.py composition (per D-11, D-12 Option A — sibling fixture mounting `_owner_routes_router`):**

```python
"""RBAC integration test fixtures (Phase 6 D-11, D-12).

Extends the root `app` fixture by mounting the test-only owner_routes router.
Production `create_app()` is NOT touched.
"""

from collections.abc import AsyncIterator
from typing import Any

import pytest_asyncio
from asgi_lifespan import LifespanManager
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.permissions import Role
from app.core.redis import get_redis
from app.core.security import hash_password
from app.main import create_app
from app.modules.auth.models import User
from tests._fixtures.owner_routes import router as _owner_routes_router

OWNER_EMAIL = "rbac-owner@example.com"
OWNER_PASSWORD = "hunter22hunter22"  # noqa: S105
RECEPTION_EMAIL = "rbac-reception@example.com"
RECEPTION_PASSWORD = "hunter22hunter22"  # noqa: S105


@pytest_asyncio.fixture
async def app_with_fixture_routes() -> AsyncIterator[FastAPI]:
    """Per-test FastAPI with the OWNER_ONLY stub router mounted (D-12 Option A)."""
    _app = create_app()
    _app.include_router(_owner_routes_router)
    async with LifespanManager(_app):
        yield _app


# db_session / redis_clean inherited from tests/conftest.py — re-bind app fixture name
# via @pytest.fixture(name="app") if rbac tests need them to point at app_with_fixture_routes.
# Cleanest pattern: rbac tests depend on app_with_fixture_routes explicitly and override
# get_db / get_redis on it directly (mirror tests/conftest.py:111-142).


async def _seed_user(db_session: AsyncSession, *, role: Role, email: str, password: str) -> User:
    user = User(
        email=email,
        password_hash=await hash_password(password),
        role=role,
        full_name=f"RBAC {role.value}",
    )
    db_session.add(user)
    await db_session.commit()
    return user


# ... owner_client / reception_client fixtures wrap _seed_user + login on a fresh AsyncClient
# bound to app_with_fixture_routes via ASGITransport (mirror tests/conftest.py:111-142).
```

**Key constraint:** `app_with_fixture_routes` is a SIBLING fixture, not a replacement. Phase 5 tests continue using the root `app` fixture — only RBAC tests opt into the fixture-router-mounted variant.

---

### `apps/backend/tests/integration/rbac/test_owner_only.py` (NEW)

**Analog:** `apps/backend/tests/integration/auth/test_login.py` (parametrize + httpx + cookie assertions) + `tests/unit/test_permissions.py:55-75` (parametrize over `OWNER_ONLY`).

**Parametrize-over-`OWNER_ONLY` pattern (from `tests/unit/test_permissions.py:61-74`):**

```python
_OWNER_ONLY_SORTED: list[tuple[Action, Resource]] = sorted(
    OWNER_ONLY, key=lambda p: (p[0].value, p[1].value)
)


@pytest.mark.parametrize("action,resource", _OWNER_ONLY_SORTED)
def test_reception_denied_for_every_owner_only_pair(action: Action, resource: Resource) -> None:
    assert can(Role.RECEPTION, action, resource) is False
```

**Cookie + envelope assertion pattern (from `test_login.py:47-66, 85-95`):**

```python
response = await async_client.post("/api/v1/auth/login", json={...})
assert response.status_code == 200, response.text
body = response.json()
assert body["code"] == "invalid_credentials"  # error envelope shape (D-20/D-22)
```

**Phase 6 TEST-05 sketch (per D-11):**

```python
import pytest
from httpx import AsyncClient

from app.core.permissions import OWNER_ONLY, Action, Resource

_PAIRS = sorted(OWNER_ONLY, key=lambda p: (p[0].value, p[1].value))


@pytest.mark.parametrize("action,resource", _PAIRS)
async def test_owner_allowed_on_every_owner_only_pair(
    owner_client: AsyncClient, action: Action, resource: Resource
) -> None:
    r = await owner_client.get(f"/_t/{action.value}/{resource.value}")
    assert r.status_code == 200
    assert r.json() == {"ok": True}


@pytest.mark.parametrize("action,resource", _PAIRS)
async def test_reception_forbidden_on_every_owner_only_pair(
    reception_client: AsyncClient, action: Action, resource: Resource
) -> None:
    r = await reception_client.get(f"/_t/{action.value}/{resource.value}")
    assert r.status_code == 403
    body = r.json()
    assert body["code"] == "forbidden"
    assert body["message"] == f"forbidden:{action.value}:{resource.value}"


@pytest.mark.parametrize("action,resource", _PAIRS)
async def test_unauthenticated_returns_401_before_403(
    async_client: AsyncClient, action: Action, resource: Resource
) -> None:
    r = await async_client.get(f"/_t/{action.value}/{resource.value}")
    assert r.status_code == 401
    assert r.json()["code"] == "invalid_token"
```

Note: `async_client` here would need to point at `app_with_fixture_routes` too (override the fixture in this module or use a different fixture name).

---

### `apps/backend/tests/integration/test_rbac_parity.py` (NEW)

**Analog:** `tests/unit/test_permissions.py:33-46` (set-equality assertion body). No file-system parsing analog exists in the codebase.

**Set-equality pattern to mirror (from `tests/unit/test_permissions.py:31-46`):**

```python
def test_resource_value_set() -> None:
    assert {r.value for r in Resource} == {
        "dashboard", "clients", "schedule", "staff", ...
    }
```

**Phase 6 TEST-06 sketch (per D-13, D-14, D-15):**

```python
"""TEST-06: backend OWNER_ONLY ⇔ frontend OWNER_ONLY parity (D-13, D-15)."""

from __future__ import annotations

import re
from pathlib import Path

from app.core.permissions import OWNER_ONLY, Action, Resource

# D-14: parents[4] from tests/integration/test_rbac_parity.py is the repo root.
_REPO_ROOT = Path(__file__).resolve().parents[4]
_CAN_TS = _REPO_ROOT / "apps" / "admin-web" / "src" / "shared" / "session" / "can.ts"
_REGISTRY_TS = _REPO_ROOT / "apps" / "admin-web" / "src" / "shared" / "session" / "registry.ts"

_PAIR_RE = re.compile(
    r"\{\s*action:\s*'([^']+)',\s*resource:\s*'([^']+)'\s*\}"
)


def _parse_owner_only_pairs() -> set[tuple[str, str]]:
    text = _CAN_TS.read_text(encoding="utf-8")
    return {(a, r) for a, r in _PAIR_RE.findall(text)}


def _parse_ts_union(text: str, name: str) -> set[str]:
    """Locate `export type {name} = ...` and extract every '<value>' literal."""
    # Find the line `export type Resource =` then read forward until the first
    # non-pipe non-string-literal line.
    lines = text.splitlines()
    start = next(i for i, ln in enumerate(lines) if f"export type {name} =" in ln)
    collected: set[str] = set()
    for ln in lines[start:]:
        for match in re.finditer(r"'([^']+)'", ln):
            collected.add(match.group(1))
        # Stop at the first non-blank line that has neither a `|` nor a string literal
        if not collected and ("'" not in ln):
            continue
        if collected and "|" not in ln and "'" not in ln:
            break
    return collected


def test_owner_only_pairs_match() -> None:
    fe_pairs = _parse_owner_only_pairs()
    be_pairs = {(a.value, r.value) for a, r in OWNER_ONLY}
    assert fe_pairs == be_pairs, f"BE-only: {be_pairs - fe_pairs}, FE-only: {fe_pairs - be_pairs}"


def test_resource_values_match() -> None:
    fe = _parse_ts_union(_REGISTRY_TS.read_text(encoding="utf-8"), "Resource")
    be = {r.value for r in Resource}
    assert fe == be, f"BE-only: {be - fe}, FE-only: {fe - be}"


def test_action_values_match() -> None:
    fe = _parse_ts_union(_REGISTRY_TS.read_text(encoding="utf-8"), "Action")
    be = {a.value for a in Action}
    assert fe == be, f"BE-only: {be - fe}, FE-only: {fe - be}"
```

**Frontend file shape locked (verified via Read):**
- `apps/admin-web/src/shared/session/can.ts:12-22` — `OWNER_ONLY` array with 9 `{ action: '...', resource: '...' }` entries on consecutive lines.
- `apps/admin-web/src/shared/session/registry.ts:1-12` — `export type Resource = | 'dashboard' | 'clients' | ... | 'owner-area'` (multi-line union).
- `apps/admin-web/src/shared/session/registry.ts:14` — `export type Action = 'view' | 'create' | 'edit' | 'delete' | 'refund'` (single-line union).

The `_parse_ts_union` helper above must handle both single-line (Action) and multi-line (Resource) union forms — the line-walker stops when a non-`|` non-string line is reached.

---

### `apps/backend/tests/integration/test_route_introspection.py` (NEW)

**Analog:** NONE in this codebase. The closest reference points are:
- `tests/integration/test_alembic_clean.py` for "test that walks framework state" pattern (no Read needed — just naming convention).
- FastAPI's `APIRoute.dependant` tree per D-18.

**Phase 6 TEST-07 sketch (per D-04, D-17, D-18, D-19):**

```python
"""TEST-07: every non-excluded APIRoute declares require_permission OR require_authenticated.

Walks app.routes from a fresh create_app(). For each APIRoute, recursively
inspects the dependant tree and asserts at least one Dependant.call has
__qualname__ starting with 'require_permission.' or 'require_authenticated.'.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.routing import APIRoute

from app.main import create_app

# D-04 + D-19: paths that may legally have NO gate. frozenset for fast lookup.
EXCLUDED_PATHS: frozenset[str] = frozenset({
    "/healthz",
    "/api/v1/auth/login",
    "/api/v1/auth/refresh",
    "/api/v1/auth/telegram/start",
    "/api/v1/auth/telegram/status",
    "/api/v1/auth/telegram/verify",
    "/openapi.json",
    "/docs",
    "/docs/oauth2-redirect",
    "/redoc",
})

EXCLUDED_PREFIXES: tuple[str, ...] = ("/api/v1/auth/telegram/",)

_GATE_PREFIXES = ("require_permission.", "require_authenticated.")


def _route_has_gate(route: APIRoute) -> bool:
    """Recursively walk route.dependant for a require_* call (D-18)."""
    seen: set[int] = set()

    def _walk(dep: Any) -> bool:
        if id(dep) in seen:
            return False
        seen.add(id(dep))
        call = getattr(dep, "call", None)
        if call is not None:
            qualname = getattr(call, "__qualname__", "")
            if any(qualname.startswith(p) for p in _GATE_PREFIXES):
                return True
        for sub in getattr(dep, "dependencies", []):
            if _walk(sub):
                return True
        return False

    return _walk(route.dependant)


def test_every_protected_route_declares_a_gate() -> None:
    app = create_app()
    failures: list[str] = []
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        path = route.path
        if path in EXCLUDED_PATHS:
            continue
        if any(path.startswith(p) for p in EXCLUDED_PREFIXES):
            continue
        if not _route_has_gate(route):
            failures.append(path)
    assert not failures, (
        f"Routes missing require_permission/require_authenticated: {failures}\n"
        f"EXCLUDED_PATHS: {sorted(EXCLUDED_PATHS)}\n"
        f"EXCLUDED_PREFIXES: {EXCLUDED_PREFIXES}"
    )
```

**Critical FastAPI internals (D-18):**
- `APIRoute.dependant` is a `fastapi.dependencies.models.Dependant` object.
- `Dependant.dependencies: list[Dependant]` — the recursive sub-deps.
- `Dependant.call` is the actual callable (the `_checker` closure for our factories).
- `_checker.__qualname__` resolves to `"require_permission.<locals>._checker"` (and similarly for `require_authenticated`) — the `startswith("require_permission.")` discriminator picks up the literal prefix before `<locals>`.

**Why this is mountable as a test even though `create_app()` is not under `LifespanManager`:** introspection only reads `app.routes` — no DB, no Redis, no lifespan needed. The fixture-router (`tests/_fixtures/owner_routes.py`) is NOT mounted by `create_app()`, so its `/_t/...` endpoints do not appear here — by design (D-12).

---

### `apps/backend/tests/integration/auth/test_logout.py` (MODIFIED)

**Analog:** SAME FILE — pattern at lines 79–80 and 156–157 (`async_client.post("/api/v1/auth/logout")`).

**Existing pattern:**

```python
with capture_logs() as captured:
    r = await async_client.post("/api/v1/auth/logout")
```

**Phase 6 minimal change (D-24) — echo the cookie as header:**

```python
with capture_logs() as captured:
    r = await async_client.post(
        "/api/v1/auth/logout",
        headers={"X-CSRF-Token": async_client.cookies["sportzal_csrf"]},
    )
```

Same one-line pattern at line 157 for `/api/v1/auth/logout-all`. The `_login(async_client)` helper at line 51 has already minted the `sportzal_csrf` cookie into the jar; tests just echo it.

**The `test_logout_unauthenticated_returns_401` test at lines 122–128 needs no change** — it expects 401 from the missing access cookie, which fires at `get_current_user` BEFORE `verify_csrf` runs (per the FastAPI sub-dependency order: `verify_csrf` is a route-level `dependencies=[...]`, it runs in lockstep with the path-op signature deps; but `get_current_user` raises 401 first because `require_authenticated` resolves identity, and the per-route dep `verify_csrf` raises only when reached. In FastAPI's actual execution order, `dependencies=[...]` runs BEFORE the path-operation function's signature deps — but raising `CsrfMismatch` in `verify_csrf` returns 403, not 401, so an unauthenticated caller without cookies would get 403 here, not 401).

**Caveat to surface in the plan:** the Phase 6 change to add `dependencies=[Depends(verify_csrf)]` may flip the unauth-on-/logout response from 401 to 403 because `verify_csrf` runs first and raises `CsrfMismatch` (403) before `require_authenticated` resolves the identity (401). The test at line 128 (`assert r.status_code == 401`) MAY break and need a corresponding update — the planner must verify FastAPI's actual dep execution order and decide whether to:
- (a) accept the new 403 response on unauth /logout (and update the test to assert 403 with `code: "csrf_mismatch"`), OR
- (b) reorder so `require_authenticated` is the path-op signature dep that runs first (which is already the case — `dependencies=[]` execute in declared order, but signature deps interleave). Empirically, FastAPI runs `dependencies=[...]` BEFORE signature `Depends(...)` — confirm at planning time.

---

## Shared Patterns

### Audit emit — locked event names (D-23)

**Source:** `apps/backend/app/core/audit.py:25-35` + `apps/backend/app/modules/auth/service.py:118-138`

**Pattern:**
```python
from app.core.audit import emit

emit(
    "rbac_forbidden",                # locked event= name
    user_id=str(user.id),
    role=user.role.value,
    action=action.value,
    resource=resource.value,
    path=request.url.path,
    ip=request.client.host if request.client is not None else None,
)
```

**Per-call-site key shapes locked in D-23:**
- `event=rbac_forbidden`: `{user_id, role, action, resource, path, ip}` — emit BEFORE `raise ForbiddenError(...)` in `require_permission._checker`.
- `event=csrf_mismatch`: `{user_id_or_none, path, method, ip, has_cookie, has_header}` — emit BEFORE `raise CsrfMismatch(...)` in `verify_csrf`. `user_id` is `None` (best-effort) because `verify_csrf` runs before `get_current_user`.
- `event=rbac_unauthenticated`: NOT emitted. The existing `InvalidAccessToken` raise in `get_current_user` already handles its own logging via Phase 5 D-20 conventions.

**Apply to:** `app/core/dependencies.py` — both `require_permission._checker` (existing, add emit before raise) and the new `verify_csrf` body.

### `Annotated[CurrentUser, Depends(...)]` style (Phase 4/5)

**Source:** `apps/backend/app/core/dependencies.py:116-121` (`require_permission` example) + `apps/backend/app/modules/auth/router.py:104-108, 124-128, 137-140`

**Pattern:**
```python
from typing import Annotated

async def some_route(
    user: Annotated[CurrentUser, Depends(require_permission(Action.DELETE, Resource.CLIENTS))],
    ...
) -> ResponseEnvelope[X]:
    ...
```

**Apply to:** every Phase 6 route migration in `app/modules/auth/router.py`. Use `_user` (underscore prefix) when the resolved user is unused inside the body — mirrors the existing `_user: Annotated[CurrentUser, Depends(get_current_user)]` at line 106.

### `AppError → JSONResponse` envelope shape (Phase 2 D-12)

**Source:** `apps/backend/app/core/exceptions.py:67-79`

**Locked envelope keys (snake_case per Phase 4 D-08, deliberately NOT camelCase):**
```python
{
    "code": exc.code,        # str — frontend matches on this
    "message": exc.message,  # str — for log/debug only
    "fields": exc.fields,    # dict[str, object] | None
}
```

**Apply to:** every Phase 6 test that asserts error response bodies (`test_owner_only.py`, possibly `test_logout.py` updates). Status codes per `AppError` subclass: `forbidden=403`, `csrf_mismatch=403`, `invalid_token=401`.

### Per-route `dependencies=[...]` for cross-cutting checks

**Source:** Phase 5 router pattern. `apps/backend/app/modules/auth/router.py` does not currently use this, but the FastAPI primitive is `@router.post("/path", dependencies=[Depends(dep)])`. Phase 6 introduces it for `verify_csrf` per D-09.

**Pattern:**
```python
@router.post(
    "/logout",
    response_model=ResponseEnvelope[None],
    dependencies=[Depends(verify_csrf)],  # runs BEFORE signature deps
)
async def logout(...) -> ResponseEnvelope[None]:
    ...
```

**Apply to:** `/logout`, `/logout-all` only. `/login`, `/refresh`, `/me`, future `/telegram/*` MUST NOT declare `verify_csrf` in `dependencies=[...]`.

### SAVEPOINT-rolled `db_session` (Phase 5 D-22)

**Source:** `apps/backend/tests/conftest.py:55-108`

**Apply to:** All RBAC tests via the existing `db_session` fixture. Seeded users (`_seed_user(role=...)`) are wiped on test teardown by the outer `trans.rollback()` — no test data leaks.

---

## No Analog Found

| File | Role | Reason |
|------|------|--------|
| `apps/backend/tests/integration/test_route_introspection.py` | route-introspection test | No existing test walks `app.routes` or inspects FastAPI's `Dependant` tree. The sketch above is grounded in FastAPI internals (`APIRoute.dependant`, `Dependant.call.__qualname__`) — planner should validate the exact attribute names against the installed FastAPI version (0.115+) at planning time. |

---

## Metadata

**Analog search scope:**
- `apps/backend/app/core/` (4 files read: `dependencies.py`, `exceptions.py`, `permissions.py`, `audit.py`, `security.py`)
- `apps/backend/app/modules/auth/` (3 files read: `router.py`, `service.py`, `models.py`)
- `apps/backend/app/main.py`, `app/api/router.py`, `app/api/v1/router.py`
- `apps/backend/tests/conftest.py`
- `apps/backend/tests/integration/auth/test_login.py`, `test_logout.py`, `test_refresh.py`
- `apps/backend/tests/integration/test_healthz.py`
- `apps/backend/tests/unit/test_permissions.py`
- `apps/admin-web/src/shared/session/can.ts`, `registry.ts`

**Files scanned:** 17

**Key invariants validated:**
- `core ⊥ modules` import boundary holds for `app/core/dependencies.py` and `app/core/exceptions.py` extensions.
- `Resource.OWNER_AREA.value == "owner-area"` (hyphen) — fixture router URL paths handle this correctly.
- `sorted(OWNER_ONLY)` comparison falls back to `StrEnum` underlying string — already used in `tests/unit/test_permissions.py:62`.
- The existing `_app_error_handler` at `app/core/exceptions.py:70-79` accepts any `AppError` subclass, so `CsrfMismatch` requires no handler change.

**Pattern extraction date:** 2026-05-02
