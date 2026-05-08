# Phase 23: Hygiene + Active Sessions Backend - Pattern Map

**Mapped:** 2026-05-08
**Files analyzed:** 12 new/modified files
**Analogs found:** 12 / 12

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `apps/backend/app/core/exceptions.py` | model | request-response | itself (`InvalidAccessToken` lines 53-57, `InvalidPassword` lines 60-71) | exact |
| `apps/backend/app/core/dependencies.py` | middleware | request-response | itself (`get_current_user` lines 194-224) | exact |
| `apps/backend/app/core/audit.py` | config | event-driven | itself (`LOCKED_AUDIT_EVENTS` lines 78-123) | exact |
| `apps/backend/app/modules/auth/schemas.py` | model | request-response | itself + `app/core/pagination.py` (`PaginatedData[T]` lines 32-43) | exact |
| `apps/backend/app/modules/auth/service.py` | service | CRUD + event-driven | itself (`revoke_session` lines 419-482, `_write_session_keys` lines 206-227) | exact |
| `apps/backend/app/modules/auth/router.py` | controller | request-response | itself (`logout` lines 115-138, `logout_all` lines 141-153) | exact |
| `apps/backend/openapi.json` | config | — | previous regen cycles (Phase 21/22 precedent) | role-match |
| `packages/api-client/src/schema.d.ts` | config | — | itself (Phase 21 drift-gate precedent) | role-match |
| `packages/api-client/src/schema.contract.test.ts` | test | — | itself lines 61-68 (`_HasSessions` conditional probe) | exact |
| `apps/backend/tests/integration/test_auth_login_argon2_hygiene.py` | test | request-response | `tests/integration/auth/test_login.py` lines 27-131 | exact |
| `apps/backend/tests/integration/test_auth_invalid_session.py` | test | request-response | `tests/integration/auth/test_login.py` + `tests/integration/rbac/` | exact |
| `apps/backend/tests/integration/test_auth_sessions_endpoints.py` | test | CRUD | `tests/integration/auth/test_logout.py` (logout + CSRF matrix) | exact |

---

## Pattern Assignments

### `apps/backend/app/core/exceptions.py` (model, request-response)

**Analog:** itself — `InvalidAccessToken` and `InvalidPassword` at lines 53-71

**New class shape** (lines 53-71 — copy both classes as the exact template):
```python
class InvalidAccessToken(AppError):  # noqa: N818
    """JWT decode/expire failure (Phase 4 — used by app.core.security.decode_access_token)."""
    code = "invalid_token"
    status_code = 401


class InvalidPassword(AppError):  # noqa: N818
    """Argon2id verify mismatch / malformed hash. ..."""
    code = "invalid_credentials"
    status_code = 401
```

**Pattern to apply:** Add `InvalidSession` as a sibling after `InvalidPassword`. Docstring must name the wrap site (`dependencies.py:221`). Use same `# noqa: N818` comment (exception not ending in Error). `code = "invalid_session"`, `status_code = 401`. No `fields` kwarg in the constructor — base `AppError.__init__` handles it.

---

### `apps/backend/app/core/dependencies.py` (middleware, request-response)

**Analog:** itself — `get_current_user` lines 194-224

**Current wrap site** (line 221):
```python
    user = await _user_loader(session, UUID(claims.sub))
```

**Pattern to apply:** Wrap the single `UUID(claims.sub)` call:
```python
    try:
        uid = UUID(claims.sub)
    except ValueError:
        raise InvalidSession("invalid_session")
    user = await _user_loader(session, uid)
```
Add `InvalidSession` to the import from `app.core.exceptions` (line 7 area). The `InvalidSession` import sits alongside the existing `InvalidAccessToken` import.

**Import pattern** (lines 7-11 of dependencies.py, extract):
```python
from app.core.exceptions import (
    ForbiddenError,
    InvalidAccessToken,
    # ADD: InvalidSession,
)
```

---

### `apps/backend/app/core/audit.py` (config, event-driven)

**Analog:** itself — `LOCKED_AUDIT_EVENTS` frozenset lines 78-123

**Existing session pair** (lines 85-86):
```python
("login_success", "session"),
("login_failed", "login_attempt"),
("session_revoked", "session"),
```

