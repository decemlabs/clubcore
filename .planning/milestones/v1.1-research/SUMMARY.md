# Project Research Summary — v1.1 Auth + Clients

**Project:** Sportzal — single-gym CRM (РФ/СНГ)
**Domain:** Two-channel auth (Telegram bot deep-link + email/password) + first business CRUD (Clients) on a FastAPI modular monolith with admin-web HTTP wiring through a typed `packages/api-client`
**Researched:** 2026-05-01
**Confidence:** HIGH

---

## Executive Summary

The v1.1 milestone adds a complete first business slice on top of the v1.0 skeleton: an authentication system with Telegram bot deep-link OTP as the primary channel and email/password as fallback, server-side RBAC at parity with the existing frontend `can(role, action, resource)` matrix, and a fully-functional `clients` CRUD with soft-delete, paginated list, and ILIKE search. The backend boundary is then exposed to `apps/admin-web` through a thin, typed `packages/api-client` generated from the FastAPI `openapi.json` — leaving all other domains (memberships, visits, billing, etc.) on the existing mock services until their own milestones land.

Research converged on a tight, low-novelty stack that reuses what the lockfile already pulls in. Three new Python deps are required (`pyjwt`, `argon2-cffi`, `python-telegram-bot`) and one new JS devDependency (`openapi-typescript`). Several superficially attractive libraries were rejected with prejudice: **passlib** (5+ years stale, broken by bcrypt 5.0), **python-jose** (107 open issues, lagging on `cryptography`), **fastapi-csrf-protect**, **openapi-fetch**, **aiogram** (parallel HTTP stack), **Casbin/Oso** (overkill for a 9-entry static matrix). Several superficially attractive cross-research conflicts were resolved in this synthesis (FEATURES.md mentioned "passlib via argon2-cffi" and "python-jose or pyjwt" — STACK wins: drop passlib entirely, pick PyJWT).

The dominant risk profile is concentrated in three areas: (1) cookie + refresh-token semantics (SameSite, Secure-in-dev, single-flight rotation, reuse detection, plaintext-in-Redis), (2) the cross-module boundary problem — `clients/router.py` needs `require_permission` but `import-linter` forbids `clients → auth`, resolved by lifting RBAC primitives into `core/permissions.py` and using a registered-loader Protocol for `get_current_user`, and (3) the OpenAPI / codegen pipeline (lifespan-safe export, drift CI check, snake↔camel boundary, Optional vs nullable in TS). All three are addressable with patterns that the research files specify down to file-and-function level.

---

## Key Findings

### Recommended Stack

The existing `apps/backend/uv.lock` already covers FastAPI 0.115+, SQLAlchemy 2.0 async, Alembic, Pydantic v2, Postgres asyncpg, Redis 5.3.1 (transitively via ARQ 0.28), structlog, httpx — roughly 80% of what v1.1 needs.

**New Python dependencies (`apps/backend/pyproject.toml`):**
- `pyjwt>=2.12.1,<3` — JWT encode/decode (HS256). Picked over python-jose (107-issue backlog, slow cryptography pin updates) and authlib (full OAuth scope creep). FastAPI tutorial migrated off jose to PyJWT in 2024.
- `argon2-cffi>=25.1.0,<26` — direct password hashing, no `passlib` wrapper. Argon2id is OWASP's 2026 default. **Wrap in `asyncio.to_thread`** because default params (~50ms) shouldn't block the event loop.
- `python-telegram-bot>=22.7,<23` — bot client. Picked over aiogram because ptb 22 uses **httpx** (already locked); aiogram pulls aiohttp as a parallel HTTP stack inside the same process.

**New JS devDependency:** `openapi-typescript@^7.13.0` — types-only codegen. Picked over `openapi-fetch`, `orval`, and `openapi-generator-cli` because the swap-seam contract `UI → TanStack Query hook → services.X → { mock | http } impl` already owns keys/optimistic updates/error mapping.

