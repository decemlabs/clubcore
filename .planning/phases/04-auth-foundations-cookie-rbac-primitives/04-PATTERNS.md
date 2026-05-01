# Phase 4: Auth Foundations & Cookie/RBAC Primitives — Pattern Map

**Mapped:** 2026-05-01
**Files analyzed:** 16 (8 core/, 1 modules/, 3 config, 4 tests)
**Analogs found:** 16 / 16 (in-tree analogs available for every file; 4 are self-rewrite/extend cases)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `apps/backend/app/core/database.py` | infra/orm-base | (extend self) | `apps/backend/app/core/database.py` (self) | exact (extend in place) |
| `apps/backend/app/core/security.py` | utility/crypto | pure function | `apps/backend/app/core/middleware.py` (module-level helpers + `register_*` factory) | role-match (cross-cutting core util) |
| `apps/backend/app/core/dependencies.py` | dependency-factory | request-response | `apps/backend/app/core/database.py:get_db` (FastAPI Depends factory) | role-match |
| `apps/backend/app/core/exceptions.py` | model/error-hierarchy | (extend self) | `apps/backend/app/core/exceptions.py` (self) | exact (extend) |
| `apps/backend/app/core/config.py` | config | (extend self) | `apps/backend/app/core/config.py` (self) | exact (extend) |
| `apps/backend/app/core/permissions.py` | utility/policy | pure function | `apps/admin-web/src/shared/session/can.ts` (semantic mirror) + `apps/backend/app/core/pagination.py` (Pydantic-free core util shape) | semantic-mirror + structural |
| `apps/backend/app/core/schemas.py` | model/contract-base | transform | `apps/backend/app/core/pagination.py` (PEP 695 generic + Pydantic BaseModel in core) | role-match |
| `apps/backend/app/core/pagination.py` | model/contract | (rewrite self) | `apps/backend/app/core/pagination.py` (self, prior shape) | exact (rewrite) |
| `apps/backend/app/modules/clients/__init__.py` | module-placeholder | n/a | `apps/backend/app/modules/members/__init__.py` (the file being renamed) | exact (`git mv`) |
| `apps/backend/.importlinter` | config/lint | n/a | `apps/backend/.importlinter` (self) | exact (one-line edit) |
| `apps/backend/pyproject.toml` | config/deps | n/a | `apps/backend/pyproject.toml` (self) | exact (extend) |
| `apps/backend/.env.example` | config/env | n/a | `apps/backend/.env.example` (self) | exact (extend) |
| `apps/backend/tests/unit/test_security.py` | test/unit | pure function | `apps/backend/tests/integration/test_healthz.py` (style + naming) | role-match (unit, not integration) |
| `apps/backend/tests/unit/test_permissions.py` | test/unit | pure function | `apps/backend/tests/integration/test_healthz.py` (test naming + assertion style) | role-match |
| `apps/backend/tests/unit/test_schemas.py` | test/unit | pure function | `apps/backend/tests/integration/test_healthz.py` (test naming + assertion style) | role-match |
| `apps/backend/tests/integration/test_alembic_clean.py` | test/integration | subprocess + DB | `apps/backend/tests/integration/test_healthz.py` (integration entry, conftest fixtures, async style) | role-match |

## Pattern Assignments

### `apps/backend/app/core/database.py` (infra/orm-base — EXTEND)

**Analog:** `apps/backend/app/core/database.py` (self — additive extension)

**Existing imports + Base** (`apps/backend/app/core/database.py:1-18`) — the extension MUST keep these intact:
```python
"""Async SQLAlchemy engine + session, lifespan-managed (D-06, D-07)."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings


class Base(DeclarativeBase):
    """Declarative base for all ORM models. Future business modules subclass this."""
```

