# Architecture Research

**Domain:** v1.11 API Handoff + Production Hardening — Phases 63–67
**Researched:** 2026-05-26
**Confidence:** HIGH (direct codebase inspection; all integration points verified in source)

---

## How v1.11 Integrates with the Existing Architecture

v1.11 is infrastructure-only: no new ORM entities, no new business modules, no new Protocol
slots. It touches four layers — the FastAPI app factory (`app/main.py`), the v1 router aggregator
(`app/api/v1/router.py`), individual module routers (Idempotency-Key adoption), and the handoff
tooling orbit around `scripts/` and `.planning/handoff/`. Each phase is mapped to its exact
integration points below.

---

## Phase 63: Tech-Debt Sweep

### Current State (Verified)

```
ruff check:   158 errors  (RUF100 × 42, F401 × 21, E501 × 14, F811 × 13, RUF059 × 12, ...)
ruff format:  widespread (205 files per DEFER-46-04 note)
mypy:         394 errors across 117 files — concentrated in:
              tests/integration/payroll/  (operator × 4)
              tests/integration/online_payments/  (~10 no-untyped-def)
              residual across other test + app files
```

Also in scope: `DEFER-36-04-B` (unknown; surfaced in v1.4 roadmap) and `DEFER-40-01` (v1.5
runbook `scripts/verify/run.sh` hardening — the script needed 4 hotfixes during Phase 40 UAT
and the fixes were deferred).

### Integration Points

**Files modified (no new files needed):**

- `apps/backend/app/**/*.py` — ruff auto-fixes (`--fix`) for F401, UP, I001, F541, UP017, UP037
- `apps/backend/tests/**/*.py` — mypy fixes (most are type annotations on test fixtures in
  `tests/integration/payroll/` and `tests/integration/online_payments/`)
- `apps/backend/scripts/verify/run.sh` — DEFER-40-01 runbook hardening
- `apps/backend/app/main.py` — the `title="Sportzal API"` and `version="1.1.0"` on line 184–185
  are Phase 63 tech-debt targets (should become `"clubcore API"` and `"1.11.0"`)

**Remaining sportzal shim residue** (Phase 63 sweep targets, not Phase 62.1 which was
code-identifier-only):

| File | Item | Nature |
|------|------|--------|
| `app/main.py:184` | `title="Sportzal API"` | String literal (API metadata) |
| `app/main.py:185` | `version="1.1.0"` | Version string (stale) |
| `app/core/security.py:247,287` | `key="sportzal_csrf"` | Cookie name — LOCKED (client contract) |
| `app/core/dependencies.py:914` | `cookies.get("sportzal_csrf")` | Cookie read — LOCKED |
| `app/core/actor_context.py:40` | `"sportzal_actor_context"` | ContextVar name — low priority |
| `app/integrations/yookassa/factory.py:86` | `User-Agent: "Sportzal/1.7 ..."` | HTTP header |
| `app/integrations/telegram/handlers.py:125` | Russian DM mentioning Sportzal | LOCKED copy (CLUB_BRAND) |

Note: `sportzal_csrf` cookie name is a **runtime client contract** — changing it would require
coordinated admin-web update. This is either Phase 63 (if doing a full cookie rename) or deferred
to v2.0. The sweep should change the `title=` / `version=` / User-Agent strings but leave the
cookie name decision explicit.

**CI gate impact:** Sweep produces zero CI regressions if done correctly — ruff/mypy are the
gates being fixed. The `openapi.json` drift gate WILL fire if `title=` or `version=` changes
because `export_openapi.py` regenerates the spec: the sweep PR must include the regenerated
`openapi.json` and `schema.d.ts`.

### Order of Operations

1. `ruff format` first (whitespace/formatting changes; produces the largest diff but is
   semantically inert — no logic changes)
2. `ruff check --fix` second (auto-fixable: F401 unused imports, I001 import sort, UP037
   quoted annotations, F541 f-strings, UP017 datetime.timezone.utc)
3. Manual fixes for non-auto-fixable: E501 long lines, F811 redefined-while-unused, RUF059,
   B017 assert-raises, S106 hardcoded passwords in test fixtures, DTZ011 date.today calls,
   N806 non-lowercase variable
4. `mypy app tests` — fix type annotation gaps in tests; most are `no-untyped-def` on test
   conftest fixtures

**One PR vs per-module:** One sweep PR is correct. Split PRs generate multiple intermediate states
where some files are formatted and others are not, causing ruff-format drift gate failures for the
intermediate commits. The sweep is a tree-wide pass; one atomic PR keeps the CI history clean.

**Pre-commit hooks:** Do NOT install pre-commit hooks in Phase 63. Pre-commit hooks change the
developer workflow contract and should be a deliberate opt-in decision. The existing CI gates
(`ruff check`, `ruff format --check`, `mypy`) provide the same coverage without runtime surprises.
If hooks are desired, that is a Phase 67 / v2.0 decision.

---

