# Requirements: Sportzal v1.1 — Auth + Clients

**Defined:** 2026-05-01
**Core Value:** Соло backend-разработчик с AI-агентами должен уметь поэтапно наращивать бизнес-фичи зала на стабильном, архитектурно ограниченном каркасе — без переписывания структуры по мере роста.

This milestone delivers the first business slice on top of the v1.0 skeleton: two-channel authentication (Telegram bot deep-link OTP + email/password), server-side RBAC at parity with the existing frontend `can(role, action, resource)` matrix, full Clients CRUD with soft-delete and ILIKE search, and a typed `packages/api-client` consumed by `apps/admin-web` via `VITE_API_MODE=http` for auth + clients only.

## v1.1 Requirements

### Infrastructure (DB + Tooling)

- [ ] **INFRA-01**: `app/core/database.py` defines `Base` with explicit `MetaData(naming_convention=...)` set BEFORE the first business migration so Alembic produces deterministic constraint names
- [ ] **INFRA-02**: `app/core/database.py` exposes `UUIDPkMixin` (PG-native `gen_random_uuid()`), `TimestampMixin` (`created_at`/`updated_at`), `SoftDeleteMixin` (`deleted_at` indexed)
- [ ] **INFRA-03**: First business Alembic migration `0001_auth.py` creates `users`, `refresh_tokens`, `otp_codes` tables
- [ ] **INFRA-04**: Second business Alembic migration `0002_clients.py` creates `clients` and `audit_log` tables and enables `pg_trgm` extension
- [ ] **INFRA-05**: `app/modules/members/` placeholder is renamed to `app/modules/clients/`; `.importlinter` `modules-independent` contract updated to reflect the rename
- [ ] **INFRA-06**: `docker-compose.yml` adds a `telegram-bot` service (`restart: unless-stopped`) alongside `web` / `worker` / `migrate`; bot reads `TELEGRAM_BOT_TOKEN` from env
- [ ] **INFRA-07**: `apps/backend/pyproject.toml` adds pinned dependencies: `pyjwt>=2.12.1,<3`, `argon2-cffi>=25.1.0,<26`, `python-telegram-bot>=22.7,<23`; `uv lock` regenerated

### Auth — Foundations & Cookies

- [ ] **AUTH-01**: `app/core/security.py` provides JWT encode/decode (HS256, 30-second clock leeway) backed by `settings.jwt_secret`
- [ ] **AUTH-02**: `app/core/security.py` provides Argon2id `hash_password` / `verify_password` wrapped via `asyncio.to_thread`; passwords are never stored in plaintext or any reversible form
- [ ] **AUTH-03**: `app/core/security.py` generates one-time codes (`secrets.randbelow`, 6 digits) and deep-link tokens (`secrets.token_urlsafe(32)`); raw codes are never persisted — only `sha256(code)`
- [ ] **AUTH-04**: Successful login issues two httpOnly Secure cookies — `sz_access` (Path=`/`, Max-Age=900s) and `sz_refresh` (Path=`/api/v1/auth`, Max-Age=2592000s); `Secure` flag is env-driven (true in prod, false in dev HTTP) with prod assertion
- [ ] **AUTH-05**: Refresh tokens are stored hashed (SHA-256) in Postgres `refresh_tokens` table with a `family_id` for rotation; reuse of any token in a family revokes the entire family
- [ ] **AUTH-06**: Server tolerates a ~5-second reuse-window during refresh rotation, returning the same new pair to mitigate parallel-request races
- [ ] **AUTH-07**: Active sessions mirror to Redis (`auth:session:{user_id}:{family_id}`) with TTL = refresh expiry; logout removes the Redis entry and stamps `revoked_at` in Postgres

### Auth — Email/Password Channel