**Pattern to apply:** Add a NEW entry to the frozenset. The entry for D-23-10:
```python
("session_revoked", "auth_session"),
```
This is a SECOND `session_revoked` pair with a DIFFERENT `resource_type`. The existing `("session_revoked", "session")` at line 86 remains for `/logout` and `/logout-all`. The new `("session_revoked", "auth_session")` is for the per-family revoke endpoint (D-23-10 specifies `resource_type='auth_session'`).

**Critical rule:** Both the `event` argument AND the `resource_type` argument to `audit.emit()` MUST be string literals at every callsite — the AST gate `tests/unit/test_audit_taxonomy.py` enforces this at CI time.

---

### `apps/backend/app/modules/auth/schemas.py` (model, request-response)

**Analog 1:** itself — existing `ResponseData` subclasses (e.g. `UserPublic`, `LoginResponse`)
**Analog 2:** `apps/backend/app/core/pagination.py` — `PaginatedData[T]` lines 32-43

**Existing schema shape** (lines 22-50 of schemas.py):
```python
class UserPublic(ResponseData):
    id: UUID
    role: Role
    full_name: str  # → fullName on wire

class LoginResponse(ResponseData):
    user: UserPublic
```

**Pagination envelope shape** (pagination.py lines 32-43):
```python
class PaginatedData[T](ResponseData):
    items: list[T]
    total: int
    page: int
    page_size: int  # → pageSize on wire
```

**Pattern to apply:** Add three new classes. All extend `ResponseData`. Import `PaginatedData` from `app.core.pagination`. camelCase serialization is automatic via `alias_generator=to_camel` on `ContractModel`.

```python
from app.core.pagination import PaginatedData

class ActiveSessionItem(ResponseData):
    family_id: UUID          # → familyId
    created_at: datetime     # → createdAt
    last_used_at: datetime   # → lastUsedAt
    user_agent: str | None   # → userAgent
    channel: str             # e.g. 'email_password' | 'telegram'
    is_current: bool         # → isCurrent

# Type alias — planner and executor may choose inline annotation instead
ActiveSessionsListResponse = PaginatedData[ActiveSessionItem]
```

`RevokeSessionResponse` may be `None` (204 → `ResponseEnvelope[None]`) — mirror the `/logout` shape; no dedicated schema class required unless the plan prefers an explicit model.

---

### `apps/backend/app/modules/auth/service.py` (service, CRUD + event-driven)

**Analog 1:** `_write_session_keys` lines 206-227 — Redis session JSON writer
**Analog 2:** `revoke_session` lines 419-482 — single-family revoke pattern
**Analog 3:** `revoke_all_sessions` lines 490-538 — bulk-revoke + audit pattern

**Redis session JSON shape** (lines 216-221):
```python
session_value = json.dumps(
    {
        "family_id": str(family_id),
        "last_seen_at": now.isoformat(),
        "refresh_token_hash": refresh_hash,
    }
)
```
CD-01: extend to `{"family_id", "last_seen_at", "refresh_token_hash", "user_agent", "channel"}`.

**Revoke single-family pattern** (lines 448-482):
```python
row = await session.scalar(
    select(RefreshToken).where(RefreshToken.token_hash == presented_hash)
)
if row is None:
    return
# ... UPDATE + audit.emit("session_revoked", resource_type="session", ...) + commit + Redis DEL
```

**Audit emit pattern** (lines 469-475):
```python
await audit.emit(
    session,
    "session_revoked",
    actor_user_id=user_id,
    resource_type="session",
    resource_id=family_id,
)
await session.commit()
```
The new `_revoke_family(user_id, family_id)` helper uses `resource_type='auth_session'` (D-23-10). The existing `revoke_session` retains `resource_type='session'`.

**Structlog WARNING emit pattern** — for HYG-01 D-23-13, add caller-side emit in the `authenticate()` function's `except InvalidPassword:` block (lines 114-127). Mirror the existing `structlog.get_logger("audit").info(event, **payload)` call in `audit.py:171` but use `logger.warning(...)` directly at the service callsite:
```python
import structlog
_log = structlog.get_logger(__name__)

# Inside authenticate(), after verify_password raises:
except InvalidPassword:
    _log.warning(
        "login_verify_error",
        reason="verify_mismatch",   # or 'invalid_hash' | 'other'
        email_lower=email_lower,
        ip=ip,
    )
    await bump_login_rate(...)
    await audit.emit(session, "login_failed", ..., reason="invalid_credentials", ...)
    raise
```

