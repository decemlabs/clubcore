# Phase 66: Idempotency Hardening — Pattern Map

**Mapped:** 2026-05-29
**Files analyzed:** 8 new/modified files
**Analogs found:** 8 / 8

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `apps/backend/app/core/idempotency.py` | utility (core primitive) | request-response | self (extend existing) | exact — self-referential |
| `apps/backend/app/modules/pt_packages/router.py` | controller | request-response | self (refactor existing inline block) | exact — self-referential |
| `apps/backend/app/modules/pt_sessions/router.py` | controller | request-response | `pt_packages/router.py:244-300` | exact |
| `apps/backend/app/modules/bookings/router.py` | controller | request-response | `pt_packages/router.py:244-300` | exact |
| `apps/backend/app/modules/memberships/router.py` | controller | request-response | `pt_packages/router.py:244-300` + `online_payments/router.py:107-176` | exact |
| `apps/backend/app/modules/online_payments/router.py` | controller | request-response | `pt_packages/router.py:244-300` + self (`_outer_idempotency_replay_or_run`) | exact — self-referential |
| `apps/backend/app/main.py` | config (OpenAPI post-processor) | transform | self (extend `_customize_openapi`) | exact — self-referential |
| `.planning/handoff/v1.11-idempotency-audit.md` | documentation | n/a | `.planning/phases/64-contract-freeze-openapi-curation/64-CONTEXT.md` audit tables | role-match |
| `apps/backend/tests/integration/{module}/test_idempotency_*.py` | test | request-response | `tests/integration/payments/test_idempotency.py` | exact |

---

## Pattern Assignments

### `apps/backend/app/core/idempotency.py` (utility, request-response)

**Analog:** self — extend the existing module.

**Current imports** (lines 21-33):
```python
from __future__ import annotations

import base64
import hashlib
import json
import re
from typing import Annotated, TypedDict

from fastapi import Depends, Request
from redis.asyncio import Redis

from app.core.exceptions import ConflictError, ValidationAppError
from app.core.redis import get_redis
```

**Required new imports for IDM-05/IDM-06 orchestrator:**
```python
# Add to imports — user-scope and AppError
from app.core.exceptions import AppError, ConflictError, ValidationAppError
# CurrentUser type for verify_idempotency signature change
from app.core.dependencies import CurrentUser, get_current_user
```

**Current constants** (lines 35-40):
```python
IDEMPOTENCY_KEY_PATTERN: str = r"^[A-Za-z0-9_:-]{1,128}$"  # IDM-02: change to {16,128}
_IDEMPOTENCY_KEY_RE = re.compile(IDEMPOTENCY_KEY_PATTERN)

IDEMPOTENCY_REDIS_PREFIX: str = "cc:idem:"
IDEMPOTENCY_TTL_SECONDS: int = 3600  # IDM-02: change to 86400
_PLACEHOLDER: str = "__in_flight__"
```

**IDM-02 changes:** `{1,128}` → `{16,128}` and `3600` → `86400`. Both must change atomically in the same commit.

**Current `verify_idempotency` signature** (lines 60-89) — IDM-05 user-scope addition:
```python
async def verify_idempotency(
    request: Request,
    redis: Annotated[Redis, Depends(get_redis)],
) -> str:
    # ...
    return f"{request.method}:{request.url.path}:{key}"
```

After IDM-05, the return value changes to include `current_user.id` FIRST (D-66-USER-SCOPE — LOCKED):
```python
async def verify_idempotency(
    request: Request,
    redis: Annotated[Redis, Depends(get_redis)],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> str:
    # ...
    return f"{current_user.id}:{request.method}:{request.url.path}:{key}"
    # Full Redis key with prefix: cc:idem:{user_id}:{method}:{path}:{header_value}
```

**Current `idempotent_response` helper** (lines 164-196) — this is the pre-handler check only. The new shared orchestrator (D-66-LIFECYCLE-HELPER) extends it with post-handler store + exception branches. The existing `idempotent_response` function is the inner logic the orchestrator wraps:
```python
async def idempotent_response(
    redis: Redis,
    key: str,
    body_bytes: bytes,
) -> IdempotencyEnvelope | None:
    # Returns None → caller runs handler, then calls store_idempotency_response
    # Returns envelope → caller replays
    # Raises ConflictError("idempotency_in_flight") or ValidationAppError("idempotency_key_reuse")
```