## Phase 64: Contract Freeze — OpenAPI Curation

### Current State (Verified)

The OpenAPI spec has **103 endpoints**. All have `operationId` values — but they are
FastAPI's **auto-generated** form: `{function_name}_api_v1_{path_fragment}_{method}`.

Examples (representative ugliness):
```
email_webhook_api_v1__internal_email_webhook_post
password_reset_confirm_endpoint_api_v1_auth_password_reset_confirm_post
list_sessions_by_pt_package_api_v1_pt_packages__pt_package_id__sessions_get
```

The spec also lacks:
- `securitySchemes` (no cookie-auth + CSRF definition in `components`)
- `servers` block (no `http://localhost:8000` dev server entry)
- `info.title` says `"Sportzal API"` (Phase 63 fixes this to `"clubcore API"`)
- `info.version` says `"1.1.0"` (should be `"1.11.0"`)
- `openapi_tags` list in `create_app()` for tag descriptions

### Integration Points

**Primary integration: `app/main.py`**

The `FastAPI(...)` constructor call currently sets only `title=` and `version=`. Phase 64 expands
this to:

```python
app = FastAPI(
    title="clubcore API",
    version="1.11.0",
    lifespan=combined_lifespan,
    docs_url="/docs" if settings.environment == "dev" else None,
    redoc_url=None,
    openapi_tags=[              # NEW: tag metadata for Redocly/Stoplight rendering
        {"name": "auth",        "description": "Authentication + session management"},
        {"name": "clients",     "description": "Client (member) CRUD"},
        {"name": "memberships", "description": "Membership plan catalog + instances"},
        {"name": "visits",      "description": "Visit check-in"},
        {"name": "schedule",    "description": "Trainer slots + recurring templates + time-off"},
        {"name": "bookings",    "description": "PT slot booking FSM"},
        {"name": "trainers",    "description": "Trainer catalog"},
        {"name": "payments",    "description": "Cash payment ledger"},
        {"name": "online-payments", "description": "ЮKassa online payments + refunds"},
        {"name": "pt-packages", "description": "PT package plans + instances"},
        {"name": "pt-sessions", "description": "PT session recording"},
        {"name": "payroll",     "description": "Trainer compensation + accrual ledger"},
        {"name": "users",       "description": "Admin user management"},
        {"name": "reports",     "description": "Aggregate reports (owner-only, read-only)"},
        {"name": "audit-log",   "description": "Audit log read API (owner-only)"},
        {"name": "_internal",   "description": "Transport-layer webhooks (not for client use)"},
    ],
)
```

**`openapi_tags` vs `tags=` on routes:** The `openapi_tags` list in `FastAPI()` provides
**descriptions** for already-existing tags. Tags are already set on every `include_router()` call
in `app/api/v1/router.py` (lines 48–113 — confirmed in source). The `openapi_tags` entries do
not change existing route tags; they attach human-readable descriptions to the tag names.

**Explicit `operation_id=` placement:**

FastAPI allows `operation_id=` on both the `@router.post(...)` decorator AND on
`include_router(..., generate_unique_id_function=...)`. The recommended pattern for this codebase
is **decorator-level `operation_id=` on the function definition**, not a centralized function.
Rationale: the generate_unique_id_function hook is called at router include time and receives only
the route; it cannot introspect the module name without fragile path parsing. Decorator-level is
explicit, co-located with the handler, and survives refactors.

**Naming convention:** Use `{module}_{verb}_{resource}` snake_case, not camelCase (RPC-style).
The existing prefix auto-generated IDs start with the function name which already follows this
pattern partially (`list_memberships`, `create_membership`, `freeze_membership`). The explicit IDs
should match the first segment (before `_api_v1_...`) of the current auto-generated IDs, stripping
the path suffix.

Example translations:
```
auto:     freeze_membership_api_v1_memberships__membership_id__freeze_post
explicit: freeze_membership

auto:     list_sessions_by_pt_package_api_v1_pt_packages__pt_package_id__sessions_get
explicit: list_pt_sessions_by_package

auto:     password_reset_confirm_endpoint_api_v1_auth_password_reset_confirm_post
explicit: auth_confirm_password_reset
```

The `endpoint` suffix in auto-generated IDs like `*_endpoint_*` is a Python function name
artifact; strip it in the explicit ID.

**Where `securitySchemes` lives:**

FastAPI does not natively render cookie-auth security schemes in the same way OpenAPI 3.0 Bearer
schemes work. The correct approach is to define a `components/securitySchemes` block via a custom
`openapi()` override method on the FastAPI app. This is done in `app/main.py` by overriding
`app.openapi` with a thin wrapper that injects the schemes after the standard spec is generated:

```python
# In create_app(), after app = FastAPI(...)
from fastapi.openapi.utils import get_openapi

def custom_openapi() -> dict:
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(
        title=app.title,
        version=app.version,
        openapi_version=app.openapi_version,
        description=app.description,
        routes=app.routes,
        tags=app.openapi_tags,
        servers=[{"url": "http://localhost:8000", "description": "Local dev"}],
    )
    schema.setdefault("components", {})
    schema["components"]["securitySchemes"] = {
        "cookieAuth": {
            "type": "apiKey",
            "in": "cookie",
            "name": "sz_access",
            "description": "HTTP-only JWT access cookie set by POST /api/v1/auth/login",
        },
        "csrfHeader": {
            "type": "apiKey",
            "in": "header",
            "name": "X-CSRF-Token",
            "description": (
                "CSRF token from the `sportzal_csrf` cookie. "
                "Required on all mutating endpoints."
            ),
        },
    }
    app.openapi_schema = schema
    return schema

app.openapi = custom_openapi  # type: ignore[method-assign]
```

This keeps all OpenAPI metadata in `app/main.py` without a separate `app/api/openapi.py` module.
One file owns the spec customization; no new module is warranted for 40 lines of override.

**Byte-stability after curation:**

The `export_openapi.py` script calls `create_app().openapi()` which is deterministic (FastAPI
caches `openapi_schema` after first call; `sort_keys=True` in `json.dumps`). After Phase 64
lands, re-running the script must produce zero git diff — the byte-stable gate still applies.
The migration strategy: one PR that adds all `operation_id=` annotations AND regenerates
`openapi.json`. Split per-module rollout is risky because the `export_openapi.py` drift gate
will fail on any intermediate commit that has some operation IDs changed but not all regenerated.
One atomic PR avoids this.

**Files modified:**

| File | Change |
|------|--------|
| `app/main.py` | `title=`, `version=`, `openapi_tags=`, `servers=`, `custom_openapi()` |
| `app/modules/auth/router.py` | Add `operation_id=` to all 17 endpoint decorators |
| `app/modules/clients/router.py` | Add `operation_id=` to 5 endpoint decorators |
| `app/modules/memberships/router.py` | Add `operation_id=` to 14 endpoint decorators |
| `app/modules/visits/router.py` | Add `operation_id=` to 4 endpoint decorators |
| `app/modules/schedule/router.py` | Add `operation_id=` to 9 endpoint decorators |
| `app/modules/bookings/router.py` | Add `operation_id=` to 4 endpoint decorators |
| `app/modules/trainers/router.py` | Add `operation_id=` to 5 endpoint decorators |
| `app/modules/payments/router.py` | Add `operation_id=` to 3 endpoint decorators |
| `app/modules/online_payments/router.py` | Add `operation_id=` to 6 endpoint decorators |
| `app/modules/pt_packages/router.py` | Add `operation_id=` to 10 endpoint decorators |
| `app/modules/pt_sessions/router.py` | Add `operation_id=` to 3 endpoint decorators |
| `app/modules/payroll/router.py` | Add `operation_id=` to 5 endpoint decorators |
| `app/modules/users/router.py` | Add `operation_id=` to 7 endpoint decorators |
| `app/modules/reports/router.py` | Add `operation_id=` to 8 endpoint decorators |
| `apps/backend/openapi.json` | Regenerated (byte-stable regen with new IDs + metadata) |
| `packages/api-client/src/schema.d.ts` | Regenerated (drift gate) |

**No new files created in Phase 64.**

---

## Phase 65: Handoff Artifacts

### Existing Precedent (Verified)

`.planning/handoff/` already contains:
- `v1.4-postman.json` — early Postman draft
- `v1.6-postman.json` — 3199-line Postman v2.1 collection (145 KB, 74 leaf items, stdlib-only
  generator script at `apps/backend/scripts/export_postman.py`)
- `v1.4-auth-runbook.md`, `v1.8-reports-runbook.md`, `v1.9-trainers-runbook.md` — operator runbooks
- `clubcore-db-rename-runbook.md` — ops runbook

The `export_postman.py` script at `apps/backend/scripts/` is a stdlib-only generator (no third-party
deps) that reads `openapi.json` and writes a filtered Postman collection (filters out `_internal`
tag). It is hardcoded to write `v1.6-postman.json` — Phase 65 updates it to write
`v1.11-clubcore.postman_collection.json`.

### Integration Points

**Postman collection:**

Path: `.planning/handoff/v1.11-clubcore.postman_collection.json`

Generated by updating `apps/backend/scripts/export_postman.py`:
- Update `TARGET` path constant (line ~37): `v1.6-postman.json` → `v1.11-clubcore.postman_collection.json`
- Update `COLLECTION_NAME` constant: `"Sportzal v1.6 — ..."` → `"clubcore API v1.11"`
- Regenerate from the Phase 64 curated `openapi.json` (103 endpoints minus `_internal` ones)

**Newman CLI smoke:**

Newman is installed as a root workspace devDependency (`pnpm add -Dw newman`). The smoke script
lives at `tools/newman/smoke.sh` (new directory). It references the Postman collection at
`.planning/handoff/v1.11-clubcore.postman_collection.json` and a Newman environment JSON at
`tools/newman/clubcore-dev.postman_environment.json`.