**Additions in Phase 4** (per CONTEXT.md D-15..D-19, lines must be appended above/around existing code):
- `from sqlalchemy import MetaData, text` and `from sqlalchemy.orm import Mapped, mapped_column`
- `from sqlalchemy import DateTime, Index` and `from sqlalchemy.dialects.postgresql import UUID`
- `from datetime import datetime` and `from uuid import UUID as UUIDType`
- `NAMING_CONVENTION = {"ix": "ix_%(column_0_label)s", "uq": "uq_%(table_name)s_%(column_0_name)s", "ck": "ck_%(table_name)s_%(constraint_name)s", "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s", "pk": "pk_%(table_name)s"}`
- Attach to `Base`: `metadata = MetaData(naming_convention=NAMING_CONVENTION)` (instance-level, on the existing class)
- Three NEW sibling classes (NOT subclasses of `Base` per D-18) — `UUIDPkMixin`, `TimestampMixin`, `SoftDeleteMixin`. The mixins use `mapped_column(...)` declarations that compose into model classes via plain MRO.

**Lifespan + `get_db` (lines 21-47) STAY UNCHANGED** — Phase 4 adds zero new session paths.

---

### `apps/backend/app/core/security.py` (utility/crypto — FILL)

**Current state** (`apps/backend/app/core/security.py:1-6`) — placeholder docstring only, no code:
```python
"""Security helpers placeholder.

TODO Phase C+: password hashing (passlib/argon2), JWT issue/verify (python-jose or PyJWT),
refresh-token rotation, secret-key signing helpers. No real auth in Phase A.
"""
```

**Closest structural analog:** `apps/backend/app/core/middleware.py` (module of pure helpers + `register_*` factory in `app.core`).

**Imports pattern** (mirror `apps/backend/app/core/middleware.py:1-12` and `apps/backend/app/core/exceptions.py:1-3` — top-doc blurb, then std-lib, then 3rd-party, then app-local):
```python
"""Security primitives: JWT, Argon2, token generators, cookie matrix (D-01..D-06, D-25..D-28)."""

# stdlib
import asyncio
import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

# third-party
import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import Response

# app-local
from app.core.config import get_settings
from app.core.exceptions import InvalidAccessToken, InvalidPassword
from app.core.permissions import Role
```

**Settings-access pattern** (copy from `apps/backend/app/core/database.py:23-29` — lazy `get_settings()` inside the helper, NEVER module-level):
```python
@asynccontextmanager
async def db_lifespan(app: FastAPI) -> AsyncIterator[None]:
    """FastAPI lifespan: create engine + sessionmaker on startup, dispose on shutdown."""
    settings = get_settings()
    engine = create_async_engine(
        str(settings.database_url),
        ...
    )
```
Apply to `encode_access_token` / `decode_access_token` — they call `get_settings()` *inside* the function body so the cached settings are picked up at call time, never at module-import.

**Domain-error pattern for `InvalidAccessToken` / `InvalidPassword`** — see exceptions section. Helpers MUST raise the dedicated `AppError` subclass (NEVER `jwt.InvalidTokenError` or `argon2.exceptions.VerifyMismatchError` to callers).

**`asyncio.to_thread` wrapping** (AUTH-02) — Argon2 is CPU-bound; the project has no prior `to_thread` analog, so the canonical idiom is:
```python
async def hash_password(plain: str) -> str:
    return await asyncio.to_thread(_PH.hash, plain)
```

**Cookie helper signature** (per D-25, single function):
```python
def issue_session_cookies(
    response: Response,
    *,
    access_token: str,
    refresh_token: str,
    csrf_token: str,
    secure: bool,
) -> None:
```
Cookie attributes locked by AUTH-04 / CSRF-01: `sz_access` (httpOnly, Path=`/`, Max-Age=900, SameSite=Lax), `sz_refresh` (httpOnly, Path=`/api/v1/auth`, Max-Age=2592000, SameSite=Lax), `sportzal_csrf` (non-httpOnly, no Path restriction, SameSite=Lax). All three respect the `secure` arg.

---

### `apps/backend/app/core/dependencies.py` (dependency-factory — FILL)

**Current state** (`apps/backend/app/core/dependencies.py:1-6`) — placeholder docstring only.

**Closest analog for FastAPI Depends factory:** `apps/backend/app/core/database.py:43-47` (`get_db`):
```python
async def get_db(request: Request) -> AsyncIterator[AsyncSession]:
    """Per-request AsyncSession from app.state.sessionmaker (D-07)."""
    session_factory = request.app.state.sessionmaker
    async with session_factory() as session:
        yield session
```