**IDM-06 exception-aware orchestrator pattern** (new function to add):

The orchestrator wraps the handler callable. Shape is at planner's discretion (context manager vs callable-wrapper). The exception branching logic to implement (per D-66-EXC-CLEANUP):
```python
# Pattern: AppError branch → serialize error envelope, store, re-raise
# Pattern: unknown Exception branch → redis.delete(_redis_key(key)), re-raise
# Error envelope shape must match exceptions.py handler at lines 441-450:
# {"code": exc.code, "message": exc.message, "fields": exc.fields}
```

The AppError handler envelope shape (from `apps/backend/app/core/exceptions.py` lines 441-450):
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

The error bytes to store for replay must be `json.dumps({"code": exc.code, "message": exc.message, "fields": exc.fields}, separators=(",", ":"), ensure_ascii=False).encode("utf-8")`.

**`__all__` export list** (lines 199-210) — add any new public names (orchestrator, updated constants).

---

### `apps/backend/app/modules/pt_packages/router.py` (controller, request-response)

**Analog:** self — refactor existing inline block onto the shared orchestrator.

**Current inline block (lines 244-300) — this IS the refactor target:**
```python
# Body hash for replay-collision detection on identical Idempotency-Key.
incoming_body = await request.body()
incoming_hash = body_sha256(incoming_body)

is_first = await begin_idempotency(redis, idempotency_key)
if not is_first:
    stored = await load_idempotency_response(redis, idempotency_key)
    if stored is None or isinstance(stored, str):
        raise ConflictError("idempotency_in_flight")
    if stored["body_hash"] != incoming_hash:
        raise ValidationAppError("idempotency_key_reuse")
    return Response(
        content=base64.b64decode(stored["body_b64"]),
        status_code=stored["status_code"],
        media_type="application/json",
    )

# ... service call + manual envelope build + redis.set ...
pt_package = await service.create_pt_package(session, actor, payload)
response_envelope = envelope(pt_package)
body_bytes = json.dumps(
    response_envelope.model_dump(mode="json", by_alias=True),
    separators=(",", ":"),
    ensure_ascii=False,
).encode("utf-8")
envelope_json = json.dumps(
    {
        "status_code": status.HTTP_201_CREATED,
        "body_hash": incoming_hash,
        "body_b64": base64.b64encode(body_bytes).decode("ascii"),
    },
    separators=(",", ":"),
    ensure_ascii=False,
)
await redis.set(
    f"{IDEMPOTENCY_REDIS_PREFIX}{idempotency_key}",
    envelope_json,
    ex=IDEMPOTENCY_TTL_SECONDS,
)
return Response(
    content=body_bytes,
    status_code=status.HTTP_201_CREATED,
    media_type="application/json",
)
```

After refactor this ~55-line block collapses to a thin call into the shared orchestrator. The `redis` parameter stays in the endpoint signature because `Depends(get_redis)` is already there (carried by `verify_idempotency` dependency graph — FastAPI deduplicates). After IDM-05 lands, `current_user` injection happens inside `verify_idempotency` automatically; no per-route signature change for user-scoping.

**Endpoint signature pattern** (lines 217-228) — the RBAC-04 ordering invariant is locked:
```python
async def create_pt_package(
    payload: PtPackageCreateRequest,
    request: Request,
    actor: Annotated[CurrentUser, Depends(require_permission(Action.CREATE, Resource.PT_PACKAGES))],
    _csrf: Annotated[None, Depends(verify_csrf)],
    idempotency_key: Annotated[str, Depends(verify_idempotency)],
    redis: Annotated[Redis, Depends(get_redis)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
```

**Ordering constraint (LOCKED, enforced by `test_route_introspection.py`):**
`auth → require_permission → verify_csrf → verify_idempotency → get_db`

---

### `apps/backend/app/modules/pt_sessions/router.py` (controller, request-response)

**Analog:** `apps/backend/app/modules/pt_packages/router.py:244-300` (verbatim copy of same inline pattern, already present in `pt_sessions/router.py:116-157` and `200-253`).

**Two callsites exist:**
- `record_pt_session` (lines 116-157, POST, 201)
- `cancel_pt_session` (lines 213-253, POST, 200)

Both follow the identical ~35-line inline claim/replay/store pattern. Both collapse to the shared orchestrator. Import cleanup: after refactor, remove `IDEMPOTENCY_REDIS_PREFIX`, `IDEMPOTENCY_TTL_SECONDS`, `begin_idempotency`, `load_idempotency_response` from imports (lines 39-46) — only `verify_idempotency` and the new orchestrator needed.

