# Phase 6: RBAC Wiring + Parity Tests - Context

**Gathered:** 2026-05-02
**Status:** Ready for planning

<domain>
## Phase Boundary

Every protected route refuses unauthenticated callers with 401 and unauthorized callers with 403 **before** any side-effect runs, and the `OWNER_ONLY` matrix can never silently drift between the backend (`app.core.permissions`) and the frontend (`apps/admin-web/src/shared/session/can.ts`). CSRF double-submit (`X-CSRF-Token` header vs `sportzal_csrf` cookie) lands on every mutating route except the auth bootstrap pair (`/auth/login`, `/auth/refresh`) and the Telegram server-side endpoints (`/auth/telegram/*`).

**Phase 6 ships:**

1. **`require_authenticated()` factory** in `app/core/dependencies.py` (NEW). Sibling to `require_permission(...)`. Resolves `CurrentUser` via `get_current_user` and returns it unchanged — used by routes that need an authenticated caller but no role gate (`/auth/me`, `/auth/logout`, `/auth/logout-all`).
2. **Migrate Phase 5 auth-meta routes** — `apps/backend/app/modules/auth/router.py`: swap `Depends(get_current_user)` → `Depends(require_authenticated())` on `/me`, `/logout`, `/logout-all`. Semantically identical for the auth flow; declares the gate factory explicitly so the introspection test enforces a strong invariant.
3. **`verify_csrf` dependency** in `app/core/dependencies.py` (NEW). Reads the `sportzal_csrf` cookie + `X-CSRF-Token` header, short-circuits on safe HTTP methods (GET/HEAD/OPTIONS/TRACE), constant-time compares the two values via `secrets.compare_digest`, raises `CsrfMismatch` (NEW `AppError` subclass) on missing-or-mismatched.
4. **`CsrfMismatch(AppError)`** in `app/core/exceptions.py` — `code = "csrf_mismatch"`, `status_code = 403`. Distinct from `forbidden` so the frontend can show a "page expired, refresh and retry" UX rather than a generic 403.
5. **CSRF wiring on Phase 5 auth router** — per-route `Depends(verify_csrf)` on `/logout` and `/logout-all` ONLY. `/login`, `/refresh`, future `/telegram/*` declare NO `verify_csrf` (exempt by omission, not by allowlist).
6. **Test fixtures + RBAC integration test (TEST-05)** — `tests/_fixtures/owner_routes.py` (NEW): a router built dynamically from `OWNER_ONLY` exposing one stub `GET /_t/{action}/{resource}` endpoint per pair, each declaring `Depends(require_permission(action, resource))`. Test FastAPI app fixture mounts both the real `api` router and the fixture router. `tests/integration/rbac/test_owner_only.py` (NEW) seeds two real DB users (one `Role.OWNER`, one `Role.RECEPTION`) via `authenticate()` + `issue_tokens()`, parametrizes over `OWNER_ONLY`, asserts owner=200 and reception=403 with `code: "forbidden"`. Also asserts unauthenticated (no cookie) → 401 with `code: "invalid_token"`.
7. **Parity test (TEST-06)** — `tests/integration/test_rbac_parity.py` (NEW): regex-parses `apps/admin-web/src/shared/session/can.ts` for the 9 `(action, resource)` pairs AND `apps/admin-web/src/shared/session/registry.ts` for the `Resource` and `Action` TS unions. Asserts three set-equalities: backend `OWNER_ONLY == frontend pairs`, backend `Resource StrEnum values == frontend Resource union`, backend `Action StrEnum values == frontend Action union`.
8. **Route-introspection test (TEST-07)** — `tests/integration/test_route_introspection.py` (NEW): walks `app.routes` from a fresh `create_app()`. For each `APIRoute`, skips `EXCLUDED_PATHS` (`/healthz`, `/api/v1/auth/login`, `/api/v1/auth/refresh`, and any `/api/v1/auth/telegram/*`), then walks the route's `dependant` tree and asserts at least one `Dependant.call` belongs to `require_permission` or `require_authenticated` (identified by `__qualname__` prefix). FastAPI built-in routes (`/openapi.json`, `/docs`, `/redoc`) and non-`APIRoute` entries (Mounts, WebSocketRoutes) are skipped.
9. **Phase 5 test compat update** — `tests/integration/auth/test_logout.py` (Phase 5) gets a small change: requests to `/logout` and `/logout-all` now must send a matching `X-CSRF-Token` header. The existing fixtures that login first already receive the `sportzal_csrf` cookie; tests echo it on the mutating call. No semantic change; tightens the test surface.

**In scope (Phase 6 REQ-IDs):** RBAC-02, RBAC-03, RBAC-04, RBAC-05, CSRF-02, TEST-05, TEST-06, TEST-07.