Trigger: **not wired into CI** for v1.11. Newman requires a live backend (Postgres + Redis +
running uvicorn). The CI backend job runs in a GitHub Actions environment without Docker Compose.
Wiring Newman into CI properly (service containers + migrations + seed data) is a v2.0 concern.
Phase 65 delivers the Newman smoke as a **local operator tool**, documented in the auth runbook.

**Auth runbook:**

Path: `.planning/handoff/clubcore-auth-runbook.md` (new file; the existing `v1.4-auth-runbook.md`
is the predecessor but stays as-is per append-only convention).

Content expands `v1.4-auth-runbook.md` to cover the full v1.11 API surface:
- Cookie-auth + CSRF flow (how `sz_access` + `sportzal_csrf` cookies work)
- Idempotency-Key semantics (from Phase 66)
- Role/RBAC overview (owner vs reception)
- Newman smoke invocation
- Docker Compose bring-up (mirrors `v1.8-reports-runbook.md` Section 1 format)

**Private OpenAPI doc-site:**

Path: `apps/backend/docs-site/` (gitignored output; generated locally on demand).

Generated by: `npx @redocly/cli build-docs apps/backend/openapi.json --output apps/backend/docs-site/index.html`

`apps/backend/docs-site/` is added to `apps/backend/.gitignore`. No CI step — the design team
runs this locally against the committed `openapi.json`. The `@redocly/cli` package is installed
as a root workspace devDependency (`pnpm add -Dw @redocly/cli`). A `make handoff` target (or
`pnpm run handoff` in root `package.json`) would chain `export_openapi → export_postman →
redocly build-docs`; whether this wrapper is implemented is a Phase 65 detail.

**Files created/modified:**

| File | Status | Notes |
|------|--------|-------|
| `.planning/handoff/v1.11-clubcore.postman_collection.json` | NEW | Generated artifact |
| `.planning/handoff/clubcore-auth-runbook.md` | NEW | Full v1.11 auth + Idempotency runbook |
| `tools/newman/smoke.sh` | NEW | Newman smoke invocation |
| `tools/newman/clubcore-dev.postman_environment.json` | NEW | Newman env (dev defaults) |
| `apps/backend/scripts/export_postman.py` | MODIFIED | Update TARGET + COLLECTION_NAME constants |
| `apps/backend/docs-site/` | NEW (gitignored) | Redocly HTML output |
| `apps/backend/.gitignore` | MODIFIED | Add `docs-site/` |
| Root `package.json` (optional) | MODIFIED | Add `handoff` script |

---

## Phase 66: Idempotency Hardening

### Current State (Verified)

`app/core/idempotency.py` **already exists** (Phase 32 D-32-18). It provides:
- `verify_idempotency` — Depends() that validates the `Idempotency-Key` header and returns a
  route-bound key `{method}:{path}:{header_value}`
- `begin_idempotency` / `store_idempotency_response` / `load_idempotency_response` — two-phase
  Redis SET NX + envelope persistence
- `idempotent_response` — composed helper (NOT yet used in any router — all existing callers use
  the manual begin/load/store pattern)
- Redis key: `cc:idem:{key}`, TTL 3600s, JSON envelope (`status_code` + `body_hash` + `body_b64`)

**Current idempotency coverage across routers (verified by AST scan):**

| Module | Has `verify_idempotency` | Endpoints covered |
|--------|--------------------------|-------------------|
| `pt_sessions` | YES | POST record, POST cancel (2 endpoints) |
| `schedule` | YES | 6 endpoints (publish, cancel, recurring template, time-off) |
| `pt_packages` | YES | 3 endpoints (create, cancel, refund) |
| `bookings` | YES | 2 endpoints (create, cancel) |
| `online_payments` | YES | 4 endpoints (sell membership redirect/QR, sell PT redirect/QR) |
| `memberships` | PARTIAL | Only POST create (sell) — cancel/freeze/unfreeze/renew/refund MISSING |
| `online_refunds` | PARTIAL | create_membership_refund_online/pt_package_refund_online MISSING |
| `clients` | NO | create, update, delete — arguably safe (natural idempotency from DB) |
| `trainers` | NO | create, update, delete — same |
| `users` | NO | all 6 mutations |
| `payroll` | NO | 3 mutations |
| `auth` | NO | login, logout, refresh, etc. — auth endpoints are deliberately exempt |
| `visits` | NO | create_visit — `UNIQUE (client_id, gym_date)` provides natural DB idempotency |

**ЮKassa webhook** uses a different Redis mechanism (`cc:yookassa:webhook:{event}:{id}` SET NX EX
86400) — this is NOT `cc:idem:*` and should NOT be unified with the client-facing idempotency flow.
The webhook dedup is IP-allowlisted transport deduplication; the client-facing Idempotency-Key is a
user-supplied retry primitive. They are separate concerns.