**Current imports** (lines 27-57):
```python
import base64
import json
from typing import Annotated
# ...
from app.core.exceptions import ConflictError, ValidationAppError
from app.core.idempotency import (
    IDEMPOTENCY_REDIS_PREFIX,
    IDEMPOTENCY_TTL_SECONDS,
    begin_idempotency,
    body_sha256,
    load_idempotency_response,
    verify_idempotency,
)
```

---

### `apps/backend/app/modules/bookings/router.py` (controller, request-response)

**Analog:** Same as `pt_sessions/router.py` — identical two-callsite pattern (lines 120-161 for `create_booking`, lines 215-256 for `cancel_booking`).

**Two callsites exist:**
- `create_booking` (lines 120-161, POST, 201)
- `cancel_booking` (lines 215-256, POST, 200)

Same import cleanup applies — the 5 low-level imports (lines 36-44) collapse to `verify_idempotency` + orchestrator after refactor.

---

### `apps/backend/app/modules/memberships/router.py` (controller, request-response)

**Analog:** `apps/backend/app/modules/pt_packages/router.py:244-300` + `apps/backend/app/modules/online_payments/router.py:107-176`

**One existing callsite (IDM-02/05/06 refactor target):**
- `create_membership` (lines 289-373) — full inline block mirroring pt_packages pattern.

**Four new category-A endpoints to wire (IDM-07 candidates — currently no `Depends(verify_idempotency)`):**
- `cancel_membership` (line 382) — no idempotency wire yet; emits `membership_cancelled` audit event → category A
- `freeze_membership` (line 421) — no idempotency wire yet; emits audit events → category A
- `unfreeze_membership` (line 452) — no idempotency wire yet; emits audit events → category A
- `renew_membership` (line 484) — no idempotency wire yet; creates a new membership row → category A

Current signatures for the four new wiring targets (status 200 for cancel/freeze/unfreeze, 201 for renew):
```python
async def cancel_membership(
    membership_id: UUID,
    payload: MembershipCancelRequest,
    actor: Annotated[CurrentUser, Depends(require_permission(Action.CANCEL, Resource.MEMBERSHIPS))],
    _csrf: Annotated[None, Depends(verify_csrf)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[MembershipResponse]:

async def freeze_membership(
    membership_id: UUID,
    actor: Annotated[CurrentUser, Depends(require_permission(Action.CREATE, Resource.MEMBERSHIPS))],
    _csrf: Annotated[None, Depends(verify_csrf)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[MembershipResponse]:
```

After IDM-07 wiring, these signatures gain `request: Request`, `idempotency_key: Annotated[str, Depends(verify_idempotency)]`, `redis: Annotated[Redis, Depends(get_redis)]`, and return type changes to `Response` (not `ResponseEnvelope`). The RBAC-04 ordering is preserved: `require_permission → verify_csrf → verify_idempotency`.

