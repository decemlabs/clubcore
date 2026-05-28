---
phase: 64-contract-freeze-openapi-curation
reviewed: 2026-05-28T00:00:00Z
depth: standard
files_reviewed: 22
files_reviewed_list:
  - apps/backend/app/main.py
  - apps/backend/app/core/openapi_responses.py
  - apps/backend/app/api/v1/router.py
  - apps/backend/app/api/v1/health.py
  - apps/backend/app/api/v1/_internal/email/router.py
  - apps/backend/app/api/v1/_internal/yookassa/router.py
  - apps/backend/app/modules/auth/router.py
  - apps/backend/app/modules/bookings/router.py
  - apps/backend/app/modules/clients/router.py
  - apps/backend/app/modules/memberships/router.py
  - apps/backend/app/modules/online_payments/router.py
  - apps/backend/app/modules/payments/router.py
  - apps/backend/app/modules/payroll/router.py
  - apps/backend/app/modules/pt_packages/router.py
  - apps/backend/app/modules/pt_sessions/router.py
  - apps/backend/app/modules/reports/router.py
  - apps/backend/app/modules/schedule/router.py
  - apps/backend/app/modules/trainers/router.py
  - apps/backend/app/modules/users/router.py
  - apps/backend/app/modules/visits/router.py
  - redocly.yaml
  - .github/workflows/ci.yml
findings:
  critical: 1
  warning: 4
  info: 2
  total: 7
status: issues_found
---

# Phase 64: Code Review Report

**Reviewed:** 2026-05-28T00:00:00Z
**Depth:** standard
**Files Reviewed:** 22
**Status:** issues_found

## Summary

Phase 64 curates the OpenAPI spec via a `_customize_openapi()` post-processor (security
schemes + global security + public opt-out + `$ref` migration of error responses), a shared
`openapi_responses.py` registry, explicit `tags=` on routers, a clean operation-ID hook, a
Redocly lint config, and a 7th CI gate. The mechanical wiring is sound and verified against the
committed `apps/backend/openapi.json`: all 10 public-endpoint opt-outs resolve to real
operations and emit `security: []`; all 96 `$ref` error-response migrations resolve with zero
dangling references; the spec is valid OAS 3.1.0 with no duplicate operation IDs; the
`anyOf [object, null]` nullability pattern is correct for 3.1.

The serious concern is **contract truthfulness** — the explicit purpose of this phase is an
"authoritative single source of truth consumed by `packages/api-client` codegen and by the
Phase 65 auth runbook." Several declarations in the curated spec do not match runtime behavior:
the advertised access-cookie name is wrong (BLOCKER), CSRF is over-declared on safe GETs, the
422 schema misrepresents FastAPI's body-validation response shape, and the operation-ID
collision documentation no longer matches the IDs the code actually produces after tags moved
onto routers.

## Critical Issues

### CR-01: `cookieAuth` security scheme advertises a non-existent cookie name (`cc_access`)

**File:** `apps/backend/app/main.py:202-212`
**Issue:** `SECURITY_SCHEMES["cookieAuth"]` declares `"name": "cc_access"` as the cookie carrying
the JWT access token. The runtime never sets or reads a cookie by that name. The issuer sets
`sz_access` (`app/core/security.py:224`) and the auth dependency reads `sz_access`
(`app/core/dependencies.py:779`). The `cc_refresh` name mentioned in the same scheme's
description is also wrong — the refresh cookie is `sz_refresh` (`app/core/security.py:235`,
read at `app/modules/auth/router.py:112`).

This is the single most consequential defect for a contract-freeze phase: the spec is the
declared source of truth for `packages/api-client` codegen and the Phase 65 auth runbook. Any
consumer or human following the frozen spec will look for / document the wrong cookie name and
the security model will be misrepresented in the authoritative artifact. Note the codebase is
internally inconsistent: the CSRF scheme correctly preserves the legacy `sportzal_csrf` name
(D-11-CSRF-DEFER) while the access/refresh cookies were renamed to `cc_*` in the spec only,
not in the code.