**ЮKassa client** (`integrations/yookassa/client.py`) uses ЮKassa's own `Idempotence-Key` header
(one `t`, not two — D-48-12) with a deterministic sha256 key generated by the `online_payments`
module. This is the outbound idempotency from our backend to ЮKassa, unrelated to the inbound
client idempotency key.

### Integration Points

**Where the dependency lives:** `app/core/idempotency.py` — **no move, no new file.** The module
is already in `app/core/` and correctly namespaced. Adding Phase 66 capabilities means adding the
`components/parameters/IdempotencyKey` OpenAPI reusable parameter definition and potentially
backfilling idempotency to endpoints identified in the audit.

**FastAPI middleware vs `Depends()` — which is idiomatic:**

`Depends()` is the correct pattern for this codebase. Reasons:
1. The existing `verify_idempotency` is already a `Depends()` dependency used on 16 endpoints.
   Changing to middleware would require touching all 16 callsites to remove the explicit dep.
2. Middleware-level idempotency requires response interception AFTER the route handler runs, which
   FastAPI's middleware model makes awkward (you'd need to buffer the full response body). The
   current `begin_idempotency / store_idempotency_response` two-phase pattern in the route handler
   is explicit and testable.
3. Middleware cannot discriminate which endpoints require idempotency; `Depends()` is opt-in per
   endpoint, which matches the business reality that not all endpoints need it (GET requests,
   auth, catalog CRUD).

**Redis key naming:** already correct — `cc:idem:{route_bound_key}` where `route_bound_key =
f"{method}:{path}:{header_value}"`. The route-binding prevents cross-endpoint replay (CR-01 from
Phase 33). No change needed.

**Audit emit semantics on replay:**

When `idempotent_response` (or the manual begin/load pattern) detects a cached response and
replays it, **the service method is never called** — the router short-circuits by returning the
cached `body_b64` as a `Response` object before the `service.*` call. This means:
- No audit row is emitted on replay (correct behavior — the original operation is the canonical event)
- No DB write occurs on replay (correct behavior — the idempotency envelope is Redis-only)
- No ARQ tasks are enqueued on replay (correct behavior)

The existing implementation already satisfies this. The router pattern is:
```python
is_first = await begin_idempotency(redis, idempotency_key)
if not is_first:
    stored = await load_idempotency_response(redis, idempotency_key)
    if isinstance(stored, str):    # "__in_flight__" placeholder
        raise ConflictError("idempotency_in_flight")
    if stored is not None:
        return Response(content=base64.b64decode(stored["body_b64"]),
                        status_code=stored["status_code"],
                        media_type="application/json")
    raise ValidationAppError("idempotency_key_reuse")
# ... run handler, store response ...
```

The service layer is only called on the `is_first == True` branch. No gating logic needed in
service; the contract is enforced at the router layer.

**Race tolerance:** Two concurrent requests with the same key — first wins (`SET NX` claims the
placeholder), second reads the placeholder and raises `409 idempotency_in_flight`. The client
retries after a short backoff and gets the cached envelope on the third attempt. This is the
existing behavior (Phase 32 D-32-20); no change in Phase 66.

**Request hashing strategy:** Current implementation hashes only the **request body bytes**
(`body_sha256` = `hashlib.sha256(body_bytes).hexdigest()`). The route binding in the key
`{method}:{path}:{header_value}` already disambiguates endpoint + actor-supplied key. There is
no need to include `actor_user_id` in the hash — two different actors using the same idempotency
key string but hitting different paths get different Redis keys due to the path segment. Adding
actor to the hash would break legitimate use cases where a retry from a refreshed session (new
cookie but same logical actor) sends the same key.

**`components/parameters/IdempotencyKey` OpenAPI reusable parameter:**

This is added in the `custom_openapi()` hook in `app/main.py` (same function that adds
`securitySchemes`). It adds to `schema["components"]["parameters"]`:

```python
schema["components"]["parameters"]["IdempotencyKey"] = {
    "name": "Idempotency-Key",
    "in": "header",
    "required": True,
    "schema": {
        "type": "string",
        "pattern": r"^[A-Za-z0-9_:-]{1,128}$",
        "description": "Client-supplied idempotency key for safe retries.",
    },
}
```

Individual endpoints that use `Depends(verify_idempotency)` get a `$ref:
"#/components/parameters/IdempotencyKey"` added to their `parameters` list. FastAPI does NOT do
this automatically from `Depends()` — the `custom_openapi()` hook must post-process the generated
schema to inject the parameter ref on the matching endpoint operation objects.

The post-processing logic in `custom_openapi()`:
```python
# Inject IdempotencyKey parameter ref on endpoints that use verify_idempotency.
# These endpoint paths are identified by scanning operationId values.
IDEMPOTENCY_OPERATION_IDS = frozenset({
    "create_membership",
    "freeze_membership",
    "unfreeze_membership",
    "cancel_membership",
    "renew_membership",
    "refund_membership",
    # ... etc (full list from Phase 64 explicit operation_id assignment)
})
for path_data in schema.get("paths", {}).values():
    for op in path_data.values():
        if isinstance(op, dict) and op.get("operationId") in IDEMPOTENCY_OPERATION_IDS:
            op.setdefault("parameters", []).append(
                {"$ref": "#/components/parameters/IdempotencyKey"}
            )
```

