# Pitfalls Research: v1.11 API Handoff + Production Hardening

**Domain:** FastAPI modular monolith — OpenAPI curation, Postman/Newman handoff, idempotency hardening, tech-debt sweep, operator runbook execution
**Researched:** 2026-05-26
**Confidence:** HIGH — based on direct codebase inspection (`app/core/idempotency.py`, `app/integrations/yookassa/`, `apps/backend/openapi.json`, `.github/workflows/ci.yml`, `RETROSPECTIVE.md`)

---

## Critical Pitfalls

### Pitfall C-01: Auto-generated operation IDs — `_api_v1_` suffix leaks into Postman + schema.d.ts

**What goes wrong:**
All 102 of the 103 current operations use FastAPI's auto-generated operation ID format: `login_api_v1_auth_login_post`, `list_audit_log_api_v1_audit_log_get`, etc. When `openapi-to-postmanv2` consumes these, every Postman request name contains the full path slug. More critically, when the frontend codegen regenerates `schema.d.ts`, the TypeScript function name is derived from the operation ID — `listAuditLogApiV1AuditLogGet()` is the generated client function name that every admin-web callsite uses. If Phase 64 adds explicit `operation_id=` to routes, FastAPI replaces the old auto-generated ID, the Postman collection picks up clean names, but `schema.d.ts` is regenerated with different function names, breaking all existing callsite references in `apps/admin-web`.

**Why it happens:**
The instinct is to "just add clean operation IDs" during curation. The developer sees the messy auto-generated names, adds `operation_id="list_audit_log"` to the route decorator, runs `export_openapi.py`, and sees a cleaner spec. What they don't immediately notice is that `pnpm --filter @clubcore/api-client codegen` now generates `listAuditLog()` instead of `listAuditLogApiV1AuditLogGet()`, and the drift gate fires because `schema.d.ts` changed. If they commit the new `schema.d.ts`, every callsite in `apps/admin-web` that used the old function name needs updating — but since Phase 64 is a backend-only milestone with `apps/admin-web` frozen, those callsites cannot be updated.

**How to avoid:**
Two viable strategies:
1. **Keep all auto-generated operation IDs unchanged** — only add the `_api_v1_` suffix stripping via `generate_unique_id_function` in `FastAPI()` constructor (replaces the path-slug suffix while keeping the function name prefix stable). This changes ALL 102 operation IDs in one commit, which is a known drift event — do it in Phase 64's first plan with a single regen. Verify the schema.d.ts diff is clean (no actual TypeScript function name changes, only the exported string values that are used in the type-level `AssertNonNever` checks). Then run the 14 `_v19Checks` + `_v18Checks` forward guards to confirm nothing broke at the type level.
2. **Never change existing operation IDs post-codegen** — freeze the current auto-generated IDs as explicit `operation_id=` values on each route (copy the existing ID verbatim), then separately clean up naming in v2.0 when admin-web integration is done. This is the safe path for v1.11.

The safe path for this milestone: use `generate_unique_id_function` to strip the `_api_v1_{method}` suffix once (Phase 64 plan 1), regen both artifacts atomically, verify all downstream guards are green. Do not change the semantic names of operations.

**Warning signs:**
- `git diff packages/api-client/src/schema.d.ts` shows function name changes (not just whitespace or comment changes) after running `export_openapi.py`
- The drift gate in CI fires on `schema.d.ts`
- TypeScript `AssertNonNever` guard compilation errors in `apps/admin-web`

**Phase to address:** Phase 64 (Contract Freeze — OpenAPI Curation), plan 1

---

### Pitfall C-02: Idempotency cache survives DB rollback — ghost transaction on retry

**What goes wrong:**
The current `app/core/idempotency.py` flow is: (1) `begin_idempotency` — SET NX placeholder, (2) run handler — DB write, (3) `store_idempotency_response` — replace placeholder with full envelope. If step (2) raises an exception and the DB write rolls back (e.g., a unique constraint violation, a service-layer `AppError`, or an async SQLAlchemy session rollback), step (3) is never called — the Redis key stays as `__in_flight__`. On the client's next retry with the same `Idempotency-Key`, `load_idempotency_response` returns `_PLACEHOLDER`, and the code raises `ConflictError("idempotency_in_flight")`. The client is blocked indefinitely — it cannot retry, cannot get a success, cannot get the real error. The placeholder TTL is 3600s, so the user is locked out for up to 1 hour.

There is a subtler variant: if the DB write SUCCEEDS but `store_idempotency_response` fails (Redis write error), the next retry sees a missing Redis key, acquires the claim, reruns the handler, and hits a DB unique constraint — which surfaces as a 500 or a misleading 409 instead of the idempotent 200.

**Why it happens:**
The `store_idempotency_response` call is placed in the route body after `await service.create_something(...)`. If the service raises, the route never reaches the store call. The Redis placeholder is an in-flight lock, not a committed log.

**How to avoid:**
Wrap the `store_idempotency_response` call in a `try/finally` pattern or use a middleware-level response hook. The standard pattern is:

```python
result = await begin_idempotency(redis, key)
if result is False:
    ...  # replay or raise in_flight
try:
    response_data = await service.do_thing(...)
    await store_idempotency_response(redis, key, status_code=200, body_bytes=response_bytes)
except AppError as exc:
    # On known app errors, store the ERROR response in the envelope too
    # so retries get the same error, not in_flight
    error_bytes = serialize_error(exc)
    await store_idempotency_response(redis, key, status_code=exc.status_code, body_bytes=error_bytes)
    raise
```

For unknown exceptions (DB unreachable, 500), the safest recovery is to DELETE the placeholder key so the next retry can attempt fresh. Add `await redis.delete(_redis_key(key))` in the `except Exception` branch. This trades "guaranteed at-most-once" for "retry gets another chance", which is the right tradeoff for non-payment endpoints.

For payment endpoints specifically (sell, refund), the handler must be idempotent at the DB layer too (the existing `UNIQUE (membership_id, ...)` + `ON CONFLICT DO NOTHING` patterns from v1.4/v1.9 provide this).

**Warning signs:**
- Integration test: submit a request that causes a service-layer exception, then retry with the same key — verify the retry gets the original error (not `idempotency_in_flight`)
- Monitoring: Redis keys matching `cc:idem:*` with value `__in_flight__` that are older than 10 minutes

**Phase to address:** Phase 66 (Idempotency Hardening) — audit all `begin_idempotency` callsites and add exception-aware cleanup

---

### Pitfall C-03: Idempotency-Key excludes `actor_user_id` — cross-user replay attack