**Out of scope (deferred to later phases):**
- `Depends(require_permission(...))` on real business endpoints — Phase 6 has no business endpoints to wire (clients arrives in Phase 8). Phase 6 ships the gate primitives, the introspection test that any future business route must satisfy, and the fixture-router-based TEST-05 that proves the gate works end-to-end.
- `/auth/telegram/start|status|verify` and the bot worker process — Phase 7. Phase 6 only adds these paths to the introspection-test exclusion list (they exist in the planned design even though no route is mounted yet — the introspection test must not panic when it walks `app.routes` and these are absent; the exclusion list is "paths that DON'T need require_permission when present", not "paths that must exist").
- `audit_log` DB table writes for `forbidden` / `csrf_mismatch` events — Phase 8 (INFRA-04, AUDIT-01..03). Phase 6 emits structlog `event=rbac_forbidden` / `event=csrf_mismatch` via the Phase 5 `app.core.audit.emit(...)` helper so Phase 8's DB writer latches on without renaming.
- Frontend echo of `X-CSRF-Token` header — Phase 9/10. The fetcher in `packages/api-client` (Phase 9) reads `sportzal_csrf` and injects the header on every mutating call. Phase 6's CSRF dependency is server-side only.
- Per-IP rate-limit on 403 responses — v1.2.

</domain>

<decisions>
## Implementation Decisions

### Authenticated-but-role-agnostic routes (RBAC-02..04)

- **D-01 [LOCKED]:** **NEW `require_authenticated()` factory in `app/core/dependencies.py`.** Sibling of `require_permission(action, resource)`. Resolves `CurrentUser` via `get_current_user` and returns it unchanged (no `can()` check). Implementation: a thin closure mirroring `require_permission`'s shape so the introspection test can identify it via `__qualname__.startswith('require_authenticated.')`:

  ```python
  def require_authenticated() -> Callable[..., Awaitable[CurrentUser]]:
      async def _checker(
          user: Annotated[CurrentUser, Depends(get_current_user)],
      ) -> CurrentUser:
          return user
      return _checker
  ```

- **D-02 [LOCKED]:** **Phase 5 auth-meta routes are MIGRATED to `Depends(require_authenticated())`.** Specifically `/auth/me`, `/auth/logout`, `/auth/logout-all`. Phase 6 edits `apps/backend/app/modules/auth/router.py` accordingly. The signature change is one line per route (`Depends(get_current_user)` → `Depends(require_authenticated())`); the request handler bodies stay identical because the dep returns the same `CurrentUser` instance.
- **D-03 [LOCKED]:** **Introspection invariant (TEST-07): every non-excluded `APIRoute` declares EXACTLY ONE of `require_permission(...)` OR `require_authenticated()`.** `Depends(get_current_user)` directly on a route signature is BANNED for protected routes and the introspection test fails the build if it appears. `get_current_user` remains the underlying primitive — `require_permission` and `require_authenticated` both depend on it; nothing else should.
- **D-04 [LOCKED]:** **Excluded paths for TEST-07** (these may legally have NO `require_permission`/`require_authenticated`):
  - `/healthz` (Kubernetes liveness — Phase 2 D-14)
  - `/api/v1/auth/login` (identity is in the body)
  - `/api/v1/auth/refresh` (identity is in the `sz_refresh` cookie; access cookie may be expired)
  - `/api/v1/auth/telegram/start` (Phase 7 — no auth yet, identity proven by deep-link consumption)
  - `/api/v1/auth/telegram/status` (Phase 7 — same)
  - `/api/v1/auth/telegram/verify` (Phase 7 — body carries `token` + `code`)
  - FastAPI built-ins: `/openapi.json`, `/docs`, `/redoc`, `/docs/oauth2-redirect`. Skipped by checking `route.endpoint` against FastAPI's internal callables OR by name match on the path.

  The exclusion list lives as a module-level constant in `tests/integration/test_route_introspection.py` so the diff is the audit trail when it changes.

### CSRF placement + exemption (CSRF-02, RBAC SC #4)

