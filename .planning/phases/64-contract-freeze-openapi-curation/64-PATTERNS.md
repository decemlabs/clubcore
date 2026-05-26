# Phase 64: Contract Freeze — OpenAPI Curation — Pattern Map

**Mapped:** 2026-05-26
**Files analyzed:** 8 (3 CREATE, 5 MODIFY + 2 regen artifacts)
**Analogs found:** 8 / 8 (all files have strong in-tree analogs)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `apps/backend/app/core/openapi_responses.py` | core-utility (literal-registry module) | static-config | `apps/backend/app/core/audit.py` §`LOCKED_AUDIT_EVENTS` (lines 263-…); `apps/backend/app/core/exceptions.py` (envelope shape) | exact (role-match + envelope-source-of-truth) |
| `redocly.yaml` (repo root) | infra-config (lint config) | static-config | `apps/backend/pyproject.toml` ruff/mypy/import-linter blocks; `pnpm-workspace.yaml` (root-level tool convention) | role-match (no prior YAML lint config in tree — closest is the multi-tool pyproject) |
| `packages/api-client/CHANGELOG.md` | docs | static | `packages/api-client/README.md` (workspace package docs) | role-match (new file; no CHANGELOG precedent in tree) |
| `apps/backend/app/main.py:183-189` (constructor edits) | composition-root | request-response (setup-time) | self — same constructor block | exact (in-place edit) |
| `apps/backend/app/main.py` (post-processor + allowlist after router include) | composition-root | static-config + setup-time mutation | `app/main.py:204-310` existing register_* idempotent slot block; `app/core/permissions.py:63` `OWNER_ONLY` frozenset literal pattern; `app/core/audit.py:263` `LOCKED_AUDIT_EVENTS` frozenset pattern | exact (extends the same composition-root file) |
| `apps/backend/app/modules/*/router.py` (×16 router files; +2 `_internal` routers) | router | request-response | `apps/backend/app/api/v1/router.py:48-113` (current `tags=[...]` on `include_router` — the source-of-truth being migrated) | exact (current pattern lives at the aggregator; FRZ-03 moves it onto the routers themselves) |
| `.github/workflows/ci.yml` (new `redocly-lint` job + drift-gate one-liner) | ci-workflow | static-config | `.github/workflows/ci.yml:19-64` (existing `backend` job) and `.github/workflows/ci.yml:66-117` (existing `frontend` job — has the second drift-gate this phase mirrors) | exact |
| `apps/backend/openapi.json`, `packages/api-client/src/schema.d.ts` | generated-artifact | static (byte-stable JSON / TS) | `apps/backend/scripts/export_openapi.py` (exporter) | exact (regen driver unchanged) |
| `.planning/REQUIREMENTS.md` line 35 (FRZ-08 path fix) | docs | static | self | exact (one-line edit) |

---

## Pattern Assignments

### 1. `apps/backend/app/core/openapi_responses.py` (core-utility — new module)

**Analogs:**
- **Frozenset-as-lock pattern** → `apps/backend/app/core/audit.py:263-…` (`LOCKED_AUDIT_EVENTS`)
- **Envelope shape (source-of-truth for the 6 response payloads)** → `apps/backend/app/core/exceptions.py:437-449` (`_app_error_handler`)

**Envelope shape to mirror** (`apps/backend/app/core/exceptions.py:440-449`):
```python
return JSONResponse(
    status_code=exc.status_code,
    content={
        "code": exc.code,
        "message": exc.message,
        "fields": exc.fields,
    },
)
```
The 6 `components.responses` objects MUST schematize `{code: string, message: string, fields: object | null}` — same three keys, same nullability for `fields`.

**Code-mapping registry** (drawn from `exceptions.py` AppError subclasses — `code` literal is what the spec describes):
| Status | `code` source | Example class |
|--------|---------------|---------------|
| 401 | `invalid_token` / `invalid_credentials` / `invalid_session` | `InvalidAccessToken` (line 79), `InvalidPassword` (line 86), `InvalidSession` (line 100) |
| 403 | `forbidden` / `csrf_mismatch` | `ForbiddenError` (line 24), `CsrfMismatch` (line 29) |
| 404 | `not_found` (subclass-specific) | `NotFoundError` (line 19), `ClientNotFoundError` (line 120) |
| 409 | `conflict` (subclass-specific) | `ConflictError` (line 43), `PhoneExistsError` (line 127) |
| 422 | `validation_error` | `ValidationAppError` (line 48) |
| 429 | `rate_limited` | `RateLimited` (line 113) |