**What goes wrong:**
`verify_idempotency` returns `f"{method}:{path}:{header_value}"` — the key includes method, path, and the raw header string, but NOT the authenticated user. If user A sends `POST /api/v1/pt-packages` with `Idempotency-Key: abc123` and it succeeds, and user B (a different operator in the same multi-user admin) sends the same request with the same key `abc123`, user B's request hits the Redis cache and gets back user A's response (user A's PT package ID, user A's client's data). In a single-gym CRM with reception + owner roles, both roles can call the same mutating endpoints. An accidental key collision (human-chosen keys like `retry-1` or timestamp-based keys) causes one user to see another user's transaction result.

**Why it happens:**
Session context is in the HTTP-only cookie (JWT), not in the `Idempotency-Key` header. The current `verify_idempotency` dependency only has access to `request` — and extracting the actor from the JWT in a `Depends()` that runs before `get_current_user` would create a dependency ordering issue. The simpler (and subtly wrong) approach of binding only to method+path+key was chosen in D-33-16.

**How to avoid:**
Bind the idempotency key to the session by adding the actor's user ID (or session token hash) to the Redis namespace. The cleanest approach: add `actor_user_id` as a parameter to `verify_idempotency` via a dependent `Depends(get_current_user)`:

```python
async def verify_idempotency(
    request: Request,
    redis: Annotated[Redis, Depends(get_redis)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> str:
    ...
    return f"{request.method}:{request.url.path}:{current_user.id}:{key}"
```

This makes the key `{method}:{path}:{user_id}:{header_value}`, which is unique per user. Existing routes that use `Depends(verify_idempotency)` automatically get the user-scoped key because FastAPI resolves the full dependency graph.

Note: the ЮKassa webhook endpoint (`/_internal/yookassa/webhook`) uses a DIFFERENT idempotency mechanism (direct `redis.set(f"cc:yk:webhook:{event_id}", NX=True, EX=86400)`) and does NOT use `verify_idempotency`. It is not affected by this fix.

**Warning signs:**
- Multiple operator accounts exist (v1.6 shipped multi-user admin with 4 OWNER_ONLY USERS pairs) — cross-user collision risk is real, not hypothetical
- Any client-side retry logic that uses deterministic keys (timestamps, sequence numbers) rather than UUIDs

**Phase to address:** Phase 66 (Idempotency Hardening) — update `verify_idempotency` signature; verify with a test that submits the same key from two different users and confirms independent responses

---

### Pitfall C-04: OpenAPI spec title `"Sportzal API"` / version `"1.1.0"` — staleness baked into handoff artifacts

**What goes wrong:**
The current `FastAPI()` constructor in `app/main.py` has `title="Sportzal API"` and `version="1.1.0"`. The v1.10 rebrand renamed all code identifiers but left this string. When Phase 65 generates the Postman collection from `openapi.json`, the collection info block reads `"name": "Sportzal API"`. When the Redocly doc-site renders, the header says "Sportzal API 1.1.0". The handoff artifacts carry the old name.

The version `"1.1.0"` is frozen from v1.1 (Phase 5) and has not tracked the codebase milestones — it is not semantically meaningful, but it signals neglect to the design team consuming the handoff.

**Why it happens:**
Phase 62 (rebrand) focused on namespaces, Redis keys, npm packages, and env vars. The `FastAPI()` `title=` and `version=` arguments are visible in generated docs but not in any source file that grep for "sportzal" catches, because they are string literals in `app/main.py` inside a Python call expression. The HISTORICAL_NOTE explicitly marks `app/main.py` as active code — so this is a missed item, not intentionally preserved.

**How to avoid:**
Phase 64 (Contract Freeze) — update `FastAPI(title="clubcore API", version="1.11.0", ...)` as the first plan. Also update `info.description` if absent. Add `servers=[{"url": "{BASE_URL}"}]` with an env-substitutable base URL (not hardcoded localhost). After this change, run `export_openapi.py` and regen `schema.d.ts` to produce the single byte-stable event that updates both drift-gate artifacts. Verify the drift gate CI passes.

**Warning signs:**
- `grep "Sportzal API" apps/backend/openapi.json` returns a hit
- `grep "1.1.0" apps/backend/openapi.json` returns a hit under `"info"`

**Phase to address:** Phase 64, plan 1 (before generating any handoff artifacts)

---

### Pitfall C-05: `store_idempotency_response` stores state at time of first response — stale cache on status-transition retry

**What goes wrong:**
For ЮKassa payment endpoints, the sell flow creates an `online_payments` row with `status='pending'`, creates the ЮKassa payment, and returns a `SellResponse` with `payment_url`. The response is cached in Redis. Separately, the ЮKassa webhook later transitions the payment to `status='succeeded'` and activates the membership. If the client retries the sell with the same `Idempotency-Key` (e.g., because the original redirect-back URL was lost), they receive the cached `SellResponse` — which still shows `status='pending'` and the original `payment_url`. This is correct behavior for idempotency (return the original response), but it can confuse clients if they expect the retry to show the current DB state.

This is distinct from a bug — it is the correct semantics of idempotency caching. The pitfall is implementing a "smart retry" that queries the DB to check current status and returns THAT instead of the cached response. This breaks idempotency guarantees and can cause double-charges if the "current status check" has a race condition.

**Why it happens:**
The desire to show clients "up-to-date" status leads developers to add a DB lookup inside the cached response path. This is wrong: if the response was cached, replay it verbatim. If the client wants current status, they should use `GET /api/v1/.../{id}`.

**How to avoid:**
In Phase 66's idempotency audit, document explicitly: the cached response is the response at time of first successful execution. Retries get the cached response unchanged. For current status, callers must use the resource's GET endpoint. Add a note to the `components/parameters/IdempotencyKey` description in the curated OpenAPI spec.

**Warning signs:**
- Any callsite that calls `load_idempotency_response` and then queries the DB to "update" the response before returning
- A comment like "return current status instead of cached status on retry"

**Phase to address:** Phase 66 (design doc and test) + Phase 64 (OpenAPI `IdempotencyKey` parameter description)

---

### Pitfall C-06: Tech-debt sweep `ruff check --fix --unsafe-fixes` silently changes semantics

**What goes wrong:**
The standard sweep order (`ruff check --fix`) uses only safe fixes. The `--unsafe-fixes` flag additionally applies rewrites that may change behavior: replacing `type(x) is Y` comparisons, removing arguments that appear unused but satisfy a Protocol, rewriting comprehensions, changing string literal forms. The 158 ruff errors in this codebase include `RUF100` (unused `# noqa`) and `F401` (unused imports) — both auto-fixable safely. But if `--unsafe-fixes` is added to "clean up faster", `RUF059` (unused unpacked variables) and certain `UP*` upgrades can change the meaning of lines that pass mypy clean.

Specifically: the codebase uses Protocol-based cross-module wiring (`register_user_loader`, `register_active_membership_resolver`, etc.). Arguments that appear "unused" in a function body may be required by the Protocol signature. Ruff's `ARG001` (unused function argument) with `--unsafe-fixes` might strip them.

**Why it happens:**
The `--unsafe-fixes` flag appears benign when running on a test codebase. On a production codebase with 10 modules, 17 Protocol slots, and ~80 linter errors, the temptation is to use it to make the sweep go faster.

**How to avoid:**
Never use `--unsafe-fixes` in Phase 63. The sweep order is:
1. `ruff check --fix app tests` (safe fixes only)
2. `ruff format app tests`
3. Manual review of remaining errors
4. `ruff check app tests` — 0 errors or documented `# noqa: RULECODE` suppressions with inline rationale

The 158 errors break down to ~80 auto-fixable safely (RUF100, F401, I001) and ~78 manual. The manual ones mostly fall into `E501` (line length), `RUF002` (Cyrillic in docstrings), and `RUF059` (unused variables) — handle those by either fixing the line or adding a targeted `# noqa` with a comment.

**Warning signs:**
- Running `ruff check --fix --unsafe-fixes` instead of `ruff check --fix`
- Any ruff fix that touches a function signature (arguments removed)
- A Protocol slot implementation that mypy suddenly can't match after the sweep

**Phase to address:** Phase 63 (Tech-Debt Sweep) — encode the safe-only sweep order in the phase requirements

---

### Pitfall C-07: Sweep PR is a monolithic diff — single regression makes the whole sweep undebuggable

**What goes wrong:**
297 files reformatted + 80 auto-fixes + 11 mypy fixes = one enormous diff PR. If any test fails after this PR, bisecting the failure is nearly impossible because every file changed. Even if CI runs `pytest` in the sweep PR and it passes, a later PR that touches the same files may surface a latent behavior change introduced silently in the sweep.

**Why it happens:**
The natural impulse after months of accumulated debt is to do it all in one shot. "One big PR, CI green, done." The problem is that 297 reformatted files is not meaningfully reviewable, and the reviewer (or the AI agent) will miss semantic changes hiding in the format noise.

**How to avoid:**
Split the sweep into at minimum three separate commits, in this order:
1. `ruff format app tests` only (pure whitespace, zero semantic change, trivially reviewable by checking that `ruff check` passes unchanged)
2. `ruff check --fix app tests` (safe auto-fixes: RUF100, F401, I001 — reviewable because the diff is semantic but small)
3. Manual fixes for mypy errors and remaining ruff violations (reviewable line-by-line)

Each commit can be a separate plan in Phase 63. CI runs on each. If step 1 + 2 CI is green and step 3 breaks a test, the bisect surface is the manual fixes only.

**Warning signs:**
- A single plan that says "run all sweep commands and commit"
- A plan that skips CI verification between ruff format and ruff check --fix
- Mypy fix changes a SQLAlchemy model attribute type (these can have runtime effects)

**Phase to address:** Phase 63 (Tech-Debt Sweep) — encode the three-commit split in the phase plan

---

### Pitfall C-08: Newman exits 0 when test scripts fail — CI smoke gate silently passes

**What goes wrong:**
Newman runs a Postman collection against a live server. If the collection has test scripts (e.g., `pm.test("status is 200", () => pm.response.to.have.status(200))`), and those tests fail, Newman exits with code 1 by default. But if the `--bail` flag is absent and test scripts fail for non-fatal reasons, Newman may exit 0 after completing all requests. Additionally, if no test scripts are defined in the generated collection (which is the case for collections generated directly from an OpenAPI spec without manual additions), Newman runs all requests and exits 0 as long as no HTTP connection error occurs — even if every endpoint returns 500.

**Why it happens:**
The OpenAPI-generated collection contains no test scripts by default. `openapi-to-postmanv2` produces request definitions but not assertion scripts. The developer runs `newman run collection.json --environment env.json`, sees "X requests, 0 failures", assumes the smoke is clean, and CI is gated on this — but the 0 failures count only connection-level failures, not HTTP status codes.

**How to avoid:**
After generating the Postman collection in Phase 65, add test scripts to the critical endpoints (at minimum: `pm.test("status 2xx", () => pm.response.to.be.success)`). This can be done by editing the collection JSON directly or via a post-generation script. Always include `--bail` in the Newman invocation so the first assertion failure halts execution and the process exits non-zero.

Additionally, use `--reporters cli,junit` with `--reporter-junit-export` so the CI job has a parseable artifact even when Newman exits non-zero.

```bash
newman run collection.json \
  --environment env.json \
  --reporters cli,junit \
  --reporter-junit-export newman-results.xml \
  --bail
```

**Warning signs:**
- The generated collection JSON has no `"tests"` blocks in any item's `"event"` array
- Newman output shows "0 test scripts" or "0 assertions"
- Newman exits 0 after all requests on a stack where `GET /healthz` returns 200 but `POST /api/v1/auth/login` returns 500

**Phase to address:** Phase 65 (Handoff Artifacts) — add minimal test scripts to critical endpoints post-generation

---

### Pitfall C-09: Newman smoke in CI with no DB — 500s from missing Postgres

**What goes wrong:**
If Phase 65 adds a Newman smoke job to CI (`.github/workflows/ci.yml`), it needs a running Postgres + Redis + migrated DB. The current CI backend job runs ruff/mypy/pytest without Docker Compose — pytest uses `httpx.ASGITransport` with the test database fixture managed by pytest-asyncio. Newman runs against a REAL HTTP server on `localhost:8000`, which requires Docker Compose to be up. If the CI job runs `newman run collection.json` without starting the stack first, every request that touches the DB returns 500 (`asyncpg.exceptions.ConnectionDoesNotExistError`).

**Why it happens:**
The developer tests Newman locally with `docker compose up` running, confirming it works. They add the Newman step to the existing `backend:` CI job, not realizing that job has no Docker daemon / no running Postgres.

**How to avoid:**
Newman smoke is NOT a CI gate on every push — it is an operator-local smoke for Phase 67 walkthroughs. Keep it out of `.github/workflows/ci.yml` unless a dedicated CI job with `services: postgres:` + `services: redis:` is added (analogous to the pytest job setup). For v1.11, the Newman smoke runs locally: `docker compose up -d && newman run collection.json --environment env.json --bail`. Phase 67 captures evidence (terminal output, exit code) as the runbook artifact.

**Warning signs:**
- A Phase 65 plan that adds a `newman` step to the existing `backend:` CI job
- CI log showing `Error: connect ECONNREFUSED 127.0.0.1:8000`

**Phase to address:** Phase 65 (Handoff Artifacts) — scope Newman explicitly as a local operator smoke, not a CI gate

---

### Pitfall C-10: Postman collection env file committed with real credentials

**What goes wrong:**
The Postman collection environment file (`apps/backend/newman-env.json`) contains test credentials for smoke runs. If it includes a real owner email/password from the production Yandex Postbox account, or a real ЮKassa API key, those credentials are checked into the repository. `newman-env.json` would be tracked (not gitignored), since it is the intended artifact of Phase 65.

**Why it happens:**
The developer copies credentials from `.env.local` into the environment file for a quick smoke test, then commits the file without stripping the secrets. "It's just test credentials" doesn't apply if the same email/password is used for the production ЮKassa sandbox account.

**How to avoid:**
The `newman-env.json` file uses ONLY fixture credentials (e.g., `owner@fixture.local` / `ownerpass123`) that match the seeded test database. It contains zero production credentials, zero API keys, zero real email addresses. A second file `apps/backend/newman-env.local.json` (gitignored) holds operator-specific overrides for Phase 67 sandbox walkthrough.

Add `*newman-env.local.json` to `.gitignore` in Phase 65 plan 1.

**Warning signs:**
- `apps/backend/newman-env.json` contains `yookassa_api_key`, real email domains (not `.local` / `.fixture`), or passwords matching what is in `.env`
- `git diff --exit-code apps/backend/newman-env.json` shows a real SMTP password or API key

**Phase to address:** Phase 65 (Handoff Artifacts) — gitignore local override file before the committed env file is created

---

### Pitfall C-11: Operator runbook stale — env var renamed, endpoint path changed since authoring

**What goes wrong:**
Four accumulated operator-pending runbooks will be executed in Phase 67:
- `v1.7-yookassa-sandbox-evidence/` (VER-03) — authored at v1.7 close (2026-05-24)
- `v1.8-reports-runbook.md` (VER-01) — authored at v1.8 close (2026-05-24)
- `v1.9-trainers-runbook.md` (D-61-12) — authored at v1.9 close (2026-05-26)
- MailHog `--profile dev` evidence (new in v1.11)

Between authoring and Phase 67 execution, the following things changed:
- Redis namespace renamed `sz:* → cc:*` (v1.10)
- `SPORTZAL_EMAIL_FROM` env renamed to `CLUBCORE_EMAIL_FROM` (v1.10, with fallback removed in Phase 62.1)
- `CLUB_BRAND` constant extracted to `app/core/branding.py` (v1.10)

The runbooks in `.planning/handoff/` are marked immutable (per `HISTORICAL_NOTE.md` for v1.4–v1.9 runbooks). But the executable steps (curl commands, env var names, endpoint URLs) may reference old identifiers.

**Why it happens:**
Runbooks are written against the codebase state at phase close. By the time Phase 67 executes them, multiple milestones may have changed env var names, Redis key prefixes, Docker service names, or endpoint paths. The runbooks are frozen artifacts, not living documents.

**How to avoid:**
Phase 67 plan 1: before executing any runbook, perform a "staleness audit" — grep each runbook for:
- `sz:` (Redis namespace, now `cc:`)
- `SPORTZAL_EMAIL_FROM`
- `sportzal` (brand references)
- Any endpoint paths against the current `openapi.json` to confirm they still exist

Create a Phase 67 pre-flight diff document listing each runbook + its stale items + the current-state replacement. Execute each runbook with corrections applied in-situ (annotate the runbook, do not rewrite the immutable original). Capture corrected commands in the Phase 67 evidence file.

**Warning signs:**
- A curl command in a runbook containing an endpoint path — verify this path still exists in the curated OpenAPI
- Any `SPORTZAL_EMAIL_FROM` env reference in a runbook
- `docker compose` service names that may have changed

**Phase to address:** Phase 67 (Operator-Pending Runbook Execution) — plan 1 is always a staleness audit before first execute

---

### Pitfall C-12: VER-03 (ЮKassa sandbox) accidentally hits production account

**What goes wrong:**
VER-03 requires executing the ЮKassa sandbox walkthrough. The `.env` file controlling the backend has `YOOKASSA_SANDBOX=true` (expected) or `YOOKASSA_SANDBOX=false` (production). If the operator has previously set `YOOKASSA_SANDBOX=false` for a production test and forgotten to revert it, Phase 67's VER-03 sends real money-movement requests to ЮKassa production. The `YOOKASSA_TRUSTED_IPS` bypass (line 89 of `webhook_verifier.py`: `if _settings.sandbox: return`) also means the IP allowlist check is skipped in sandbox mode — this is correct for development but must be verified to be active in the evidence.

**Why it happens:**
Operator has multiple `.env` files or has a local production `.env.local` that overrides the default. The `verify_yookassa_ip` sandbox bypass is set at module import time (`_settings: Final[YooKassaSettings] = YooKassaSettings()`), so if the wrong env file is active, the bypass state is fixed for the process lifetime.

**How to avoid:**
Phase 67 VER-03 pre-flight checklist:
1. `grep YOOKASSA_SANDBOX apps/backend/.env` — must be `true`
2. `uv run python -c "from app.integrations.yookassa.settings import YooKassaSettings; s=YooKassaSettings(); print(s.sandbox)"` — must print `True`
3. The ЮKassa sandbox account and production account have DIFFERENT `YOOKASSA_SHOP_ID` values — verify the shop_id in `.env` matches the sandbox dashboard, not the production dashboard

Capture these as "preconditions verified" lines in the Phase 67 evidence file before any ЮKassa API calls are made.

**Warning signs:**
- VER-03 produces real `payment_id` values starting with `2b0` (ЮKassa production UUIDs look different from sandbox)
- Real RUB debits appearing on the test card

**Phase to address:** Phase 67 (Operator-Pending Runbook Execution) — add explicit sandbox verification step to VER-03 pre-flight

---

### Pitfall C-13: OpenAPI 3.1 `anyOf: [T, {type: null}]` — Postman and older tooling doesn't render nullable fields

**What goes wrong:**
The current `openapi.json` is OpenAPI 3.1 (FastAPI 0.115+ generates 3.1 by default). In OpenAPI 3.1, nullable fields are expressed as `anyOf: [{"type": "string"}, {"type": "null"}]`. The existing spec has 156 `anyOf`/`oneOf` usages. When `openapi-to-postmanv2 6.0.1` consumes a 3.1 spec, it handles `anyOf/null` correctly. However, some downstream tooling (older Postman GUI versions, swagger-ui, certain code generators) still expects the 3.0 `nullable: true` syntax. The current spec has exactly 1 `nullable` keyword — possibly a leftover from a 3.0 schema fragment.

For v1.11 this is LOW risk — the recommended toolchain (openapi-to-postmanv2 6.0.1, Redocly CLI 2.31.4) handles 3.1. But if the design team consuming the handoff uses an older Postman version or their own code generator, they may see broken nullable fields.

**Why it happens:**
FastAPI 0.115+ generates 3.1 by default. The `nullable: true` keyword in 3.0 does not exist in 3.1 (it's ignored or causes a validation warning). Any existing `nullable: true` in the spec is a 3.0 holdover that should be cleaned up.

**How to avoid:**
Phase 64 (Contract Freeze) — run `npx @redocly/cli lint apps/backend/openapi.json` with the recommended `redocly.yaml` config. Redocly flags OpenAPI 3.0 idioms in a 3.1 spec. The single `nullable` occurrence should be removed and replaced with `anyOf: [{type: "string"}, {type: "null"}]` if it appears in a schema. Document in the handoff that the spec is 3.1 and the design team's tooling must support 3.1.

**Warning signs:**
- `grep "nullable" apps/backend/openapi.json` returns more than 0 hits
- Redocly lint reports `nullable is not valid in OpenAPI 3.1` warnings

**Phase to address:** Phase 64 (Contract Freeze) — lint pass before generating handoff artifacts

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|---|---|---|---|
| Keep `_api_v1_` operation ID suffix instead of curating clean IDs | Zero drift-gate disruption | Downstream Postman collection has ugly request names; design team must parse path slug to find endpoints | Acceptable for v1.11 if admin-web is frozen; fix in v2.0 when frontend integration allows synchronized rename |
| Skip adding auth scopes to `securitySchemes` in OpenAPI | Faster curation | Downstream codegen generates clients that don't attempt auth; design team must read the runbook | Never — add at least a `cookieAuth` scheme definition even if routes are not individually annotated |
| Newman smoke with no test assertions (just reachability) | Faster Phase 65 | CI gate passes even when every endpoint returns 500 | Never — always add `pm.response.to.be.success` to each request minimum |
| Single idempotency TTL of 1h for all endpoints | Simple, already implemented | Payment retries after 1h get a new execution (potential double-charge) | Never for payment endpoints; acceptable for non-financial mutations |
| Execute all three runbooks in one Phase 67 session | Faster completion | A failure in VER-03 (ЮKassa sandbox) blocks VER-01 (reports) evidence capture | Acceptable if the operator can checkpoint failures; NOT acceptable if VER-03 might leave the DB in an inconsistent state that affects VER-01 |
| Ruff sweep in one giant commit | One CI pass | Undebuggable if anything breaks; reviewer cannot meaningfully review 297-file diff | Never — split format / safe-fix / manual-fix into separate commits |

---

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|---|---|---|
| ЮKassa webhook idempotency vs. generic `app/core/idempotency.py` | Wiring `Depends(verify_idempotency)` on the ЮKassa webhook endpoint | Webhook endpoint uses `redis.set(f"cc:yk:webhook:{event_id}", NX=True, EX=86400)` directly — a separate dedup mechanism. It does NOT use `verify_idempotency` and never should (the webhook has no `Idempotency-Key` header from ЮKassa) |
| Postman CSRF header | Bearer token auth in Postman collection | The API uses HTTP-only cookie auth + `X-CSRF-Token` on every mutating endpoint. The Postman collection needs pre-request scripts to: (1) POST `/auth/login`, (2) save the `Set-Cookie` header, (3) extract the CSRF token from the response or a GET endpoint, and send it as `X-CSRF-Token` on subsequent mutations |
| Redocly lint on OpenAPI 3.1 | Treating all warnings as errors | `tag-description: warn` is the right severity — not every tag needs a description. `operation-operationId: error` IS the right severity — missing operation IDs break Postman collection folder structure |
| `ruff format` + `ruff check --fix` ordering | Running `ruff check --fix` before `ruff format` | Always format FIRST. `ruff check --fix` may add or remove whitespace in ways that interact with auto-format, producing a diff that is not byte-stable until format runs again. Order: format, then check fix, then manual |
| `mypy` on SQLAlchemy 2.0 models | `attr-defined` errors on mapped column attributes | SQLAlchemy 2.0 uses `Mapped[T]` annotations which mypy understands correctly. The 4 `attr-defined` errors in `app/modules/auth/models.py` are NOT SQLAlchemy issues — they are missing `__all__` in the models module. Fix by adding `__all__` |
| Email capture for Phase 67 | Adding MailHog + SMTP adapter path | The existing `SandboxEmailClient` logs full email envelopes to structlog. Use `EMAIL_PROVIDER=sandbox` for Phase 67 email evidence capture — zero new code required. MailHog requires a new SMTP adapter (out of v1.11 scope) |

---

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|---|---|---|---|
| Idempotency key TTL 1h for payment endpoints | Operator retries a payment after 1h system downtime, gets a new execution (potential double-charge) | Set `IDEMPOTENCY_TTL_SECONDS = 86400` (24h) to match ЮKassa webhook dedup window | At first system downtime longer than 1h where a payment was in-flight |
| Storing full response body in Redis for every idempotent request | Large response bodies (e.g., paginated lists with 100 items) inflate Redis memory | Scope idempotency to mutating endpoints only (POST/PUT/PATCH) — never GET; the current `verify_idempotency` is only wired to sale/refund/booking routes, which return small responses (single resource) | Non-issue at single-gym scale; would matter at SaaS scale |
| Newman smoke against a freshly seeded DB with no data | Endpoints that require existing data (e.g., `GET /api/v1/memberships/{id}`) return 404 instead of 200, causing test assertion failures | Seed the DB with enough fixture data before running Newman (use the existing `scripts/seed_verification_fixtures.py` pattern from v1.3 Phase 29) | On every local Newman run without a proper seed step |

---

## Security Mistakes

| Mistake | Risk | Prevention |
|---|---|---|
| Cross-user idempotency cache (missing `actor_user_id` in key) | User A's transaction result served to user B on key collision — data leakage + potential wrong resource activation | Bind idempotency key to `{method}:{path}:{user_id}:{header_value}` (see Pitfall C-03) |
| VER-03 with `YOOKASSA_SANDBOX=false` | Real money movement on production ЮKassa account | Mandatory pre-flight: print `YooKassaSettings().sandbox` before any Phase 67 ЮKassa call |
| `newman-env.json` with real credentials | Credentials exposed in git history | Only fixture credentials (`@fixture.local`) in committed file; real overrides in gitignored `*.local.json` |
| Evidence files capturing PII | Operator runbook evidence may contain real client names, emails, payment amounts from sandbox/production | Scrub PII from all evidence files before committing to `.planning/milestones/v1.11-OPERATOR-EVIDENCE.md`; use fixture client names in sandbox |
| MailHog `--profile dev` accidentally active in production docker-compose | All outgoing email is silently trapped — members never receive membership expiry warnings | MailHog must be behind `profiles: ["dev"]`; the production compose file has no `--profile dev`; verify with `docker compose ps` after production stack start |

---

## "Looks Done But Isn't" Checklist

- [ ] **OpenAPI curation:** Spec title changed from `"Sportzal API"` to `"clubcore API"` AND version updated AND `servers:[]` populated — verify `grep "Sportzal API" openapi.json` returns 0 hits
- [ ] **Drift gate:** After Phase 64 curation, BOTH `openapi.json` AND `schema.d.ts` are regenerated and committed as a single atomic event — verify `git diff --exit-code apps/backend/openapi.json packages/api-client/src/schema.d.ts` passes in CI
- [ ] **Postman collection:** Collection was generated AFTER Phase 64 curation (not before) — verify the collection's `"info"` name matches the curated spec's `info.title`
- [ ] **Newman smoke:** Collection contains at least one test assertion per request — verify `grep "pm.test" collection.json | wc -l` is greater than 0
- [ ] **Idempotency hardening:** `verify_idempotency` key includes `actor_user_id` — verify with a test that submits the same header from two users and confirms Redis stores distinct keys
- [ ] **Idempotency TTL:** `IDEMPOTENCY_TTL_SECONDS` is 86400 (24h) — verify `grep IDEMPOTENCY_TTL app/core/idempotency.py`
- [ ] **Tech-debt sweep:** `uv run ruff check app tests` exits 0 — verify in CI, not just locally (ruff version must match `uv sync --frozen`)
- [ ] **Tech-debt sweep:** `uv run mypy app` exits 0 — verify `mypy` runs against the clean tree, not a stale mypy cache (delete `.mypy_cache` before final check)
- [ ] **Runbook staleness:** Each operator runbook checked for `sz:`, `SPORTZAL`, `1.1.0` version references before execution — verify pre-flight diff document exists in Phase 67 plan 1
- [ ] **VER-03 sandbox gate:** `YOOKASSA_SANDBOX=true` verified in env before ANY ЮKassa API call in Phase 67 — verify by printing `YooKassaSettings().sandbox` in the evidence

---

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---|---|---|
| Operation IDs changed, schema.d.ts broke admin-web | HIGH | Revert operation ID changes to original auto-generated values via `git revert`; re-approach using `generate_unique_id_function` suffix stripping instead of explicit `operation_id=` |
| In-flight placeholder stuck in Redis after handler exception | LOW | `redis-cli DEL "cc:idem:{method}:{path}:{user_id}:{key}"` for the affected key; client can retry immediately |
| VER-03 sandbox hit production by accident | HIGH | Contact ЮKassa support to reverse the test payment; document in evidence file; never close VER-03 evidence as PASS |
| Postman collection generated before OpenAPI was curated | LOW | Regenerate the collection post-curation: `openapi2postmanv2 -s apps/backend/openapi.json -o ...`; recommit |
| Tech-debt sweep broke a test | MEDIUM | `git bisect` across the three-commit sweep sequence; identify which specific fix caused the regression; fix the root cause rather than reverting the sweep |
| Runbook evidence contains PII | MEDIUM | Amend the evidence commit, replacing PII with `[REDACTED]`; if on a feature branch before PR merge, amend is safe |
| Drift gate fires after curation | LOW | The spec and schema.d.ts must always be regenerated as a pair; run `uv run python -m scripts.export_openapi && pnpm --filter @clubcore/api-client codegen` then commit both files in one commit |

---

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---|---|---|
| C-01: Operation ID rename breaks schema.d.ts | Phase 64 plan 1 | Drift gate CI passes; `_v19Checks` + `_v18Checks` TypeScript guards compile clean |
| C-02: In-flight placeholder stuck after rollback | Phase 66 | Integration test: submit a request that raises a service error, retry with same key — verify error response (not `idempotency_in_flight`) |
| C-03: Cross-user idempotency replay | Phase 66 | New test: two users, same key, verify independent Redis entries |
| C-04: `title="Sportzal API"` stale | Phase 64 plan 1 | `grep "Sportzal API" openapi.json` returns 0 |
| C-05: Stale cache on status-transition retry | Phase 66 design doc + Phase 64 | Code review: no DB lookup inside cached response path; OpenAPI IdempotencyKey description documents semantics |
| C-06: Unsafe ruff fixes change semantics | Phase 63 requirements | Sweep requirements explicitly forbid `--unsafe-fixes`; mypy passes after sweep |
| C-07: Monolithic sweep PR | Phase 63 plans | Three commits: format / safe-fix / manual; each has a CI green checkpoint |
| C-08: Newman exits 0 with no assertions | Phase 65 | `grep "pm.test" collection.json | wc -l` > 0; Newman run exits 1 on a deliberately broken request |
| C-09: Newman in CI without DB | Phase 65 plan 1 | Newman is NOT added to `.github/workflows/ci.yml`; documented as local-only in Phase 67 |
| C-10: Credentials in newman-env.json | Phase 65 plan 1 | `grep -E "@(?!fixture\.local)" apps/backend/newman-env.json` returns 0 |
| C-11: Stale runbook env var names | Phase 67 plan 1 | Pre-flight diff document exists before first runbook execution |
| C-12: VER-03 hits production | Phase 67 (VER-03 pre-flight) | `YooKassaSettings().sandbox == True` printed in evidence before ЮKassa calls |
| C-13: OpenAPI 3.1 nullable in 3.0 style | Phase 64 lint pass | `@redocly/cli lint openapi.json` exits 0; `grep "nullable" openapi.json` returns 0 |

---

## Sources

- Direct codebase inspection:
  - `apps/backend/app/core/idempotency.py` — existing implementation; in-flight placeholder + 1h TTL confirmed
  - `apps/backend/app/integrations/yookassa/webhook_verifier.py` — separate dedup mechanism; does not use `verify_idempotency`
  - `apps/backend/app/integrations/yookassa/client.py` — `IDEMPOTENCE_KEY_HEADER` spelling quirk (one `t`) documented at D-48-12
  - `apps/backend/app/main.py` — `title="Sportzal API"`, `version="1.1.0"` confirmed stale
  - `apps/backend/openapi.json` — 3.1 spec; 102/103 operations have auto-generated `_api_v1_` suffix IDs; 0 servers; 0 securitySchemes; 1 `nullable` keyword
  - `.github/workflows/ci.yml` — no Newman job; drift gate guards both `openapi.json` and `schema.d.ts`
  - `.planning/handoff/v1.6-postman.json` — prior collection uses Postman v2.1 schema; no test scripts in existing file
- `.planning/RETROSPECTIVE.md` — v1.3 REG-29-01/03/04 inline regression fix pattern; v1.5 Phase 40 runbook staleness (4 hotfixes needed on first execution); v1.6 Phase 46 VER-09 fixture-path failure; v1.10 RETROSPECTIVE confirming stale `one_liner` extraction patterns
- `.planning/PROJECT.md` — v1.11 scope; `DEFER-46-04` breakdown; operator-pending carry-over list; `cc:yk:webhook:` Redis key shape for ЮKassa dedup
- `.planning/HISTORICAL_NOTE.md` — immutability boundary for v1.4–v1.9 runbooks
- IETF `draft-ietf-httpapi-idempotency-key-header-07` — cache window guidance; key format recommendations

---

*Pitfalls research for: v1.11 API Handoff + Production Hardening (Phases 63–67)*
*Researched: 2026-05-26*