**Reject list:** `passlib`, `python-jose`, `authlib`, `pyrogram`, `aiogram`, `aioredis`, `fastapi-csrf-protect`, `openapi-fetch`, `openapi-generator-cli`, `orval`, **Keycloak/Auth0/OIDC**, **Casbin/Oso/OPA**, **SQLAlchemy-Continuum**.

**Cross-research conflict resolutions (load-bearing for the planner):**
- FEATURES.md mentions "`python-jose` or `pyjwt`" and "`passlib[argon2]`". STACK.md is authoritative: **PyJWT, no passlib, argon2-cffi direct.**
- ARCHITECTURE.md's pyproject diff lists `pyjwt` only — aligned.
- ARCHITECTURE.md mentions both `aiogram` and `ptb` ambiguously in handler pseudocode. STACK and PITFALLS converge on **`python-telegram-bot`**.

### Expected Features

**Must have (table stakes — locked into v1.1 scope):**

*Auth:*
- Telegram bot deep-link OTP (`https://t.me/<bot>?start=<token>` → bot DMs 6-digit code → user pastes into `/login` form). Long-polling acceptable in dev; webhook deferred.
- Email/password fallback with Argon2id, admin-provisioned (no public `/register`), min 12-char policy, rate-limited (5/15min/email).
- JWT access (15min) + refresh (30d) in **two separate httpOnly cookies**; refresh path-scoped to `/api/v1/auth`.
- Refresh **rotation with family-id reuse-detection**; on detected reuse → revoke entire family. Server-side session record in Redis (`session:{user_id}:{family_id}`).
- CSRF double-submit cookie + `X-CSRF-Token` header on mutating endpoints (skip on `/auth/login` and Telegram callback).
- Idle timeout 7d; absolute timeout = refresh lifetime (30d).

*RBAC:*
- `Role = 'owner' | 'reception'` enum mirrored in DB.
- `OWNER_ONLY` matrix at byte-level parity with `apps/admin-web/src/shared/session/can.ts` (9 entries).
- `require_permission(action, resource)` as a FastAPI **dependency** (not a service-body call).
- 403 response shape matches frontend's `DomainError { code, message, fields? }`.

*Clients schema:*
- Branded `id: ClientId` (UUIDv4), ФИО triple, `phone` (E.164, partial unique on alive rows), `birthday?`, `gender?`, `email?`, `notes?`, audit timestamps, `deleted_at?` (soft-delete only), `created_by_user_id` FK.
- `tags: text[]` with GIN index.
- `telegram_user_id` (BIGINT nullable UNIQUE) — added now to avoid future migration.
- `emergency_contact: jsonb`.
- `pg_trgm` GIN on `lower(last_name)` and `lower(first_name)`.

*Endpoints:*
- `POST /auth/login`, `POST /auth/telegram/start`, `POST /auth/telegram/verify`, `POST /auth/refresh`, `POST /auth/logout`, `POST /auth/logout-all`, `GET /auth/me`.
- `GET/POST/PATCH/DELETE /api/v1/clients`, `GET /api/v1/clients/{id}` with `{items,total,page,pageSize}` pagination, `q=` ILIKE, filters by tag/gender/signup-date/has_telegram, sort by `created_at DESC` (default) or `last_name ASC`.

*Cross-cutting:*
- `audit_log` table + writes from auth flows + clients mutations. **Read endpoint deferred to v1.2** but the table must ship in v1.1.

**Should have (deferred to v1.2+):** Active-sessions UI, audit log read endpoint, password reset via Telegram, HIBP pwned-password check, webhook-based bot.

**Defer (v2+):** Public self-registration, photo upload, bulk CSV import, last-visit filter, multi-tenancy.

**Anti-features explicitly rejected:** SMS OTP, Telegram Login Widget, email password reset, forced password rotation, password complexity rules, account lockout, CAPTCHA, localStorage tokens, stateless-only JWT, hard delete, custom field schema, full-text search, saved filters, CSV export, policy engine, dynamic role creation, multi-tenancy, RLS.