**Locked-registry idiom to copy** (`apps/backend/app/core/audit.py:263-269`):
```python
LOCKED_AUDIT_EVENTS: frozenset[tuple[str, str]] = frozenset(
    {
        # v1.1 (Phase 5/6/7/8) — pairs verified against actual callsites in
        # apps/backend/app/**/*.py (NOT just the docstring; planner action item
        # per Phase 15 PATTERNS.md). Drift from the original docstring resolved
        # in favour of the runtime callsite (the actual emitter wins).
        ("login_success", "session"),
        ...
```
Apply: declare the 6 response objects either as a `dict[str, dict[str, object]]` `OPENAPI_ERROR_RESPONSES` mapping (key = component name `"Unauthorized"|"Forbidden"|...`) OR as 6 module-level `dict` constants. Either is fine; mirror the comment discipline (each entry annotated with the AppError class it represents).

---

### 2. `apps/backend/app/main.py:183-189` — FastAPI constructor edits (Plan 64-01 + 64-02 + 64-03)

**Analog:** self — current block:
```python
app = FastAPI(
    title="Sportzal API",                       # FRZ-01 → "clubcore API"
    version="1.1.0",                            # FRZ-01 → "1.11.0"
    lifespan=combined_lifespan,
    docs_url="/docs" if settings.environment == "dev" else None,
    redoc_url=None,
)
```

**Edits:**
- `title="clubcore API"`, `version="1.11.0"`, populate `description=` (engineering-targeted multiline string per `<specifics>` in CONTEXT.md).
- Add `servers=[{"url": "http://localhost:8000", "description": "Local dev"}]` (single entry per D-64-NO-SERVER-LIST-EXPANSION).
- Add `openapi_tags=[...]` (the 10-domain ordered list from D-64-TAG-ORDER + `Internal` last).
- Add `generate_unique_id_function=custom_unique_id` where `custom_unique_id` is a top-level function: `def custom_unique_id(route: APIRoute) -> str: return re.sub(r'_api_v1_.*', '', route.name)` (D-64-OPID-HOOK — final regex confirmed against the live operation-ID corpus by the executor; D-64-OPID-COLLISION fallback documented in plan if collisions arise).

---

### 3. `apps/backend/app/main.py` — Post-processor + public-endpoint allowlist (Plan 64-04 + 64-05)

**Analogs:**
- **Idempotent slot/registration after router includes** → `app/main.py:204-340` (16 `register_*` calls).
- **Frozenset allowlist literal** → `app/core/permissions.py:63-89` (`OWNER_ONLY`).
- **Lazy app.state closure pattern** → `app/main.py:309` (`set_auth_redis_factory(lambda: app.state.redis)`) and `app/main.py:330-333` (`_yookassa_client_provider` closure).

**Idempotent-registration pattern to mirror** (`app/main.py:204-212`):
```python
# D-15: composition root fills the Phase 4 loader slot. This is the ONLY
# place where app.main reaches into app.modules.*. The importlinter
# contract scopes source_modules=app.core, so app.main is intentionally
# outside the scope.
#
# WR-05 (Phase 9 review): register_user_loader is idempotent by design —
# see app/core/dependencies.py:54-61. Re-registering replaces the slot,
# which is intentional so tests can inject a stub loader through
# create_app(). [...]
register_user_loader(load_user_by_id)
```
Use the same comment discipline (cite the D-64 decision IDs) when wiring the OpenAPI post-processor.

**Frozenset-allowlist literal to mirror** (`app/core/permissions.py:63-72`):
```python
# Verbatim mirror of apps/admin-web/src/shared/session/can.ts (40 entries after Phase 58 INFRA-15).
# frozenset for set-membership lookup in can() and parity-set equality in Phase 6.
OWNER_ONLY: frozenset[tuple[Action, Resource]] = frozenset(
    {
        (Action.VIEW, Resource.FINANCE),
        (Action.VIEW, Resource.REPORTS),
        (Action.VIEW, Resource.PAYROLL),
        ...
```
Apply to the public-endpoint allowlist (D-64-SEC-APPLY):
```python
# Phase 64 FRZ-05 / D-64-SEC-APPLY — public endpoints opted out of the
# global security=[{cookieAuth, csrfHeader}] default. Frozenset literal so
# additions are visible in diff (mirrors OWNER_ONLY discipline at
# app/core/permissions.py:63).
PUBLIC_ENDPOINT_OPERATION_IDS: frozenset[str] = frozenset(
    {
        "healthz",
        "login",
        "request_password_reset",
        "confirm_password_reset",
        "request_otp",
        "verify_otp",
        # ... telegram + _internal/* identifiers
    }
)
```
(Exact identifier list is post-FRZ-02 operation IDs; executor enumerates by grepping for routes without `Depends(get_current_user)` / `Depends(require_*)`.)