- [ ] **AUTH-EP-01**: User logs in via `POST /api/v1/auth/login` with `{email, password}`; on success, server returns 200 with cookies set and `{user: {id, role, fullName}}`
- [ ] **AUTH-EP-02**: Wrong credentials return 401 with `DomainError { code: "invalid_credentials" }`; the response is timing-equivalent to the success path (no enumeration via response time)
- [ ] **AUTH-EP-03**: Login is rate-limited per email — 5 failed attempts within 15 minutes → 429 `rate_limited`
- [ ] **AUTH-EP-04**: No public self-registration endpoint; one initial owner user is created by `scripts/seed_demo_data.py` (email + Argon2id password from env)
- [ ] **AUTH-EP-05**: Password minimum length is 12 characters; no complexity rules, no forced rotation, no account lockout (per NIST 800-63B 2024)

### Auth — Telegram OTP Channel

- [ ] **AUTH-TG-01**: User requests a Telegram-OTP login via `POST /api/v1/auth/telegram/start`; server returns `{deepLinkUrl: "https://t.me/<bot>?start=<token>", deepLinkToken}` with the deep-link token TTL = 10 minutes
- [ ] **AUTH-TG-02**: When user presses `/start <token>` in the bot, the bot worker binds `telegram_chat_id` to the OTP record and DM-sends a 6-digit code with TTL = 5 minutes; max 5 verification attempts per code
- [ ] **AUTH-TG-03**: User polls `GET /api/v1/auth/telegram/status?token=<deep_link_token>` to learn when the bot has bound the chat (frontend prompts for the code only after `bound: true`)
- [ ] **AUTH-TG-04**: User verifies via `POST /api/v1/auth/telegram/verify` with `{token, code}`; on success the user is upserted (matched by `telegram_chat_id`) and a session is issued just like the email/password path
- [ ] **AUTH-TG-05**: Bot worker runs as a separate process (`python -m app.workers.telegram_bot`) using `python-telegram-bot` long-polling; it is NOT an ARQ task. ARQ is used only for fire-and-forget jobs (e.g. send-OTP retry)
- [ ] **AUTH-TG-06**: When the bot detects "user has not started a chat yet" (`Forbidden: bot was blocked` / `chat not found`), the verify endpoint returns 409 `bot_not_started` with the deep-link URL so the frontend can re-display it

### Auth — Logout & /me

- [ ] **AUTH-LO-01**: `POST /api/v1/auth/logout` revokes the current session (deletes Redis entry, stamps `revoked_at` in DB) and clears both cookies
- [ ] **AUTH-LO-02**: `POST /api/v1/auth/logout-all` revokes every active session for the current user
- [ ] **AUTH-LO-03**: Password change (deferred admin endpoint) revokes all existing sessions for the affected user
- [ ] **AUTH-LO-04**: `GET /api/v1/auth/me` returns the current user's `{id, role, fullName, email, hasTelegram}`; 401 if unauthenticated

### CSRF

- [ ] **CSRF-01**: Server sets a non-httpOnly `sportzal_csrf` cookie (32-byte hex, `Secure`, `SameSite=Lax`) on successful login; the frontend fetch wrapper echoes the value via the `X-CSRF-Token` header on every mutating request
- [ ] **CSRF-02**: A `Depends(verify_csrf)` is applied at router level on every POST/PATCH/DELETE route except `/auth/login`, `/auth/telegram/*` (server-side) and the bot deep-link callback; mismatched/missing token → 403

### RBAC (Server-side)

- [ ] **RBAC-01**: `app/core/permissions.py` defines `Role`, `Action`, `Resource` `StrEnum`s and an `OWNER_ONLY: frozenset[tuple[Action, Resource]]` matrix; `can(role, action, resource)` mirrors `apps/admin-web/src/shared/session/can.ts` byte-for-byte
- [ ] **RBAC-02**: `app/core/dependencies.py` provides `get_current_user` (loads user via a registered loader; the loader is registered by `app/main.py` from `app.modules.auth.service.load_user_by_id` so `import-linter` `modules-independent` contract is preserved) and `require_permission(action, resource)`
- [ ] **RBAC-03**: Every business endpoint declares its permission via `Depends(require_permission(...))` on the route signature; `require_permission` is never invoked from inside service bodies (lint-enforced)
- [ ] **RBAC-04**: Unauthenticated requests to protected routes return 401; authenticated-but-forbidden return 403 with `DomainError { code: "forbidden", message }`; resource existence is NOT leaked (404 vs 403 must be consistent — 403 takes precedence when the user lacks read permission)
- [ ] **RBAC-05**: Reception role is denied: `view:finance|reports|payroll|compensation|settings|owner-area`, `edit:templates`, `delete:clients`, `refund:finance` (verbatim mirror of `OWNER_ONLY`)

