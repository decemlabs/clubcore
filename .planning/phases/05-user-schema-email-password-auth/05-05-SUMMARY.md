---
phase: 05-user-schema-email-password-auth
plan: 05
subsystem: backend/auth
tags: [auth, router, schemas, pydantic, fastapi, cookies, envelope]
dependency_graph:
  requires:
    - "05-01"   # Settings: cookie_secure, refresh_reuse_window_seconds
    - "05-02"   # core/redis.py get_redis dep, core/audit.py emit, clear_session_cookies sibling
    - "05-03"   # auth/models.py User ORM (id/role/full_name/email/telegram_chat_id)
    - "05-04"   # auth/service.py authenticate / issue_tokens / rotate_refresh / revoke_* (PARALLEL — wave 3 sibling worktree)
  provides:
    - "/api/v1/auth/login + /refresh + /logout + /logout-all + /me endpoint surface"
    - "LoginRequest / LoginResponse / UserPublic / MeResponse contract DTOs"
    - "ResponseEnvelope[X] declared on every Phase 5 auth route (D-14)"
    - "/refresh cookie-based identity (NOT get_current_user) preserving refresh-after-access-expiry semantics"
  affects:
    - "Phase 6 RBAC + CSRF wiring (CSRF-02 list excludes /login + /refresh as already-built)"
    - "Phase 9 OpenAPI codegen (LoginRequest / MeResponse become typed TS types in packages/api-client)"
    - "Phase 10 admin-web wiring (frontend hits these endpoints first)"
tech_stack:
  added:
    - "email-validator>=2.0 (required by Pydantic EmailStr — Pydantic ships email validation as optional extra)"
  patterns:
    - "Pydantic v2 ContractModel hierarchy: RequestContract (extra='forbid') for input, ResponseData (extra='ignore') for output"
    - "to_camel alias generator inherited from ContractModel — Python snake_case ↔ wire camelCase"
    - "FastAPI response_model=ResponseEnvelope[X] declared explicitly per endpoint (D-14, no middleware)"
    - "Annotated[Type, Depends(...)] dependency injection pattern from Phase 4 health.py + dependencies.py"
    - "cast(User, user) at /me to cross from CurrentUser Protocol (id+role only) to full SA User row — safe because composition root register_user_loader fixes the loader"
    - "EmailStr with Pydantic Field(min_length=12) at the contract boundary — service layer never sees < 12 char password"
key_files:
  created: []
  modified:
    - "apps/backend/app/modules/auth/schemas.py (was placeholder; replaced with 4 Pydantic models)"
    - "apps/backend/app/modules/auth/router.py (was placeholder; replaced with 5 endpoint declarations)"
    - "apps/backend/pyproject.toml (added email-validator>=2.0)"
    - "apps/backend/uv.lock (regenerated with email-validator==2.3.0 + dnspython==2.8.0)"
decisions:
  - "Used `cast(User, user)` at /me rather than widening CurrentUser Protocol with email/full_name/telegram_chat_id — Phase 4 D-24 deliberately keeps the Protocol minimal; the cast is the documented escape hatch for the route that needs the full row"
  - "Added email-validator as a top-level project dependency rather than `pydantic[email]` extras — uv tracks it more cleanly and `pydantic[email]` would be a no-op (Pydantic 2.11+ already declares the optional dep)"
  - "`/refresh` declares `response_model=ResponseEnvelope[None]` — the new tokens travel in cookies; the body is empty `data: null` so frontend's TanStack Query mutation can ignore it but OpenAPI codegen still produces a typed wrapper"
  - "`/logout` keeps `Depends(get_current_user)` (NOT cookie-only) — logout from an unauthenticated session returns 401, not 200. This is deliberate per the threat model: untrusted clients should not be able to clear cookies as a side-channel; logout is idempotent only for AUTHENTICATED callers (T-05.05-06 mitigation)"
metrics:
  duration: "~6 minutes"
  completed: "2026-05-02"
  task_count: 2
  file_count: 4