**Post-processor install site:** AFTER `app.include_router(api)` at `app/main.py:371`. Pattern:
```python
def _customize_openapi() -> dict[str, Any]:
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(
        title=app.title, version=app.version,
        description=app.description, routes=app.routes,
        tags=app.openapi_tags, servers=app.servers,
    )
    # Inject components.responses (D-64-RESPONSES-APPLY)
    schema.setdefault("components", {}).setdefault("responses", {}).update(
        OPENAPI_ERROR_RESPONSES,
    )
    # Inject components.securitySchemes + global security (D-64-SEC-SCHEMES + SEC-APPLY)
    schema["components"].setdefault("securitySchemes", {}).update(SECURITY_SCHEMES)
    schema["security"] = [{"cookieAuth": [], "csrfHeader": []}]
    # Per-operation $ref migration for {401,403,404,409,422,429}
    # + per-operation security=[] override for PUBLIC_ENDPOINT_OPERATION_IDS
    for path_item in schema["paths"].values():
        for op in path_item.values():
            if isinstance(op, dict):
                # ... mutate op["responses"] + op["security"]
                pass
    app.openapi_schema = schema
    return schema

app.openapi = _customize_openapi  # type: ignore[method-assign]
```
**Byte-stability gate (D-64-BYTE-STABLE):** the post-processor MUST produce identical output across cold/warm `create_app()` calls — the exporter at `scripts/export_openapi.py:60` already runs `json.dumps(..., sort_keys=True)`, which collapses Python dict-iteration nondeterminism. The post-processor only needs to avoid order-sensitive list mutations.

---

### 4. `apps/backend/app/modules/*/router.py` — Explicit `tags=[...]` (Plan 64-03 / FRZ-03)

**Analog:** `apps/backend/app/api/v1/router.py:48-113` — the aggregator currently passes `tags=[...]` at `include_router` time:
```python
v1.include_router(auth_router, prefix="/auth", tags=["auth"])
v1.include_router(clients_router, prefix="/clients", tags=["clients"])
v1.include_router(plans_router, prefix="/membership-plans", tags=["membership-plans"])
v1.include_router(memberships_router, prefix="/memberships", tags=["memberships"])
v1.include_router(
    online_payments_router, prefix="/online-payments", tags=["online-payments"],
)
v1.include_router(payments_router, prefix="/payments", tags=["payments"])
...
v1.include_router(audit_log_router, prefix="/audit-log", tags=["audit-log"])
v1.include_router(
    email_webhook_router, prefix="/_internal/email", tags=["_internal"],
)
v1.include_router(
    yookassa_webhook_router, prefix="/_internal/yookassa", tags=["_internal"],
)
```

**Current router-construction style** (all 23 router files follow this — `apps/backend/app/modules/clients/router.py:49`):
```python
router = APIRouter()
```
**FRZ-03 edit:** change to:
```python
router = APIRouter(tags=["Clients"])
```
**Tag-name mapping** (kebab-on-wire → PascalCase domain label per D-64-TAG-ORDER):
| Current `tags=[...]` (aggregator) | Phase 64 router tag | Routers affected |
|----|----|----|
| `["auth"]` | `["Auth"]` | `auth/router.py` |
| `["clients"]` | `["Clients"]` | `clients/router.py` |
| `["membership-plans"]` + `["memberships"]` | `["Memberships"]` | `memberships/router.py` (both `router` + `memberships_router`) |
| `["visits"]` | `["Visits"]` | `visits/router.py` |
| `["schedule"]` | `["Schedule"]` | `schedule/router.py` (×3: `schedule_router`, `recurring_templates_router`, `time_off_router`) |
| `["bookings"]` | `["Bookings"]` | `bookings/router.py` (×2) |
| `["trainers"]` | `["Trainers"]` | `trainers/router.py` |
| `["payments"]` + `["online-payments"]` + `["pt-package-plans"]` + `["pt-packages"]` + `["pt-sessions"]` + `["payroll"]` | `["Payments"]` | `payments/`, `online_payments/`, `pt_packages/` (×2), `pt_sessions/` (×2), `payroll/` (×1) |
| `["reports"]` | `["Reports"]` | `reports/router.py` (×1 — `router`) |
| `["audit-log"]` | `["Audit-log"]` | `reports/router.py` (`audit_log_router`) |
| `["_internal"]` | `["Internal"]` | `_internal/email/router.py`, `_internal/yookassa/router.py` |
| n/a (users not in 10-domain list) | `["Users"]` (carve under Auth? — executor confirms; CONTEXT.md does not name Users explicitly but listing exists at `app/modules/users/router.py`) | `users/router.py` |