**Fix:** Align the scheme with the actual cookie names (the security half of the post-processor
must reflect runtime, not aspirational v2.0 names):
```python
SECURITY_SCHEMES: dict[str, dict[str, str]] = {
    "cookieAuth": {
        "type": "apiKey",
        "in": "cookie",
        "name": "sz_access",  # was cc_access — must match app/core/security.py:224
        "description": (
            "Access-token httpOnly cookie. Refresh-token cookie (sz_refresh) is "
            "server-internal flow ..."
        ),
    },
    ...
}
```
If the intent is to rename to `cc_access` at runtime, that is a coordinated cookie-rename
(mirroring the deferred `sportzal_csrf` → `clubcore_csrf` cutover) and must change
`issue_session_cookies`, `clear_session_cookies`, and the access-cookie read in
`dependencies.py` together — not the spec alone.

## Warnings

### WR-01: Global `security` over-declares `csrfHeader` on safe GET operations

**File:** `apps/backend/app/main.py:620`
**Issue:** The post-processor sets `schema["security"] = [{"cookieAuth": [], "csrfHeader": []}]`
as the global default, applied to every non-public operation including GETs. At runtime, CSRF is
only verified on mutations — `verify_csrf` is wired onto POST/PATCH/DELETE handlers, and GET
routes are explicitly CSRF-exempt (`auth/router.py:15` "`/me` does NOT declare `verify_csrf`",
`:168` "GET is CSRF-exempt"). The frozen spec therefore tells a generated client to send
`X-CSRF-Token` on safe reads (`GET /me`, `GET /sessions`, every list endpoint) where the server
neither requires nor checks it. A spec-faithful codegen client would attach a header the
contract claims is required but the server ignores.

**Fix:** Apply `csrfHeader` only to non-safe methods during the per-operation walk, e.g.:
```python
SAFE_METHODS = {"get", "head", "options"}
for path_item in schema["paths"].values():
    for method, op in path_item.items():
        if not isinstance(op, dict):
            continue
        if op.get("operationId") in PUBLIC_ENDPOINT_OPERATION_IDS:
            op["security"] = []
        elif method in SAFE_METHODS:
            op["security"] = [{"cookieAuth": []}]  # CSRF not required on safe reads
```
Keep the global default as cookie+csrf for mutations.

### WR-02: 422 `$ref` migration misrepresents FastAPI request-validation responses

**File:** `apps/backend/app/main.py:633-638` and `apps/backend/app/core/openapi_responses.py:107-128`
**Issue:** The walk rewrites every `"422"` response to `$ref: 422_ValidationError`, whose schema
is the AppError envelope `{code, message, fields}`. But there is no `RequestValidationError`
handler registered — only the `AppError` handler exists (`app/core/exceptions.py:437-449`). So
FastAPI's default request-body validation 422 returns its native `HTTPValidationError` shape
(`{detail: [{loc, msg, type}]}`), which the spec now claims is the envelope shape. Verified:
`HTTPValidationError` remains in `components.schemas` but is referenced by nothing after the
rewrite (it was the original 422 schema). The `otp_request` docstring
(`auth/router.py:398-401`) explicitly relies on FastAPI returning a body-validation 422 for an
invalid body — that 422's true wire shape is `HTTPValidationError`, not the envelope. A codegen
client deserializing a real body-validation 422 against the frozen schema would fail.

**Fix:** Either (a) register a `RequestValidationError` handler that re-shapes FastAPI's 422 into
the `{code, message, fields}` envelope so the spec becomes truthful, or (b) only migrate the
422 to the envelope `$ref` for operations whose 422 originates from `ValidationAppError` and
leave FastAPI-generated 422s pointing at `HTTPValidationError`. Option (a) is the cleaner fix and
makes the whole error surface uniform.