---

### `apps/backend/app/modules/auth/router.py` (controller, request-response)

**Analog:** itself — `/logout` handler lines 115-138 and `/logout-all` lines 141-153

**Auth + CSRF dep matrix** (lines 123-124 and 144-146):
```python
_user: Annotated[CurrentUser, Depends(require_authenticated())],
_csrf: Annotated[None, Depends(verify_csrf)],
session: Annotated[AsyncSession, Depends(get_db)],
redis: Annotated[Redis, Depends(get_redis)],
```
RBAC-04 ordering: auth dep declared BEFORE CSRF dep so unauthenticated callers get 401 before 403.

**GET sessions route shape** (no CSRF — GET is exempt per Phase 6 D-09):
```python
@router.get("/sessions", response_model=ResponseEnvelope[PaginatedData[ActiveSessionItem]])
async def list_sessions(
    user: Annotated[CurrentUser, Depends(require_authenticated())],
    query: PageQuery = Depends(),
    request: Request = ...,
    session: Annotated[AsyncSession, Depends(get_db)] = ...,
    redis: Annotated[Redis, Depends(get_redis)] = ...,
) -> ResponseEnvelope[PaginatedData[ActiveSessionItem]]:
    ...
    return envelope(await list_user_sessions(...))
```

**POST revoke route shape** (requires CSRF — mutating method):
```python
@router.post("/sessions/{family_id}/revoke", response_model=ResponseEnvelope[None], status_code=204)
async def revoke_family(
    family_id: UUID,
    response: Response,
    user: Annotated[CurrentUser, Depends(require_authenticated())],
    _csrf: Annotated[None, Depends(verify_csrf)],
    ...
) -> ResponseEnvelope[None]:
    ...
    return envelope(None)
```
Self-revoke branch calls `clear_session_cookies(response, secure=settings.cookie_secure)` — same pattern as `/logout` lines 137.

**Import additions** to router.py — mirror the existing import block (lines 22-57):
```python
from app.core.pagination import PageQuery, PaginatedData
from app.modules.auth.schemas import (
    ...,
    ActiveSessionItem,
)
from app.modules.auth.service import (
    ...,
    list_user_sessions,
    _revoke_family,  # or a public alias
)
```

---

## Shared Patterns

### AppError subclass shape
**Source:** `apps/backend/app/core/exceptions.py` lines 53-71
**Apply to:** `InvalidSession` new class
```python
class InvalidSession(AppError):  # noqa: N818
    """UUID parse failure on sz_access sub claim (Phase 23 D-23-11/D-23-12)."""
    code = "invalid_session"
    status_code = 401
```
No `__init__` override — `AppError.__init__(message, *, fields)` is inherited. Call as `raise InvalidSession("invalid_session")`.

### CSRF signature-level dependency ordering (RBAC-04)
**Source:** `apps/backend/app/modules/auth/router.py` lines 122-124
**Apply to:** `POST /sessions/{family_id}/revoke`
```python
_user: Annotated[CurrentUser, Depends(require_authenticated())],
_csrf: Annotated[None, Depends(verify_csrf)],
```
Auth dep FIRST, CSRF dep SECOND — FastAPI resolves deps in declaration order. Unauthenticated callers get 401 before CSRF check.

### Audit emit callsite literals
**Source:** `apps/backend/app/core/audit.py` lines 165-180
**Apply to:** all new `audit.emit()` callsites in service.py and router.py
```python
await audit.emit(
    session,
    "session_revoked",           # MUST be a string literal
    actor_user_id=user.id,
    resource_type="auth_session", # MUST be a string literal
    resource_id=family_id,
)
```
The AST gate `tests/unit/test_audit_taxonomy.py` fails CI on any non-literal. Both `event` and `resource_type` must appear as literal strings at every callsite.

### Pagination envelope
**Source:** `apps/backend/app/core/pagination.py` lines 20-43
**Apply to:** `GET /sessions` response model and service return type
```python
# Request params
query: PageQuery = Depends()  # page=1, page_size=20, max 100

# Response
response_model=ResponseEnvelope[PaginatedData[ActiveSessionItem]]
```
Wire shape: `{"data": {"items": [...], "total": N, "page": 1, "pageSize": 20}}`.