**Coupling note:** When routers declare `tags=[...]` themselves, the `tags=[...]` kwarg on each `v1.include_router(...)` call in `app/api/v1/router.py:48-113` becomes redundant. Per FastAPI semantics, the router-level tags are union'd with the include-level tags — this DOUBLES tags in the spec. Plan 64-03 MUST either (a) drop the `tags=` kwargs from `app/api/v1/router.py` simultaneously, or (b) verify FastAPI dedups identical tags. Executor confirms behavior against installed FastAPI 0.115+.

---

### 5. `.github/workflows/ci.yml` — 7th gate `redocly-lint` + drift-gate extension

**Analog (top-level job shape):** `.github/workflows/ci.yml:19-64` (existing `backend` job).
```yaml
backend:
  name: Backend (drift gates + statics)
  runs-on: ubuntu-latest
  defaults:
    run:
      working-directory: apps/backend
  steps:
    - name: Checkout
      uses: actions/checkout@v4
    ...
```

**Analog (drift-gate step to extend):** `.github/workflows/ci.yml:60-64`:
```yaml
- name: Drift gate — apps/backend/openapi.json
  working-directory: ${{ github.workspace }}
  run: |
    git ls-files --error-unmatch apps/backend/openapi.json
    git diff --exit-code apps/backend/openapi.json
```
**Analog (second drift-gate template — already exists for `schema.d.ts` in the `frontend` job):** `.github/workflows/ci.yml:114-117`:
```yaml
- name: Drift gate — packages/api-client/src/schema.d.ts
  run: |
    git ls-files --error-unmatch packages/api-client/src/schema.d.ts
    git diff --exit-code packages/api-client/src/schema.d.ts
```
So the D-64-PATH-FIX one-liner from the closure plan is ALREADY in the workflow under the `frontend` job — confirm during planning whether plan 64-07 still needs to add it (CONTEXT.md says "adding a second drift check on `packages/api-client/src/schema.d.ts` is in-scope" but the file already has it). Plan 64-07 should reconcile this discrepancy in its scope-narrowing step.

**New `redocly-lint` job to add** (mirrors `backend`/`frontend` shape):
```yaml
redocly-lint:
  name: Redocly lint (openapi.json)
  runs-on: ubuntu-latest
  steps:
    - name: Checkout
      uses: actions/checkout@v4
    - name: Set up Node 20
      uses: actions/setup-node@v4
      with:
        node-version: "20"
    - name: Redocly lint
      run: npx -y @redocly/cli@latest lint apps/backend/openapi.json
```
Pinning decision per D-64-REDOCLY-CI-PLACEMENT: `@latest` is acceptable but executor MAY pin to an exact version (e.g. `@redocly/cli@1.34.4`) for byte-stable CI — pick at plan time and document in 64-06 plan.

---

### 6. `redocly.yaml` (repo root) — Redocly lint config (Plan 64-06 / FRZ-07)

**Analog:** No prior Redocly config in the tree. Closest convention is the repo-root tool config pattern: `pnpm-workspace.yaml` at root, `apps/backend/pyproject.toml` with `[tool.ruff]`/`[tool.mypy]`/`[tool.importlinter]` blocks.

**Shape (per D-64-REDOCLY-RULESET):**
```yaml
# Redocly CLI lint config (Phase 64 FRZ-07 / D-64-REDOCLY-RULESET).
# Targets apps/backend/openapi.json — the curated single-source-of-truth
# spec. Wired as the 7th CI gate in .github/workflows/ci.yml (job
# `redocly-lint`). Not used by any other tooling.

extends:
  - recommended

# Each `off` MUST be annotated with the trade-off reason (D-64-REDOCLY-RULESET).
rules:
  # (example — only add if the executor's first lint run flags issues that
  # are out of v1.11 scope per D-64-NO-EXAMPLES)
  # operation-4xx-response: warn   # do not require 4xx on every op; covered by components.responses migration
```
**Cwd:** Per D-64 "Claude's Discretion" — root is recommended (repo-wide tool config convention). Executor MAY relocate to `apps/backend/` if Redocly CLI has strong cwd opinions; document the decision in the plan.