- **D-05 [LOCKED]:** **`verify_csrf` is attached at the SUB-ROUTER level, not as middleware and not as a `v1` blanket dep.** Each business sub-router (Phase 8 `clients`, future modules) declares `APIRouter(dependencies=[Depends(verify_csrf)])`. The auth router (which mixes exempt + protected) opts in per-route only on `/logout` and `/logout-all`. New module = new sub-router = automatic CSRF; no allowlist surface to drift.
- **D-06 [LOCKED]:** **`verify_csrf` short-circuits on safe HTTP methods (GET, HEAD, OPTIONS, TRACE).** Sub-router-level dep means the same `verify_csrf` runs on every method on `clients/*`; safe methods MUST not 403 for missing CSRF (read-only). Implementation: read `request.method`, return `None` for safe methods before any cookie/header access.
- **D-07 [LOCKED]:** **Validation is double-submit cookie pattern with `secrets.compare_digest`.** Read `sportzal_csrf` cookie + `X-CSRF-Token` header; if either is missing or they don't match (constant-time compare), raise `CsrfMismatch`. No HMAC-bound CSRF token — the random 32-byte hex is enough at this scale (Phase 4 D-26 already commits to the 32-byte hex generator).
- **D-08 [LOCKED]:** **NEW `CsrfMismatch(AppError)` in `app/core/exceptions.py`** — `code = "csrf_mismatch"`, `status_code = 403`. Reuses the existing `AppError → JSONResponse` handler (Phase 2 D-12). Distinct from `forbidden` so the frontend (Phase 10) can recover gracefully (page expired → silent refresh + retry) without conflating with a true RBAC denial.
- **D-09 [LOCKED]:** **Auth router CSRF wiring (per-route):**
  - `/login` — NO `verify_csrf` (exempt; identity is in the body, no prior cookie state).
  - `/refresh` — NO `verify_csrf` (exempt; the sole protection is the `sz_refresh` cookie + family rotation, and `/refresh` may be called when the access token has expired and CSRF cookie is fresh, so adding CSRF here is correct in theory but operationally fragile).
  - `/logout` — `dependencies=[Depends(verify_csrf)]` (mutating, authenticated).
  - `/logout-all` — `dependencies=[Depends(verify_csrf)]` (mutating, authenticated).
  - `/me` — NO `verify_csrf` (GET; safe-method short-circuit would skip it anyway, but the per-route dep is omitted for clarity).
  - Future `/telegram/start|status|verify` (Phase 7) — NO `verify_csrf` (exempt list).

### TEST-05 strategy without real OWNER_ONLY business routes (RBAC-05)

- **D-10 [LOCKED]:** **Test-only fixture router built dynamically from `OWNER_ONLY`.** Lives at `apps/backend/tests/_fixtures/owner_routes.py`. Imports `OWNER_ONLY` at collection time and registers one stub endpoint per `(action, resource)` pair:

  ```python
  # path uses Action.value / Resource.value as URL segments;
  # resource value is already URL-safe ("owner-area", lowercase).
  router = APIRouter(prefix="/_t", tags=["_test_only"])
  for action, resource in sorted(OWNER_ONLY):
      def _make(a: Action, r: Resource):
          @router.get(
              f"/{a.value}/{r.value}",
              dependencies=[Depends(require_permission(a, r))],
          )
          async def _stub() -> dict[str, bool]:
              return {"ok": True}
          _stub.__name__ = f"stub_{a.value}_{r.value}"
          return _stub
      _make(action, resource)
  ```

  The closure factory `_make` exists to bind `a`/`r` per iteration (Python late-binding gotcha). The path prefix `/_t` (underscore-T) is unmistakably non-production and would be visually obvious if it ever leaked into a real route enumeration. The test app fixture mounts both `api` and this router; the production `create_app()` MUST NOT mount it — guard with a fixture-only mount in `tests/conftest.py`.