### Architecture Approach

The architecture is constrained by three `import-linter` contracts already enforced in v1.0: `core ⊥ modules`, `modules independent`, `integrations ⊥ modules`. The central architectural problem of v1.1 is that RBAC naturally cuts across modules. The resolution is **lift RBAC primitives into `core`**.

**Major components:**

1. **`app/core/permissions.py` (NEW)** — `Role`/`Action`/`Resource` StrEnums, `OWNER_ONLY: frozenset` matrix, `can()`. Mirrors `apps/admin-web/src/shared/session/can.ts` byte-for-byte.
2. **`app/core/security.py` (FILL)** — JWT encode/decode (HS256, 30s leeway), Argon2id `hash_password`/`verify_password`, deep-link/OTP code generators, SHA-256 hashing for refresh tokens.
3. **`app/core/dependencies.py` (FILL)** — `get_current_user` and `require_permission` as FastAPI dependencies. Uses **registered-loader Protocol pattern**: `core/dependencies.py` defines `class CurrentUser(Protocol)` and `register_user_loader(loader)`; `app/main.py` (composition root, exempt from import-linter) calls `register_user_loader(load_user_by_id)` at startup.
4. **`app/modules/auth`** — `models.py` (User, RefreshToken, OtpCode), `schemas.py`, `service.py`, `repository.py`, `router.py`. Refresh tokens **hybrid**: full row in Postgres + Redis index `auth:session:{user_id}:{family_id}` for fast revoke.
5. **`app/modules/clients`** (RENAME from `members` placeholder) — only imports from `core` for `require_permission`; no auth import.
6. **`app/integrations/telegram/{bot,sender,handlers}.py`** — pure adapter. Cross-module callback (bot → auth) goes through a **Protocol injected at startup**, NOT a direct import.
7. **`app/workers/telegram_bot.py` (NEW)** — standalone process running `Application.run_polling()`. **NOT an ARQ task**. Added to `docker-compose.yml` as a fourth service.
8. **`scripts/export_openapi.py` + `apps/backend/openapi.json` (checked in)** — `app.openapi()` dumped via lifespan-safe path; CI runs `git diff --exit-code openapi.json`.
9. **`packages/api-client/`** — single thin generated package. `src/schema.d.ts` (gitignored) + ~80 LOC hand-rolled `fetcher.ts` (cookie credentials, single-flight refresh, typed `ApiError`).
10. **`apps/admin-web/src/features/auth/*` + wiring** — calls go through swap-seam (`VITE_API_MODE=http` for `/login` and `/clients/*`; other modules stay on mocks).

**Key decisions:**
- UUID PKs with Postgres native `gen_random_uuid()` (PG13+, no `pgcrypto`).
- `Base.metadata` naming convention set BEFORE first migration.
- **Pagination contract drift fix:** backend currently uses `limit/offset`; flip to `{items, total, page, pageSize}` to match frontend (frontend is locked).
- **camelCase JSON wire format** via Pydantic `alias_generator=to_camel` + `populate_by_name=True`.
- **Soft-delete via partial unique index:** `Index("uq_clients_phone_alive", "phone", unique=True, postgresql_where=text("deleted_at IS NULL"))`.
- **Module rename:** `app/modules/members/` → `app/modules/clients/`.

### Critical Pitfalls