---

### 7. `packages/api-client/CHANGELOG.md` — Keep-a-Changelog (Plan 64-07 / D-64-CHANGELOG-NEW)

**Analog:** No prior CHANGELOG in tree. Closest convention is the existing `packages/api-client/README.md` (workspace package docs).

**Shape (Keep-a-Changelog v1.1; first entry):**
```markdown
# Changelog

All notable changes to `@clubcore/api-client` are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased] — 2026-05-26 — v1.11.0 Contract Freeze

### Added
- FRZ-01: `info.title="clubcore API"`, `info.version="1.11.0"`, populated `info.description`; `servers=[{url:"http://localhost:8000", description:"Local dev"}]`.
- FRZ-02: All 102+ operation IDs cleaned via `generate_unique_id_function` suffix-strip (D-11-OPID).
- FRZ-03: Explicit `openapi_tags` ordering 10 business domains (Auth → Audit-log) + `Internal` last; every router declares `tags=[...]` explicitly.
- FRZ-04: Complete `info{}` metadata under clubcore name.
- FRZ-05: `securitySchemes` — `cookieAuth` (cc_access) + `csrfHeader` (X-CSRF-Token); `sportzal_csrf` cookie carry-over documented per D-11-CSRF-DEFER.
- FRZ-06: Shared `components.responses` for 401/403/404/409/422/429 envelopes; `$ref` migration at usage sites.
- FRZ-07: Redocly lint added as 7th CI gate.
- FRZ-08: Pre-freeze baseline captured; `contract-freeze-v1.11.0` annotated tag.

### Notes
- `sportzal_csrf` cookie name retained in v1.11 per D-11-CSRF-DEFER; rename to `clubcore_csrf` scheduled for v2.0 with coordinated admin-web cutover.
- Doc-site is private per D-11-DOCS-PRIVATE; no public publish path.
```

---

### 8. `apps/backend/openapi.json` + `packages/api-client/src/schema.d.ts` — Regen artifacts

**Analog:** `apps/backend/scripts/export_openapi.py` — already byte-stable. **Drift-gate command** (per-plan D-64-BYTE-STABLE):
```bash
cd apps/backend && uv run python -m scripts.export_openapi && \
  cd $REPO_ROOT && pnpm --filter @clubcore/api-client codegen && \
  git diff --exit-code apps/backend/openapi.json packages/api-client/src/schema.d.ts
```

**Critical pre-check** (`scripts/export_openapi.py:18-19`): script tolerates `.openapi()` returning a post-processed dict — there is NO assertion against `app.openapi_schema`-cache mutation. Confirmed safe for D-64-RESPONSES-APPLY post-processor strategy.

---

### 9. `.planning/REQUIREMENTS.md` line 35 — FRZ-08 path correction (Plan 64-07)

**Analog:** self. Edit per D-64-PATH-FIX:
- Replace `apps/admin-web/packages/api-client/openapi.json apps/admin-web/packages/api-client/src/generated/schema.d.ts`
- With `apps/backend/openapi.json packages/api-client/src/schema.d.ts`

---

## Shared Patterns

### Composition-root carve-out comment discipline
**Source:** `apps/backend/app/main.py:193-203` (and every subsequent `register_*` block).
**Apply to:** Every new statement added to `create_app()` in Plans 64-01, 64-02, 64-03, 64-04, 64-05. Comment must cite the FRZ-# requirement and the D-64-* decision ID (mirrors how existing code cites `D-15`, `WR-05`, `Phase 17 MEM-05`, etc.).

### Frozenset-as-runtime-lock idiom
**Sources:**
- `apps/backend/app/core/audit.py:263-…` (`LOCKED_AUDIT_EVENTS`)
- `apps/backend/app/core/audit.py:436-…` (`LOCKED_EMAIL_TEMPLATES`)
- `apps/backend/app/core/permissions.py:63-89` (`OWNER_ONLY`)

**Apply to:** `PUBLIC_ENDPOINT_OPERATION_IDS` in `app/main.py` (Plan 64-04 / D-64-SEC-APPLY). AST-gate is OPTIONAL — D-64 "Established Patterns" notes "likely deferred — security-allowlist drift is caught by the Redocly lint + drift gate combo." Do NOT introduce an AST gate in Phase 64 unless the executor flags it as cheap; defer to Phase 66 (idempotency) where similar literal-lock discipline may emerge.