---

# Phase 5 Plan 5: Auth Router + Schemas Summary

## One-Liner

Wave-3 parallel implementation of the Phase 5 auth contract layer: 4 Pydantic schemas (LoginRequest/LoginResponse/UserPublic/MeResponse) and 5 thin endpoint wrappers (/login, /refresh, /logout, /logout-all, /me) all declaring `response_model=ResponseEnvelope[X]` per D-14.

## What Was Built

**Schemas (`apps/backend/app/modules/auth/schemas.py`):**

- `LoginRequest(RequestContract)` — `email: EmailStr`, `password: str = Field(min_length=12)`. `extra='forbid'` is inherited from `RequestContract` so unknown JSON keys produce 422 (T-05.05-02 mitigation).
- `UserPublic(ResponseData)` — `id: UUID`, `role: Role`, `full_name: str`. Wire form: `{ id, role, fullName }`. Deliberately no email / no telegram_chat_id / no password_hash (T-05.05-10 mitigation — login response leaks the minimum).
- `LoginResponse(ResponseData)` — `user: UserPublic`. Wraps `UserPublic` so the envelope shape is `{ data: { user: { id, role, fullName } } }`.
- `MeResponse(ResponseData)` — `id`, `role`, `full_name`, `email`, `has_telegram: bool`. The `has_telegram` derived flag (T-05.05-04 mitigation) keeps the raw `telegram_chat_id` BIGINT off the wire even though the User row has it.

camelCase wire format is automatic via the `to_camel` alias generator on `ContractModel` (Phase 4 D-09); Python identifiers stay snake_case. Roundtrip verified: `MeResponse(...).model_dump(by_alias=True)` produces `fullName` + `hasTelegram`.

**Router (`apps/backend/app/modules/auth/router.py`):**

5 endpoints, fully replacing the Phase A placeholder:

| Method | Path | Body / Source of identity | Dependencies |
| --- | --- | --- | --- |
| POST | `/login` | `LoginRequest` body (email + password) | `get_db` + `get_redis` |
| POST | `/refresh` | `sz_refresh` cookie (read directly via `request.cookies.get`) | `get_db` + `get_redis` |
| POST | `/logout` | `sz_refresh` cookie if present | `get_current_user` + `get_db` + `get_redis` |
| POST | `/logout-all` | `user.id` from access token | `get_current_user` + `get_db` + `get_redis` |
| GET | `/me` | `user` from access token | `get_current_user` |

All 5 declare `response_model=ResponseEnvelope[X]` per D-14 (no envelope-wrapping middleware). `/refresh` deliberately does NOT take `Depends(get_current_user)` — an expired access token must NOT block a refresh call (T-05.05-01 mitigation). When the `sz_refresh` cookie is missing, `/refresh` raises `InvalidAccessToken("missing_refresh_cookie")` → 401.

`/logout` is idempotent: if the refresh cookie is absent or already revoked, it still calls `clear_session_cookies(response, secure=settings.cookie_secure)` so the browser ends in a clean state. The `Depends(get_current_user)` parameter is kept (named `_user` to silence "unused" warnings) — logout from an unauthenticated session returns 401, not 200, by design.

`/me` uses `cast(User, user)` because `CurrentUser` Protocol exposes only `id` + `role` (Phase 4 D-24). The runtime instance IS a `User` because `app.main.create_app()` calls `register_user_loader(load_user_by_id)` (Plan 06). Without the cast, mypy strict flags access to `email` / `full_name` / `telegram_chat_id`. Documented as accepted risk T-05.05-08.

**Dependency change (`pyproject.toml` + `uv.lock`):**

Added `email-validator>=2.0` as a top-level dependency. Pydantic 2.11+ declares it as an optional dep that fires `ImportError` only when an `EmailStr` field is actually instantiated — Phase 5 is the first phase that uses `EmailStr`, so the install gate flips here. uv resolved to `email-validator==2.3.0` + transitively pulled in `dnspython==2.8.0`.