1. **Alembic naming convention not set BEFORE first migration (#11)** — set `MetaData(naming_convention=...)` in `app/core/database.py`. CI gate: autogenerate on clean DB must produce empty migration.
2. **Refresh-token rotation race causes mass logout (#4)** — fix on **both sides**: server allows ~5s reuse-window returning the same new pair; client (api-client fetcher) implements module-scoped single-flight `Promise<void> | null`.
3. **Soft-delete partial unique index missing (#13)** — use `postgresql_where=text("deleted_at IS NULL")` from day one.
4. **Frontend `can()` ↔ backend `OWNER_ONLY` drift (#27)** — daily/PR CI parity test imports both and compares. Plus a route-introspection test asserting `require_permission` is wired on every protected route.
5. **`require_permission` as a service-body call instead of `Depends` (#29)** — mandate `Depends(require_permission(...))` on the route signature; AST grep / lint to forbid in service bodies.

Honourable mentions: Cookie `Secure=True` silently dropped in dev HTTP (#2), SameSite=Strict breaks Telegram return navigation (#1), plaintext refresh tokens in Redis (#5), Telegram DM blocked silent failure (#10), CSRF surface re-introduced by cookie auth (#3), OTP brute-force without max-attempts (#9), login redirect loop on refresh failure (#30).

---

## Implications for Roadmap

The three research docs converged on the same logical order. Merged ordering:

### Phase 1: Auth Foundations
**Rationale:** All later work depends on JWT primitives, cookie matrix, RBAC enums, SQLAlchemy mixins, and the cross-module pattern.
**Delivers:** `core/security.py` (JWT, argon2, code generators); `core/permissions.py` (enums, OWNER_ONLY, `can`); `core/database.py` extended with mixins AND `MetaData(naming_convention=...)`; `core/dependencies.py` (Protocol-based `get_current_user` + `register_user_loader` + `require_permission`); cookie-flag ADR (`Lax`, `Secure` env-driven with prod assertion); CSRF double-submit ADR; cross-module Protocol/loader ADR; pagination contract flip to `{items,total,page,pageSize}`; Pydantic v2 base schema with `alias_generator=to_camel`.
**Avoids pitfalls:** #1, #2, #5, #11, #12, #19, #25, #32.
**Research flag:** standard patterns; no deeper research needed.

### Phase 2: User Schema + Email/Password Auth
**Rationale:** Email/password is simpler than Telegram and doesn't need a separate process; gets JWT + cookies + rotation flowing end-to-end before adding the OTP channel.
**Delivers:** `auth/models.py` (User, RefreshToken, OtpCode); first business migration `0001_auth.py` with naming convention; `auth/{schemas,service,repository,router}.py` with `/auth/login`, `/auth/refresh` (with family rotation + reuse window), `/auth/logout`, `/auth/logout-all`, `GET /auth/me`; `app/main.py` wires routers + `register_user_loader`; server-side single-flight reuse window; `revoke_all_sessions` on password change; pytest SAVEPOINT-based session fixture; settings-level `cookie_secure` flag with prod assertion; seed script creating one owner user.
**Avoids pitfalls:** #3 (CSRF), #4 server-side, #6, #16, #18.
**Research flag:** standard.

### Phase 3: RBAC Wiring + Tests
**Rationale:** Before any business endpoint lands, prove `require_permission` is callable as `Depends`, verify 401/403/200 paths, ensure OWNER_ONLY matrix is byte-equal with frontend.
**Delivers:** Wire `Depends(require_permission(...))` examples; integration tests (401/403/200); **parity test** vs `apps/admin-web/src/shared/session/can.ts`; route-introspection test enumerating `app.routes`; AST/grep lint forbidding `require_permission` in service bodies; documented "list visibility ⇒ detail visibility" rule.
**Avoids pitfalls:** #19, #27, #28, #29.
**Research flag:** none — purely mechanical.

### Phase 4: Telegram OTP Channel
**Rationale:** Highest risk in the milestone (external API, separate process, polling, DM-blocked edge cases). Done after JWT pipeline is proven.
**Delivers:** `integrations/telegram/{bot,sender,handlers}.py` (ptb 22 client, send adapter, `/start <token>` handler); `workers/telegram_bot.py` standalone polling entry-point; `workers/tasks/notifications.py` ARQ `send_otp` task; `auth/service.py` adds `create_otp_request` + `consume_otp` (6-digit `secrets.randbelow`, SHA-256 hash, max 5 attempts, 5min OTP TTL, 10min deep-link TTL); `POST /auth/otp/request|verify|status`; cross-module callback via Protocol DI; `docker-compose.yml` new `telegram-bot` service with `restart: unless-stopped`; `.env.example` adds Telegram vars; DM-blocked → 409 `bot_not_started` with deep-link in response; per-IP rate limit + per-user attempt counter.
**Avoids pitfalls:** #7, #8 (sidestepped by bot-deep-link), #9, #10, #20.
**Research flag:** **NEEDS DEEPER RESEARCH** — ptb 22.x deep-linking exact API, error class hierarchy, polling vs webhook toggle. Pull `python-telegram-bot` via Context7 in Phase 4 planning.

### Phase 5: Clients Module
**Rationale:** First business module. Cannot land before auth (every endpoint uses `Depends(require_permission(...))`).
**Delivers:** `modules/clients/{models,schemas,service,repository,router}.py`; migration `0002_clients.py` enables `pg_trgm`; `clients` table with all table-stakes fields; `tags text[]` GIN; `lower(last_name)`/`lower(first_name)` GIN trgm; **partial unique index** on `phone WHERE deleted_at IS NULL`; `emergency_contact jsonb`; reserved `telegram_user_id`; `audit_log` table + service helper called from auth + clients mutations; `GET /api/v1/clients` (pagination, ILIKE, filters, sorts) with **repository helpers (`list_alive`, `get_alive`)** so soft-delete filter cannot be forgotten; full CRUD with role-appropriate `require_permission`; `DELETE` is soft-delete only; ON DELETE RESTRICT for any future FKs.
**Avoids pitfalls:** #13, #14, #15, #17 (documented).
**Research flag:** none.

### Phase 6: OpenAPI Pipeline + `packages/api-client`
**Rationale:** Backend must be stable before codegen lands; codegen must land before admin-web wiring.
**Delivers:** `scripts/export_openapi.py` (`create_app().openapi()` with `indent=2, sort_keys=True`, lifespan-safe); `apps/backend/openapi.json` checked in; CI drift step; `packages/api-client/` (`openapi-typescript` devDep + `codegen` script; gitignored `schema.d.ts`; `fetcher.ts` ~80 LOC with cookie credentials, retry policy excluding `/auth/*`, single-flight refresh, typed `ApiError`); TS contract test asserting no `snake_case` properties; hand-written `Page<T>` helper; Optional → nullable convention test.
**Avoids pitfalls:** #4 client-side, #22, #23, #24, #25, #26.
**Research flag:** **NEEDS DEEPER RESEARCH** — `openapi-typescript` 7.13 CLI flags, FastAPI `app.openapi()` lifespan-safety with Pydantic v2 alias generators. Pull both via Context7.

### Phase 7: admin-web Auth + Clients Wiring
**Rationale:** Last in the chain because it consumes everything else.
**Delivers:** `shared/api/services/http/{auth,clients}.ts` implementing existing service contracts via `@sportzal/api-client`; `shared/api/contracts/index.ts` Zod for `AuthService`/`ClientsService`; `features/auth/*` (login form with email/password tab + Telegram tab + OTP input + polling); TanStack Router `beforeLoad` redirect-back via search; TanStack Query `retry` excluding 401; single-flight refresh in fetcher; one-shot `/login` redirect with module flag; form 422 → RHF `setError` per field; ESLint rule banning `fetch(` outside api-client + http services + negative-test fixture; `VITE_API_MODE=http` only for `/login` and `/clients/*`; structlog redactor for secrets with snapshot test.
**Avoids pitfalls:** #21, #22, #30, #31.
**Research flag:** **LIGHT** — TanStack Query 5.x retry semantics + TanStack Router protected-route idiom via Context7.

### Phase Ordering Rationale
- **Foundations before features:** Phase 1 settles cookie matrix, Alembic naming, cross-module pattern, pagination contract — extremely expensive to retrofit.
- **Email/password before Telegram (Phase 2 → 4):** in-process JWT flow proven without external API noise.
- **RBAC stub (Phase 3) before any business endpoint:** parity test green before clients routes use `require_permission` for real.
- **Clients (Phase 5) before frontend wiring (Phase 7):** OpenAPI surface stable before codegen, codegen stable before HTTP services land in admin-web.
- **OpenAPI pipeline (Phase 6) is its own phase:** export script + drift CI is non-trivial.
- **Audit log table ships with clients (Phase 5):** retrofitting writes into 6+ endpoints later is exactly the rework FEATURES.md flagged.

### Research Flags
- **Phase 4 (Telegram OTP):** ptb 22.x deep-linking + error classes + polling/webhook toggle + composition root.
- **Phase 6 (OpenAPI + api-client):** `openapi-typescript` 7.13 CLI behavior + FastAPI `app.openapi()` lifespan-safety.
- **Phase 7 (admin-web wiring) — light:** TanStack Query 5 retry + Router redirect-search.

Phases skipping deep research: Phase 1 (Foundations), Phase 2 (Email/Password), Phase 3 (RBAC Wiring), Phase 5 (Clients).

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | **HIGH** | Versions verified against PyPI/npm 2026-05-01; rationale grounded in maintenance status, FastAPI tutorial alignment, and existing lockfile. |
| Features | **HIGH** | OWASP, NIST 800-63B, FastAPI docs; gym-CRM field set verified across 5 vendors; РФ market constraints already locked. |
| Architecture | **MEDIUM-HIGH** | Codebase facts HIGH; recommended cross-module Protocol/loader pattern is MEDIUM (idiomatic but not unique). |
| Pitfalls | **HIGH** | 32 pitfalls anchored to specific files/contracts with code-level mitigations and verification tests. |

**Overall confidence:** HIGH.

### Gaps to Address
1. **Cookie strategy in production:** Phase 1 ADR locks dev choice (Lax) and explicitly defers prod choice (same-origin vs split-origin + `SameSite=None; Secure`) to deployment milestone — but writes the CSRF double-submit machinery now so the prod flip is just config.
2. **mypy stubs for PyJWT:** verify on first `mypy --strict` run in Phase 1; add `types-pyjwt` only if needed.
3. **redis-py upper bound:** stay at 5.x (ARQ 0.28 caps `<6`); track ARQ issue tracker; bump together when arq lifts cap.
4. **OpenAPI export DB-independence:** Phase 6 acceptance criterion — script runs successfully without DB and produces deterministic byte-stable output across macOS/Linux.
5. **Audit log retention policy:** v1.1 ships writes only; long-term retention (152-ФЗ alignment, partition pruning) is out of scope. Add TODO note in `audit_log` migration referencing future milestone.
6. **Conflicts already resolved (no further action):**
   - Password lib: drop `passlib`, use `argon2-cffi` directly (FEATURES vs STACK — STACK wins).
   - JWT lib: PyJWT, not python-jose (FEATURES vs STACK — STACK wins).
   - Telegram lib: python-telegram-bot, not aiogram (transport coherence with httpx).
   - Module rename: `members/` → `clients/` (frontend term canonical).
   - Pagination: flip backend to `{items,total,page,pageSize}` + camelCase.

---

## Detailed Research Files

- `.planning/research/STACK.md` — dependency choices, version pins, reject list, integration costs.
- `.planning/research/FEATURES.md` — table-stakes / differentiator / anti-feature breakdown, prioritization matrix, v1.1 launch checklist, out-of-scope carry-overs.
- `.planning/research/ARCHITECTURE.md` — file-and-function-level layout, cross-module RBAC pattern with code samples, build order, files-touched summary, open questions.
- `.planning/research/PITFALLS.md` — 32 pitfalls with phases, prevention code, warning signs, recovery cost; technical-debt patterns; "looks done but isn't" checklist; pitfall-to-phase mapping table.