**Phase 66 vs Phase 64 ordering dependency:**

Phase 66 adds `components/parameters/IdempotencyKey` and backfills idempotency on several
endpoints. Both changes are reflected in `openapi.json`. Therefore:
- Phase 64 must happen before Phase 65 (Postman collection sourced from spec)
- Phase 66 changes the spec shape (adds `components/parameters`) — therefore Phase 66 must
  happen BEFORE Phase 65 is finalized, OR Phase 65 must be regenerated after Phase 66

**Recommended ordering: 63 → 64 → 66 → 65 → 67**

Phase 66 CAN run in parallel with Phase 64 code changes (adding `Depends(verify_idempotency)` to
more endpoints does not break Phase 64's `operation_id=` annotations). But Phase 65 artifact
generation should happen AFTER both 64 and 66 are merged, to ensure the Postman collection and
auth runbook reflect the final spec including the `IdempotencyKey` parameter.

**Endpoints needing idempotency backfill (Phase 66 audit results):**

High-priority (financial/state-mutating, no natural DB idempotency):
- `memberships/cancel_membership` — currently missing, has payment/FSM side effects
- `memberships/freeze_membership` — missing, FSM transition + `membership_freeze_periods` write
- `memberships/unfreeze_membership` — missing, FSM transition
- `memberships/renew_membership` — missing, creates new membership row
- `memberships/refund_membership` — missing, payment ledger write
- `online_payments/refund_membership_online` — missing, ЮKassa refund call
- `online_payments/refund_pt_package_online` — missing, ЮKassa refund call

Lower-priority (catalog CRUD — natural idempotency from DB constraints or soft-delete):
- `clients/create_client`, `update_client`, `delete_client` — UNIQUE phone/email + soft-delete
  provide natural idempotency; skip in Phase 66
- `trainers/*`, `users/*`, `payroll/*` — same rationale; skip in Phase 66
- `visits/create_visit` — `UNIQUE (client_id, gym_date)` is the natural idempotency; skip

**Files modified in Phase 66:**

| File | Change |
|------|--------|
| `app/main.py` | Extend `custom_openapi()` with `components/parameters/IdempotencyKey` + inject on matching endpoints |
| `app/modules/memberships/router.py` | Add `Depends(verify_idempotency)` + begin/load/store pattern to 5 endpoints |
| `app/modules/online_payments/router.py` | Add `Depends(verify_idempotency)` to 2 refund endpoints |
| `apps/backend/openapi.json` | Regenerated (new components/parameters, idempotency refs on more endpoints) |
| `packages/api-client/src/schema.d.ts` | Regenerated |

---

## Phase 67: Operator-Pending Runbook Execution

### Integration Points

**Evidence file:** `.planning/milestones/v1.10-OPERATOR-EVIDENCE.md`

Per D-62.1-B2 (frontmatter `convention: append-only`), v1.11 Phase 67 evidence is **appended to
the existing v1.10 file**, not scattered across per-phase files. The YAML frontmatter documents
the convention; existing RUN-08 sections are immutable.

**Pending items to execute:**

| Item | Source | What operator does |
|------|--------|--------------------|
| v1.7 VER-03 | `v1.7-yookassa-sandbox-evidence/` | Live ЮKassa sandbox payment walkthrough |
| v1.7 CARRY-01 | `.planning/handoff/v1.7-email-deliverability-evidence/` | Live RU email deliverability probe |
| v1.7 CARRY-02 | `.planning/handoff/v1.6-template-countersign.md` precedent | Owner countersign 15-template LOCKED_EMAIL_TEMPLATES |
| v1.8 VER-01 | `.planning/handoff/v1.8-reports-runbook.md` | Live `docker compose up` reports walkthrough |
| v1.9 D-61-12 | `.planning/handoff/v1.9-trainers-runbook.md` | Live trainers walkthrough |
| MailHog `--profile dev` | `apps/backend/docker-compose.yml` | Add MailHog service, capture evidence |

**MailHog integration point:**

`apps/backend/docker-compose.yml` currently has 5 services: `backend`, `telegram-bot`, `arq-worker`,
`migrate`, `postgres`, `redis`. MailHog is added as a **`--profile dev`** optional service:

```yaml
mailhog:
  image: mailhog/mailhog:v1.0.1
  ports:
    - "8025:8025"    # Web UI
    - "1025:1025"    # SMTP
  profiles:
    - dev
```

The `.env` (or `.env.example`) gains a `MAILHOG_ENABLED=true` toggle alongside an `EMAIL_SMTP_*`
override for `localhost:1025` when the `dev` profile is active. This does not affect the production
path (MailHog is `profiles: dev` gated and never starts in the default `docker compose up`).

**Files modified in Phase 67:**

| File | Change |
|------|--------|
| `.planning/milestones/v1.10-OPERATOR-EVIDENCE.md` | APPEND sections for RUN-01..06 |
| `apps/backend/docker-compose.yml` | Add MailHog service under `profiles: dev` |
| `apps/backend/.env.example` | Add MailHog SMTP override entries |

---

## Phase Build Order and Cross-Phase Dependencies

```
Phase 63 (Tech-Debt Sweep)
    └─► Phase 64 (Contract Freeze — OpenAPI Curation)
            ├─► Phase 66 (Idempotency Hardening) [can start in parallel with 64,
            │       must complete before 65 artifact generation]
            │
            └─► Phase 65 (Handoff Artifacts)
                    └─► Phase 67 (Operator-Pending Runbook Execution)
```

**Why 63 before 64:**

Phase 64 changes `openapi.json`. If ruff/mypy errors exist in the tree, the CI backend gate will
fail on the Phase 64 PR before the drift check even runs. Phase 63 sweep brings CI green first so
Phase 64 can land cleanly.

**Why 64 before 65:**

All handoff artifacts (Postman collection, auth runbook, doc-site) are sourced from the curated
`openapi.json`. Generating Postman before `operation_id=` values are stable means the collection
will have ugly auto-generated IDs. Phase 64 must be merged before Phase 65 artifact generation.

**Why 66 should complete before 65 is finalized:**

Phase 66 adds `components/parameters/IdempotencyKey` to the spec, which changes the Postman
collection shape (endpoints that require the key get a `Idempotency-Key` param pre-populated in
Postman). If Phase 65 generates the collection before Phase 66 merges, the Postman collection is
incomplete. The auth runbook also documents Idempotency-Key semantics — easier to write after
the full picture is known.

**Phase 66 parallel window:**

The code changes in Phase 66 (adding `Depends(verify_idempotency)` to memberships/online_payments
routers) do NOT depend on Phase 64 being complete — you can add `operation_id=` and
`Depends(verify_idempotency)` in the same PR if preferred. However, the `openapi.json` regen at
the end of Phase 66 must include BOTH the Phase 64 `operation_id=` changes AND the Phase 66
`IdempotencyKey` parameter additions to remain byte-stable going forward. Simplest approach:
merge Phase 64 first, then open Phase 66.

---

## Component Boundaries Summary

| Component | Phase | Status | Change Type |
|-----------|-------|--------|-------------|
| `app/main.py` | 63 + 64 + 66 | MODIFIED | `title=`, `version=`, `openapi_tags=`, `servers=`, `custom_openapi()` override with `securitySchemes` + `parameters` |
| `app/api/v1/router.py` | — | NO CHANGE | Tags already set on all `include_router()` calls |
| `app/modules/*/router.py` (15 files) | 64 | MODIFIED | Add `operation_id=` to all 103 decorators |
| `app/modules/memberships/router.py` | 66 | MODIFIED | Add `Depends(verify_idempotency)` to 5 endpoints |
| `app/modules/online_payments/router.py` | 66 | MODIFIED | Add `Depends(verify_idempotency)` to 2 endpoints |
| `app/core/idempotency.py` | — | NO CHANGE | Already correct; `idempotent_response` helper is unused but correct |
| `apps/backend/scripts/export_postman.py` | 65 | MODIFIED | Update TARGET + COLLECTION_NAME |
| `apps/backend/docker-compose.yml` | 67 | MODIFIED | Add MailHog service under `profiles: dev` |
| `.planning/handoff/v1.11-clubcore.postman_collection.json` | 65 | NEW (generated) | |
| `.planning/handoff/clubcore-auth-runbook.md` | 65 | NEW | |
| `tools/newman/smoke.sh` | 65 | NEW | |
| `tools/newman/clubcore-dev.postman_environment.json` | 65 | NEW | |
| `apps/backend/docs-site/` | 65 | NEW (gitignored) | Redocly HTML |
| `.planning/milestones/v1.10-OPERATOR-EVIDENCE.md` | 67 | APPEND-ONLY | RUN-01..06 evidence |

**No new `app.modules.*` modules. No new Protocol slots. No new ORM models. No Alembic migrations.**

---

## Data Flow Changes

v1.11 adds no new data flows. The only runtime behavior changes are:

1. More endpoints enforce idempotency (Phase 66 backfill) — same Redis `cc:idem:*` namespace,
   same TTL, same envelope shape.
2. `sportzal_csrf` cookie name is unchanged (locked runtime contract); `X-CSRF-Token` header name
   is unchanged. OpenAPI spec now documents these in `securitySchemes`.

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: Centralized generate_unique_id_function for operation_id

**What people try:** pass `generate_unique_id_function=lambda route: f"{route.tags[0]}_{route.name}"`
to `include_router()` or `FastAPI()` to avoid per-decorator `operation_id=` annotations.

**Why it's wrong here:** the function receives a `fastapi.routing.APIRoute` object. Getting the
module tag from it requires parsing `route.path` (fragile) or assuming `route.tags[0]` is always
set (not true for routes without explicit tags, or for `_internal` routes). The 15 router files
already have explicit `tags=[...]` on `include_router()` so the tags ARE available — but the
function-name segment (which needs deduplication) is still the function name anyway.

**Do this instead:** explicit `operation_id=` on each decorator. It is mechanical work (103
endpoints) but produces a stable, searchable, codebase-local identifier.

### Anti-Pattern 2: Idempotency middleware instead of Depends()

**What people try:** an ASGI middleware that intercepts POST/PATCH/DELETE requests, checks Redis
before dispatching, and intercepts the response to store it.

**Why it's wrong here:** 16 existing callsites already use `Depends(verify_idempotency)`.
Switching to middleware would require removing those 16 `Depends()` lines AND implementing
response buffering in middleware (complex). The `Depends()` pattern is already tested,
working, and consistent with the project's FastAPI idioms.

**Do this instead:** continue with `Depends(verify_idempotency)` + manual two-phase pattern.

### Anti-Pattern 3: Unifying webhook Redis dedup with client idempotency

**What people try:** consolidate `cc:yookassa:webhook:{event}:{id}` (SET NX EX 86400) and
`cc:idem:{key}` (SET NX EX 3600) into a single idempotency subsystem.

**Why it's wrong:** the webhook dedup key is constructed from ЮKassa event types and payment IDs
(opaque to the client). Its TTL is 86400s (matches ЮKassa retry window). The client-facing
idempotency key is caller-supplied, route-bound, and has a 3600s TTL. Different purposes,
different key shapes, different TTLs, different error responses (webhook returns 200 always;
client endpoints return 409). Unifying them would create a confusing abstraction over two
distinct security/reliability primitives.

**Do this instead:** leave them as separate subsystems.

### Anti-Pattern 4: Regenerating handoff artifacts before spec is frozen

**What people try:** generate Postman collection after Phase 64 but before Phase 66, then do a
"quick update" after Phase 66 as a fixup.

**Why it's wrong:** the `openapi.json` drift gate will fail if Phase 66 changes the spec but the
committed collection was generated from the pre-Phase-66 spec. Every handoff artifact is derived
from `openapi.json`; the collection, runbook, and doc-site must all be generated in one pass from
the final frozen spec.

**Do this instead:** complete Phase 64 + Phase 66, then generate all artifacts in Phase 65 from
the final `openapi.json`.

### Anti-Pattern 5: MailHog in the default docker-compose profile

**What people try:** add MailHog as a regular service (no `profiles: dev` tag) so it always
starts.

**Why it's wrong:** MailHog is a dev-only email catch-all. Production deployments (and CI) should
never start a MailHog container by default. Starting it without the `--profile dev` flag gives
operators a silent mail sink in production.

**Do this instead:** `profiles: [dev]` on the MailHog service definition. Operator evidence
captured with `docker compose --profile dev up`.

---

## Sources

- Direct codebase: `apps/backend/app/main.py` (FastAPI constructor, lifespan, composition root)
- Direct codebase: `apps/backend/app/api/v1/router.py` (all 103 endpoint mounts with tags)
- Direct codebase: `apps/backend/app/core/idempotency.py` (full idempotency subsystem)
- Direct codebase: `apps/backend/app/modules/*/router.py` (AST scan of all 15 module routers)
- Direct codebase: `apps/backend/app/api/v1/_internal/yookassa/router.py` (webhook dedup pattern)
- Direct codebase: `apps/backend/app/integrations/yookassa/client.py` (IDEMPOTENCE_KEY_HEADER)
- Direct codebase: `apps/backend/scripts/export_postman.py` (existing Postman generator)
- Direct codebase: `apps/backend/scripts/export_openapi.py` (byte-stable export)
- Direct codebase: `apps/backend/openapi.json` (103 endpoints, 0 securitySchemes, 0 parameters)
- Direct codebase: `apps/backend/.importlinter` (architectural contracts)
- Direct codebase: `apps/backend/pyproject.toml` + `ruff.toml` (tooling config)
- Direct codebase: `.github/workflows/ci.yml` (2-job CI: backend static gates + frontend drift)
- Direct codebase: `apps/backend/docker-compose.yml` (5-service stack, no MailHog)
- Direct codebase: `.planning/handoff/` (precedent for artifact placement and naming)
- Direct codebase: `.planning/milestones/v1.10-OPERATOR-EVIDENCE.md` (append-only convention)
- Direct codebase: `apps/backend/app/modules/auth/router.py` (CSRF dependency pattern)
- Ruff live run: 158 errors categorized (RUF100 × 42, F401 × 21, E501 × 14, ...)
- Mypy live run: 394 errors across 117 files

---

*Architecture research for: v1.11 API Handoff + Production Hardening (clubcore FastAPI modular monolith)*
*Researched: 2026-05-26*