## Tasks Completed

| Task | Name | Commit | Files |
| --- | --- | --- | --- |
| 1 | Implement Pydantic schemas (LoginRequest/LoginResponse/UserPublic/MeResponse) | `6e1f33f` | `apps/backend/app/modules/auth/schemas.py`, `apps/backend/pyproject.toml`, `apps/backend/uv.lock` |
| 2 | Implement auth router with /login /refresh /logout /logout-all /me | `23ee99a` | `apps/backend/app/modules/auth/router.py` |

## Verification

### Task 1 (schemas) — all pass

- `grep` of every required substring (`class LoginRequest(RequestContract)`, `class UserPublic(ResponseData)`, `class LoginResponse(ResponseData)`, `class MeResponse(ResponseData)`, `password: str = Field(min_length=12)`, `has_telegram: bool`) — all present.
- `uv run mypy app/modules/auth/schemas.py` — `Success: no issues found in 1 source file`.
- `uv run ruff check app/modules/auth/schemas.py` — `All checks passed!`.
- Runtime: `LoginRequest(email='a@b.co', password='hunter22hunter22')` succeeds; `LoginRequest(..., password='short')` raises `ValidationError` (min_length=12 enforced); `MeResponse(...).model_dump(by_alias=True)` includes `fullName` + `hasTelegram` (camelCase wire confirmed).

### Task 2 (router) — structural verifications pass; symbol-resolution verifications deferred to post-merge

**Pass in this worktree:**

- All 5 endpoints declared with the correct decorator + path + `response_model=ResponseEnvelope[X]` (verified by grep at the precise line numbers).
- The substring `response_model=ResponseEnvelope[` appears exactly 5 times across the file (verified by `grep -c`).
- `/refresh` reads `request.cookies.get("sz_refresh")` and raises `InvalidAccessToken("missing_refresh_cookie")` when absent.
- `/refresh` does NOT depend on `get_current_user`; `/login` does NOT either; `/logout`, `/logout-all`, `/me` DO.
- `/logout` always calls `clear_session_cookies(response, secure=...)` regardless of whether `sz_refresh` was present.
- `uv run lint-imports` — `Contracts: 3 kept, 0 broken.` (core ⊥ modules / modules-independent / integrations ⊥ modules all green).
- `uv run ruff check app/modules/auth/router.py` — `All checks passed!`.

**Deferred to post-merge with parallel plan 05-04:**

- `uv run mypy app/modules/auth/router.py` reports 5 `attr-defined` errors for symbols (`authenticate`, `issue_tokens`, `rotate_refresh`, `revoke_session`, `revoke_all_sessions`) that Plan 05-04 produces in `app/modules/auth/service.py` in a sibling worktree (wave 3 parallel execution). These will resolve when the orchestrator merges both worktrees.
- `uv run python -c "from app.modules.auth.router import router"` — same root cause: `ImportError: cannot import name 'authenticate' from 'app.modules.auth.service'`. Will pass post-merge.
- The router signature was authored against the contract in `05-PATTERNS.md` ("app/modules/auth/service.py") and `05-04-PLAN.md` `must_haves.artifacts` (which lists the exact 7 exports, 5 of which we import). No drift expected.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 — Critical functionality] Added `email-validator` dependency**

- **Found during:** Task 1 verification (initial `from pydantic import EmailStr` import succeeded but `LoginRequest(email='a@b.co', ...)` raised `ImportError: email-validator is not installed, run \`pip install 'pydantic[email]'\``).
- **Issue:** Pydantic 2.11+ ships `EmailStr` but defers the actual validator import to instantiation time. Without `email-validator`, every `/login` and `/me` codepath would 500 at runtime even though imports succeed.
- **Fix:** Added `"email-validator>=2.0"` to `[project].dependencies` in `apps/backend/pyproject.toml` and ran `uv sync` (regenerated `uv.lock`).
- **Files modified:** `apps/backend/pyproject.toml`, `apps/backend/uv.lock`.
- **Commit:** Folded into `6e1f33f` (Task 1 commit) since it's required for the schemas to function.
- **Plan note:** The Plan 05-05 author flagged this in the Task 1 `<action>` notes: "if `email-validator` is not present, the import will fail at runtime. If so, add `\"email-validator>=2.0\",` to dependencies in this task as well." Followed exactly.