- **D-11 [LOCKED]:** **TEST-05 authenticates via real seeded users + real `/auth/login`.** Two pytest fixtures (`owner_client`, `reception_client`) seed a `User` row in the SAVEPOINT-scoped `db_session` with `role=OWNER` / `role=RECEPTION`, then issue `POST /api/v1/auth/login` so the test client picks up real `sz_access` + `sz_refresh` + `sportzal_csrf` cookies. Tests parametrize over `sorted(OWNER_ONLY)` and assert:
  - `owner_client.get(f"/_t/{a}/{r}")` → 200 with body `{"ok": True}`.
  - `reception_client.get(f"/_t/{a}/{r}")` → 403 with body `{"code": "forbidden", ...}`.
  - Unauthenticated `async_client.get(f"/_t/{a}/{r}")` → 401 with body `{"code": "invalid_token", ...}` (per RBAC-04 — 401 takes precedence over 403 when there's no identity at all).

  Slowest of the three test strategies considered; chosen because it exercises the full stack (Argon2 verify → JWT mint → cookie issue → JWT decode → loader → require_permission → can() → ForbiddenError handler) on every parametrized RBAC test. Catches integration regressions in the auth chain that mock-loader strategies would miss.

- **D-12 [LOCKED]:** **The fixture router is mounted ONLY in tests; production `create_app()` is unchanged.** Mounting strategy in tests:
  - Option A (preferred): the existing `app` fixture in `tests/conftest.py` is extended with an `app_with_fixture_routes` sibling fixture that calls `create_app()` and additionally `app.include_router(_owner_routes_router, prefix="")` before yielding. RBAC tests use the new fixture; existing Phase 5 tests use `app`.
  - Option B (planner's call): a single `app` fixture that always mounts the fixture router, gated by a `if "PYTEST_RUNNING" in os.environ` check inside `create_app()`. Rejected by default — leaks test concerns into production code.
  - The planner picks A vs a fully-isolated test-app builder helper; the user-facing constraint is that production `create_app()` must remain free of any test-router import.

### Parity test mechanics (TEST-06)

- **D-13 [LOCKED]:** **Three set-equalities, not just one.** The parity test asserts:
  1. `set(OWNER_ONLY) == fe_pairs_from_can_ts` — the 9 `(action, resource)` pairs.
  2. `{r.value for r in Resource} == fe_resources_from_registry_ts` — all 11 Resource values match the TS `Resource` union.
  3. `{a.value for a in Action} == fe_actions_from_registry_ts` — all 5 Action values match the TS `Action` union.

  Catches the failure mode where someone renames `Resource.SCHEDULE` → `'timetable'` in TS (no OWNER_ONLY entry on `schedule` so pair-only parity stays green) but `can()` then returns garbage for the renamed resource at runtime in `RoleGate.tsx`.

- **D-14 [LOCKED]:** **TS file location resolved relative to the test file.** From `apps/backend/tests/integration/test_rbac_parity.py`, `Path(__file__).resolve().parents[4]` is the repo root. Frontend files are then `parents[4] / "apps" / "admin-web" / "src" / "shared" / "session" / "can.ts"` and `.../registry.ts`. Tests fail loudly (collected-as-error, not silent skip) if the files are absent — a missing parity source is a parity failure, not a "skip and hope" outcome.
- **D-15 (Discretion):** **Regex parsing, not a TS toolchain.** `can.ts` is matched with `r"\{\s*action:\s*'([^']+)',\s*resource:\s*'([^']+)'\s*\}"` — captures the 9 pairs verbatim. `registry.ts` Resource union: locate the `export type Resource =` line, read forward until the first non-pipe non-string-literal line, extract every `'<value>'`. Same for `export type Action =`. No Node subprocess, no `tree-sitter`, no TS compiler API — the file shape is locked by Phase 4 D-22 / can.ts comment "// frozenset for set-membership lookup" and any reformatting that breaks the regex is a parity-test failure (intentional — the regex anchors the file shape).
- **D-16 (Discretion):** **Parity test lives at `tests/integration/test_rbac_parity.py`** (top-level `integration/`, NOT `integration/rbac/`). Rationale: the test never spins up the FastAPI app — it's a static-file analysis. Filesystem-style location (top-level `integration/`) signals "doesn't need DB/Redis"; the `rbac/` subdir is for HTTP-level RBAC tests (TEST-05).

### Route-introspection mechanics (TEST-07)

- **D-17 [LOCKED]:** **Walk `app.routes` from a fresh `create_app()`.** For each `route in app.routes`:
  - Skip if `not isinstance(route, fastapi.routing.APIRoute)` — drops `Mount` / `WebSocketRoute`.
  - Skip if `route.path in EXCLUDED_PATHS` (D-04 list, plus `/openapi.json`, `/docs`, `/docs/oauth2-redirect`, `/redoc`).
  - Skip if `route.path.startswith("/api/v1/auth/telegram/")` — Phase 7 routes, exempt by prefix.
  - Otherwise: assert `_route_has_gate(route)` is True.
- **D-18 [LOCKED]:** **`_route_has_gate(route) -> bool`** walks `route.dependant.dependencies` recursively, examining every `Dependant.call`. Returns True if any `call.__qualname__` starts with `require_permission.` or `require_authenticated.` — the closure inside each factory is named `_checker`, but `__qualname__` is `require_permission.<locals>._checker` (Python convention), and a startswith match on the factory name is the cleanest discriminator. The recursion is necessary because FastAPI nests `Depends(...)` chains (e.g., `require_permission` itself depends on `get_current_user`).
- **D-19 (Discretion):** **The introspection test's exclusion list is a module-level constant exported for debugging.** When the test fails ("route X has no gate"), the failure message includes the full `EXCLUDED_PATHS` set so a developer can immediately see "is X meant to be excluded?". The constant is a `frozenset[str]` (paths) + a `tuple[str, ...]` (prefixes for the telegram subtree).

### Error envelope (RBAC-04, CSRF-02 SC)

- **D-20 [LOCKED]:** **403 from `require_permission` carries `code: "forbidden"`, message `f"forbidden:{action.value}:{resource.value}"`** (already the Phase 4 D-24 implementation). `fields: null`. Frontend matches on `code` only; the message is for log/debug.
- **D-21 [LOCKED]:** **403 from `verify_csrf` carries `code: "csrf_mismatch"`, message `"csrf_mismatch"`** (uniform). `fields: null`. Distinct error code so the frontend fetcher (Phase 9) can branch: `csrf_mismatch` → silently refresh CSRF cookie + retry once; `forbidden` → propagate to the UI as a user-actionable error.
- **D-22 [LOCKED]:** **401 from `get_current_user` is unchanged** (Phase 4 D-24): `code: "invalid_token"` with a sub-message indicating which fail mode (`missing_access_cookie`, `token_expired`, `invalid_token`, `wrong_token_type`, `unknown_role`, `user_loader_not_registered`, `user_not_found`). RBAC-04 guarantee: 401 fires BEFORE the role-based 403 path because `get_current_user` runs first in the dependency chain. No change required.

### Audit log emission (Phase 8 hand-off)

- **D-23 (Discretion):** **`require_permission` and `verify_csrf` emit structlog events via `app.core.audit.emit(...)` (Phase 5 D-21 helper).** Event names locked now so Phase 8's DB writer latches on:
  - `event=rbac_forbidden` `{user_id, role, action, resource, path, ip}` — fired before raising `ForbiddenError`.
  - `event=csrf_mismatch` `{user_id_or_none, path, method, ip, has_cookie: bool, has_header: bool}` — fired before raising `CsrfMismatch`. `user_id` is best-effort: `verify_csrf` runs before `get_current_user` per route, so the user might not be resolved yet — emit `None` if so.
  - `event=rbac_unauthenticated` is NOT emitted (the existing `InvalidAccessToken` raise in `get_current_user` handles its own logging via Phase 5 D-20 conventions).

### Phase 5 test compatibility

- **D-24 [LOCKED]:** **`tests/integration/auth/test_logout.py` is updated to send `X-CSRF-Token`** on `/logout` and `/logout-all` calls. The test fixtures already login first (so `sportzal_csrf` cookie is present); the test simply echoes `client.cookies["sportzal_csrf"]` as the header. One-line change per call site. Phase 6 owns this update — it's the necessary tightening when CSRF wiring lands.
- **D-25 (Discretion):** **No retroactive update to the Phase 5 conftest seeded-user pattern.** Phase 6's RBAC integration tests need both an owner and a reception seeded user; Phase 5's `seed_demo_data.py` only seeds an owner. Phase 6 ships per-test fixtures (`_seed_user(role)`) inside `tests/integration/rbac/conftest.py` rather than extending the production seed script. The seed script is for dev/operator bootstrap; tests own their own data via SAVEPOINT-rolled fixtures (Phase 5 D-22).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project specs
- `CLAUDE.md` — backend stack lock (Python 3.12 + uv + FastAPI + SQLAlchemy 2.0 async + Pydantic v2 + Postgres 16 + Redis 7 + structlog), modular-monolith layout, RU/CIS regional constraints, `httpx ASGITransport` + `pytest-asyncio` testing rule.
- `apps/admin-web/CLAUDE.md` — frontend RBAC contract (`useSession()` exposes `{role}`; `routeRegistry` + `can(role, action, resource)` is the FE source of truth).
- `.planning/PROJECT.md` — milestone scope, architectural invariants (`core ⊥ modules`), key decisions table, Out-of-Scope (no multi-tenancy, role set permanently `{owner, reception}`).
- `.planning/REQUIREMENTS.md` — Phase 6 owns these REQ-IDs (every plan task must trace): `RBAC-02`, `RBAC-03`, `RBAC-04`, `RBAC-05`, `CSRF-02`, `TEST-05`, `TEST-06`, `TEST-07`. Other REQ-IDs belong to Phases 4/5/7/8/9/10.
- `.planning/ROADMAP.md` Phase 6 section — goal + four numbered success criteria (reception=403/owner=200 on every OWNER_ONLY pair; every business route declares `Depends(require_permission(...))` verified by introspection; parity test fails build on FE↔BE drift; CSRF on POST/PATCH/DELETE except auth bootstrap).

### Cross-phase context (load-bearing)
- `.planning/phases/04-auth-foundations-cookie-rbac-primitives/04-CONTEXT.md` — D-21 (`OWNER_ONLY` frozenset shape), D-22 (`Role`/`Action`/`Resource` StrEnum string values mirrored from FE), D-23 (`can()` body), D-24 (`get_current_user` + `register_user_loader` + `require_permission` Protocol-based DI — Phase 6 fills the slot already wired by Phase 5 D-15), D-25 (`issue_session_cookies` + `Settings.cookie_secure`), D-26 (`generate_csrf_token` 32-byte hex, regenerated on login/refresh/OTP-verify).
- `.planning/phases/05-user-schema-email-password-auth/05-CONTEXT.md` — D-15 (`register_user_loader(load_user_by_id)` already called inside `create_app()`), D-16 (`/api/v1` prefix flip already done), D-17 (`clear_session_cookies` helper), D-20/D-21 (audit-emit helper + locked event names — Phase 6 adds `rbac_forbidden` and `csrf_mismatch`), D-22 (SAVEPOINT-based `db_session` fixture — Phase 6 RBAC tests use it), D-26 (Phase 5 routes use `Depends(get_current_user)` only — Phase 6 migrates to `require_authenticated` per D-02 above).
- `.planning/phases/02-backend-skeleton-with-quality-tooling/02-CONTEXT.md` — D-12/D-13 (AppError hierarchy → `CsrfMismatch` extends), D-14 (`/healthz` at root — exclusion in TEST-07).

### Research files
- `.planning/research/PITFALLS.md` — #19 (RBAC `core ⊥ modules` cleanly handled by the Protocol pattern from Phase 4 D-24); #25 (camelCase wire — error response uses snake-case `code`/`message` keys deliberately, matching the existing `AppError` handler — Phase 4 D-08).
- `.planning/research/ARCHITECTURE.md` — file-and-function-level layout for `app/core/dependencies.py` (Phase 6 extends).

### Source files Phase 6 directly reads or mutates
- `apps/backend/app/core/dependencies.py` — extend with `require_authenticated()` factory (D-01) and `verify_csrf` dependency (D-05..D-07). Existing `CurrentUser` Protocol, `register_user_loader`, `get_current_user`, `require_permission` preserved unchanged.
- `apps/backend/app/core/exceptions.py` — extend with `CsrfMismatch(AppError)` (D-08).
- `apps/backend/app/core/audit.py` — Phase 5 helper consumed by D-23 emit sites; no changes to the helper itself.
- `apps/backend/app/modules/auth/router.py` — migrate `/me`, `/logout`, `/logout-all` to `Depends(require_authenticated())` (D-02); add per-route `dependencies=[Depends(verify_csrf)]` to `/logout` and `/logout-all` (D-09).
- `apps/backend/tests/_fixtures/owner_routes.py` — NEW. Dynamic fixture router built from `OWNER_ONLY` (D-10).
- `apps/backend/tests/integration/rbac/__init__.py` — NEW. Empty.
- `apps/backend/tests/integration/rbac/conftest.py` — NEW. `owner_client` / `reception_client` fixtures + `_seed_user(role)` helper + test-app fixture mounting `owner_routes` router (D-12).
- `apps/backend/tests/integration/rbac/test_owner_only.py` — NEW. TEST-05 — parametrized over `OWNER_ONLY`; owner=200, reception=403, unauth=401 (D-11).
- `apps/backend/tests/integration/test_rbac_parity.py` — NEW. TEST-06 — three set-equalities (D-13), TS regex parser (D-15).
- `apps/backend/tests/integration/test_route_introspection.py` — NEW. TEST-07 — exclusion list constant (D-04, D-19), `_route_has_gate` recursion (D-18).
- `apps/backend/tests/integration/auth/test_logout.py` — Phase 5 file; one-line update per `/logout` and `/logout-all` call to send `X-CSRF-Token` header (D-24).
- `apps/backend/app/main.py` — UNCHANGED. `create_app()` does NOT mount the test fixture router. Composition root stays clean.

### Frontend reference (READ-ONLY in Phase 6)
- `apps/admin-web/src/shared/session/can.ts` — source of truth for `OWNER_ONLY` pairs (TEST-06). 9 entries verbatim mirrored.
- `apps/admin-web/src/shared/session/registry.ts` — source of truth for `Resource` and `Action` TS unions (TEST-06). 11 + 5 values verbatim mirrored.
- `apps/admin-web/src/shared/session/types.ts` — `Role` type (string union `'owner' | 'reception'`); not parsed by TEST-06 because the role set is locked at compile time on both sides per PROJECT.md OoS.

### External docs (consulted)
- OWASP CSRF Prevention Cheat Sheet 2024 — double-submit cookie pattern (D-07); `secrets.compare_digest` constant-time compare; safe-method short-circuit (D-06).
- FastAPI routing internals — `APIRoute.dependant` tree shape, `Dependant.call` introspection (D-18).
- RFC 7231 §4.2.1 — safe HTTP methods (GET/HEAD/OPTIONS/TRACE) (D-06).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable assets (Phase 4/5 outputs Phase 6 consumes verbatim)
- `app/core/permissions.py:OWNER_ONLY` (frozenset of 9 pairs) — read by `require_permission`, by TEST-05 fixture-router builder (D-10), and by TEST-06 parity (D-13).
- `app/core/permissions.py:Role` / `Action` / `Resource` StrEnums — read by TEST-06 (D-13) and parametrized over by TEST-05 (D-11).
- `app/core/permissions.py:can(role, action, resource)` — already implements the gate logic; Phase 6 does NOT reimplement.
- `app/core/dependencies.py:CurrentUser` Protocol + `register_user_loader` + `get_current_user` + `require_permission` — extended with `require_authenticated` and `verify_csrf` (siblings, not replacements).
- `app/core/exceptions.py:AppError` + `register_exception_handlers` — `CsrfMismatch(AppError)` rides on the existing `_app_error_handler` mapping `AppError` → `JSONResponse({code, message, fields})`. No handler change.
- `app/core/security.py:generate_csrf_token` — emits the value Phase 6 validates. No change in Phase 6.
- `app/core/security.py:issue_session_cookies` — sets `sportzal_csrf` cookie with `Path=/`, `httponly=False`, `samesite=lax`. The cookie is read by `verify_csrf` (D-07) via `request.cookies["sportzal_csrf"]`.
- `app/core/audit.py:emit` (Phase 5) — Phase 6 emits `event=rbac_forbidden` and `event=csrf_mismatch` (D-23).
- `app/main.py:create_app` — already calls `register_user_loader(load_user_by_id)` (Phase 5 D-15). Phase 6 does NOT touch composition root.
- `app/modules/auth/service.py:authenticate` / `issue_tokens` — used by RBAC test fixtures to seed authenticated owner/reception clients (D-11).
- `tests/conftest.py:app` / `async_client` / `db_session` — Phase 3+5 fixtures. Phase 6 RBAC tests reuse them; the fixture-router test app extends `app` (D-12).

### Established patterns to honor
- **Factory pattern, no module-level `app`** (Phase 2 main.py docstring) — Phase 6's test fixture router is registered via a NEW pytest fixture, not by mutating `create_app()`.
- **`core ⊥ modules`** (importlinter) — `app/core/dependencies.py` MUST NOT import from `app.modules.*`. `verify_csrf` reads only `request.cookies` + `request.headers` + raises `CsrfMismatch` (in `app.core`); `require_authenticated` is a thin wrapper over `get_current_user`. Both stay inside `app.core`.
- **AppError → JSONResponse** (Phase 2 D-12, Phase 4 D-08) — `CsrfMismatch` is a subclass; the existing handler emits the right shape.
- **Per-route `dependencies=[...]` for cross-cutting checks** (Phase 5 router pattern for CSRF-exempt routes) — Phase 6 uses `dependencies=[Depends(verify_csrf)]` on `/logout` and `/logout-all` rather than adding `Depends(verify_csrf)` to every signature.
- **SAVEPOINT-rolled `db_session`** (Phase 5 D-22) — RBAC tests seed users inside the rolled-back transaction, so the seeded owner/reception don't leak across tests.
- **Russian-narrative + English-code docs style** (Phase 3 D-05) — PLAN.md / SUMMARY.md narrative in Russian, code in English.

### Integration points
- **Phase 5 (already shipped) — Phase 6 retroactively migrates `/auth/me`, `/auth/logout`, `/auth/logout-all` to `Depends(require_authenticated())`** (D-02). Phase 5 tests update only `test_logout.py` to send `X-CSRF-Token` (D-24); login/refresh/me tests unchanged.
- **Phase 7 (Telegram OTP)** — `/auth/telegram/start|status|verify` are already in the TEST-07 exclusion list (D-04). Phase 7 mounts these routes; the introspection test continues to pass without edits because the exclusion list anticipates them. Phase 7's bot-driven session issuance does NOT need to declare `require_permission` — same exemption rationale as `/login`.
- **Phase 8 (Clients + Audit Log)** — `clients` sub-router declares `APIRouter(dependencies=[Depends(verify_csrf)])` per D-05. Every `clients` endpoint declares `Depends(require_permission(action, resource))` per D-03. The introspection test (TEST-07) verifies this without change. Phase 8 also enables `audit_log` DB writes; the Phase 6 emit sites for `rbac_forbidden` / `csrf_mismatch` (D-23) gain DB rows automatically.
- **Phase 9 (OpenAPI + api-client)** — the `openapi.json` export now includes `csrf_mismatch` as a 403 response code on every mutating route. The fetcher in `packages/api-client` (Phase 9) branches on `code`: `csrf_mismatch` → refresh CSRF cookie + retry; `forbidden` → propagate; `invalid_token` → single-flight `/auth/refresh`.
- **Phase 10 (admin-web wiring)** — frontend reads `sportzal_csrf` cookie and injects `X-CSRF-Token` header on every mutating call via the fetcher; FE-07 ESLint rule already bans direct `fetch(` outside the api-client.

</code_context>

<specifics>
## Specific Ideas

- **`require_permission` and `require_authenticated` are SIBLINGS, not parent/child.** A future contributor might be tempted to refactor `require_permission` to compose `require_authenticated` + a `can()` check. Don't — both wrap `get_current_user` directly; nesting them adds an extra `Dependant` layer that the introspection test must traverse and gives no design benefit. Keep them as separate single-level wrappers around `get_current_user`.
- **The introspection test is the architectural enforcement, not the documentation.** PROJECT.md / CLAUDE.md don't need a "every protected route declares a gate" rule because TEST-07 fails the build if any route lacks one. The test IS the rule. A new contributor learns the rule by failing the test, which is the point.
- **CSRF dep at sub-router level + opt-in per-route on auth router is intentional asymmetry.** The auth router is the ONE router where the exempt-vs-protected line cuts through individual routes (`/login` exempt, `/logout` protected). Every other router is uniform (all-protected); blanket sub-router dep is correct there. Don't propose unifying these — the asymmetry reflects reality.
- **Fixture router path prefix `/_t` is deliberately ugly.** It signals "this is not real" at a glance in any route enumeration, log line, or stack trace. Don't propose `/test/...` or `/internal/...` — those look like legitimate routes and have been mistaken for production endpoints in past projects.
- **Three set-equalities in TEST-06, not one.** Pair-only parity (option B in the discussion) leaves a hole: a frontend rename of a Resource value that's NOT in OWNER_ONLY (e.g., `'schedule'` → `'timetable'`) silently breaks frontend `RoleGate` checks for that resource without failing TEST-06. The user explicitly chose the stronger parity to close that hole.
- **`CsrfMismatch` is distinct from `forbidden` for frontend recovery semantics.** A `forbidden` response means the user cannot do this; surface it in the UI. A `csrf_mismatch` response means the page is stale; refresh the CSRF cookie (call `/auth/refresh` or simply re-read cookies) and retry once. Conflating them under `code: "forbidden"` would force the frontend to either retry on every 403 (eats 403 UX) or never auto-recover (eats CSRF UX). Distinct codes are the correct factoring.
- **Real seeded users for TEST-05 (D-11) is the slowest-but-most-honest choice — and the user picked it on purpose.** Faster strategies (mock loader, dependency_overrides) would skip the Argon2 verify, JWT mint, cookie issue, JWT decode, and registered loader paths. Phase 6 owns the gate; Phase 6 should prove the gate works on the real auth chain that ships, not on a stripped-down approximation. Don't downgrade this to mock loaders later "for speed".
- **`tests/_fixtures/owner_routes.py` lives at `tests/_fixtures/`, not `tests/fixtures/` or inside `tests/integration/rbac/`.** The leading underscore mirrors Python's "private module" convention; `_fixtures/` signals "tests-internal helpers, not test files themselves" so pytest doesn't try to collect it as test functions. Aligns with the SQLAlchemy / FastAPI test-fixture conventions.

</specifics>

<deferred>
## Deferred Ideas

- **`Depends(require_permission(...))` on real business endpoints (clients delete, etc.)** — Phase 8 (CLIENTS-08 + RBAC-03 enforcement on real routes). Phase 6 ships only the gate primitives + the introspection test that future routes must satisfy.
- **`audit_log` DB rows for `rbac_forbidden` / `csrf_mismatch` events** — Phase 8 (INFRA-04, AUDIT-01..03). Phase 6 emits structlog events with locked names; Phase 8's `audit.emit(...)` swap-in writes them to DB.
- **Frontend `X-CSRF-Token` header injection** — Phase 9 (`packages/api-client/src/fetcher.ts` reads `sportzal_csrf`, injects header) + Phase 10 (admin-web consumes the fetcher).
- **CSRF retry-on-mismatch fetcher logic** — Phase 9 (api-client): on 403 with `code: "csrf_mismatch"`, refresh the cookie (one strategy: call `/auth/refresh` which rotates `sportzal_csrf` per Phase 4 D-26) and retry the original request once.
- **Per-IP rate-limit on 403 responses** — v1.2. Phase 6's `verify_csrf` and `require_permission` raise unconditionally; aggregate rate-limit on repeat 403s is a noisy-neighbor mitigation, not a correctness concern.
- **`is_active` / `email_verified` checks in `require_authenticated`** — v1.2 (these columns don't exist on `User` per Phase 5 D-06). If they're added, `require_authenticated` becomes the natural enforcement point.
- **HMAC-bound CSRF tokens (vs random)** — v2+. Phase 4 D-26 commits to 32-byte random hex; D-07 here matches with `secrets.compare_digest`. Switching to HMAC requires a server-side secret rotation strategy that's premature for a 1-2 user system.
- **`/auth/refresh` CSRF protection** — explicitly NOT applied (D-09). The refresh endpoint may be called when the access cookie has expired, and adding CSRF would force the frontend to read `sportzal_csrf` (which DOES survive across access-cookie expiry) before every refresh call. The defensive value is small (refresh is protected by family rotation) and the operational cost is real. Revisit only if a concrete attack scenario emerges.
- **CSRF on WebSocket / SSE handshake** — no such endpoints exist in v1.1; if added, the `verify_csrf` dependency works as-is on the upgrade request.
- **OPTIONS preflight handling** — `verify_csrf` short-circuits on OPTIONS per D-06; no special CORS handling needed in Phase 6 because admin-web is same-origin to the API in production (subdomain routing) and dev uses Vite proxy. If cross-origin admin-web ever ships, CORS middleware is a Phase 11+ concern.
- **Active-sessions UI / per-session revoke** — v1.2 (AUTH-V12-01). Phase 6 doesn't touch session inspection.
- **Policy engine (Casbin / Oso / OPA)** — explicit OoS (REQUIREMENTS.md). The 9-entry static matrix is the correct tool; Phase 6's introspection test ensures the matrix is enforced everywhere.

</deferred>

---

*Phase: 06-rbac-wiring-parity-tests*
*Context gathered: 2026-05-02*