### Clients

- [ ] **CLIENTS-01**: `clients` table schema: `id` (UUIDv4 server-default), ФИО triple (`last_name`, `first_name`, `middle_name?`), `phone` (E.164 string), `email?`, `birthday? date`, `gender?`, `tags text[]`, `notes?`, `emergency_contact? jsonb`, `telegram_user_id? bigint UNIQUE`, `created_by_user_id` FK, `created_at`, `updated_at`, `deleted_at?`
- [ ] **CLIENTS-02**: Phone uniqueness is enforced by a partial unique index `WHERE deleted_at IS NULL` so soft-deleted phones don't block reuse
- [ ] **CLIENTS-03**: Search/filter list `GET /api/v1/clients` returns `{items, total, page, pageSize}`; supports `q=` ILIKE on `last_name + first_name + middle_name + phone` (using `pg_trgm` GIN indexes on `lower(last_name)` and `lower(first_name)`)
- [ ] **CLIENTS-04**: List supports filters by `tag`, `gender`, signup-date range (`createdFrom`, `createdTo`), `hasTelegram`; sort by `created_at DESC` (default) or `last_name ASC`
- [ ] **CLIENTS-05**: `GET /api/v1/clients/{id}` returns a single client; soft-deleted clients return 404
- [ ] **CLIENTS-06**: `POST /api/v1/clients` creates a client; required: `lastName`, `firstName`, `phone`; phone validated as E.164
- [ ] **CLIENTS-07**: `PATCH /api/v1/clients/{id}` partial-updates a client; reception cannot edit owner-only fields if any are introduced later
- [ ] **CLIENTS-08**: `DELETE /api/v1/clients/{id}` is owner-only and is a soft-delete (sets `deleted_at`); hard delete is never exposed
- [ ] **CLIENTS-09**: All clients queries go through repository helpers (`list_alive`, `get_alive`) that enforce `deleted_at IS NULL` so the filter cannot be forgotten by the service layer

### Audit Log

- [ ] **AUDIT-01**: `audit_log` table stores `{id, actor_user_id, action, resource_type, resource_id, payload jsonb, created_at}`; ON DELETE RESTRICT on the actor FK
- [ ] **AUDIT-02**: Audit writes are emitted from auth flows (`login_success`, `logout`, `otp_issued`, `otp_consumed`, `session_revoked`, `family_reuse_detected`) and clients mutations (`client_created`, `client_updated`, `client_soft_deleted`)
- [ ] **AUDIT-03**: Audit read endpoint is **out of scope for v1.1** — table exists, writes happen, no `GET /audit-log` is exposed (deferred to v1.2)

### API Surface (OpenAPI + packages/api-client)

- [ ] **API-01**: `apps/backend/scripts/export_openapi.py` calls `create_app().openapi()` (lifespan-safe, no DB required) and writes `apps/backend/openapi.json` with deterministic byte-stable output (`indent=2, sort_keys=True`)
- [ ] **API-02**: CI step regenerates `openapi.json` and runs `git diff --exit-code` to block drift between code and the checked-in spec
- [ ] **API-03**: Backend wire format is **camelCase** via Pydantic `alias_generator=to_camel` + `populate_by_name=True` on a base response/request model; Python identifiers stay snake_case internally
- [ ] **API-04**: Pagination envelope is `{items, total, page, pageSize}`; `app/core/pagination.py` is updated to the new shape (replaces v1.0 `limit/offset`); frontend contract becomes the single source of truth
- [ ] **API-05**: `packages/api-client` adds `openapi-typescript@^7.13.0` as a devDependency and a `codegen` script that produces `src/schema.d.ts` (committed to git per Phase 9 D-07 — required for API-07 drift-gate to be meaningful) from `apps/backend/openapi.json`
- [ ] **API-06**: `packages/api-client/src/fetcher.ts` (~80 LOC) exposes `request<P, M>(method, path, init)` with `credentials: 'include'`, automatic `X-CSRF-Token` injection, typed `ApiError` with `code/message/fields`, and module-scoped single-flight `/auth/refresh` on 401
- [ ] **API-07**: CI step runs `pnpm --filter @sportzal/api-client codegen && git diff --exit-code` to block schema drift