### importlinter exemption for `app.main`
**Source:** `apps/backend/app/main.py:11-13` module docstring — *"app.main is exempt from core-not-depend-on-modules because that contract scopes source_modules = app.core, not app."*
**Apply to:** All Phase 64 edits in `app/main.py`. Imports from `app.modules.*` for operation-ID enumeration (if needed for the public-endpoint allowlist) are allowed in this file ONLY.

### Lazy `app.state` closure for runtime-resolved values
**Source:** `apps/backend/app/main.py:309` (`set_auth_redis_factory(lambda: app.state.redis)`) and `app/main.py:330-333` (`_yookassa_client_provider` closure).
**Apply to:** Any post-processor that needs to read settings or app-state lazily (probably NOT needed for the OpenAPI post-processor, which operates on `app.routes` after include_router, but document this pattern as available).

### Russian "carry-over" comment marker
**Source:** `apps/backend/app/core/exceptions.py:29-41` (`CsrfMismatch` references `sportzal_csrf`); `apps/backend/app/modules/auth/router.py:106-110` (`sz_refresh` cookie carry-over comments).
**Apply to:** `cookieAuth` / `csrfHeader` `description=` strings in `SECURITY_SCHEMES` (Plan 64-04). Document `sportzal_csrf` cookie name as `# v1.X carry-over` per D-11-CSRF-DEFER + the established v1.10 carry-over annotation pattern (D-64 "Established Patterns").

---

## No Analog Found

None. Every Phase 64 file has at least one strong in-tree analog.

---

## Metadata

**Analog search scope:**
- `apps/backend/app/main.py` (composition root)
- `apps/backend/app/core/*.py` (audit, exceptions, permissions, dependencies)
- `apps/backend/app/modules/*/router.py` (×16) + `apps/backend/app/api/v1/_internal/*/router.py` (×2)
- `apps/backend/app/api/router.py` + `apps/backend/app/api/v1/router.py`
- `apps/backend/scripts/export_openapi.py`
- `.github/workflows/ci.yml`
- `packages/api-client/` workspace
- Repo root layout

**Files scanned:** ~30 (focused on composition-root + router analogs + CI workflow)
**Pattern extraction date:** 2026-05-26

---

## Notes for the Planner

1. **Tag double-application risk (FRZ-03):** When routers declare `tags=[...]` themselves AND `app/api/v1/router.py:48-113` also passes `tags=[...]` on `include_router(...)`, FastAPI MAY emit duplicate tags in the spec. Plan 64-03 MUST either (a) drop the kwargs from the aggregator, or (b) confirm FastAPI dedups. Executor should add a verification step (grep the regen'd openapi.json for duplicate strings in any operation's `tags` array).

2. **Drift-gate already covers schema.d.ts:** CONTEXT.md D-64-PATH-FIX claims the second drift check is "in-scope for plan 64-07 (one-line addition to the existing drift step)" but `.github/workflows/ci.yml:114-117` already drift-gates `packages/api-client/src/schema.d.ts` inside the `frontend` job. Plan 64-07 should confirm no further CI edit is needed — only the REQUIREMENTS.md path fix.

3. **Post-processor byte-stability proof:** D-64-BYTE-STABLE requires every plan to leave `openapi.json` + `schema.d.ts` byte-stable. The exporter at `scripts/export_openapi.py:60` (`json.dumps(..., indent=2, sort_keys=True, ensure_ascii=False) + "\n"`) sorts keys at the top level, which collapses Python dict-iteration nondeterminism. The post-processor only needs to avoid order-sensitive list mutations (e.g., do not `.append()` to `tags` in an iteration order that depends on dict insertion).

4. **Users module tag:** CONTEXT.md D-64-TAG-ORDER lists 10 domains but `app/modules/users/router.py` exists (multi-user admin, Phase 43). It does NOT map to one of the 10. Executor must decide: (a) add an 11th tag `"Users"` after `"Audit-log"` and before `"Internal"`, or (b) fold under `"Auth"`. Phase 64 plan must surface this gap.

5. **operation_id collision check (FRZ-02):** D-64-OPID-COLLISION mandates verifying no collisions after suffix-strip. If two `list_*` handlers collide (e.g., `list_clients` + `list_clients` across modules), fallback per D-64-OPID-COLLISION is stripped-name + tag prefix (`clients_list`, `auth_list_sessions`). Document any collision-set in plan 64-02.