**2. [Rule 1 — Bug] Removed literal `response_model=ResponseEnvelope[X]` from docstring**

- **Found during:** Task 2 verification (initial `grep -c 'response_model=ResponseEnvelope\['` returned 6, not 5).
- **Issue:** The acceptance criterion `grep ... | wc -l | grep -E '^\s*5$'` requires the literal substring to appear exactly 5 times. The original module-level docstring contained `response_model=ResponseEnvelope[X]` as descriptive prose, which counted as a 6th match.
- **Fix:** Rephrased the docstring to "Endpoints declare ResponseEnvelope[X] as their response_model per Phase 4 D-14 — no envelope-wrapping middleware." Same meaning, no false-positive grep hit.
- **Files modified:** `apps/backend/app/modules/auth/router.py`.
- **Commit:** Folded into `23ee99a` (Task 2 commit) since the file was not yet committed when the issue was found.

## Threat Mitigations Verified

| Threat ID | Disposition | How mitigated in code |
| --- | --- | --- |
| T-05.05-01 (Spoofing — /refresh without get_current_user) | mitigate | `/refresh` reads `sz_refresh` directly; no `Depends(get_current_user)` parameter. |
| T-05.05-02 (Tampering — extra fields) | mitigate | `LoginRequest` extends `RequestContract` which sets `extra='forbid'`. |
| T-05.05-03 (Repudiation — missing IP) | accept | `request.client.host if request.client is not None else None` threads `ip=None` to `authenticate(...)`. |
| T-05.05-04 (Info disclosure — telegram_chat_id) | accept | `MeResponse.has_telegram: bool` is the only telegram-related field on the wire. |
| T-05.05-05 (Info disclosure — password in logs) | mitigate | Router never logs `payload.password`; emit happens inside `authenticate(...)` (Plan 05-04) which only emits `email` per D-21. |
| T-05.05-06 (DoS — unauthenticated /logout floods) | mitigate | `Depends(get_current_user)` short-circuits 401 before any DB / Redis op. |
| T-05.05-07 (DoS — bad /refresh cookies) | mitigate | `rotate_refresh`'s SHA-256 + indexed UNIQUE lookup is single-query (Plan 05-04 responsibility). |
| T-05.05-08 (EoP — /me cast to User) | accept | Documented compositional invariant: `register_user_loader(load_user_by_id)` is wired in `app.main.create_app()` (Plan 06). If the loader changes, the cast becomes unsafe — revisit. |
| T-05.05-09 (Tampering — response_model bypass) | mitigate | Every route declares `response_model=ResponseEnvelope[X]` (5/5 verified by grep). |
| T-05.05-10 (Info disclosure — LoginResponse leaks) | mitigate | `UserPublic` exposes only `id` / `role` / `fullName` — no email, no telegram_chat_id, no password_hash. |

No new threat surface introduced beyond the plan's threat register.

## Known Stubs

None. Both files are fully implemented; the open dependency is on parallel plan 05-04 (`app/modules/auth/service.py` — symbol resolution at merge time), which is itself fully planned, not a stub.

## Self-Check: PASSED

**Files exist:**

- `apps/backend/app/modules/auth/schemas.py` — FOUND
- `apps/backend/app/modules/auth/router.py` — FOUND
- `apps/backend/pyproject.toml` — FOUND (modified)
- `apps/backend/uv.lock` — FOUND (modified)
- `.planning/phases/05-user-schema-email-password-auth/05-05-SUMMARY.md` — FOUND (this file)

**Commits exist:**

- `6e1f33f` — FOUND (Task 1)
- `23ee99a` — FOUND (Task 2)