**Imports pattern** (Annotated + Depends + Protocol — Phase 4 introduces the Protocol slot):
```python
"""FastAPI dependencies: CurrentUser Protocol, loader registration, RBAC gate (D-24)."""

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

**Module-slot pattern** (NEW idiom for this codebase — no prior in-tree analog; canonical Python pattern):
```python
class CurrentUser(Protocol):
    id: UUID
    role: Role


UserLoader = Callable[[AsyncSession, UUID], Awaitable[CurrentUser | None]]
_user_loader: UserLoader | None = None


def register_user_loader(loader: UserLoader) -> None:
    global _user_loader
    _user_loader = loader
```

**Dependency body** mirrors `get_db`'s "request → app.state → ..." flow but reads cookies instead. Errors use the Phase-4 `InvalidAccessToken` (NOT `HTTPException`) so the existing `_app_error_handler` returns the documented `{code, message, fields}` body.

---

### `apps/backend/app/core/exceptions.py` (model/error-hierarchy — EXTEND)

**Analog:** `apps/backend/app/core/exceptions.py` (self).

**Existing class pattern** (`apps/backend/app/core/exceptions.py:7-36`) — every subclass overrides class-level `code` + `status_code` and inherits the `__init__` signature:
```python
class AppError(Exception):
    """Base domain error. Subclasses set class-level `code` and `status_code`."""

    code: str = "app_error"
    status_code: int = 500

    def __init__(self, message: str, *, fields: dict[str, object] | None = None) -> None:
        self.message = message
        self.fields = fields
        super().__init__(message)


class NotFoundError(AppError):
    code = "not_found"
    status_code = 404


class ForbiddenError(AppError):
    code = "forbidden"
    status_code = 403


class ConflictError(AppError):
    code = "conflict"
    status_code = 409


class ValidationAppError(AppError):
    code = "validation_error"
    status_code = 422
```

**Additions for Phase 4** (append after `ValidationAppError`, BEFORE `register_exception_handlers`):
```python
class InvalidAccessToken(AppError):
    code = "invalid_token"
    status_code = 401


class InvalidPassword(AppError):
    code = "invalid_credentials"
    status_code = 401


class RateLimited(AppError):
    code = "rate_limited"
    status_code = 429
```

**`_app_error_handler` JSON shape (`apps/backend/app/core/exceptions.py:42-51`) STAYS UNCHANGED** — the Phase-4 `ProblemDetails` pydantic model documents this shape for OpenAPI but does not alter the response body emitted at runtime:
```python
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

---

### `apps/backend/app/core/config.py` (config — EXTEND)

**Analog:** `apps/backend/app/core/config.py` (self).

**Existing field-declaration pattern** (`apps/backend/app/core/config.py:10-29`):
```python
class Settings(BaseSettings):
    """Read configuration from environment + .env file. No prefix; raw env var names."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: PostgresDsn
    redis_url: RedisDsn
    environment: Literal["dev", "staging", "prod"] = "dev"
    debug: bool = False
    secret_key: SecretStr


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance. Cache survives the process lifetime."""
    return Settings()
```

**Additions** (per D-05 + D-25): 4 new fields with defaults that match `.env.example`:
- `access_token_ttl_seconds: int = 900`
- `refresh_token_ttl_seconds: int = 2592000`
- `jwt_clock_leeway_seconds: int = 30`
- `cookie_secure: bool = False`

Append below `secret_key`. Do NOT introduce env-prefix; raw env var names (UPPER_SNAKE_CASE auto-derived by pydantic-settings) match the existing convention at line 11. `get_settings()` and `@lru_cache` STAY unchanged.

---

### `apps/backend/app/core/permissions.py` (utility/policy — NEW)