### Frontend Wiring (admin-web)

- [x] **FE-01**: `apps/admin-web/src/shared/api/services/http/auth.ts` and `http/clients.ts` implement the existing service contracts using `@sportzal/api-client`; mock services for other domains remain untouched
- [ ] **FE-02**: `apps/admin-web/src/features/auth/*` provides a `/login` route with two tabs (email/password, Telegram OTP); the Telegram tab polls the status endpoint and prompts for the code once the chat is bound
- [ ] **FE-03**: `VITE_API_MODE=http` is wired only for `/login` and `/clients/*` routes via the existing swap seam; running `VITE_API_MODE=mock` keeps the legacy mock behavior for those routes (no regression)
- [x] **FE-04**: TanStack Query hooks for clients use a `clientsKeys` factory; route loaders call `queryClient.ensureQueryData` with the same keys; mutations use `onMutate`/`onError`/`onSettled` for optimistic updates with rollback
- [ ] **FE-05**: On 401 the fetch wrapper attempts a single-flight refresh; on refresh failure it redirects to `/login?next=<encoded-from>` (one-shot module flag prevents redirect loops); successful login restores the original location
- [ ] **FE-06**: Logout clears the TanStack Query cache and redirects to `/login`
- [ ] **FE-07**: ESLint rule bans direct `fetch(` outside `packages/api-client/src/` and `apps/admin-web/src/shared/api/services/http/`; a negative-test fixture keeps the rule honest

### Tests

- [ ] **TEST-01**: pytest fixture `db_session` uses SAVEPOINT-based per-test rollback against a real Postgres (the docker-compose service); per-test isolation is maintained without dropping the schema between tests
- [ ] **TEST-02**: Email/password integration tests: 200 happy, 401 invalid credentials, 429 rate-limited; `set-cookie` headers verified for `Path`, `HttpOnly`, `SameSite`
- [ ] **TEST-03**: Telegram OTP integration tests use a stubbed `integrations.telegram.sender` (records calls, returns success/failure deterministically): happy `start → bot stub → verify`; expired OTP / wrong code / max-attempts; 409 `bot_not_started` path
- [ ] **TEST-04**: Refresh-rotation integration tests: happy rotation; reuse → family revocation + 401 + audit `family_reuse_detected`; reuse-window race returns the same pair
- [ ] **TEST-05**: RBAC integration tests: 401 unauth on protected route; reception → 403 on every entry in `OWNER_ONLY`; owner → 200 happy
- [ ] **TEST-06**: Parity test reads both `apps/backend/app/core/permissions.py` and `apps/admin-web/src/shared/session/can.ts` and asserts the `OWNER_ONLY` matrices are equal as sets of `(action, resource)` pairs
- [ ] **TEST-07**: Route-introspection test enumerates `app.routes` and asserts every business endpoint (excluding `/healthz`, `/auth/login`, `/auth/telegram/*`, `/auth/refresh`) declares a `require_permission` dependency
- [ ] **TEST-08**: Alembic acceptance: on a clean Postgres, run all migrations to head; then `alembic check` (autogenerate-on-clean) must produce an empty diff — guards against missing naming-convention or model/migration drift

## v1.2 Requirements (Deferred)

Not committed to v1.1 roadmap, but acknowledged for the next milestone.

### Auth (continued)