### WR-03: Operation-ID collision comments are stale and produce confusing cross-domain IDs

**File:** `apps/backend/app/main.py:104-115, 267-278`
**Issue:** The comments state the collision fallback derives the prefix from the path mounts
(`membership-plans` → `membership_plans_list_plans`, `pt-package-plans` →
`pt_package_plans_list_plans`). After FRZ-03 moved `tags=` onto the routers, `route.tags[0]` is
now the business tag, not the path prefix. The committed spec confirms the actual IDs are
`memberships_list_plans` / `memberships_create_plan` / `memberships_get_plan` /
`memberships_update_plan` (Memberships tag) and `payments_list_plans` / `payments_create_plan` /
`payments_get_plan` / `payments_update_plan` (the pt_packages plans router carries tag
`Payments`). So a PT-package *plan* operation is namespaced under `payments_*`, which is
misleading for codegen consumers. The documentation is now factually wrong, and the chosen IDs
couple plan operations to an unrelated domain name.

**Fix:** Update the comments to reflect tag-derived prefixes, and consider deriving the
disambiguation prefix from the path mount (stable, intention-revealing) rather than `tags[0]`:
```python
# derive from route.path_format, e.g. "/pt-package-plans/..." -> "pt_package_plans"
```
At minimum, correct the comment so future maintainers do not chase phantom IDs.

### WR-04: `custom_unique_id` strip-regex is dead code; comment overstates what FastAPI passes

**File:** `apps/backend/app/main.py:259-278`
**Issue:** `re.sub(r"_api_v1_.*", "", route.name)` operates on `route.name`, which is the
endpoint function's `__name__` (e.g. `login`, `health`) — it never contains an `_api_v1_...`
suffix. That verbose form (`login_api_v1_auth_login_post`) is what FastAPI's *default*
`generate_unique_id` builds from `route.unique_id`, not something present in `route.name`. So the
strip branch never fires; the function effectively returns `route.name` with collision-set
disambiguation. The result is correct (verified: clean IDs in the spec), but the regex and its
docstring describe behavior that does not occur, which will mislead anyone debugging operation-ID
generation.

**Fix:** Drop the no-op `re.sub` and return `route.name` directly, or document that the strip is
defensive against a non-default base behavior:
```python
def custom_unique_id(route: APIRoute) -> str:
    name = route.name  # FastAPI sets this to the handler __name__
    if name in _OPID_COLLISION_SET and route.tags:
        tag_prefix = re.sub(r"[^a-z0-9]", "_", str(route.tags[0]).lower())
        return f"{tag_prefix}_{name}"
    return name
```

## Info

### IN-01: `redocly-lint` CI job pins `@redocly/cli@latest` (non-reproducible, supply-chain surface)

**File:** `.github/workflows/ci.yml:142`
**Issue:** `npx -y @redocly/cli@latest lint ...` resolves a floating version on every run. A new
Redocly release can flip the gate red without any repo change (new default rules), and `@latest`
+ `-y` auto-installs whatever the registry serves at run time. The job comment already
acknowledges this and defers pinning. Lint-only, no runtime artifact, so low severity.

**Fix:** Pin an exact version, e.g. `npx -y @redocly/cli@1.34.4 lint apps/backend/openapi.json`,
and bump deliberately in maintenance commits.

### IN-02: `redocly-lint` validates a committed artifact it does not regenerate

**File:** `.github/workflows/ci.yml:127-142`
**Issue:** The job lints `apps/backend/openapi.json` as committed but never runs the exporter, so
it cannot catch a spec that is stale relative to source. Staleness is covered separately by the
`backend` job's drift gate (`ci.yml:60-64`), so this is acceptable as designed — noting it so the
division of responsibility between the two gates is explicit and not assumed redundant.

**Fix:** None required. Optionally add a one-line comment on the redocly job pointing at the
drift gate that guarantees freshness.

---

_Reviewed: 2026-05-28T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