**Semantic mirror:** `apps/admin-web/src/shared/session/can.ts:1-28` (source of truth for `OWNER_ONLY`):
```typescript
export const OWNER_ONLY: ReadonlyArray<{ action: Action; resource: Resource }> = [
  { action: 'view', resource: 'finance' },
  { action: 'view', resource: 'reports' },
  { action: 'view', resource: 'payroll' },
  { action: 'view', resource: 'compensation' },
  { action: 'view', resource: 'settings' },
  { action: 'view', resource: 'owner-area' },
  { action: 'edit', resource: 'templates' },
  { action: 'delete', resource: 'clients' },
  { action: 'refund', resource: 'finance' },
]

export function can(role: Role, action: Action, resource: Resource): boolean {
  if (role === 'owner') return true
  return !OWNER_ONLY.some((entry) => entry.action === action && entry.resource === resource)
}
```

**StrEnum value source:** `apps/admin-web/src/shared/session/registry.ts:1-14` — `Resource` (11 values) and `Action` (5 values). Backend StrEnum `value` MUST match these strings byte-for-byte (parity test in Phase 6 reads `can.ts` via regex). Note: `Resource.OWNER_AREA = "owner-area"` — string contains a hyphen, Python member name uses underscore.

**Structural analog (Pydantic-free core utility):** `apps/backend/app/core/pagination.py:1-21` (currently imports only `pydantic` — but `permissions.py` has zero pydantic dependency, just stdlib `enum.StrEnum`):
```python
"""Pagination primitives: LimitOffsetParams + generic Page[T] (BE-08)."""

from pydantic import BaseModel, Field
```
Mirror the *structure* (1-line top-doc citing requirement → imports → declarations) but `permissions.py` only imports `from enum import StrEnum` and uses `frozenset` from builtins.

**`can()` body** (per D-23, byte-for-byte semantic mirror of `can.ts`):
```python
def can(role: Role, action: Action, resource: Resource) -> bool:
    if role is Role.OWNER:
        return True
    return (action, resource) not in OWNER_ONLY
```

---

### `apps/backend/app/core/schemas.py` (model/contract-base — NEW)

**Analog:** `apps/backend/app/core/pagination.py` (closest in-tree — also a Pydantic-only core module declaring base contract types with PEP 695 generics).

**Imports + class hierarchy pattern** (mirror `apps/backend/app/core/pagination.py:1-4` style — terse top-doc, then `from pydantic import BaseModel, ...`, then class declarations):
```python
"""Wire-format contract: ContractModel hierarchy + ResponseEnvelope[T] + ProblemDetails (D-07..D-13)."""

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel
```

**`ConfigDict` pattern** (NEW idiom — no prior in-tree usage). Phase 4 introduces this; ensure `validate_by_name=True` AND `validate_by_alias=True` are BOTH set (Pydantic 2.11 raises `PydanticUserError(code='validate-by-alias-and-name-false')` if both are False). Do NOT use the deprecated `populate_by_name=True`.

**PEP 695 generic pattern** (verbatim from `apps/backend/app/core/pagination.py:13-20`):
```python
class Page[T](BaseModel):
    """Generic page envelope for list responses. Mirrors the contract documented
    in CLAUDE.md Domain Conventions: never return bare arrays."""

    items: list[T]
    total: int
    limit: int
    offset: int
```
Apply identically to `ResponseEnvelope[T](ContractModel): data: T`. The class hierarchy (5 classes per D-09: `ContractModel` → `RequestContract`, `ResponseData` → `ResponseEnvelope[T]`, plus `ProblemDetails`) follows the `BaseModel` + class-level `model_config = ConfigDict(...)` shape.

**`ProblemDetails` shape source** — mirror the runtime body emitted by `apps/backend/app/core/exceptions.py:42-51`:
```python
content={
    "code": exc.code,
    "message": exc.message,
    "fields": exc.fields,
},
```
→ `ProblemDetails(ContractModel): code: str; message: str; fields: dict[str, object] | None = None`. NOT RFC 7807 `{type, title, status, detail, instance}` (per `<specifics>` D-08 rationale).

---

### `apps/backend/app/core/pagination.py` (model/contract — REWRITE)

**Analog:** `apps/backend/app/core/pagination.py` (self, prior shape — wholesale replacement).