- **AUTH-V12-01**: Active-sessions UI for the current user (list devices, revoke individual sessions)
- **AUTH-V12-02**: Password reset via Telegram bot DM (no email link in v1)
- **AUTH-V12-03**: HaveIBeenPwned password check on registration / change
- **AUTH-V12-04**: Webhook-based Telegram bot mode for production (long-polling stays in dev)

### Audit

- **AUDIT-V12-01**: `GET /api/v1/audit-log` endpoint with pagination + filters (owner-only)
- **AUDIT-V12-02**: Audit log read UI in admin-web

### Clients (continued)

- **CLIENTS-V12-01**: Photo upload + storage strategy
- **CLIENTS-V12-02**: Bulk CSV import (validation, dry-run, partial-success report)
- **CLIENTS-V12-03**: "Last visit" filter (depends on visits module)
- **CLIENTS-V12-04**: Client tags taxonomy management (CRUD on tags)

## Out of Scope

Explicit exclusions. Documented to prevent scope creep and to make the rejection auditable.

| Feature | Reason |
|---------|--------|
| Public self-registration (`POST /auth/register`) | Single-gym pet project; one owner user is seeded by script |
| SMS OTP | Cost + RU regulation burden; Telegram is the regional primary channel per PROJECT.md |
| Telegram Login Widget | Requires public HTTPS domain; bot deep-link works in docker-compose dev without ngrok |
| Email password reset | Email integration deferred; password reset will go through Telegram in v1.2 |
| Forced password rotation | Counter-productive per NIST 800-63B 2024 |
| Password complexity rules (uppercase/digits/symbols) | Counter-productive per NIST 800-63B 2024; min-length only |
| Account lockout (vs rate limit) | DoS amplifier per OWASP; rate-limit is the safer pattern |
| CAPTCHA / Turnstile | Premature for a 1-2 user system |
| LocalStorage tokens | XSS-vulnerable; cookies-only is the v1.1 contract |
| Stateless-only JWT (no DB session) | Cannot revoke; family rotation needs DB anyway |
| Hard delete of clients | Audit / compliance — soft-delete only |
| Custom field schema for clients | Premature; fixed columns + `tags`/`notes`/`emergency_contact jsonb` cover v1.1 |
| Full-text search (Elasticsearch / tsvector) | Overkill at gym scale; ILIKE + `pg_trgm` is enough |
| Saved filters / shared views | Premature; URL-based query state is enough |
| CSV export of clients | Defer to v1.2+ |
| Policy engine (Casbin / Oso / OPA) | 9-entry static matrix; an `if`-statement is the correct tool |
| Dynamic role creation | `Role = 'owner' \| 'reception'` is locked at compile time |
| Multi-tenancy / `tenant_id` / RLS / `SET LOCAL` | Pet project on 1 zal — explicit Out of Scope from PROJECT.md |
| Stripe integration | RU region — forbidden in this project forever |
| `apps/client-web` (member-facing app) | Phase J or later — not until admin side is solid |
| Kubernetes / Terraform / production deploy | Dev docker-compose only |
| MFA beyond Telegram OTP (TOTP, WebAuthn) | Telegram OTP is already a second factor when paired with email/password |
| OAuth scopes | Two static roles; scopes would be ceremony |
| Separate IAM service | Modular monolith — one process |
| `audit_log` read endpoint / UI | Deferred to v1.2; table + writes ship in v1.1 |

## Traceability

REQ-ID → Phase mapping populated by `/gsd-roadmapper` on 2026-05-01.