### Cookie clear (self-revoke / D-23-8)
**Source:** `apps/backend/app/modules/auth/router.py` lines 133-137
**Apply to:** self-revoke branch in `POST /sessions/{family_id}/revoke`
```python
settings = get_settings()
clear_session_cookies(response, secure=settings.cookie_secure)
```
Clears all three cookies: `sz_access` (Path=/), `sz_refresh` (Path=/api/v1/auth), `sportzal_csrf` (Path=/).

### Test fixture: SAVEPOINT session + ASGITransport client
**Source:** `apps/backend/tests/conftest.py` lines 48-143
**Apply to:** all three new integration test files
```python
async def test_example(
    async_client: AsyncClient,   # httpx client over ASGITransport, not network
    db_session: AsyncSession,    # SAVEPOINT-wrapped; commits become nested SAVEPOINTs
    app: FastAPI,                # LifespanManager-fired; app.state.redis available
) -> None:
    ...
```
`async_client` fixture already installs `get_db` and `get_redis` overrides — no manual `app.dependency_overrides` in tests unless testing a custom override scenario (see `test_visits_meta.py` for the manual-override pattern).

### Test fixture: redis flush between tests
**Source:** `apps/backend/tests/integration/auth/test_login.py` lines 27-46 and `test_logout.py` lines 37-53
**Apply to:** `test_auth_login_argon2_hygiene.py` (rate-limit test requires clean Redis) and `test_auth_sessions_endpoints.py`
```python
@pytest_asyncio.fixture
async def redis_clean(app: FastAPI) -> Redis:
    client: Redis = app.state.redis
    await client.flushdb()
    return client

@pytest_asyncio.fixture
async def seeded_owner(db_session: AsyncSession, redis_clean: Redis) -> User:
    user = User(
        email=OWNER_EMAIL,
        password_hash=await hash_password(OWNER_PASSWORD),
        role=Role.OWNER,
        full_name="...",
    )
    db_session.add(user)
    await db_session.commit()
    return user
```

### structlog capture in tests
**Source:** `apps/backend/tests/integration/auth/test_logout.py` lines 84-94
**Apply to:** `test_auth_login_argon2_hygiene.py` (HYG-01 structlog WARNING assertion)
```python
from structlog.testing import capture_logs

with capture_logs() as captured:
    r = await async_client.post("/api/v1/auth/login", json={...})

events = [c.get("event") for c in captured]
assert "login_verify_error" in events
# Also check the 'reason' field:
warn_entry = next(c for c in captured if c.get("event") == "login_verify_error")
assert warn_entry.get("reason") in {"invalid_hash", "verify_mismatch", "other"}
```

### Schema contract test flip
**Source:** `packages/api-client/src/schema.contract.test.ts` lines 61-68
**Apply to:** `packages/api-client/src/schema.contract.test.ts` — flip the conditional from "absent" to "present"
```typescript
// Current (Phase 21 — sessions absent):
type _HasSessions = HasPath<'/api/v1/auth/sessions'>
type _SessionsProbe = _HasSessions extends true
  ? AssertNonNever<paths['/api/v1/auth/sessions' & keyof paths]['get']>
  : true
const _sessionsCheck: _SessionsProbe = true

// After Phase 23 regen — sessions path IS present:
// Add '/api/v1/auth/sessions' to the static _checks tuple as AssertNonNever<...>
// and add '/api/v1/auth/sessions/{family_id}/revoke' post check.
// The _HasSessions conditional probe can remain as-is (it resolves to the first
// branch now that the path exists, which evaluates AssertNonNever — still true).
```

---

## No Analog Found

All files have close analogs within the existing codebase. No files require fallback to RESEARCH.md external patterns.

---

## Metadata

**Analog search scope:** `apps/backend/app/core/`, `apps/backend/app/modules/auth/`, `apps/backend/tests/integration/auth/`, `apps/backend/tests/conftest.py`, `packages/api-client/src/`
**Files scanned:** 14 source files read directly; ~10 grep searches
**Pattern extraction date:** 2026-05-08