**Special case — `freeze_membership` has no request body.** The body hash is `body_sha256(b"")`. The orchestrator must handle empty bodies correctly (idempotent_response still uses the membership_id path-param as part of the route-binding in `verify_idempotency`'s key shape, so empty-body collision is scoped to the user+path combination).

---

### `apps/backend/app/modules/online_payments/router.py` (controller, request-response)

**Analog:** self — `_outer_idempotency_replay_or_run` at lines 107-176 is already the module-local orchestrator pattern. After IDM-02/05/06, this function refactors onto the shared orchestrator from `app/core/idempotency.py`.

**Current module-local helper** (lines 107-176) — the callable-wrapper pattern:
```python
async def _outer_idempotency_replay_or_run(
    *,
    request: Request,
    idempotency_key: str,
    redis: Redis,
    runner: Callable[[], Awaitable[SellResponse]],
) -> Response:
    incoming_body = await request.body()
    incoming_hash = body_sha256(incoming_body)

    is_first = await begin_idempotency(redis, idempotency_key)
    if not is_first:
        stored = await load_idempotency_response(redis, idempotency_key)
        if stored is None or isinstance(stored, str):
            raise ConflictError("idempotency_in_flight")
        if stored["body_hash"] != incoming_hash:
            raise ValidationAppError("idempotency_key_reuse")
        return Response(
            content=base64.b64decode(stored["body_b64"]),
            status_code=stored["status_code"],
            media_type="application/json",
        )

    sell_response = await runner()
    response_envelope = envelope(sell_response)
    body_bytes = json.dumps(
        response_envelope.model_dump(mode="json", by_alias=True),
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    envelope_json = json.dumps(...)
    await redis.set(f"{IDEMPOTENCY_REDIS_PREFIX}{idempotency_key}", envelope_json, ex=IDEMPOTENCY_TTL_SECONDS)
    return Response(content=body_bytes, status_code=status.HTTP_201_CREATED, media_type="application/json")
```

This is the **best existing analog for the shared orchestrator's callable-wrapper shape** — the planner should consider this the reference implementation when deciding on context-manager vs callable-wrapper (it already exists and works). The shared orchestrator in `app/core/idempotency.py` will generalize this pattern with the IDM-06 exception branches added.

**Two refund endpoints that are IDM-07 new wiring targets (lines 417-471+):**
- `refund_membership_online` — `POST /memberships/{membership_id}/refund`
- `refund_pt_package_online` — `POST /pt-packages/{pt_package_id}/refund`
These are financial mutations that must become category-A.

---

### `apps/backend/app/main.py` — `_customize_openapi()` post-processor (config, transform)

**Analog:** self — extend the existing `_customize_openapi` closure.

**Current post-processor pattern** (lines 604-644) — the IDM-04 injection follows the exact same structure as the existing security and responses injections:
```python
def _customize_openapi() -> dict[str, Any]:
    if app.openapi_schema:
        return app.openapi_schema
    schema: dict[str, Any] = get_openapi(
        title=app.title, version=app.version, description=app.description,
        routes=app.routes, tags=app.openapi_tags, servers=app.servers,
    )
    # Inject securitySchemes (D-64-SEC-SCHEMES).
    schema.setdefault("components", {}).setdefault("securitySchemes", {}).update(SECURITY_SCHEMES)
    schema["security"] = [{"cookieAuth": [], "csrfHeader": []}]
    # Inject shared error response objects.
    schema["components"].setdefault("responses", {}).update(OPENAPI_ERROR_RESPONSES)
    # Per-operation walk: (a) opt out public endpoints, (b) replace inline responses with $ref.
    for path_item in schema["paths"].values():
        for op in path_item.values():
            if isinstance(op, dict):
                if op.get("operationId") in PUBLIC_ENDPOINT_OPERATION_IDS:
                    op["security"] = []
                op_responses: dict[str, object] = op.get("responses", {})
                for status, component_name in STATUS_TO_COMPONENT.items():
                    if status in op_responses:
                        op_responses[status] = {"$ref": f"#/components/responses/{component_name}"}
    app.openapi_schema = schema
    return schema

app.openapi = _customize_openapi  # type: ignore[method-assign]
```

**IDM-04 injection pattern** — add to this function:

1. Add `components.parameters.IdempotencyKey` (new `setdefault` block, before the per-op walk):
```python
# Phase 66 IDM-04 — IdempotencyKey reusable parameter.
schema["components"].setdefault("parameters", {})["IdempotencyKey"] = {
    "name": "Idempotency-Key",
    "in": "header",
    "required": True,
    "description": (
        "Client-supplied idempotency token (16-128 chars, [A-Za-z0-9_:-]). "
        "The cached response is the response at time of first successful execution; "
        "retries replay it verbatim. For current resource state, use the resource's GET endpoint."
    ),
    "schema": {"type": "string", "pattern": r"^[A-Za-z0-9_:-]{16,128}$"},
}
```

2. In the per-operation walk, inject the `$ref` for every category-A operation (those whose operationId is in the category-A allowlist frozenset). The allowlist mirrors the `PUBLIC_ENDPOINT_OPERATION_IDS` frozenset discipline (D-64-SEC-APPLY, line 230):
```python
# Phase 66 IDM-04 — inject IdempotencyKey parameter $ref for category-A ops.
if op.get("operationId") in CATEGORY_A_OPERATION_IDS:
    op.setdefault("parameters", []).append(
        {"$ref": "#/components/parameters/IdempotencyKey"}
    )
```

**Note:** The frozenset literal `CATEGORY_A_OPERATION_IDS` must be declared at module level alongside `PUBLIC_ENDPOINT_OPERATION_IDS` (line 230) and `STATUS_TO_COMPONENT` (line 249). Its contents are determined by the IDM-01 audit (plan 66-01) and the IDM-07 wiring list (plan 66-03). The planner should declare it empty initially and populate after the audit completes.

**Pattern lockstep constraint (IDM-02):** The `schema.pattern` value `r"^[A-Za-z0-9_:-]{16,128}$"` MUST match `IDEMPOTENCY_KEY_PATTERN` in `idempotency.py` exactly. A divergence here breaks the spec-vs-runtime contract.

---

### `.planning/handoff/v1.11-idempotency-audit.md` (documentation)

**Analog:** `.planning/phases/64-contract-freeze-openapi-curation/64-CONTEXT.md` audit tables for reference structure; no direct code analog.

**Required columns per D-66-CLASSIFY-RUBRIC:**
```markdown
| endpoint | method | classification | emits-audit-event? | DB-unique-guarded? | rationale |
```

**Classification values:** A (enforce Idempotency-Key), B (exempt), C (inconsistent → IDM-07 target).

---

### `apps/backend/tests/integration/{module}/test_idempotency_*.py` (tests)

**Analog:** `apps/backend/tests/integration/payments/test_idempotency.py` — exact structural pattern for double-submit tests.

**Test file structure** (from `tests/integration/payments/test_idempotency.py`):
```python
"""Integration tests for [endpoint] Idempotency-Key contract.

Phase 66 IDM-03 — double-submit tests. Verifies:
  - missing header → 422 idempotency_key_required
  - invalid format → 422 idempotency_key_invalid_format
  - first call → 201/200 with envelope
  - replay (same key, same body) → byte-identical cached envelope
  - replay (same key, different body) → 422 idempotency_key_reuse +
    only ONE row persisted (no second mutation)
  - [IDM-06] AppError path → replay returns same error, NOT idempotency_in_flight
  - [IDM-06] rollback path → fresh retry allowed (no idempotency_in_flight lockout)
"""

from __future__ import annotations
from uuid import uuid4
from httpx import AsyncClient

async def test_replay_returns_cached_envelope(authed_client_owner: AsyncClient) -> None:
    key = uuid4().hex
    body_json = {...}
    headers = {"X-CSRF-Token": _csrf_header(authed_client_owner), "Idempotency-Key": key}

    r1 = await authed_client_owner.post("/api/v1/...", json=body_json, headers=headers)
    assert r1.status_code == 201, r1.text

    r2 = await authed_client_owner.post("/api/v1/...", json=body_json, headers=headers)
    assert r2.status_code == 201, r2.text
    assert r2.content == r1.content  # byte-identical replay
```

**No-re-emit-audit assertion pattern (IDM-03):**
```python
# Import the audit model for the relevant domain
from sqlalchemy import select
from app.modules.audit.models import AuditEvent  # or domain-specific audit table

# Assert after replay that the audit count is still 1
rows = (await db_session.execute(
    select(AuditEvent).where(AuditEvent.subject_id == membership_id)
)).scalars().all()
assert len(rows) == 1  # replay did NOT write a second audit row
```

**Fixture chain (from `tests/conftest.py:109-140`):**
```python
# Fixtures to use in IDM-03 tests:
# - async_client / authed_client_owner — ASGITransport + real Redis (app.state.redis)
# - db_session — SAVEPOINT-wrapped Postgres session (clean per test)
# Both are already declared in tests/conftest.py and domain conftest.py files.
# Redis is real (app.state.redis, not a mock) — the SET NX / GET calls hit the
# same process-singleton client the route handler uses.
```

**IDM-06 rollback-path test structure:**
```python
async def test_db_rollback_allows_retry(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unknown exception (DB rollback) → placeholder deleted → fresh retry succeeds."""
    key = uuid4().hex
    headers = {"X-CSRF-Token": ..., "Idempotency-Key": key}

    # Patch service to raise on first call, succeed on second.
    call_count = 0
    original_fn = service.create_x
    async def _patched(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RuntimeError("simulated DB error")
        return await original_fn(*args, **kwargs)
    monkeypatch.setattr(service, "create_x", _patched)

    r1 = await authed_client_owner.post("/api/v1/...", json=body_json, headers=headers)
    assert r1.status_code == 500  # first call fails

    r2 = await authed_client_owner.post("/api/v1/...", json=body_json, headers=headers)
    assert r2.status_code != 409  # NOT idempotency_in_flight — placeholder was deleted
    # r2.status_code is 201 if second call succeeds
```

---

## Shared Patterns

### RBAC-04 dependency ordering (locked)
**Source:** `apps/backend/app/modules/pt_packages/router.py:15-16` doc + `pt_sessions/router.py:96-98` doc
**Apply to:** All route handler signatures with `verify_idempotency`
```python
# Invariant enforced by tests/integration/test_route_introspection.py
# MUST appear in this order in every mutation endpoint signature:
actor: Annotated[CurrentUser, Depends(require_permission(...))]
_csrf: Annotated[None, Depends(verify_csrf)]
idempotency_key: Annotated[str, Depends(verify_idempotency)]
redis: Annotated[Redis, Depends(get_redis)]   # FastAPI deduplicates — no extra DB hit
session: Annotated[AsyncSession, Depends(get_db)]
```

### Verbatim replay response (locked)
**Source:** `apps/backend/app/modules/pt_packages/router.py:265-269`, `pt_sessions/router.py:126-130`
**Apply to:** All orchestrator replay paths
```python
return Response(
    content=base64.b64decode(stored["body_b64"]),
    status_code=stored["status_code"],
    media_type="application/json",
)
```

### Response body serialization (locked)
**Source:** `apps/backend/app/modules/pt_packages/router.py:276-281`
**Apply to:** All orchestrator success-store paths
```python
body_bytes = json.dumps(
    response_envelope.model_dump(mode="json", by_alias=True),
    separators=(",", ":"),
    ensure_ascii=False,
).encode("utf-8")
```

### AppError envelope shape (IDM-06 error store)
**Source:** `apps/backend/app/core/exceptions.py:441-450`
**Apply to:** IDM-06 exception-aware orchestrator AppError branch
```python
# Serialize for storage before re-raising:
error_body = json.dumps(
    {"code": exc.code, "message": exc.message, "fields": exc.fields},
    separators=(",", ":"),
    ensure_ascii=False,
).encode("utf-8")
await store_idempotency_response(redis, key, status_code=exc.status_code, body_bytes=error_body)
```

### OpenAPI post-processor injection pattern
**Source:** `apps/backend/app/main.py:615-638`
**Apply to:** IDM-04 `components.parameters` injection and per-operation `$ref` injection
```python
# Components injection — before the per-operation walk:
schema["components"].setdefault("parameters", {}).update(IDEMPOTENCY_PARAMETER)

# Per-operation injection — inside the `for op in path_item.values()` walk:
if op.get("operationId") in CATEGORY_A_OPERATION_IDS:
    op.setdefault("parameters", []).append(
        {"$ref": "#/components/parameters/IdempotencyKey"}
    )
```

### Frozenset-as-lock (explicit allowlist discipline)
**Source:** `apps/backend/app/main.py:230-243` (`PUBLIC_ENDPOINT_OPERATION_IDS`)
**Apply to:** `CATEGORY_A_OPERATION_IDS` declaration in `main.py`
```python
# Frozenset literal so additions are visible in diff (mirrors OWNER_ONLY
# discipline at app/core/permissions.py and LOCKED_AUDIT_EVENTS at app/core/audit.py).
CATEGORY_A_OPERATION_IDS: frozenset[str] = frozenset(
    {
        # Populated after IDM-01 audit (plan 66-01).
        # e.g. "create_membership", "freeze_membership", "create_pt_package", ...
    }
)
```

### ЮKassa webhook exclusion comment
**Source:** `apps/backend/app/api/v1/_internal/yookassa/router.py:53-58` (separate dedup namespace)
**Apply to:** IDM-07 — add inline comment at the yookassa webhook handler
```python
# IDM-07: This endpoint is NOT wired to verify_idempotency. It uses a separate
# Redis dedup path on WEBHOOK_DEDUP_KEY_PREFIX ("cc:yookassa:webhook:") with
# 86400s TTL — independent of the operator-facing cc:idem: namespace. There is
# no current_user to scope to (IP-authenticated transport callback). D-11-IDM-WEBHOOK.
```

---

## No Analog Found

No files in this phase lack an analog. All patterns have concrete existing implementations to copy from.

---

## Metadata

**Analog search scope:** `apps/backend/app/core/`, `apps/backend/app/modules/`, `apps/backend/app/main.py`, `apps/backend/tests/integration/payments/`
**Files read:** 10 source files
**Pattern extraction date:** 2026-05-29