| Requirement | Phase | Status |
|-------------|-------|--------|
| INFRA-01 | Phase 4 | Pending |
| INFRA-02 | Phase 4 | Pending |
| INFRA-03 | Phase 5 | Pending |
| INFRA-04 | Phase 8 | Pending |
| INFRA-05 | Phase 4 | Pending |
| INFRA-06 | Phase 7 | Pending |
| INFRA-07 | Phase 4 | Pending |
| AUTH-01 | Phase 4 | Pending |
| AUTH-02 | Phase 4 | Pending |
| AUTH-03 | Phase 4 | Pending |
| AUTH-04 | Phase 4 | Pending |
| AUTH-05 | Phase 5 | Pending |
| AUTH-06 | Phase 5 | Pending |
| AUTH-07 | Phase 5 | Pending |
| AUTH-EP-01 | Phase 5 | Pending |
| AUTH-EP-02 | Phase 5 | Pending |
| AUTH-EP-03 | Phase 5 | Pending |
| AUTH-EP-04 | Phase 5 | Pending |
| AUTH-EP-05 | Phase 5 | Pending |
| AUTH-TG-01 | Phase 7 | Pending |
| AUTH-TG-02 | Phase 7 | Pending |
| AUTH-TG-03 | Phase 7 | Pending |
| AUTH-TG-04 | Phase 7 | Pending |
| AUTH-TG-05 | Phase 7 | Pending |
| AUTH-TG-06 | Phase 7 | Pending |
| AUTH-LO-01 | Phase 5 | Pending |
| AUTH-LO-02 | Phase 5 | Pending |
| AUTH-LO-03 | Phase 5 | Pending |
| AUTH-LO-04 | Phase 5 | Pending |
| CSRF-01 | Phase 4 | Pending |
| CSRF-02 | Phase 6 | Pending |
| RBAC-01 | Phase 4 | Pending |
| RBAC-02 | Phase 6 | Pending |
| RBAC-03 | Phase 6 | Pending |
| RBAC-04 | Phase 6 | Pending |
| RBAC-05 | Phase 6 | Pending |
| CLIENTS-01 | Phase 8 | Pending |
| CLIENTS-02 | Phase 8 | Pending |
| CLIENTS-03 | Phase 8 | Pending |
| CLIENTS-04 | Phase 8 | Pending |
| CLIENTS-05 | Phase 8 | Pending |
| CLIENTS-06 | Phase 8 | Pending |
| CLIENTS-07 | Phase 8 | Pending |
| CLIENTS-08 | Phase 8 | Pending |
| CLIENTS-09 | Phase 8 | Pending |
| AUDIT-01 | Phase 8 | Pending |
| AUDIT-02 | Phase 8 | Pending |
| AUDIT-03 | Phase 8 | Pending |
| API-01 | Phase 9 | Pending |
| API-02 | Phase 9 | Pending |
| API-03 | Phase 4 | Pending |
| API-04 | Phase 4 | Pending |
| API-05 | Phase 9 | Pending |
| API-06 | Phase 9 | Pending |
| API-07 | Phase 9 | Pending |
| FE-01 | Phase 10 | Complete |
| FE-02 | Phase 10 | Pending |
| FE-03 | Phase 10 | Pending |
| FE-04 | Phase 10 | Complete |
| FE-05 | Phase 10 | Pending |
| FE-06 | Phase 10 | Pending |
| FE-07 | Phase 10 | Pending |
| TEST-01 | Phase 5 | Pending |
| TEST-02 | Phase 5 | Pending |
| TEST-03 | Phase 7 | Pending |
| TEST-04 | Phase 5 | Pending |
| TEST-05 | Phase 6 | Pending |
| TEST-06 | Phase 6 | Pending |
| TEST-07 | Phase 6 | Pending |
| TEST-08 | Phase 5 | Pending |

**Coverage:**
- v1.1 requirements: 70 total
- Mapped to phases: 70 ✓
- Unmapped: 0

**Distribution:**
- Phase 4 (Auth Foundations): 12 requirements
- Phase 5 (User Schema + Email/Password): 17 requirements
- Phase 6 (RBAC Wiring + Parity Tests): 8 requirements
- Phase 7 (Telegram OTP Channel): 8 requirements
- Phase 8 (Clients Module + Audit Log): 13 requirements
- Phase 9 (OpenAPI Pipeline + api-client): 5 requirements
- Phase 10 (admin-web Auth + Clients Wiring): 7 requirements

---
*Requirements defined: 2026-05-01*
*Last updated: 2026-05-01 — traceability populated after roadmap approval (phases 4-10)*