**Existing shape being deleted** (`apps/backend/app/core/pagination.py:1-21`):
```python
"""Pagination primitives: LimitOffsetParams + generic Page[T] (BE-08)."""

from pydantic import BaseModel, Field


class LimitOffsetParams(BaseModel):
    """Bounded limit/offset pagination params for list endpoints."""

    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class Page[T](BaseModel):
    """Generic page envelope for list responses. Mirrors the contract documented
    in CLAUDE.md Domain Conventions: never return bare arrays."""

    items: list[T]
    total: int
    limit: int
    offset: int
```

**Replacement** (per D-10) preserves the PEP 695 generic style + `Field(default=..., ge=..., le=...)` validators but flips to page/pageSize and inherits from the new contract bases:
```python
"""Pagination contract: PageQuery (request) + PaginatedData[T] (response payload) (D-10, API-04)."""

from pydantic import Field

from app.core.schemas import PaginatedData_was_here  # placeholder; actual import below
from app.core.schemas import RequestContract, ResponseData


class PageQuery(RequestContract):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)  # → pageSize on wire via to_camel


class PaginatedData[T](ResponseData):
    items: list[T]
    total: int
    page: int
    page_size: int  # → pageSize on wire
```

**Field constraint convention** preserved verbatim from existing line 9: `Field(default=20, ge=1, le=100)` — same pageSize bounds as the deleted `limit`. `LimitOffsetParams` and the old `Page[T]` are DELETED with no compatibility shim (clean break — no in-tree consumers; only `/healthz` exists and it doesn't paginate).

---

### `apps/backend/app/modules/clients/__init__.py` (module-placeholder — `git mv`)

**Source (current):** `apps/backend/app/modules/members/__init__.py:1`:
```python
"""Members module placeholder. TODO Phase B+: client/member entity + CRUD endpoints."""
```

**Action:** `git mv apps/backend/app/modules/members apps/backend/app/modules/clients` — preserves blame. Update the docstring inside `__init__.py` from "Members module" to "Clients module" as a follow-up edit.

---

### `apps/backend/.importlinter` (config/lint — one-line edit)

**Analog:** `apps/backend/.importlinter` (self).

**Existing contract block** (`apps/backend/.importlinter:13-25`) — only line 19 changes:
```ini
[importlinter:contract:modules-independent]
name = modules cannot import each other
type = independence
modules =
    app.modules.auth
    app.modules.members        ← REPLACE THIS LINE WITH:  app.modules.clients
    app.modules.memberships
    app.modules.visits
    app.modules.trainers
    app.modules.schedule
    app.modules.bookings
    app.modules.billing
    app.modules.notifications
```

The two surrounding contracts (`core-not-depend-on-modules` lines 5-11, `integrations-not-depend-on-modules` lines 27-33) STAY UNCHANGED.

---

### `apps/backend/pyproject.toml` (config/deps — extend)

**Analog:** `apps/backend/pyproject.toml` (self).

**Existing dependency style** (`apps/backend/pyproject.toml:6-18`):
```toml
dependencies = [
    "fastapi>=0.115",
    "sqlalchemy>=2.0",
    "asyncpg>=0.30",
    "alembic>=1.13",
    "pydantic>=2.0",
    "pydantic-settings>=2.0",
    "structlog>=24.0",
    "arq>=0.26",
    "redis>=5.0",
    "httpx>=0.27",
    "uvicorn[standard]>=0.30",
]
```

**Mutations** (per CONTEXT.md INFRA-07):
- BUMP `pydantic>=2.0` → `pydantic>=2.11,<3` (line 11)
- ADD three lines (alphabetical sort, matching the style — no upper bound on existing entries except the new ones which carry `<N` per CONTEXT.md):
  - `"argon2-cffi>=25.1.0,<26"`
  - `"pyjwt>=2.12.1,<3"`
  - `"python-telegram-bot>=22.7,<23"`
- Run `uv lock` to regenerate `uv.lock`.

**`[tool.pytest.ini_options]` warning filters at lines 48-51 stay unchanged** — the existing `ignore::DeprecationWarning:pydantic.*` already covers any 2.11 deprecations during the cutover.

---

### `apps/backend/.env.example` (config/env — extend)

**Analog:** `apps/backend/.env.example` (self).

**Existing comment + key style** (`apps/backend/.env.example:1-15`):
```bash
# Async PostgreSQL DSN. Phase 3 docker-compose provides this Postgres at localhost:5432.
DATABASE_URL=postgresql+asyncpg://app:app@localhost:5432/sportzal
...
# Placeholder secret. Auth lands in Phase C+ — value is intentionally non-secret in dev.
SECRET_KEY=change-me-dev-only-not-secret
```

**Additions** (per D-05 + D-25) — match the "comment-then-key=value" rhythm; UPPER_SNAKE_CASE:
- `# Access JWT TTL (seconds). 900 = 15 min; refresh-rotates short windows.`
- `ACCESS_TOKEN_TTL_SECONDS=900`
- `# Refresh token TTL (seconds). 2592000 = 30 days.`
- `REFRESH_TOKEN_TTL_SECONDS=2592000`
- `# JWT clock leeway (seconds) for cross-container drift.`
- `JWT_CLOCK_LEEWAY_SECONDS=30`
- `# Set Secure cookie attribute. dev=false (local http); prod startup ASSERTS true.`
- `COOKIE_SECURE=false`

---

### `apps/backend/tests/unit/test_security.py` (test/unit — FILL)

**Current state** (`apps/backend/tests/unit/test_security.py:1-16`) — import smoke only, must be wholesale replaced.

**Closest in-tree analog:** `apps/backend/tests/integration/test_healthz.py:1-32` (test naming + assertion style; note: integration, but Phase-4 unit tests follow the same naming/idiom — no fixtures needed because Phase 4 helpers are pure functions).

**Test naming pattern** (verbatim from `apps/backend/tests/integration/test_healthz.py:18`):
```python
async def test_healthz_returns_200_and_status_ok(async_client: AsyncClient) -> None:
    response = await async_client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```
→ Phase 4 unit tests: `def test_encode_decode_round_trip() -> None`, `def test_decode_expired_raises_invalid_access_token() -> None`, `def test_hash_verify_round_trip() -> None`, `def test_verify_wrong_password_raises_invalid_password() -> None`, `def test_generate_otp_code_is_6_digits() -> None`, `def test_generate_deep_link_token_is_43_chars() -> None`. Sentence-style names per CLAUDE.md Testing Conventions.

**Module-level imports** (no fixtures needed — Phase 4 helpers are sync where possible; `hash_password`/`verify_password` are async and need `pytest-asyncio` which is `auto` mode per `pyproject.toml:45`):
```python
"""Unit tests for app.core.security helpers (D-29)."""
from __future__ import annotations

import pytest

from app.core.exceptions import InvalidAccessToken, InvalidPassword
from app.core.permissions import Role
from app.core.security import (
    decode_access_token,
    encode_access_token,
    generate_csrf_token,
    generate_deep_link_token,
    generate_otp_code,
    generate_refresh_token,
    hash_password,
    verify_password,
)
```

**`from __future__ import annotations`** — copy from `apps/backend/tests/integration/test_healthz.py:11`. Convention across Phase 3 tests.

---

### `apps/backend/tests/unit/test_permissions.py` (test/unit — NEW)

**Analog:** `apps/backend/tests/integration/test_healthz.py:1-32` (style only).

**Imports + skeleton** (no fixtures — pure-Python tests):
```python
"""Unit tests for app.core.permissions (D-29). Verifies OWNER_ONLY and can() semantics."""
from __future__ import annotations

import pytest

from app.core.permissions import OWNER_ONLY, Action, Resource, Role, can
```

**Test cases per D-29** (5 distinct tests):
- `test_owner_short_circuits_true` — `for action in Action: for resource in Resource: assert can(Role.OWNER, action, resource) is True`
- `test_reception_denied_for_every_owner_only_pair` — iterate `OWNER_ONLY`; each → `can(Role.RECEPTION, action, resource) is False`
- `test_reception_allowed_outside_owner_only` — sample non-`OWNER_ONLY` pair (e.g., `(Action.VIEW, Resource.CLIENTS)`) → `True`
- `test_owner_only_is_frozenset_instance` — `assert isinstance(OWNER_ONLY, frozenset)`
- `test_owner_only_has_exactly_nine_entries` — `assert len(OWNER_ONLY) == 9` (parity guard against `apps/admin-web/src/shared/session/can.ts:12-22` count)

---

### `apps/backend/tests/unit/test_schemas.py` (test/unit — NEW)

**Analog:** `apps/backend/tests/integration/test_healthz.py` (style + naming).

**Imports + skeleton:**
```python
"""Unit tests for app.core.schemas wire format (D-29). camelCase wire / snake_case Python."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.pagination import PaginatedData, PageQuery
from app.core.schemas import (
    ContractModel,
    ProblemDetails,
    RequestContract,
    ResponseData,
    ResponseEnvelope,
)
```

**Test cases per D-29** (per CONTEXT.md):
- `test_request_contract_forbids_extras` — pydantic `extra='forbid'` raises `ValidationError` on unknown field
- `test_contract_model_round_trips_camel_and_snake` — both `{"pageSize": 10}` and `{"page_size": 10}` validate successfully (validate_by_name + validate_by_alias)
- `test_response_envelope_dump_by_alias_has_data_key` — `ResponseEnvelope[X](data=X(...)).model_dump(by_alias=True)["data"]` shape match
- `test_paginated_data_serializes_camel_case_pageSize` — wire form has `pageSize`, Python attr is `page_size`
- `test_problem_details_accepts_optional_fields_none` — `ProblemDetails(code="x", message="y")` validates without `fields`

---

### `apps/backend/tests/integration/test_alembic_clean.py` (test/integration — NEW)

**Analog:** `apps/backend/tests/integration/test_healthz.py:1-32` + `apps/backend/tests/conftest.py:32-39, 42-77` (env-loading + per-test app fixture pattern).

**Test entry pattern** (mirror `apps/backend/tests/integration/test_healthz.py`):
```python
"""Integration test: alembic upgrade head + alembic check produce empty diff (SC #3)."""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
```

**Subprocess invocation pattern** — Phase 4 introduces this idiom (no prior in-tree analog for `subprocess` calls). Use `subprocess.run([...], cwd=BACKEND_DIR, check=False, capture_output=True, text=True)` and assert on `returncode == 0` AND `"No new upgrade operations detected." in result.stdout` per RESEARCH.md §Summary point 2.

**Reuse Phase 3 fixture pattern** — the `db_session` fixture from `apps/backend/tests/conftest.py:58-77` shows the canonical "skip if DB not reachable" idiom that this test mirrors:
```python
async with sessionmaker() as session:
    try:
        await session.execute(text("select 1"))
    except Exception as exc:  # noqa: BLE001 — D-10: skip on any connectivity failure
        pytest.skip(
            f"DATABASE_URL not reachable; run `docker compose up postgres` first ({exc!r})"
        )
```
→ The alembic test does the same: try a quick DB ping (or `subprocess.run(["uv", "run", "alembic", "current"], ...)` with non-zero return → `pytest.skip`).

**`.env.example` autoload** is already handled in `apps/backend/tests/conftest.py:32-39` — the alembic subprocess inherits `os.environ`, so `DATABASE_URL` etc. are available without extra plumbing.

---

## Shared Patterns

### Cross-cutting: AppError raise convention

**Source:** `apps/backend/app/core/exceptions.py:7-36` and runtime handler at lines 42-51.

**Apply to:** Every new helper that fails — `decode_access_token`, `verify_password`, `get_current_user`, `require_permission`. Raise the dedicated `AppError` subclass with a short underscored message string. NEVER raise `HTTPException`, NEVER leak library-specific exceptions (`jwt.InvalidTokenError`, `argon2.exceptions.VerifyMismatchError`) to callers.

```python
# correct — domain-typed:
raise InvalidAccessToken("missing_access_cookie")
raise InvalidPassword("verify_mismatch")
raise ForbiddenError(f"forbidden:{action.value}:{resource.value}")
```

### Cross-cutting: lazy `get_settings()` calls

**Source:** `apps/backend/app/core/database.py:24` (`settings = get_settings()` *inside* `db_lifespan`, never at module import).

**Apply to:** `app/core/security.py` (every JWT helper) — call `get_settings()` inside the function body so the `@lru_cache` works correctly under tests that monkey-patch env vars before the cache fills.

### Cross-cutting: PEP 695 generics (NOT `typing.Generic[T]`)

**Source:** `apps/backend/app/core/pagination.py:13` (`class Page[T](BaseModel)`).

**Apply to:** `app/core/schemas.py:ResponseEnvelope[T]` and `app/core/pagination.py:PaginatedData[T]`. Do NOT add `from typing import Generic, TypeVar`. Project hard-pins Python 3.12 (`pyproject.toml:5`); Pydantic 2.11+ supports PEP 695 natively.

### Cross-cutting: Test file conventions

**Source:** `apps/backend/tests/integration/test_healthz.py:11` and `apps/backend/tests/conftest.py:11`:
```python
from __future__ import annotations
```
+ test names as full sentences (`test_healthz_returns_200_and_status_ok`).

**Apply to:** All 4 new/filled test files. Module-level docstring → `from __future__ import annotations` → imports → tests. `pytest-asyncio` is `auto` mode (`apps/backend/pyproject.toml:45`) so async tests need no `@pytest.mark.asyncio` decorator.

### Cross-cutting: import ordering (stdlib → 3rd-party → app-local)

**Source:** `apps/backend/app/core/middleware.py:3-12` and `apps/backend/app/main.py:11-18`. Three blocks separated by a blank line. ruff enforces this; matches the project's existing style.

**Apply to:** `app/core/security.py`, `app/core/dependencies.py`, `app/core/permissions.py`, `app/core/schemas.py`, all 4 test files.

### Cross-cutting: factory + composition root awareness

**Source:** `apps/backend/app/main.py:1-44` — `create_app()` is the ONLY composition root; module-level `app = create_app()` is forbidden by the docstring.

**Apply to:** Phase 4 does NOT modify `app/main.py` (per CONTEXT.md scope — `register_user_loader` wiring lands in Phase 5). But `app/core/dependencies.py` MUST design `register_user_loader` as a composition-root-callable function so Phase 5 can call it inside `create_app()` without core-importing-modules.

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| (none — every Phase 4 file has at least a structural in-tree analog) | | | |

**Notes on near-misses:**
- `app/core/security.py` Argon2 `asyncio.to_thread` wrapping — no prior `to_thread` usage in-tree, but the idiom is canonical Python and the structural analog (pure-helpers + factory module) is `app/core/middleware.py`.
- `tests/integration/test_alembic_clean.py` `subprocess.run` call — no prior subprocess test; `tests/conftest.py:32-39` (env-loader running at import time, reading `.env.example`) is the closest "test layer reaching outside Python" idiom.
- Pydantic `ConfigDict(alias_generator=to_camel, ...)` — first usage in the project. RESEARCH.md §7 carries the verified API; planner may reference RESEARCH.md directly when no codebase analog exists for the inner ConfigDict shape.

## Metadata

**Analog search scope:**
- `apps/backend/app/core/` (all 8 files read)
- `apps/backend/app/main.py`, `apps/backend/app/api/router.py`, `apps/backend/app/api/v1/router.py`, `apps/backend/app/api/v1/health.py`
- `apps/backend/app/modules/members/__init__.py`
- `apps/backend/tests/conftest.py`, `apps/backend/tests/integration/test_healthz.py`, `apps/backend/tests/unit/test_security.py`
- `apps/backend/.importlinter`, `apps/backend/pyproject.toml`, `apps/backend/.env.example`, `apps/backend/alembic/env.py`
- `apps/admin-web/src/shared/session/can.ts`, `apps/admin-web/src/shared/session/registry.ts` (READ-ONLY semantic mirror source)

**Files scanned:** 18 (full read on each analog; no re-reads)
**Pattern extraction date:** 2026-05-01

---

*Phase: 04-auth-foundations-cookie-rbac-primitives*
*Pattern map ready for `/gsd-planner` consumption.*
